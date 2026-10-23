"""命名回归：仅构造中性字体，不依赖外部字体或额外测试框架。"""
import io
import os
import sys
import traceback

from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
sys.path.insert(0, _project_dir)

from FontMerger import apply_naming, get_copyrights, get_family


def _font(family="Neutral Family", style="Regular"):
    """创建含两个字形的最小 TrueType 字体。"""
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder([".notdef", "space"])
    builder.setupCharacterMap({32: "space"})
    pen = TTGlyphPen(None)
    builder.setupGlyf({g: pen.glyph() for g in (".notdef", "space")})
    builder.setupHorizontalMetrics({g: (500, 0)
                                    for g in (".notdef", "space")})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": family, "styleName": style,
                            "fullName": family + " " + style,
                            "psName": "NeutralFamily-" + style,
                            "uniqueFontIdentifier": "Neutral;" + style,
                            "version": "Version 1.000",
                            "copyright": "Neutral main rights"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200,
                    usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    return builder.font


def _set(font, name_id, text, lang=0x0409, platform=3, encoding=1):
    font["name"].setName(text, name_id, platform, encoding, lang)


def _get(font, name_id, lang=0x0409, platform=3, encoding=1):
    record = font["name"].getName(name_id, platform, encoding, lang)
    return record.toUnicode() if record is not None else None


def _snapshot(font):
    return sorted((r.nameID, r.platformID, r.platEncID,
                   r.langID, r.toUnicode()) for r in font["name"].names)


def _roundtrip(font):
    data = io.BytesIO()
    font.save(data)
    data.seek(0)
    return TTFont(data)


def _localized():
    font = _font()
    for name_id, text in ((1, "中性字族"), (2, "常规"),
                          (4, "中性字族 常规"), (0, "中性主版权")):
        _set(font, name_id, text, 0x0804)
    return font


def test_family_selection_is_deterministic():
    font = _localized()
    _set(font, 16, "Neutral Typographic")
    family = get_family(font)
    font["name"].names.reverse()
    assert isinstance(family, str)
    assert family == get_family(font) == "Neutral Typographic"
    print("  族名选择：2 种记录顺序得到相同英文排印族名")


def test_copyrights_preserve_languages_and_list_api():
    main = _localized()
    base = _font("Neutral Base")
    _set(base, 0, "Neutral base rights")
    _set(base, 0, "中性打底版权", 0x0804)
    rights = get_copyrights(main, base)
    assert isinstance(rights, list) and len(rights) == 2
    output = apply_naming(main, get_family(main), list(rights))
    assert _get(output, 0) == "Neutral main rights\n\nNeutral base rights"
    assert _get(output, 0, 0x0804) == "中性主版权\n\n中性打底版权"
    assert _get(output, 1, 0x0804) == "中性字族 mod"
    assert _get(output, 4, 0x0804) == "中性字族 mod 常规"
    assert _get(output, 16, 0x0804) == "中性字族 mod"
    assert _get(output, 17, 0x0804) == "常规"
    assert _get(output, 6, 0x0804) == _get(output, 6)
    output = _roundtrip(output)
    assert "中性打底版权" in _get(output, 0, 0x0804)
    print("  多语言：2 个来源 × 2 种语言版权及 1/4/6/16/17 同步")


def test_plain_inputs_preserve_localized_copyrights():
    font = _localized()
    apply_naming(font, "Neutral Family", ["Neutral main rights",
                                          "Neutral extra rights"])
    assert _get(font, 1) == "Neutral Family mod"
    assert _get(font, 1, 0x0804) == "中性字族 mod"
    assert "中性主版权" in _get(font, 0, 0x0804)
    assert "Neutral extra rights" in _get(font, 0)
    print("  普通 list/str：保留中文原记录并接纳额外版权")


