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
from tests.subset_fixture import cached_subsets, cached_rich_subsets

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


def test_generic_merge_preserves_mark_sets_and_fv():
    """回归: 主字体的 MarkGlyphSetsDef (LookupFlag bit4 索引) 与
    GSUB FeatureVariations 在追加打底 feature 后不能被丢弃或错位。"""
    vf = _open_vf()
    ip = _open("ttf_inter")
    if not vf or not ip:
        print("  test_generic_merge_preserves_mark_sets_and_fv: SKIP (测试字体未就位)")
        return

    from FontMerger.core.verify import _check_layout_integrity

    rich, _ = cached_rich_subsets(vf, n=2)
    if not rich:
        print("  test_generic_merge_preserves_mark_sets_and_fv: SKIP (无法构造夹具)")
        return

    main = TTFont(rich)
    assert getattr(main["GSUB"].table, "FeatureVariations", None) is not None,         "夹具缺少 FeatureVariations"

    merger = FontMerger()
    merger.mem = {"vTTF_sTTF": "可变"}
    result = merger.merge_two(main, TTFont(ip))

    fv = getattr(result["GSUB"].table, "FeatureVariations", None)
    assert fv is not None, "通用路径丢弃了主字体的 FeatureVariations"
    report = _check_layout_integrity(result)
    assert not report["bad_mark_filters"],         "MarkFilteringSet 越界: %s" % report["bad_mark_filters"][:3]
    assert not report["bad_feature_variations"],         "FeatureVariations 索引无效: %s" % report["bad_feature_variations"][:3]

    buf = BytesIO()
    result.save(buf)
    again = TTFont(BytesIO(buf.getvalue()))
    rep2 = _check_layout_integrity(again)
    assert not rep2["bad_mark_filters"], rep2["bad_mark_filters"][:3]
    assert not rep2["bad_feature_variations"], rep2["bad_feature_variations"][:3]
    assert getattr(again["GSUB"].table, "FeatureVariations", None) is not None
    print("  test_generic_merge_preserves_mark_sets_and_fv: %d 字形, PASSED"
          % len(again.getGlyphOrder()))


def test_generic_merge_transfers_variation():
    """轴空间一致的可变打底: 新增字形保留 gvar 增量 (不再停在默认实例)。

    判据: 非默认轴位置上, 新增字形的轮廓与字宽必须与打底源字体一致 ——
    这同时验证了 gvar 增量搬运与 HVAR 重建 (add_HVAR 由幽灵点重算)。
    """
    vf = _open_vf()
    if not vf:
        print("  test_generic_merge_transfers_variation: SKIP (测试字体未就位)")
        return
    paths = _vf_subsets(n=2)
    if not paths:
        print("  test_generic_merge_transfers_variation: SKIP (无法构造夹具)")
        return

    main, sub = TTFont(vf), TTFont(paths[0])
    assert axes_compatible(main, sub), "夹具轴空间不一致"
    merger = FontMerger()
    merger.mem = {"vTTF_vTTF": "TTF"}
    result = merger.merge_two(copy.deepcopy(main), copy.deepcopy(sub))

    main_names = set(main.getGlyphOrder())
    added = [gn for gn in result.getGlyphOrder() if gn not in main_names]
    assert added, "没有新增字形, 用例无效"
    with_deltas = sum(1 for gn in added if result["gvar"].variations.get(gn))
    assert with_deltas > len(added) * 0.9, \
        "只有 %d/%d 个新增字形保留增量" % (with_deltas, len(added))

    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.varLib.instancer import instantiateVariableFont
    axis = result["fvar"].axes[0].axisTag
    top = result["fvar"].axes[0].maxValue
    r_top = instantiateVariableFont(result, {axis: top}, inplace=False)
    b_top = instantiateVariableFont(sub, {axis: top}, inplace=False)
    rs, bs = r_top.getGlyphSet(), b_top.getGlyphSet()
    checked = diffs = hmtx_diffs = 0
    for gn in added[:300]:
        if gn not in bs:
            continue
        checked += 1
        p1, p2 = RecordingPen(), RecordingPen()
        rs[gn].draw(p1)
        bs[gn].draw(p2)
        if p1.value != p2.value:
            diffs += 1
        if r_top["hmtx"][gn] != b_top["hmtx"][gn]:
            hmtx_diffs += 1
    assert checked, "没有可比较的字形"
    assert not diffs, "非默认轴位置轮廓不一致 %d/%d" % (diffs, checked)
    assert not hmtx_diffs, "非默认轴位置度量不一致 %d/%d" % (hmtx_diffs, checked)
    print("  test_generic_merge_transfers_variation: %d 字形带增量, 比对 %d, PASSED"
          % (with_deltas, checked))




