# -*- coding: utf-8 -*-
"""同源分片并集合并 — merge_subsets()

场景: 一个可变字体被 pyftsubset 按 unicode-range 切成 N 个分片 (webfont
@font-face 分片), 现在要把它们**保特性**地并回一个可变字体。

为什么不能走 merge_two: 可变×可变路径会 variable_to_static(打底) 并走 TTX
往返, 打底字形因此丢失 gvar/HVAR/VVAR 与布局特性 (vert/vrt2/kern/mark);
而且 post 3.0 字体经 TTX 往返后字形名会按 cmap 重算, 注入的字形名全部错位
(保存时报 dangling cmap)。同源分片**不需要**实例化、不需要轴并集 ——
各分片的 fvar/gvar region 完全一致, 逐字形并集即可完整保留可变性与特性。

算法:
  1  主分片 = subsets[0]; 强制加载逐字形表, glyf.ensureDecompiled()
  2  逐个分片: 算改名表 (自动名 glyphNNNNN / 被布局引用的重名 → 别名;
     其余重名 = 同源字形 → 去重)
  3  逐字形追加 glyf (复合组件同步改名) / hmtx / vmtx / gvar
  4  cmap 按 (platformID, platEncID) 并集, 缺子表则新建
  5  GDEF: GlyphClassDef / MarkGlyphSets / MarkAttachClassDef / AttachList
     / LigCaretList 并集; VarStore region 并集 + VarData 拼接 + 索引重定位
  6  GSUB/GPOS: 各分片 lookup 全部追加 + 字形名 remap + VariationIndex 重定位
     + 同 tag FeatureRecord 并成一条 + ScriptList/LangSys 并集
  7  按码位重排 GID (format 4 才能装得下, 同时改善 loca 局部性)
  8  修复 OpenType 排序不变量 (resort_layout)
  9  HVAR 由合并后 gvar 幽灵点重建; VVAR VarStore 并集 + DeltaSetIndexMap 重定位
  10 name 表补全 (16/17/25 + 实例 PS 名); head.flags 清 woff2 残留位
  11 重算 head/hhea/vhea/maxp/OS/2 度量

轮廓支持:
  * glyf: 逐字形复制 glyf/hmtx/vmtx/gvar, HVAR 由 gvar 幽灵点重建;
  * CFF2: 逐字形复制 CharStrings + FDSelect, FDArray 按内容去重并集
    (blend/vsindex 原样保留), HVAR/VVAR 做 VarStore 并集 + 索引重定位。
    要求各分片共享同一 CFF2 VarStore / GlobalSubrs 结构 (见
    format/cff2_union.py); 结构被重构过时明确报错而不是产出坏字体。

特性:
  * GSUB/GPOS 同 tag feature 并集 + ScriptList 并入 + FeatureVariations
    索引重写; GDEF 字类/MarkGlyphSets/VarStore 并集, VariationIndex 重定位。

用法:
    from FontMerger import merge_subsets
    merge_subsets(subset_paths, out_path="Merged.ttf", tag="ja")
"""
import copy
import os

from fontTools.ttLib import newTable
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.ttLib.tables.otTables import NO_VARIATION_INDEX

from .glyph_rename import alias_name
from ..format.cff2_union import (FDUnion, IncompatibleCFF2Error,
                                 check_cff2_compatible,
                                 copy_glyphs as copy_cff2_glyphs,
                                 sync_glyph_order)
from ..tables.layout_union import (LayoutUnion, MarkGlyphSetUnion,
                                   layout_glyph_names, remap_glyph_names,
                                   resort_layout)
from ..tables.varstore import VarStoreUnion
from ..utils.detect import is_auto_glyph_name, is_cff, is_same_source, type_label
from ..utils.save import save_font, default_flavor_for

#: 需要强制加载的逐字形表 (改字形序之前必须先读出来)
_PER_GLYPH_TABLES = ("glyf", "hmtx", "vmtx", "gvar", "cmap", "HVAR", "VVAR")
_PER_GLYPH_TABLES_CFF2 = ("CFF2", "hmtx", "vmtx", "cmap", "HVAR", "VVAR")

#: cmap 子表格式 → 可容纳的最大码位
_CMAP_LIMITS = {0: 0xFF, 4: 0xFFFF, 6: 0xFFFF, 12: 0x10FFFF}

