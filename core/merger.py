"""FontMerger 主类 — 编排 16 种类型组合的合并流程"""
import copy
from io import BytesIO
from fontTools.ttLib import TTFont
from ..utils.detect import is_cff, is_ttf, is_variable, type_label
from ..format.converter import convert_font_format
from ..format.static_extract import variable_to_static
from ..format.subsetter import create_glyph_subset
from .conflict import resolve_conflicts, plan_alias
from .glyph_copy import merge_glyphs_via_ttx


def _diagnose_empty_merge(m, b, conflicts):
    """诊断为何合并没有新增字形，返回可读的原因"""
    from ..format.cid_convert import _is_cid_font
    mn = set(m.getGlyphOrder())
    bn = set(b.getGlyphOrder())

    # 情况1: 双CID字体字符集高度重叠
    if _is_cid_font(m) and _is_cid_font(b):
        overlap = mn & bn
        if len(overlap) > len(mn) * 0.5:
            return ("两个CID字体字符集高度重叠 (共同字形 {}/{}). "
                    "建议: 调换主/打底顺序, 或将其中一个转为name-keyed后再合并. "
                    "详见 fontTools issue #3890").format(len(overlap), len(mn))

    # 情况2: 打底字形的码位全部与主字体冲突
    if len(conflicts) > len(bn) * 0.9:
        return ("打底字体 {}/{} 字形与主字体码位或名称冲突. "
                "两个字体可能覆盖同一字符集, 合并无意义").format(len(conflicts), len(bn))

    # 情况3: 打底字形的名称全部已在主字体中
    if len(overlap := mn & bn) > len(bn) * 0.9:
        return ("打底字体 {}/{} 字形名已存在于主字体. "
                "可能为同一字体的不同版本").format(len(overlap), len(bn))

    # 情况4: 打底字形数很少
    if len(bn) <= 5:
        return "打底字体字形数过少 (≤5)"

    return "所有打底字形均被主字体覆盖或冲突"


def check_compatibility(main_font, base_font):
    """在合并前检查两个字体的兼容性, 返回 (ok: bool, warnings: list[str])"""
    warnings = []
    from ..format.cid_convert import _is_cid_font

    # CID + CID 同字符集
    if _is_cid_font(main_font) and _is_cid_font(base_font):
        mn = set(main_font.getGlyphOrder())
        bn = set(base_font.getGlyphOrder())
        overlap = mn & bn
        if len(overlap) > len(mn) * 0.5:
            warnings.append(
                "双CID字体: 字符集高度重叠 ({} 个CID名冲突). "
                "合并后新增字形可能为0. "
                "建议: 调换主/打底顺序, 或使用非CID字体作为主字体".format(len(overlap)))

    # 混合轮廓格式 (CFF + glyf)
    if is_cff(main_font) != is_cff(base_font):
        main_type = "CFF" if is_cff(main_font) else "glyf"
        base_type = "CFF" if is_cff(base_font) else "glyf"
        warnings.append(
            "混合轮廓格式: 主字体为{}, 打底为{}. 将自动转换打底字体".format(main_type, base_type))

    # 可变字体提醒: 走 merge_two 的可变路径时, 打底字体会被实例化为静态
    # (新增字形将失去轴变化) —— 这是**信息损失**, 必须明示。
    if is_variable(main_font):
        warnings.append(
            "主字体为可变字体: 默认路径保留主字体可变性, 但打底字形按默认实例合并 "
            "(新增字形不随轴变化); 同源分片请改用 merge_subsets()")
    if is_variable(base_font):
        warnings.append(
            "打底字体为可变字体: 将先实例化为静态再合并, 其字形不随轴变化; "
            "同源分片请改用 merge_subsets()")

    # UPM 不匹配
    main_upm = main_font["head"].unitsPerEm
    base_upm = base_font["head"].unitsPerEm
    if main_upm != base_upm:
        warnings.append(
            "UPM不匹配: 主字体{} vs 打底字体{}. 将自动缩放打底字体".format(main_upm, base_upm))

    return (len([w for w in warnings if "合并后新增字形可能为0" in w]) == 0, warnings)


def axes_compatible(main_font, base_font):
    """两个字体的轴空间与 avar 映射是否完全一致。

    逐字形增量 (gvar 的 tuple 峰值坐标) 是**归一化坐标**; 只有当两边的
    fvar 轴 (顺序/tag/上下限/默认值) 与 avar 映射都一样时, 打底的增量才能
    原样搬到主字体上。轴空间不一致就该先在设计空间层面做合成
    (fontTools.varLib.merger / varLib.build 的领域), 不属于这里。
    """
    if not (is_variable(main_font) and is_variable(base_font)):
        return False
    if "glyf" not in main_font or "glyf" not in base_font:
        return False
    ma = [(a.axisTag, a.minValue, a.defaultValue, a.maxValue)
          for a in main_font["fvar"].axes]
    ba = [(a.axisTag, a.minValue, a.defaultValue, a.maxValue)
          for a in base_font["fvar"].axes]
    if ma != ba:
        return False

    def avar_key(font):
        if "avar" not in font:
            return None
        segments = getattr(font["avar"], "segments", None)
        if not segments:
            return None
        return tuple(sorted((tag, tuple(sorted(pts.items())))
                            for tag, pts in segments.items()))

    return avar_key(main_font) == avar_key(base_font)


