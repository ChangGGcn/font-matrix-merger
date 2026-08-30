#!/usr/bin/env python3
"""FontMerger 单元测试"""
import os, sys, copy, tempfile

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_dir = os.path.dirname(os.path.dirname(_script_dir))
_test_fonts_dir = os.path.join(_project_dir, "test")
sys.path.insert(0, _project_dir)

from FontMerger import *
from fontTools.ttLib import TTFont


def test_detect():
    """测试字体检测"""
    otf = TTFont(os.path.join(_test_fonts_dir, "OpenType", "ClassicoURW-Reg.otf"))
    ttf = TTFont(os.path.join(_test_fonts_dir, "TrueType", "tt0015m_.ttf"))
    vf = TTFont(os.path.join(_test_fonts_dir, "otf_variable_fonts",
                              "SourceHanSansCN-VF.otf"))

    assert is_cff(otf), "OTF should be CFF"
    assert not is_ttf(otf), "OTF should not be TTF"
    assert not is_variable(otf), "static OTF should not be variable"

    assert is_ttf(ttf), "TTF should be glyf-based"
    assert not is_cff(ttf), "TTF should not be CFF"

    assert is_variable(vf), "VF should be variable"
    assert is_cff(vf), "VF OTF should be CFF"

    print("  test_detect: PASSED")


def test_conflict():
    """测试冲突检测"""
    otf = TTFont(os.path.join(_test_fonts_dir, "OpenType", "ClassicoURW-Reg.otf"))
    ttf = TTFont(os.path.join(_test_fonts_dir, "TrueType", "tt0015m_.ttf"))

    conflicts = resolve_conflicts(otf, ttf)
    assert isinstance(conflicts, set), "Conflicts should be a set"
    assert ".notdef" not in conflicts, ".notdef should be exempt"
    print(f"  test_conflict: {len(conflicts)} conflicts found, PASSED")


def test_naming():
    """测试名称处理"""
    otf = TTFont(os.path.join(_test_fonts_dir, "OpenType", "ClassicoURW-Reg.otf"))
    otf_copy = copy.deepcopy(otf)

    cr = get_copyrights(otf, otf)
    fn = get_family(otf)
    result = apply_naming(otf_copy, fn, cr)

    new_fn = get_family(result)
    assert "mod" in new_fn, "Family name should contain 'mod'"
    print("  test_naming: PASSED")


def test_merge_otf_otf():
    """测试 OTF+OTF 合并"""
    otf1 = TTFont(os.path.join(_test_fonts_dir, "OpenType", "ClassicoURW-Reg.otf"))
    otf2 = TTFont(os.path.join(_test_fonts_dir, "OpenType", "FZHengFSJF-R.OTF"))

    merger = FontMerger()
    result = merger.merge_two(otf1, otf2)

    assert len(result.getGlyphOrder()) > len(otf1.getGlyphOrder()), \
        f"Should have more glyphs: {len(result.getGlyphOrder())} vs {len(otf1.getGlyphOrder())}"
    print(f"  test_merge_otf_otf: {len(otf1.getGlyphOrder())} → {len(result.getGlyphOrder())} glyphs, PASSED")


def test_merge_ttf_ttf():
    """测试 TTF+TTF 合并"""
    ttf1 = TTFont(os.path.join(_test_fonts_dir, "TrueType", "tt0015m_.ttf"))
    ttf2 = TTFont(os.path.join(_test_fonts_dir, "TrueType", "FZYASHJW.TTF"))

    merger = FontMerger()
    result = merger.merge_two(ttf1, ttf2)

    assert len(result.getGlyphOrder()) > len(ttf1.getGlyphOrder()), \
        f"Should have more glyphs"
    print(f"  test_merge_ttf_ttf: {len(ttf1.getGlyphOrder())} → {len(result.getGlyphOrder())} glyphs, PASSED")


def test_table_registry():
    """测试表合并注册表"""
    from FontMerger.tables.base import TABLE_MERGE_REGISTRY
    expected = {"head", "hhea", "vhea", "OS/2", "post", "name",
                "cmap", "hmtx", "vmtx", "GSUB", "GPOS", "GDEF",
                "fvar", "avar", "kern", "maxp"}
    registered = set(TABLE_MERGE_REGISTRY.keys())
    missing = expected - registered
    assert not missing, f"Missing table handlers: {missing}"
    print(f"  test_table_registry: {len(registered)} handlers, PASSED")


def test_high_level_api():
    """测试高级 API"""
    main_path = os.path.join(_test_fonts_dir, "OpenType", "ClassicoURW-Reg.otf")
    base_path = os.path.join(_test_fonts_dir, "OpenType", "FZHengFSJF-R.OTF")

    result = merge_fonts(main_path, [base_path], interactive=False)
    assert len(result.getGlyphOrder()) > 657, "Should add glyphs"
    print(f"  test_high_level_api: {len(result.getGlyphOrder())} glyphs, PASSED")


def main():
    print("FontMerger Test Suite")
    print("=" * 50)

    tests = [
        test_detect, test_conflict, test_naming,
        test_table_registry, test_merge_ttf_ttf,
        test_merge_otf_otf, test_high_level_api,
    ]

    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  {test.__name__}: FAILED - {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*50}")
    print(f"  Results: {passed}/{len(tests)} passed")

    return passed == len(tests)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
