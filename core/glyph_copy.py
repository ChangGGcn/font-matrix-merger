"""字形/度量/cmap 复制 — 通过 TTX XML roundtrip"""
import os, sys, subprocess, copy, tempfile, atexit
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
        for glyph_elem in base_glyf:
            name = glyph_elem.get("name")
            if name and name in glyph_set:
                existing_names = {e.get("name") for e in main_glyf}
                if name not in existing_names:
                    main_glyf.append(copy.deepcopy(glyph_elem))

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


def merge_glyphs_via_ttx(main_font, base_font, glyphs_to_add):
    """通过 TTX XML roundtrip 合并字形 (最可靠方法)"""
    if not glyphs_to_add:
        return copy.deepcopy(main_font)

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

        inject_glyphs_xml(main_ttx, base_ttx, merged_ttx, glyphs_to_add)

        subprocess.run(
            [sys.executable, "-m", "fontTools", "ttx",
             "-o", merged_bin, merged_ttx],
            check=True, capture_output=True, timeout=300
        )

        result = TTFont(merged_bin)

        # 复制 OT 特性: 仅从主字体恢复 (打底字体的 OT 表已剥离，避免 CID/命名方案冲突)
        for tag in ("GSUB", "GPOS", "GDEF"):
            if tag not in result and tag in main_font:
                result[tag] = copy.deepcopy(main_font[tag])

        # 复制新增字形的 cmap 映射
        _copy_cmap_mappings(result, base_font, glyphs_to_add)

        return result
    finally:
        _rmtree(tmpdir)


def _copy_cmap_mappings(dst, src, glyph_names):
    for table in src["cmap"].tables:
        if not (hasattr(table, "cmap") and table.cmap):
            continue
        for cp, gn in table.cmap.items():
            if gn not in glyph_names:
                continue
            for rt in dst["cmap"].tables:
                if (hasattr(rt, "cmap")
                        and rt.format == table.format
                        and rt.platEncID == table.platEncID
                        and rt.platformID == table.platformID):
                    if cp not in rt.cmap:
                        rt.cmap[cp] = gn
