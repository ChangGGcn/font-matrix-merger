#!/usr/bin/env python3
"""轴空间映射与 hat 重参数化的数学自检 (阶段 0, 不依赖字体文件)

判据: 细化 (refine) 后的 hat 之和必须在**任意**采样点逐点复现
      原 hat ∘ T (T = 源空间 → 合并空间的坐标变换), 误差 < 1e-9。
"""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
_test_fonts_dir = os.path.join(_project_dir, "test")
sys.path.insert(0, _project_dir)
sys.path.insert(0, _repo_dir)

from FontMerger.format.axis_mapping import (AxisMapping, PiecewiseLinear,
                                            axis_mappings, evaluate_supports,
                                            fvar_triples, hat_value, refine_1d,
                                            refine_support,
                                            refine_support_rebased,
                                            source_location, support_value)


def _sample(lo=-1.0, hi=1.0, n=2001):
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def _max_err_1d(lower, peak, upper, mapping, terms):
    """逐点误差 —— 用**引擎语义** (supportScalar) 求和: 跨 0 的 hat 会被整条
    忽略, 所以理想 hat 相加会漏掉这类错误 (见 test_refine_cross_zero)。"""
    ot_terms = [({"wght": (l, p, u)}, w) for l, p, u, w in terms]
    worst = 0.0
    for x in _sample():
        want = hat_value(source_location(mapping, x), lower, peak, upper)
        got = evaluate_supports({"wght": x}, ot_terms)
        worst = max(worst, abs(want - got))
    return worst


def test_piecewise_linear_basics():
    """fvar 反归一化 / avar / 复合 / 逆 的基本语义"""
    pl = PiecewiseLinear.fvar((100, 400, 900))
    assert abs(pl.map(0.0) - 400) < 1e-9
    assert abs(pl.map(-1.0) - 100) < 1e-9
    assert abs(pl.map(1.0) - 900) < 1e-9
    assert abs(pl.map(0.5) - 650) < 1e-9

    # user -> norm 与 fontTools 的 normalizeValue 一致 (双段线性)
    inv = pl.inverse()
    assert abs(inv.map(400) - 0.0) < 1e-9
    assert abs(inv.map(650) - 0.5) < 1e-9
    assert abs(inv.map(100) - (-1.0)) < 1e-9

    avar = PiecewiseLinear.avar({-1.0: -1.0, 0.0: 0.0, 0.5: 0.25, 1.0: 1.0})
    assert abs(avar.map(0.5) - 0.25) < 1e-9
    assert abs(avar.inverse().map(0.25) - 0.5) < 1e-9

    comp = avar.compose(pl.inverse())      # user -> norm
    assert abs(comp.map(650) - 0.25) < 1e-9
    assert PiecewiseLinear.identity().is_identity()
    print("  test_piecewise_linear_basics: PASSED")


def test_refine_identity():
    """恒等映射: 细化应退化为原 hat (单条, 权重 1)"""
    m = AxisMapping((100, 400, 900), None, (100, 400, 900), None)
    assert m.is_identity()
    terms = refine_1d(0.2, 0.6, 1.0, m)
    assert len(terms) == 1, terms
    l, p, u, w = terms[0]
    assert abs(w - 1.0) < 1e-9
    assert (abs(l - 0.2), abs(p - 0.6), abs(u - 1.0)) == (0.0, 0.0, 0.0)
    assert _max_err_1d(0.2, 0.6, 1.0, m, terms) < 1e-9
    print("  test_refine_identity: PASSED")


def test_refine_affine_range():
    """范围不同 (无 avar): 重参数化仍逐点精确"""
    m = AxisMapping((50, 400, 1000), None, (100, 400, 900), None)
    # OT 只允许落在 0 一侧的支撑 (跨 0 的 tuple 会被引擎忽略, 属非法输入)
    cases = [(-1.0, -0.5, 0.0), (0.0, 0.5, 1.0), (-1.0, -1.0, 0.0),
             (0.0, 1.0, 1.0), (-1.0, -0.2, 0.0)]
    for lower, peak, upper in cases:
        if lower == peak == upper:
            continue
        terms = refine_1d(lower, peak, upper, m)
        err = _max_err_1d(lower, peak, upper, m, terms)
        assert err < 1e-9, (lower, peak, upper, err, terms)
    print("  test_refine_affine_range: PASSED")


