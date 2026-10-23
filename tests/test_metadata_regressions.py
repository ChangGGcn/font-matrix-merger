"""中性合成字体的元数据回归；不读取本地字体配置。"""
import copy
import io
import os
import sys
import traceback

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
sys.path.insert(0, _project_dir)

from FontMerger.core.glyph_copy import merge_glyphs_object
from FontMerger.tables.maxp import merge_maxp
from FontMerger.tables.metrics import merge_hmtx
from FontMerger.tables.os2 import merge_os2


def _font(names, cmap=None, widths=None):
    """在内存中构造无外部字体依赖的最小 TTF。"""
    order = [".notdef"] + list(names)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap or {65 + i: n for i, n in enumerate(names)})
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        pen.moveTo((0, -200))
        pen.lineTo((400, -200))
        pen.lineTo((400, 700))
        pen.lineTo((0, 700))
        pen.closePath()
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: ((widths or {}).get(n, 500), 0)
                               for n in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200,
                usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Neutral", "styleName": "Regular",
                       "uniqueFontIdentifier": "Neutral-1",
                       "fullName": "Neutral Regular",
                       "psName": "Neutral-Regular"})
    fb.setupPost()
    fb.setupMaxp()
    return fb.font


def _joined(main, base, names):
    return merge_glyphs_object(main, base, names)


def _reload(font):
    stream = io.BytesIO()
    font.save(stream)
    stream.seek(0)
    return TTFont(stream)


def test_os2_alias_is_not_missing_attribute():
    font = _font(["a"])
    table = font["OS/2"]
    table.fsFirstCharIndex = 65
    table.fsLastCharIndex = 90
    assert table.usFirstCharIndex == 65
    assert table.usLastCharIndex == 90


def test_os2_ranges_follow_actual_cmap():
    main = _font(["a"], {65: "a"})
    base = _font(["b"], {66: "b"})
    base["OS/2"].ulUnicodeRange4 = 0xFFFFFFFF
    merged = _joined(main, base, ["b"])
    merge_os2(merged, main, [base], {"b"})
    assert merged["OS/2"].ulUnicodeRange4 == 0


def test_metrics_only_contain_surviving_glyphs():
    main = _font(["a"])
    base = _font(["b", "dropped"], {66: "b", 67: "dropped"})
    merged = _joined(main, base, ["b"])
    merge_hmtx(merged, main, [base], {"b"})
    assert set(merged["hmtx"].metrics) == set(merged.getGlyphOrder())


def test_maxp_kept_programs_receive_source_resources():
    from fontTools.ttLib.tables.ttProgram import Program
    main = _font(["a"])
    base = _font(["b"], {66: "b"})
    program = Program()
    program.fromBytecode([0xB0, 0, 0x21])
    base["glyf"]["b"].program = program
    base["maxp"].maxStorage = 72
    base["maxp"].maxStackElements = 223
    merged = _joined(main, base, ["b"])
    merge_maxp(merged, main, [base], {"b"})
    assert merged["maxp"].maxStorage == 72
    assert merged["maxp"].maxStackElements == 223



def _set_program(font, name, bytecode):
    from fontTools.ttLib.tables.ttProgram import Program
    program = Program()
    program.fromBytecode(bytecode)
    font["glyf"][name].program = program


def _bundle(font, function=0):
    from array import array
    from fontTools.ttLib import newTable
    from fontTools.ttLib.tables.ttProgram import Program
    for tag, bytecode in (("fpgm", [0xB0, function, 0x2C, 0x2D]),
                           ("prep", [0xB0, function, 0x2B])):
        table = newTable(tag)
        table.program = Program()
        table.program.fromBytecode(bytecode)
        font[tag] = table
    table = newTable("cvt ")
    table.values = array("h", [50, 100])
    font["cvt "] = table
    font["maxp"].maxFunctionDefs = function + 1
    font["maxp"].maxStackElements = 8
    font["maxp"].maxStorage = 72