def transfer_glyph_variations(result, base_var, glyph_names):
    """把打底 VF 的逐字形 gvar 增量搬进合并结果。

    调用前必须确认 :func:`axes_compatible` (轴空间/avar 一致), 否则峰值
    坐标含义不同。搬运后 HVAR 需要重建 —— 用 fontTools 官方的
    varLib.hvar.add_HVAR() 从 gvar 幽灵点重算, 这样新增字形的字宽也随轴变化,
    而不是停在默认实例的值。

    Returns:
        实际搬运增量的字形数
    """
    if "gvar" not in result or "gvar" not in getattr(base_var, "keys", lambda: [])():
        return 0
    n_axes = len(result["fvar"].axes)
    moved = 0
    for gn in glyph_names:
        variations = base_var["gvar"].variations.get(gn)
        if not variations:
            continue
        if any(len(tv.axes) != n_axes for tv in variations):
            continue        # 轴数不符: 放弃该字形, 保持默认实例
        result["gvar"].variations[gn] = copy.deepcopy(variations)
        moved += 1
    if moved:
        try:
            from fontTools.varLib.hvar import add_HVAR
            add_HVAR(result)
        except Exception as e:
            print(f"  [增量] HVAR 重建失败 ({e}), 新增字形的字宽可能不随轴变化")
    return moved


def _copy_axis_records(src_font, dst_font, merged_fvar, merged_avar):
    """把合并轴空间写进主字体: fvar (含打底独有轴) + avar + 轴名记录。"""
    from fontTools.ttLib.tables._f_v_a_r import Axis

    src_axes = {a.axisTag: a for a in src_font["fvar"].axes}
    dst_axes = {a.axisTag: a for a in dst_font["fvar"].axes}
    new_axes = []
    for tag, (lo, default, hi) in merged_fvar.items():
        if tag in dst_axes:
            axis = dst_axes[tag]
            axis.minValue, axis.defaultValue, axis.maxValue = lo, default, hi
        elif tag in src_axes:                # 打底独有轴: 连轴名一起搬过来
            axis = copy.deepcopy(src_axes[tag])
            axis.minValue, axis.defaultValue, axis.maxValue = lo, default, hi
            _copy_name_records(src_font, dst_font, axis.axisNameID)
        else:
            axis = Axis()
            axis.axisTag = tag
            axis.minValue, axis.defaultValue, axis.maxValue = lo, default, hi
            axis.axisNameID = 256
        new_axes.append(axis)
    dst_font["fvar"].axes = new_axes
    _fill_fvar_instances(dst_font, merged_fvar)
    for axis in new_axes:                   # 新增轴补 STAT AxisRecord
        if axis.axisTag not in dst_axes:
            from ..format.vf_axes import _ensure_stat_axis
            _ensure_stat_axis(dst_font, axis)

    if merged_avar:
        # avar 的 compile 会为**每条** fvar 轴取 segments[axis] —— 无 avar 的轴
        # (打底独有轴等) 必须补恒等段, 否则保存时 KeyError
        identity = {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0}
        segments = {tag: dict(merged_avar.get(tag) or identity)
                    for tag in merged_fvar}
        if "avar" in dst_font:
            dst_font["avar"].segments = segments
        else:
            from fontTools.ttLib import newTable
            avar = newTable("avar")
            avar.segments = segments
            dst_font["avar"] = avar
    elif "avar" in dst_font:
        del dst_font["avar"]                # avar_mode=2: 完全不用 avar


def _fill_fvar_instances(font, merged_fvar):
    """fvar 命名实例: 新轴补默认值 (实例缺轴坐标会让 instancer 直接 KeyError)"""
    fvar = font.get("fvar")
    if fvar is None:
        return
    for inst in getattr(fvar, "instances", None) or []:
        coords = getattr(inst, "coordinates", None)
        if coords is None:
            continue
        for tag, (_lo, default, _hi) in merged_fvar.items():
            coords.setdefault(tag, default)


def _copy_name_records(src_font, dst_font, name_id):
    """确保 nameID 在两个字体里都有记录 (打底独有轴的名字)"""
    if "name" not in src_font or "name" not in dst_font:
        return
    have = {(r.nameID, r.platformID, r.platEncID, r.langID)
            for r in dst_font["name"].names}
    for rec in src_font["name"].names:
        if rec.nameID != name_id:
            continue
        key = (rec.nameID, rec.platformID, rec.platEncID, rec.langID)
        if key not in have:
            dst_font["name"].names.append(copy.deepcopy(rec))