def test_refine_avar():
    """两边 avar 都非平凡: 断点需纳入节点, 细化后仍逐点精确"""
    merged_avar = {-1.0: -1.0, 0.0: 0.0, 0.5: 0.25, 1.0: 1.0}
    src_avar = {-1.0: -1.0, 0.0: 0.0, 0.25: 0.4, 0.6: 0.7, 1.0: 1.0}
    m = AxisMapping((100, 400, 900), merged_avar, (100, 400, 900), src_avar)
    assert not m.is_identity()
    cases = [(0.0, 0.5, 1.0), (-1.0, -0.5, 0.0), (0.0, 0.25, 1.0),
             (0.0, 0.7, 1.0), (-0.6, -0.3, 0.0)]
    for lower, peak, upper in cases:
        terms = refine_1d(lower, peak, upper, m)
        err = _max_err_1d(lower, peak, upper, m, terms)
        assert err < 1e-9, (lower, peak, upper, err, terms)
    print("  test_refine_avar: 最多拆 %d 条/支撑, PASSED"
          % max(len(refine_1d(*c, m)) for c in cases))


def test_refine_range_and_avar():
    """范围 + avar 同时不同 (真实场景的主要形态)"""
    merged_avar = {-1.0: -1.0, 0.0: 0.0, 0.20001220703125: 0.17999267578125,
                   0.4000244140625: 0.3599853515625, 1.0: 1.0}
    src_avar = {-1.0: -1.0, 0.0: 0.0, 0.25: 0.4, 1.0: 1.0}
    m = AxisMapping((100, 400, 900), merged_avar, (1, 400, 900), src_avar)
    ok = 0
    for lower, peak, upper in [(0.0, 0.3, 1.0), (0.0, 0.5, 1.0),
                               (-1.0, -0.5, 0.0), (-1.0, -0.14, 0.0)]:
        terms = refine_1d(lower, peak, upper, m)
        err = _max_err_1d(lower, peak, upper, m, terms)
        assert err < 1e-9, (lower, peak, upper, err)
        ok += 1
    print("  test_refine_range_and_avar: %d 组, PASSED" % ok)


def test_refine_default_mismatch():
    """源默认点与合并默认点不重合 (fvar 默认值不同): 必须重定基, 且不产生
    peak == 0 或跨 0 的非法 hat。"""
    m = AxisMapping((8, 20, 60), None, (14, 14, 32), None)
    lower, peak, upper = 0.0, 1.0, 1.0
    constant, terms = refine_support_rebased({"opsz": (lower, peak, upper)},
                                             {"opsz": m})
    assert abs(constant) > 1e-6, "该用例应触发重定基"
    for sup, _ in terms:
        l, p, u = sup["opsz"]
        assert p != 0.0 and not (l < 0.0 < u), (l, p, u)
    worst = 0.0
    for x in _sample(n=2001):
        want = hat_value(source_location(m, x), lower, peak, upper)
        got = constant + evaluate_supports({"opsz": x}, terms)
        worst = max(worst, abs(want - got))
    assert worst < 1e-9, worst
    print("  test_refine_default_mismatch: 常数 %.3f, %d 条 hat, 误差 %.1e, PASSED"
          % (constant, len(terms), worst))


def test_refine_boundary_truncation():
    """源的支撑超出合并域: 边界截断处用半 hat 表达, 域内仍精确"""
    # 合并域窄 (100..900), 源域宽 (0..1000): 源在 [-1,1] 的支撑映射后会越界
    m = AxisMapping((300, 500, 800), None, (0, 500, 1000), None)
    terms = refine_1d(0.0, 1.0, 1.0, m)
    err = _max_err_1d(0.0, 1.0, 1.0, m, terms)
    assert err < 1e-9, (err, terms)
    # 负侧: start==peak 的半 hat
    terms = refine_1d(-1.0, -1.0, 0.0, m)
    err = _max_err_1d(-1.0, -1.0, 0.0, m, terms)
    assert err < 1e-9, (err, terms)
    print("  test_refine_boundary_truncation: PASSED")


