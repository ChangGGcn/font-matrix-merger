# -*- coding: utf-8 -*-
"""中性最小字体回归：位置/长度、竖排原点、指令策略及格式保存。"""

import contextlib
import io
import os
import sys
import traceback
from array import array

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.psCharStrings import T2CharString
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables.ttProgram import Program

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
from FontMerger.format.converter import cff_to_glyf, glyf_to_cff
from FontMerger.format.transform import apply_scale_offset, scale_font


def _rect(pen, top):
    pen.moveTo((20, -100))
    pen.lineTo((420, -100))
    pen.lineTo((420, top))
    pen.lineTo((20, top))
    pen.closePath()


def _font(cff=False, vorg=False, variable=False, hinted=False):
    """所有数值均为设计单位；不依赖外部字体。"""
    order = [".notdef", "x", "H", "composite"]
    fb = FontBuilder(1000, isTTF=not cff)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({120: "x", 72: "H", 192: "composite"})
    glyphs = {}
    for name in order:
        pen = (T2CharStringPen(600, None) if cff else TTGlyphPen(None))
        if name in ("x", "H"):
            _rect(pen, 400 if name == "x" else 700)
        elif name == "composite":
            if cff:
                _rect(pen, 500)
            else:
                pen = TTGlyphPen(glyphs)
                pen.addComponent("H", (0.5, 0, 0.25, 0.75, 20, 30))
        glyphs[name] = (pen.getCharString() if cff else pen.glyph())
    if cff:
        fb.setupCFF("NeutralRegression", {"FamilyName": "Neutral"},
                    glyphs, {})
    else:
        fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (600, 20) for n in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200, lineGap=100)
    fb.setupNameTable({"familyName": "Neutral", "styleName": "Regular",
                       "psName": "NeutralRegression"})
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200,
                sTypoLineGap=100, usWinAscent=850, usWinDescent=250,
                sxHeight=400, sCapHeight=700, yStrikeoutPosition=300,
                yStrikeoutSize=50)
    fb.setupPost(underlinePosition=-100, underlineThickness=50)
    fb.setupMaxp()
    tops = {".notdef": 0, "x": 400, "H": 700,
            "composite": 500 if cff else 555}
    origins = {n: 950 if vorg and n == "H" else 900 for n in order}
    fb.setupVerticalMetrics({n: (1000, origins[n] - tops[n]) for n in order})
    fb.setupVerticalHeader(ascent=500, descent=-500, lineGap=80)
    if vorg:
        fb.setupVerticalOrigins(origins, defaultVerticalOrigin=900)
    if variable:
        fb.setupFvar([("wght", 100, 400, 900, "Weight")], [])
        deltas = [(0, 20), (0, 20), (0, 40), (0, 40)]
        deltas += [(0, 0)] * 4
        fb.setupGvar({"H": [TupleVariation(
            {"wght": (0, 1, 1)}, deltas)]})
    font = fb.font
    if hinted and not cff:
        p = Program()
        p.fromBytecode([0xB0, 0, 0x2F])
        font["glyf"]["H"].program = p
        for tag in ("fpgm", "prep"):
            font[tag] = newTable(tag)
            font[tag].program = Program()
            font[tag].program.fromBytecode([0xB0, 0, 0x21])
        font["cvt "] = newTable("cvt ")
        font["cvt "].values = array("h", [100, 200])
        font["maxp"].maxZones = 2
        font["maxp"].maxStorage = 1
        font["maxp"].maxFunctionDefs = 1
    return font


def _cff2_font():
    font = _font(cff=True)
    fb = FontBuilder(font=font)
    fb.setupFvar([("wght", 100, 400, 900, "Weight")], [])
    glyphs = {}
    for name in font.getGlyphOrder():
        program = [] if name == ".notdef" else [
            20, -100, 20, 1, "blend", "rmoveto",
            400, 0, 0, 800, -400, 0, "rlineto"]
        glyphs[name] = T2CharString(program=program)
    fb.setupCFF2(glyphs, regions=[{"wght": (0, 1, 1)}])
    del font["CFF "]
    return _reload(font)


