# -*- coding: utf-8 -*-
"""字体缩放与基线偏移：保持 UPM，实施 (x*s, y*s+offset)。

glyf 使用 fontTools 的坐标变换，保留点序、部件和 gvar 拓扑；
CFF/CFF2 使用官方 ScalerVisitor/specializer，保留 blend 而不烘焙默认轮廓。
非恒等变换统一显式移除 hinting 和过期像素缓存，避免指令恢复旧坐标。
竖排约定：无 VORG 时固定缩放后的隐式原点；有 VORG 时显式原点
与轮廓同移。tsb 总由原点减新 yMax 求得，不重复扣除 offset。
"""

import math

from fontTools.cffLib.specializer import (
    commandsToProgram, generalizeCommands, programToCommands)
from fontTools.misc.fixedTools import otRound
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib.scaleUpem import ScalerVisitor
from fontTools.ttLib.tables._g_l_y_f import (
    SCALED_COMPONENT_OFFSET, SCALE_COMPONENT_OFFSET_DEFAULT,
    UNSCALED_COMPONENT_OFFSET)

from ..utils.detect import is_cff, is_ttf


def _transform_matrix(scale, baseline_offset):
    """构造关于原点缩放、再沿 y 平移的仿射矩阵。"""
    return Transform(scale, 0, 0, scale, 0, baseline_offset)


def _remove_hinting(font):
    """就地采用官方去指令工具，并成套删除全局程序与像素缓存。"""
    print("  [告警] 非恒等轮廓变换采用无 hinting 降级："
          "移除字形指令及全局程序，避免恢复变换前坐标")
    if "glyf" in font:
        font["glyf"].removeHinting()
    for tag in ("CFF ", "CFF2"):
        if tag in font:
            font[tag].cff.remove_hints()
    # VDMX/hdmx 是栅格化后的像素缓存，不能当设计单位直接缩放。
    for tag in ("cvt ", "cvar", "fpgm", "prep", "gasp",
                "hdmx", "LTSH", "VDMX", "DSIG"):
        if tag in font:
            del font[tag]
            print("  [告警] 轮廓变换后删除失效表 %s" % tag.strip())
    if "maxp" in font and font["maxp"].tableVersion == 0x00010000:
        maxp = font["maxp"]
        for attr in ("maxTwilightPoints", "maxStorage", "maxFunctionDefs",
                     "maxInstructionDefs", "maxStackElements",
                     "maxSizeOfInstructions"):
            setattr(maxp, attr, 0)
        maxp.maxZones = 1
    if "head" in font:
        # 无指令时不再声明依赖整数 ppem 或指令修改 advance。
        font["head"].flags &= ~((1 << 3) | (1 << 4))


def scale_font(font, scale, baseline_offset):
    """就地缩放字体并偏移基线，返回同一字体，保持 UPM 与轴拓扑。

    Args:
        font: TTFont。
        scale: float，缩放系数（110% 为 1.1）。
        baseline_offset: float，y 向上为正，单位为字体设计单位。
    """
    if scale == 1.0 and baseline_offset == 0:
        return font
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("缩放系数必须为有限正数")
    if not math.isfinite(baseline_offset):
        raise ValueError("基线偏移必须为有限数")
    if not (is_cff(font) or is_ttf(font)):
        raise ValueError("无法识别的轮廓格式: 无 CFF/CFF2/glyf 表")
    if "VARC" in font:
        raise ValueError("暂不支持 VARC 的基线变换，拒绝烘焙可变轮廓")

    old_bounds = _glyph_bounds(font)
    old_origins = {}
    if "vmtx" in font:
        for name, (_, tsb) in font["vmtx"].metrics.items():
            old_origins[name] = (font["VORG"][name] if "VORG" in font
                                 else old_bounds[name][3] + tsb)
    positions = _vertical_positions(font)
    upem = font["head"].unitsPerEm
    matrices = []
    for tag in ("CFF ", "CFF2"):
        if tag in font:
            for top in font[tag].cff.topDictIndex:
                matrices.append((top, list(top.FontMatrix)))

    _remove_hinting(font)
    if scale != 1.0:
        # 官方工具已覆盖全局度量、GPOS/BASE/MATH、gvar 和 VarStore。
        # glyf 单独处理，避免重建轮廓及点匹配部件缺 x/y 的限制。
        visitor = ScalerVisitor(scale)
        visitor.font = font
        for tag in font.keys():
            if tag not in ("GlyphOrder", "glyf", "VORG"):
                visitor.visit(font[tag])
        font["head"].unitsPerEm = upem
        # 此接口是视觉缩放，不是 UPM 改换，不能抵消 CFF 的轮廓缩放。
        for top, matrix in matrices:
            top.FontMatrix = matrix

    if "glyf" in font:
        _scale_glyf(font, _transform_matrix(scale, baseline_offset))
    elif baseline_offset:
        _translate_cff(font, baseline_offset)

    for obj, attr, old_value, sign in positions:
        value = otRound(old_value * scale + sign * baseline_offset)
        if attr in ("usWinAscent", "usWinDescent"):
            value = max(0, value)
        setattr(obj, attr, value)
    if "VORG" in font:
        vorg = font["VORG"]
        vorg.defaultVertOriginY = otRound(
            vorg.defaultVertOriginY * scale + baseline_offset)
        for name, value in list(vorg.VOriginRecords.items()):
            vorg.VOriginRecords[name] = otRound(
                value * scale + baseline_offset)

    bounds = _glyph_bounds(font)
    if "vmtx" in font:
        for name, (advance, _) in list(font["vmtx"].metrics.items()):
            origin = (font["VORG"][name] if "VORG" in font else
                      otRound(old_origins[name] * scale))
            font["vmtx"].metrics[name] = (
                advance, otRound(origin - bounds[name][3]))
    nonempty = [box for box in bounds.values() if box != (0, 0, 0, 0)]
    if nonempty:
        box = (min(b[0] for b in nonempty), min(b[1] for b in nonempty),
               max(b[2] for b in nonempty), max(b[3] for b in nonempty))
        head = font["head"]
        head.xMin, head.yMin = math.floor(box[0]), math.floor(box[1])
        head.xMax, head.yMax = math.ceil(box[2]), math.ceil(box[3])
        if "CFF " in font:
            font["CFF "].cff.topDictIndex[0].FontBBox = list(box)
    for tag in ("hhea", "vhea"):
        if tag in font:
            font[tag].recalc(font)
    print("  [变换] 缩放 x%.3f, 基线偏移 %+.1f (%d glyphs)" %
          (scale, baseline_offset, len(font.getGlyphOrder())))
    return font