def test_refine_multi_axis():
    """多轴支撑: 逐轴细化后笛卡尔积, 逐点精确"""
    mappings = axis_mappings(
        {"wght": (100, 400, 900), "opsz": (8, 20, 60)},
        {"wght": {-1.0: -1.0, 0.0: 0.0, 0.5: 0.25, 1.0: 1.0}},
        {"wght": (100, 400, 900), "opsz": (14, 14, 32)},
        {"wght": {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0},
         "opsz": {-1.0: -1.0, 0.0: 0.0, 0.5: 0.6, 1.0: 1.0}},
    )
    support = {"wght": (0.0, 0.5, 1.0), "opsz": (0.0, 1.0, 1.0)}
    constant, terms = refine_support_rebased(support, mappings)
    assert terms, "细化结果为空"
    # 合法性: 峰值 ≠ 0、不跨 0
    for sup, _ in terms:
        for tag, (l, p, u) in sup.items():
            assert p != 0.0, (tag, l, p, u)
            assert not (l < 0.0 < u), (tag, l, p, u)
    worst = 0.0
    for w in _sample(n=41):
        for o in _sample(n=41):
            loc = {"wght": w, "opsz": o}
            want = 1.0
            for tag, (l, p, u) in support.items():
                want *= hat_value(source_location(mappings[tag], loc[tag]), l, p, u)
            worst = max(worst, abs((want - constant)
                                   - evaluate_supports(loc, terms)))
    assert worst < 1e-9, (worst,)
    print("  test_refine_multi_axis: %d 条 hat, 常数 %.3f, 误差 %.1e, PASSED"
          % (len(terms), constant, worst))


def test_real_avar_roundtrip():
    """用真实字体 (InterVariable) 的 avar 做自检: 合并空间=源空间时恒等;
    合并域加宽后仍逐点精确"""
    from fontTools.ttLib import TTFont
    p = os.path.join(_test_fonts_dir, "ttf_variable_fonts/InterVariable.ttf")
    if not os.path.exists(p):
        print("  test_real_avar_roundtrip: SKIP (测试字体未就位)")
        return
    font = TTFont(p)
    triples = fvar_triples(font)
    avar = {tag: dict(pts) for tag, pts in font["avar"].segments.items()}
    same = axis_mappings(triples, avar, triples, avar)
    assert all(m.is_identity() for m in same.values()), "同空间应判为恒等"

    wide = dict(triples)
    wide["wght"] = (50, 400, 1000)
    maps = axis_mappings(wide, avar, triples, avar)
    worst = 0.0
    for lower, peak, upper in ((0.0, 0.5, 1.0), (-1.0, -0.3, 0.0)):
        terms = refine_1d(lower, peak, upper, maps["wght"])
        for x in _sample(n=1001):
            want = hat_value(source_location(maps["wght"], x), lower, peak, upper)
            got = sum(w * hat_value(x, l, p, u) for l, p, u, w in terms)
            worst = max(worst, abs(want - got))
    assert worst < 1e-9, worst
    print("  test_real_avar_roundtrip: 误差 %.1e, PASSED" % worst)