def _bounds(font, name, location=None):
    glyph_set = font.getGlyphSet(location=location)
    pen = BoundsPen(glyph_set)
    glyph_set[name].draw(pen)
    return pen.bounds


def _reload(font):
    data = io.BytesIO()
    font.save(data)
    data.seek(0)
    result = TTFont(data)
    result.ensureDecompiled()
    return result


def _capture(call, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = call(*args)
    return result, out.getvalue()


def test_vertical_positions_and_lengths():
    font = _font()
    assert scale_font(font, 1.5, 40) is font
    os2 = font["OS/2"]
    assert (os2.sTypoAscender, os2.sTypoDescender,
            os2.sTypoLineGap) == (1240, -260, 150)
    assert (os2.usWinAscent, os2.usWinDescent) == (1315, 335)
    assert (os2.sxHeight, os2.sCapHeight) == (640, 1090)
    assert (os2.yStrikeoutPosition, os2.yStrikeoutSize) == (490, 75)
    assert (font["hhea"].ascent, font["hhea"].descent,
            font["hhea"].lineGap) == (1240, -260, 150)
    assert (font["vhea"].ascent, font["vhea"].descent,
            font["vhea"].lineGap) == (750, -750, 120)
    assert (font["post"].underlinePosition,
            font["post"].underlineThickness) == (-110, 75)
    reloaded = _reload(font)
    assert (reloaded["glyf"]["H"].yMin,
            reloaded["glyf"]["H"].yMax) == (-110, 1090)
    assert reloaded["head"].unitsPerEm == 1000


def test_negative_offset_win_descent():
    font = apply_scale_offset(_font(), 100, -50)
    assert font["OS/2"].usWinAscent == 800
    assert font["OS/2"].usWinDescent == 300
    assert font["OS/2"].sTypoLineGap == 100
    assert _reload(font)["glyf"]["H"].yMin == -150


def test_vertical_origin_without_vorg():
    font = scale_font(_font(), 1.5, 40)
    # 无显式 VORG 时维持隐式竖排原点，只移动轮廓，tsb 抵消位移。
    assert font["vmtx"].metrics["H"] == (1500, 260)
    font = _reload(font)
    assert font["glyf"]["H"].yMax + font["vmtx"].metrics["H"][1] == 1350


def test_vertical_origin_with_vorg():
    font = scale_font(_font(cff=True, vorg=True), 1.5, 40)
    # 显式原点与轮廓同移，tsb 不再额外减 offset。
    assert font["VORG"].defaultVertOriginY == 1390
    assert font["VORG"].VOriginRecords["H"] == 1465
    assert font["vmtx"].metrics["H"] == (1500, 375)
    font = _reload(font)
    assert font["VORG"]["H"] == 1465
    assert font["vmtx"].metrics["H"] == (1500, 375)


def test_identity_preserves_hinting():
    font = _font(hinted=True)
    result, log = _capture(scale_font, font, 1.0, 0)
    assert result is font
    assert list(font["glyf"]["H"].program.getBytecode()) == [0xB0, 0, 0x2F]
    assert "fpgm" in font and "prep" in font and "cvt " in font
    assert log == ""


def test_nonidentity_removes_hinting_consistently():
    for factor, offset in ((1.0, 50), (1.5, 0)):
        font, log = _capture(scale_font, _font(hinted=True), factor, offset)
        assert "hint" in log.lower() and "[告警]" in log
        for tag in ("fpgm", "prep", "cvt ", "cvar"):
            assert tag not in font, tag
        font = _reload(font)
        for glyph in font["glyf"].glyphs.values():
            assert not getattr(glyph, "program", Program()).getBytecode()
        assert font["maxp"].maxStorage == 0
        assert font["maxp"].maxFunctionDefs == 0


def test_composite_transform_preserves_topology():
    font = scale_font(_font(), 1.5, 40)
    glyph = font["glyf"]["composite"]
    assert glyph.isComposite()
    assert glyph.components[0].glyphName == "H"
    # 原矩阵 y=0.75*y+30；整体缩放后再平移，而非重复平移部件。
    # fontTools 的 otRound(-27.5) 为 -27，不能用 Python 银行家舍入。
    assert glyph.yMin == -27
    assert glyph.yMax == 873
    assert _reload(font)["glyf"]["composite"].isComposite()


def test_gvar_transform_preserves_deltas():
    font = scale_font(_font(variable=True), 1.5, 40)
    assert len(font["glyf"]["H"].coordinates) == 4
    assert font["gvar"].variations["H"][0].coordinates[:4] == [
        (0, 30), (0, 30), (0, 60), (0, 60)]
    font = _reload(font)
    assert "fvar" in font and "gvar" in font
    assert len(font["gvar"].variations["H"][0].coordinates) == 8
    from fontTools.varLib.instancer import instantiateVariableFont
    static = instantiateVariableFont(font, {"wght": 900}, inplace=False)
    assert (static["glyf"]["H"].yMin, static["glyf"]["H"].yMax) == (-80, 1150)


def test_vdmx_removed_with_warning():
    font = _font()
    font["VDMX"] = newTable("VDMX")
    font["VDMX"].groups = [{12: (9, -3), 24: (18, -6)}]
    font, log = _capture(scale_font, font, 1.0, 50)
    assert "VDMX" not in font
    assert "VDMX" in log and "[告警]" in log
    assert "VDMX" not in _reload(font)


def test_scale_upem_already_scales_vertical_metrics():
    font = _font(vorg=True)
    scale_upem(font, 2000)
    assert font["head"].unitsPerEm == 2000
    assert (font["OS/2"].sTypoAscender, font["OS/2"].sTypoDescender,
            font["OS/2"].sTypoLineGap) == (1600, -400, 200)
    assert (font["OS/2"].usWinAscent,
            font["OS/2"].usWinDescent) == (1700, 500)
    assert (font["hhea"].ascent, font["hhea"].descent) == (1600, -400)
    assert font["vhea"].lineGap == 160
    assert font["vmtx"].metrics["H"] == (2000, 500)
    assert font["VORG"].defaultVertOriginY == 1800


def test_cff_to_glyf_saves_true_type_maxp():
    source = _font(cff=True)
    assert source["maxp"].tableVersion == 0x00005000
    result = cff_to_glyf(source)
    assert "loca" in result
    assert result["maxp"].tableVersion == 0x00010000
    assert "CFF " in source and "glyf" not in source
    result = _reload(result)
    assert len(result["loca"].locations) == 5
    assert (result["glyf"]["H"].yMin, result["glyf"]["H"].yMax) == (-100, 700)
    assert result["maxp"].numGlyphs == 4


def test_cff_to_glyf_retains_explicit_origin_in_tsb():
    source = _font(cff=True, vorg=True)
    # 显式 VORG 是权威来源，即使旧 tsb 不一致也应在转换时纠正。
    source["vmtx"].metrics["H"] = (1000, 200)
    result = _reload(cff_to_glyf(source))
    assert "VORG" not in result
    assert result["glyf"]["H"].yMax + result["vmtx"].metrics["H"][1] == 950


def test_cff_width_tracks_scaled_advance():
    font = scale_font(_font(cff=True), 1.5, 40)
    assert _bounds(font, "H") == (30, -110, 630, 1090)
    assert font["hmtx"].metrics["H"] == (900, 30)
    font = _reload(font)
    charstring = font["CFF "].cff.topDictIndex[0].CharStrings["H"]
    charstring.draw(BoundsPen(None))
    assert charstring.width == 900
    assert _bounds(font, "H") == (30, -110, 630, 1090)


def test_cff2_blend_survives_transform():
    font = scale_font(_cff2_font(), 1.5, 40)
    assert "CFF2" in font and "fvar" in font
    assert _bounds(font, "H") == (30, -110, 630, 1090)
    assert _bounds(font, "H", {"wght": 900}) == (30, -80, 630, 1120)
    program = font["CFF2"].cff.topDictIndex[0].CharStrings["H"].program
    assert "blend" in program
    font = _reload(font)
    assert font["head"].unitsPerEm == 1000
    assert _bounds(font, "H", {"wght": 900}) == (30, -80, 630, 1120)


def test_conversion_hinting_policy_is_explicit():
    source = _font(cff=True)
    cs = source["CFF "].cff.topDictIndex[0].CharStrings["H"]
    cs.program[1:1] = [10, 20, "hstem"]
    cs.private.BlueValues = [-100, -90, 690, 700]
    result, log = _capture(cff_to_glyf, source)
    assert "[告警]" in log and "hint" in log.lower()
    assert "hstem" in cs.program
    assert not result["glyf"]["H"].program.getBytecode()
    result, log = _capture(glyf_to_cff, _font(hinted=True))
    assert "[告警]" in log and "hint" in log.lower()
    assert all(tag not in result for tag in ("cvt ", "fpgm", "prep"))
    assert _reload(result)["maxp"].tableVersion == 0x00005000


def test_cross_outline_variable_conversion_is_rejected():
    for font, convert, tag in ((_font(variable=True), glyf_to_cff, "gvar"),
                               (_cff2_font(), cff_to_glyf, "CFF2")):
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                convert(font)
        except ValueError as exc:
            assert "variable_to_static" in str(exc)
        else:
            raise AssertionError("不能将可变默认轮廓静默烘焙")
        assert "[告警]" in out.getvalue()
        assert "fvar" in font and tag in font
        assert font["fvar"].axes[0].defaultValue == 400


def test_composite_gvar_and_point_matching_survive():
    font = _font(variable=True)
    font["gvar"].variations["composite"] = [TupleVariation(
        {"wght": (0, 1, 1)}, [(0, 20)] + [(0, 0)] * 4)]
    from fontTools.varLib.instancer import instantiateVariableFont
    original = instantiateVariableFont(font, {"wght": 900}, inplace=False)
    # 部件自身的 H 变化也要计入：740*0.75+30+20 = 605。
    assert original["glyf"]["composite"].yMax == 605
    font = _reload(scale_font(font, 1.5, 40))
    assert font["glyf"]["composite"].isComposite()
    assert font["gvar"].variations["composite"][0].coordinates[0] == (0, 30)
    static = instantiateVariableFont(font, {"wght": 900}, inplace=False)
    assert static["glyf"]["composite"].yMax == 948

    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
    font = _font()
    first = GlyphComponent()
    first.glyphName, first.x, first.y, first.flags = "H", 0, 0, 0
    second = GlyphComponent()
    second.glyphName, second.firstPt, second.secondPt = "x", 0, 3
    second.flags = 0
    glyph = Glyph()
    glyph.numberOfContours = -1
    glyph.components = [first, second]
    font["glyf"]["composite"] = glyph
    font = _reload(scale_font(font, 1.5, 40))
    glyph = font["glyf"]["composite"]
    assert len(glyph.components) == 2
    assert glyph.components[1].firstPt == 0
    assert glyph.components[1].secondPt == 3
    assert (glyph.yMin, glyph.yMax) == (-860, 1090)


def main():
    tests = [
        test_vertical_positions_and_lengths,
        test_negative_offset_win_descent,
        test_vertical_origin_without_vorg,
        test_vertical_origin_with_vorg,
        test_identity_preserves_hinting,
        test_nonidentity_removes_hinting_consistently,
        test_composite_transform_preserves_topology,
        test_gvar_transform_preserves_deltas,
        test_vdmx_removed_with_warning,
        test_scale_upem_already_scales_vertical_metrics,
        test_cff_to_glyf_saves_true_type_maxp,
        test_cff_to_glyf_retains_explicit_origin_in_tsb,
        test_cff_width_tracks_scaled_advance,
        test_cff2_blend_survives_transform,
        test_conversion_hinting_policy_is_explicit,
        test_cross_outline_variable_conversion_is_rejected,
        test_composite_gvar_and_point_matching_survive,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print("  %s: PASSED" % test.__name__)
        except Exception as exc:
            print("  %s: FAILED - %s" % (test.__name__, exc))
            traceback.print_exc()
    print("Results: %d/%d passed" % (passed, len(tests)))
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