def _bytes(font, name):
    return bytes(font["glyf"][name].program.getBytecode())


def test_finalizer_uses_official_average_and_context():
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from FontMerger.tables.metadata_recalc import recalc_after_merge
    font = _font(["a", "alternate", "zero", "f", "i", "ffi"],
                 {65: "a", 66: "a", 102: "f", 105: "i"},
                 {".notdef": 500, "a": 100, "alternate": 900,
                  "zero": 0, "f": 500, "i": 500, "ffi": 500})
    addOpenTypeFeaturesFromString(
        font, "feature liga { sub f f i by ffi; } liga;")
    font["OS/2"].xAvgCharWidth = 100
    font["OS/2"].usMaxContext = 1
    font["hmtx"].metrics["stale"] = (9999, 0)
    recalc_after_merge(font)
    assert font["OS/2"].xAvgCharWidth == 500
    assert font["OS/2"].usMaxContext == 3
    assert "alternate" in font.getGlyphOrder()
    assert "ffi" in font.getGlyphOrder()
    assert "stale" not in font["hmtx"].metrics
    reloaded = _reload(font)
    assert reloaded["OS/2"].xAvgCharWidth == 500
    assert reloaded["OS/2"].usMaxContext == 3


def test_finalizer_bmp_clamp_and_clipping_bounds():
    from FontMerger.tables.metadata_recalc import recalc_after_merge
    font = _font(["supplement"], {0x10000: "supplement"})
    font["OS/2"].usWinAscent = 20
    font["OS/2"].usWinDescent = 10
    font["OS/2"].ulCodePageRange1 = 0xFFFFFFFF
    font["OS/2"].ulCodePageRange2 = 0xFFFFFFFF
    typo = (font["OS/2"].sTypoAscender, font["OS/2"].sTypoDescender)
    recalc_after_merge(font)
    assert font["OS/2"].usFirstCharIndex == 0xFFFF
    assert font["OS/2"].usLastCharIndex == 0xFFFF
    assert font["OS/2"].getCodePageRanges() == {0}
    assert font["OS/2"].usWinAscent == 700
    assert font["OS/2"].usWinDescent == 200
    assert (font["OS/2"].sTypoAscender,
            font["OS/2"].sTypoDescender) == typo
    assert font["head"].yMin == -200
    assert font["head"].yMax == 700
    assert _reload(font)["OS/2"].usWinDescent == 200


def test_panose_stays_main_and_does_not_alias():
    main = _font(["a"])
    base = _font(["b"], {66: "b"})
    base["OS/2"].panose.bFamilyType = 2
    base["OS/2"].panose.bWeight = 9
    merged = _joined(main, base, ["b"])
    merge_os2(merged, main, [base], {"b"})
    assert not any(vars(merged["OS/2"].panose).values())
    assert merged["OS/2"].panose is not main["OS/2"].panose
    assert base["OS/2"].panose.bWeight == 9


def test_os2_version_zero_not_upgraded_without_fields():
    main = _font(["a"])
    main["OS/2"].version = 0
    for field in ("sxHeight", "sCapHeight", "usMaxContext",
                  "ulCodePageRange1", "ulCodePageRange2",
                  "usDefaultChar", "usBreakChar"):
        if hasattr(main["OS/2"], field):
            delattr(main["OS/2"], field)
    base = _font(["b"], {66: "b"})
    merged = _joined(main, base, ["b"])
    merge_os2(merged, main, [base], {"b"})
    assert merged["OS/2"].version == 0
    assert _reload(merged)["OS/2"].version == 0