def test_typographic_and_ribbi_names_remain_distinct():
    semibold = _font("Neutral Family Semibold")
    _set(semibold, 16, "Neutral Family")
    _set(semibold, 17, "Semibold")
    _set(semibold, 1, "Neutral Family Semibold", platform=1,
         encoding=0, lang=0)
    regular = _font()
    for font in (semibold, regular):
        apply_naming(font, get_family(font), get_copyrights(font))
    assert _get(semibold, 1) == "Neutral Family mod Semibold"
    assert _get(semibold, 16) == "Neutral Family mod"
    assert _get(semibold, 2) == "Regular"
    assert _get(semibold, 17) == "Semibold"
    assert _get(semibold, 4) == "Neutral Family mod Semibold"
    assert _get(semibold, 6) != _get(regular, 6)
    assert "mod" in _get(semibold, 6)
    print("  RIBBI：保留 Regular/排印 Semibold，2 个字重 PS 名不同")


def test_postscript_names_are_legal_and_collision_resistant():
    names = []
    for family in ("中性字族", "其他字族", "Neutral [One]", "Neutral One",
                   "N" * 100 + "A", "N" * 100 + "B"):
        font = _font()
        apply_naming(font, family, [])
        ps = _get(font, 6)
        assert 1 <= len(ps) <= 63
        assert all(33 <= ord(c) <= 126 and c not in "[](){}<>/%"
                   for c in ps)
        names.append(ps)
    assert len(set(names)) == 6
    print("  PS：6 个非拉丁/非法符号/超长输入，均合法且唯一")


def test_non_latin_without_mac_roman_is_serializable():
    font = _font()
    _set(font, 8, "Neutral Original Maker", platform=1,
         encoding=0, lang=0)
    apply_naming(font, "中性新字族", ["中性版权"])
    loaded = _roundtrip(font)
    assert _get(loaded, 1) == "中性新字族 mod"
    assert _get(loaded, 8, 0, 1, 0) == "Neutral Original Maker"
    assert _get(loaded, 0) == "Neutral main rights\n\n中性版权"
    print("  编码：不可 MacRoman 编码的名称可重载，厂商记录未删")


def test_language_specific_mac_encoding_and_extra_languages():
    font = _localized()
    _set(font, 1, "Famille neutre", 0x040C)
    _set(font, 2, "Normal", 0x040C)
    _set(font, 0, "Droits neutres", 0x040C)
    _set(font, 1, "中性字族", 33, 1, 25)
    _set(font, 0, "中性主版权", 33, 1, 25)
    apply_naming(font, get_family(font), get_copyrights(font))
    loaded = _roundtrip(font)
    assert _get(loaded, 1, 33, 1, 25) == "中性字族 mod"
    assert _get(loaded, 0, 33, 1, 25) == "中性主版权"
    assert _get(loaded, 1, 0x040C) == "Famille neutre mod"
    assert _get(loaded, 17, 0x040C) == "Normal"
    print("  语言编码：中文 Mac 编码与法语本地化各自保留")


def test_naming_is_idempotent_and_preserves_provenance():
    font = _localized()
    for name_id in (7, 8, 9, 11, 13, 14):
        _set(font, name_id, "Neutral provenance %d" % name_id)
    original = {n: _get(font, n) for n in (5, 7, 8, 9, 11, 13, 14)}
    revision = font["head"].fontRevision
    family, rights = get_family(font), get_copyrights(font)
    apply_naming(font, family, rights)
    first = _snapshot(font)
    apply_naming(font, family, rights)
    assert _snapshot(font) == first
    font = _roundtrip(font)
    apply_naming(font, get_family(font), get_copyrights(font))
    assert _snapshot(font) == first
    assert font["head"].fontRevision == revision
    assert {n: _get(font, n) for n in original} == original
    assert "mod" in _get(font, 3)
    print("  幂等：3 次命名含重载完全一致；7 类来源/版本记录未变")


def test_variable_references_and_instance_ps_names_are_untouched():
    font = _font()
    builder = FontBuilder(font=font)
    builder.setupFvar([("wght", 100, 400, 900, "Weight")],
                      [{"location": {"wght": 400},
                        "stylename": "Regular",
                        "postscriptfontname": "NeutralInstance-Regular"}])
    buildStatTable(font, [{"tag": "wght", "name": "Weight",
                           "values": [{"value": 400, "name": "Regular",
                                       "flags": 2}]}])
    before_fvar = font["fvar"].compile(font)
    before_stat = font["STAT"].compile(font)
    before_names = [r for r in _snapshot(font) if r[0] >= 256]
    apply_naming(font, get_family(font), get_copyrights(font))
    font = _roundtrip(font)
    assert font["fvar"].compile(font) == before_fvar
    assert font["STAT"].compile(font) == before_stat
    assert [r for r in _snapshot(font) if r[0] >= 256] == before_names
    print("  VF：fvar/STAT 字节及轴、实例 PS 自定义 name 记录保持不变")


