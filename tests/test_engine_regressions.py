# -*- coding: utf-8 -*-
"""真实引擎回归：用系统 HarfBuzz / FreeType 验证合并出口的布局与加载行为。

设计要点：
  * 不引入 uharfbuzz / hb-shape / ots / pytest；只用 stdlib ctypes 调用
    系统已安装的 libharfbuzz.so.0 与 libfreetype.so.6；
  * 字体全部由 FontBuilder + feaLib 现场构造，中性命名、无磁盘字体依赖；
  * 每个 ctypes 函数显式设置 argtypes/restype；HarfBuzz 的 blob/face/font/
    buffer 与 FreeType 的 memory face 都保持底层 bytes 存活到销毁之后，
    避免引擎持有悬空指针；
  * 系统库缺失时用例打印 SKIP 后正常返回（本机应无 SKIP）。

覆盖内容：
  1. GSUB 上下文（Context/ChainContext）从打底追加后，其 nested lookup
     必须实际执行（对照把引用错指到主/诱饵 lookup 时的输出）；
  2. GPOS 主字体 kern 的每个字对增量逐值保留，打底不相交字对也生效；
  3. 多个来源在不同 script 下使用同 tag feature 时互不污染；
  4. FreeType 能加载「采用打底 hint 资源」与「剥离新字形指令」两种合并结果，
     FT_Load_Glyph 对全部字形返回 0。
"""
import copy
import ctypes
import os
import sys
from array import array
from io import BytesIO

_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
sys.path.insert(0, _project_dir)   # FontMerger 包
sys.path.insert(0, _repo_dir)      # tests.*

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.ttProgram import Program

from FontMerger import FontMerger


_UPEM = 1000
_HB_LIBRARY = "libharfbuzz.so.0"
_FT_LIBRARY = "libfreetype.so.6"
#: hb_memory_mode_t: HB_MEMORY_MODE_DUPLICATE（copy 一份，防调用方释放）
_HB_MEMORY_MODE_DUPLICATE = 1
#: hb_direction_t: HB_DIRECTION_LTR
_HB_DIRECTION_LTR = 4
#: hb_feature_t 的全局生效区间
_HB_FEATURE_END = 0xFFFFFFFF
#: FT_LOAD_* 标志
_FT_LOAD_DEFAULT = 0
_FT_LOAD_NO_HINTING = 2
#: glyph program 最小合法字节码：PUSHB[ ] 0; POP（无副作用）
_NOOP_PROGRAM = b"\xb0\x00\x21"


# ---------------------------------------------------------------------------
# HarfBuzz ctypes 绑定
# ---------------------------------------------------------------------------
class _HbGlyphInfo(ctypes.Structure):
    """hb_glyph_info_t（20 字节，var1/var2 只按 u32 看待）。"""
    _fields_ = [("codepoint", ctypes.c_uint32),
                ("mask", ctypes.c_uint32),
                ("cluster", ctypes.c_uint32),
                ("var1", ctypes.c_uint32),
                ("var2", ctypes.c_uint32)]


class _HbGlyphPosition(ctypes.Structure):
    """hb_glyph_position_t（20 字节）。"""
    _fields_ = [("x_advance", ctypes.c_int32),
                ("y_advance", ctypes.c_int32),
                ("x_offset", ctypes.c_int32),
                ("y_offset", ctypes.c_int32),
                ("var", ctypes.c_uint32)]


class _HbFeature(ctypes.Structure):
    """hb_feature_t。"""
    _fields_ = [("tag", ctypes.c_uint32),
                ("value", ctypes.c_uint32),
                ("start", ctypes.c_uint32),
                ("end", ctypes.c_uint32)]


_HB_STATE = {"tried": False, "lib": None, "error": None}


