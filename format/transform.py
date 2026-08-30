# -*- coding: utf-8 -*-
"""字体缩放与基线偏移

语义 (Logic.md 通用步骤):
  - 缩放倍率 sc (% 百分制): 关于 (0,0) 点缩放, sc=110 表示放大 110%
  - 基线偏移 of: 基线沿 y 轴平移 of 单位 (字形实际渲染基线位置上移/下移)

实现: 复用 fontTools 官方 Pen 管线 (与 ufo2ft/varLib 一致):
  glyf:  TTGlyphPen + TransformPen 重建
  CFF:   T2CharStringPen + TransformPen 重建 (先 desubroutinize)
同时更新度量表: hmtx/vmtx 缩放 advance, OS/2 与 head/Post 的关键度量。

参考:
  - fontTools.pens.transformPen.TransformPen
  - fontTools.ttLib.scaleUpem (CFF desubroutinize + 逐字符程序变换思路)
"""
import copy
from fontTools.misc.transform import Transform
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont, newTable
from ..utils.detect import is_cff, is_ttf


def _transform_matrix(scale, baseline_offset):
    """构造仿射矩阵: 关于 (0,0) 点缩放 scale, 再沿 y 平移 baseline_offset。

    fontTools Transform 约定: (x, y) -> (x*sx + y*shx + tx, ...)
    缩放: Transform(scale, 0, 0, scale, 0, 0)
    加基线偏移: 在缩放基础上 y += baseline_offset
    """
    return Transform(scale, 0, 0, scale, 0, baseline_offset)


def scale_font(font, scale, baseline_offset):
    """缩放字体 (关于原点), 并施加基线偏移。就地修改并返回 font。

    Args:
        font: TTFont
        scale: float, 缩放系数 (110% -> 1.1)
        baseline_offset: float, 基线偏移 (y 向上为正, 单位: font units)
    """
    if scale == 1.0 and baseline_offset == 0:
        return font

    # CFF2 可变字体: 先实例化到默认轴 (blend 展开), 否则 draw() 无法处理 vsindex/blend
    if "CFF2" in font:
        from .static_extract import variable_to_static
        font = variable_to_static(font, remove_overlaps=False)

    matrix = _transform_matrix(scale, baseline_offset)
    order = font.getGlyphOrder()

    if is_cff(font):
        _scale_cff(font, matrix)
    elif is_ttf(font):
        _scale_glyf(font, matrix)
    else:
        raise ValueError("无法识别的轮廓格式: 无 CFF/CFF2/glyf 表")

    # 缩放度量表 (hmtx advance 宽度按 scale 缩放; lsb 也缩放)
    _scale_metrics(font, "hmtx", scale)
    if "vmtx" in font:
        _scale_metrics(font, "vmtx", scale)

    # 缩放 OS/2 与 head/hhea/post 中的关键度量 (整体坐标缩放)
    _scale_misc_metrics(font, scale)

    _scale_cmap_nothing()  # cmap 无需改动 (码位 → 字形名不变)

    print(f"  [变换] 缩放 x{scale:.3f}, 基线偏移 {baseline_offset:+.1f} "
          f"({len(order)} glyphs)")
    return font


def _scale_glyf(font, matrix):
    """glyf 字形: TTGlyphPen + TransformPen 重建"""
    glyf = font["glyf"]
    glyph_set = font.getGlyphSet()
    new_glyphs = {}
    for gn in font.getGlyphOrder():
        try:
            tt_pen = TTGlyphPen(glyph_set)
            tp = TransformPen(tt_pen, matrix)
            glyph_set[gn].draw(tp)
            g = tt_pen.glyph()
            # TTGlyphPen.glyph() 不设 xMin/yMin — 需要重算
            if not hasattr(g, "xMin"):
                if g.numberOfContours == 0:
                    g.xMin = g.yMin = g.xMax = g.yMax = 0
                else:
                    g.recalcBounds(glyf)
            new_glyphs[gn] = g
        except Exception as e:
            print(f"    [跳过] 字形 {gn}: {e}")
            new_glyphs[gn] = glyph_set[gn]
    glyf.glyphs = new_glyphs
    # loca 由编译时重算


