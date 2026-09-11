# -*- coding: utf-8 -*-
"""GSUB/GPOS 并集合并

不同字体 (如同源分片) 各自带一份 GSUB/GPOS: 每个分片的 vert/vrt2/kern/mark
只覆盖自己的字形。合并时必须把各表的 lookup **全部追加**、字形名 remap、
lookup 索引重定位, 再把同 tag 的 FeatureRecord 并成一条 (多记录同 tag 虽合法,
但部分老引擎只取第一条)。

同时提供两个通用工具:
  * :func:`remap_glyph_names` — 深度重命名字形引用 (字形重排/改名后调用);
  * :func:`offset_var_devices` — GPOS VariationIndex 的 VarData outer 偏移;
  * :func:`resort_layout` — 字形顺序改变后修复 OpenType 排序不变量。
"""
import copy

from fontTools.ttLib.tables import otTables as ot


# --------------------------------------------------------------------------
# 通用对象级工具
# --------------------------------------------------------------------------
def remap_glyph_names(obj, ren, seen=None):
    """深度重命名 otTables 对象树里的字形引用。

    Args:
        obj: otTables 对象 / dict / list
        ren: {旧名: 新名}; 未列出的字符串原样保留 (所以对 tag / 数字属性安全)
        seen: 内部递归去重, 外部勿传
    """
    if seen is None:
        seen = set()
    if isinstance(obj, str) or id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(k, str) and k in ren:
                del obj[k]
                obj[ren[k]] = v
                k = ren[k]
            if isinstance(v, str):
                if v in ren:
                    obj[k] = ren[v]
            else:
                remap_glyph_names(v, ren, seen)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            if isinstance(v, str):
                if v in ren:
                    obj[i] = ren[v]
            else:
                remap_glyph_names(v, ren, seen)
    elif hasattr(obj, "__dict__"):
        for k, v in list(vars(obj).items()):
            if k.startswith("_"):
                continue
            if isinstance(v, str):
                if v in ren:
                    setattr(obj, k, ren[v])
            else:
                remap_glyph_names(v, ren, seen)


def offset_var_devices(obj, delta, seen=None):
    """把对象树里所有 VariationIndex (DeltaFormat=0x8000) 的 outer 索引加 delta"""
    if not delta:
        return
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, ot.Device):
        # 0xFFFF/0xFFFF = NO_VARIATION_INDEX (无变化), 不能加偏移
        if (getattr(obj, "DeltaFormat", 0) == 0x8000
                and (obj.StartSize, obj.EndSize) != (0xFFFF, 0xFFFF)):
            obj.StartSize += delta
        return
    if isinstance(obj, dict):
        for v in obj.values():
            offset_var_devices(v, delta, seen)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            offset_var_devices(v, delta, seen)
    elif hasattr(obj, "__dict__"):
        for k, v in vars(obj).items():
            if k.startswith("_"):
                continue
            offset_var_devices(v, delta, seen)


def layout_glyph_names(font):
    """字体 GSUB/GPOS/GDEF 引用到的全部字形名"""
    known = set(font.getGlyphOrder())
    found = set()

    def walk(obj, seen):
        if isinstance(obj, str):
            if obj in known:
                found.add(obj)
            return
        if id(obj) in seen:
            return
        seen.add(id(obj))
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and k in known:
                    found.add(k)
                walk(v, seen)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v, seen)
        elif hasattr(obj, "__dict__"):
            for k, v in vars(obj).items():
                if k.startswith("_"):
                    continue
                walk(v, seen)

    for tag in ("GSUB", "GPOS", "GDEF"):
        if tag in font:
            walk(font[tag].table, set())
    return found


# --------------------------------------------------------------------------
# 排序不变量 (P4)
# --------------------------------------------------------------------------
_COVERAGE_ATTRS = ("Coverage", "MarkCoverage", "BaseCoverage", "LigatureCoverage",
                   "Mark1Coverage", "Mark2Coverage", "BacktrackCoverage",
                   "InputCoverage", "LookAheadCoverage")