def _bind_harfbuzz():
    """加载 libharfbuzz 并显式声明全部用到的函数签名。"""
    try:
        lib = ctypes.CDLL(_HB_LIBRARY)
    except OSError as error:
        _HB_STATE["error"] = str(error)
        return None
    # 版本/生命周期
    lib.hb_version_string.restype = ctypes.c_char_p
    lib.hb_version_string.argtypes = []
    lib.hb_blob_create.restype = ctypes.c_void_p
    lib.hb_blob_create.argtypes = [ctypes.c_char_p, ctypes.c_uint,
                                   ctypes.c_int, ctypes.c_void_p,
                                   ctypes.c_void_p]
    lib.hb_blob_destroy.restype = None
    lib.hb_blob_destroy.argtypes = [ctypes.c_void_p]
    lib.hb_face_create.restype = ctypes.c_void_p
    lib.hb_face_create.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    lib.hb_face_destroy.restype = None
    lib.hb_face_destroy.argtypes = [ctypes.c_void_p]
    lib.hb_font_create.restype = ctypes.c_void_p
    lib.hb_font_create.argtypes = [ctypes.c_void_p]
    lib.hb_font_destroy.restype = None
    lib.hb_font_destroy.argtypes = [ctypes.c_void_p]
    lib.hb_font_set_scale.restype = None
    lib.hb_font_set_scale.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                      ctypes.c_int]
    lib.hb_font_set_ppem.restype = None
    lib.hb_font_set_ppem.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.c_uint]
    lib.hb_ot_font_set_funcs.restype = None
    lib.hb_ot_font_set_funcs.argtypes = [ctypes.c_void_p]
    # buffer / shape
    lib.hb_buffer_create.restype = ctypes.c_void_p
    lib.hb_buffer_create.argtypes = []
    lib.hb_buffer_destroy.restype = None
    lib.hb_buffer_destroy.argtypes = [ctypes.c_void_p]
    lib.hb_buffer_add_codepoints.restype = None
    lib.hb_buffer_add_codepoints.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
        ctypes.c_uint, ctypes.c_int]
    lib.hb_buffer_set_direction.restype = None
    lib.hb_buffer_set_direction.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.hb_buffer_set_script.restype = None
    lib.hb_buffer_set_script.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.hb_script_from_string.restype = ctypes.c_uint32
    lib.hb_script_from_string.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib.hb_shape.restype = None
    lib.hb_shape.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                             ctypes.POINTER(_HbFeature), ctypes.c_uint]
    lib.hb_buffer_get_glyph_infos.restype = ctypes.POINTER(_HbGlyphInfo)
    lib.hb_buffer_get_glyph_infos.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    lib.hb_buffer_get_glyph_positions.restype = ctypes.POINTER(
        _HbGlyphPosition)
    lib.hb_buffer_get_glyph_positions.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    return lib


def _harfbuzz():
    """单例加载；缺失时返回 None 并记录原因供 SKIP 使用。"""
    if not _HB_STATE["tried"]:
        _HB_STATE["tried"] = True
        _HB_STATE["lib"] = _bind_harfbuzz()
    return _HB_STATE["lib"]


def _hb_version(lib):
    """HarfBuzz 版本字符串（bytes → str）。"""
    raw = lib.hb_version_string()
    return raw.decode("ascii", "replace") if raw else "unknown"


