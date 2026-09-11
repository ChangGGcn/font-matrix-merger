# -*- coding: utf-8 -*-
"""跨设计空间的可变数据合成 (阶段 1: glyf/gvar + ItemVariationStore)

把打底可变字体的逐字形增量, 从其**自己的归一化空间**重参数化到合并字体的
归一化空间, 使合并结果在合并设计空间的每一点上都等于"两个字体在该点实例的
合并" (逐点等价, 见 format/axis_mapping.py 的数学基础)。

策略 (默认值即交互式 CLI 的行为):
  * range_policy="main+extra": 共有轴用主字体范围, 打底独有轴用打底范围;
    "union" (并集) / "main" (仅主) 为高级参数;
  * avar_mode: 0=尊重主 avar, 打底数据经用户空间重参数化 (默认);
    1=忽略打底 avar (打底按 fvar 归一化直接映射); 2=完全不用 avar;
  * fit="exact": 精确拆 hat (默认, 逐点零误差);
    "affine": 只映射支撑端点/峰 (体积最小, 有已知偏差, 高级参数);
  * 打底在合并默认位置的实例 (含幽灵点) 由 fontTools instancer 精确插值得到,
    即"必要时插值出新 master"。
"""
import copy
import itertools

from fontTools.ttLib.tables import otTables as ot
from fontTools.varLib.instancer import instantiateVariableFont

from .axis_mapping import (AxisMapping, avar_segments, evaluate_supports,
                           fvar_triples, refine_support_rebased, support_value)


def plan_axis_space(main_font, base_font, range_policy="main+extra",
                    avar_mode=0):
    """规划合并后的轴空间, 返回 (merged_fvar, merged_avar, 映射)。

    merged_fvar: {tag: (min, default, max)}
    merged_avar: {tag: {from: to}} 或 {}
    mappings:    {tag: AxisMapping} —— 合并空间 -> 各源空间 (base/main 共用同一
                 合并空间, 这里返回合并空间到 base 的映射; main 的映射按需另取)
    """
    main_axes = fvar_triples(main_font)
    base_axes = fvar_triples(base_font)
    main_avar = avar_segments(main_font) if avar_mode != 2 else {}
    base_avar = avar_segments(base_font) if avar_mode == 0 else {}

    merged_fvar = {}
    for tag, triple in main_axes.items():
        if tag in base_axes and range_policy == "union":
            lo = min(triple[0], base_axes[tag][0])
            hi = max(triple[2], base_axes[tag][2])
            merged_fvar[tag] = (lo, triple[1], hi)
        else:
            merged_fvar[tag] = triple
    if range_policy != "main":
        for tag, triple in base_axes.items():
            merged_fvar.setdefault(tag, triple)

    merged_avar = {}
    if avar_mode != 2:
        for tag in merged_fvar:
            if tag in main_avar:
                merged_avar[tag] = dict(main_avar[tag])
            elif tag in base_avar:
                merged_avar[tag] = dict(base_avar[tag])

    mappings = {}
    for tag, bt in base_axes.items():
        if tag not in merged_fvar:
            continue                     # range_policy="main" 丢掉了打底独有轴
        mappings[tag] = AxisMapping(merged_fvar[tag], merged_avar.get(tag),
                                    bt, base_avar.get(tag))
    return merged_fvar, merged_avar, mappings


def merged_default_location(merged_fvar, font=None):
    """合并字体的默认轴位置 (用户坐标); font 给定时投影到它的轴上"""
    loc = {tag: triple[1] for tag, triple in merged_fvar.items()}
    if font is None:
        return loc
    own = set(fvar_triples(font))
    return {k: v for k, v in loc.items() if k in own}


def instance_at_merged_default(font, merged_fvar):
    """把源字体实例化到**合并默认位置** (即插值出新的默认 master)。

    含幽灵点: 实例化后的 hmtx/轮廓就是合并默认点上的正确值。
    """
    loc = merged_default_location(merged_fvar, font)
    if not loc:
        return copy.deepcopy(font)
    return instantiateVariableFont(font, loc, inplace=False, optimize=False)


def _map_support_terms(support, mappings, fit="exact"):
    """源空间支撑 -> 合并空间项: [(support_dict, weight)], 常数另行返回"""
    if fit == "affine":
        sup = {}
        for tag, (lower, peak, upper) in support.items():
            if peak == 0.0:
                continue
            m = mappings.get(tag)
            if m is None:
                continue
            sup[tag] = tuple(round(v, 10) for v in
                             (m.to_merged(lower), m.to_merged(peak),
                              m.to_merged(upper)))
        return (0.0, [(sup, 1.0)]) if sup else (0.0, [])
    return refine_support_rebased(support, mappings)