def _compose_cff2_base(m, b, base_font, plan):
    """CFF2 打底: 把轮廓的可变数据 (blend/vsindex) 重参数化后并入。

    b 仍来自"合并默认点实例化" (hmtx/度量/布局静态值都在合并默认点上), 只把
    CFF2 表换成重参数化后的版本 —— 于是轮廓在合并空间各处都对, 度量变化由
    HVAR 在字形合并之后并入 (见 _finish_cff2_hvar)。
    """
    from ..format.cff2_compose import (is_cff2_variable, merge_cff2_var_stores,
                                       reparametrize_cff2, reparametrize_hvar,
                                       cff2_var_store)

    if not (is_cff2_variable(m) and is_cff2_variable(base_font)):
        return False
    src_tags = [a.axisTag for a in base_font["fvar"].axes]
    # main_maps 的插入序 = 主字体原始 fvar 轴序 (此刻 m 的 fvar 已是合并轴空间)
    main_tags = list(plan["main_maps"])
    dst_tags = list(plan["fvar"])
    base_var = copy.deepcopy(base_font)
    rep = reparametrize_cff2(base_var, plan["base_maps"], src_tags, dst_tags)
    reparametrize_hvar(base_var, plan["base_maps"], src_tags, dst_tags,
                       folded_default=True)
    info = merge_cff2_var_stores(m, base_var, plan["main_maps"], main_tags,
                                 dst_tags)
    base_hvar = base_var.get("HVAR")
    plan["cff2"] = {
        "rep": rep,
        "offset": info["offset"],
        "main_changed": info["main_changed"],
        "hvar_store": (base_hvar.table.VarStore if base_hvar is not None else None),
        "hvar_map": (dict(base_hvar.table.AdvWidthMap.mapping)
                     if base_hvar is not None
                     and getattr(base_hvar.table, "AdvWidthMap", None) is not None
                     else {}),
    }
    b["CFF2"] = base_var["CFF2"]
    print("  [合成] 打底 CFF2: %d 个 blend 重参数化 (列 %d → %d, VarStore 基址 %d%s)"
          % (rep["blends"], rep["columns"][0], rep["columns"][1], info["offset"],
             ", 主 VarStore 已重算" if info["main_changed"] else ""))
    return True


def _finish_cff2_hvar(result, m, plan):
    """字形合并之后: 打底 HVAR 的变化宽度接入 (AdvWidthMap 按字形名重建)"""
    info = plan.get("cff2") if plan else None
    if not info or info.get("hvar_store") is None:
        return
    from ..format.cff2_compose import merge_cff2_hvar

    added = set(result.getGlyphOrder()) - set(m.getGlyphOrder())
    rep = merge_cff2_hvar(result, info["hvar_store"], info["hvar_map"], added)
    if rep:
        print("  [合成] 打底 HVAR: %d 个字形接入变化宽度 (VarStore 基址 %d)"
              % (rep["glyphs"], rep["offset"]))


def _transfer_base_layout_once(b, base_font, plan):
    """打底布局变化数据 (GDEF VarStore + GPOS VariationIndex) 并入实例化后的打底。

    失败不影响主流程: 打底布局停在"合并默认点实例化"的状态 (即改动前的行为),
    只打印告警 —— 布局变化数据的丢失远好于写出引用错乱的布局表。
    """
    from ..format.variation_compose import transfer_base_layout

    try:
        report = transfer_base_layout(b, base_font, plan["base_maps"],
                                      plan["fvar"])
    except Exception as e:
        print(f"  [合成] 打底布局变化数据未并入 (保留默认实例): {e}")
        return
    if report["grafted"]:
        print("  [合成] 打底布局变化数据: GDEF VarStore %d 个 VarData, "
              "列 %d → %d (VariationIndex 行保持)"
              % (report["var_data"], report["columns"][0],
                 report["columns"][1]))


def _map_main_var_stores(font, mappings, src_tags, dst_tags, label="合成"):
    """把主字体自己的 ItemVariationStore 重参数化到合并轴空间 (行保持)。

    涉及 GDEF (GPOS/GSUB 的 VariationIndex 基座) 与 HVAR/VVAR/MVAR/BASE。
    轴范围改写或新增轴时 region 的 (start, peak, end) 必须重算:
    RegionAxisCount 与新 fvar 轴数不一致会直接写出非法字体; 共有轴范围变化
    而不重算则会把增量解释到错误的归一化空间。行保持 → VariationIndex 的
    (outer, inner) 引用不需要重写。

    Returns:
        {"regions", "columns_in", "columns_out", "constant"} 汇总
    """
    from ..format.variation_compose import reparametrize_var_store

    total = {"regions": 0, "columns_in": 0, "columns_out": 0, "constant": False}
    for tag in ("GDEF", "HVAR", "VVAR", "MVAR", "BASE"):
        if tag not in font:
            continue
        table = getattr(font[tag], "table", None)
        store = getattr(table, "VarStore", None) if table is not None else None
        if store is None:
            continue
        new_store, report = reparametrize_var_store(store, mappings, src_tags,
                                                    dst_tags)
        table.VarStore = new_store
        for key in ("regions", "columns_in", "columns_out"):
            total[key] += report[key]
        total["constant"] = total["constant"] or report["constant"]
        print("  [%s] 主字体 %s VarStore: %d 区域, %d → %d 列%s"
              % (label, tag, report["regions"], report["columns_in"],
                 report["columns_out"],
                 " (含恒定列)" if report["constant"] else ""))
    return total


