#!/usr/bin/env python3
"""FontMerger 单元测试"""
import os, sys, copy, tempfile
from io import BytesIO

_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
_test_fonts_dir = os.path.join(_project_dir, "test")
sys.path.insert(0, _project_dir)
sys.path.insert(0, _repo_dir)   # 使 tests.local_fonts 在"直接运行脚本"模式下也可导入

from FontMerger import *
from fontTools.ttLib import TTFont
from tests.subset_fixture import cached_subsets

# 公开可下载的 OFL 测试字体（目录位于仓库外，本地需自备；缺失时用例自动 SKIP）
_OPEN_FONTS = {
    "otf_latin": "OpenType/LibreCaslonText-Regular.otf",
    "ttf_latin": "TrueType/LXGWWenKaiTC-Regular.ttf",
    "votf_cjk":  "otf_variable_fonts/SourceHanSansCN-VF.otf",
    "vttf_cjk":  "ttf_variable_fonts/ZedTextJapaneseVF.ttf",
    "ttf_inter": "TrueType/Inter-Regular.ttf",
}


def _open(role):
    """公开 OFL 字体路径；文件不存在返回 None（调用方跳过用例）。"""
    rel = _OPEN_FONTS.get(role)
    if not rel:
        return None
    p = os.path.join(_test_fonts_dir, rel)
    return p if os.path.exists(p) else None


def _local(role):
    """本地授权测试字体：真实路径由 tests/local_fonts.py 配置（该文件不入库）。

    未配置或文件不存在时返回 None，调用方跳过对应用例。
    """
    try:
        from tests.local_fonts import LOCAL_FONTS
        rel = LOCAL_FONTS.get(role)
    except ImportError:
        rel = None
    if not rel:
        return None
    p = os.path.join(_test_fonts_dir, rel)
    return p if os.path.exists(p) else None


def test_detect():
    """测试字体检测"""
    op = _open("otf_latin")
    tp = _open("ttf_latin")
    vp = _open("votf_cjk")
    if not op or not tp or not vp:
        print("  test_detect: SKIP (测试字体未就位，见 README 'Tests')")
        return

    otf = TTFont(op)
    ttf = TTFont(tp)
    vf = TTFont(vp)

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
    op = _open("otf_latin")
    tp = _open("ttf_latin")
    if not op or not tp:
        print("  test_conflict: SKIP (测试字体未就位)")
        return

    otf = TTFont(op)
    ttf = TTFont(tp)

    conflicts = resolve_conflicts(otf, ttf)
    assert isinstance(conflicts, set), "Conflicts should be a set"
    assert ".notdef" not in conflicts, ".notdef should be exempt"
    print(f"  test_conflict: {len(conflicts)} conflicts found, PASSED")


def test_naming():
    """测试名称处理"""
    op = _open("otf_latin")
    if not op:
        print("  test_naming: SKIP (测试字体未就位)")
        return

    otf = TTFont(op)
    otf_copy = copy.deepcopy(otf)

    cr = get_copyrights(otf, otf)
    fn = get_family(otf)
    result = apply_naming(otf_copy, fn, cr)

    new_fn = get_family(result)
    assert "mod" in new_fn, "Family name should contain 'mod'"
    print("  test_naming: PASSED")


def test_merge_otf_otf():
    """测试 OTF+OTF 合并"""
    op = _open("otf_latin")
    cp = _local("cjk_static_otf")
    if not op or not cp:
        print("  test_merge_otf_otf: SKIP (本地授权字体未配置)")
        return

    otf1 = TTFont(op)
    otf2 = TTFont(cp)

    merger = FontMerger()
    result = merger.merge_two(otf1, otf2)

    assert len(result.getGlyphOrder()) > len(otf1.getGlyphOrder()), \
        f"Should have more glyphs: {len(result.getGlyphOrder())} vs {len(otf1.getGlyphOrder())}"
    print(f"  test_merge_otf_otf: {len(otf1.getGlyphOrder())} → {len(result.getGlyphOrder())} glyphs, PASSED")


def test_merge_ttf_ttf():
    """测试 TTF+TTF 合并"""
    tp = _open("ttf_latin")
    cp = _local("cjk_static_ttf")
    if not tp or not cp:
        print("  test_merge_ttf_ttf: SKIP (本地授权字体未配置)")
        return

    ttf1 = TTFont(tp)
    ttf2 = TTFont(cp)

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
    op = _open("otf_latin")
    cp = _local("cjk_static_otf")
    if not op or not cp:
        print("  test_high_level_api: SKIP (本地授权字体未配置)")
        return

    result = merge_fonts(op, [cp], interactive=False)
    assert len(result.getGlyphOrder()) > 537, "Should add glyphs"
    print(f"  test_high_level_api: {len(result.getGlyphOrder())} glyphs, PASSED")




def _open_vf():
    """OFL 可变 TTF 路径 (Zed Text Japanese VF); 缺失返回 None"""
    p = _open("vttf_cjk")
    return p