def test_random_stress():
    """随机化压力: 随机范围/avar/支撑, 逐点精确 + 生成的 hat 全部合法"""
    import random
    rng = random.Random(20240911)
    worst = 0.0
    worst_case = {}
    n_terms = 0
    for case in range(120):
        def triple():
            default = rng.choice([0, 100, 400, 500])
            lo = default - rng.choice([0, 100, 400])
            hi = default + rng.choice([0, 200, 500, 900])
            return (lo, default, hi)
        mt, st = triple(), triple()
        def avar():
            # 真实 avar 必须**单调不减** (fontTools 会校验), 随机值要排序钳制
            if rng.random() < 0.4:
                return None
            raw = {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0}
            for _ in range(rng.randint(1, 3)):
                k = round(rng.uniform(-0.9, 0.9), 4)
                if abs(k) < 1e-6:
                    continue
                raw[k] = max(-1.0, min(1.0, k + rng.uniform(-0.2, 0.2)))
            pts = {}
            last = -1.0
            for k in sorted(raw):
                v = max(raw[k], last)
                # avar 规范: 必须过 (0,0), 且负侧 ≤ 0、正侧 ≥ 0 (单调不减)
                if abs(k) < 1e-9:
                    v = 0.0
                elif k < 0:
                    v = min(v, 0.0)
                else:
                    v = max(v, 0.0)
                v = max(v, last)
                pts[k] = v
                last = v
            return pts
        ma, sa = avar(), avar()
        m = AxisMapping(mt, ma, st, sa)
        if m.collapsing_flats():
            continue          # 平台段压缩用户区间 → 逐点等价不可达 (见库文档)
        # 随机合法支撑 (落在 0 的一侧)
        sign = rng.choice([-1, 1])
        a = rng.uniform(0.0, 0.8) * sign
        b = rng.uniform(abs(a), 1.0) * sign
        c = rng.uniform(abs(b), 1.0) * sign
        lower, peak, upper = sorted([a, b, c]) if sign > 0 else sorted([a, b, c], reverse=True)
        if sign < 0:
            lower, peak, upper = -abs(upper), -abs(peak), -abs(lower)
            lower, upper = min(lower, upper), max(lower, upper)
        lower, upper = min(lower, upper), max(lower, upper)
        if not (lower <= peak <= upper) or peak == 0.0 or lower < 0.0 < upper:
            continue
        constant, terms = refine_support_rebased({"wght": (lower, peak, upper)},
                                                 {"wght": m})
        for sup, w in terms:
            l, p, u = sup["wght"]
            assert p != 0.0 and not (l < 0.0 < u) and l <= p <= u, (l, p, u)
        # 只在合并轴的**实际定义域**内采样: 单侧轴 (min == default 或
        # default == max) 只有一半的归一化域
        lo_dom, hi_dom = -1.0, 1.0
        if mt[0] == mt[1]:
            lo_dom = 0.0
        if mt[2] == mt[1]:
            hi_dom = 0.0
        for i in range(201):
            x = lo_dom + (hi_dom - lo_dom) * i / 200.0
            want = hat_value(source_location(m, x), lower, peak, upper)
            got = constant + evaluate_supports({"wght": x}, terms)
            if abs(want - got) > worst:
                worst = abs(want - got)
                worst_case = {"mt": mt, "ma": ma, "st": st, "sa": sa,
                              "support": (lower, peak, upper), "x": x}
        n_terms += len(terms)
    # 随机用例含节点去重/浮点往返, 容差取 1e-7 (远低于 F2Dot14 量化 6e-5)
    assert worst < 1e-7, (
        "worst=%r @x=%r (want=%r got=%r) 用例: merged=%r/%r source=%r/%r support=%r"
        % (worst, worst_case.get("x"), worst_case.get("want"),
           worst_case.get("got"), worst_case.get("mt"), worst_case.get("ma"),
           worst_case.get("st"), worst_case.get("sa"), worst_case.get("support")))
    print("  test_random_stress: 120 例, 共 %d 条 hat, 最大误差 %.1e, PASSED"
          % (n_terms, worst))


def test_collapsing_flat_detection():
    """压缩平台段的检测: 合并 avar 把一段用户区间压成一点时, 必须能识别出来
    (此时逐点等价不可达, 调用方应告警或改用 avar_mode=2)。"""
    flat_avar = {-1.0: -1.0, 0.0: 0.0, 0.3: 0.0, 1.0: 1.0}
    m = AxisMapping((-100, 0, 900), flat_avar, (0, 400, 600), None)
    flats = m.collapsing_flats()
    assert flats, "应检测出平台段"
    norm, lo, hi = flats[0]
    assert abs(norm) < 1e-9 and hi - lo > 1.0, flats
    clean = AxisMapping((-100, 0, 900), {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0},
                        (0, 400, 600), None)
    assert not clean.collapsing_flats()
    print("  test_collapsing_flat_detection: 平台段 %.0f..%.0f → norm %.3f, PASSED"
          % (lo, hi, norm))


def test_refine_cross_zero():
    """默认点不重合时, 重定基后的 hat 绝不能跨越归一化默认点 0。

    0 是重定基后的零点, 同时也必须是节点: 一旦它被当成"斜率连续"的冗余点
    剪掉, 相邻 tent 就会横跨 0 —— OT 引擎对 lower < 0 < upper 的区域整条
    忽略 (supportScalar), 于是整个支撑的增量凭空消失 (实测误差 0.625)。
    """
    m = AxisMapping((-100, 400, 900), None, (0, 100, 900), None)
    assert abs(m.to_source(0.0) - 0.375) < 1e-9       # 源默认点 ≠ 合并默认点
    constant, terms = refine_support_rebased({"wght": (0.0, 1.0, 1.0)},
                                             {"wght": m})
    assert abs(constant - 0.375) < 1e-9, constant
    assert terms, "细化结果为空"
    for sup, _w in terms:
        l, p, u = sup["wght"]
        assert p != 0.0 and not (l < 0.0 < u), (l, p, u)
    worst = 0.0
    for x in _sample(-1.0, 1.0, 2001):
        want = hat_value(source_location(m, x), 0.0, 1.0, 1.0)
        got = constant + evaluate_supports({"wght": x}, terms)
        worst = max(worst, abs(want - got))
    assert worst < 1e-7, worst
    print("  test_refine_cross_zero: 常数 %.3f, %d 条 hat, 误差 %.1e, PASSED"
          % (constant, len(terms), worst))


