"""字形子集创建 — 从字体中提取指定字形的最小子集"""
import copy
from fontTools.ttLib import TTFont
from ..utils.detect import is_cff


def create_glyph_subset(font, glyph_names, strip_layout=True):
    """创建仅包含指定字形的子集字体，可选剔除 OT 布局表"""
    sub = TTFont()

    for tag in font.keys():
        if tag == "GlyphOrder":
            continue
        if strip_layout and tag in ("GSUB", "GPOS", "GDEF", "BASE", "VORG", "JSTF"):
            continue
        sub[tag] = copy.deepcopy(font[tag])

    order = []
    if ".notdef" in glyph_names:
        order.append(".notdef")
    for gn in glyph_names:
        if gn != ".notdef" and gn in font.getGlyphOrder():
            order.append(gn)
    if not order:
        order = [".notdef"]
    sub.setGlyphOrder(order)

    if "maxp" in sub:
        sub["maxp"].numGlyphs = len(order)

    keep = set(order)
    for table in sub["cmap"].tables:
        if hasattr(table, "cmap") and table.cmap:
            for cp in [cp for cp, gn in table.cmap.items() if gn not in keep]:
                del table.cmap[cp]

    for tag in ("hmtx", "vmtx"):
        if tag in sub:
            sub[tag].metrics = {gn: m for gn, m in
                                sub[tag].metrics.items() if gn in keep}

    return sub