def test_finalizer_does_not_replay_variation_or_layout():
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from FontMerger.tables.metadata_recalc import recalc_after_merge
    font = _font(["a", "alternate"])
    FontBuilder(font=font).setupFvar(
        [("wght", 100, 400, 900, "Weight")], [])
    addOpenTypeFeaturesFromString(
        font, "feature salt { sub a by alternate; } salt;")
    axis_table, layout = font["fvar"], font["GSUB"]
    recalc_after_merge(font)
    assert font["fvar"] is axis_table
    assert font["GSUB"] is layout
    assert _reload(font)["fvar"].axes[0].maxValue == 900


def test_hinting_adopts_complete_bundle_and_resources():
    from FontMerger.core.hinting_policy import apply_hinting_policy
    main = _font(["a"])
    base = _font(["b"], {66: "b"})
    _bundle(base)
    _set_program(base, "b", [0xB0, 0, 0x2B])
    merged = _joined(main, base, ["b"])
    apply_hinting_policy(merged, main, base, {"b"})
    assert all(tag in merged for tag in ("fpgm", "prep", "cvt "))
    assert all(tag not in main for tag in ("fpgm", "prep", "cvt "))
    assert _bytes(merged, "b") == _bytes(base, "b")
    assert merged["maxp"].maxStorage == 72
    assert merged["maxp"].maxFunctionDefs == 1
    assert merged["maxp"].maxSizeOfInstructions >= 3
    assert _reload(merged)["maxp"].maxStorage == 72


def test_hinting_compatible_programs_take_resource_maxima():
    from FontMerger.core.hinting_policy import apply_hinting_policy
    main = _font(["a"])
    base = _font(["b"], {66: "b"})
    _bundle(main)
    _bundle(base)
    main["maxp"].maxStorage = 10
    main["maxp"].maxStackElements = 20
    base["maxp"].maxStackElements = 223
    _set_program(main, "a", [0xB0, 0, 0x2B])
    _set_program(base, "b", [0xB0, 0, 0x2B])
    merged = _joined(main, base, ["b"])
    apply_hinting_policy(merged, main, base, {"b"})
    assert _bytes(merged, "a") == _bytes(main, "a")
    assert _bytes(merged, "b") == _bytes(base, "b")
    assert merged["maxp"].maxStorage == 72
    assert merged["maxp"].maxStackElements == 223
    assert _reload(merged)["maxp"].maxStackElements == 223


def test_hinting_incompatible_bundle_strips_only_new_programs():
    from FontMerger.core.hinting_policy import apply_hinting_policy
    main = _font(["a"])
    base = _font(["b"], {66: "b"})
    _bundle(main, 0)
    _bundle(base, 1)
    main["maxp"].maxStorage = 10
    _set_program(main, "a", [0xB0, 0, 0x2B])
    _set_program(base, "b", [0xB0, 1, 0x2B])
    merged = _joined(main, base, ["b"])
    apply_hinting_policy(merged, main, base, {"b"})
    assert _bytes(merged, "b") == b""
    assert _bytes(merged, "a") == _bytes(main, "a")
    assert _bytes(base, "b") == bytes([0xB0, 1, 0x2B])
    assert merged["maxp"].maxStorage == 10
    assert merged["fpgm"].compile(merged) == main["fpgm"].compile(main)
    assert _bytes(_reload(merged), "b") == b""


def test_hinting_main_prep_alone_blocks_base_adoption():
    from FontMerger.core.hinting_policy import apply_hinting_policy
    main = _font(["a"])
    base = _font(["b"], {66: "b"})
    _bundle(main)
    del main["fpgm"]
    del main["cvt "]
    _bundle(base)
    _set_program(base, "b", [0xB0, 0, 0x2B])
    merged = _joined(main, base, ["b"])
    apply_hinting_policy(merged, main, base, {"b"})
    assert "fpgm" not in merged
    assert "cvt " not in merged
    assert _bytes(merged, "b") == b""
    assert merged["prep"].compile(merged) == main["prep"].compile(main)