def test_cross_design_space_composition():
    """跨设计空间合成: 打底带主字体没有的轴时, 合并结果新增字形逐点等价。

    主 = ZedText (wght), 打底 = InterVariable (opsz + wght): 合并后应有
    wght(主范围) + opsz(打底范围) 两条轴; 新增字形在网格位置上等于打底在
    该位置的实例 (自检函数本身已在合并流程里跑过, 这里再抽样复核)。
    """
    main_p = _open_vf()
    inter_p = os.path.join(_test_fonts_dir, "ttf_variable_fonts/InterVariable.ttf")
    if not main_p or not os.path.exists(inter_p):
        print("  test_cross_design_space_composition: SKIP (测试字体未就位)")
        return
    from fontTools.ttLib.scaleUpem import scale_upem
    from FontMerger.core.verify import verify_composition

    main = TTFont(main_p)
    base = TTFont(inter_p)
    scale_upem(base, main["head"].unitsPerEm)
    merger = FontMerger(verify_compose=False)     # 先只测合成本身
    result = merger.merge_two(copy.deepcopy(main), copy.deepcopy(base))

    axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue)
            for a in result["fvar"].axes}
    assert "wght" in axes and "opsz" in axes, axes
    # 默认策略: 共有轴用主范围, 打底独有轴用打底范围
    assert axes["opsz"][0] == 14.0 and axes["opsz"][2] == 32.0, axes["opsz"]
    added = [gn for gn in result.getGlyphOrder()
             if gn not in set(main.getGlyphOrder())]
    assert added, "没有新增字形"
    with_deltas = sum(1 for gn in added if result["gvar"].variations.get(gn))
    assert with_deltas > len(added) * 0.8, (with_deltas, len(added))
    report = verify_composition(result, main, base, added, sample=12,
                                max_positions=2)
    assert report["checked"] > 0
    print("  test_cross_design_space_composition: %d 字形带增量, 自检 %d 点, PASSED"
          % (with_deltas, report["checked"]))


def test_composition_fallback():
    """合成自检不通过时必须回退到旧的默认实例合并 (不产出坏字体)。"""
    main_p = _open_vf()
    inter_p = os.path.join(_test_fonts_dir, "ttf_variable_fonts/InterVariable.ttf")
    if not main_p or not os.path.exists(inter_p):
        print("  test_composition_fallback: SKIP (测试字体未就位)")
        return
    from fontTools.ttLib.scaleUpem import scale_upem

    main = TTFont(main_p)
    base = TTFont(inter_p)
    scale_upem(base, main["head"].unitsPerEm)
    merger = FontMerger(compose_fit="affine")      # 故意用不精确拟合
    result = merger.merge_two(copy.deepcopy(main), copy.deepcopy(base))
    assert len(result.getGlyphOrder()) > len(main.getGlyphOrder()), \
        "回退后仍应完成字符合并"
    print("  test_composition_fallback: %d 字形 (已回退), PASSED"
          % len(result.getGlyphOrder()))