#: VVAR / HVAR 里按字形索引的 DeltaSetIndexMap
_VVAR_MAPS = ("AdvHeightMap", "TsbMap", "BsbMap", "VOrgMap")
_HVAR_MAPS = ("AdvWidthMap", "LsbMap", "RsbMap")


def _copy_cmap_subtable(dst_font, src_st, fmt, sub_idx):
    """在 dst 里找/建一个与 src_st 同 (platformID, platEncID) 的子表"""
    key = (src_st.platformID, src_st.platEncID)
    st = sub_idx.get(key)
    if st is None:
        st = CmapSubtable.newSubtable(fmt)
        st.platformID = src_st.platformID
        st.platEncID = src_st.platEncID
        st.language = getattr(src_st, "language", 0)
        st.cmap = {}
        dst_font["cmap"].tables.append(st)
        sub_idx[key] = st
    return st


class SameSourceSubsetMerger:
    """把同一可变字体的多个 unicode-range 分片并成一个可变字体"""

    def __init__(self, tag="s", verbose=True):
        self.tag = tag or "s"
        self.verbose = verbose
        self.var_store = VarStoreUnion()      # GDEF ItemVariationStore
        self.vvar_store = VarStoreUnion()     # VVAR 自己的 ItemVariationStore
        self.hvar_store = VarStoreUnion()     # HVAR 自己的 ItemVariationStore
        self.fd_union = None                  # CFF2: FDArray 并集
        self.cff2 = False
        self.gdef_class_defs = {}
        self.mark_attach_class_defs = {}
        self.mark_union = MarkGlyphSetUnion()
        self.attach_list = None
        self.lig_caret_list = None
        self.layout = {"GSUB": LayoutUnion("GSUB"), "GPOS": LayoutUnion("GPOS")}
        self.subset_renames = []
        self.subset_orders = []
        self.subset_labels = []
        self.final_order = []
        self.stats = {"subsets": 0, "glyphs_added": 0, "aliased": 0,
                      "deduplicated": 0, "cmap_added": 0, "cmap_conflicts": 0,
                      "cmap_subtables": 0, "features": {},
                      "final_glyphs": 0}

    def log(self, *args):
        if self.verbose:
            print(*args, flush=True)

    # ------------------------------------------------------------------
    # CFF2
    # ------------------------------------------------------------------
    @staticmethod
    def _check_cff2(subsets):
        """CFF2 分片: 必须是同源结构 (FDArray/VarStore/GlobalSubrs 一致)。

        CFF2 的 blend/vsindex 与 FDSelect 都是**索引**, 分片结构被重构过
        (如 pyftsubset 剪过 FDArray/VarData) 就必须做基址重定位才能并集 ——
        那属于另一条实现路径, 这里明确拒绝, 避免产出坏字体。
        """
        for f in subsets:
            if "CFF2" not in f:
                raise NotImplementedError(
                    "merge_subsets: CFF/CFF2 混合或纯 CFF1 分片暂不支持")
        for i, f in enumerate(subsets[1:], 1):
            ok, reason = check_cff2_compatible(subsets[0], f)
            if not ok:
                raise NotImplementedError(
                    "merge_subsets: 分片 %d 无法零重定位并集 — %s" % (i, reason))

    @staticmethod
    def _copy_cff2_glyphs(merged, base, pairs, fd_map=None):
        """复制打底 CFF2 字形 (CharStrings + FDSelect), 返回复制的最终名。"""
        return copy_cff2_glyphs(merged, base, pairs, fd_map)

    # ------------------------------------------------------------------
    # 改名表
    # ------------------------------------------------------------------
    @staticmethod
    def rename_map(base, main_names, tag, index, layout_names=frozenset()):
        """旧名 → 新名 (只含需要**别名**的字形)。

        重名有两种完全不同的含义:

        * 自动名 (glyphNNNNN, post 3.0): 不同字体里的同名是**不同字形**,
          一律加别名, 保留该分片的全部字形;
        * cmap 派生的名字 (uniXXXX / AGL 名) 已在主字体中: 是**同源字形**
          (少数被两个分片共享的码位)。若该分片布局表引用了它, 仍要保留一份
          —— 这样该分片引用到的字形全部落在"追加块"里, Coverage 顺序天然
          保持; 否则直接去重 (引用回落到主字体的同形字形)。
        """
        ren = {}
        taken = set(main_names)
        for gn in base.getGlyphOrder():
            if gn == ".notdef":
                continue
            if is_auto_glyph_name(gn):
                new = alias_name(gn, taken, tag, index)
                ren[gn] = new
                taken.add(new)
            elif gn in main_names and gn in layout_names:
                new = alias_name(gn, taken, tag, index)
                ren[gn] = new
                taken.add(new)
        return ren

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def merge(self, subsets, labels=None):
        """并集合并 subsets (list[TTFont]); subsets[0] 作为基底会被就地修改"""
        subsets = list(subsets)
        if not subsets:
            raise ValueError("merge_subsets: 至少需要 1 个分片")
        self.cff2 = is_cff(subsets[0])
        if self.cff2:
            self._check_cff2(subsets)
        if len(subsets) > 1 and not is_same_source(subsets):
            raise ValueError(
                "merge_subsets: 输入不是同源分片 (fvar 轴空间或轮廓格式不一致); "
                "异源字体请用 merge_two()/merge_fonts()")
        self.subset_labels = list(labels) if labels else [str(i) for i in range(len(subsets))]

        merged = subsets[0]
        for tag in (_PER_GLYPH_TABLES_CFF2 if self.cff2 else _PER_GLYPH_TABLES):
            if tag in merged:
                merged[tag]
        if not self.cff2:
            # 复合字形惰性持有组件 GID: 必须在字形序改变之前展开
            merged["glyf"].ensureDecompiled()
        else:
            self.fd_union = FDUnion(merged["CFF2"].cff.topDictIndex[0])

        merged_order = list(merged.getGlyphOrder())
        merged_names = set(merged_order)
        merged_cmap = {}
        for st in merged["cmap"].tables:
            if hasattr(st, "cmap") and st.cmap:
                merged_cmap.update(st.cmap)
        merged_sub_idx = {}
        for st in merged["cmap"].tables:
            if hasattr(st, "cmap") and st.cmap is not None:
                merged_sub_idx.setdefault((st.platformID, st.platEncID), st)

        for index, base in enumerate(subsets):
            if index == 0:
                ren = {gn: gn for gn in base.getGlyphOrder()}
                to_add = []
            else:
                if not self.cff2 and "glyf" in base:
                    # 展开打底字形 (组件名按**打底自己的**字形序解析)
                    base["glyf"].ensureDecompiled()
                ren = self.rename_map(base, merged_names, self.tag, index,
                                      layout_glyph_names(base))
                self.stats["aliased"] += len(ren)
                self.stats["deduplicated"] += sum(
                    1 for gn in base.getGlyphOrder()
                    if gn != ".notdef" and gn not in ren and gn in merged_names)
                to_add = [gn for gn in base.getGlyphOrder()
                          if ren.get(gn, gn) not in merged_names]
            self.subset_renames.append(ren)
            self.subset_orders.append(list(base.getGlyphOrder()))
            cmap_before = self.stats["cmap_added"]

            # GDEF 先做: GPOS 的 VariationIndex 依赖本分片的 VarData 基址
            var_offset = 0
            mark_set_remap = ()
            if "GDEF" in base:
                var_offset, mark_set_remap = self._merge_gdef(base["GDEF"].table, ren)

            # ---- 轮廓 (glyf 对象复制 / CFF2 对象复制) ----
            pairs = []          # (打底字形名, 合并后字形名)
            if self.cff2:
                for old in to_add:
                    new = ren.get(old, old)
                    if new not in merged_names:
                        pairs.append((old, new))
                if pairs:
                    fd_map = self.fd_union.add(base["CFF2"].cff.topDictIndex[0])
                    self._copy_cff2_glyphs(merged, base, pairs, fd_map)
            else:
                for old in to_add:
                    new = ren.get(old, old)
                    if new in merged_names:
                        continue
                    glyph = copy.deepcopy(base["glyf"][old])
                    if glyph.isComposite():
                        for comp in glyph.components:
                            comp.glyphName = ren.get(comp.glyphName,
                                                     comp.glyphName)
                    # 直接写 glyphs 字典: glyf.__setitem__ 会顺手 append 到
                    # glyf.glyphOrder —— 而该列表就是 merged_order 本体 (setGlyphOrder
                    # 传的是引用), 会与本循环的 append 重复。末尾统一 setGlyphOrder。
                    merged["glyf"].glyphs[new] = glyph
                    if "gvar" in base and "gvar" in merged:
                        variations = base["gvar"].variations.get(old)
                        if variations:
                            merged["gvar"].variations[new] = copy.deepcopy(variations)
                    pairs.append((old, new))

            # ---- 度量 / 变体映射 (两条路径共用) ----
            added_names = set()
            for old, new in pairs:
                added_names.add(new)
                merged_order.append(new)
                merged_names.add(new)
                merged["hmtx"][new] = base["hmtx"][old]
                if "vmtx" in merged:
                    # 主字体有 vmtx 时每个字形都必须有纵向度量, 否则编译期 KeyError
                    if "vmtx" in base and old in base["vmtx"].metrics:
                        merged["vmtx"][new] = base["vmtx"][old]
                    else:
                        merged["vmtx"][new] = (0, 0)

            # HVAR/VVAR: 本分片的 VarData 基址 + 逐个字形重定位
            vvar_offset = 0
            if "VVAR" in base and "VVAR" in merged:
                vvar_offset = self.vvar_store.add(base["VVAR"].table.VarStore)
            hvar_offset = 0
            if "HVAR" in base and "HVAR" in merged:
                hvar_offset = self.hvar_store.add(base["HVAR"].table.VarStore)

            self._merge_cmap(merged, base, merged_sub_idx, ren, merged_names,
                             merged_cmap)
            if index > 0 and added_names:
                self._merge_variation_maps(merged, base, ren, vvar_offset,
                                           hvar_offset, added_names)

            for table_tag, state in self.layout.items():
                if table_tag in base:
                    state.add_from(base[table_tag].table, ren,
                                   var_offset=var_offset,
                                   mark_set_remap=mark_set_remap)

            self.stats["glyphs_added"] += len(added_names)
            merged.setGlyphOrder(merged_order)
            self.log(f"  [{index:3d}] +{len(added_names):4d} 字形, cmap +"
                     f"{self.stats['cmap_added'] - cmap_before}")

        merged.setGlyphOrder(merged_order)

        # 布局表必须在字形重排**之前**建好 (add_from 已经按追加顺序排好)
        for table_tag, state in self.layout.items():
            table = state.finalize()
            if table is not None:
                wrapper = newTable(table_tag)
                wrapper.table = table
                merged[table_tag] = wrapper
            elif table_tag in merged:
                del merged[table_tag]

        # 按码位重排 GID: format 4 才能装下, 且 loca/glyf 局部性更好
        self._reorder_by_codepoint(merged, merged_cmap)
        self._finalize_gdef(merged)
        # GDEF 是重建的 (AttachList/LigCaretList 来自暂存副本), 重新按新字形序排序
        resort_layout(merged)
        if self.cff2:
            # CFF2 没有 charset 表: 编译按 top.charset 顺序取 CharStrings,
            # charset / FDSelect 必须与最终字形序一致
            sync_glyph_order(merged)
        self._harmonize_cmap(merged, merged_cmap)
        merged["cmap"].tables.sort(key=lambda st: (st.platformID, st.platEncID))
        self.stats["cmap_subtables"] = len(merged["cmap"].tables)

        self._finalize_variation_maps(merged)

        if "gvar" in merged and "fvar" in merged:
            from fontTools.varLib.hvar import add_HVAR
            add_HVAR(merged)

        self._recalc_metrics(merged)
        self.final_order = list(merged.getGlyphOrder())
        self.stats["subsets"] = len(subsets)
        self.stats["final_glyphs"] = len(self.final_order)
        for tag, state in self.layout.items():
            self.stats["features"][tag] = sorted(
                {fr.FeatureTag for fr in state.feature_records})
        return merged

    # ------------------------------------------------------------------
    # cmap
    # ------------------------------------------------------------------
    def _merge_cmap(self, merged, base, merged_sub_idx, ren, merged_names,
                    merged_cmap):
        for base_st in base["cmap"].tables:
            if not (hasattr(base_st, "cmap") and base_st.cmap):
                continue
            for cp, old in base_st.cmap.items():
                new = ren.get(old, old)
                if new not in merged_names:
                    continue
                mst = _copy_cmap_subtable(merged, base_st, base_st.format,
                                          merged_sub_idx)
                if cp in mst.cmap:
                    if mst.cmap[cp] != new:
                        self.stats["cmap_conflicts"] += 1
                    continue
                mst.cmap[cp] = new
                if cp not in merged_cmap:
                    merged_cmap[cp] = new
                    self.stats["cmap_added"] += 1

    @staticmethod
    def _harmonize_cmap(merged, cmap_map):
        """每个 Unicode 子表都要覆盖合并后的全部码位 (按其格式上限)。

        客户端只取 (3,10) format 12 时也必须能找到只出现在别的分片 format 4
        里的 BMP 码位, 反之亦然。
        """
        for st in merged["cmap"].tables:
            fmt = getattr(st, "format", None)
            if fmt not in _CMAP_LIMITS or not hasattr(st, "cmap") or st.cmap is None:
                continue
            if hasattr(st, "isUnicode") and not st.isUnicode():
                continue
            limit = _CMAP_LIMITS[fmt]
            st.cmap = {cp: gn for cp, gn in cmap_map.items() if cp <= limit}

    # ------------------------------------------------------------------
    # 字形重排
    # ------------------------------------------------------------------
    def _reorder_by_codepoint(self, merged, cmap_map):
        old_order = merged.getGlyphOrder()
        if "glyf" in merged:
            # 仍在惰性持有组件 GID 的字形, 趁当前字形序还有效先展开 (P5)
            merged["glyf"].ensureDecompiled()
        cp_of = {}
        for cp, gn in cmap_map.items():
            if gn not in cp_of or cp < cp_of[gn]:
                cp_of[gn] = cp
        cmap_glyphs = sorted(cp_of, key=lambda g: (cp_of[g], g))
        rest = [g for g in old_order if g not in cp_of and g != ".notdef"]
        new_order = [".notdef"] + cmap_glyphs + rest
        if len(new_order) != len(old_order) or len(set(new_order)) != len(old_order):
            raise AssertionError("字形重排丢失或重复了字形")
        merged.setGlyphOrder(new_order)
        resort_layout(merged)

    # ------------------------------------------------------------------
    # GDEF
    # ------------------------------------------------------------------
    def _merge_gdef(self, gdef, ren):
        """并入一个分片的 GDEF; 返回 (VarData 基址, MarkSet 索引重映射)"""
        if gdef.GlyphClassDef is not None:
            for gn, cls in (gdef.GlyphClassDef.classDefs or {}).items():
                self.gdef_class_defs.setdefault(ren.get(gn, gn), cls)
        if getattr(gdef, "MarkAttachClassDef", None) is not None:
            for gn, cls in (gdef.MarkAttachClassDef.classDefs or {}).items():
                self.mark_attach_class_defs.setdefault(ren.get(gn, gn), cls)
        # MarkGlyphSetsDef 并集 (共享 MarkGlyphSetUnion: 内容去重 + 索引重映射)
        mark_remap = self.mark_union.add(
            getattr(gdef, "MarkGlyphSetsDef", None), remap_name=ren)
        if getattr(gdef, "AttachList", None) is not None and self.attach_list is None:
            self.attach_list = copy.deepcopy(gdef.AttachList)
            remap_glyph_names(self.attach_list, ren)
        if (getattr(gdef, "LigCaretList", None) is not None
                and self.lig_caret_list is None):
            self.lig_caret_list = copy.deepcopy(gdef.LigCaretList)
            remap_glyph_names(self.lig_caret_list, ren)
        return self.var_store.add(getattr(gdef, "VarStore", None)), tuple(mark_remap)

    def _finalize_gdef(self, merged):
        if not (self.gdef_class_defs or self.mark_union
                or self.mark_attach_class_defs or self.attach_list
                or self.lig_caret_list or self.var_store.var_data):
            if "GDEF" in merged:
                del merged["GDEF"]
            return
        wrapper = newTable("GDEF")
        gdef = ot.GDEF()
        # Version 门槛: 1.2 才有 MarkGlyphSetsDef, 1.3 才有 VarStore
        if self.var_store.var_data:
            gdef.Version = 0x00010003
        elif self.mark_union:
            gdef.Version = 0x00010002
        else:
            gdef.Version = 0x00010000
        gdef.GlyphClassDef = None
        if self.gdef_class_defs:
            cd = ot.ClassDef()
            cd.classDefs = dict(self.gdef_class_defs)
            gdef.GlyphClassDef = cd
        gdef.AttachList = self.attach_list
        gdef.LigCaretList = self.lig_caret_list
        gdef.MarkAttachClassDef = None
        if self.mark_attach_class_defs:
            cd = ot.ClassDef()
            cd.classDefs = dict(self.mark_attach_class_defs)
            gdef.MarkAttachClassDef = cd
        order_index = {g: i for i, g in enumerate(merged.getGlyphOrder())}
        gdef.MarkGlyphSetsDef = self.mark_union.build(order_index)
        gdef.VarStore = self.var_store.build()
        wrapper.table = gdef
        merged["GDEF"] = wrapper

    # ------------------------------------------------------------------
    # VVAR
    # ------------------------------------------------------------------
    def _merge_variation_maps(self, merged, base, ren, vvar_offset, hvar_offset,
                              added_names):
        """把本分片 HVAR/VVAR 的 DeltaSetIndexMap 重定位后并入。

        DeltaSetIndexMap 的值是 (outer<<16)|inner: outer 是 VarData 序号,
        inner 是该 VarData 内的 region 序号。VarData 拼接后 outer 要加上
        本分片的基址偏移 (region 序号不变)。
        """
        for tag, attrs, offset in (("VVAR", _VVAR_MAPS, vvar_offset),
                                   ("HVAR", _HVAR_MAPS, hvar_offset)):
            if tag not in base or tag not in merged:
                continue
            src = base[tag].table
            dst = merged[tag].table
            for attr in attrs:
                smap = getattr(src, attr, None)
                dmap = getattr(dst, attr, None)
                if smap is None or dmap is None or not getattr(smap, "mapping", None):
                    continue
                for old, val in smap.mapping.items():
                    new = ren.get(old, old)
                    if new not in added_names:
                        continue
                    if val != NO_VARIATION_INDEX and offset:
                        val = (((val >> 16) + offset) << 16) | (val & 0xFFFF)
                    dmap.mapping[new] = val

    def _finalize_variation_maps(self, merged):
        """写回并集 VarStore, 并保证 DeltaSetIndexMap 覆盖全部字形。

        fontTools 的 VarIdxMap.preWrite 会按字形序逐个取值, 缺项直接 KeyError;
        没有增量的字形必须显式给 NO_VARIATION_INDEX。
        """
        order = merged.getGlyphOrder()
        for tag, attrs, union in (("VVAR", _VVAR_MAPS, self.vvar_store),
                                  ("HVAR", _HVAR_MAPS, self.hvar_store)):
            if tag not in merged:
                continue
            table = merged[tag].table
            if union.var_data:
                table.VarStore = union.build()
            for attr in attrs:
                m = getattr(table, attr, None)
                if m is None or not hasattr(m, "mapping"):
                    continue
                for gn in order:
                    m.mapping.setdefault(gn, NO_VARIATION_INDEX)

    # ------------------------------------------------------------------
    # 度量重算
    # ------------------------------------------------------------------
    @staticmethod
    def _recalc_metrics(font):
        from fontTools.otlLib.maxContextCalc import maxCtxFont

        if "glyf" not in font:
            return _recalc_metrics_cff(font)
        glyf = font["glyf"]
        head = font["head"]
        hmtx = font["hmtx"]
        order = font.getGlyphOrder()

        xmin = ymin = 1 << 30
        xmax = ymax = -(1 << 30)
        for gn in order:
            g = glyf[gn]
            if g.numberOfContours == 0:
                g.xMin = g.yMin = g.xMax = g.yMax = 0
                continue
            g.recalcBounds(glyf)
            xmin = min(xmin, g.xMin)
            ymin = min(ymin, g.yMin)
            xmax = max(xmax, g.xMax)
            ymax = max(ymax, g.yMax)
        if xmin <= xmax:
            head.xMin, head.yMin, head.xMax, head.yMax = xmin, ymin, xmax, ymax

        advance_max = 0
        min_lsb = 1 << 30
        min_rsb = 1 << 30
        x_max_extent = -(1 << 30)
        for gn in order:
            advance, lsb = hmtx[gn]
            g = glyf[gn]
            width = (g.xMax - g.xMin) if g.numberOfContours else 0
            advance_max = max(advance_max, advance)
            min_lsb = min(min_lsb, lsb)
            min_rsb = min(min_rsb, advance - lsb - width)
            x_max_extent = max(x_max_extent, lsb + width)
        hhea = font["hhea"]
        hhea.advanceWidthMax = advance_max
        hhea.minLeftSideBearing = min_lsb
        hhea.minRightSideBearing = min_rsb
        hhea.xMaxExtent = x_max_extent

        if "vhea" in font and "vmtx" in font:
            vhea = font["vhea"]
            adv_height_max = 0
            min_tsb = 1 << 30
            min_bsb = 1 << 30
            y_max_extent = -(1 << 30)
            for gn in order:
                adv, tsb = font["vmtx"][gn]
                g = glyf[gn]
                height = (g.yMax - g.yMin) if g.numberOfContours else 0
                adv_height_max = max(adv_height_max, adv)
                min_tsb = min(min_tsb, tsb)
                min_bsb = min(min_bsb, adv - tsb - height)
                y_max_extent = max(y_max_extent, tsb + height)
            vhea.advanceHeightMax = adv_height_max
            vhea.minTopSideBearing = min_tsb
            vhea.minBottomSideBearing = min_bsb
            vhea.yMaxExtent = y_max_extent

        if "OS/2" in font:
            os2 = font["OS/2"]
            os2.recalcAvgCharWidth(font)
            os2.recalcUnicodeRanges(font)
            codepoints = [cp for st in font["cmap"].tables
                          if hasattr(st, "cmap") and st.cmap for cp in st.cmap]
            if codepoints:
                os2.usFirstCharIndex = min(min(codepoints), 0xFFFF)
                os2.usLastCharIndex = min(max(codepoints), 0xFFFF)
            try:
                os2.usMaxContext = maxCtxFont(font)
            except Exception:
                pass
            try:
                os2.recalcCodePageRanges(font)
            except Exception:
                pass
        font["maxp"].recalc(font)

    # ------------------------------------------------------------------
    # 结果映射
    # ------------------------------------------------------------------
    def glyph_map(self):
        """{分片标签: {源字形名: 合并后 GID}} (重排之后)"""
        gid = {gn: i for i, gn in enumerate(self.final_order)}
        out = {}
        for index, label in enumerate(self.subset_labels):
            ren = self.subset_renames[index]
            entry = {}
            for gn in self.subset_orders[index]:
                target = ".notdef" if gn == ".notdef" else ren.get(gn, gn)
                if target in gid:
                    entry[gn] = gid[target]
            out[label] = entry
        return out