def test_base_only_copyright_language_and_no_false_translation():
    main = _localized()
    base = _font("Neutral Base")
    _set(base, 0, "Neutrale Rechte", 0x0407)
    apply_naming(main, get_family(main), get_copyrights(main, base))
    assert _get(main, 0, 0x0407) == "Neutrale Rechte"
    assert _get(main, 0, 0x0804) == "中性主版权"
    assert "Neutrale Rechte" not in _get(main, 0)
    font = _font()
    font["name"].names = []
    _set(font, 1, "中性字族", 0x0804)
    _set(font, 2, "常规", 0x0804)
    _set(font, 0, "中性版权", 0x0804)
    apply_naming(font, get_family(font), get_copyrights(font))
    assert _get(font, 0) is None
    assert _get(font, 0, 0x0804) == "中性版权"
    assert _get(_roundtrip(main), 0, 0x0407) == "Neutrale Rechte"
    print("  独有版权语言：保留打底德文，不把中文版权伪装成英文")


def test_non_english_styles_have_distinct_ps_names():
    names = []
    for style in ("常规", "粗体"):
        font = _font()
        font["name"].names = []
        _set(font, 1, "中性字族", 0x0804)
        _set(font, 2, style, 0x0804)
        apply_naming(font, get_family(font), [])
        names.append(_get(font, 6))
        assert _get(font, 17, 0x0804) == style
        _roundtrip(font)
    assert len(set(names)) == 2
    print("  无英文样式：2 个本地化字重 PS 名不同")


def test_cff_postscript_identity_matches_name_table():
    builder = FontBuilder(1000, isTTF=False)
    builder.setupGlyphOrder([".notdef"])
    builder.setupCharacterMap({})
    builder.setupHorizontalMetrics({".notdef": (500, 0)})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "Neutral CFF",
                            "styleName": "Regular",
                            "psName": "NeutralCFF-Regular",
                            "fullName": "Neutral CFF Regular"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200,
                    usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    pen = T2CharStringPen(500, None)
    builder.setupCFF("NeutralCFF-Regular",
                     {"FamilyName": "Neutral CFF",
                      "FullName": "Neutral CFF Regular",
                      "Notice": "Neutral original notice",
                      "Copyright": "Neutral original rights"},
                     {".notdef": pen.getCharString()}, {})
    font = builder.font
    apply_naming(font, get_family(font), [])
    font = _roundtrip(font)
    cff = font["CFF "].cff
    assert cff.fontNames == [_get(font, 6)]
    assert cff.topDictIndex[0].FamilyName == _get(font, 16)
    assert cff.topDictIndex[0].FullName == _get(font, 4)
    assert cff.topDictIndex[0].Notice == "Neutral original notice"
    assert cff.topDictIndex[0].Copyright == "Neutral original rights"
    print("  CFF：内部 PS/Family/FullName 与 name 一致，原版权未改")


def main():
    tests = [test_family_selection_is_deterministic,
             test_copyrights_preserve_languages_and_list_api,
             test_plain_inputs_preserve_localized_copyrights,
             test_typographic_and_ribbi_names_remain_distinct,
             test_postscript_names_are_legal_and_collision_resistant,
             test_non_latin_without_mac_roman_is_serializable,
             test_language_specific_mac_encoding_and_extra_languages,
             test_naming_is_idempotent_and_preserves_provenance,
             test_variable_references_and_instance_ps_names_are_untouched,
             test_base_only_copyright_language_and_no_false_translation,
             test_non_english_styles_have_distinct_ps_names,
             test_cff_postscript_identity_matches_name_table]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception:
            print("  %s: FAILED" % test.__name__)
            traceback.print_exc()
    print("Results: %d/%d passed" % (passed, len(tests)))
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