def reparametrize_gvar(merged_font, source_font, mappings, glyph_names=None,
                       fit="exact"):
    """把 source_font 的逐字形 gvar 增量重参数化进 merged_font。

    merged_font 的 fvar/avar 必须是规划好的合并轴空间; 调用前应已用
    instance_at_merged_default() 得到的实例作为默认轮廓。

    Returns:
        {"glyphs": n, "tuples_in": n, "tuples_out": n, "collapsing_flats": [...]}
    """
    stats = {"glyphs": 0, "tuples_in": 0, "tuples_out": 0,
             "collapsing_flats": []}
    if "gvar" not in merged_font or "gvar" not in source_font:
        return stats
    for tag, m in mappings.items():
        for flat in m.collapsing_flats():
            stats["collapsing_flats"].append((tag,) + tuple(flat))

    names = glyph_names if glyph_names is not None else source_font.getGlyphOrder()
    existing = merged_font["gvar"].variations
    for gn in names:
        source_tuples = source_font["gvar"].variations.get(gn)
        if not source_tuples:
            continue
        out = []
        for tv in source_tuples:
            support = {tag: tuple(v) for tag, v in tv.axes.items()
                       if tuple(v)[1] != 0.0}
            if not support:
                continue
            stats["tuples_in"] += 1
            try:
                _, terms = _map_support_terms(support, mappings, fit)
            except KeyError:
                continue
            for sup, weight in terms:
                if abs(weight) < 1e-6:
                    continue
                new_tv = copy.deepcopy(tv)
                new_tv.axes = {tag: tuple(v) for tag, v in sup.items()}
                deltas = []
                for coord in tv.coordinates:
                    if coord is None:
                        deltas.append(None)
                    elif isinstance(coord, tuple):
                        deltas.append(tuple(round(c * weight) for c in coord))
                    else:
                        deltas.append(round(coord * weight))
                new_tv.coordinates = deltas
                out.append(new_tv)
                stats["tuples_out"] += 1
        if out:
            existing[gn] = out
            stats["glyphs"] += 1
    return stats


#: 空支撑 = 标量恒 1 的"恒定 region"。OT 语义: 某轴 peakCoord = 0 时该轴被忽略,
#: 全轴 peak 都为 0 的 region 标量恒 1 —— 于是"合并默认点取值 C"可以作为一个
#: 额外的列承载, 不必去改 GPOS 的静态值。
CONSTANT_SUPPORT = {}


def _store_region_supports(var_store, src_tags):
    """VarStore 的每个 region → {轴 tag: (start, peak, end)}"""
    out = []
    for region in var_store.VarRegionList.Region:
        sup = {}
        for i, ax in enumerate(region.VarRegionAxis):
            if i < len(src_tags):
                sup[src_tags[i]] = (float(ax.StartCoord), float(ax.PeakCoord),
                                    float(ax.EndCoord))
        out.append(sup)
    return out


def _make_region(support, dst_tags):
    """按目标轴序构造 VarRegion (目标有而源没有的轴 = 恒定 0)"""
    region = ot.VarRegion()
    region.VarRegionAxis = []
    for tag in dst_tags:
        start, peak, end = support.get(tag, (0.0, 0.0, 0.0))
        axis = ot.VarRegionAxis()
        axis.StartCoord, axis.PeakCoord, axis.EndCoord = (float(start),
                                                          float(peak),
                                                          float(end))
        region.VarRegionAxis.append(axis)
    return region


def _num_shorts(rows, orig=0):
    """VarData.wordDeltaCount: 前 n 个增量按 int16 存, 其余按 int8"""
    long_words = bool(orig & 0x8000)
    limit = 32767 if long_words else 127
    n1 = 0
    for row in rows:
        for i, v in enumerate(row):
            if abs(v) > limit:
                n1 = max(n1, i + 1)
    return n1 | (0x8000 if long_words else 0)