def _vertical_positions(font):
    """保存纵向位置；行距/厚度/advance 属于长度，绝不加 offset。"""
    result = []
    specs = {
        "OS/2": (("sTypoAscender", 1), ("sTypoDescender", 1),
                 ("usWinAscent", 1), ("usWinDescent", -1),
                 ("sxHeight", 1), ("sCapHeight", 1),
                 ("yStrikeoutPosition", 1)),
        "hhea": (("ascent", 1), ("descent", 1)),
        "post": (("underlinePosition", 1),),
    }
    for tag, attrs in specs.items():
        if tag not in font:
            continue
        for attr, sign in attrs:
            value = getattr(font[tag], attr, None)
            # OS/2 的零高度表示未知，不凭偏移编造高度。
            if value is None or (attr in ("sxHeight", "sCapHeight")
                                 and value == 0):
                continue
            result.append((font[tag], attr, value, sign))
    if "CFF " in font:
        for top in font["CFF "].cff.topDictIndex:
            result.append((top, "UnderlinePosition",
                           top.UnderlinePosition, 1))
    return result


def _glyph_bounds(font):
    """返回默认位置的包围盒；测量可变字体不改写其点或 blend。"""
    result = {}
    if "glyf" in font:
        glyf = font["glyf"]
        done = set()
        for name in font.getGlyphOrder():
            glyph = glyf[name]
            glyph.recalcBounds(glyf, boundsDone=done)
            result[name] = ((glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
                            if glyph.numberOfContours else (0, 0, 0, 0))
    else:
        glyph_set = font.getGlyphSet()
        for name in font.getGlyphOrder():
            pen = BoundsPen(glyph_set)
            glyph_set[name].draw(pen)
            result[name] = pen.bounds or (0, 0, 0, 0)
    return result


def _scale_glyf(font, matrix):
    """就地变换坐标，保留点序、复合结构和 gvar 对点的索引。"""
    scale, offset = matrix.xx, matrix.dy
    for glyph in font["glyf"].glyphs.values():
        if not glyph.isComposite():
            if hasattr(glyph, "coordinates"):
                glyph.coordinates.scale((scale, scale))
                glyph.coordinates.translate((0, offset))
                glyph.coordinates.toInt()
            continue
        for component in glyph.components:
            # 点匹配部件靠已平移的锚点定位，不能再给部件添加位移。
            if not hasattr(component, "x"):
                continue
            transform = getattr(component, "transform", ((1, 0), (0, 1)))
            xx, xy = transform[0][0], transform[1][0]
            yx, yy = transform[0][1], transform[1][1]
            scaled = (component.flags & SCALED_COMPONENT_OFFSET or
                      (not component.flags & UNSCALED_COMPONENT_OFFSET and
                       SCALE_COMPONENT_OFFSET_DEFAULT))
            dx, dy = -xy * offset, (1 - yy) * offset
            if scaled and offset:
                determinant = xx * yy - xy * yx
                if determinant == 0:
                    raise ValueError("奇异复合部件矩阵无法安全偏移")
                dx, dy = ((yy * dx - xy * dy) / determinant,
                          (-yx * dx + xx * dy) / determinant)
            component.x = otRound(component.x * scale + dx)
            component.y = otRound(component.y * scale + dy)


def _translate_cff(font, offset):
    """仅改变首个 moveto 的默认坐标，不改 blend 增量或 vsindex。"""
    tag = "CFF2" if "CFF2" in font else "CFF "
    cff = font[tag].cff
    cff.desubroutinize()
    for top in cff.topDictIndex:
        store = getattr(top, "VarStore", None)
        regions = store.getNumRegions if store is not None else None
        for name in top.charset:
            charstring = top.CharStrings[name]
            charstring.decompile()
            commands = generalizeCommands(programToCommands(
                charstring.program, getNumRegions=regions))
            for operator, args in commands:
                if operator == "rmoveto":
                    if isinstance(args[1], list):
                        args[1][0] += offset
                    else:
                        args[1] += offset
                    break
            charstring.program = commandsToProgram(commands)


def apply_scale_offset(font, scale_percent, baseline_offset):
    """对外接口：百分制缩放，基线偏移为字体单位；不改变 CLI 方向。"""
    return scale_font(font, scale_percent / 100.0, baseline_offset)