def _make_var_store(regions, columns, rows, num_shorts=0):
    """构造单 VarData 的 ItemVariationStore: regions=[[(s,p,e), ...], ...]"""
    from fontTools.ttLib.tables import otTables as ot

    vs = ot.VarStore()
    vs.Format = 1
    vrl = ot.VarRegionList()
    vrl.RegionAxisCount = len(regions[0]) if regions else 1
    vrl.RegionCount = len(regions)
    vrl.Region = []
    for region_support in regions:
        region = ot.VarRegion()
        region.VarRegionAxis = []
        for (start, peak, end) in region_support:
            axis = ot.VarRegionAxis()
            axis.StartCoord, axis.PeakCoord, axis.EndCoord = start, peak, end
            region.VarRegionAxis.append(axis)
        vrl.Region.append(region)
    vs.VarRegionList = vrl
    vd = ot.VarData()
    vd.VarRegionIndex = list(columns)
    vd.VarRegionCount = len(columns)
    vd.ItemCount = len(rows)
    vd.Item = [list(row) for row in rows]
    vd.NumShorts = num_shorts
    vs.VarData = [vd]
    vs.VarDataCount = 1
    return vs


def _store_supports(var_store, tags):
    from FontMerger.format.variation_compose import _store_region_supports
    return _store_region_supports(var_store, tags)


def _store_response(var_store, tags, outer, inner, loc):
    """引擎语义: VarData[outer].Item[inner] 与各列 region 标量做点积"""
    vd = var_store.VarData[outer]
    sups = _store_supports(var_store, tags)
    return sum(vd.Item[inner][c] * support_value(loc, sups[r])
               for c, r in enumerate(vd.VarRegionIndex))


def _source_response(src_store, mapping, outer, inner, x):
    """源语义: Σ_c delta_c · φ_c(T(x)) —— T 由 mapping (合并 → 源) 给出"""
    vd = src_store.VarData[outer]
    sups = _store_supports(src_store, ["wght"])
    return sum(vd.Item[inner][c]
               * hat_value(source_location(mapping, x), *sups[r]["wght"])
               for c, r in enumerate(vd.VarRegionIndex))


