# -*- coding: utf-8 -*-
"""字形重命名 — 同步更新字体里所有按字形名索引的结构

字体里大量结构以**字形名**为键 (glyf/hmtx/vmtx/cmap/CharStrings/HVAR 映射…),
OpenType 布局表更是到处引用字形名。只改 GlyphOrder 而不改这些引用, 保存出的
字体就会引用不存在的字形。:func:`rename_glyphs` 把这份"改名清单"一次做全。
"""
import copy

from ..tables.layout_union import remap_glyph_names


def alias_name(name, taken, tag="b", index=1):
    """为 name 生成一个不在 taken 中的别名: {tag}{index:03d}.{name}

    已是该形式时追加 _n 直到不冲突。
    """
    cand = "%s%03d.%s" % (tag, index, name)
    i = 1
    while cand in taken:
        cand = "%s%03d_%d.%s" % (tag, index, i, name)
        i += 1
    return cand


def _rename_glyf(font, mapping):
    if "glyf" not in font:
        return
    glyf = font["glyf"]
    # 复合字形惰性持有组件 GID; 重组字形序之前必须先展开, 否则组件会指向错字形
    glyf.ensureDecompiled()
    for gn, g in list(glyf.glyphs.items()):
        new = mapping.get(gn)
        if new is None or new == gn:
            continue
        if g.isComposite():
            for comp in g.components:
                comp.glyphName = mapping.get(comp.glyphName, comp.glyphName)
        del glyf.glyphs[gn]
        glyf.glyphs[new] = g


def _rename_cff(font, mapping):
    for tag in ("CFF ", "CFF2"):
        if tag not in font:
            continue
        top = font[tag].cff.topDictIndex[0]
        cs = getattr(top, "CharStrings", None)
        if cs is not None and getattr(cs, "charStrings", None):
            cs.charStrings = {mapping.get(k, k): v
                              for k, v in cs.charStrings.items()}
        charset = getattr(top, "charset", None)
        if charset:
            top.charset = [mapping.get(n, n) for n in charset]
        fdselect = getattr(top, "FDSelect", None)
        if fdselect is not None and getattr(fdselect, "mapping", None):
            fdselect.mapping = {mapping.get(k, k): v
                                for k, v in fdselect.mapping.items()}


def _rename_metrics(font, tag, mapping):
    if tag not in font:
        return
    m = font[tag].metrics
    if not isinstance(m, dict):
        return
    font[tag].metrics = {mapping.get(k, k): v for k, v in m.items()}


def _rename_cmap(font, mapping):
    if "cmap" not in font:
        return
    for st in font["cmap"].tables:
        cm = getattr(st, "cmap", None)
        if not cm:
            continue
        for cp in list(cm.keys()):
            gn = cm[cp]
            if gn in mapping:
                cm[cp] = mapping[gn]


def _rename_variation_maps(font, mapping):
    """HVAR/VVAR 的 DeltaSetIndexMap (按字形名索引) 改名"""
    for tag in ("HVAR", "VVAR"):
        if tag not in font:
            continue
        table = font[tag].table
        for attr in ("AdvWidthMap", "LsbMap", "RsbMap",
                     "AdvHeightMap", "TsbMap", "BsbMap", "VOrgMap"):
            m = getattr(table, attr, None)
            if m is None or not getattr(m, "mapping", None):
                continue
            m.mapping = {mapping.get(k, k): v for k, v in m.mapping.items()}


def rename_glyphs(font, mapping):
    """就地重命名字形, 同步更新所有按名索引的结构。

    覆盖: GlyphOrder / glyf (含复合组件) / CFF·CFF2 CharStrings+charset /
    hmtx / vmtx / cmap / VORG / HVAR·VVAR DeltaSetIndexMap /
    GSUB·GPOS·GDEF 的全部字形引用。

    Args:
        font: TTFont (就地修改)
        mapping: {旧名: 新名}; 未列出的字形保持不变

    Returns:
        font
    """
    mapping = {k: v for k, v in mapping.items() if k != v}
    if not mapping:
        return font

    order = list(font.getGlyphOrder())
    new_order = [mapping.get(gn, gn) for gn in order]
    if len(set(new_order)) != len(new_order):
        dupes = {n for n in new_order if new_order.count(n) > 1}
        raise ValueError("重命名产生重名: %s" % sorted(dupes)[:5])

    _rename_glyf(font, mapping)
    _rename_cff(font, mapping)
    _rename_metrics(font, "hmtx", mapping)
    _rename_metrics(font, "vmtx", mapping)
    _rename_cmap(font, mapping)
    _rename_variation_maps(font, mapping)
    if "VORG" in font and getattr(font["VORG"], "VOriginRecords", None):
        font["VORG"].VOriginRecords = {
            mapping.get(k, k): v for k, v in font["VORG"].VOriginRecords.items()}
    for tag in ("GSUB", "GPOS", "GDEF"):
        if tag in font:
            remap_glyph_names(font[tag].table, mapping)
    font.setGlyphOrder(new_order)
    return font


def renamed_copy(font, mapping):
    """返回改名后的深拷贝 (不修改原字体)"""
    if not mapping:
        return copy.deepcopy(font)
    return rename_glyphs(copy.deepcopy(font), mapping)
