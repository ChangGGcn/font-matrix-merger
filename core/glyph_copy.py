"""字形/度量/cmap 复制 — 通过 TTX XML roundtrip"""
import os, sys, subprocess, copy, tempfile, atexit, weakref
import xml.etree.ElementTree as ET
from fontTools.ttLib import TTFont
from ..utils.detect import is_cff


def _rmtree(d):
    try:
        for root, dirs, files in os.walk(d, topdown=False):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d2 in dirs:
                os.rmdir(os.path.join(root, d2))
        os.rmdir(d)
    except OSError:
        pass


def inject_glyphs_xml(main_ttx, base_ttx, output_ttx, glyph_names):
    """将 base TTX 中的指定字形注入到 main TTX"""
    glyph_set = set(glyph_names)

    with open(main_ttx, "r", encoding="utf-8") as f:
        main_xml = f.read()
    with open(base_ttx, "r", encoding="utf-8") as f:
        base_xml = f.read()

    main_root = ET.fromstring(main_xml)
    base_root = ET.fromstring(base_xml)

    # GlyphOrder
    go_elem = main_root.find("GlyphOrder")
    if go_elem is not None:
        existing = {e.get("name") for e in go_elem.findall("GlyphID")}
        for gn in glyph_names:
            if gn not in existing:
                gid = ET.SubElement(go_elem, "GlyphID")
                gid.set("name", gn)
                gid.set("id", str(len(existing)))
                existing.add(gn)

    # CFF/CFF2 CharStrings
    for table_tag in ("CFF", "CFF2"):
        main_cff = main_root.find(table_tag)
        base_cff = base_root.find(table_tag)
        if main_cff is None or base_cff is None:
            continue
        main_fonts = list(main_cff.iter("CFFFont"))
        base_fonts = list(base_cff.iter("CFFFont"))
        for mfe, bfe in zip(main_fonts, base_fonts):
            main_cs = mfe.find("CharStrings")
            base_cs = bfe.find("CharStrings")
            if main_cs is None or base_cs is None:
                continue

            # FDArray 对齐: 打底 FDArray 追加到主, 注入的 CharString fdSelectIndex 加偏移
            main_fda = mfe.find("FDArray")
            base_fda = bfe.find("FDArray")
            fd_offset = 0
            if main_fda is not None and base_fda is not None:
                main_fds = list(main_fda.findall("FontDict"))
                base_fds = list(base_fda.findall("FontDict"))
                if base_fds:
                    fd_offset = len(main_fds)
                    for fd_elem in base_fds:
                        main_fda.append(copy.deepcopy(fd_elem))
                    for i, fd_elem in enumerate(main_fda.findall("FontDict")):
                        fd_elem.set("index", str(i))

            for cs_elem in base_cs:
                name = cs_elem.get("name")
                if name and name in glyph_set:
                    copied = copy.deepcopy(cs_elem)
                    if fd_offset and copied.get("fdSelectIndex") is not None:
                        copied.set("fdSelectIndex",
                                   str(int(copied.get("fdSelectIndex")) + fd_offset))
                    main_cs.append(copied)

    # glyf
    main_glyf = main_root.find("glyf")
    base_glyf = base_root.find("glyf")
    if main_glyf is not None and base_glyf is not None:
        existing_names = {e.get("name") for e in main_glyf}
        for glyph_elem in base_glyf:
            name = glyph_elem.get("name")
            if name and name in glyph_set and name not in existing_names:
                main_glyf.append(copy.deepcopy(glyph_elem))
                existing_names.add(name)

    # hmtx
    main_hmtx = main_root.find("hmtx")
    base_hmtx = base_root.find("hmtx")
    if main_hmtx is not None and base_hmtx is not None:
        existing_mtx = {e.get("name") for e in main_hmtx}
        for mtx_elem in base_hmtx:
            name = mtx_elem.get("name")
            if name and name in glyph_set and name not in existing_mtx:
                main_hmtx.append(copy.deepcopy(mtx_elem))

    # vmtx (纵向度量): 与 glyphOrder 对齐 — 新字形若 base 无 vmtx 条目,
    # 编译时 vmtx 遍历全部 glyphOrder 会 KeyError, 补默认 (0,0)
    main_vmtx = main_root.find("vmtx")
    base_vmtx = base_root.find("vmtx")
    if main_vmtx is not None:
        existing_v = {e.get("name") for e in main_vmtx}
        if base_vmtx is not None:
            for v_elem in base_vmtx:
                name = v_elem.get("name")
                if name and name in glyph_set and name not in existing_v:
                    main_vmtx.append(copy.deepcopy(v_elem))
                    existing_v.add(name)
        # 补缺失 (glyphOrder 中有但 vmtx 无)
        go_elem = main_root.find("GlyphOrder")
        if go_elem is not None:
            for gid in go_elem.findall("GlyphID"):
                gn = gid.get("name")
                if gn and gn in glyph_set and gn not in existing_v:
                    sub = ET.SubElement(main_vmtx, "mtx")
                    sub.set("name", gn)
                    sub.set("height", "0")
                    sub.set("tsb", "0")
                    existing_v.add(gn)

    # HVAR/VVAR/AVAR 的 VarIdxMap (AdvWidthMap/LsbMap/RsbMap/TsbMap/BsbMap/
    # AdvHeightMap/VOrgMap): 必须覆盖全部字形, 新增字形映射到 NO_VARIATION_INDEX
    for var_tag in ("HVAR", "VVAR", "AVAR"):
        var_elem = main_root.find(var_tag)
        if var_elem is None:
            continue
        for map_elem in var_elem.iter():
            if map_elem.tag in ("AdvWidthMap", "LsbMap", "RsbMap",
                                "TsbMap", "BsbMap", "AdvHeightMap", "VOrgMap"):
                existing_maps = {e.get("glyph") for e in map_elem.findall("Map")}
                for gn in glyph_names:
                    if gn not in existing_maps:
                        m_el = ET.SubElement(map_elem, "Map")
                        m_el.set("glyph", gn)
                        m_el.set("outer", "0xFFFF")   # NO_VARIATION_INDEX = 0xFFFFFFFF
                        m_el.set("inner", "0xFFFF")

    # maxp
    maxp_elem = main_root.find("maxp")
    if maxp_elem is not None:
        for num in maxp_elem.findall("numGlyphs"):
            go = main_root.find("GlyphOrder")
            if go is not None:
                count = len(go.findall("GlyphID"))
                num.set("value", str(count))

    xml_str = ET.tostring(main_root, encoding="unicode")
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
    with open(output_ttx, "w", encoding="utf-8") as f:
        f.write(xml_str)

    # 返回最终字形序: 二进制里 GID 顺序 == TTX 的 GlyphOrder 顺序,
    # 编译回来后要据此恢复字形名 (post 3.0 的二进制不存名字)
    if go_elem is not None:
        return [e.get("name") for e in go_elem.findall("GlyphID")]
    return None