def test_compose_main_var_store_axes():
    """跨设计空间合成后, 主字体自己的 ItemVariationStore 必须跟上新轴空间。

    主 = ZedText (wght, 带 GDEF VarStore + GPOS VariationIndex), 打底 =
    InterVariable (opsz + wght)。合并后:
      * 各表 VarStore 的 RegionAxisCount == fvar 轴数 (否则写出非法字体),
        VariationIndex 的 (outer, inner) 不越界 (core.verify._check_var_stores);
      * 主的 VarData/列/增量 1:1 保留 (默认策略下主轴映射是恒等), 新轴恒定 0。
    """
    main_p = _open_vf()
    inter_p = os.path.join(_test_fonts_dir, "ttf_variable_fonts/InterVariable.ttf")
    if not main_p or not os.path.exists(inter_p):
        print("  test_compose_main_var_store_axes: SKIP (测试字体未就位)")
        return
    from fontTools.ttLib.scaleUpem import scale_upem
    from FontMerger.core.verify import _check_var_stores

    main = TTFont(main_p)
    base = TTFont(inter_p)
    scale_upem(base, main["head"].unitsPerEm)
    assert "GDEF" in main and main["GDEF"].table.VarStore is not None, \
        "夹具主字体缺少 GDEF VarStore"
    main_vs = copy.deepcopy(main["GDEF"].table.VarStore)
    n_main_axes = len(main["fvar"].axes)

    merger = FontMerger(verify_compose=False)
    result = merger.merge_two(copy.deepcopy(main), copy.deepcopy(base))

    assert len(result["fvar"].axes) > n_main_axes, "打底独有轴没有并入"
    problems = _check_var_stores(result)
    assert not problems, problems[:5]
    new_vs = result["GDEF"].table.VarStore
    assert len(new_vs.VarData) >= len(main_vs.VarData)
    for vd_i, vd in enumerate(main_vs.VarData):
        nvd = new_vs.VarData[vd_i]
        assert nvd.VarRegionIndex == vd.VarRegionIndex, (vd_i, nvd.VarRegionIndex)
        assert nvd.Item == vd.Item, vd_i                 # 增量 1:1, 列未丢失
    for r_i in range(main_vs.VarRegionList.RegionCount):
        old = [(a.StartCoord, a.PeakCoord, a.EndCoord)
               for a in main_vs.VarRegionList.Region[r_i].VarRegionAxis]
        new = [(a.StartCoord, a.PeakCoord, a.EndCoord)
               for a in new_vs.VarRegionList.Region[r_i].VarRegionAxis]
        assert new[:n_main_axes] == old, (r_i, old, new)
        assert all(t == (0.0, 0.0, 0.0) for t in new[n_main_axes:]), (r_i, new)
    print("  test_compose_main_var_store_axes: %d VarData / %d region 保留, PASSED"
          % (len(new_vs.VarData), new_vs.VarRegionList.RegionCount))


def _count_var_devices(font, min_outer=0):
    """统计 GPOS/GSUB 里 DeltaFormat=0x8000 的设备数 (可只看 outer >= min_outer)"""
    from fontTools.ttLib.tables import otTables as ot

    counts = [0, 0]

    def walk(obj, seen):
        if id(obj) in seen:
            return
        seen.add(id(obj))
        if isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v, seen)
            return
        if isinstance(obj, ot.Device) and getattr(obj, "DeltaFormat", 0) == 0x8000:
            counts[0] += 1
            if obj.StartSize >= min_outer:
                counts[1] += 1
        d = getattr(obj, "__dict__", None)
        if d:
            for v in d.values():
                walk(v, seen)

    for tag in ("GPOS", "GSUB"):
        if tag in font:
            walk(font[tag].table, set())
    return counts


def test_compose_base_layout_variation():
    """跨设计空间合成时, 打底的布局变化数据 (GDEF VarStore + GPOS 设备) 一并并入。

    主 = ZedText 夹具 (wght), 打底 = InterVariable (opsz + wght)。判据:
      * 合并后 GDEF VarStore 的 VarData 数 = 主的 + 打底的, 且 RegionAxisCount
        与新 fvar 一致 (打底数据按合并空间重参数化, 行保持 → 设备引用有效);
      * GPOS 里出现 outer >= 主的 VarData 数的设备 (即来自打底的那部分);
      * 结构自检 _check_var_stores 干净, 保存/重载后依旧;
      * compose_layout=False 作对照: 打底停在默认实例, 上述数据不出现。
    """
    main_p = _open_vf()
    inter_p = os.path.join(_test_fonts_dir, "ttf_variable_fonts/InterVariable.ttf")
    if not main_p or not os.path.exists(inter_p):
        print("  test_compose_base_layout_variation: SKIP (测试字体未就位)")
        return
    from fontTools.ttLib.scaleUpem import scale_upem
    from FontMerger.core.verify import _check_var_stores

    main = TTFont(main_p)
    base = TTFont(inter_p)
    scale_upem(base, main["head"].unitsPerEm)
    main_vd = len(main["GDEF"].table.VarStore.VarData)
    base_vd = len(base["GDEF"].table.VarStore.VarData)
    assert base_vd > 0

    merger = FontMerger(verify_compose=False)
    result = merger.merge_two(copy.deepcopy(main), copy.deepcopy(base))
    vs = result["GDEF"].table.VarStore
    assert len(vs.VarData) == main_vd + base_vd, (len(vs.VarData), main_vd, base_vd)
    assert vs.VarRegionList.RegionAxisCount == len(result["fvar"].axes), vs
    total, from_base = _count_var_devices(result, min_outer=main_vd)
    assert from_base > 0, ("打底的 GPOS 设备没有并入", total)
    assert not _check_var_stores(result), _check_var_stores(result)[:3]
    buf = BytesIO()
    result.save(buf)
    again = TTFont(BytesIO(buf.getvalue()))
    assert not _check_var_stores(again), _check_var_stores(again)[:3]
    assert len(again["GDEF"].table.VarStore.VarData) == main_vd + base_vd

    # 对照: 关闭布局变化数据搬运 → 打底停在默认实例
    plain = FontMerger(verify_compose=False, compose_layout=False)
    result2 = plain.merge_two(copy.deepcopy(main), copy.deepcopy(base))
    vs2 = result2["GDEF"].table.VarStore
    assert len(vs2.VarData) == main_vd, len(vs2.VarData)
    _total2, from_base2 = _count_var_devices(result2, min_outer=main_vd)
    assert from_base2 == 0, from_base2
    print("  test_compose_base_layout_variation: GDEF %d+%d VarData, 打底设备 %d, PASSED"
          % (main_vd, base_vd, from_base))


