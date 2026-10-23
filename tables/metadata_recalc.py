"""按最终字体重算元数据，不重放 fvar 或 OT 表合并。

字形/布局合并完成后调用；就地修改 font，不改设计来源或命名。
重算失败保留原字段并显式告警，PANOSE 全零保留，不能猜测另一设计的风格。
"""
import math

from fontTools.otlLib.maxContextCalc import maxCtxFont
from fontTools.pens.boundsPen import BoundsPen


def _attempt(label, action):
    """隔离可重算统计项；失败保留已有信息并告警。"""
    try:
        action()
    except Exception as error:
        print("  [元数据警告] %s 重算失败，保留已有字段: %s" %
              (label, error))


def _recalc_os2(font):
    """就地使用 fontTools 的规范实现重算 OS/2 派生字段。"""
    if "OS/2" not in font:
        return
    table = font["OS/2"]
    if "cmap" in font:
        _attempt("Unicode 范围", lambda: table.recalcUnicodeRanges(font))
        if table.version >= 1:
            _attempt("代码页范围",
                     lambda: table.recalcCodePageRanges(font))
        _attempt("首末码位",
                 lambda: table.updateFirstAndLastCharIndex(font))
    _attempt("平均字宽", lambda: table.recalcAvgCharWidth(font))
    if table.version >= 2:
        _attempt("最大上下文",
                 lambda: setattr(table, "usMaxContext", maxCtxFont(font)))
    panose = getattr(table, "panose", None)
    if panose is not None and not any(vars(panose).values()):
        print("  [元数据警告] PANOSE 全零，保留主设计分类；不借用打底风格")


def _recalc_bounds(font):
    """按最终轮廓更新 head bbox；不以 cmap 裁掉未编码的布局字形。"""
    bounds = []
    if "glyf" in font:
        glyf = font["glyf"]
        for name in font.getGlyphOrder():
            glyph = glyf[name]
            glyph.recalcBounds(glyf)
            if glyph.numberOfContours:
                bounds.append((glyph.xMin, glyph.yMin,
                               glyph.xMax, glyph.yMax))
    else:
        glyphs = font.getGlyphSet()
        for name in font.getGlyphOrder():
            pen = BoundsPen(glyphs)
            glyphs[name].draw(pen)
            if pen.bounds is not None:
                bounds.append(pen.bounds)
    if bounds:
        box = (math.floor(min(b[0] for b in bounds)),
               math.floor(min(b[1] for b in bounds)),
               math.ceil(max(b[2] for b in bounds)),
               math.ceil(max(b[3] for b in bounds)))
    else:
        box = (0, 0, 0, 0)
    if "head" in font:
        head = font["head"]
        head.xMin, head.yMin, head.xMax, head.yMax = box
    if "OS/2" in font:
        table = font["OS/2"]
        old = (table.usWinAscent, table.usWinDescent)
        table.usWinAscent = max(table.usWinAscent, box[3], 0)
        table.usWinDescent = max(table.usWinDescent, -box[1], 0)
        if old != (table.usWinAscent, table.usWinDescent):
            print("  [元数据] Win 度量扩大为 %d/%d，覆盖全部默认轮廓" %
                  (table.usWinAscent, table.usWinDescent))


def recalc_after_merge(font):
    """就地收尾最终字体；在字形与布局合并后调用，不返回新字体。

    Args:
        font: 最终 TTFont；保留 fvar、OT、name 与主设计风格。
    Returns:
        None；未知统计项失败打印告警，不掩盖外部验证异常。
    """
    for tag in ("hmtx", "vmtx"):
        if tag in font:
            alive = set(font.getGlyphOrder())
            metrics = font[tag].metrics
            stale = set(metrics) - alive
            for name in stale:
                del metrics[name]
            if stale:
                print("  [元数据] %s 清除 %d 条非存活字形度量" %
                      (tag, len(stale)))
    _attempt("轮廓包围盒", lambda: _recalc_bounds(font))
    if "maxp" in font:
        font["maxp"].numGlyphs = len(font.getGlyphOrder())
        if "glyf" in font and font["maxp"].tableVersion == 0x10000:
            _attempt("maxp 轮廓资源", lambda: font["maxp"].recalc(font))
    for tag in ("hhea", "vhea"):
        if tag in font:
            _attempt(tag, lambda tag=tag: font[tag].recalc(font))
    _recalc_os2(font)