def _recalc_metrics_cff(font):
    """CFF/CFF2 字体的度量重算 (没有 glyf 表, 用 BoundsPen 取边界)"""
    from fontTools.otlLib.maxContextCalc import maxCtxFont
    from fontTools.pens.boundsPen import BoundsPen

    order = font.getGlyphOrder()
    glyph_set = font.getGlyphSet()
    head = font["head"]
    hmtx = font["hmtx"]

    bounds = {}
    xmin = ymin = 1 << 30
    xmax = ymax = -(1 << 30)
    for gn in order:
        pen = BoundsPen(glyph_set)
        try:
            glyph_set[gn].draw(pen)
        except Exception:
            pen.bounds = None
        b = pen.bounds
        bounds[gn] = b
        if b:
            xmin = min(xmin, b[0])
            ymin = min(ymin, b[1])
            xmax = max(xmax, b[2])
            ymax = max(ymax, b[3])
    if xmin <= xmax:
        head.xMin, head.yMin, head.xMax, head.yMax = xmin, ymin, xmax, ymax

    advance_max = 0
    min_lsb = 1 << 30
    min_rsb = 1 << 30
    x_max_extent = -(1 << 30)
    for gn in order:
        advance, lsb = hmtx[gn]
        b = bounds[gn]
        width = (b[2] - b[0]) if b else 0
        advance_max = max(advance_max, advance)
        min_lsb = min(min_lsb, lsb)
        min_rsb = min(min_rsb, advance - lsb - width)
        x_max_extent = max(x_max_extent, lsb + width)
    hhea = font["hhea"]
    hhea.advanceWidthMax = advance_max
    hhea.minLeftSideBearing = min_lsb
    hhea.minRightSideBearing = min_rsb
    hhea.xMaxExtent = x_max_extent

    if "vhea" in font and "vmtx" in font:
        vhea = font["vhea"]
        adv_height_max = 0
        min_tsb = 1 << 30
        min_bsb = 1 << 30
        y_max_extent = -(1 << 30)
        for gn in order:
            adv, tsb = font["vmtx"][gn]
            b = bounds[gn]
            height = (b[3] - b[1]) if b else 0
            adv_height_max = max(adv_height_max, adv)
            min_tsb = min(min_tsb, tsb)
            min_bsb = min(min_bsb, adv - tsb - height)
            y_max_extent = max(y_max_extent, tsb + height)
        vhea.advanceHeightMax = adv_height_max
        vhea.minTopSideBearing = min_tsb
        vhea.minBottomSideBearing = min_bsb
        vhea.yMaxExtent = y_max_extent

    if "OS/2" in font:
        os2 = font["OS/2"]
        os2.recalcAvgCharWidth(font)
        os2.recalcUnicodeRanges(font)
        codepoints = [cp for st in font["cmap"].tables
                      if hasattr(st, "cmap") and st.cmap for cp in st.cmap]
        if codepoints:
            os2.usFirstCharIndex = min(min(codepoints), 0xFFFF)
            os2.usLastCharIndex = min(max(codepoints), 0xFFFF)
        try:
            os2.usMaxContext = maxCtxFont(font)
        except Exception:
            pass
        try:
            os2.recalcCodePageRanges(font)
        except Exception:
            pass
    # maxp.recalc() 是 glyf 专用 (会取 glyf 表); CFF/CFF2 只需字形数
    font["maxp"].numGlyphs = len(order)