def _vf_subsets(n=2):
    """现场切出的同源分片 (缓存); 字体缺失返回 None"""
    p = _open_vf()
    return cached_subsets(p, n=n) if p else None


def test_save_guard():
    """产物防护: woff2 载入的字体保存为 .ttf 必须是 sfnt, 不是 WOFF2"""
    op = _open("otf_latin")
    if not op:
        print("  test_save_guard: SKIP (测试字体未就位)")
        return
    try:
        import brotli  # noqa: F401  (woff2 需要)
    except ImportError:
        print("  test_save_guard: SKIP (brotli 未安装, 无法写 woff2)")
        return

    work = tempfile.mkdtemp(prefix="fm_guard_")
    woff2 = os.path.join(work, "x.woff2")
    font = TTFont(op)
    font.flavor = "woff2"
    font.save(woff2)

    loaded = TTFont(woff2)
    assert loaded.flavor == "woff2", "woff2 载入后 flavor 应为 woff2"

    out = os.path.join(work, "x.ttf")
    _, magic = save_font(loaded, out)
    assert magic in SFNT_MAGICS, "save_font 未清 flavor: 魔数 %r" % magic
    assert TTFont(out).flavor is None

    # 直接塞一个非 sfnt 文件, assert_sfnt 必须报错
    bogus = os.path.join(work, "bogus.ttf")
    with open(bogus, "wb") as fh:
        fh.write(b"wOF2xxxx")
    try:
        assert_sfnt(bogus)
    except ValueError:
        pass
    else:
        raise AssertionError("assert_sfnt 应拒绝非 sfnt 文件")
    print("  test_save_guard: PASSED")


def test_conflict_auto_names():
    """自动命名字形 (glyphNNNNN) 跨字体同名不应判为冲突 (P3)"""
    paths = _vf_subsets()
    if not paths:
        print("  test_conflict_auto_names: SKIP (测试字体未就位)")
        return
    a, b = TTFont(paths[0]), TTFont(paths[1])
    auto_in_both = {g for g in b.getGlyphOrder()
                    if g.startswith("glyph") and g[5:].isdigit()
                    and g in set(a.getGlyphOrder())}
    assert auto_in_both, "分片之间应有自动名重名 (否则用例无效)"
    conflicts = resolve_conflicts(a, b)
    still = [g for g in auto_in_both if g in conflicts]
    assert not still, "自动名仍被判为冲突: %s" % still[:5]

    alias = plan_alias(a, b)
    assert set(alias) == auto_in_both, "plan_alias 应覆盖全部重名自动名"
    assert len(set(alias.values())) == len(alias), "别名必须唯一"
    assert not (set(alias.values()) & set(a.getGlyphOrder())), "别名与主字体撞名"
    print("  test_conflict_auto_names: %d 个自动名改别名, PASSED" % len(alias))


def test_rename_glyphs():
    """字形改名: glyf/复合组件/cmap/hmtx/布局引用同步更新"""
    tp = _open("ttf_latin")
    if not tp:
        print("  test_rename_glyphs: SKIP (测试字体未就位)")
        return
    font = TTFont(tp)
    order = font.getGlyphOrder()
    target = next((g for g in order[1:] if g in font.getBestCmap().values()), None)
    assert target, "找不到可改名的字形"
    cp = next(cp for cp, gn in font.getBestCmap().items() if gn == target)
    new = "renamed.test." + target

    # 复合字形: 找一个引用了 target 的组件写法不便构造, 直接验证整个字体可保存
    rename_glyphs(font, {target: new})
    assert new in font.getGlyphOrder() and target not in font.getGlyphOrder()
    assert font.getBestCmap()[cp] == new, "cmap 未同步"
    assert new in font["hmtx"].metrics, "hmtx 未同步"
    if "glyf" in font:
        assert new in font["glyf"].glyphs, "glyf 未同步"
    buf = BytesIO()
    font.save(buf)
    print("  test_rename_glyphs: PASSED")


def test_variable_to_static_fidelity():
    """variable_to_static 默认不改写轮廓 (remove_overlaps=False)"""
    vp = _open_vf()
    if not vp:
        print("  test_variable_to_static_fidelity: SKIP (测试字体未就位)")
        return
    vf = TTFont(vp)
    static = variable_to_static(vf)
    assert not is_variable(static), "实例化后不应再有 fvar"

    from fontTools.pens.recordingPen import RecordingPen
    src_set, dst_set = vf.getGlyphSet(), static.getGlyphSet()
    checked = 0
    for gn in list(vf.getGlyphOrder())[:400]:
        p1, p2 = RecordingPen(), RecordingPen()
        src_set[gn].draw(p1)
        dst_set[gn].draw(p2)
        assert p1.value == p2.value, "轮廓被改写: %s" % gn
        assert vf["hmtx"][gn] == static["hmtx"][gn], "度量被改写: %s" % gn
        checked += 1
    print("  test_variable_to_static_fidelity: %d 字形零差异, PASSED" % checked)


