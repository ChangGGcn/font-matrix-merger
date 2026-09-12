#!/usr/bin/env python3
"""merge_subsets() 同源分片并集合并测试

用例需要一个本地自备的商业授权可变 CJK 字体 — 缺失时自动 SKIP:
  路径经 tests/local_fonts.py 的角色 "vf_ttf_cjk" 配置 (该文件不入库)。

分片由 pyftsubset 现场生成 (见 tests/subset_fixture.py), 因此不依赖任何
webfont 分片文件是否随仓库分发。
"""
import os
import sys
import tempfile

_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
_test_fonts_dir = os.path.join(_project_dir, "test")
sys.path.insert(0, _project_dir)
sys.path.insert(0, _repo_dir)

from fontTools.ttLib import TTFont

from FontMerger import (FontMerger, is_same_source, is_variable, merge_subsets,
                        verify_merge, save_font)
from FontMerger.core.verify import _check_layout_integrity
from tests.subset_fixture import cached_subsets, cached_rich_subsets

#: 本地可变 CJK TTF (商业授权; 经 tests/local_fonts.py 的 "vf_ttf_cjk" 角色配置):
#: 带 gvar/HVAR/VVAR/GDEF VarStore/vert/vrt2/kern/mark
_VF_ROLE = "vf_ttf_cjk"
#: OFL 静态字体 (异源合并用)
_STATIC_TTF = "TrueType/LXGWWenKaiTC-Regular.ttf"
#: OFL CFF2 可变字体 (CFF2 分片并集用)
_CFF2_VF = "otf_variable_fonts/SourceSerif4Variable-Roman.otf"


def _vf():
    """本地授权可变 CJK 字体路径 (tests/local_fonts.py 配置); 未配置/不存在返回 None"""
    try:
        from tests.local_fonts import LOCAL_FONTS
        rel = LOCAL_FONTS.get(_VF_ROLE)
    except ImportError:
        rel = None
    if not rel:
        return None
    p = os.path.join(_test_fonts_dir, rel)
    return p if os.path.exists(p) else None


def _static():
    p = os.path.join(_test_fonts_dir, _STATIC_TTF)
    return p if os.path.exists(p) else None


def _subsets(n=3):
    src = _vf()
    return cached_subsets(src, n=n) if src else None


def _features(font, tag):
    if tag not in font or font[tag].table.FeatureList is None:
        return set()
    return {fr.FeatureTag for fr in font[tag].table.FeatureList.FeatureRecord}


def test_same_source_detection():
    """同源判定: 分片互为同源, 与别的字体不是"""
    paths = _subsets()
    st = _static()
    if not paths or not st:
        print("  test_same_source_detection: SKIP (测试字体未就位)")
        return
    fonts = [TTFont(p) for p in paths]
    assert is_same_source(fonts), "同一字体的分片应判为同源"
    assert not is_same_source([fonts[0], TTFont(st)]), "异源字体不应判为同源"
    assert not is_same_source(fonts[:1]), "单个字体不应判为同源"
    print("  test_same_source_detection: PASSED")


def test_merge_subsets_roundtrip():
    """并集合并: 码位/可变性/布局特性/竖排/name 全部保住"""
    paths = _subsets()
    src_path = _vf()
    if not paths or not src_path:
        print("  test_merge_subsets_roundtrip: SKIP (测试字体未就位)")
        return

    src = TTFont(src_path)
    src_cps = set(src.getBestCmap())
    # pyftsubset 会把"字形全被剪掉"的 feature 整条删掉, 所以判据是
    # **各分片实际带有的 feature 并集**必须全部保留 (源字体独有的 ss14 等
    # 若连分片都没有, 就不该要求合并结果有)。
    subset_feat = {}
    for p in paths:
        f = TTFont(p)
        for tag in ("GSUB", "GPOS"):
            subset_feat.setdefault(tag, set()).update(_features(f, tag))

    merged = merge_subsets(paths, tag="t", verbose=False)

    # 1) 码位完整
    merged_cps = set(merged.getBestCmap())
    assert src_cps <= merged_cps, \
        "码位缺失 %d 个" % len(src_cps - merged_cps)

    # 2) 可变性保留
    assert is_variable(merged), "合并结果必须仍是可变字体"
    for tag in ("gvar", "fvar", "HVAR", "VVAR", "STAT"):
        assert tag in merged, "丢失 %s" % tag
    assert [a.axisTag for a in merged["fvar"].axes] == \
           [a.axisTag for a in src["fvar"].axes]
    assert len(merged["fvar"].instances) == len(src["fvar"].instances)

    # 3) 布局特性 (GSUB 的 vert/vrt2 等, GPOS 的 kern/mark) 全部保留
    for tag in ("GSUB", "GPOS"):
        got = _features(merged, tag)
        missing = subset_feat.get(tag, set()) - got
        assert not missing, "%s 丢失特性 %s" % (tag, sorted(missing))

    # 4) 逐字形 gvar 增量: 新增字形必须有轴变化 (P0 回归)
    gvar = merged["gvar"].variations
    n_varying = sum(1 for gn in merged.getGlyphOrder() if gvar.get(gn))
    assert n_varying > len(src.getGlyphOrder()), \
        "新增字形没有 gvar 增量 (n=%d)" % n_varying

    # 5) GDEF VarStore + 竖排度量
    assert "GDEF" in merged and merged["GDEF"].table.VarStore is not None
    assert "vmtx" in merged and "vhea" in merged

    # 6) name 表补全 + head.flags
    assert merged["name"].getDebugName(16), "缺少 nameID 16"
    assert merged["name"].getDebugName(25), "缺少 nameID 25"
    for inst in merged["fvar"].instances:
        assert inst.postscriptNameID not in (0xFFFF, None), \
            "命名实例缺少 PostScript 名"
    assert not (merged["head"].flags & 0x0800), "head.flags 未清 WOFF2 位"

    print("  test_merge_subsets_roundtrip: %d 分片 → %d 字形, %d 码位, PASSED"
          % (len(paths), len(merged.getGlyphOrder()), len(merged_cps)))