def _hb_shape(lib, font_bytes, codepoints, script=None, features=None):
    """调用真实 hb_shape；返回 [(gid, cluster, x_adv, y_adv, x_off)]。

    font_bytes 在函数内保持引用到引擎对象销毁之后（blob 也使用 DUPLICATE
    模式），避免 HarfBuzz 持有已释放的 Python bytes。
    """
    data = bytes(font_bytes)
    blob = lib.hb_blob_create(data, len(data), _HB_MEMORY_MODE_DUPLICATE,
                              None, None)
    assert blob, "hb_blob_create 失败"
    face = lib.hb_face_create(blob, 0)
    assert face, "hb_face_create 失败"
    font = lib.hb_font_create(face)
    assert font, "hb_font_create 失败"
    lib.hb_ot_font_set_funcs(font)
    lib.hb_font_set_scale(font, _UPEM, _UPEM)
    lib.hb_font_set_ppem(font, _UPEM, _UPEM)
    buffer = lib.hb_buffer_create()
    assert buffer, "hb_buffer_create 失败"
    try:
        codepoint_array = (ctypes.c_uint32 * len(codepoints))(*codepoints)
        lib.hb_buffer_add_codepoints(buffer, codepoint_array,
                                     len(codepoints), 0, len(codepoints))
        lib.hb_buffer_set_direction(buffer, _HB_DIRECTION_LTR)
        if script is not None:
            script_tag = lib.hb_script_from_string(
                script.encode("ascii"), -1)
            lib.hb_buffer_set_script(buffer, script_tag)
        feature_array = None
        feature_count = 0
        if features:
            feature_array = (_HbFeature * len(features))()
            for index, (tag, value) in enumerate(features):
                feature_array[index].tag = int.from_bytes(
                    tag.encode("ascii"), "big")
                feature_array[index].value = value
                feature_array[index].start = 0
                feature_array[index].end = _HB_FEATURE_END
            feature_count = len(features)
        lib.hb_shape(font, buffer, feature_array, feature_count)
        length = ctypes.c_uint(0)
        infos = lib.hb_buffer_get_glyph_infos(buffer, ctypes.byref(length))
        positions = lib.hb_buffer_get_glyph_positions(
            buffer, ctypes.byref(length))
        result = []
        for index in range(length.value):
            result.append((infos[index].codepoint, infos[index].cluster,
                           positions[index].x_advance,
                           positions[index].y_advance,
                           positions[index].x_offset))
        return result
    finally:
        # bytes 与所有引擎对象都在同一作用域内，销毁后再离开。
        lib.hb_buffer_destroy(buffer)
        lib.hb_font_destroy(font)
        lib.hb_face_destroy(face)
        lib.hb_blob_destroy(blob)
        del data


def _shape_names(lib, font_bytes, codepoints, script=None, features=None):
    """按合并字体的 GlyphOrder 把 hb_shape 的 gid 换成字形名。"""
    order = TTFont(BytesIO(font_bytes)).getGlyphOrder()
    shaped = _hb_shape(lib, font_bytes, codepoints, script, features)
    return [order[gid] for gid, _cluster, _xa, _ya, _xo in shaped]


def _shape_positions(lib, font_bytes, codepoints, script=None, features=None):
    """只取与字形命名无关的定位结果，便于跨字体逐值比较。"""
    shaped = _hb_shape(lib, font_bytes, codepoints, script, features)
    return [(cluster, x_advance, x_offset)
            for _gid, cluster, x_advance, _y, x_offset in shaped]


# ---------------------------------------------------------------------------
# FreeType ctypes 绑定
# ---------------------------------------------------------------------------
_FT_STATE = {"tried": False, "lib": None, "error": None}


def _bind_freetype():
    """加载 libfreetype 并显式声明全部用到的函数签名。"""
    try:
        lib = ctypes.CDLL(_FT_LIBRARY)
    except OSError as error:
        _FT_STATE["error"] = str(error)
        return None
    lib.FT_Init_FreeType.restype = ctypes.c_int
    lib.FT_Init_FreeType.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    lib.FT_Done_FreeType.restype = ctypes.c_int
    lib.FT_Done_FreeType.argtypes = [ctypes.c_void_p]
    lib.FT_New_Memory_Face.restype = ctypes.c_int
    lib.FT_New_Memory_Face.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                       ctypes.c_long, ctypes.c_long,
                                       ctypes.POINTER(ctypes.c_void_p)]
    lib.FT_Done_Face.restype = ctypes.c_int
    lib.FT_Done_Face.argtypes = [ctypes.c_void_p]
    lib.FT_Set_Pixel_Sizes.restype = ctypes.c_int
    lib.FT_Set_Pixel_Sizes.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                       ctypes.c_uint]
    lib.FT_Load_Glyph.restype = ctypes.c_int
    lib.FT_Load_Glyph.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                  ctypes.c_int]
    lib.FT_Get_Char_Index.restype = ctypes.c_uint
    lib.FT_Get_Char_Index.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    lib.FT_Library_Version.restype = None
    lib.FT_Library_Version.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    return lib


def _freetype():
    """单例加载；缺失时返回 None 并记录原因供 SKIP 使用。"""
    if not _FT_STATE["tried"]:
        _FT_STATE["tried"] = True
        _FT_STATE["lib"] = _bind_freetype()
    return _FT_STATE["lib"]