def sort_coverage_with(cov, arrays, order_index):
    """按新字形顺序排序 Coverage 及其并行数组 (PairSet/MarkRecord/…)"""
    if cov is None or not getattr(cov, "glyphs", None):
        return
    idx = sorted(range(len(cov.glyphs)),
                 key=lambda i: order_index.get(cov.glyphs[i], 1 << 30))
    cov.glyphs = [cov.glyphs[i] for i in idx]
    for arr in arrays:
        if arr is None:
            continue
        arr[:] = [arr[i] for i in idx]


def _fix_subtable_order(st, order_index):
    """修复单个 lookup 子表的 Coverage / 并行数组排序"""
    if st is None:
        return
    cls = type(st).__name__
    if cls in ("ExtensionSubst", "ExtensionPos"):
        _fix_subtable_order(getattr(st, "ExtSubTable", None), order_index)
        return
    fmt = getattr(st, "Format", None)
    if cls == "PairPos":
        sort_coverage_with(st.Coverage, [st.PairSet] if fmt == 1 else [], order_index)
        if fmt == 1 and st.PairSet:
            # PairValueRecord 必须按第二字形 GID 升序
            for pair_set in st.PairSet:
                pair_set.PairValueRecord.sort(
                    key=lambda r: order_index.get(r.SecondGlyph, 1 << 30))
    elif cls == "MarkBasePos":
        sort_coverage_with(st.MarkCoverage, [st.MarkArray.MarkRecord], order_index)
        sort_coverage_with(st.BaseCoverage, [st.BaseArray.BaseRecord], order_index)
    elif cls == "MarkLigPos":
        sort_coverage_with(st.MarkCoverage, [st.MarkArray.MarkRecord], order_index)
        sort_coverage_with(st.LigatureCoverage,
                           [st.LigatureArray.LigatureAttach], order_index)
    elif cls == "MarkMarkPos":
        sort_coverage_with(st.Mark1Coverage, [st.Mark1Array.MarkRecord], order_index)
        sort_coverage_with(st.Mark2Coverage, [st.Mark2Array.Mark2Record], order_index)
    elif cls == "ReverseChainSingleSubst":
        sort_coverage_with(st.Coverage, [st.Substitute], order_index)
    elif cls in ("ContextSubst", "ContextPos") and fmt == 1:
        arr_name = "SubRuleSet" if cls == "ContextSubst" else "PosRuleSet"
        sort_coverage_with(st.Coverage, [getattr(st, arr_name, None)], order_index)
    elif cls in ("ChainContextSubst", "ChainContextPos") and fmt == 1:
        arr_name = ("ChainSubRuleSet" if cls == "ChainContextSubst"
                    else "ChainPosRuleSet")
        sort_coverage_with(st.Coverage, [getattr(st, arr_name, None)], order_index)
    elif cls == "SinglePos":
        sort_coverage_with(st.Coverage, [], order_index)
    else:
        # dict-keyed (SingleSubst/LigatureSubst) 或 class-based (format 2/3):
        # 各 Coverage 相互独立, 单独排序即可
        for attr in _COVERAGE_ATTRS:
            val = getattr(st, attr, None)
            if isinstance(val, list):
                for cov in val:
                    sort_coverage_with(cov, [], order_index)
            else:
                sort_coverage_with(val, [], order_index)


def resort_layout(font):
    """字形顺序改变后, 修复 GSUB/GPOS/GDEF 的排序不变量。

    必须维护的不变量 (任一被破坏 fontTools 仍能保存, 但 HarfBuzz 会静默出错):

      * Coverage 按 GID 升序;
      * PairPos Format 1 的 PairValueRecord 按第二字形 GID 升序;
      * MarkBasePos / MarkLigPos / MarkMarkPos 的各 Coverage 与其数组同序;
      * Context/ChainContext Format 1 的 Coverage ↔ RuleSet 同序;
      * ReverseChainSingleSubst 的 Coverage ↔ Substitute 同序;
      * GDEF AttachList / LigCaretList 的 Coverage ↔ 数组同序。

    Args:
        font: TTFont (就地修改)

    Returns:
        font
    """
    order_index = {g: i for i, g in enumerate(font.getGlyphOrder())}
    for tag in ("GSUB", "GPOS"):
        if tag not in font:
            continue
        table = font[tag].table
        if not table.LookupList:
            continue
        for lookup in table.LookupList.Lookup:
            for st in lookup.SubTable:
                _fix_subtable_order(st, order_index)
    if "GDEF" in font:
        gdef = font["GDEF"].table
        if getattr(gdef, "AttachList", None) is not None:
            sort_coverage_with(gdef.AttachList.Coverage,
                               [gdef.AttachList.AttachPoint], order_index)
        if getattr(gdef, "LigCaretList", None) is not None:
            sort_coverage_with(gdef.LigCaretList.Coverage,
                               [gdef.LigCaretList.LigGlyph], order_index)
    return font