def test_merge_subsets_save_and_reload():
    """产物落盘: sfnt 魔数 + 重新载入后 cmap/布局引用无悬空"""
    paths = _subsets()
    if not paths:
        print("  test_merge_subsets_save_and_reload: SKIP (测试字体未就位)")
        return

    out_dir = tempfile.mkdtemp(prefix="fm_out_")
    out = os.path.join(out_dir, "merged.ttf")
    merged = merge_subsets(paths, out_path=out, tag="t", verbose=False)

    with open(out, "rb") as fh:
        magic = fh.read(4)
    assert magic in (b"\x00\x01\x00\x00", b"OTTO"), \
        "输出不是 sfnt: %r" % magic

    again = TTFont(out)
    order = set(again.getGlyphOrder())
    bad = [(cp, gn) for st in again["cmap"].tables
           if hasattr(st, "cmap") and st.cmap
           for cp, gn in st.cmap.items() if gn not in order]
    assert not bad, "cmap 悬空引用 %d 个: %s" % (len(bad), bad[:3])
    assert len(again.getGlyphOrder()) == len(merged.getGlyphOrder())
    print("  test_merge_subsets_save_and_reload: PASSED")


def test_merge_subsets_verify():
    """自检: 抽样逐字形比对 (轮廓/度量) 应零差异"""
    paths = _subsets()
    if not paths:
        print("  test_merge_subsets_verify: SKIP (测试字体未就位)")
        return

    merged = merge_subsets(paths, tag="t", verbose=False)
    report = verify_merge(paths, merged,
                          glyph_map=merged.subset_merger.glyph_map(),
                          axis_positions=[None], sample=250, verbose=False)
    assert report["ok"], "自检失败: %s" % report["failures"]
    assert report["checks"]["glyphs"]["compared"] > 0
    assert report["checks"]["codepoints"]["missing"] == 0
    print("  test_merge_subsets_verify: 比对 %d 字形, PASSED"
          % report["checks"]["glyphs"]["compared"])


def test_merge_subsets_cff2():
    """CFF2 分片并集: CharStrings/blend/vsindex/FDSelect/HVAR 全部保留。

    判据用 verify_merge 在 **多个轴位置** 逐字形比对 —— 非默认位置的轮廓
    完全依赖 CFF2 的 blend/vsindex, 能过就说明增量数据没丢。
    """
    src = os.path.join(_test_fonts_dir, _CFF2_VF)
    if not os.path.exists(src):
        print("  test_merge_subsets_cff2: SKIP (测试字体未就位)")
        return
    paths = cached_subsets(src, n=3)
    merged = merge_subsets(paths, tag="c", verbose=False)

    assert "CFF2" in merged and "glyf" not in merged, "输出不是 CFF2"
    assert is_variable(merged), "可变性丢失"
    src_font = TTFont(src)
    missing_cp = set(src_font.getBestCmap()) - set(merged.getBestCmap())
    assert not missing_cp, "码位缺失 %d 个" % len(missing_cp)

    # HVAR 的 DeltaSetIndexMap 必须覆盖全部字形 (fontTools preWrite 会 KeyError)
    assert "HVAR" in merged
    hmap = merged["HVAR"].table.AdvWidthMap.mapping
    assert all(gn in hmap for gn in merged.getGlyphOrder()), \
        "HVAR 映射不完整"

    # 落盘 + 重载 + 多轴位置自检
    out_dir = tempfile.mkdtemp(prefix="fm_cff2_")
    out = os.path.join(out_dir, "merged.otf")
    save_font(merged, out)
    with open(out, "rb") as fh:
        assert fh.read(4) == b"OTTO"
    again = TTFont(out)
    report = verify_merge(paths, again,
                          glyph_map=merged.subset_merger.glyph_map(),
                          sample=120, verbose=False)
    assert report["ok"], "自检失败: %s" % report["failures"]
    assert report["checks"]["glyphs"]["compared"] > 0
    print("  test_merge_subsets_cff2: %d 字形, 比对 %d, PASSED"
          % (len(merged.getGlyphOrder()),
             report["checks"]["glyphs"]["compared"]))