#: HVAR/VVAR 里按字形索引的 DeltaSetIndexMap (preWrite 要求覆盖全部字形)
_VARIATION_MAPS = ("AdvWidthMap", "LsbMap", "RsbMap",
                   "AdvHeightMap", "TsbMap", "BsbMap", "VOrgMap")


def _extend_variation_maps(font, glyph_names):
    """给 HVAR/VVAR 的 DeltaSetIndexMap 补上新字形 (无变化索引)。"""
    from fontTools.ttLib.tables.otTables import NO_VARIATION_INDEX

    for tag in ("HVAR", "VVAR"):
        if tag not in font:
            continue
        table = font[tag].table
        for attr in _VARIATION_MAPS:
            m = getattr(table, attr, None)
            if m is None or not hasattr(m, "mapping"):
                continue
            for gn in glyph_names:
                m.mapping.setdefault(gn, NO_VARIATION_INDEX)


def _prepare_glyph_copy(main_font, base_font, glyphs_to_add):
    """补齐 glyf 依赖，并为同名组件单独改名，绝不借用主轮廓。"""
    if "glyf" not in base_font:
        return base_font, list(glyphs_to_add)
    known = set(main_font.getGlyphOrder())
    base_names = set(base_font.getGlyphOrder())
    source_ref = (getattr(base_font, "_fontmerge_copy_source", None)
                  or weakref.ref(base_font))
    source = source_ref()
    previous = getattr(main_font, "_fontmerge_glyph_sources", {})
    same_source = {gn for gn, origin in previous.items()
                   if source is not None and origin() is source}
    required = set(glyphs_to_add) & base_names - known
    pending = list(required)
    while pending:
        gn = pending.pop()
        glyph = base_font["glyf"][gn]
        if not glyph.isComposite():
            continue
        for comp in glyph.components:
            cname = comp.glyphName
            if cname not in base_names:
                raise ValueError("打底组件不存在: %s → %s" % (gn, cname))
            if cname not in required and cname not in same_source:
                required.add(cname)
                pending.append(cname)
    ren = {}
    taken = known | base_names
    from .glyph_rename import alias_name, renamed_copy
    for gn in base_font.getGlyphOrder():
        if gn in required and gn in known:
            ren[gn] = alias_name(gn, taken)
            taken.add(ren[gn])
    if ren:
        base_font = renamed_copy(base_font, ren)
        base_font._fontmerge_copy_source = source_ref
        required = {ren.get(gn, gn) for gn in required}
    return base_font, [gn for gn in base_font.getGlyphOrder()
                       if gn in required]


