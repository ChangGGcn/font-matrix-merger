# -*- coding: utf-8 -*-
"""可变字体 Axis 并集 (Logic.md D 组 Axis 处理)

规则:
  - Axis 上下限设为各字体上下限的并集 (min = 取更小, max = 取更大)
  - 打底字体有主字体没有的 Axis → 添加到主字体, 并为无该轴的
    字体 (的 Master) 的这项轴值设置为默认轴值
  - 已并入主字体的打底字形在新增轴上以默认值出现 (恒定, 不插值)

表同步: fvar (axes/instances), avar (新轴无映射则跳过), STAT,
       gvar/CFF2 varStore (新增轴无 delta 数据, 自动恒定)。
"""
import copy
from fontTools.ttLib import newTable
from fontTools.ttLib.tables._f_v_a_r import table__f_v_a_r
from fontTools.ttLib.tables._a_v_a_r import table__a_v_a_r


def get_axes_info(font):
    """现有轴: (axisTag, min, default, max, name) 列表"""
    if "fvar" not in font:
        return []
    return [(a.axisTag, a.minValue, a.defaultValue, a.maxValue, a.axisNameID)
            for a in font["fvar"].axes]


def union_axes(main_font, base_font):
    """把 base_font 的轴并入 main_font (Axis 并集)。

    Args:
        main_font: 主字体 (就地修改, 需含 fvar)
        base_font: 打底字体 (只读)

    Returns:
        added: 新增轴列表 [(axisTag, min, default, max)]
    """
    if "fvar" not in main_font:
        print("  [Axis并集] 主字体非可变, 跳过")
        return []
    if "fvar" not in base_font:
        print("  [Axis并集] 打底非可变, 跳过")
        return []

    main_axes = {a.axisTag: a for a in main_font["fvar"].axes}
    base_axes = {a.axisTag: a for a in base_font["fvar"].axes}

    added = []
    for atag, a in base_axes.items():
        if atag in main_axes:
            # 共有轴: 扩展上下限 (并集)
            m = main_axes[atag]
            lo = min(m.minValue, a.minValue)
            hi = max(m.maxValue, a.maxValue)
            if lo < m.minValue or hi > m.maxValue:
                print(f"  [Axis并集] {atag}: [{m.minValue},{m.maxValue}] → [{lo},{hi}]")
            m.minValue = lo
            m.maxValue = hi
            # 默认值保持主字体 (打底统一到主默认)
        else:
            # 独有轴: 加入主字体
            print(f"  [Axis并集] 新增 {atag}: [{a.minValue},{a.maxValue}] (默认 {a.defaultValue})")
            new_axis = copy.deepcopy(a)
            main_font["fvar"].axes.append(new_axis)
            added.append((atag, a.minValue, a.defaultValue, a.maxValue))
            # 补 STAT 轴条目
            _ensure_stat_axis(main_font, new_axis)

    # fvar 实例: 主实例保留; 新增轴上补默认值 (实例若无此轴值)
    _fill_default_axis_values(main_font, added)

    # 同步 varStore (CFF2/HVAR 等): 每个 Region 追加新轴 (恒定 0/0/0)
    if added:
        _extend_varstore_regions(main_font, len(added))
        _extend_avar_axes(main_font, len(added))

    return added


def _extend_avar_axes(font, n_new_axes):
    """avar 表: 新轴追加恒等 SegmentMap。

    注意 table__a_v_a_r.compile 是**按 fvar 轴序取 self.segments[axis]** 重建
    SegmentMap 的, 直接改 self.table.AxisSegmentMap 不生效 —— 必须同时写
    segments (否则保存时 KeyError: '<新轴 tag>')。
    """
    if "avar" not in font:
        return
    av = font["avar"]
    from fontTools.ttLib.tables.otTables import AxisSegmentMap
    av.table.AxisCount += n_new_axes
    for _ in range(n_new_axes):
        seg = AxisSegmentMap()
        seg.PositionMap = []
        av.table.AxisSegmentMap.append(seg)
    axes = [a.axisTag for a in font["fvar"].axes]
    for axis in axes[-n_new_axes:] if n_new_axes else []:
        av.segments.setdefault(axis, {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0})