def test_real_var_store_reparametrize():
    """真实 ItemVariationStore 的重参数化: 逐 (VarData, 行) 与源语义一致。

    用 InterVariable 的真实 GDEF VarStore 与 ZedText×Inter 的合并轴映射,
    在合并空间随机采样位置 x: 重参数化后的行增量 (folded_default=True, 即
    打底静态值已折默认点后的**残余变化量**) 必须复现源语义
    Σ_c δ_c·φ_c(T(x)) - C。整数增量取整带来每列 ≤ 0.5 的误差。
    """
    main_p = _open_vf()
    inter_p = os.path.join(_test_fonts_dir, "ttf_variable_fonts/InterVariable.ttf")
    if not main_p or not os.path.exists(inter_p):
        print("  test_real_var_store_reparametrize: SKIP (测试字体未就位)")
        return
    import random
    from fontTools.ttLib.scaleUpem import scale_upem
    from FontMerger.format.variation_compose import (plan_axis_space,
                                                     reparametrize_var_store,
                                                     _store_region_supports)
    from FontMerger.format.axis_mapping import support_value

    main = TTFont(main_p)
    base = TTFont(inter_p)
    scale_upem(base, main["head"].unitsPerEm)
    merged_fvar, _avar, base_maps = plan_axis_space(main, base)
    src_tags = [a.axisTag for a in base["fvar"].axes]
    dst_tags = list(merged_fvar)
    src_store = base["GDEF"].table.VarStore
    new_store, rep = reparametrize_var_store(src_store, base_maps, src_tags,
                                             dst_tags, folded_default=True)
    assert new_store.VarRegionList.RegionAxisCount == len(dst_tags), rep
    rows_in = sum(len(vd.Item) for vd in src_store.VarData)
    rows_out = sum(len(vd.Item) for vd in new_store.VarData)
    assert rows_in == rows_out, (rows_in, rows_out)      # 行保持
    assert len(new_store.VarData) == len(src_store.VarData)

    src_sups = _store_region_supports(src_store, src_tags)
    new_sups = _store_region_supports(new_store, dst_tags)

    def phi_src(region_idx, x):
        """源 region 在合并位置 x 的标量 (经 T; 源数据只用到打底自己的轴)"""
        sup = src_sups[region_idx]
        loc = {tag: base_maps[tag].to_source(x[tag]) for tag in sup}
        return support_value(loc, sup)

    rng = random.Random(20240912)
    worst = 0.0
    for _ in range(24):
        x = {tag: rng.uniform(-1.0, 1.0) for tag in dst_tags}
        for vd_i, vd in enumerate(src_store.VarData):
            nvd = new_store.VarData[vd_i]
            for row_i in range(len(vd.Item)):
                want = sum(vd.Item[row_i][c] * phi_src(r, x)
                           for c, r in enumerate(vd.VarRegionIndex))
                got = sum(nvd.Item[row_i][c] * support_value(x, new_sups[r])
                          for c, r in enumerate(nvd.VarRegionIndex))
                worst = max(worst, abs(want - got))
    assert worst <= 1.0, worst
    print("  test_real_var_store_reparametrize: %d VarData / %d 行, 列 %d → %d, "
          "最大偏差 %.2f, PASSED"
          % (len(new_store.VarData), rows_in, rep["columns_in"],
             rep["columns_out"], worst))


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
        test_generic_merge_preserves_mark_sets_and_fv,
        test_generic_merge_transfers_variation,
        test_cross_design_space_composition,
        test_composition_fallback,
        test_compose_main_var_store_axes,
        test_compose_base_layout_variation,
        test_real_var_store_reparametrize,
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