def _record_copy_sources(result, main_font, base_font, glyph_names):
    """只在内存记同源分块来源；弱引用失效或重载后宁可独立复制。"""
    origins = dict(getattr(main_font, "_fontmerge_glyph_sources", {}))
    source = (getattr(base_font, "_fontmerge_copy_source", None)
              or weakref.ref(base_font))
    origins.update((gn, source) for gn in glyph_names)
    result._fontmerge_glyph_sources = origins


def merge_glyphs_object(main_font, base_font, glyphs_to_add):
    """对象级逐字形复制 (仅 glyf 轮廓), 等价于 TTX 往返但快几个数量级。

    整字体 TTX 往返的代价与字体规模成正比: 给 25k 字形的字体加 135 个字形
    也要序列化/编译整个字体 (实测约 150 秒)。glyf 路径直接搬对象即可:

      * glyf: 深拷贝字形与组件闭包，同名组件先改名而不借用主轮廓;
        打底组件缺失时明确失败，不能写出无法编译的字体;
      * hmtx/vmtx: 逐字形复制;
      * gvar: 逐字形复制增量 (打底静态时无增量);
      * HVAR/VVAR: DeltaSetIndexMap 补 NO_VARIATION_INDEX;
      * cmap: 按 (platformID, platEncID) 并集, 缺子表则新建。

    CFF/CFF2/CID 仍走 TTX 方案 (:func:`merge_glyphs_via_ttx`)。
    """
    base_font, glyphs_to_add = _prepare_glyph_copy(
        main_font, base_font, glyphs_to_add)
    result = copy.deepcopy(main_font)
    for tag in ("glyf", "hmtx", "vmtx", "gvar", "cmap", "HVAR", "VVAR"):
        if tag in result:
            result[tag]
    result["glyf"].ensureDecompiled()
    if "glyf" in base_font:
        base_font["glyf"].ensureDecompiled()

    order = list(result.getGlyphOrder())
    known = set(order)
    base_order = list(base_font.getGlyphOrder())
    base_names = set(base_order)

    # _prepare_glyph_copy 已补齐依赖并处理同名组件。
    include = set(glyphs_to_add) & base_names - known
    # 保持打底字体的 GID 顺序 (Coverage/并行数组同序的前提)
    ordered = [gn for gn in base_order
               if gn in include and gn not in known]

    added = []
    for gn in ordered:
        glyph = copy.deepcopy(base_font["glyf"][gn])
        result["glyf"][gn] = glyph
        result["hmtx"][gn] = base_font["hmtx"][gn]
        if "vmtx" in result:
            # 主字体有 vmtx 时, 每个字形都必须有纵向度量, 否则编译期 KeyError。
            # 打底没有该条目 (如拉丁字体无边表) → 补 (0,0), 与 TTX 路径一致。
            if "vmtx" in base_font and gn in base_font["vmtx"].metrics:
                result["vmtx"][gn] = base_font["vmtx"][gn]
            else:
                result["vmtx"][gn] = (0, 0)
        if "gvar" in base_font and "gvar" in result:
            variations = base_font["gvar"].variations.get(gn)
            if variations:
                result["gvar"].variations[gn] = copy.deepcopy(variations)
        order.append(gn)
        known.add(gn)
        added.append(gn)
    result.setGlyphOrder(order)
    if "maxp" in result:
        result["maxp"].numGlyphs = len(order)
    _extend_variation_maps(result, added)
    _copy_cmap_mappings(result, base_font, added)
    _record_copy_sources(result, main_font, base_font, added)
    return result


