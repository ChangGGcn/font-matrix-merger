# -*- coding: utf-8 -*-
"""GSUB/GPOS 并集合并

不同字体 (如同源分片) 各自带一份 GSUB/GPOS: 每个分片的 vert/vrt2/kern/mark
只覆盖自己的字形。合并时必须把各表的 lookup **全部追加**、字形名 remap、
lookup 内外两层索引重定位，再在同一 Script/LangSys 内把同 tag 特性并成一条。
不得跨脚本污染、不得拆散 Coverage 与并行数组；FV 无法无损表达时明确拒绝。

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
        for cov in st.BacktrackCoverage + st.LookAheadCoverage:
            sort_coverage_with(cov, [], order_index)
    elif cls in ("ContextSubst", "ContextPos") and fmt == 1:
        arr_name = "SubRuleSet" if cls == "ContextSubst" else "PosRuleSet"
        sort_coverage_with(st.Coverage, [getattr(st, arr_name, None)], order_index)
    elif cls in ("ChainContextSubst", "ChainContextPos") and fmt == 1:
        arr_name = ("ChainSubRuleSet" if cls == "ChainContextSubst"
                    else "ChainPosRuleSet")
        sort_coverage_with(st.Coverage, [getattr(st, arr_name, None)], order_index)
    elif cls == "SinglePos":
        sort_coverage_with(st.Coverage, [st.Value] if fmt == 2 else [],
                           order_index)
    elif cls == "CursivePos":
        sort_coverage_with(st.Coverage, [st.EntryExitRecord], order_index)
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
        mark_sets = getattr(gdef, "MarkGlyphSetsDef", None)
        if mark_sets is not None:
            for cov in mark_sets.Coverage:
                sort_coverage_with(cov, [], order_index)
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


def _lookup_records(obj, seen=None):
    """收集嵌套上下文动作；共享子表只访问一次。"""
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return []
    seen.add(id(obj))
    if isinstance(obj, (ot.SubstLookupRecord, ot.PosLookupRecord)):
        return [obj]
    if isinstance(obj, dict):
        values = obj.values()
    elif isinstance(obj, (list, tuple)):
        values = obj
    elif hasattr(obj, "__dict__"):
        values = [v for k, v in vars(obj).items() if not k.startswith("_")]
    else:
        return []
    return [r for v in values for r in _lookup_records(v, seen)]


def _prune_context_refs(st, available):
    """删除引用失效 lookup 的整条规则，不将动作删空后误变为 ignore。"""
    cls = type(st).__name__
    if cls in ("ExtensionSubst", "ExtensionPos"):
        return _prune_context_refs(st.ExtSubTable, available)
    if cls not in ("ContextSubst", "ChainContextSubst",
                   "ContextPos", "ChainContextPos"):
        return True
    subst = cls.endswith("Subst")
    rec_attr = "SubstLookupRecord" if subst else "PosLookupRecord"
    count_attr = "SubstCount" if subst else "PosCount"

    def valid(rule):
        records = getattr(rule, rec_attr, [])
        # 本来就是 ignore 的零动作规则必须保留；部分动作失效也整条删除。
        if any(r.LookupListIndex not in available for r in records):
            return False
        setattr(rule, count_attr, len(records))
        return True

    if st.Format == 3:
        return valid(st)
    prefix = "Chain" if cls.startswith("Chain") else ""
    kind = "Sub" if subst else "Pos"
    rule_attr = prefix + kind + ("Rule" if st.Format == 1 else "ClassRule")
    set_attr = prefix + kind + ("RuleSet" if st.Format == 1 else "ClassSet")
    sets = getattr(st, set_attr)
    for i, rule_set in enumerate(sets):
        if rule_set is None:
            continue
        rules = [r for r in getattr(rule_set, rule_attr) if valid(r)]
        setattr(rule_set, rule_attr, rules)
        setattr(rule_set, rule_attr + "Count", len(rules))
        if not rules:
            sets[i] = None
    # Coverage/类编号与 RuleSet 的槽位保持对应，不能独立压缩数组。
    setattr(st, set_attr + "Count", len(sets))
    return any(rule_set is not None for rule_set in sets)


def _prepare_lookup_graph(lookups, lookup_base, roots=None):
    """就地修剪复制后的 lookup 图，再按源顺序一次性重映射全部内部索引。"""
    candidates = {i: lk for i, lk in enumerate(lookups) if lk is not None}
    dropped_rules = 0
    while True:
        available = set(candidates)
        for i, lookup in list(candidates.items()):
            before = len(_lookup_records(lookup))
            lookup.SubTable = [st for st in lookup.SubTable
                               if _prune_context_refs(st, available)]
            lookup.SubTableCount = len(lookup.SubTable)
            dropped_rules += before - len(_lookup_records(lookup))
            if not lookup.SubTable:
                del candidates[i]
        if available == set(candidates):
            break
    if roots is not None:
        reachable = set()
        pending = list(roots)
        while pending:
            i = pending.pop()
            if i in reachable or i not in candidates:
                continue
            reachable.add(i)
            pending.extend(r.LookupListIndex
                           for r in _lookup_records(candidates[i]))
        candidates = {i: lk for i, lk in candidates.items() if i in reachable}
    order = sorted(candidates)
    index_map = {old: lookup_base + new for new, old in enumerate(order)}
    result = [candidates[i] for i in order]
    # 同一动作/Extension 子表可能共享，必须在整张图上去重，而非每个入口加偏移。
    for record in _lookup_records(result):
        record.LookupListIndex = index_map[record.LookupListIndex]
    if dropped_rules:
        print("  [OT合并] 告警: 删除 %d 个失效上下文动作所在规则，保留其余规则"
              % dropped_rules)
    return result, index_map


def _ordered_unique(values):
    """保留首次出现顺序的去重。"""
    return list(dict.fromkeys(values))


def _merge_required_feature(lang, required, records):
    """合并同 tag 必需特性；不同 tag 冲突保留主来源并明确告警。"""
    if required in (None, 0xFFFF):
        return
    current = getattr(lang, "ReqFeatureIndex", 0xFFFF)
    if current in (None, 0xFFFF):
        lang.ReqFeatureIndex = required
    elif current != required:
        if records[current].FeatureTag == records[required].FeatureTag:
            indices = getattr(lang, "_required_features", [current])
            lang._required_features = _ordered_unique(indices + [required])
        else:
            print("  [OT合并] 告警: 必需特性 tag 冲突，保留主来源 %s，"
                  "不将打底 %s 降为可选特性"
                  % (records[current].FeatureTag, records[required].FeatureTag))


def _coalesce_langsys_features(table):
    """仅在同一 LangSys 归并同 tag，保留主参数和 FV 的逐条件替换语义。"""
    records = table.FeatureList.FeatureRecord
    variations = getattr(table, "FeatureVariations", None)
    fv_records = (variations.FeatureVariationRecord if variations else [])
    for rec in fv_records:
        fts = rec.FeatureTableSubstitution
        if fts and any(not 0 <= sub.FeatureIndex < len(records)
                       for sub in fts.SubstitutionRecord):
            raise ValueError("FeatureVariations 含无效 feature 索引")
    cache = {}

    def combine(indices):
        indices = tuple(_ordered_unique(indices))
        if len(indices) == 1:
            return indices[0]
        if indices in cache:
            return cache[indices]
        first = indices[0]
        feature = copy.deepcopy(records[first])
        feature.Feature.LookupListIndex = _ordered_unique(
            li for i in indices for li in records[i].Feature.LookupListIndex)
        feature.Feature.LookupCount = len(feature.Feature.LookupListIndex)
        new_index = len(records)
        records.append(feature)
        cache[indices] = new_index
        for rec in fv_records:
            fts = rec.FeatureTableSubstitution
            if fts is None:
                continue
            by_index = {sub.FeatureIndex: sub.Feature
                        for sub in fts.SubstitutionRecord}
            if not any(i in by_index for i in indices):
                continue
            # 替换某成员时，其它来源/成员仍用默认 lookup；空替换也不能丢弃。
            selected = [by_index.get(i, records[i].Feature) for i in indices]
            sub = ot.FeatureTableSubstitutionRecord()
            sub.FeatureIndex = new_index
            sub.Feature = copy.deepcopy(selected[0])
            sub.Feature.LookupListIndex = _ordered_unique(
                li for feat in selected for li in feat.LookupListIndex)
            sub.Feature.LookupCount = len(sub.Feature.LookupListIndex)
            fts.SubstitutionRecord.append(sub)
        return new_index

    if table.ScriptList is not None:
        for sr in table.ScriptList.ScriptRecord:
            for lang in lang_systems(sr.Script):
                groups = {}
                for i in lang.FeatureIndex:
                    if not 0 <= i < len(records):
                        raise ValueError("LangSys 含无效 feature 索引")
                    groups.setdefault(records[i].FeatureTag, []).append(i)
                lang.FeatureIndex = [combine(group) for group in groups.values()]
                required = getattr(lang, "_required_features", None)
                if required:
                    lang.ReqFeatureIndex = combine(required)
                    del lang._required_features
    # FeatureList 必须按 tag 排序。LangSys.FeatureIndex 是任意顺序，保留原序
    # 只是保守处理，不宣称它决定 lookup 执行顺序（执行顺序来自 LookupList）。
    order = sorted(range(len(records)), key=lambda i: (records[i].FeatureTag, i))
    index_map = {old: new for new, old in enumerate(order)}
    table.FeatureList.FeatureRecord = [records[i] for i in order]
    table.FeatureList.FeatureCount = len(records)
    if table.ScriptList is not None:
        table.ScriptList.ScriptRecord.sort(key=lambda sr: sr.ScriptTag)
        table.ScriptList.ScriptCount = len(table.ScriptList.ScriptRecord)
        for sr in table.ScriptList.ScriptRecord:
            sr.Script.LangSysRecord = sorted(sr.Script.LangSysRecord or [],
                                             key=lambda lr: lr.LangSysTag)
            sr.Script.LangSysCount = len(sr.Script.LangSysRecord)
            for lang in lang_systems(sr.Script):
                lang.FeatureIndex = [index_map[i] for i in lang.FeatureIndex]
                lang.FeatureCount = len(lang.FeatureIndex)
                req = getattr(lang, "ReqFeatureIndex", 0xFFFF)
                if req not in (0xFFFF, None):
                    if req not in index_map:
                        raise ValueError("LangSys 含无效必需 feature 索引")
                    lang.ReqFeatureIndex = index_map[req]
    if variations is not None:
        if remap_feature_variations(variations, index_map):
            raise ValueError("FeatureVariations 无法完整重映射")
        for rec in fv_records:
            fts = rec.FeatureTableSubstitution
            if fts is not None:
                fts.SubstitutionRecord.sort(key=lambda sub: sub.FeatureIndex)
                fts.SubstitutionCount = len(fts.SubstitutionRecord)
    return table


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
        self._fv_conditions = None

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
        if (base_table.FeatureList is None
                or not base_table.FeatureList.FeatureRecord):
            return
        fv = getattr(base_table, "FeatureVariations", None)
        conditions = (tuple(_freeze(rec.ConditionSet)
                            for rec in fv.FeatureVariationRecord) if fv else None)
        if (conditions is not None and self._fv_conditions is not None
                and conditions != self._fv_conditions):
            raise ValueError("同源 FeatureVariations 条件或优先顺序不一致，拒绝有损并集")
        base_lookups = copy.deepcopy(
            base_table.LookupList.Lookup if base_table.LookupList else [])
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
        base_lookups, lookup_map = _prepare_lookup_graph(base_lookups, lookup_base)
        if fv is not None:
            for rec in fv.FeatureVariationRecord:
                fts = rec.FeatureTableSubstitution
                for sub in (fts.SubstitutionRecord if fts else []):
                    if not 0 <= sub.FeatureIndex < len(
                            base_table.FeatureList.FeatureRecord):
                        raise ValueError("FeatureVariations 引用失效 feature，拒绝有损并集")
                    if any(j not in lookup_map for j in sub.Feature.LookupListIndex):
                        raise ValueError("FeatureVariations 引用失效 lookup，拒绝有损并集")
        self.lookups.extend(base_lookups)
        if conditions is not None:
            self._fv_conditions = conditions

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
            idxs = [lookup_map[j] for j in fr.Feature.LookupListIndex
                    if j in lookup_map]
            if (not idxs and fr.Feature.LookupListIndex
                    and i not in fv_feature_indices):
                continue
            new_fr = copy.deepcopy(fr)
            new_fr.Feature.LookupListIndex = idxs
            new_fr.Feature.LookupCount = len(idxs)
            index_map[i] = len(self.feature_records)
            self.feature_records.append(new_fr)
        if base_table.ScriptList is not None:
            self._merge_scripts(base_table.ScriptList, index_map)
        self._add_feature_variations(base_table, ren, lookup_map,
                                     index_map, var_offset)

    def _add_feature_variations(self, base_table, ren, lookup_map,
                                base_index_map, var_offset):
        """同源条件序列已核对一致，保留首个匹配语义及空替换。"""
        fv = getattr(base_table, "FeatureVariations", None)
        if fv is None:
            return
        for position, rec in enumerate(fv.FeatureVariationRecord):
            key = (position, _freeze(rec.ConditionSet))
            merged = self.fv_records.get(key)
            if merged is None:
                merged = copy.deepcopy(rec)
                if merged.FeatureTableSubstitution is not None:
                    merged.FeatureTableSubstitution.SubstitutionRecord = []
                self.fv_records[key] = merged
                self.fv_order.append(key)
            fts = rec.FeatureTableSubstitution
            if fts is None:
                continue
            if merged.FeatureTableSubstitution is None:
                merged.FeatureTableSubstitution = ot.FeatureTableSubstitution()
                merged.FeatureTableSubstitution.Version = 0x00010000
                merged.FeatureTableSubstitution.SubstitutionRecord = []
            subs = merged.FeatureTableSubstitution.SubstitutionRecord
            for sub in fts.SubstitutionRecord:
                if sub.FeatureIndex not in base_index_map:
                    raise ValueError("FeatureVariations 引用失效 feature，拒绝有损并集")
                ns = copy.deepcopy(sub)
                ns.FeatureIndex = base_index_map[sub.FeatureIndex]
                remap_glyph_names(ns.Feature, ren)
                ns.Feature.LookupListIndex = [lookup_map[j]
                                               for j in sub.Feature.LookupListIndex]
                ns.Feature.LookupCount = len(ns.Feature.LookupListIndex)
                offset_var_devices(ns.Feature, var_offset)
                subs.append(ns)
            merged.FeatureTableSubstitution.SubstitutionCount = len(subs)

    # -- ScriptList --------------------------------------------------------
    def _merge_scripts(self, base_script_list, base_index_map):
        merged_by_tag = {sr.ScriptTag: sr for sr in self.script_records}
        for bsr in base_script_list.ScriptRecord:
            msr = merged_by_tag.get(bsr.ScriptTag)
            if msr is None:
                msr = copy.deepcopy(bsr)
                for lang in self._lang_systems(msr.Script):
                    lang.FeatureIndex = _ordered_unique(
                        base_index_map[i] for i in lang.FeatureIndex
                        if i in base_index_map)
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
                required = base_index_map.get(
                    getattr(b_lang, "ReqFeatureIndex", 0xFFFF))
                _merge_required_feature(m_lang, required, self.feature_records)

    _lang_systems = staticmethod(lang_systems)
    _lang_systems_with_tag = staticmethod(lang_systems_with_tag)
    _find_or_create_lang = staticmethod(find_or_create_lang)

    # -- 收尾 --------------------------------------------------------------
    def finalize(self):
        """按 LangSys 归并同 tag，再统一重写默认/必需/FV 的 feature 索引。"""
        if not self.feature_records:
            return None
        table = ot.GSUB() if self.tag == "GSUB" else ot.GPOS()
        table.Version = 0x00010000
        table.ScriptList = ot.ScriptList()
        table.ScriptList.ScriptRecord = copy.deepcopy(self.script_records)
        table.FeatureList = ot.FeatureList()
        table.FeatureList.FeatureRecord = copy.deepcopy(self.feature_records)
        table.LookupList = ot.LookupList()
        table.LookupList.Lookup = copy.deepcopy(self.lookups)
        table.LookupList.LookupCount = len(self.lookups)
        table.FeatureVariations = None
        if self.fv_order:
            fv = ot.FeatureVariations()
            fv.Version = 0x00010000
            fv.FeatureVariationRecord = [copy.deepcopy(self.fv_records[key])
                                         for key in self.fv_order]
            fv.FeatureVariationRecordCount = len(fv.FeatureVariationRecord)
            table.FeatureVariations = fv
            table.Version = 0x00010001
        return _coalesce_langsys_features(table)