def load_subsets(subsets):
    """把 str/Path/TTFont 混合列表统一为 (TTFont 列表, 标签列表)"""
    from .. import load_font

    fonts, labels = [], []
    for i, item in enumerate(subsets):
        if isinstance(item, (str, os.PathLike)):
            fonts.append(load_font(str(item)))
            labels.append(os.path.basename(str(item)))
        else:
            fonts.append(item)
            labels.append("subset%03d" % i)
    return fonts, labels


def merge_subsets(subsets, out_path=None, tag="s", output_flavor=None,
                  complete_name_table=True, fix_head_flags=True,
                  verify=False, verbose=True, **verify_kwargs):
    """并集合并同一可变字体的多个 unicode-range 分片 (保 gvar/布局特性)。

    Args:
        subsets: 分片列表 (TTFont 或路径); 顺序即合并顺序, subsets[0] 是基底
                 (**会被就地修改** —— 作为合并结果继续追加字形)
        out_path: 输出路径; None = 只返回 TTFont 不落盘
        tag: 别名前缀 (自动名/重名别名形如 "ja007.glyph00123")
        output_flavor: None = 桌面 sfnt (.ttf/.otf); "woff2" = web 字体
        complete_name_table: 补 nameID 16/17/25 + 实例 PS 名 (Windows 必需)
        fix_head_flags: 清 head.flags 的 WOFF2 残留位 (bit 11)
        verify: 合并后跑 verify_merge() 自检; 不通过抛 AssertionError
        verify_kwargs: 透传给 verify_merge (如 axis_positions=…)

    Returns:
        合并后的 TTFont (flavor 已按 output_flavor 设置)
    """
    fonts, labels = load_subsets(subsets)
    merger = SameSourceSubsetMerger(tag=tag, verbose=verbose)
    merger.log(f"[并集] {len(fonts)} 个分片, 基底: {type_label(fonts[0])}, "
               f"{len(fonts[0].getGlyphOrder())} 字形")
    merged = merger.merge(fonts, labels=labels)

    if merged.get("maxp") is not None:
        merged["maxp"].numGlyphs = len(merged.getGlyphOrder())

    if complete_name_table:
        from ..tables.name_table import complete_vf_name_table
        complete_vf_name_table(merged)
    if fix_head_flags:
        from ..tables.head import fix_head_flags as _fix
        _fix(merged)

    if verify:
        from .verify import verify_merge
        report = verify_merge(fonts, merged, glyph_map=merger.glyph_map(),
                              **verify_kwargs)
        if not report["ok"]:
            raise AssertionError("merge_subsets 自检未通过: %s"
                                 % report.get("failures"))
        merger.log("[校验] 分片一致性自检通过")

    if out_path is not None:
        if output_flavor is None:
            output_flavor = default_flavor_for(out_path)
        _, magic = save_font(merged, out_path, flavor=output_flavor)
        merger.log(f"[保存] {out_path}  魔数 {magic!r}  "
                   f"{os.path.getsize(out_path) / 1e6:.1f} MB  "
                   f"{len(merged.getGlyphOrder())} 字形")

    merged.subset_merger = merger
    return merged