def test_hinting_multilevel_preserves_previous_interpreter():
    from FontMerger.core.hinting_policy import apply_hinting_policy
    main = _font(["a"])
    first = _font(["b"], {66: "b"})
    second = _font(["c"], {67: "c"})
    _bundle(first, 0)
    _bundle(second, 1)
    _set_program(first, "b", [0xB0, 0, 0x2B])
    _set_program(second, "c", [0xB0, 1, 0x2B])
    one = _joined(main, first, ["b"])
    apply_hinting_policy(one, main, first, {"b"})
    two = _joined(one, second, ["c"])
    apply_hinting_policy(two, one, second, {"c"})
    assert _bytes(two, "b") == _bytes(first, "b")
    assert _bytes(two, "c") == b""
    assert two["fpgm"].compile(two) == first["fpgm"].compile(first)
    reloaded = _reload(two)
    assert _bytes(reloaded, "b") == _bytes(first, "b")
    assert _bytes(reloaded, "c") == b""


def test_hinting_no_imported_programs_does_not_change_resources():
    from FontMerger.core.hinting_policy import apply_hinting_policy
    main = _font(["a"])
    base = _font(["b", "hinted"], {66: "b", 67: "hinted"})
    _bundle(base)
    _set_program(base, "hinted", [0xB0, 0, 0x2B])
    merged = _joined(main, base, ["b"])
    old = copy.deepcopy(vars(merged["maxp"]))
    apply_hinting_policy(merged, main, base, {"b"})
    merge_maxp(merged, main, [base], {"b"})
    assert vars(merged["maxp"]) == old
    assert "fpgm" not in merged


def test_hinting_axis_mismatch_is_conservatively_stripped():
    from FontMerger.core.hinting_policy import apply_hinting_policy
    main = _font(["a"])
    base = _font(["b"], {66: "b"})
    FontBuilder(font=main).setupFvar(
        [("wght", 100, 400, 900, "Weight")], [])
    _bundle(main)
    _bundle(base)
    _set_program(base, "b", [0xB0, 0, 0x2B])
    merged = _joined(main, base, ["b"])
    apply_hinting_policy(merged, main, base, {"b"})
    assert _bytes(merged, "b") == b""


def _kern(font, pairs, coverage=1):
    from fontTools.ttLib import newTable
    from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0
    table = newTable("kern")
    table.version = 0
    subtable = KernTable_format_0()
    subtable.version = 0
    subtable.coverage = coverage
    subtable.kernTable = pairs
    table.kernTables = [subtable]
    font["kern"] = table


def test_table_policy_drops_stale_tables_and_unions_safe_kern():
    from fontTools.ttLib import newTable
    from FontMerger.core.table_policy import apply_table_policy
    main = _font(["a"])
    base = _font(["b", "dropped"], {66: "b", 67: "dropped"})
    _kern(main, {("a", "a"): -10})
    _kern(base, {("a", "a"): -20, ("a", "b"): -30,
                 ("b", "a"): -40, ("b", "dropped"): -50})
    for tag in ("DSIG", "hdmx", "LTSH"):
        main[tag] = newTable(tag)
    base["VDMX"] = newTable("VDMX")
    merged = _joined(main, base, ["b"])
    apply_table_policy(merged, main, [base], {"b"})
    assert not set(("DSIG", "hdmx", "LTSH", "VDMX")) & set(merged.keys())
    pairs = {}
    for subtable in merged["kern"].kernTables:
        pairs.update(subtable.kernTable)
    assert pairs == {("a", "a"): -10, ("a", "b"): -30,
                     ("b", "a"): -40}
    assert "VDMX" in base and "DSIG" in main
    reloaded = _reload(merged)
    assert sum(len(s.kernTable) for s in reloaded["kern"].kernTables) == 3


def test_kern_unknown_semantics_are_not_imported():
    from FontMerger.core.table_policy import apply_table_policy
    main = _font(["a"])
    base = _font(["b"], {66: "b"})
    _kern(base, {("a", "b"): -30}, coverage=9)
    merged = _joined(main, base, ["b"])
    apply_table_policy(merged, main, [base], {"b"})
    assert "kern" not in merged