def _ft_load_all(lib, font_bytes, glyph_count):
    """从内存加载 face 并逐个 FT_Load_Glyph。

    Returns:
        (version_tuple, [(load_flag, gid, error_code), ...])
    """
    data = bytes(font_bytes)
    library = ctypes.c_void_p()
    error = lib.FT_Init_FreeType(ctypes.byref(library))
    assert error == 0, "FT_Init_FreeType 返回 %d" % error
    face = ctypes.c_void_p()
    try:
        error = lib.FT_New_Memory_Face(library, data, len(data), 0,
                                       ctypes.byref(face))
        assert error == 0, "FT_New_Memory_Face 返回 %d" % error
        major = ctypes.c_int(0)
        minor = ctypes.c_int(0)
        patch = ctypes.c_int(0)
        lib.FT_Library_Version(library, ctypes.byref(major),
                               ctypes.byref(minor), ctypes.byref(patch))
        version = (major.value, minor.value, patch.value)
        error = lib.FT_Set_Pixel_Sizes(face, 0, 32)
        assert error == 0, "FT_Set_Pixel_Sizes 返回 %d" % error
        results = []
        for flag in (_FT_LOAD_DEFAULT, _FT_LOAD_NO_HINTING):
            for gid in range(glyph_count):
                code = lib.FT_Load_Glyph(face, gid, flag)
                results.append((flag, gid, code))
        return version, results
    finally:
        # data 保持到 FT_Done_Face 之后；FT 不复制 memory face 的缓冲区。
        if face.value:
            lib.FT_Done_Face(face)
        lib.FT_Done_FreeType(library)
        del data


def _ft_char_index(lib, font_bytes, codepoint):
    """FT_Get_Char_Index 的独立封装（同样保持 bytes 存活）。"""
    data = bytes(font_bytes)
    library = ctypes.c_void_p()
    assert lib.FT_Init_FreeType(ctypes.byref(library)) == 0
    face = ctypes.c_void_p()
    try:
        assert lib.FT_New_Memory_Face(library, data, len(data), 0,
                                      ctypes.byref(face)) == 0
        return lib.FT_Get_Char_Index(face, codepoint)
    finally:
        if face.value:
            lib.FT_Done_Face(face)
        lib.FT_Done_FreeType(library)
        del data


# ---------------------------------------------------------------------------
# 最小中性字体夹具（FontBuilder + feaLib）
# ---------------------------------------------------------------------------
def _build_font(glyphs, cmap, fea="", hint_globals=False,
                glyph_programs=None):
    """构造完整最小 TTF；可选打底侧全局 hint 资源与逐字形指令。"""
    builder = FontBuilder(_UPEM, isTTF=True)
    builder.setupGlyphOrder(glyphs)
    builder.setupCharacterMap(cmap)
    glyph_dict = {}
    for name in glyphs:
        pen = TTGlyphPen(None)
        if name != ".notdef":
            pen.moveTo((20, 0))
            pen.lineTo((400, 0))
            pen.lineTo((400, 700))
            pen.closePath()
        glyph = pen.glyph()
        program = (glyph_programs or {}).get(name)
        if program is not None:
            instructions = Program()
            instructions.fromBytecode(program)
            glyph.program = instructions
        glyph_dict[name] = glyph
    builder.setupGlyf(glyph_dict)
    builder.setupHorizontalMetrics(
        dict((name, (600, 20)) for name in glyphs))
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "Engine Regression",
                            "styleName": "Regular",
                            "psName": "EngineRegression-Regular"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200,
                     usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    if hint_globals:
        fpgm = newTable("fpgm")
        fpgm.program = Program()
        fpgm.program.fromBytecode(b"")
        builder.font["fpgm"] = fpgm
        prep = newTable("prep")
        prep.program = Program()
        prep.program.fromBytecode(_NOOP_PROGRAM)
        builder.font["prep"] = prep
        cvt = newTable("cvt ")
        # fontTools 的 cvt compile 直接对 values 做 array.byteswap()
        cvt.values = array("h", [0, 0])
        builder.font["cvt "] = cvt
    if fea:
        addOpenTypeFeaturesFromString(builder.font, fea)
    return builder.font