def _extend_varstore_regions(font, n_new_axes):
    """给所有 varStore (CFF2 CharStrings.varStore, HVAR/VVAR) 的 Region 追加恒定轴。

    Region 的 VarRegionAxisList 按轴顺序排列; 新轴恒定时
    StartCoord=PeakCoord=EndCoord=0 (峰值 0 表示该区域在该轴无变化)。
    """
    # CFF2 的 VarStore
    if "CFF2" in font:
        try:
            td = font["CFF2"].cff.topDictIndex[0]
            vs = td.CharStrings.varStore.otVarStore
            _extend_region_list(vs.VarRegionList, n_new_axes)
        except Exception as e:
            print(f"  [Axis并集] CFF2 varStore 轴扩展失败: {e}")
    # 通用: 扫描已知可能带 VarStore 的表 (CFF2/HVAR/VVAR/MVAR/GDEF/...)
    # GDEF 的 VarStore (ItemVariationStore) 不直接引用字形, 可安全扩展
    handled = set()
    for tag in ("HVAR", "VVAR", "MVAR", "GDEF", "BASE", "JSTF"):
        if tag not in font:
            continue
        try:
            vs = font[tag].table.VarStore
            if vs is not None:
                _extend_region_list(vs.VarRegionList, n_new_axes)
                handled.add(tag)
        except Exception as e:
            print(f"  [Axis并集] {tag} varStore 轴扩展失败: {e}")
    if handled:
        print(f"  [Axis并集] varStore 轴扩展: {sorted(handled)}")


def _extend_region_list(region_list, n_new_axes):
    """向 VarRegionList 的每个 Region 追加 n_new_axes 个恒定轴坐标"""
    from fontTools.ttLib.tables.otTables import VarRegionAxis
    region_list.RegionAxisCount += n_new_axes
    for region in region_list.Region:
        for _ in range(n_new_axes):
            ax = VarRegionAxis()
            ax.StartCoord = 0.0
            ax.PeakCoord = 0.0
            ax.EndCoord = 0.0
            region.VarRegionAxis.append(ax)


def _fill_default_axis_values(font, added):
    """fvar 实例与 avar 在没有新增轴值的轴补默认值"""
    if "fvar" not in font or not added:
        return
    fvar = font["fvar"]
    axes_info = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue)
                 for a in fvar.axes}
    for inst in fvar.instances:
        # 已有轴值字典
        coords = getattr(inst, "coordinates", None)
        if coords is None:
            continue
        # 检查每个轴是否有坐标
        for atag, (lo, default, hi) in axes_info.items():
            if atag not in coords:
                # 补默认值 (来自 fvar 轴定义)
                coords[atag] = default
        inst.coordinates = coords


def _ensure_stat_axis(font, axis):
    """STAT 表补轴条目 (简化: 若 STAT 存在则添加 DesignAxisRecord)"""
    if "STAT" not in font:
        return
    stat = font["STAT"].table
    if getattr(stat, "DesignAxisRecord", None) is None:
        return
    # 检查是否已有该 tag
    existing = [r.AxisTag for r in stat.DesignAxisRecord.Axis]
    if axis.axisTag in existing:
        return
    from fontTools.ttLib.tables.otTables import AxisRecord
    ar = AxisRecord()
    ar.AxisTag = axis.axisTag
    # AxisNameID: 新增轴用 fvar 的名称
    ar.AxisNameID = axis.axisNameID
    ar.AxisOrdering = len(existing)
    stat.DesignAxisRecord.Axis.append(ar)


def axis_union_merge(main_font, base_font):
    """对外入口: 合并轴空间并返回新增轴"""
    return union_axes(main_font, base_font)