def merge_glyphs_via_ttx(main_font, base_font, glyphs_to_add, use_ttx=None):
    """合并打底字形。

    glyf 轮廓走对象级复制 (:func:`merge_glyphs_object`), CFF/CFF2 走
    TTX XML 往返 (CID-keyed CFF 只有这条路可靠)。

    Args:
        use_ttx: None = 按字体类型自动选择; True/False = 强制
    """
    if not glyphs_to_add:
        result = copy.deepcopy(main_font)
        _copy_cmap_mappings(result, base_font, [])
        return result

    if use_ttx is None:
        use_ttx = is_cff(main_font) or is_cff(base_font)
    if not use_ttx and "glyf" in main_font and "glyf" in base_font:
        return merge_glyphs_object(main_font, base_font, glyphs_to_add)

    base_font, glyphs_to_add = _prepare_glyph_copy(
        main_font, base_font, glyphs_to_add)
    tmpdir = tempfile.mkdtemp(prefix="fontmerge_")
    atexit.register(lambda: _rmtree(tmpdir))

    main_ttx = os.path.join(tmpdir, "main.ttx")
    base_ttx = os.path.join(tmpdir, "base.ttx")
    merged_ttx = os.path.join(tmpdir, "merged.ttx")
    merged_bin = os.path.join(tmpdir, "merged" +
                              (".otf" if is_cff(main_font) else ".ttf"))

    try:
        # 剥离打底字体的 OT 布局表 (防止不同命名方案间的 GPOS/GSUB 引用断裂)
        # 主字体的 OT 表完整保留。打底字体的 OT 特性稍后由 merge_ot_features 处理。
        base_stripped = copy.deepcopy(base_font)
        for tag in ("GSUB", "GPOS", "GDEF"):
            if tag in base_stripped:
                del base_stripped[tag]

        main_font.saveXML(main_ttx)
        base_stripped.saveXML(base_ttx)

        intended_order = inject_glyphs_xml(main_ttx, base_ttx, merged_ttx,
                                           glyphs_to_add)

        subprocess.run(
            [sys.executable, "-m", "fontTools", "ttx",
             "-o", merged_bin, merged_ttx],
            check=True, capture_output=True, timeout=300
        )

        result = TTFont(merged_bin)

        # post 3.0 (pyftsubset 常见) 的二进制**不保存字形名**: fontTools 载入时
        # 按 cmap 反推 —— 刚注入的字形此刻还没有 cmap 条目, 名字会被重新编号,
        # 于是布局引用与之后补写的 cmap 全部对不上 (保存时报 dangling cmap)。
        # 二进制的 GID 顺序就是 merged.ttx 的 GlyphOrder 顺序, 按位置恢复即可。
        if intended_order and len(intended_order) == len(result.getGlyphOrder()):
            result.setGlyphOrder(list(intended_order))

        # 复制 OT 特性: 仅从主字体恢复 (打底字体的 OT 表已剥离，避免 CID/命名方案冲突)
        for tag in ("GSUB", "GPOS", "GDEF"):
            if tag not in result and tag in main_font:
                result[tag] = copy.deepcopy(main_font[tag])

        # 复制新增字形的 cmap 映射
        _copy_cmap_mappings(result, base_font, glyphs_to_add)
        _record_copy_sources(result, main_font, base_font, glyphs_to_add)

        return result
    finally:
        _rmtree(tmpdir)


def _unicode_cmap(font):
    """返回优先最佳子表、再补其余子表独有码位的 Unicode 映射。"""
    if "cmap" not in font:
        return {}
    result = dict(font.getBestCmap() or {})
    for st in font["cmap"].tables:
        if st.isUnicode() and st.format != 14:
            for cp, gn in st.cmap.items():
                result.setdefault(cp, gn)
    return result


def _cmap_limit(fmt):
    """返回格式能表达的最大码位；format 4 的 FFFF 是结束哨兵。"""
    return {0: 0xFF, 2: 0xFFFF, 4: 0xFFFE, 6: 0xFFFF,
            8: 0x10FFFF, 10: 0x10FFFF, 12: 0x10FFFF,
            13: 0x10FFFF}.get(fmt, -1)