def _font_bytes(font):
    """内存序列化，不落盘；引擎读取的始终是编译后的二进制。"""
    stream = BytesIO()
    font.save(stream)
    return stream.getvalue()


def _merge(main, base):
    """走完整合并入口（静态 TTF × 静态 TTF），输入传副本。"""
    merger = FontMerger()
    return merger.merge_two(copy.deepcopy(main), copy.deepcopy(base))


def _roundtrip(font):
    """保存并重载，确保引擎验证的是真实可编译产物。"""
    data = _font_bytes(font)
    reloaded = TTFont(BytesIO(data))
    return reloaded, _font_bytes(reloaded)


def _skip(test_name, lib_name, error):
    print("  %s: SKIP (%s 缺失: %s)" % (test_name, lib_name, error))


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------
def test_engine_bindings_smoke():
    """最小绑定冒烟：两个引擎都能加载并处理同一份中性字体。"""
    hb = _harfbuzz()
    ft = _freetype()
    if hb is None:
        _skip("test_engine_bindings_smoke", _HB_LIBRARY, _HB_STATE["error"])
        return
    if ft is None:
        _skip("test_engine_bindings_smoke", _FT_LIBRARY, _FT_STATE["error"])
        return
    # 复用 tests/test_invariants.py 的 _font：固定 5 字形 / 600 advance。
    from tests.test_invariants import _font
    font = _font()
    data = _font_bytes(font)
    shaped = _hb_shape(hb, data, [65, 66], script="Latn")
    assert len(shaped) == 2, shaped
    assert [item[0] for item in shaped] == [1, 2], shaped
    assert [item[2] for item in shaped] == [600, 600], shaped
    glyph_count = len(TTFont(BytesIO(data)).getGlyphOrder())
    version, results = _ft_load_all(ft, data, glyph_count)
    bad = [item for item in results if item[2] != 0]
    assert not bad, bad
    print("  test_engine_bindings_smoke: hb %s, ft %d.%d.%d, "
          "%d 字形 × 2 加载模式" % (_hb_version(hb), version[0], version[1],
                                    version[2], glyph_count))


def test_gsub_context_nested_lookup():
    """打底 Context 追加后 nested lookup 必须按重映射后的目标实际执行。

    打底 GSUB 图：DECOY(q→q.alt) 归 calt；INNER(q→q.alt2) 只被
    ChainContext 嵌套引用；liga 里的上下文规则引用 INNER。合并后
    hb_shape("qx") 必须以 q.alt2 出字；若嵌套索引错指到 DECOY（或主
    lookup），结果会变成 q.alt——用实际引擎输出区分，而不是只看索引范围。
    """
    hb = _harfbuzz()
    if hb is None:
        _skip("test_gsub_context_nested_lookup", _HB_LIBRARY,
              _HB_STATE["error"])
        return
    main = _build_font(
        [".notdef", "A", "A.alt"], {65: "A"},
        "languagesystem latn dflt; "
        "feature salt { sub A by A.alt; } salt;")
    base = _build_font(
        [".notdef", "q", "q.alt", "q.alt2", "x"], {113: "q", 120: "x"},
        "languagesystem latn dflt; "
        "lookup DECOY { sub q by q.alt; } DECOY; "
        "lookup INNER { sub q by q.alt2; } INNER; "
        "feature calt { lookup DECOY; } calt; "
        "feature liga { sub q' lookup INNER x; } liga;")
    merged, data = _roundtrip(_merge(main, base))
    features = [("calt", 0), ("liga", 1)]
    names = _shape_names(hb, data, [113, 120], "Latn", features)
    assert names == ["q.alt2", "x"], names

    # 负对照 1：把嵌套引用改指到 DECOY，真实引擎输出必须随之改变，
    # 证明本用例不是"只要索引在范围内就通过"。
    broken = copy.deepcopy(merged)
    context_lookup = None
    decoy_index = None
    main_index = None
    for index, lookup in enumerate(broken["GSUB"].table.LookupList.Lookup):
        for subtable in lookup.SubTable:
            records = getattr(subtable, "SubstLookupRecord", None)
            if records:
                context_lookup = records[0]
            mapping = getattr(subtable, "mapping", None)
            if mapping and dict(mapping) == {"q": "q.alt"}:
                decoy_index = index
            if mapping and dict(mapping) == {"A": "A.alt"}:
                main_index = index
    assert context_lookup is not None, "合并结果里找不到上下文动作"
    assert decoy_index is not None, "合并结果里找不到诱饵 lookup"
    assert main_index is not None, "合并结果里找不到主 lookup"
    correct_index = context_lookup.LookupListIndex
    assert correct_index != decoy_index, (correct_index, decoy_index)
    assert correct_index != main_index, (correct_index, main_index)
    context_lookup.LookupListIndex = decoy_index
    broken_names = _shape_names(hb, _font_bytes(broken), [113, 120],
                                "Latn", features)
    assert broken_names == ["q.alt", "x"], broken_names

    # 负对照 2：错指到主字体 lookup 时，q 不归它管，序列应完全不变，
    # 用来区分"执行了正确的打底 nested lookup"与"指向主 lookup"。
    context_lookup.LookupListIndex = main_index
    main_mispoint = _shape_names(hb, _font_bytes(broken), [113, 120],
                                 "Latn", features)
    assert main_mispoint == ["q", "x"], main_mispoint

    # 主字体自己的 feature/lookup 在追加打底后仍按脚本可达。
    main_names = _shape_names(hb, data, [65], "Latn", [("salt", 1)])
    assert main_names == ["A.alt"], main_names
    print("  test_gsub_context_nested_lookup: q→%s（错指诱饵 q→%s，"
          "错指主 lookup q→%s），主 salt 保持"
          % (names[0], broken_names[0], main_mispoint[0]))