# --------------------------------------------------------------------------
# GSUB/GPOS 并集
# --------------------------------------------------------------------------
def lang_systems(script):
    """Script 下的所有 LangSys (DefaultLangSys + LangSysRecord)"""
    out = []
    if script.DefaultLangSys is not None:
        out.append(script.DefaultLangSys)
    for lr in (script.LangSysRecord or []):
        out.append(lr.LangSys)
    return out


def lang_systems_with_tag(script):
    """Script 下的 (langTag, LangSys); DefaultLangSys 的 tag 为 None"""
    out = []
    if script.DefaultLangSys is not None:
        out.append((None, script.DefaultLangSys))
    for lr in (script.LangSysRecord or []):
        out.append((lr.LangSysTag, lr.LangSys))
    return out


def find_or_create_lang(script, lang_tag):
    """找到或新建 script 下 lang_tag 的 LangSys"""
    if lang_tag is None:
        if script.DefaultLangSys is None:
            lang = ot.LangSys()
            lang.LookupOrder = None
            lang.ReqFeatureIndex = 0xFFFF
            lang.FeatureIndex = []
            script.DefaultLangSys = lang
        return script.DefaultLangSys
    for lr in (script.LangSysRecord or []):
        if lr.LangSysTag == lang_tag:
            return lr.LangSys
    lang = ot.LangSys()
    lang.LookupOrder = None
    lang.ReqFeatureIndex = 0xFFFF
    lang.FeatureIndex = []
    lr = ot.LangSysRecord()
    lr.LangSysTag = lang_tag
    lr.LangSys = lang
    if script.LangSysRecord is None:
        script.LangSysRecord = []
    script.LangSysRecord.append(lr)
    return lang


def _freeze(value, depth=0):
    """把 FeatureParams 等对象转成可哈希签名 (repr 含内存地址, 不可用)"""
    if depth > 4:
        return repr(value)
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return value
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v, depth + 1)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v, depth + 1) for v in value)
    if hasattr(value, "__dict__"):
        return (type(value).__name__,
                tuple(sorted((k, _freeze(v, depth + 1))
                             for k, v in vars(value).items()
                             if not k.startswith("_"))))
    return repr(value)


class MarkGlyphSetUnion:
    """GDEF MarkGlyphSetsDef 并集 + 索引重映射。

    参考 fontTools.merge.layout 的 MarkGlyphSetsDef.mergeMap (Coverage 拼接)
    与 Lookup.mapMarkFilteringSets (LookupFlag bit4 索引重映射)：
    LookupFlag bit4 (0x0010) 表示 Lookup.MarkFilteringSet 指向 GDEF
    MarkGlyphSetsDef.Coverage 的**下标**, 所以并集后必须重映射,
    否则被并进来的打底 lookup 会指向别的字体的 mark 集合。
    相同内容的集合去重 (同源分片里极常见), 避免 123 份副本。
    """

    def __init__(self):
        self.coverages = []
        self._index = {}

    def add(self, mark_glyph_sets, remap_name=None, alive=None, order_index=None):
        """并入一份 MarkGlyphSetsDef; 返回 局部索引 → 并集索引 的列表"""
        remap = []
        if mark_glyph_sets is None:
            return remap
        for cov in mark_glyph_sets.Coverage:
            glyphs = [remap_name.get(g, g) if remap_name else g for g in cov.glyphs]
            if alive is not None:
                glyphs = [g for g in glyphs if g in alive]
            if order_index is not None:
                glyphs = sorted(glyphs, key=lambda g: order_index.get(g, 1 << 30))
            else:
                glyphs = sorted(glyphs)
            key = tuple(glyphs)
            idx = self._index.get(key)
            if idx is None:
                idx = len(self.coverages)
                self._index[key] = idx
                self.coverages.append(list(glyphs))
            remap.append(idx)
        return remap

    def build(self, order_index=None):
        """构造 MarkGlyphSetsDef; 空集返回 None"""
        if not self.coverages:
            return None
        mgs = ot.MarkGlyphSetsDef()
        mgs.MarkSetTableFormat = 1
        mgs.Coverage = []
        for glyphs in self.coverages:
            cov = ot.Coverage()
            if order_index is not None:
                cov.glyphs = sorted(glyphs, key=lambda g: order_index.get(g, 1 << 30))
            else:
                cov.glyphs = list(glyphs)
            mgs.Coverage.append(cov)
        mgs.MarkSetCount = len(mgs.Coverage)
        return mgs

    def __bool__(self):
        return bool(self.coverages)