def _reparametrize_main_after_union(main_font, before_axes, before_avar):
    """旧回退路径的补救: 轴并集后主字体的 VarStore 也要跟着新轴空间走。

    旧路径不改主字体的 gvar (历史已知限制), 但 VarStore 的区域坐标**必须**
    重算 —— 轴数不一致是非法字体; 共有轴范围被并集撑大时, 旧坐标会把增量
    解释到错误的归一化空间。宁可把无法精确表达的列清零也不要写错值。
    """
    from ..format.axis_mapping import AxisMapping, avar_segments, fvar_triples

    after_axes = fvar_triples(main_font)
    src_tags = list(before_axes)
    dst_tags = list(after_axes)
    if src_tags == dst_tags and all(before_axes[t] == after_axes.get(t)
                                    for t in src_tags):
        return None                        # 轴空间没变
    after_avar = avar_segments(main_font)
    mappings = {}
    for tag in src_tags:
        mappings[tag] = AxisMapping(after_axes.get(tag, before_axes[tag]),
                                    after_avar.get(tag), before_axes[tag],
                                    before_avar.get(tag))
    return _map_main_var_stores(main_font, mappings, src_tags, dst_tags,
                                label="回退")


def _apply_axis_plan(main_font, base_font, range_policy, avar_mode, fit):
    """按策略把主字体扩成合并轴空间, 并重参数化主字体自身的增量。

    Returns:
        plan = {"fvar":…, "avar":…, "base_maps":…} 或 None (不可合成)
    """
    from ..format.variation_compose import (plan_axis_space,
                                            reparametrize_gvar)
    from ..format.axis_mapping import AxisMapping

    _force_load_axis_tables(main_font)

    merged_fvar, merged_avar, base_maps = plan_axis_space(
        main_font, base_font, range_policy=range_policy, avar_mode=avar_mode)
    if not merged_fvar or not base_maps:
        return None
    src_tags = [a.axisTag for a in main_font["fvar"].axes]
    dst_tags = list(merged_fvar)
    # 主字体自身也要重参数化吗? (范围并集 / 放弃 avar 时归一化变了)
    main_axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue)
                 for a in main_font["fvar"].axes}
    from ..format.axis_mapping import avar_segments
    main_avar = avar_segments(main_font) if avar_mode != 2 else {}
    main_maps = {}
    needs_main = False
    for tag, triple in main_axes.items():
        if tag not in merged_fvar:
            continue
        m = AxisMapping(merged_fvar[tag], merged_avar.get(tag),
                        triple, main_avar.get(tag))
        main_maps[tag] = m
        if not m.is_identity():
            needs_main = True
    if needs_main and "gvar" in main_font:
        source = copy.deepcopy(main_font)
        reparametrize_gvar(main_font, source, main_maps,
                           list(main_font.getGlyphOrder()), fit=fit)
    if needs_main or src_tags != dst_tags:
        # 轴空间变了 (范围/avar/轴集合): 主字体自己的 ItemVariationStore
        # (GDEF/GPOS 的 VariationIndex 基座, 以及 HVAR/VVAR/MVAR) 的 region
        # 坐标必须跟着变 —— 轴数不一致会写出非法字体, 共有轴范围变化则会把
        # 增量解释到错误的归一化空间。
        _map_main_var_stores(main_font, main_maps, src_tags, dst_tags)
    _copy_axis_records(base_font, main_font, merged_fvar, merged_avar)
    return {"fvar": merged_fvar, "avar": merged_avar, "base_maps": base_maps,
            "main_maps": main_maps}


def _finish_variable_merge(merger, result, m, b, variable_source, plan):
    """字形合并后的可变数据收尾: 跨设计空间合成 (含自检) 或增量搬运。

    合成自检失败会向上抛异常, 由 FontMerger._do_merge 回退到旧路径;
    这里返回"实际新增的字形名"列表 (含组件闭包补进来的)。
    """
    _finish_cff2_hvar(result, m, plan)
    main_names = set(m.getGlyphOrder())
    added_now = [gn for gn in result.getGlyphOrder() if gn not in main_names]
    if plan is not None:
        from ..format.variation_compose import reparametrize_gvar
        stats = reparametrize_gvar(result, variable_source, plan["base_maps"],
                                   added_now, fit=merger.compose_fit)
        if stats["glyphs"] and "gvar" in result:
            from fontTools.varLib.hvar import add_HVAR
            add_HVAR(result)
        moved = stats["glyphs"]
        print("  [合成] %d 个新增字形按合并空间重参数化 (tuple %d → %d)"
              % (moved, stats["tuples_in"], stats["tuples_out"]))
        if merger.verify_compose:
            from .verify import verify_composition
            verify_composition(result, m, variable_source, added_now,
                               max_positions=4, adv_tolerance=3.0)
    elif variable_source is not None:
        moved = transfer_glyph_variations(result, variable_source, added_now)
        if moved:
            print(f"  [增量] {moved} 个新增字形保留轴变化 (gvar 增量搬运)")
    return added_now