def _copy_cmap_mappings(dst, src, glyph_names):
    """就地并入新增字形映射，同步 Unicode 子表，保留主映射和 UVS。

    非 Unicode 子表保持独立编码域；默认 UVS 遇到普通 cmap 主映射不同
    时转为显式打底字形，以免把原有变体偷偷变成主字体轮廓。
    """
    if "cmap" not in dst or "cmap" not in src:
        return
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

    available = set(dst.getGlyphOrder())
    selected = set(glyph_names) & available
    merged = _unicode_cmap(dst)
    source = _unicode_cmap(src)
    for cp, gn in source.items():
        if gn in selected:
            merged.setdefault(cp, gn)

    by_key = {}
    for st in dst["cmap"].tables:
        key = (st.platformID, st.platEncID, st.format,
               getattr(st, "language", 0))
        by_key.setdefault(key, st)
    for st in src["cmap"].tables:
        if st.format == 14:
            continue
        entries = {cp: gn for cp, gn in st.cmap.items() if gn in selected}
        if not entries:
            continue
        key = (st.platformID, st.platEncID, st.format,
               getattr(st, "language", 0))
        target = by_key.get(key)
        if target is None:
            # 同平台/编码/语言不能留下两个不同格式：fontTools 无法排序，
            # 且选择方会产生歧义。保留表达范围较大的格式而非塞进窄表。
            same_encoding = next((old for old in dst["cmap"].tables
                                  if old.format != 14
                                  and (old.platformID, old.platEncID,
                                       getattr(old, "language", 0))
                                  == (key[0], key[1], key[3])), None)
            if (same_encoding is not None
                    and _cmap_limit(same_encoding.format)
                    >= _cmap_limit(st.format)):
                target = same_encoding
            else:
                target = CmapSubtable.newSubtable(st.format)
                target.platformID, target.platEncID = st.platformID, st.platEncID
                target.language = getattr(st, "language", 0)
                target.cmap = {}
                if same_encoding is None:
                    dst["cmap"].tables.append(target)
                else:
                    position = dst["cmap"].tables.index(same_encoding)
                    dst["cmap"].tables[position] = target
            by_key[key] = target
        if not st.isUnicode():
            for cp, gn in entries.items():
                target.cmap.setdefault(cp, gn)

    # format 0 的 GID 只有 8 位，Mac 等非 Unicode 子表也受此限制。
    # Unicode 按稍后写入的并集判断；其它编码必须保留自己的映射域。
    reverse = dst.getReverseGlyphMap()
    for position, st in enumerate(dst["cmap"].tables):
        if st.format != 0:
            continue
        mapping = ({cp: gn for cp, gn in merged.items() if 0 <= cp <= 0xFF}
                   if st.isUnicode() else st.cmap)
        if any(reverse[gn] > 0xFF for gn in mapping.values()):
            wider = CmapSubtable.newSubtable(6)
            wider.platformID, wider.platEncID = st.platformID, st.platEncID
            wider.language = getattr(st, "language", 0)
            wider.cmap = dict(st.cmap)
            dst["cmap"].tables[position] = wider
            print("  [cmap] 平台 %d/编码 %d 的 format 0 升级为 6："
                  "保留映射，支持大于 255 的字形编号"
                  % (st.platformID, st.platEncID))

    # 子表身份包括格式与语言，不能把 format 12 写进同编码的 format 4。
    for st in dst["cmap"].tables:
        if st.isUnicode() and st.format != 14:
            limit = _cmap_limit(st.format)
            if limit >= 0:
                st.cmap = {cp: gn for cp, gn in merged.items()
                           if 0 <= cp <= limit}
            if st.format in (12, 13):
                # 新表的 XML 输出也要求头字段；只做 save() 无法发现缺项。
                reverse = dst.getReverseGlyphMap()
                groups = 0
                previous = None
                step = 1 if st.format == 12 else 0
                for cp, gn in sorted(st.cmap.items()):
                    gid = reverse[gn]
                    if (previous is None or cp != previous[0] + 1
                            or gid != previous[1] + step):
                        groups += 1
                    previous = (cp, gid)
                st.reserved = 0
                st.nGroups = groups
                st.length = 16 + groups * 12

    uvs_tables = [st for st in dst["cmap"].tables if st.format == 14]
    pairs = {}
    for st in uvs_tables:
        for selector, entries in st.uvsDict.items():
            target = pairs.setdefault(selector, {})
            for cp, gn in entries:
                target.setdefault(cp, gn)
    changed = False
    for st in src["cmap"].tables:
        if st.format != 14:
            continue
        for selector, entries in st.uvsDict.items():
            target = pairs.setdefault(selector, {})
            for cp, gn in entries:
                if cp in target:
                    continue
                if gn is None:
                    original = source.get(cp)
                    if original is None:
                        continue
                    if merged.get(cp) != original:
                        if original not in selected:
                            continue
                        gn = original
                    elif original not in available:
                        continue
                elif gn not in selected:
                    continue
                target[cp] = gn
                changed = True
    if changed:
        if not uvs_tables:
            target = CmapSubtable.newSubtable(14)
            target.platformID, target.platEncID, target.language = 0, 5, 0
            target.cmap = {}
            dst["cmap"].tables.append(target)
            uvs_tables.append(target)
        for st in uvs_tables:
            st.uvsDict = {selector: sorted(entries.items())
                          for selector, entries in pairs.items() if entries}