def remap_feature_variations(fv, index_map):
    """按 index_map 重写 FeatureVariations 里全部 FeatureIndex。

    FeatureVariations 的 FeatureTableSubstitution.SubstitutionRecord 用
    FeatureIndex 指向 FeatureList; FeatureList 一旦重排 (合并/排序) 就必须
    同步重写, 否则替换规则会挂到别的 feature 上 —— 这正是"重排就丢弃
    FeatureVariations"的根因, 修好后无需丢弃。

    Returns:
        (是否仍有未映射项) —— 有则说明该 Variant 已失效, 调用方应整体丢弃
    """
    if fv is None:
        return False
    dangling = False
    for rec in fv.FeatureVariationRecord:
        fts = rec.FeatureTableSubstitution
        if fts is None:
            continue
        for sub in fts.SubstitutionRecord:
            new = index_map.get(sub.FeatureIndex)
            if new is None:
                dangling = True
            else:
                sub.FeatureIndex = new
    return dangling


class LayoutUnion:
    """把多个字体的 GSUB 或 GPOS 并成一张表"""

    def __init__(self, tag):
        if tag not in ("GSUB", "GPOS"):
            raise ValueError("tag must be GSUB or GPOS: %r" % tag)
        self.tag = tag
        self.feature_records = []
        self.lookups = []
        self.script_records = []
        self.fv_records = {}
        self.fv_order = []

    # -- 并入一份表 --------------------------------------------------------
    def add_from(self, base_table, ren, var_offset=0, mark_set_remap=()):
        """并入一个字体 (或分片) 的 GSUB/GPOS 表。

        Args:
            base_table: otTables.GSUB/GPOS
            ren: 该字体字形名重映射 {旧: 新}
            var_offset: 该字体的 GDEF VarData 基址偏移
            mark_set_remap: 该字体 MarkGlyphSetsDef 的索引重映射
                            (局部索引 → 并集索引), 用于 LookupFlag bit4
        """
        if (base_table.LookupList is None or not base_table.LookupList.Lookup
                or base_table.FeatureList is None
                or not base_table.FeatureList.FeatureRecord):
            return
        base_lookups = copy.deepcopy(base_table.LookupList.Lookup)
        for lk in base_lookups:
            remap_glyph_names(lk, ren)
            offset_var_devices(lk, var_offset)
            if mark_set_remap and getattr(lk, "MarkFilteringSet", None) is not None:
                # LookupFlag bit4 (0x0010) 使用 GDEF MarkGlyphSetsDef 的索引
                if getattr(lk, "LookupFlag", 0) & 0x0010:
                    idx = lk.MarkFilteringSet
                    lk.MarkFilteringSet = (mark_set_remap[idx]
                                           if idx < len(mark_set_remap) else 0)
        lookup_base = len(self.lookups)
        n_base = len(base_table.LookupList.Lookup)
        self.lookups.extend(base_lookups)

        # FeatureVariations 引用的 feature (典型如 rvrn) 常常**本身没有 lookup**
        # (替换表由条件提供); 这类 feature 记录必须保留, 否则 FV 无处可指。
        fv_feature_indices = set()
        fv = getattr(base_table, "FeatureVariations", None)
        if fv is not None:
            for rec in fv.FeatureVariationRecord:
                fts = rec.FeatureTableSubstitution
                for sub in (fts.SubstitutionRecord if fts else []):
                    fv_feature_indices.add(sub.FeatureIndex)

        index_map = {}
        for i, fr in enumerate(base_table.FeatureList.FeatureRecord):
            idxs = [lookup_base + j for j in fr.Feature.LookupListIndex
                    if j < n_base]
            if not idxs and i not in fv_feature_indices:
                continue
            new_fr = copy.deepcopy(fr)
            new_fr.Feature.LookupListIndex = idxs
            index_map[i] = len(self.feature_records)
            self.feature_records.append(new_fr)
        if base_table.ScriptList is not None:
            self._merge_scripts(base_table.ScriptList, index_map)
        self._add_feature_variations(base_table, ren, lookup_base, n_base,
                                     index_map, var_offset)

    def _add_feature_variations(self, base_table, ren, lookup_base, n_base,
                                base_index_map, var_offset):
        """并入 FeatureVariations: 条件集相同的记录合并, 替换 lookup 取并集。

        同源分片常各自带一份**条件集完全相同**的 FeatureVariations, 其替换
        lookup 只覆盖自己的字形 —— 按条件集签名归并后把这些 lookup 并到
        同一条 SubstitutionRecord 里, 语义正是"该条件下这批字形用替换形"。
        """
        fv = getattr(base_table, "FeatureVariations", None)
        if fv is None:
            return
        for rec in fv.FeatureVariationRecord:
            fts = rec.FeatureTableSubstitution
            if fts is None or not fts.SubstitutionRecord:
                continue
            key = _freeze(rec.ConditionSet)
            merged = self.fv_records.get(key)
            if merged is None:
                merged = copy.deepcopy(rec)
                merged.FeatureTableSubstitution.SubstitutionRecord = []
                self.fv_records[key] = merged
                self.fv_order.append(key)
            subs = merged.FeatureTableSubstitution.SubstitutionRecord
            by_index = {s.FeatureIndex: s for s in subs}
            for sub in fts.SubstitutionRecord:
                new_fi = base_index_map.get(sub.FeatureIndex)
                if new_fi is None:
                    continue
                new_feat = copy.deepcopy(sub.Feature)
                remap_glyph_names(new_feat, ren)
                idxs = [lookup_base + j for j in new_feat.LookupListIndex
                        if j < n_base]
                if not idxs:
                    continue
                new_feat.LookupListIndex = idxs
                offset_var_devices(new_feat, var_offset)
                target = by_index.get(new_fi)
                if target is None:
                    ns = copy.deepcopy(sub)
                    ns.FeatureIndex = new_fi
                    ns.Feature = new_feat
                    subs.append(ns)
                    by_index[new_fi] = ns
                else:
                    for i in idxs:
                        if i not in target.Feature.LookupListIndex:
                            target.Feature.LookupListIndex.append(i)

    # -- ScriptList --------------------------------------------------------
    def _merge_scripts(self, base_script_list, base_index_map):
        merged_by_tag = {sr.ScriptTag: sr for sr in self.script_records}
        for bsr in base_script_list.ScriptRecord:
            msr = merged_by_tag.get(bsr.ScriptTag)
            if msr is None:
                msr = copy.deepcopy(bsr)
                for lang in self._lang_systems(msr.Script):
                    lang.FeatureIndex = sorted({base_index_map[i]
                                                for i in lang.FeatureIndex
                                                if i in base_index_map})
                    if getattr(lang, "ReqFeatureIndex", 0xFFFF) not in (0xFFFF, None):
                        lang.ReqFeatureIndex = base_index_map.get(
                            lang.ReqFeatureIndex, 0xFFFF)
                self.script_records.append(msr)
                merged_by_tag[bsr.ScriptTag] = msr
                continue
            for lang_tag, b_lang in self._lang_systems_with_tag(bsr.Script):
                m_lang = self._find_or_create_lang(msr.Script, lang_tag)
                for fi in b_lang.FeatureIndex:
                    mapped = base_index_map.get(fi)
                    if mapped is not None and mapped not in m_lang.FeatureIndex:
                        m_lang.FeatureIndex.append(mapped)

    _lang_systems = staticmethod(lang_systems)
    _lang_systems_with_tag = staticmethod(lang_systems_with_tag)
    _find_or_create_lang = staticmethod(find_or_create_lang)

    # -- 收尾 --------------------------------------------------------------
    @staticmethod
    def _group_key(fr):
        params = fr.Feature.FeatureParams
        return (fr.FeatureTag, _freeze(params) if params is not None else None)

    def finalize(self):
        """合并同 tag feature、按 tag 排序、重写全部索引, 返回 otTables 表"""
        if not self.feature_records:
            return None

        # 1. 同 tag (+ 同 FeatureParams) 的 FeatureRecord 并成一条
        groups = {}
        order = []
        for fr in self.feature_records:
            key = self._group_key(fr)
            grp = groups.get(key)
            if grp is None:
                grp = copy.deepcopy(fr)
                grp.Feature.LookupListIndex = list(fr.Feature.LookupListIndex)
                groups[key] = grp
                order.append(key)
            else:
                for li in fr.Feature.LookupListIndex:
                    if li not in grp.Feature.LookupListIndex:
                        grp.Feature.LookupListIndex.append(li)
        group_index = {key: i for i, key in enumerate(order)}
        old_to_group = {i: group_index[self._group_key(fr)]
                        for i, fr in enumerate(self.feature_records)}

        # 2. FeatureList 按 tag 字母序排序 (规范要求)
        records = [groups[k] for k in order]
        sort_order = sorted(range(len(records)), key=lambda i: (records[i].FeatureTag, i))
        final_map = {old: new for new, old in enumerate(sort_order)}
        records = [records[i] for i in sort_order]

        # 3. 重写 ScriptList 里的全部 feature 索引
        for sr in self.script_records:
            for lang in self._lang_systems(sr.Script):
                lang.FeatureIndex = sorted({final_map[old_to_group[i]]
                                            for i in lang.FeatureIndex
                                            if i in old_to_group})
                if getattr(lang, "ReqFeatureIndex", 0xFFFF) not in (0xFFFF, None):
                    old = lang.ReqFeatureIndex
                    lang.ReqFeatureIndex = (final_map[old_to_group[old]]
                                            if old in old_to_group else 0xFFFF)

        table = ot.GSUB() if self.tag == "GSUB" else ot.GPOS()
        table.Version = 0x00010000
        script_list = ot.ScriptList()
        script_list.ScriptRecord = sorted(self.script_records,
                                          key=lambda sr: sr.ScriptTag)
        for sr in script_list.ScriptRecord:
            if sr.Script.LangSysRecord:
                sr.Script.LangSysRecord = sorted(sr.Script.LangSysRecord,
                                                 key=lambda lr: lr.LangSysTag)
            else:
                sr.Script.LangSysRecord = []
        table.ScriptList = script_list

        feature_list = ot.FeatureList()
        feature_list.FeatureRecord = records
        table.FeatureList = feature_list

        lookup_list = ot.LookupList()
        lookup_list.Lookup = self.lookups
        table.LookupList = lookup_list

        # FeatureVariations: FeatureIndex 要走同一套 group→final 映射
        table.FeatureVariations = self._finalize_feature_variations(
            old_to_group, final_map)
        if table.FeatureVariations is not None:
            table.Version = 0x00010001
        return table

    def _finalize_feature_variations(self, old_to_group, final_map):
        if not self.fv_order:
            return None
        fv = ot.FeatureVariations()
        fv.Version = 0x00010000
        fv.FeatureVariationRecord = []
        for key in self.fv_order:
            rec = self.fv_records[key]
            fts = rec.FeatureTableSubstitution
            by_final = {}
            order = []
            for sub in fts.SubstitutionRecord:
                old = sub.FeatureIndex
                if old not in old_to_group:
                    continue
                new = final_map[old_to_group[old]]
                target = by_final.get(new)
                if target is None:
                    ns = copy.deepcopy(sub)
                    ns.FeatureIndex = new
                    by_final[new] = ns
                    order.append(ns)
                else:
                    for i in sub.Feature.LookupListIndex:
                        if i not in target.Feature.LookupListIndex:
                            target.Feature.LookupListIndex.append(i)
            if not order:
                continue
            fts.SubstitutionRecord = order
            fts.SubstitutionCount = len(order)
            fv.FeatureVariationRecord.append(rec)
        if not fv.FeatureVariationRecord:
            return None
        fv.FeatureVariationRecordCount = len(fv.FeatureVariationRecord)
        return fv
