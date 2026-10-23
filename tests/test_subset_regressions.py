"""子集闭包回归：组件与布局依赖必须由 fontTools Subsetter 同步。"""
import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_invariants import _font
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from FontMerger import create_glyph_subset


def test_composite_closure_and_roundtrip():
    font = _font()
    pen = TTGlyphPen(font.getGlyphSet())
    pen.addComponent("A", (1, 0, 0, 1, 40, 0))
    font["glyf"]["B"] = pen.glyph()
    subset = create_glyph_subset(font, ["B"])
    assert ".notdef" in subset.getGlyphOrder(), subset.getGlyphOrder()
    assert "A" in subset.getGlyphOrder(), "复合组件没有进入闭包"
    assert "A.alt" not in subset["glyf"].glyphs
    stream = BytesIO()
    subset.save(stream)
    stream.seek(0)
    reloaded = TTFont(stream)
    assert reloaded["glyf"]["B"].components[0].glyphName == "A"
    assert font.getGlyphOrder() == [".notdef", "A", "B", "A.alt", "B.alt"]
    print("  test_composite_closure_and_roundtrip: 3 字形闭包，输入不变")


def test_layout_output_closure():
    font = _font()
    addOpenTypeFeaturesFromString(
        font, "feature salt { sub A by A.alt; } salt;")
    subset = create_glyph_subset(font, ["A"], strip_layout=False)
    assert set(subset.getGlyphOrder()) == {".notdef", "A", "A.alt"}
    mapping = subset["GSUB"].table.LookupList.Lookup[0].SubTable[0].mapping
    assert mapping == {"A": "A.alt"}, mapping
    stream = BytesIO()
    subset.save(stream)
    stream.seek(0)
    assert "GSUB" in TTFont(stream)
    assert "GSUB" not in create_glyph_subset(font, ["A"])
    print("  test_layout_output_closure: 1 条替换规则闭包保留，strip仍生效")


def test_encoded_empty_glyph_preserved():
    font = _font()
    font["glyf"]["A"] = TTGlyphPen(None).glyph()
    subset = create_glyph_subset(font, (g for g in ["A"]))
    assert subset.getBestCmap() == {65: "A"}, subset.getBestCmap()
    assert set(subset.getGlyphOrder()) == {".notdef", "A"}
    print("  test_encoded_empty_glyph_preserved: 1 个编码空字形保留")


def test_unsupported_tables_are_explicitly_dropped():
    import contextlib
    from io import StringIO
    from fontTools.ttLib import newTable
    from fontTools.ttLib.tables import otTables as ot
    font = _font()
    dsig = newTable("DSIG")
    dsig.ulVersion, dsig.usNumSigs, dsig.usFlag = 1, 0, 0
    dsig.signatureRecords = []
    font["DSIG"] = dsig
    ltsh = newTable("LTSH")
    ltsh.version = 0
    ltsh.yPels = {name: 0 for name in font.getGlyphOrder()}
    font["LTSH"] = ltsh
    jstf = newTable("JSTF")
    jstf.table = ot.JSTF()
    jstf.table.Version = 0x10000
    jstf.table.JstfScriptCount = 0
    jstf.table.JstfScriptRecord = []
    font["JSTF"] = jstf
    log = StringIO()
    with contextlib.redirect_stdout(log):
        subset = create_glyph_subset(font, ["A"], strip_layout=False)
    for tag in ("DSIG", "LTSH", "JSTF"):
        assert tag not in subset and tag in font
        assert tag in log.getvalue(), log.getvalue()
    stream = BytesIO()
    subset.save(stream)
    print("  test_unsupported_tables_are_explicitly_dropped: 3 表删除有告警，来源不变")


def test_missing_requests_keep_legacy_behavior_with_warning():
    import contextlib
    from io import StringIO
    font = _font()
    log = StringIO()
    with contextlib.redirect_stdout(log):
        subset = create_glyph_subset(font, ["absent.glyph"])
    assert subset.getGlyphOrder() == [".notdef"]
    assert "1 个请求字形不存在" in log.getvalue()
    print("  test_missing_requests_keep_legacy_behavior_with_warning: 1 缺失请求明确告警")


def main():
    tests = [test_composite_closure_and_roundtrip,
             test_layout_output_closure, test_encoded_empty_glyph_preserved,
             test_unsupported_tables_are_explicitly_dropped,
             test_missing_requests_keep_legacy_behavior_with_warning]
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