def test_gpos_kern_values_preserved():
    """主 kern 逐值保留；打底不相交字对在合并字体里也按源值生效。"""
    hb = _harfbuzz()
    if hb is None:
        _skip("test_gpos_kern_values_preserved", _HB_LIBRARY,
              _HB_STATE["error"])
        return
    main = _build_font(
        [".notdef", "A", "B", "C", "A.alt"], {65: "A", 66: "B", 67: "C"},
        "feature kern { pos A B -100; pos B C -40; } kern;")
    base = _build_font(
        [".notdef", "m", "n", "m.alt"], {109: "m", 110: "n"},
        "feature kern { pos m n -70; } kern;")
    main_data = _font_bytes(main)
    base_data = _font_bytes(base)
    _merged, merged_data = _roundtrip(_merge(main, base))
    kern = [("kern", 1)]
    for codepoints, label in (([65, 66], "AB"), ([66, 67], "BC")):
        got = _shape_positions(hb, merged_data, codepoints, "Latn", kern)
        want = _shape_positions(hb, main_data, codepoints, "Latn", kern)
        assert got == want, (label, got, want)
    ab = _shape_positions(hb, merged_data, [65, 66], "Latn", kern)
    assert ab[0][1] == 500, ab
    bc = _shape_positions(hb, merged_data, [66, 67], "Latn", kern)
    assert bc[0][1] == 560, bc
    got = _shape_positions(hb, merged_data, [109, 110], "Latn", kern)
    want = _shape_positions(hb, base_data, [109, 110], "Latn", kern)
    assert got == want, (got, want)
    assert got[0][1] == 530, got
    print("  test_gpos_kern_values_preserved: AB 500 / BC 560 / "
          "打底 mn 530（各减 100/40/70）")