def reparametrize_var_store(var_store, mappings, src_tags, dst_tags=None,
                            folded_default=False, eps=1e-4):
    """ItemVariationStore 的 region 从源轴空间重参数化到合并轴空间 (行保持)。

    VariationIndex 的 (outer, inner) = (VarData 序号, 该 VarData 的**行号**):
    引擎取这一行的增量向量与各列 region 的标量做点积。也就是说一行可以承载
    **多个** hat (列 = hat, 行值 = 权重) —— 与 gvar 的元组体系同构, 因此可以
    **精确**重参数化, 不存在"一个设备只能一个 region"的限制:

      * φ_S(T(x)) 精确分解成 Σ_k w_k·φ_{S_k}(x) + C  (refine_support_rebased);
      * 新 region 表 = 所有分解项的并集 (+ 恒定 region, 见 folded_default);
      * **行保持**: ItemCount 与行序不变, 行增量按权重重分配到新列, 于是
        所有 (outer, inner) 引用无需重写 (并集时的 outer 基址偏移机制照旧)。

    Args:
        var_store: otTables.VarStore 或 None
        mappings: {轴 tag: AxisMapping} —— 合并空间 → 源空间
        src_tags: 源字体的 fvar 轴序 (VarRegionAxis 下标含义)
        dst_tags: 合并字体的 fvar 轴序 (缺省同 src_tags)
        folded_default: 静态值里是否已经折入了"合并默认点"的贡献。打底布局在
            合并默认点实例化后即如此 —— 此时必须丢掉常数 C (否则会重复计入);
            False 时 C 由一个峰值全 0 的恒定 region 承载 (标量恒 1)。

    Returns:
        (new_var_store, report); report: regions/columns_in/columns_out/
        constant/changed
    """
    report = {"regions": 0, "columns_in": 0, "columns_out": 0,
              "constant": False, "changed": False}
    if var_store is None:
        return None, report
    dst_tags = list(dst_tags if dst_tags is not None else src_tags)
    src_regions = _store_region_supports(var_store, src_tags)
    report["regions"] = len(src_regions)

    new_regions = []
    region_index = {}

    def index_of(support):
        key = tuple(sorted((tag, tuple(round(v, 9) for v in sup))
                           for tag, sup in support.items()))
        if key not in region_index:
            region_index[key] = len(new_regions)
            new_regions.append(support)
        return region_index[key]

    # 每个源 region 的"新列计划": (新 region 下标, 权重) 列表
    plans = []
    for sup in src_regions:
        if not sup:                       # 恒定 region: 原样保留
            plans.append([(index_of(CONSTANT_SUPPORT), 1.0)])
            continue
        constant, terms = refine_support_rebased(sup, mappings, eps)
        if folded_default:
            constant = 0.0
        agg = {}                          # 相同新 region 的权重先合并
        order = []
        for term_support, weight in terms:
            idx = index_of(dict(term_support))
            if idx not in agg:
                order.append(idx)
                agg[idx] = 0.0
            agg[idx] += weight
        cols = [(idx, agg[idx]) for idx in order if abs(agg[idx]) > eps]
        if abs(constant) > eps:
            cols.append((index_of(CONSTANT_SUPPORT), constant))
            report["constant"] = True
        plans.append(cols)

    new_var_data = []
    for vd in var_store.VarData:
        items = list(getattr(vd, "Item", None) or [])
        src_index = list(vd.VarRegionIndex)
        report["columns_in"] += len(src_index)
        n_new = sum(len(plans[r]) for r in src_index)
        rows = []
        for item in items:
            row = [0] * n_new
            pos = 0
            for c, r in enumerate(src_index):
                val = (item[c] if isinstance(item, (list, tuple))
                       and c < len(item) else 0)
                for _idx, weight in plans[r]:
                    row[pos] = int(round(val * weight))
                    pos += 1
            rows.append(row)
        nvd = ot.VarData()
        nvd.VarRegionIndex = [idx for r in src_index for idx, _w in plans[r]]
        nvd.VarRegionCount = len(nvd.VarRegionIndex)
        nvd.ItemCount = len(rows)
        nvd.Item = rows
        nvd.NumShorts = _num_shorts(rows, getattr(vd, "NumShorts", 0) or 0)
        report["columns_out"] += nvd.VarRegionCount
        new_var_data.append(nvd)

    out = ot.VarStore()
    out.Format = 1
    vrl = ot.VarRegionList()
    vrl.RegionAxisCount = max(1, len(dst_tags))
    vrl.RegionCount = len(new_regions)
    vrl.Region = [_make_region(sup, dst_tags) for sup in new_regions]
    out.VarRegionList = vrl
    out.VarData = new_var_data
    out.VarDataCount = len(new_var_data)
    trivial = all(len(plans[i]) == 1 and plans[i][0] == (i, 1.0)
                  for i in range(len(plans)))
    report["changed"] = not (trivial and list(src_tags) == dst_tags)
    return out, report