def _force_load_axis_tables(font):
    """轴数变化前把"按轴数编码"的表读进内存。

    否则之后从 reader 读到的是旧轴数的二进制 (gvar.axisCount 等), 与新的
    fvar 不一致, instancer 会直接断言失败 (实测 (2, 1, ['wght','opsz']))。
    """
    for tag in ("gvar", "HVAR", "VVAR", "MVAR", "cvar", "avar", "STAT"):
        if tag in font:
            font[tag]


def _collapsing_flats(plan):
    """合并 avar 的压缩平台段 (该区间无法逐点等价, 需要告警)"""
    out = []
    for tag, mapping in plan.get("base_maps", {}).items():
        for norm, lo, hi in mapping.collapsing_flats():
            out.append((tag, norm, lo, hi))
    return out


def _remove_ros(font):
    """从 CFF 字体移除 ROS/FDSelect/FDArray, 转回 name-keyed"""
    if "CFF " not in font:
        return
    td = font["CFF "].cff.topDictIndex[0]
    if hasattr(td, 'ROS'):
        del td.ROS
    if hasattr(td, 'FDSelect'):
        del td.FDSelect
    if hasattr(td, 'FDArray') and td.FDArray and len(td.FDArray) > 0:
        if hasattr(td.FDArray[0], 'Private') and td.FDArray[0].Private:
            td.Private = td.FDArray[0].Private
        del td.FDArray


def _add_cid_prefix(font, prefix):
    """给 CID 字体的所有字形名加前缀，避免与另一个 CID 字体重名。
    同时移除 ROS/FDSelect 转回 name-keyed (消除 CFF 编译时的 CID 约束)。
    .notdef 保留原名。"""
    order = font.getGlyphOrder()
    mapping = {}
    for gn in order:
        if gn == ".notdef":
            mapping[gn] = gn  # 保留 .notdef
        else:
            mapping[gn] = prefix + gn
    new_order = [mapping[gn] for gn in order]

    cff_td = font["CFF "].cff.topDictIndex[0]
    cs = cff_td.CharStrings
    cs.charStrings = {mapping.get(k, k): v for k, v in cs.charStrings.items()}
    cff_td.charset = new_order
    font.setGlyphOrder(new_order)

    # 移除 CID 标记：转回 name-keyed CFF
    if hasattr(cff_td, 'ROS'):
        del cff_td.ROS
    if hasattr(cff_td, 'FDSelect'):
        del cff_td.FDSelect
    # 合并 Private (单 FD 字体)
    if hasattr(cff_td, 'FDArray') and cff_td.FDArray and len(cff_td.FDArray) > 0:
        if hasattr(cff_td.FDArray[0], 'Private') and cff_td.FDArray[0].Private:
            cff_td.Private = cff_td.FDArray[0].Private
        del cff_td.FDArray

    if "hmtx" in font:
        font["hmtx"].metrics = {mapping.get(k, k): v
                                for k, v in font["hmtx"].metrics.items()}
    if "vmtx" in font:
        font["vmtx"].metrics = {mapping.get(k, k): v
                                for k, v in font["vmtx"].metrics.items()}
    for table in font["cmap"].tables:
        if hasattr(table, "cmap") and table.cmap:
            for cp in list(table.cmap.keys()):
                gn = table.cmap[cp]
                table.cmap[cp] = mapping.get(gn, gn)
    if "maxp" in font:
        font["maxp"].numGlyphs = len(new_order)


def _normalize_upm(main_font, base_font):
    """如果 UPM 不同，将打底字体缩放为主字体的 UPM"""
    main_upm = main_font["head"].unitsPerEm
    base_upm = base_font["head"].unitsPerEm
    if main_upm == base_upm:
        return base_font

    from fontTools.ttLib.scaleUpem import scale_upem
    print(f"  [UPM] 缩放打底字体: {base_upm} → {main_upm}")
    scaled = copy.deepcopy(base_font)
    scale_upem(scaled, main_upm)
    return scaled