def test_merge_subsets_rejects_foreign():
    """异源字体不能走 merge_subsets"""
    paths = _subsets()
    st = _static()
    if not paths or not st:
        print("  test_merge_subsets_rejects_foreign: SKIP (测试字体未就位)")
        return
    try:
        merge_subsets([paths[0], st], tag="t", verbose=False)
    except ValueError as e:
        assert "同源" in str(e)
        print("  test_merge_subsets_rejects_foreign: PASSED")
        return
    raise AssertionError("异源输入应抛 ValueError")


def test_glyph_map_covers_sources():
    """glyph_map: 每个分片字形都能定位到合并后的 GID"""
    paths = _subsets()
    if not paths:
        print("  test_glyph_map_covers_sources: SKIP (测试字体未就位)")
        return
    merged = merge_subsets(paths, tag="t", verbose=False)
    gmap = merged.subset_merger.glyph_map()
    assert len(gmap) == len(paths)
    n_merged = len(merged.getGlyphOrder())
    for label, entry in gmap.items():
        assert entry, "分片 %s 的映射为空" % label
        for gn, gid in entry.items():
            assert 0 <= gid < n_merged, "GID 越界: %s → %s" % (gn, gid)
    print("  test_glyph_map_covers_sources: PASSED")


def test_subset_merge_preserves_mark_sets_and_fv():
    """GDEF MarkGlyphSetsDef 的 LookupFlag bit4 索引与 GSUB FeatureVariations
    的 FeatureIndex 在合并/重排后必须仍指向正确目标。"""
    rich, paths = cached_rich_subsets(_vf(), n=2)
    if not paths:
        print("  test_subset_merge_preserves_mark_sets_and_fv: SKIP (测试字体未就位)")
        return

    merged = merge_subsets(paths, tag="t", verbose=False)
    report = _check_layout_integrity(merged)
    assert not report["bad_mark_filters"],         "MarkFilteringSet 越界: %s" % report["bad_mark_filters"][:3]
    assert not report["bad_feature_variations"],         "FeatureVariations 索引无效: %s" % report["bad_feature_variations"][:3]

    src_fv = [p for p in paths
              if getattr(TTFont(p)["GSUB"].table, "FeatureVariations", None)
              is not None]
    merged_fv = getattr(merged["GSUB"].table, "FeatureVariations", None)
    assert merged_fv is not None, "分片带 FeatureVariations 却丢失了"
    assert len(merged_fv.FeatureVariationRecord) >= 1

    # 语义检查: 分片 mark 集合覆盖的字形 (经 glyph_map 映射) 必须落在合并后
    # 被引用集合的 Coverage 里
    gmap = merged.subset_merger.glyph_map()
    order = merged.getGlyphOrder()
    labels = [os.path.basename(p) for p in paths]
    mgs = merged["GDEF"].table.MarkGlyphSetsDef
    merged_sets = [set(c.glyphs) for c in mgs.Coverage]
    checked = 0
    for label, p in zip(labels, paths):
        sub = TTFont(p)
        sg = sub["GDEF"].table.MarkGlyphSetsDef if "GDEF" in sub else None
        if sg is None:
            continue
        for cov_dict in [None]:
            pass
        for cov in sg.Coverage:
            mapped = {order[gmap[label][g]] for g in cov.glyphs
                      if g in gmap.get(label, {})}
            if not mapped:
                continue
            assert any(mapped <= s for s in merged_sets),                 "分片 %s 的 mark 集合没有对应到合并后任一集合" % label
            checked += 1
    assert checked, "用例无效: 分片没有 mark 集合"

    # 落盘 + 重载后索引仍是二进制里的真实索引
    out_dir = tempfile.mkdtemp(prefix="fm_fv_")
    out = os.path.join(out_dir, "merged.ttf")
    save_font(merged, out)
    again = TTFont(out)
    rep2 = _check_layout_integrity(again)
    assert not rep2["bad_mark_filters"] and not rep2["bad_feature_variations"],         "重载后索引失效: %s %s" % (rep2["bad_mark_filters"],
                                  rep2["bad_feature_variations"])
    print("  test_subset_merge_preserves_mark_sets_and_fv: "
          "mark 集合 %d, FV 记录 %d, PASSED"
          % (len(merged_sets), len(merged_fv.FeatureVariationRecord)))


def main():
    print("FontMerger merge_subsets Test Suite")
    print("=" * 50)
    tests = [
        test_same_source_detection,
        test_merge_subsets_roundtrip,
        test_merge_subsets_save_and_reload,
        test_merge_subsets_verify,
        test_merge_subsets_rejects_foreign,
        test_glyph_map_covers_sources,
        test_subset_merge_preserves_mark_sets_and_fv,
        test_merge_subsets_cff2,
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
    sys.exit(0 if main() else 1)
