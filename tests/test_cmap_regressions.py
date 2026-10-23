# -*- coding: utf-8 -*-
"""合成字体回归：码位优先级、子表同步、UVS、组件与 CID。"""
import copy
import io
import os
import sys
import traceback
import tempfile

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
sys.path.insert(0, _project_dir)

from FontMerger.core.conflict import (plan_alias, resolve_conflicts,
                                      _plan_merge_aliases)
from FontMerger.core.glyph_rename import renamed_copy, rename_glyphs
from FontMerger.core.glyph_copy import (merge_glyphs_via_ttx,
                                        _copy_cmap_mappings, inject_glyphs_xml)
from FontMerger.format.cid_merge import (shift_cid_range,
                                         cid_ufo_style_merge)


def _font(cmap, widths=None, components=None, cff=False):
    widths = widths or {}
    components = components or {}
    names = set(cmap.values()) | set(widths) | set(components)
    order = [".notdef"] + sorted(names - {".notdef"})
    fb = FontBuilder(1000, isTTF=not cff)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    if cff:
        charstrings = {}
        for gn in order:
            pen = T2CharStringPen(500, None)
            pen.moveTo((0, 0))
            pen.lineTo((widths.get(gn, 100), 0))
            pen.lineTo((0, 100))
            pen.closePath()
            charstrings[gn] = pen.getCharString()
        fb.setupCFF("NeutralTest-Regular", {}, charstrings, {})
    else:
        glyphs = {}
        for gn in order:
            pen = TTGlyphPen(None)
            if gn in components:
                pen.addComponent(components[gn], (1, 0, 0, 1, 0, 0))
                pen.glyphSet = {components[gn]: object()}
            else:
                pen.moveTo((0, 0))
                pen.lineTo((widths.get(gn, 100), 0))
                pen.lineTo((0, 100))
                pen.closePath()
            glyphs[gn] = pen.glyph()
        fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({gn: (widths.get(gn, 500), 0)
                               for gn in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Neutral Test",
                       "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200,
                usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    fb.setupMaxp()
    return fb.font


def _reload(font):
    stream = io.BytesIO()
    font.save(stream)
    stream.seek(0)
    return TTFont(stream)


def _uvs(font, entries):
    table = CmapSubtable.newSubtable(14)
    table.platformID = 0
    table.platEncID = 5
    table.language = 0
    table.cmap = {}
    table.uvsDict = entries
    font["cmap"].tables.append(table)


def _merge(main, base, use_ttx=False):
    ren = _plan_merge_aliases(main, base)
    base = renamed_copy(base, ren)
    conflicts = resolve_conflicts(main, base)
    known = set(main.getGlyphOrder())
    added = [gn for gn in base.getGlyphOrder()
             if gn not in conflicts and gn not in known]
    return _reload(merge_glyphs_via_ttx(main, base, added, use_ttx))


def test_partial_conflict_and_alias():
    for cff, use_ttx in ((False, False), (False, True), (True, True)):
        main = _font({0x41: "shared"}, {"shared": 210}, cff=cff)
        base = _font({0x41: "shared", 0x42: "shared",
                      0x43: "partial"}, {"shared": 430}, cff=cff)
        for st in base["cmap"].tables:
            st.cmap[0x44] = "partial"
        for st in main["cmap"].tables:
            st.cmap[0x43] = "shared"
        result = _merge(main, base, use_ttx)
        cm = result.getBestCmap()
        assert set(cm) == {0x41, 0x42, 0x43, 0x44}, cm
        assert cm[0x41] == cm[0x43] == "shared", cm
        assert cm[0x42] != "shared", cm
        assert result["hmtx"][cm[0x42]][0] == 430
        assert cm[0x44] == "partial", cm
    print("  部分冲突及同名别名: 3 路径 × 4 码位 PASSED")


def test_unicode_subtable_sync():
    main = _font({0x41: "main"})
    full = CmapSubtable.newSubtable(12)
    full.platformID, full.platEncID, full.language = 0, 4, 0
    full.cmap = {0x41: "main"}
    main["cmap"].tables.append(full)
    base = _font({0x42: "base", 0x10000: "supplement"})
    result = _merge(main, base)
    for st in result["cmap"].tables:
        if st.isUnicode() and st.format != 14:
            assert st.cmap[0x41] == "main"
            assert st.cmap[0x42] == "base", (st.platformID, st.platEncID)
            assert (0x10000 in st.cmap) == (st.format == 12)
    print("  Unicode 子表同步: BMP / 非 BMP 范围 PASSED")


def test_uvs_default_and_nondefault():
    for use_ttx in (False, True):
        main = _font({0x41: "main"})
        base = _font({0x41: "base", 0x42: "new"},
                     {"variant": 640})
        _uvs(main, {0xFE0F: [(0x41, "main")]})
        _uvs(base, {0xFE0F: [(0x41, "variant"), (0x42, None)],
                    0xE0100: [(0x41, None), (0x42, "variant")]})
        result = _merge(main, base, use_ttx)
        tables = [st for st in result["cmap"].tables if st.format == 14]
        assert len(tables) == 1
        uvs = tables[0].uvsDict
        assert dict(uvs[0xFE0F]) == {0x41: "main", 0x42: None}, uvs
        assert dict(uvs[0xE0100]) == {0x41: "base",
                                           0x42: "variant"}, uvs
        assert result.getBestCmap()[0x41] == "main"
        assert result["hmtx"]["variant"][0] == 640
    print("  UVS 默认/非默认: 2 路径 × 4 序列 PASSED")


def test_rename_component_and_uvs():
    font = _font({0x41: "composite"}, {"part": 230},
                 {"composite": "part"})
    _uvs(font, {0xE0100: [(0x41, "part"), (0x42, None)]})
    rename_glyphs(font, {"part": "renamed"})
    result = _reload(font)
    assert result["glyf"]["composite"].components[0].glyphName == "renamed"
    uvs = [st for st in result["cmap"].tables if st.format == 14][0]
    assert dict(uvs.uvsDict[0xE0100])[0x41] == "renamed"
    print("  改名同步: 未改名复合字形 + UVS PASSED")


def test_component_source_identity():
    for use_ttx in (False, True):
        main = _font({0x41: "part"}, {"part": 210})
        base = _font({0x41: "part", 0x42: "composite"},
                     {"part": 430}, {"composite": "part"})
        result = _merge(main, base, use_ttx)
        gn = result["glyf"]["composite"].components[0].glyphName
        assert gn != "part", gn
        assert result["hmtx"][gn][0] == 430
        assert result.getBestCmap()[0x41] == "part"
    print("  组件闭包: 2 路径保留打底同名组件 PASSED")


def _cid_font():
    font = _font({0x41: "cid00001"}, {"cid00002": 620}, cff=True)
    from fontTools.cffLib import FDArrayIndex, FontDict, FDSelect
    top = font["CFF "].cff.topDictIndex[0]
    fd = FontDict()
    fd.Private = top.Private
    top.FDArray = FDArrayIndex()
    top.FDArray.append(fd)
    top.FDSelect = FDSelect()
    top.FDSelect.gidArray = [0] * len(font.getGlyphOrder())
    top.ROS = ("Neutral", "Identity", 0)
    top.CIDCount = 3
    for gn in font.getGlyphOrder():
        top.CharStrings[gn].fdSelectIndex = 0
    del top.Private
    _uvs(font, {0xE0100: [(0x41, "cid00002")]})
    return _reload(font)


def test_format_ranges_and_same_encoding():
    main = _font({0x41: "main"})
    for fmt, encoding in ((0, 0), (6, 2), (12, 4)):
        st = CmapSubtable.newSubtable(fmt)
        st.platformID, st.platEncID, st.language = 0, encoding, 0
        st.cmap = {0x41: "main"}
        main["cmap"].tables.append(st)
    base = _font({0x41: "other", 0x42: "base", 0x100: "bmp",
                  0x10000: "supplement"})
    full = copy.deepcopy(next(st for st in base["cmap"].tables
                              if st.format == 12))
    full.platformID, full.platEncID = 0, 3
    base["cmap"].tables = [st for st in base["cmap"].tables
                            if (st.platformID, st.platEncID) != (0, 3)]
    base["cmap"].tables.append(full)
    result = _merge(main, base)
    expected = {0x41: "main", 0x42: "base",
                0x100: "bmp", 0x10000: "supplement"}
    for st in result["cmap"].tables:
        limit = {0: 0xFF, 4: 0xFFFE, 6: 0xFFFF, 12: 0x10FFFF}[st.format]
        assert st.cmap == {cp: gn for cp, gn in expected.items()
                           if cp <= limit}, (st.format, st.cmap)
    assert next(st for st in result["cmap"].tables
                if (st.platformID, st.platEncID) == (0, 3)).format == 12
    print("  格式范围: 0/4/6/12 及同编码升级 PASSED")


def test_uvs_only_and_new_subtable():
    for cff, use_ttx in ((False, False), (False, True), (True, True)):
        main = _font({0x41: "main"}, cff=cff)
        base = _font({0x41: "base"}, {"variant": 660}, cff=cff)
        _uvs(base, {0xE0100: [(0x99, "variant"), (0x41, None)]})
        result = _merge(main, base, use_ttx)
        st = [st for st in result["cmap"].tables if st.format == 14][0]
        assert dict(st.uvsDict[0xE0100]) == {0x99: "variant", 0x41: "base"}
        assert result.getBestCmap() == {0x41: "main"}
    print("  仅 UVS 字形及新 format 14: 3 路径 PASSED")


def test_lowlevel_component_closure():
    for use_ttx in (False, True):
        main = _font({0x41: "part"}, {"part": 210})
        base = _font({0x41: "part", 0x42: "composite"},
                     {"part": 430}, {"composite": "part"})
        result = _reload(merge_glyphs_via_ttx(
            main, base, ["composite"], use_ttx))
        comp = result["glyf"]["composite"].components[0].glyphName
        assert comp != "part"
        assert result["hmtx"][comp][0] == 430
        assert result.getBestCmap()[0x41] == "part"
    print("  低层直接复制: 2 路径组件来源不混用 PASSED")


def _variable_font(cmap):
    font = _font(cmap)
    fb = FontBuilder(font=font)
    fb.setupFvar([("wght", 100, 400, 900, "Weight")], [])
    from fontTools.ttLib.tables.TupleVariation import TupleVariation
    variations = {}
    for gn in font.getGlyphOrder():
        coords = [(0, 0)] * 7
        if gn == ".notdef":
            variations[gn] = []
            continue
        coords[1] = (80, 0)
        # 三个轮廓点后，右幽灵点下标4同步表达+80字宽，与HVAR一致。
        coords[4] = (80, 0)
        variations[gn] = [TupleVariation({"wght": (0, 1, 1)}, coords)]
    fb.setupGvar(variations)
    from fontTools.ttLib.tables import otTables
    from fontTools.varLib.builder import (buildVarRegionList, buildVarData,
                                          buildVarStore, buildVarIdxMap)
    region = buildVarRegionList([{"wght": (0, 1, 1)}], ["wght"])
    data = buildVarData([0], [[0], [80]], optimize=False)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(region, [data])
    hvar.table.AdvWidthMap = buildVarIdxMap(
        [0 if gn == ".notdef" else 1 for gn in font.getGlyphOrder()],
        font.getGlyphOrder())
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar
    return _reload(font)


def test_variable_alias_maps():
    main = _variable_font({0x41: "shared"})
    base = _variable_font({0x42: "shared"})
    aliases = _plan_merge_aliases(main, base)
    renamed = _reload(renamed_copy(base, aliases))
    gn = aliases["shared"]
    assert gn in renamed["gvar"].variations
    assert "shared" not in renamed["gvar"].variations
    assert renamed["gvar"].variations[gn][0].coordinates[1] == (80, 0)
    assert renamed["HVAR"].table.AdvWidthMap.mapping[gn] == 1
    assert renamed.getBestCmap()[0x42] == gn
    result = _merge(main, base)
    assert result.getBestCmap() == {0x41: "shared", 0x42: gn}
    assert result["gvar"].variations[gn][0].coordinates[1] == (80, 0)
    print("  VF 同名别名: gvar/HVAR/cmap 保存重载 PASSED")


def test_post3_partial_identity():
    for use_ttx in (False, True):
        main = _font({0x41: "shared"}, {"shared": 210})
        base = _font({0x41: "shared", 0x42: "shared"}, {"shared": 430})
        main["post"].formatType = 3.0
        base["post"].formatType = 3.0
        result = _merge(_reload(main), _reload(base), use_ttx)
        cmap = result.getBestCmap()
        assert cmap[0x41] != cmap[0x42]
        assert result["hmtx"][cmap[0x41]][0] == 210
        assert result["hmtx"][cmap[0x42]][0] == 430
        assert result["glyf"][cmap[0x41]].xMax == 210
        assert result["glyf"][cmap[0x42]].xMax == 430
    print("  post3 部分冲突: 2 路径轮廓/度量身份 PASSED")


def test_format0_large_glyph_ids():
    main = _font({0x41: "main"},
                 {"padding%03d" % i: 500 for i in range(260)})
    st = CmapSubtable.newSubtable(0)
    st.platformID, st.platEncID, st.language = 0, 0, 0
    st.cmap = {0x41: "main"}
    main["cmap"].tables.append(st)
    base = _font({0x42: "tail"})
    result = _merge(main, base)
    target = next(st for st in result["cmap"].tables
                  if (st.platformID, st.platEncID) == (0, 0))
    assert target.format == 6
    assert target.cmap[0x42] == "tail"
    assert result.getGlyphID("tail") > 255
    print("  format0 GID 范围: 超过255自动升级format6 PASSED")


def test_ttx_existing_names_linear_scan():
    import xml.etree.ElementTree as ET
    from unittest.mock import patch
    counts = [0]

    class CountingElement(ET.Element):
        def __iter__(self):
            for i in range(len(self)):
                if self.tag == "glyf":
                    counts[0] += 1
                yield self[i]

    original = ET.fromstring
    calls = [0]

    def parse(text):
        calls[0] += 1
        if calls[0] == 1:
            parser = ET.XMLParser(target=ET.TreeBuilder(
                element_factory=CountingElement))
            return original(text, parser=parser)
        return original(text)

    main = _font({0x41 + i: "main%02d" % i for i in range(16)})
    base = _font({0x100 + i: "base%02d" % i for i in range(32)})
    with tempfile.TemporaryDirectory(prefix="cmap_regression_") as work:
        main_path = os.path.join(work, "main.ttx")
        base_path = os.path.join(work, "base.ttx")
        out_path = os.path.join(work, "out.ttx")
        main.saveXML(main_path)
        base.saveXML(base_path)
        with patch.object(ET, "fromstring", parse):
            inject_glyphs_xml(main_path, base_path, out_path,
                              base.getGlyphOrder()[1:])
        assert counts[0] <= 2 * (17 + 32), counts
        result = TTFont()
        result.importXML(out_path)
        result = _reload(result)
        assert len(result.getGlyphOrder()) == 49
    print("  TTX 集合扫描: 32新增字形，仅%d次访问 PASSED" % counts[0])


def test_chunked_component_source_reuse():
    for use_ttx in (False, True):
        main = _font({0x41: "main"})
        base = _font({0x42: "first", 0x43: "second"},
                     {"part": 430}, {"first": "part", "second": "part"})
        first = merge_glyphs_via_ttx(main, base, ["first"], use_ttx)
        result = merge_glyphs_via_ttx(first, base, ["second"], use_ttx)
        result = _reload(result)
        assert len(result.getGlyphOrder()) == 5, result.getGlyphOrder()
        for gn in ("first", "second"):
            assert result["glyf"][gn].components[0].glyphName == "part"
        # 换成不同来源的同名组件时，不能错误复用上述来源标记。
        other = _font({0x44: "third"}, {"part": 620}, {"third": "part"})
        third = _reload(merge_glyphs_via_ttx(
            result, other, ["third"], use_ttx))
        part = third["glyf"]["third"].components[0].glyphName
        assert part != "part"
        assert third["hmtx"][part][0] == 620
    print("  分块组件: 同源复用/异源同名隔离两路径 PASSED")


def test_public_alias_contract():
    main = _font({0x41: "shared"}, {"glyph00001": 500})
    base = _font({0x42: "shared"}, {"glyph00001": 500})
    alias = plan_alias(main, base)
    assert set(alias) == {"glyph00001"}, alias
    assert isinstance(resolve_conflicts(main, base), set)
    assert "glyph00001" not in resolve_conflicts(main, base)
    assert ".notdef" not in resolve_conflicts(main, base)
    assert set(_plan_merge_aliases(main, base)) == {"shared", "glyph00001"}
    print("  公共 API: 原自动名别名/冲突集合契约 PASSED")


def test_sequential_ttx_and_xml_headers():
    main = _font({0x41: "main"})
    base = _reload(_font({0x10000: "first", 0x10001: "second"}))
    first = merge_glyphs_via_ttx(main, base, ["first"], True)
    xml = io.BytesIO()
    first.saveXML(xml)
    assert b"cmap_format_12" in xml.getvalue()
    result = merge_glyphs_via_ttx(first, base, ["second"], True)
    result = _reload(result)
    assert result.getBestCmap() == {0x41: "main", 0x10000: "first",
                                    0x10001: "second"}
    print("  连续 TTX: 2 次注入 + 新 format12 XML 头 PASSED")


def test_highlevel_cid_and_variable_alias():
    from FontMerger import FontMerger, DEFAULT_ANSWERS
    main = _cid_font()
    base = _cid_font()
    for st in base["cmap"].tables:
        if st.format != 14:
            st.cmap[0x42] = "cid00001"
    merger = FontMerger()
    merger.mem = dict(DEFAULT_ANSWERS)
    result = _reload(merger.merge_two(main, base))
    assert result.getBestCmap()[0x41] == "cid00001"
    assert result.getBestCmap()[0x42] != "cid00001"
    assert len(result["CFF "].cff.topDictIndex[0].FDArray) == 2
    main = _variable_font({0x41: "shared"})
    base = _variable_font({0x42: "shared"})
    import contextlib
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        result = _reload(merger.merge_two(main, base))
    assert "回退到默认实例合并" not in log.getvalue(), log.getvalue()
    gn = result.getBestCmap()[0x42]
    assert gn != "shared"
    assert result.getBestCmap()[0x41] == "shared"
    assert result["gvar"].variations[gn][0].coordinates[1] == (80, 0)
    from fontTools.varLib.instancer import instantiateVariableFont
    peak = instantiateVariableFont(result, {"wght": 900}, inplace=False)
    for cp in (0x41, 0x42):
        target = peak.getBestCmap()[cp]
        assert peak["hmtx"][target][0] == 580
    print("  高层双 CID / VF: 无回退合成，峰值字宽580单位 PASSED")


def test_highlevel_cid_unique_uvs_renames():
    from FontMerger import FontMerger, DEFAULT_ANSWERS
    main = _cid_font()
    base = _cid_font()
    for st in base["cmap"].tables:
        if st.format == 14:
            st.uvsDict[0xE0101] = [(0x42, "cid00002")]
        else:
            st.cmap[0x42] = "cid00001"
    merger = FontMerger()
    merger.mem = dict(DEFAULT_ANSWERS)
    result = merger.merge_two(main, base)
    renames = result._fontmerger_base_renames
    assert renames["cid00001"] == "cid00103", renames
    assert renames["cid00002"] == "cid00104", renames
    assert all(isinstance(gn, str) and isinstance(new, str)
               for gn, new in renames.items())
    loaded = _reload(result)
    assert not hasattr(loaded, "_fontmerger_base_renames")
    assert loaded.getBestCmap()[0x41] == "cid00001"
    assert loaded.getBestCmap()[0x42] == "cid00103"
    uvs = next(st for st in loaded["cmap"].tables if st.format == 14)
    assert dict(uvs.uvsDict[0xE0101])[0x42] == "cid00104"
    assert dict(uvs.uvsDict[0xE0100])[0x41] == "cid00002"
    print("  高层 CID 独有 UVS: 偏移映射/主优先/非序列化标记 PASSED")


def test_cid_merge_roundtrip():
    main = _cid_font()
    base = _cid_font()
    for st in base["cmap"].tables:
        if st.format != 14:
            st.cmap[0x42] = "cid00001"
    main_top = main["CFF "].cff.topDictIndex[0]
    base_top = base["CFF "].cff.topDictIndex[0]
    main_top.FDArray[0].Private.defaultWidthX = 210
    base_top.FDArray[0].Private.defaultWidthX = 730
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    addOpenTypeFeaturesFromString(
        main, "feature salt { sub cid00001 by cid00002; } salt;")
    result = _reload(cid_ufo_style_merge(main, base))
    cmap = result.getBestCmap()
    assert set(cmap) == {0x41, 0x42}, cmap
    assert cmap[0x41] != cmap[0x42], cmap
    assert result["hmtx"][cmap[0x41]][0] == 500
    top = result["CFF "].cff.topDictIndex[0]
    assert top.CharStrings[cmap[0x41]].private.defaultWidthX == 210
    assert top.CharStrings[cmap[0x42]].private.defaultWidthX == 730
    lookup = result["GSUB"].table.LookupList.Lookup[0].SubTable[0]
    assert cmap[0x41] in lookup.mapping, lookup.mapping
    print("  双 CID 合并: 码位/源 Private/主布局保存重载 PASSED")


def test_cid_shift_cmap():
    font = _cid_font()
    # 必须展开 cmap：惰性 GID 解码会掩盖偏移后仍引用旧名字的缺陷。
    assert font.getBestCmap()[0x41] == "cid00001"
    for st in font["cmap"].tables:
        if st.format == 14:
            assert dict(st.uvsDict[0xE0100])[0x41] == "cid00002"
    shift_cid_range(font, 100)
    result = _reload(font)
    assert result.getBestCmap()[0x41] == "cid00101"
    uvs = [st for st in result["cmap"].tables if st.format == 14][0]
    assert dict(uvs.uvsDict[0xE0100])[0x41] == "cid00102"
    print("  CID 偏移: 普通 cmap 与 UVS 保存重载 PASSED")


def test_nonunicode_format0_large_glyph_ids():
    """Mac 编码与 Unicode 分域；新增 GID>255 也必须可保存。"""
    from FontMerger.utils.save import save_font
    for use_ttx in (False, True):
        for existing in (False, True):
            main = _font({0x41: "main"},
                         {"padding%03d" % i: 500 for i in range(260)})
            base = _font({0x42: "tail", 0x43: "other"})
            mac = CmapSubtable.newSubtable(0)
            mac.platformID, mac.platEncID, mac.language = 1, 0, 5
            mac.cmap = {0x41: "other", 0x42: "tail", 0x80: "other"}
            base["cmap"].tables.append(mac)
            if existing:
                original = CmapSubtable.newSubtable(0)
                original.platformID = 1
                original.platEncID, original.language = 0, 5
                original.cmap = {0x41: "main"}
                main["cmap"].tables.append(original)
            result = _merge(main, base, use_ttx)
            tables = [st for st in result["cmap"].tables
                      if (st.platformID, st.platEncID, st.language) == (1, 0, 5)]
            assert len(tables) == 1 and tables[0].format == 6
            expected = {0x41: "main" if existing else "other",
                        0x42: "tail", 0x80: "other"}
            assert tables[0].cmap == expected, tables[0].cmap
            assert result.getBestCmap() == {0x41: "main", 0x42: "tail",
                                            0x43: "other"}
            assert result.getGlyphID("tail") > 255
            assert mac.format == 0 and mac.cmap[0x41] == "other"
            with tempfile.TemporaryDirectory(prefix="fm-format0-") as temp:
                path = os.path.join(temp, "Merged.ttf")
                _, magic = save_font(result, path)
                assert magic == b"\x00\x01\x00\x00"
                again = TTFont(path)
                copied = next(st for st in again["cmap"].tables
                              if (st.platformID, st.platEncID) == (1, 0))
                assert copied.cmap == expected
                again.close()
    print("  非Unicode format0: 对象/TTX × 新建/已有Mac表，GID>255 保存重载 PASSED")


def test_nonunicode_format0_byte_boundary_stays_valid():
    """有效 GID=255 不升级，Unicode 同码数值不覆盖 Mac 编码。"""
    main = _font({0x41: "zz.last"},
                 {"padding%03d" % i: 500 for i in range(254)})
    assert main.getGlyphID("zz.last") == 255
    mac = CmapSubtable.newSubtable(0)
    mac.platformID, mac.platEncID, mac.language = 1, 0, 7
    mac.cmap = {0x80: "zz.last"}
    main["cmap"].tables.append(mac)
    _copy_cmap_mappings(main, _font({0x42: "unused"}), [])
    result = _reload(main)
    copied = next(st for st in result["cmap"].tables if st.platformID == 1)
    assert copied.format == 0 and copied.language == 7
    assert copied.cmap == {0x80: "zz.last"}
    assert result.getGlyphID("zz.last") == 255
    assert result.getBestCmap() == {0x41: "zz.last"}
    print("  非Unicode format0边界: GID255原样保留，Mac/Unicode不串域 PASSED")


def main():
    tests = [test_partial_conflict_and_alias, test_unicode_subtable_sync,
             test_uvs_default_and_nondefault, test_rename_component_and_uvs,
             test_component_source_identity, test_cid_shift_cmap,
             test_cid_merge_roundtrip, test_format_ranges_and_same_encoding,
             test_uvs_only_and_new_subtable, test_lowlevel_component_closure,
             test_variable_alias_maps, test_post3_partial_identity,
             test_format0_large_glyph_ids,
             test_nonunicode_format0_large_glyph_ids,
             test_nonunicode_format0_byte_boundary_stays_valid,
             test_ttx_existing_names_linear_scan,
             test_chunked_component_source_reuse,
             test_public_alias_contract,
             test_sequential_ttx_and_xml_headers,
             test_highlevel_cid_and_variable_alias,
             test_highlevel_cid_unique_uvs_renames]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            print("  %s: FAILED - %s" % (test.__name__, exc))
            traceback.print_exc()
    print("Results: %d/%d passed" % (passed, len(tests)))
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