class FontMerger:
    """字体合并器。

    跨设计空间合成的策略参数 (默认值即交互式 CLI 行为):
        compose_variations: 是否启用"打底字形随轴变化"的跨设计空间合成
        compose_range: "main+extra" (共有轴用主范围 + 打底独有轴) |
                       "union" (并集) | "main" (仅主范围) —— 高级参数
        compose_fit: "exact" (精确拆 hat) | "affine" (仅仿射, 体积最小) —— 高级参数
        avar_mode: 0=尊重主 avar (打底重参数化到主空间); 1=忽略打底 avar;
                   2=完全不用 avar
        verify_compose: 合成后跑网格采样自检, 不通过则回退到默认实例合并
        compose_layout: 打底的布局变化数据 (GDEF ItemVariationStore + GPOS 的
                   VariationIndex 设备) 一并重参数化并入 (默认 True)
    """

    def __init__(self, compose_variations=True, compose_range="main+extra",
                 compose_fit="exact", avar_mode=0, verify_compose=True,
                 compose_layout=True):
        self.mem = {}
        self.compose_variations = compose_variations
        self.compose_range = compose_range
        self.compose_fit = compose_fit
        self.avar_mode = avar_mode
        self.verify_compose = verify_compose
        self.compose_layout = compose_layout

    def ask(self, key, q, opts=None):
        if key in self.mem:
            print(f"  [记忆] {q} → {self.mem[key]}")
            return self.mem[key]
        print(f"\n[询问] {q}")
        if opts:
            for i, o in enumerate(opts, 1):
                print(f"  {i}. {o}")
        while True:
            a = input("> ").strip()
            if opts:
                try:
                    n = int(a) - 1
                    if 0 <= n < len(opts):
                        self.mem[key] = opts[n]
                        return opts[n]
                except ValueError:
                    pass
                print(f"  请输入 1-{len(opts)}")
            else:
                self.mem[key] = a
                return a

    def merge_two(self, m, b):
        ms = not is_variable(m)
        mt = is_ttf(m)
        bs = not is_variable(b)
        bt = is_ttf(b)
        print(f"  主: {type_label(m)} | 打底: {type_label(b)}")

        if ms and not mt:
            if bs and not bt:       return self._sOTF_sOTF(m, b)
            if bs and bt:           return self._sOTF_sTTF(m, b)
            if not bs and not bt:   return self._sOTF_vOTF(m, b)
            if not bs and bt:       return self._sOTF_vTTF(m, b)
        if ms and mt:
            if bs and not bt:       return self._sTTF_sOTF(m, b)
            if bs and bt:           return self._sTTF_sTTF(m, b)
            if not bs and not bt:   return self._sTTF_vOTF(m, b)
            if not bs and bt:       return self._sTTF_vTTF(m, b)
        if not ms and not mt:
            if bs and not bt:       return self._vOTF_sOTF(m, b)
            if bs and bt:           return self._vOTF_sTTF(m, b)
            if not bs and not bt:   return self._vOTF_vOTF(m, b)
            if not bs and bt:       return self._vOTF_vTTF(m, b)
        if not ms and mt:
            if bs and not bt:       return self._vTTF_sOTF(m, b)
            if bs and bt:           return self._vTTF_sTTF(m, b)
            if not bs and not bt:   return self._vTTF_vOTF(m, b)
            if not bs and bt:       return self._vTTF_vTTF(m, b)

    def _do_merge(self, m, b, variable_source=None):
        """合并一级 (可变打底: 先试跨设计空间合成, 失败回退默认实例合并)。

        Args:
            m: 主字体
            b: 打底字体 (原始对象; 可变时由本函数决定如何实例化)
            variable_source: 打底的可变字体 (启用合成/增量搬运时使用)
        """
        if variable_source is not None and self.compose_variations:
            try:
                return self._do_merge_once(m, b, variable_source, compose=True)
            except Exception as e:
                print(f"  [合成] 回退到默认实例合并: {e}")
        return self._do_merge_once(m, b, variable_source, compose=False)

    def _do_merge_once(self, m, b, variable_source=None, compose=False):
        plan = None
        if variable_source is not None:
            if compose:
                from ..format.variation_compose import instance_at_merged_default
                m = copy.deepcopy(m)
                # UPM 先归一: 后续所有增量/轮廓都按主字体 UPM 表达
                variable_source = _normalize_upm(m, variable_source)
                plan = _apply_axis_plan(m, variable_source, self.compose_range,
                                        self.avar_mode, self.compose_fit)
                if plan is None:
                    raise RuntimeError("轴空间无法规划 (见 compose_range 参数)")
                b = instance_at_merged_default(variable_source, plan["fvar"])
                if self.compose_layout:
                    _transfer_base_layout_once(b, variable_source, plan)
                if self.compose_variations:
                    _compose_cff2_base(m, b, variable_source, plan)
                for tag, norm, lo, hi in _collapsing_flats(plan):
                    print(f"  [告警] 合并 avar 的轴 {tag} 把用户区间 "
                          f"[{lo:.0f}, {hi:.0f}] 压成归一化点 {norm:.3f}: "
                          f"该区间无法逐点等价 (可改用 avar_mode=2)")
            elif is_variable(b):
                # 旧路径: 轴并集 (仅轴空间) + 打底按自身默认实例化
                from ..format.axis_mapping import avar_segments, fvar_triples
                _force_load_axis_tables(m)
                before_axes, before_avar = fvar_triples(m), avar_segments(m)
                m = self._axis_union(m, variable_source)
                _reparametrize_main_after_union(m, before_axes, before_avar)
                if not axes_compatible(m, variable_source):
                    variable_source = None
                b = variable_to_static(b)
        # ── 预处理 ──
        b = _normalize_upm(m, b)

        from ..format.cid_convert import _is_cid_font, ensure_cid_format, cid_to_name
        m_is_cid = _is_cid_font(m)
        b_is_cid = _is_cid_font(b)

        if m_is_cid and b_is_cid:
            # 双 CID: 仿 UFO CIDMap 重映射 — 打底 CID 偏移, 直接复制 CharString
            print("  [CID消歧] 双CID字体, 使用CID偏移+直接CharString复制")
            from ..format.cid_merge import cid_ufo_style_merge
            result = cid_ufo_style_merge(m, b)
            # cid_ufo_style_merge 已包含完整合并+save→reload, 直接返回
            # 但还需处理 OT 特性: 主字体优先
            for tag in ("GSUB", "GPOS", "GDEF"):
                if tag not in result and tag in m:
                    result[tag] = copy.deepcopy(m[tag])
            return result
        elif m_is_cid and not b_is_cid:
            # 主 CID + 打底 name-keyed: 打底转 CID → 走双 CID 路径 (主字体的 CID 结构保留)
            print("  [CID归一] 主字体为 CID: 打底 name→CID, 走双 CID 合并")
            from ..format.cid_convert import ensure_cid_format
            # 打底若是 glyf/TTF: 先转 CFF (cid_ufo_style_merge 是 CFF 专用)
            if not is_cff(b):
                b = convert_font_format(b, to_cff=True)
            _b = ensure_cid_format(b)
            if _b is not b:
                b = _b
            from ..format.cid_merge import cid_ufo_style_merge
            result = cid_ufo_style_merge(m, b)
            for tag in ("GSUB", "GPOS", "GDEF"):
                if tag not in result and tag in m:
                    result[tag] = copy.deepcopy(m[tag])
            return result
        elif not m_is_cid and b_is_cid:
            if "CFF2" in m:
                # 主 CFF2 (无 ROS, FD 体系保留): 打底 CID CFF 直接转 CFF2, 保留 FDArray
                print("  [CID归一] 主字体为CFF2: 打底 CID CFF→CFF2 (FD 保留, inject 时重映射)")
                from fontTools.cffLib.CFFToCFF2 import convertCFFToCFF2
                _b = copy.deepcopy(b)
                _b["CFF "].cff.desubroutinize()
                convertCFFToCFF2(_b)
                b = _b
            else:
                # 主是 name-keyed CFF: 打底转 name-keyed (避免主被强制 CID 后 FD 冲突)
                print("  [CID归一] 打底字体 CID→name (输出统一为 name-keyed)")
                b = cid_to_name(b)

        if is_cff(m) != is_cff(b):
            print("  [转换] 轮廓格式不同，自动转换打底字体...")
            b = convert_font_format(b, to_cff=is_cff(m))
        if is_cff(m) and is_cff(b):
            # CFF 版本对齐: 主 CFF2 参数化, 打底静态 CFF → 先转 CFF2 才能注入
            if "CFF2" in m and "CFF " in b:
                print("  [转换] CFF 版本对齐: 打底 CFF → CFF2 (配合主字体)")
                from fontTools.cffLib.CFFToCFF2 import convertCFFToCFF2
                _base = copy.deepcopy(b)
                _base["CFF "].cff.desubroutinize()
                convertCFFToCFF2(_base)
                b = _base
            elif "CFF " in m and "CFF2" in b:
                print("  [转换] CFF 版本对齐: 打底 CFF2 → CFF (配合主字体)")
                from fontTools.cffLib.CFF2ToCFF import _convertCFF2ToCFF
                from fontTools.ttLib.tables.C_F_F_ import table_C_F_F_
                _base = copy.deepcopy(b)
                _convertCFF2ToCFF(_base["CFF2"].cff, _base)
                cff_data = _base["CFF2"].cff
                del _base["CFF2"]
                cff_table = table_C_F_F_("CFF ")
                cff_table.cff = cff_data
                _base["CFF "] = cff_table
                b = _base

        # ── 冲突检测与合并 ──
        # 自动命名字形 (post 3.0 的 glyphNNNNN) 跨字体同名但不同源: 改名后加入
        alias = plan_alias(m, b)
        if alias:
            from .glyph_rename import renamed_copy
            print(f"  [改名] {len(alias)} 个自动命名字形重名, 加别名后加入")
            b = renamed_copy(b, alias)
        cf = resolve_conflicts(m, b)
        print(f"  [冲突] {len(cf)} 个字形")
        mn = set(m.getGlyphOrder())
        to_add = [gn for gn in b.getGlyphOrder()
                  if gn not in cf and gn not in mn]
        print(f"  [新增] {len(to_add)} 个字形")
        if not to_add:
            reason = _diagnose_empty_merge(m, b, cf)
            print(f"  [提示] 无新增字形 — {reason}")
            return copy.deepcopy(m)

        CHUNK_SIZE = 5000
        if len(to_add) > CHUNK_SIZE:
            return self._chunked_merge(m, b, to_add, CHUNK_SIZE,
                                       variable_source, plan)

        try:
            result = merge_glyphs_via_ttx(m, b, to_add)
        except Exception as e:
            print(f"  [合并失败] {e}")
            return copy.deepcopy(m)
        print(f"  合并后字形: {len(result.getGlyphOrder())}")
        # 可变数据收尾: 合成自检失败要向上抛 (由 _do_merge 回退到旧路径),
        # 不能在这里被当成"字形合并失败"吞掉
        added_now = _finish_variable_merge(self, result, m, b, variable_source,
                                           plan)
        # 合并打底 OT 特性 (修剪到仅与保留字形相关, 冲突以主为准)
        _merge_base_layout_once(result, b, to_add)
        return result

    def _chunked_merge(self, m, b, to_add, chunk_size, variable_source=None,
                       plan=None):
        """分块合并: 将打底字体按 chunk_size 拆分, 逐块合并到主字体"""
        chunks = [to_add[i:i+chunk_size] for i in range(0, len(to_add), chunk_size)]
        print(f"  [分块] {len(chunks)} 块, 每块 ≤{chunk_size} 字形")
        current = m
        for i, chunk in enumerate(chunks):
            print(f"    块 {i+1}/{len(chunks)}: {len(chunk)} 字形...", end=" ", flush=True)
            try:
                current = merge_glyphs_via_ttx(current, b, chunk)
                print(f"→ {len(current.getGlyphOrder())} 字形")
            except Exception as e:
                print(f"失败: {e}")
                return current if len(current.getGlyphOrder()) > len(m.getGlyphOrder()) else copy.deepcopy(m)
        _finish_variable_merge(self, current, m, b, variable_source, plan)
        # 分块完成后统一合并打底 OT 特性一次
        _merge_base_layout_once(current, b, to_add)
        return current

    # ---- 静态+静态 ----
    def _sOTF_sOTF(self, m, b): return self._do_merge(m, b)
    def _sTTF_sTTF(self, m, b): return self._do_merge(m, b)
    def _sOTF_sTTF(self, m, b):
        self.ask("sOTF_sTTF", "导出为 TTF 还是 OTF？", ["OTF", "TTF"])
        return self._do_merge(m, b)
    def _sTTF_sOTF(self, m, b):
        self.ask("sTTF_sOTF", "导出为 TTF 还是 OTF？", ["TTF", "OTF"])
        return self._do_merge(m, b)

    # ---- 静态+可变 ----
    def _sOTF_vOTF(self, m, b): return self._do_merge(m, variable_to_static(b))
    def _sOTF_vTTF(self, m, b): return self._do_merge(m, variable_to_static(b))
    def _sTTF_vOTF(self, m, b): return self._do_merge(m, variable_to_static(b))
    def _sTTF_vTTF(self, m, b): return self._do_merge(m, variable_to_static(b))

    # ---- 可变OTF为主+静态打底 ----
    def _vOTF_sOTF(self, m, b):
        fmt = self.ask("vOTF_sOTF", "导出为可变/静态？", ["可变", "静态"])
        if fmt == "静态": return self._do_merge(variable_to_static(m), b)
        return self._do_merge(m, b)
    def _vOTF_sTTF(self, m, b):
        fmt = self.ask("vOTF_sTTF", "导出为可变/静态？", ["可变", "静态"])
        if fmt == "静态":
            self.ask("vOTF_sTTF2", "TTF/OTF？", ["TTF", "OTF"])
            return self._do_merge(variable_to_static(m), b)
        return self._do_merge(m, b)

    # ---- 可变TTF为主+静态打底 ----
    def _vTTF_sOTF(self, m, b):
        fmt = self.ask("vTTF_sOTF", "导出为可变/静态？", ["可变", "静态"])
        if fmt == "静态":
            self.ask("vTTF_sOTF2", "TTF/OTF？", ["TTF", "OTF"])
            return self._do_merge(variable_to_static(m), b)
        return self._do_merge(m, b)
    def _vTTF_sTTF(self, m, b):
        fmt = self.ask("vTTF_sTTF", "导出为可变/静态？", ["可变", "静态"])
        if fmt == "静态": return self._do_merge(variable_to_static(m), b)
        return self._do_merge(m, b)

    # ---- 可变+可变 ----
    # 打底可变时把**原始对象**交给 _do_merge: 它先试跨设计空间合成
    # (必要处插值出新 master), 失败再回退到"按打底默认实例化"。
    def _vOTF_vOTF(self, m, b):
        return self._do_merge(m, b, variable_source=b)
    def _vOTF_vTTF(self, m, b):
        self.ask("vOTF_vTTF", "OTF/TTF？", ["OTF", "TTF"])
        return self._do_merge(m, b, variable_source=b)
    def _vTTF_vOTF(self, m, b):
        self.ask("vTTF_vOTF", "TTF/OTF？", ["TTF", "OTF"])
        return self._do_merge(m, b, variable_source=b)
    def _vTTF_vTTF(self, m, b):
        return self._do_merge(m, b, variable_source=b)

    @staticmethod
    def _axis_union(m, b):
        """主 VF 轴空间与打底 VF 轴空间取并集 (在原始 VF 上操作)"""
        if is_variable(m) and is_variable(b):
            from ..format.vf_axes import union_axes
            union_axes(m, b)
        return m


def _merge_base_layout_once(result, base_font, to_add):
    """在最终合并结果上统一做一次打底 OT 特性合并 (避免分块重复追加)"""
    try:
        from ..tables.ot_merge import merge_ot_features
        merge_ot_features(result, base_font, list(to_add))
    except Exception as e:
        print(f"  [OT合并] 跳过打底布局合并: {e}")
