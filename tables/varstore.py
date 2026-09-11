# -*- coding: utf-8 -*-
"""GDEF ItemVariationStore 并集

GPOS 的 Device(DeltaFormat=0x8000) 即 VariationIndex, 用 (outer, inner) 两级
索引引用 GDEF 的 ItemVariationStore: outer = VarData 序号, inner = 该 VarData
内的 region 序号。合并多个字体时必须:

  1. region 按 (StartCoord, PeakCoord, EndCoord) 去重取并集;
  2. 各字体的 VarData 依次拼接, 其 VarRegionIndex 重映射到并集 region 表;
  3. 返回该字体 VarData 的**基址偏移** — 该字体 GPOS/GSUB 里所有
     VariationIndex 的 outer 索引都要加上这个偏移 (见 offset_var_devices)。

不同分片的 region 集合常常不同 (3 区/4 区), 直接沿用打底索引会错位。
"""
import copy

from fontTools.ttLib.tables import otTables as ot


class VarStoreUnion:
    """多字体 ItemVariationStore 的并集构造器"""

    def __init__(self):
        self.region_keys = []
        self.region_index = {}
        self.var_data = []

    def add(self, var_store):
        """并入一个字体的 ItemVariationStore, 返回其 VarData 基址偏移。

        Args:
            var_store: otTables.VarStore 或 None

        Returns:
            该字体第一个 VarData 在并集中的下标 (无 varStore 时为 0)
        """
        if var_store is None:
            return 0
        offset = len(self.var_data)
        remap = []
        for region in var_store.VarRegionList.Region:
            key = tuple((a.StartCoord, a.PeakCoord, a.EndCoord)
                        for a in region.VarRegionAxis)
            idx = self.region_index.get(key)
            if idx is None:
                idx = len(self.region_keys)
                self.region_index[key] = idx
                self.region_keys.append(key)
            remap.append(idx)
        for vd in var_store.VarData:
            new_vd = copy.deepcopy(vd)
            new_vd.VarRegionIndex = [remap[i] for i in vd.VarRegionIndex]
            new_vd.VarRegionCount = len(new_vd.VarRegionIndex)
            self.var_data.append(new_vd)
        return offset

    def build(self):
        """构造并集 ItemVariationStore; 无数据返回 None"""
        if not self.var_data:
            return None
        vs = ot.VarStore()
        vs.Format = 1
        vrl = ot.VarRegionList()
        vrl.RegionAxisCount = len(self.region_keys[0]) if self.region_keys else 1
        vrl.RegionCount = len(self.region_keys)
        vrl.Region = []
        for key in self.region_keys:
            region = ot.VarRegion()
            region.VarRegionAxis = []
            for (start, peak, end) in key:
                axis = ot.VarRegionAxis()
                axis.StartCoord, axis.PeakCoord, axis.EndCoord = start, peak, end
                region.VarRegionAxis.append(axis)
            vrl.Region.append(region)
        vs.VarRegionList = vrl
        vs.VarData = self.var_data
        vs.VarDataCount = len(self.var_data)
        return vs

    def __bool__(self):
        return bool(self.var_data)