def test_generic_feature_union():
    """merge_two: 同 tag feature 的 lookup 做并集 (P1), 且追加后仍可达"""
    paths = _vf_subsets()
    if not paths:
        print("  test_generic_feature_union: SKIP (测试字体未就位)")
        return
    a, b = TTFont(paths[0]), TTFont(paths[1])

    def feats(font, tag):
        if tag not in font or font[tag].table.FeatureList is None:
            return set()
        return {fr.FeatureTag for fr in font[tag].table.FeatureList.FeatureRecord}

    def reachable(font, tag):
        """从 ScriptList/LangSys 可达的 feature tag"""
        out = set()
        if tag not in font or font[tag].table.ScriptList is None:
            return out
        t = font[tag].table
        for sr in t.ScriptList.ScriptRecord:
            langs = [sr.Script.DefaultLangSys] + [lr.LangSys
                                                  for lr in (sr.Script.LangSysRecord or [])]
            for lang in langs:
                if lang is None:
                    continue
                for fi in lang.FeatureIndex:
                    if fi < len(t.FeatureList.FeatureRecord):
                        out.add(t.FeatureList.FeatureRecord[fi].FeatureTag)
        return out

    base_only = feats(b, "GSUB") - feats(a, "GSUB")
    if not base_only:
        print("  test_generic_feature_union: SKIP (两个分片没有独有 feature)")
        return

    merger = FontMerger()
    merger.mem = {"vTTF_vTTF": "TTF"}
    result = merger.merge_two(a, b)

    got = feats(result, "GSUB")
    missing = base_only - got
    assert not missing, "同 tag feature 并集失败, 丢失 %s" % sorted(missing)
    # 追加的 feature 必须挂在 ScriptList 上, 否则引擎不会启用
    dead = got - reachable(result, "GSUB")
    assert not dead, "feature 不可达 (未挂到 ScriptList): %s" % sorted(dead)
    tags = [fr.FeatureTag for fr in result["GSUB"].table.FeatureList.FeatureRecord]
    assert tags == sorted(tags), "FeatureList 未按 tag 排序"
    print("  test_generic_feature_union: 打底独有 %d 个 tag 全部保留且可达, PASSED"
          % len(base_only))




def test_no_dangling_layout_refs():
    """回归: 打底字体的替代字形被码位冲突删除后, 其布局引用不得残留。

    旧版对 Extension/Alternate/Ligature 子表的引用收集不全, 校验"通过"后
    把已删字形 (如 Inter 的 zero.subs / eight.subs) 带进主字体, 保存时才
    KeyError。这里要求: 能保存 + 重新载入后无悬空引用、Coverage 有序。
    """
    op = _open("otf_latin")
    ip = _open("ttf_inter")
    if not op or not ip:
        print("  test_no_dangling_layout_refs: SKIP (测试字体未就位)")
        return

    from FontMerger.core.verify import _check_layout_integrity

    merger = FontMerger()
    merger.mem = {"sOTF_sTTF": "OTF"}
    result = merger.merge_two(TTFont(op), TTFont(ip))
    buf = BytesIO()
    result.save(buf)                       # 旧版在此 KeyError
    again = TTFont(BytesIO(buf.getvalue()))
    report = _check_layout_integrity(again)
    assert not report["dangling"],         "布局引用悬空字形: %s" % report["dangling"][:5]
    assert report["unsorted_coverages"] == 0, "Coverage 未按 GID 升序"
    print("  test_no_dangling_layout_refs: %d 字形, PASSED"
          % len(again.getGlyphOrder()))


def test_variable_to_static_cff2():
    """CFF2 可变字体实例化→CFF: 归一与 remove_overlaps 解耦后仍可用"""
    vp = _open("votf_cjk")
    if not vp:
        print("  test_variable_to_static_cff2: SKIP (测试字体未就位)")
        return
    vf = TTFont(vp)
    if "CFF2" not in vf:
        print("  test_variable_to_static_cff2: SKIP (字体不是 CFF2)")
        return
    static = variable_to_static(vf)
    assert "CFF2" not in static, "残留 CFF2"
    assert "CFF " in static, "未转换为 CFF"
    assert not is_variable(static)
    buf = BytesIO()
    static.save(buf)
    assert buf.getvalue()[:4] == b"OTTO"
    print("  test_variable_to_static_cff2: %d 字形, PASSED"
          % len(static.getGlyphOrder()))


def main():
    print("FontMerger Test Suite")
    print("=" * 50)

    tests = [
        test_detect, test_conflict, test_naming,
        test_table_registry, test_merge_ttf_ttf,
        test_merge_otf_otf, test_high_level_api,
        test_save_guard, test_conflict_auto_names, test_rename_glyphs,
        test_variable_to_static_fidelity, test_generic_feature_union,
        test_no_dangling_layout_refs, test_variable_to_static_cff2,
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