def test_var_store_reparametrize():
    """ItemVariationStore 重参数化 (行保持): 逐个位置精确复现源语义。

    VariationIndex 的 (outer, inner) = (VarData 序号, **行号**): 一行的增量向量
    与各列 region 标量做点积, 所以一行能承载多个 hat —— 重参数化可以做到
    逐点精确 (含"合并默认点取值 C ≠ 0"的恒定列与钳制平台段)。
    容差 1e-6: 细化出的 hat 权重本身有 ~1e-10 级浮点误差 (见随机压测)。
    """
    from FontMerger.format.variation_compose import reparametrize_var_store

    ident = AxisMapping((0, 400, 900), None, (0, 400, 900), None)
    # 多行 (多个设备引用), 每行增量不同 —— 行保持的直接检验
    store = _make_var_store([[(0.0, 1.0, 1.0)]], [0], [[12], [-5], [3]])

    # ① 恒等映射: 结构与增量原样保留
    new, rep = reparametrize_var_store(store, {"wght": ident},
                                       ["wght"], ["wght"])
    assert rep["columns_in"] == 1 and rep["columns_out"] == 1, rep
    assert not rep["changed"] and not rep["constant"], rep
    assert new.VarData[0].Item == [[12], [-5], [3]]
    assert new.VarData[0].ItemCount == 3

    # ② 轴扩展 (打底独有轴 opsz): region 追加恒定轴, 增量/引用不变
    new2, rep2 = reparametrize_var_store(store, {"wght": ident},
                                         ["wght"], ["wght", "opsz"])
    assert rep2["changed"] and new2.VarRegionList.RegionAxisCount == 2, rep2
    ax = new2.VarRegionList.Region[0].VarRegionAxis
    assert (ax[0].StartCoord, ax[0].PeakCoord, ax[0].EndCoord) == (0.0, 1.0, 1.0)
    assert (ax[1].StartCoord, ax[1].PeakCoord, ax[1].EndCoord) == (0.0, 0.0, 0.0)
    assert new2.VarData[0].Item == [[12], [-5], [3]]
    assert new2.VarData[0].ItemCount == 3

    # ③ 合并范围更窄 → 合成结果是一个**缩放** hat (权重 5/14): 换 region +
    #    缩放行增量。取增量 14 的倍数使缩放在整数域精确。
    narrow = AxisMapping((0, 400, 900), None, (0, 400, 1800), None)
    store14 = _make_var_store([[(0.0, 1.0, 1.0)]], [0], [[14], [28]])
    new3, rep3 = reparametrize_var_store(store14, {"wght": narrow},
                                         ["wght"], ["wght"])
    assert new3.VarData[0].Item == [[5], [10]], new3.VarData[0].Item
    assert not rep3["constant"], rep3
    for x in _sample(-1.0, 1.0, 401):
        want = _source_response(store14, narrow, 0, 0, x)
        got = _store_response(new3, ["wght"], 0, 0, {"wght": x})
        assert abs(want - got) < 1e-6, (x, want, got)

    # ④ 钳制平台段 (合并范围更宽): 需要两个 hat → 两列, 一行同时承载
    plateau = AxisMapping((0, 400, 1800), None, (0, 400, 900), None)
    new4, rep4 = reparametrize_var_store(store, {"wght": plateau},
                                         ["wght"], ["wght"])
    assert new4.VarData[0].VarRegionCount == 2, new4.VarData[0].VarRegionIndex
    assert new4.VarData[0].ItemCount == 3, "行数必须保持"
    for row in (0, 1, 2):
        for x in _sample(-1.0, 1.0, 401):
            want = _source_response(store, plateau, 0, row, x)
            got = _store_response(new4, ["wght"], 0, row, {"wght": x})
            assert abs(want - got) < 1e-6, (row, x, want, got)

    # ⑤ 默认点不重合 → C = φ(T(0)) ≠ 0 由一个恒定列承载 (峰值全 0, 标量恒 1);
    #    folded_default=True (打底布局已按合并默认实例化) 时不能加恒定列。
    mismatch = AxisMapping((-100, 400, 900), None, (0, 100, 900), None)
    store8 = _make_var_store([[(0.0, 1.0, 1.0)]], [0], [[8], [0]])
    new5, rep5 = reparametrize_var_store(store8, {"wght": mismatch},
                                         ["wght"], ["wght"])
    assert rep5["constant"], rep5
    for x in _sample(-1.0, 1.0, 401):
        want = _source_response(store8, mismatch, 0, 0, x)
        got = _store_response(new5, ["wght"], 0, 0, {"wght": x})
        assert abs(want - got) < 1e-6, (x, want, got)
    new6, rep6 = reparametrize_var_store(store8, {"wght": mismatch},
                                         ["wght"], ["wght"],
                                         folded_default=True)
    assert not rep6["constant"], rep6
    for x in _sample(-1.0, 1.0, 401):
        want = (_source_response(store8, mismatch, 0, 0, x)
                - _source_response(store8, mismatch, 0, 0, 0.0))
        got = _store_response(new6, ["wght"], 0, 0, {"wght": x})
        assert abs(want - got) < 1e-6, (x, want, got)
    print("  test_var_store_reparametrize: 恒等/扩展/缩放/平台段/恒定列/折叠默认,"
          " PASSED")



def main():
    print("FontMerger axis-mapping Test Suite")
    print("=" * 50)
    tests = [
        test_piecewise_linear_basics,
        test_refine_identity,
        test_refine_affine_range,
        test_refine_avar,
        test_refine_range_and_avar,
        test_refine_default_mismatch,
        test_refine_boundary_truncation,
        test_refine_multi_axis,
        test_real_avar_roundtrip,
        test_random_stress,
        test_collapsing_flat_detection,
        test_refine_cross_zero,
        test_var_store_reparametrize,
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
    print(f"\n{"="*50}")
    print(f"  Results: {passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