def _cff_font(names, cmap, vertical=True):
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    order = [".notdef"] + list(names)
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    charstrings = {}
    for name in order:
        pen = T2CharStringPen(500, None)
        pen.moveTo((0, -200))
        pen.lineTo((400, -200))
        pen.lineTo((400, 700))
        pen.lineTo((0, 700))
        pen.closePath()
        charstrings[name] = pen.getCharString()
    fb.setupCFF("Neutral-Regular", {"FullName": "Neutral Regular",
                                    "FamilyName": "Neutral",
                                    "Weight": "Regular"}, charstrings, {})
    fb.setupHorizontalMetrics({name: (500, 0) for name in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    if vertical:
        fb.setupVerticalMetrics({name: (1000, 100) for name in order})
        fb.setupVerticalHeader(ascent=800, descent=-200)
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200,
                usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Neutral", "styleName": "Regular"})
    fb.setupPost()
    fb.setupMaxp()
    return fb.font


def _vorg(font, default, records):
    from fontTools.ttLib import newTable
    table = newTable("VORG")
    table.majorVersion, table.minorVersion = 1, 0
    table.defaultVertOriginY = default
    table.VOriginRecords = records
    table.numVertOriginYMetrics = len(records)
    font["VORG"] = table


def _joined_cff(main, base):
    result = copy.deepcopy(main)
    added = set(base.getGlyphOrder()) - set(main.getGlyphOrder())
    cs = result["CFF "].cff.topDictIndex[0].CharStrings
    bcs = base["CFF "].cff.topDictIndex[0].CharStrings
    for name in added:
        cs[name] = copy.deepcopy(bcs[name])
        result["hmtx"][name] = base["hmtx"][name]
        if "vmtx" in result:
            result["vmtx"][name] = base["vmtx"][name]
    order = result.getGlyphOrder() + sorted(added)
    result.setGlyphOrder(order)
    result["CFF "].cff.topDictIndex[0].charset = order
    from FontMerger.core.glyph_copy import _copy_cmap_mappings
    _copy_cmap_mappings(result, base, added)
    return result


def test_vorg_unions_per_glyph_not_source_default():
    from FontMerger.core.table_policy import apply_table_policy
    from FontMerger.tables.metadata_recalc import recalc_after_merge
    main = _cff_font(["a"], {65: "a"})
    base = _cff_font(["b"], {66: "b"})
    _vorg(main, 880, {"a": 920})
    _vorg(base, 1000, {"b": 1010})
    merged = _joined_cff(main, base)
    apply_table_policy(merged, main, [base], {"b"})
    assert merged["VORG"]["a"] == 920
    assert merged["VORG"][".notdef"] == 880
    assert merged["VORG"]["b"] == 1010
    assert merged["VORG"].defaultVertOriginY == 880
    recalc_after_merge(merged)
    reloaded = _reload(merged)
    assert reloaded["VORG"]["a"] == 920
    assert reloaded["VORG"]["b"] == 1010
    assert reloaded["maxp"].numGlyphs == 3


def test_base_only_vorg_restores_main_metric_origins():
    from FontMerger.core.table_policy import apply_table_policy
    main = _cff_font(["a"], {65: "a"})
    base = _cff_font(["b"], {66: "b"})
    _vorg(base, 1000, {})
    merged = _joined_cff(main, base)
    apply_table_policy(merged, main, [base], {"b"})
    assert merged["VORG"]["a"] == 800
    assert merged["VORG"][".notdef"] == 800
    assert merged["VORG"]["b"] == 1000
    assert _reload(merged)["VORG"]["a"] == 800


def test_vorg_without_main_origin_evidence_is_not_adopted():
    from FontMerger.core.table_policy import apply_table_policy
    main = _cff_font(["a"], {65: "a"}, vertical=False)
    base = _cff_font(["b"], {66: "b"})
    _vorg(base, 1000, {})
    merged = _joined_cff(main, base)
    apply_table_policy(merged, main, [base], {"b"})
    assert "VORG" not in merged



def test_hinting_unknown_cvar_is_stripped_not_reinterpreted():
    from fontTools.ttLib import newTable
    from FontMerger.core.hinting_policy import apply_hinting_policy
    main = _font(["a"])
    base = _font(["b"], {66: "b"})
    _bundle(base)
    base["cvar"] = newTable("cvar")
    _set_program(base, "b", [0xB0, 0, 0x2B])
    merged = _joined(main, base, ["b"])
    apply_hinting_policy(merged, main, base, {"b"})
    assert _bytes(merged, "b") == b""
    assert "fpgm" not in merged
    assert "cvar" not in merged
    assert _bytes(_reload(merged), "b") == b""


def test_hinting_malformed_environment_falls_back_to_strip():
    from fontTools.ttLib import newTable
    from FontMerger.core.hinting_policy import apply_hinting_policy
    main = _font(["a"])
    base = _font(["b"], {66: "b"})
    main["fpgm"] = newTable("fpgm")
    _bundle(base)
    _set_program(base, "b", [0xB0, 0, 0x2B])
    merged = _joined(main, base, ["b"])
    apply_hinting_policy(merged, main, base, {"b"})
    assert _bytes(merged, "b") == b""
    assert "prep" not in merged
    assert "cvt " not in merged


def test_vertical_metrics_do_not_add_dropped_glyphs():
    from FontMerger.tables.metrics import merge_vmtx
    main = _font(["a"])
    base = _font(["b", "dropped"], {66: "b", 67: "dropped"})
    FontBuilder(font=main).setupVerticalMetrics(
        {name: (1000, 100) for name in main.getGlyphOrder()})
    FontBuilder(font=base).setupVerticalMetrics(
        {name: (1000, 100) for name in base.getGlyphOrder()})
    merged = _joined(main, base, ["b"])
    merge_vmtx(merged, main, [base], {"b"})
    assert set(merged["vmtx"].metrics) == set(merged.getGlyphOrder())


def main():
    tests = [test_os2_alias_is_not_missing_attribute,
             test_os2_ranges_follow_actual_cmap,
             test_metrics_only_contain_surviving_glyphs,
             test_maxp_kept_programs_receive_source_resources,
             test_finalizer_uses_official_average_and_context,
             test_finalizer_bmp_clamp_and_clipping_bounds,
             test_panose_stays_main_and_does_not_alias,
             test_os2_version_zero_not_upgraded_without_fields,
             test_finalizer_does_not_replay_variation_or_layout,
             test_hinting_adopts_complete_bundle_and_resources,
             test_hinting_compatible_programs_take_resource_maxima,
             test_hinting_incompatible_bundle_strips_only_new_programs,
             test_hinting_main_prep_alone_blocks_base_adoption,
             test_hinting_multilevel_preserves_previous_interpreter,
             test_hinting_no_imported_programs_does_not_change_resources,
             test_hinting_axis_mismatch_is_conservatively_stripped,
             test_table_policy_drops_stale_tables_and_unions_safe_kern,
             test_kern_unknown_semantics_are_not_imported,
             test_vorg_unions_per_glyph_not_source_default,
             test_base_only_vorg_restores_main_metric_origins,
             test_vorg_without_main_origin_evidence_is_not_adopted,
             test_hinting_unknown_cvar_is_stripped_not_reinterpreted,
             test_hinting_malformed_environment_falls_back_to_strip,
             test_vertical_metrics_do_not_add_dropped_glyphs]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print("  %s: PASSED" % test.__name__)
        except Exception as error:
            print("  %s: FAILED - %s" % (test.__name__, error))
            traceback.print_exc()
    print("Results: %d/%d passed" % (passed, len(tests)))
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
