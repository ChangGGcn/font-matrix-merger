"""字形轮廓格式转换: glyf ↔ CFF

方法:
  glyf→CFF: 新建空 OTF, 拷贝原字体表, FontBuilder.setupCFF 构建 CFF
  CFF→glyf: Cu2QuPen + TTGlyphPen (三次→二次近似)
"""

import copy
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.fontBuilder import FontBuilder
from ..utils.detect import is_cff, is_ttf


def cff_to_glyf(font):
    """CFF→glyf: Cu2QuPen 三次→二次近似"""
    if not is_cff(font):
        return copy.deepcopy(font)

    result = copy.deepcopy(font)
    glyph_set = result.getGlyphSet()
    order = result.getGlyphOrder()

    glyf_table = newTable("glyf")
    glyf_table.glyphs = {}
    glyf_table.glyphOrder = order

    for gn in order:
        try:
            if gn in glyph_set:
                tt_pen = TTGlyphPen(glyph_set)
                cu2qu_pen = Cu2QuPen(tt_pen, max_err=1.0, reverse_direction=True)
                glyph_set[gn].draw(cu2qu_pen)
                g = tt_pen.glyph()
                # TTGlyphPen.glyph() 不设置 xMin/yMin — saveXML 会崩溃
                # 参考 fontTools 官方 otf2ttf.py 模式：显式 recalcBounds
                if not hasattr(g, 'xMin'):
                    if g.numberOfContours == 0:
                        g.xMin = g.yMin = g.xMax = g.yMax = 0
                    else:
                        g.recalcBounds(glyf_table)
                glyf_table[gn] = g
        except Exception:
            pass

    cff_key = "CFF2" if "CFF2" in result else "CFF "
    if cff_key in result:
        del result[cff_key]

    result["glyf"] = glyf_table
    if "loca" not in result:
        result["loca"] = newTable("loca")
    result.sfntVersion = "\x00\x01\x00\x00"

    # 移除不兼容表
    for tag in ("cvt ", "fpgm", "prep", "gasp", "VORG", "DSIG"):
        if tag in result:
            del result[tag]

    # 修正 numberOfHMetrics
    if "hhea" in result and "hmtx" in result:
        result["hhea"].numberOfHMetrics = len(result["hmtx"].metrics)

    # 保留字形名: 确保 post 表包含字形名 (formatType=3.0 会导致丢失)
    if "post" in result:
        order = result.getGlyphOrder()
        result["post"].formatType = 2.0
        # 构建 mapping: 标准名→索引 (空 = 所有名都是非标准的)
        result["post"].mapping = {}
        result["post"].glyphOrder = order
        result["post"].extraNames = []

    return result


def glyf_to_cff(font):
    """glyf→CFF: 新建空 OTF + 拷贝原表 + FontBuilder 构建 CFF"""
    if not is_ttf(font):
        return copy.deepcopy(font)

    glyph_set = font.getGlyphSet()
    order = font.getGlyphOrder()

    # 1. 用 pen 转换每个字形为 T2CharString
    charstrings = {}
    for gn in order:
        glyph_obj = glyph_set.get(gn)
        if glyph_obj is None:
            t2_pen = T2CharStringPen(width=0, glyphSet=glyph_set)
            charstrings[gn] = t2_pen.getCharString()
            continue

        width = glyph_obj.width
        cs = None
        try:
            t2_pen = T2CharStringPen(width=width, glyphSet=glyph_set)
            qu2cu_pen = Qu2CuPen(t2_pen, max_err=1.0, all_cubic=True,
                                 reverse_direction=True)
            glyph_obj.draw(qu2cu_pen)
            cs = t2_pen.getCharString()
        except Exception:
            pass

        if cs is None:
            try:
                cs = _fallback_glyf_to_cff(glyph_set, gn, width)
            except Exception:
                t2_pen = T2CharStringPen(width=width, glyphSet=glyph_set)
                cs = t2_pen.getCharString()

        charstrings[gn] = cs

    # 2. 新建空 OTF，拷贝原字体的所有非 glyph 表
    result = TTFont(sfntVersion="OTTO")
    result.setGlyphOrder(order)

    # 拷贝表 (排除 TTF 专用 + CFF 冲突表)
    skip = {"glyf", "loca", "cvt ", "fpgm", "prep", "gasp",
            "CFF ", "CFF2", "GlyphOrder", "LTSH", "hdmx", "VDMX"}
    for tag in font.keys():
        if tag not in skip:
            result[tag] = copy.deepcopy(font[tag])

    # 确保必要表存在
    if "post" not in result:
        result["post"] = newTable("post")
        result["post"].formatType = 3.0

    # 3. 使用 FontBuilder 构建 CFF
    fb = FontBuilder(font=result)

    # 从 name 表获取信息
    ps_name = font["name"].getDebugName(6) or "ConvertedFont"
    family = font["name"].getBestFamilyName() or "Converted"

    font_info = {
        "version": "001.000",
        "FamilyName": family,
        "isFixedPitch": bool(font["post"].isFixedPitch) if "post" in font else 0,
        "ItalicAngle": float(font["post"].italicAngle) if "post" in font else 0,
        "UnderlinePosition": int(font["post"].underlinePosition) if "post" in font else -100,
        "UnderlineThickness": int(font["post"].underlineThickness) if "post" in font else 50,
    }

    fb.setupGlyphOrder(order)
    fb.setupCFF(psName=ps_name, charStringsDict=charstrings,
                fontInfo=font_info, privateDict={})
    # 不添加 DSIG (避免 dummy DSIG 问题)
    fb.setupHorizontalMetrics({gn: font["hmtx"].metrics[gn]
                               for gn in order if gn in font["hmtx"].metrics})
    fb.setupMaxp()
    fb.setupPost()

    # ---- Windows/Office 兼容性修复 ----
    _apply_windows_fixes(result, font)

    return result