def test_cross_script_same_tag_isolation():
    """主 + 两个打底在不同 script 使用同 tag liga，合并不互相污染。"""
    hb = _harfbuzz()
    if hb is None:
        _skip("test_cross_script_same_tag_isolation", _HB_LIBRARY,
              _HB_STATE["error"])
        return
    main = _build_font(
        [".notdef", "A", "A.alt"], {65: "A"},
        "languagesystem latn dflt; "
        "feature liga { sub A by A.alt; } liga;")
    donor1 = _build_font(
        [".notdef", "q", "q.alt"], {113: "q"},
        "languagesystem cyrl dflt; "
        "feature liga { sub q by q.alt; } liga;")
    donor2 = _build_font(
        [".notdef", "w", "w.alt"], {119: "w"},
        "languagesystem grek dflt; "
        "feature liga { sub w by w.alt; } liga;")
    merged = _merge(_merge(main, donor1), donor2)
    _reloaded, data = _roundtrip(merged)
    cases = [
        # (标签, 码位, 脚本, 期望字形)
        ("A@latn", 65, "Latn", "A.alt"),
        ("A@cyrl", 65, "Cyrl", "A"),
        ("q@cyrl", 113, "Cyrl", "q.alt"),
        ("q@latn", 113, "Latn", "q"),
        ("w@grek", 119, "Grek", "w.alt"),
        ("w@latn", 119, "Latn", "w"),
    ]
    for label, codepoint, script, expected in cases:
        names = _shape_names(hb, data, [codepoint], script)
        assert names == [expected], (label, names)
    print("  test_cross_script_same_tag_isolation: 3 script × 各自/交叉 "
          "= 6 组，替换只在本 script 生效")


def test_freetype_hint_bundle_loads():
    """主无 hint、打底带 hint：合并采用打底全局程序，FreeType 可加载。"""
    ft = _freetype()
    if ft is None:
        _skip("test_freetype_hint_bundle_loads", _FT_LIBRARY,
              _FT_STATE["error"])
        return
    main = _build_font([".notdef", "M"], {77: "M"})
    base = _build_font(
        [".notdef", "H"], {72: "H"}, hint_globals=True,
        glyph_programs={"H": _NOOP_PROGRAM})
    _reloaded, data = _roundtrip(_merge(main, base))
    font = TTFont(BytesIO(data))
    for tag in ("fpgm", "prep", "cvt "):
        assert tag in font, "合并结果缺少打底 hint 资源 %r" % tag
    program = getattr(font["glyf"]["H"], "program", None)
    assert program is not None and bytes(program.getBytecode()), \
        "新增字形的指令没有保留"
    version, results = _ft_load_all(ft, data, len(font.getGlyphOrder()))
    bad = [item for item in results if item[2] != 0]
    assert not bad, bad
    char_index = _ft_char_index(ft, data, 72)
    assert char_index != 0, "FT_Get_Char_Index('H') = 0"
    print("  test_freetype_hint_bundle_loads: ft %d.%d.%d, hint 资源 "
          "3 张, %d 字形 × 2 加载模式全 0" % (version[0], version[1],
                                              version[2],
                                              len(font.getGlyphOrder())))


def test_freetype_stripped_font_loads():
    """主已有全局程序、打底仅字形指令：剥离新指令后 FreeType 仍可加载。"""
    ft = _freetype()
    if ft is None:
        _skip("test_freetype_stripped_font_loads", _FT_LIBRARY,
              _FT_STATE["error"])
        return
    main = _build_font([".notdef", "M"], {77: "M"}, hint_globals=True)
    base = _build_font(
        [".notdef", "H"], {72: "H"},
        glyph_programs={"H": _NOOP_PROGRAM})
    _reloaded, data = _roundtrip(_merge(main, base))
    font = TTFont(BytesIO(data))
    assert "prep" in font, "主字体的全局程序被误删"
    program = getattr(font["glyf"]["H"], "program", None)
    bytecode = bytes(program.getBytecode()) if program is not None else b""
    assert not bytecode, "不安全的打底字形指令没有被剥离"
    version, results = _ft_load_all(ft, data, len(font.getGlyphOrder()))
    bad = [item for item in results if item[2] != 0]
    assert not bad, bad
    print("  test_freetype_stripped_font_loads: ft %d.%d.%d, 新字形指令 "
          "0 字节, %d 字形 × 2 加载模式全 0" % (version[0], version[1],
                                                version[2],
                                                len(font.getGlyphOrder())))


def main():
    tests = [
        test_engine_bindings_smoke,
        test_gsub_context_nested_lookup,
        test_gpos_kern_values_preserved,
        test_cross_script_same_tag_isolation,
        test_freetype_hint_bundle_loads,
        test_freetype_stripped_font_loads,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print("  %s: PASSED" % test.__name__)
        except Exception:
            import traceback
            traceback.print_exc()
    print("Results: %d/%d passed" % (passed, len(tests)))
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
