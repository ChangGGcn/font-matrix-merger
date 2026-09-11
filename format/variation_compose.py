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

from fontTools.ttLib.tables import otTables as ot
from fontTools.varLib.instancer import instantiateVariableFont

from .axis_mapping import (AxisMapping, avar_segments, fvar_triples,
                           refine_support_rebased)


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


def reparametrize_var_store(var_store, mappings, fit="exact"):
    """把 ItemVariationStore 的 region 从源空间重参数化到合并空间。

    GDEF/GPOS 的 VariationIndex 用 (VarData 序号, region 序号) 索引 store;
    region 的 (start, peak, end) 是归一化坐标, 跨设计空间时必须重参数化 ——
    一个 region 可能展开成多个 hat, 此时该列的增量按权重复制到各 hat。
    """
    if var_store is None:
        return None
    src_regions = list(var_store.VarRegionList.Region)
    region_terms = []          # 每个源 region -> [(sig, support, weight)]
    for region in src_regions:
        support = {}
        for tag, axis in enumerate(region.VarRegionAxis):
            support[tag] = (axis.StartCoord, axis.PeakCoord, axis.EndCoord)
        region_terms.append(support)
    # 轴序: VarRegionAxis 的顺序对应 fvar 轴序, 这里用 fvar 轴 tag 重建
    return _rebuild_var_store(var_store, src_regions, mappings, fit)


def _rebuild_var_store(var_store, src_regions, mappings, fit):
    """内部: 逐 VarData 重建 (region 索引是 VarData 局部的)"""
    from .axis_mapping import refine_support_rebased as _refine

    axis_tags = list(mappings.keys())
    new_regions = []
    new_index = {}

    def region_index(support):
        key = tuple(sorted((t, tuple(v)) for t, v in support.items()))
        if key not in new_index:
            new_index[key] = len(new_regions)
            new_regions.append(support)
        return new_index[key]

    new_var_data = []
    for vd in var_store.VarData:
        items = getattr(vd, "Item", None)
        if items is None:
            items = getattr(vd, "ItemVariationData", None) or []
        item_count = len(items)
        columns = {}          # 新 region 索引 -> [deltas per item]
        for col, r_idx in enumerate(vd.VarRegionIndex):
            support = {}
            for ax_i, axis in enumerate(src_regions[r_idx].VarRegionAxis):
                if ax_i < len(axis_tags):
                    support[axis_tags[ax_i]] = (axis.StartCoord,
                                                axis.PeakCoord,
                                                axis.EndCoord)
            if fit == "affine":
                _, terms = _map_support_terms(support, mappings, fit)
            else:
                _, terms = _refine(support, mappings)
            for sup, weight in terms:
                if abs(weight) < 1e-6:
                    continue
                idx = region_index(sup)
                col_out = columns.setdefault(idx, [0] * item_count)
                for i in range(item_count):
                    row = items[i]
                    val = row[col] if isinstance(row, (list, tuple)) and col < len(row) else 0
                    col_out[i] += int(round(val * weight))
        if not columns:
            continue
        order = sorted(columns)
        nvd = ot.VarData()
        nvd.VarRegionIndex = order
        nvd.VarRegionCount = len(order)
        nvd.ItemCount = item_count
        nvd.Item = [[columns[c][i] for c in order] for i in range(item_count)]
        nvd.NumShorts = max((len([v for v in row if v]) for row in nvd.Item),
                            default=0)
        new_var_data.append(nvd)
    if not new_var_data:
        return None
    out = ot.VarStore()
    out.Format = 1
    vrl = ot.VarRegionList()
    vrl.RegionAxisCount = len(axis_tags) or 1
    vrl.RegionCount = len(new_regions)
    vrl.Region = []
    for support in new_regions:
        region = ot.VarRegion()
        region.VarRegionAxis = []
        for tag in axis_tags:
            axis = ot.VarRegionAxis()
            start, peak, end = support.get(tag, (0.0, 0.0, 0.0))
            axis.StartCoord, axis.PeakCoord, axis.EndCoord = start, peak, end
            region.VarRegionAxis.append(axis)
        vrl.Region.append(region)
    out.VarRegionList = vrl
    out.VarData = new_var_data
    out.VarDataCount = len(new_var_data)
    return out
