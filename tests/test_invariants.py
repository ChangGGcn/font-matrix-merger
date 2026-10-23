"""合并出口不变量回归；只用现场构造字体，不依赖本地字体。"""
import copy
import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from fontTools.fontBuilder import FontBuilder
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from FontMerger.core.invariants import (assert_cmap_union,
                                         assert_font_structure)
from FontMerger.core.verify import _check_layout_integrity


def _font(cmap=None):
    cmap = cmap or {65: "A", 66: "B"}
    order = [".notdef", "A", "B", "A.alt", "B.alt"]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        if name != ".notdef":
            pen.moveTo((20, 0))
            pen.lineTo((300, 0))
            pen.lineTo((300, 600))
            pen.closePath()
        glyphs[name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({g: (600, 20) for g in order})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupCharacterMap(cmap)
    builder.setupNameTable({"familyName": "Audit Fixture",
                            "styleName": "Regular",
                            "psName": "AuditFixture-Regular"})
    builder.setupOS2()
    builder.setupPost()
    builder.setupMaxp()
    builder.font["maxp"].numGlyphs = len(order)
    return builder.font


def _fails(fn, text):
    try:
        fn()
    except AssertionError as error:
        assert text in str(error), str(error)
    else:
        raise AssertionError("未识别故意构造的结构缺陷：%s" % text)


def test_exact_union_and_main_priority():
    main = _font({65: "A"})
    base = _font({65: "A.alt", 66: "B"})
    result = _font()
    assert assert_cmap_union(result, main, base)
    _fails(lambda: assert_cmap_union(main, main, base), "缺失 1")
    for table in result["cmap"].tables:
        table.cmap[65] = "A.alt"
    _fails(lambda: assert_cmap_union(result, main, base), "被覆盖")
    print("  test_exact_union_and_main_priority: 2 码位，丢失/覆盖均检出")


def test_unicode_subtable_and_metric_guards():
    font = _font()
    assert assert_font_structure(font)
    broken = copy.deepcopy(font)
    broken["cmap"].tables[0].cmap = dict(
        broken["cmap"].tables[0].cmap)
    del broken["cmap"].tables[0].cmap[66]
    _fails(lambda: assert_font_structure(broken), "子表不同步")
    broken = copy.deepcopy(font)
    del broken["hmtx"].metrics["B"]
    _fails(lambda: assert_font_structure(broken), "缺少字形度量")
    stream = BytesIO()
    font.save(stream)
    stream.seek(0)
    assert assert_font_structure(TTFont(stream))
    print("  test_unicode_subtable_and_metric_guards: 保存重载，2 类错误检出")


def test_nested_lookup_guard():
    font = _font()
    addOpenTypeFeaturesFromString(font, """
        lookup Swap { sub A by A.alt; } Swap;
        feature calt { sub A' lookup Swap B; } calt;
    """)
    assert not _check_layout_integrity(font)["bad_lookup_references"]
    record = font["GSUB"].table.LookupList.Lookup[1].SubTable[0]
    record.SubstLookupRecord[0].LookupListIndex = 999
    errors = _check_layout_integrity(font)["bad_lookup_references"]
    assert len(errors) == 1 and errors[0][2] == 999, errors
    _fails(lambda: assert_font_structure(font), "bad_lookup_references")
    print("  test_nested_lookup_guard: 1 处嵌套越界精确检出")


def test_glyph_count_guard():
    font = _font()
    font["maxp"].numGlyphs -= 1
    _fails(lambda: assert_font_structure(font), "maxp")
    print("  test_glyph_count_guard: 1 处字形数不同步检出")


def test_high_level_partial_conflicts():
    from FontMerger import FontMerger, create_glyph_subset
    main = create_glyph_subset(_font({65: "A"}), ["A"])
    base = create_glyph_subset(_font({65: "A", 66: "A"}), ["A"])
    before_main = copy.deepcopy(main.getBestCmap())
    before_base = copy.deepcopy(base.getBestCmap())
    result = FontMerger().merge_two(main, base)
    assert result.getBestCmap()[65] == "A"
    added_name = result.getBestCmap()[66]
    assert added_name != "A" and added_name in result.getGlyphOrder()
    assert main.getBestCmap() == before_main
    assert base.getBestCmap() == before_base
    assert assert_font_structure(result)
    print("  test_high_level_partial_conflicts: 2 码位并集，主映射/输入不变")


def test_no_added_glyph_uvs_exit():
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
    from FontMerger import FontMerger, create_glyph_subset
    main = create_glyph_subset(_font({65: "A"}), ["A"])
    base = copy.deepcopy(main)
    uvs = CmapSubtable.newSubtable(14)
    uvs.platformID, uvs.platEncID, uvs.language = 0, 5, 0xFF
    uvs.cmap = {}
    uvs.uvsDict = {0xFE0F: [(65, None)]}
    base["cmap"].tables.append(uvs)
    # 新序列必须保留源字形身份，即使需将默认 UVS 转成显式别名字形。
    fresh = FontMerger().merge_two(main, base)
    from FontMerger import renamed_copy
    explicit = next(table.uvsDict[0xFE0F][0][1]
                    for table in fresh["cmap"].tables if table.format == 14)
    assert explicit is not None and explicit != "A"
    normalized_base = renamed_copy(base, {"A": explicit})
    assert assert_cmap_union(fresh, main, normalized_base)
    assert fresh["hmtx"][explicit] == base["hmtx"]["A"]
    _fails(lambda: assert_cmap_union(main, main, base), "UVS")
    # 重复序列已由主字体覆盖时，不应为了它再复制打底字形。
    main["cmap"].tables.append(copy.deepcopy(uvs))
    result = FontMerger().merge_two(main, base)
    assert result.getGlyphOrder() == main.getGlyphOrder()
    assert any(table.format == 14 and
               table.uvsDict == {0xFE0F: [(65, None)]}
               for table in result["cmap"].tables)
    assert assert_cmap_union(result, main, base)
    print("  test_no_added_glyph_uvs_exit: 0 新字形出口及默认UVS语义保留")


def test_chunked_ttx_exit():
    from unittest.mock import patch
    from FontMerger import FontMerger, create_glyph_subset
    from FontMerger.core.glyph_copy import merge_glyphs_via_ttx
    main = create_glyph_subset(_font({65: "A"}), ["A"])
    base = create_glyph_subset(
        _font({66: "B", 67: "A.alt", 0x10000: "B.alt"}),
        ["B", "A.alt", "B.alt"])
    # 官方 FontBuilder 的 format12 XML 头仅在二进制编译后完整。
    source_stream = BytesIO()
    base.save(source_stream)
    source_stream.seek(0)
    base = TTFont(source_stream)
    def ttx_copy(a, b, names):
        return merge_glyphs_via_ttx(a, b, names, use_ttx=True)
    with patch("FontMerger.core.merger.merge_glyphs_via_ttx", ttx_copy):
        result = FontMerger()._chunked_merge(
            main, base, ["B", "A.alt", "B.alt"], 1)
    assert set(result.getBestCmap()) == {65, 66, 67, 0x10000}
    assert assert_font_structure(result)
    print("  test_chunked_ttx_exit: 3 次TTX注入，4 码位及非BMP保留")


def test_injection_failure_is_not_partial_success():
    from unittest.mock import patch
    from FontMerger import FontMerger, create_glyph_subset
    main = create_glyph_subset(_font({65: "A"}), ["A"])
    base = create_glyph_subset(_font({66: "B"}), ["B"])
    with patch("FontMerger.core.merger.merge_glyphs_via_ttx",
               side_effect=RuntimeError("synthetic injection failure")):
        try:
            FontMerger().merge_two(main, base)
        except RuntimeError as error:
            assert "合并未完成" in str(error), str(error)
        else:
            raise AssertionError("注入失败却被报为成功")
    assert main.getBestCmap() == {65: "A"}
    print("  test_injection_failure_is_not_partial_success: 1 次注入失败明确终止")


def test_upm_vorg_override_not_double_scaled():
    from fontTools.ttLib import newTable
    from FontMerger import glyf_to_cff
    from FontMerger.core.merger import _normalize_upm
    main = _font()
    main["head"].unitsPerEm = 2000
    base = glyf_to_cff(_font())
    base["OS/2"].sTypoAscender = 800
    vorg = newTable("VORG")
    vorg.majorVersion, vorg.minorVersion = 1, 0
    vorg.defaultVertOriginY = 900
    vorg.VOriginRecords = {"A": 950}
    base["VORG"] = vorg
    result = _normalize_upm(main, base)
    assert result["head"].unitsPerEm == 2000
    assert result["VORG"].defaultVertOriginY == 1800
    assert result["VORG"].VOriginRecords["A"] == 1900
    assert result["OS/2"].sTypoAscender == 1600
    assert result["hhea"].ascent == 1600
    assert base["VORG"].VOriginRecords["A"] == 950
    stream = BytesIO()
    result.save(stream)
    stream.seek(0)
    assert TTFont(stream)["VORG"].VOriginRecords["A"] == 1900
    print("  test_upm_vorg_override_not_double_scaled: 1000→2000，原点1800/1900")


def test_invalid_default_uvs_is_input_error():
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
    from FontMerger import FontMerger
    main = _font({65: "A"})
    base = copy.deepcopy(main)
    uvs = CmapSubtable.newSubtable(14)
    uvs.platformID, uvs.platEncID, uvs.language = 0, 5, 0
    uvs.cmap = {}
    uvs.uvsDict = {0xFE0F: [(0x99, None)]}
    base["cmap"].tables.append(uvs)
    try:
        FontMerger().merge_two(main, base)
    except ValueError as error:
        assert "输入打底字体" in str(error) and "非法默认 UVS" in str(error)
    else:
        raise AssertionError("未拒绝无基础码位的默认UVS")
    assert main.getBestCmap() == {65: "A"}
    print("  test_invalid_default_uvs_is_input_error: 1 个非法序列在修改前拒绝")


def test_private_chunk_rejects_unnormalized_source():
    from FontMerger import FontMerger
    main, base = _font(), _font()
    try:
        FontMerger()._chunked_merge(main, base, ["B"], 1)
    except ValueError as error:
        assert "先完成打底同名归一" in str(error)
    else:
        raise AssertionError("未归一的分块来源未被拒绝")
    print("  test_private_chunk_rejects_unnormalized_source: 前置契约明确拒绝")


def test_decomposed_comparison_checks_real_component_geometry():
    from fontTools.pens.recordingPen import (RecordingPen,
                                             DecomposingRecordingPen)
    from FontMerger import renamed_copy
    font = _font()
    pen = TTGlyphPen(font.getGlyphSet())
    pen.addComponent("A", (1, 0, 0, 1, 40, 0))
    font["glyf"]["B"] = pen.glyph()
    renamed = renamed_copy(font, {"A": "source.A"})
    def draw(value, decomposed):
        glyphs = value.getGlyphSet()
        out = (DecomposingRecordingPen(glyphs) if decomposed
               else RecordingPen())
        glyphs["B"].draw(out)
        return out.value
    assert draw(font, False) != draw(renamed, False)
    assert draw(font, True) == draw(renamed, True)
    broken = copy.deepcopy(renamed)
    broken["glyf"]["source.A"].coordinates[1] = (321, 0)
    # 旧 raw 记录看不到组件内部已坏；严格分解比较能检出真实变化。
    assert draw(renamed, False) == draw(broken, False)
    assert draw(renamed, True) != draw(broken, True)
    print("  test_decomposed_comparison_checks_real_component_geometry: 别名不误报，21单位真错检出")


def main():
    tests = [test_exact_union_and_main_priority,
             test_unicode_subtable_and_metric_guards,
             test_nested_lookup_guard, test_glyph_count_guard,
             test_high_level_partial_conflicts, test_no_added_glyph_uvs_exit,
             test_chunked_ttx_exit, test_injection_failure_is_not_partial_success,
             test_upm_vorg_override_not_double_scaled,
             test_invalid_default_uvs_is_input_error,
             test_private_chunk_rejects_unnormalized_source,
             test_decomposed_comparison_checks_real_component_geometry]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception:
            import traceback
            traceback.print_exc()
    print("Results: %d/%d passed" % (passed, len(tests)))
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