def _apply_windows_fixes(result, source_font):
    """应用 Windows/Office 兼容性修复 (参考 windows-font-fixing skill)"""
    # 1. CFF Weight 字段 (浏览器/Office 读取此字段覆盖 OS/2.usWeightClass)
    if "CFF " in result:
        cff = result["CFF "].cff.topDictIndex[0]
        weight_map = {100: "Thin", 200: "Extra-light", 300: "Light",
                      400: "Regular", 500: "Medium", 600: "Semi-bold",
                      700: "Bold", 800: "Extra-bold", 900: "Black"}
        usWeight = result["OS/2"].usWeightClass if "OS/2" in result else 400
        cff.rawDict["Weight"] = weight_map.get(usWeight, "Regular")

    # 2. Fix nameID 2 RIBBI compliance ("Roman" -> "Regular")
    for r in result["name"].names:
        if r.nameID == 2:
            val = r.toUnicode()
            if val == "Roman":
                r.string = "Regular"
            elif val == "Italic":
                r.string = "Italic"
            elif val == "Bold Italic":
                r.string = "Bold Italic"

    # 3. 确保 nameID 16/17 存在 (Windows 字体菜单分组)
    name1 = result["name"].getDebugName(1) or result["name"].getBestFamilyName() or "Converted"
    name2 = "Regular"
    for r in result["name"].names:
        if r.nameID == 2 and r.platformID == 3:
            name2 = r.toUnicode()
    has16 = any(r.nameID == 16 for r in result["name"].names)
    has17 = any(r.nameID == 17 for r in result["name"].names)
    if not has16:
        result["name"].setName(name1, 16, 3, 1, 0x0409)
    if not has17:
        result["name"].setName(name2, 17, 3, 1, 0x0409)

    # 4. Fix post table underline values (0 can cause renderer issues)
    if "post" in result:
        if result["post"].underlinePosition == 0:
            result["post"].underlinePosition = -100
        if result["post"].underlineThickness == 0:
            result["post"].underlineThickness = 50

    # 5. OS/2 version upgrade (needed for proper Windows rendering)
    if "OS/2" in result:
        os2 = result["OS/2"]
        if os2.version < 3:
            # 补充 v2+ 必需字段
            if not hasattr(os2, 'sxHeight') or os2.sxHeight == 0:
                os2.sxHeight = os2.sTypoAscender // 2 if os2.sTypoAscender > 0 else 500
            if not hasattr(os2, 'sCapHeight') or os2.sCapHeight == 0:
                os2.sCapHeight = os2.sTypoAscender if os2.sTypoAscender > 0 else 700
            os2.usDefaultChar = getattr(os2, 'usDefaultChar', 0)
            os2.usBreakChar = getattr(os2, 'usBreakChar', 32)
            os2.usMaxContext = getattr(os2, 'usMaxContext', 0)
            os2.version = 3

    # 6. head.checkSumAdjustment — 强制重新计算
    if "head" in result:
        result["head"].checkSumAdjustment = 0

    # 7. 移除可能导致 Windows 兼容问题的表
    for tag in ("DSIG", "PCLT", "LTSH", "hdmx", "VDMX", "meta", "trak"):
        if tag in result:
            del result[tag]


def _fallback_glyf_to_cff(glyph_set, gn, width):
    try:
        tt_pen = TTGlyphPen(None)
        cu2qu_pen = Cu2QuPen(tt_pen, max_err=1.0, reverse_direction=False)
        glyph_set[gn].draw(cu2qu_pen)
        cleaned = tt_pen.glyph()
        t2_pen = T2CharStringPen(width=width, glyphSet=None)
        qu2cu_pen = Qu2CuPen(t2_pen, max_err=1.0, all_cubic=True,
                             reverse_direction=True)
        cleaned.draw(pen=qu2cu_pen, glyfTable=None)
        return t2_pen.getCharString()
    except Exception:
        t2_pen = T2CharStringPen(width=width, glyphSet=None)
        return t2_pen.getCharString()


def convert_font_format(font, to_cff):
    """将字体转换为目标轮廓格式"""
    if is_cff(font) == to_cff:
        return copy.deepcopy(font)
    if to_cff:
        return glyf_to_cff(font)
    else:
        return cff_to_glyf(font)