def _scale_cff(font, matrix):
    """CFF/CFF2 CharString: T2CharStringPen + TransformPen 重建"""
    if "CFF2" in font:
        cff = font["CFF2"].cff
    else:
        cff = font["CFF "].cff
    # desubroutinize 保证每个字形是自包含程序 (缩放后无需 subr)
    cff.desubroutinize()
    for fontname in cff.keys():
        cff_font = cff[fontname]
        cs = cff_font.CharStrings
        gs = [cff_font.getGlyphSet()] if hasattr(cff_font, "getGlyphSet") else None
        # 逐字形重建
        for gn in cff_font.charset:
            try:
                old_cs, _ = cs.getItemAndSelector(gn)
                if not hasattr(old_cs, "width") or old_cs.width is None:
                    # draw 一次以计算宽度 (extractor 在 draw 时填充 width)
                    from fontTools.pens.boundsPen import BoundsPen
                    old_cs.draw(BoundsPen(None))
                t2_pen = T2CharStringPen(width=old_cs.width, glyphSet=cs)
                tp = TransformPen(t2_pen, matrix)
                old_cs.draw(tp)
                new_cs = t2_pen.getCharString(private=old_cs.private)
                cs[gn] = new_cs
            except Exception as e:
                print(f"    [跳过] 字形 {gn}: {e}")
    # CFF 私有字典中受缩放影响的数值 (UnderlinePosition 等)
    _scale_cff_private(cff, matrix)


def _scale_cff_private(cff, matrix):
    """CFF 里坐标类数值的缩放 (FontBBox/Underline/StrokeWidth 等)"""
    sx = matrix[0]
    for fontname in cff.keys():
        td = cff[fontname]
        for attr in ("FontBBox", "UnderlinePosition", "UnderlineThickness",
                     "StrokeWidth"):
            if hasattr(td, attr):
                val = getattr(td, attr)
                if isinstance(val, (list, tuple)):
                    setattr(td, attr, [v * sx for v in val])
                elif isinstance(val, (int, float)):
                    setattr(td, attr, val * sx)


def _scale_metrics(font, tag, scale):
    """缩放度量表: advance 与 side-bearing 均按 scale"""
    if tag not in font:
        return
    table = font[tag]
    metrics = dict(table.metrics)
    for gn, (adv, lsb) in metrics.items():
        metrics[gn] = (int(round(adv * scale)), int(round(lsb * scale)))
    table.metrics = metrics
    # hhea/vhea numberOfHMetrics 保持 (等长数组)


def _scale_misc_metrics(font, scale):
    """关键全局度量 (字体内部坐标均被缩放)"""
    if "head" in font:
        head = font["head"]
        if head.xMin is not None:
            head.xMin = int(round(head.xMin * scale))
            head.yMin = int(round(head.yMin * scale))
            head.xMax = int(round(head.xMax * scale))
            head.yMax = int(round(head.yMax * scale))
    if "OS/2" in font:
        os2 = font["OS/2"]
        for attr in ("sTypoAscender", "sTypoDescender", "sTypoLineGap",
                     "usWinAscent", "usWinDescent", "sxHeight", "sCapHeight",
                     "ySubscriptXSize", "ySubscriptYSize",
                     "ySubscriptXOffset", "ySubscriptYOffset",
                     "ySuperscriptXSize", "ySuperscriptYSize",
                     "ySuperscriptXOffset", "ySuperscriptYOffset",
                     "yStrikeoutSize", "yStrikeoutPosition"):
            if hasattr(os2, attr) and getattr(os2, attr) is not None:
                try:
                    setattr(os2, attr, int(round(getattr(os2, attr) * scale)))
                except (TypeError, ValueError):
                    pass
    if "hhea" in font:
        hhea = font["hhea"]
        for attr in ("ascent", "descent", "lineGap"):
            if hasattr(hhea, attr):
                setattr(hhea, attr, int(round(getattr(hhea, attr) * scale)))
    if "post" in font:
        post = font["post"]
        for attr in ("underlinePosition", "underlineThickness"):
            if getattr(post, attr, 0) not in (None, 0):
                setattr(post, attr, int(round(getattr(post, attr) * scale)))
    if "VORG" in font:
        vorg = font["VORG"]
        if getattr(vorg, "defaultVertOriginY", None):
            vorg.defaultVertOriginY = int(round(vorg.defaultVertOriginY * scale))


def _scale_cmap_nothing():
    pass


def apply_scale_offset(font, scale_percent, baseline_offset):
    """对外接口: scale_percent 为百分制 (110 表示 110%), baseline_offset 为字体单位"""
    scale = scale_percent / 100.0
    return scale_font(font, scale, baseline_offset)
