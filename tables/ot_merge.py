# -*- coding: utf-8 -*-
"""OpenType 布局特性 (GSUB/GPOS/GDEF) 合并

Logic.md 第 3 条:
  主字体 OpenType 特性完全保留;
  打底字体中与主字体不冲突的语言和特性表可以完全保留
  (剔除与已删除字形相关的项); 如有冲突以主字体为基准。

实现思路 (fontTools.subset 官方机制):
  打底字体的布局表先按"存活字形集"做引用修剪 ——
  lookup 的规则只保留覆盖了存活字形的条目, 闭包自动补入
  规则依赖的字形 (如 kern 对), 最后与主字体布局表合并。

合并细则:
  * 字形取舍: 打底 lookup 引用的字形必须都在主字体里, 否则整条 lookup 跳过
    (Extension 子表要展开递归, 见 _lookup_glyphs_in_font);
  * 先构建存活 lookup 的完整索引映射并补齐嵌套闭包；失效动作所在规则整条删除;
  * 同 tag feature 仅在同一 Script/LangSys 内做 lookup 并集，主来源参数优先，
    不改其它脚本/语言的引用，必需特性与可选特性不混为一谈;
  * 打底的 ScriptList/LangSys 一并并入, 之后 FeatureList 按 tag 排序并
    重写全部 FeatureIndex (否则追加的 feature 不可达);
  * GDEF GlyphClassDef/MarkAttachClassDef 取并集 (主优先), ItemVariationStore
    做 region 并集 + VarData 拼接, 打底 GPOS 的 VariationIndex 按基址重定位;
  * 追加/改名之后调用 resort_layout() 修复 Coverage 与并行数组的同序不变量。
"""
import copy
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables as ot
from fontTools.subset import Subsetter, Options

from .layout_union import (MarkGlyphSetUnion, find_or_create_lang,
                           _coalesce_langsys_features, _lookup_records,
                           _merge_required_feature, _ordered_unique,
                           _prepare_lookup_graph,
                           lang_systems, lang_systems_with_tag,
                           offset_var_devices, remap_feature_variations,
                           resort_layout)
from .varstore import VarStoreUnion


def _layout_tags():
    return ("GDEF", "GSUB", "GPOS")


def prune_base_layout(base_font, kept_glyphs):
    """修剪打底字体的 GSUB/GPOS/GDEF, 只保留与 kept_glyphs 相关的规则。

    使用 fontTools.subset.Subsetter 的闭包机制:
      - populate(glyphs=kept) 后 closure 会把规则的依赖字形补进保留集;
      - 再对布局表做引用修剪 (lookup/feature/script 空则删);
      - 布局表从修剪后的字体"提取"回来 (不修改轮廓)。

    Args:
        base_font: 打底字体 (会被深拷贝处理后返回新字体)
        kept_glyphs: 已合并进主字体的打底字形 (iterable)

    Returns:
        修剪后的 TTFont (仅布局表变化, 轮廓不变但可作废)
    """
    from io import BytesIO

    work = copy.deepcopy(base_font)
    kept = set(kept_glyphs) | {".notdef"}

    # Subsetter 选项: 关闭字形子集化以外的表裁剪, 只允许布局修剪
    opts = Options()
    opts.layout_features = ["*"]          # 保留所有 feature
    opts.notdef_outline = True            # 保留 .notdef
    opts.name_IDs = []                    # 不动 name
    opts.name_legacy = False
    opts.drop_tables = []                 # 不删任何表
    # 关键: 这些默认开启的选项只影响轮廓/cmap 等, 不影响布局闭包

    ss = Subsetter(options=opts)
    ss.populate(glyphs=list(kept))

    # 只调用闭包 + 布局修剪, 不真正子集化轮廓
    # 做法: 让 Subsetter 对打底做整体 subset (轮廓也剪),
    #       但我们只需提取其布局表结果。
    try:
        ss.subset(work)
    except Exception as e:
        print(f"  [OT修剪] 打底布局子集化失败: {e}")
        return None

    # 布局表在 subset 后被修剪, 提取它们
    result = TTFont(sfntVersion=work.sfntVersion)
    for tag in _layout_tags():
        if tag in work:
            result[tag] = copy.deepcopy(work[tag])
    # 保留 glyphOrder (修剪后的) 供合并时引用检查
    result.setGlyphOrder(work.getGlyphOrder())
    return result


def merged_kept_glyphs(base_font, kept_glyphs):
    """返回打底布局修剪后仍然的有效字形集 (闭包后的保留集)"""
    pruned = prune_base_layout(base_font, kept_glyphs)
    if pruned is None:
        return set(kept_glyphs), None
    return set(pruned.getGlyphOrder()), pruned


def merge_base_layout(main_font, base_pruned, kept_glyphs):
    """把修剪后的打底布局表合并进主字体。

    规则:
      - 主字体已有 GSUB/GPOS/GDEF: 保留主来源规则，打底按存活 lookup 图
        追加，只在相同 script/lang 内归并同 tag（主参数优先）。
      - 主字体无对应表: 仍须校验打底引用并重定位 GDEF 相关索引后采用。
      - 打底 FV 不与已有主条件跨来源拼接；主无布局表时可完整采用。

    Args:
        main_font: 主字体 (就地修改)
        base_pruned: prune_base_layout 的结果 (TTFont, 含修剪后的布局表)
        kept_glyphs: 打底中真正并入主字体的字形 (用于跳过已删字形)

    Returns:
        main_font
    """
    kept = set(kept_glyphs)
    main_layout = {tag: main_font[tag] for tag in _layout_tags() if tag in main_font}
    base_layout = {tag: base_pruned[tag] for tag in _layout_tags() if tag in base_pruned}

    if not base_layout:
        print("  [OT合并] 打底无布局表, 跳过")
        return main_font

    # GDEF VarStore 并集: 主的 VarData 保持在前 (基址 0), 打底的接在后面。
    # 打底 GPOS 里所有 VariationIndex 的 outer 索引要加上打底的基址偏移。
    var_union = VarStoreUnion()
    mark_union = MarkGlyphSetUnion()
    var_offset = 0
    mark_remap = ()

    # 合并 GDEF (GlyphClassDef/MarkAttach 等): 主优先
    if "GDEF" in base_layout:
        if "GDEF" in main_layout:
            alive = set(main_font.getGlyphOrder())
            order_index = {g: i for i, g in enumerate(main_font.getGlyphOrder())}
            var_union.add(getattr(main_layout["GDEF"].table, "VarStore", None))
            # 主的 mark 集合先入并集 → 索引恒等映射, 主自己的 lookup 不受影响
            mark_union.add(getattr(main_layout["GDEF"].table, "MarkGlyphSetsDef", None),
                           alive=alive, order_index=order_index)
            var_offset, mark_remap = _merge_gdef(main_font, main_layout["GDEF"],
                                                 base_layout["GDEF"], kept,
                                                 var_union, mark_union)
            _apply_gdef_extras(main_font, main_layout["GDEF"], var_union,
                               mark_union, order_index)
        else:
            # 主无 GDEF: 采用打底 GDEF, 但只保留名称与主字体一致的字形
            # (避免打底 name 空间如 uni0041 与主 A 错位)
            _use_base_gdef(main_font, base_layout["GDEF"])

    # 合并 GSUB/GPOS
    for tag in ("GSUB", "GPOS"):
        if tag not in base_layout:
            continue
        if tag not in main_layout:
            # 不能直接复制：主无该表时同样可能有失效字形、内部索引和 GDEF 偏移。
            adopted = newTable(tag)
            adopted.table = ot.GSUB() if tag == "GSUB" else ot.GPOS()
            adopted.table.Version = 0x00010000
            adopted.table.ScriptList = None
            adopted.table.FeatureList = None
            adopted.table.LookupList = None
            adopted.table.FeatureVariations = None
            _merge_gsub_gpos(main_font, tag, adopted.table,
                             base_layout[tag].table, var_offset, mark_remap)
            if adopted.table.FeatureList is not None:
                main_font[tag] = adopted
                resort_layout(main_font)
            continue

        main_tbl = main_layout[tag].table
        base_tbl = base_layout[tag].table
        _merge_gsub_gpos(main_font, tag, main_tbl, base_tbl, var_offset,
                         mark_remap)

    resort_layout(main_font)
    return main_font


def _apply_gdef_extras(font, main_gdef, var_union, mark_union, order_index):
    """把并集 ItemVariationStore / MarkGlyphSetsDef 写回主的 GDEF 并升 Version。

    GDEF Version 门槛: MarkGlyphSetsDef 需要 ≥ 1.2, VarStore 需要 1.3。
    """
    table = main_gdef.table
    if var_union:
        table.VarStore = var_union.build()
    if mark_union:
        table.MarkGlyphSetsDef = mark_union.build(order_index)
    if var_union:
        table.Version = max(0x00010003, table.Version or 0)
    elif mark_union and (table.Version or 0) < 0x00010002:
        table.Version = 0x00010002


def _use_base_gdef(font, base_gdef):
    """主无 GDEF 时采用打底 GDEF (按名称过滤到主字形集)"""
    alive = set(font.getGlyphOrder())
    new_gdef = copy.deepcopy(base_gdef)
    t = new_gdef.table
    # GlyphClassDef 过滤
    if t.GlyphClassDef is not None and t.GlyphClassDef.classDefs:
        t.GlyphClassDef.classDefs = {
            g: v for g, v in t.GlyphClassDef.classDefs.items() if g in alive
        }
    # MarkGlyphSets 过滤
    if getattr(t, "MarkGlyphSetsDef", None) is not None:
        for cov in t.MarkGlyphSetsDef.Coverage:
            cov.glyphs = [g for g in cov.glyphs if g in alive]
    # AttachList/LigCaretList 的空表删除
    if getattr(t, "AttachList", None) is not None and not t.AttachList.Coverage.glyphs:
        t.AttachList = None
    font["GDEF"] = new_gdef
    n_cls = len(t.GlyphClassDef.classDefs) if t.GlyphClassDef is not None else 0
    print(f"  [OT合并] GDEF: 来自打底 (主无, 过滤后 {n_cls} 个字类)")


def _merge_gdef(font, main_gdef, base_gdef, kept, var_union=None,
                mark_union=None):
    """GDEF 合并: 类定义取并集 (冲突以主为准), VarStore 做并集。

    GlyphClassDef / MarkAttachClassDef 是"字形 → 类"的映射, 主字体的值优先,
    打底补齐新增字形 —— 只保留主的会让新增字形丢失 mark/base 分类, GPOS 的
    mark 附着对它失效。MarkGlyphSetsDef 的 Coverage 索引被 LookupFlag 直接
    引用, 索引体系不同, 仍只在主缺失时整体采用。

    Returns:
        打底 VarData 在并集中的基址偏移 (其 GPOS VariationIndex 需 +offset)
    """
    from fontTools.ttLib.tables.otTables import ClassDef

    mt = main_gdef.table
    bt = base_gdef.table
    alive = set(font.getGlyphOrder())

    added_cls = 0
    if bt.GlyphClassDef is not None and bt.GlyphClassDef.classDefs:
        if mt.GlyphClassDef is None:
            mt.GlyphClassDef = ClassDef()
            mt.GlyphClassDef.classDefs = {}
        for g, v in bt.GlyphClassDef.classDefs.items():
            if g in alive and g not in mt.GlyphClassDef.classDefs:
                mt.GlyphClassDef.classDefs[g] = v
                added_cls += 1
    if getattr(bt, "MarkAttachClassDef", None) is not None and bt.MarkAttachClassDef.classDefs:
        if getattr(mt, "MarkAttachClassDef", None) is None:
            mt.MarkAttachClassDef = ClassDef()
            mt.MarkAttachClassDef.classDefs = {}
        for g, v in bt.MarkAttachClassDef.classDefs.items():
            if g in alive and g not in mt.MarkAttachClassDef.classDefs:
                mt.MarkAttachClassDef.classDefs[g] = v

    # MarkGlyphSetsDef 并集: 返回打底局部索引 → 并集索引 的映射,
    # 打底 lookup 的 LookupFlag bit4 索引要据此重写
    mark_remap = ()
    if mark_union is not None:
        mark_remap = mark_union.add(
            getattr(bt, "MarkGlyphSetsDef", None), alive=alive,
            order_index={g: i for i, g in enumerate(font.getGlyphOrder())})

    n_cls = len(mt.GlyphClassDef.classDefs) if mt.GlyphClassDef is not None else 0
    print(f"  [OT合并] GDEF: 字类 {n_cls} (打底补 {added_cls}), "
          f"mark 集合 {len(mark_union.coverages) if mark_union else 0}")

    # VarStore 并集: 打底的 GPOS VariationIndex 要按基址偏移重定位
    var_offset = var_union.add(getattr(bt, "VarStore", None)) if var_union is not None else 0
    return var_offset, mark_remap


def _merge_gsub_gpos(font, tag, main_tbl, base_tbl, var_offset=0,
                     mark_set_remap=()):
    """按源顺序合并完整 lookup 图，再按 LangSys 合并同 tag（主参数优先）。"""
    base_lookups = base_tbl.LookupList.Lookup if base_tbl.LookupList else []
    if base_tbl.FeatureList is None:
        print("  [OT合并] %s: 打底无 feature/lookup，保留主来源" % tag)
        return
    # 先在副本上验证 FV/必需引用，失败时不留下部分追加的布局表。
    original = main_tbl
    main_tbl = copy.deepcopy(main_tbl)
    if main_tbl.LookupList is None:
        main_tbl.LookupList = ot.LookupList()
        main_tbl.LookupList.Lookup = []
    if main_tbl.FeatureList is None:
        main_tbl.FeatureList = ot.FeatureList()
        main_tbl.FeatureList.FeatureRecord = []
    main_lookups = main_tbl.LookupList.Lookup
    records = list(main_tbl.FeatureList.FeatureRecord)
    adopt_fv = not main_lookups and not records
    base_fv = getattr(base_tbl, "FeatureVariations", None)

    # kern 及其上下文闭包不能通用地按码位重定向到主来源字形，避免双重定位。
    kern_lookups = set()
    pending = [i for fr in base_tbl.FeatureList.FeatureRecord
               if tag == "GPOS" and fr.FeatureTag == "kern"
               for i in fr.Feature.LookupListIndex]
    while pending:
        i = pending.pop()
        if i in kern_lookups or not 0 <= i < len(base_lookups):
            continue
        kern_lookups.add(i)
        pending.extend(r.LookupListIndex for r in _lookup_records(base_lookups[i]))
    candidates = copy.deepcopy(base_lookups)
    for i, lookup in enumerate(candidates):
        if i not in kern_lookups:
            _remap_lookup_glyph_names(font, lookup)
        if not _lookup_glyphs_in_font(font, lookup):
            candidates[i] = None
            continue
        offset_var_devices(lookup, var_offset)
        if (mark_set_remap and getattr(lookup, "LookupFlag", 0) & 0x0010):
            idx = lookup.MarkFilteringSet
            if not 0 <= idx < len(mark_set_remap):
                candidates[i] = None
                continue
            lookup.MarkFilteringSet = mark_set_remap[idx]
    roots = [i for fr in base_tbl.FeatureList.FeatureRecord
             for i in fr.Feature.LookupListIndex]
    fv_features = set()
    if adopt_fv and base_fv is not None:
        for rec in base_fv.FeatureVariationRecord:
            fts = rec.FeatureTableSubstitution
            for sub in (fts.SubstitutionRecord if fts else []):
                fv_features.add(sub.FeatureIndex)
                roots.extend(sub.Feature.LookupListIndex)
    added, lookup_map = _prepare_lookup_graph(candidates, len(main_lookups), roots)
    if adopt_fv and base_fv is not None:
        for rec in base_fv.FeatureVariationRecord:
            fts = rec.FeatureTableSubstitution
            for sub in (fts.SubstitutionRecord if fts else []):
                if any(i not in lookup_map for i in sub.Feature.LookupListIndex):
                    raise ValueError("打底 FeatureVariations 引用失效 lookup，保留主布局")
    main_lookups.extend(added)
    main_tbl.LookupList.LookupCount = len(main_lookups)
    feature_of_base = {}
    feature_map = {}
    for i, fr in enumerate(base_tbl.FeatureList.FeatureRecord):
        idxs = _ordered_unique(lookup_map[j] for j in fr.Feature.LookupListIndex
                               if j in lookup_map)
        # 空默认特性可能只有参数，或者由 FV 提供替换，均不应静默删除。
        if (not idxs and fr.Feature.LookupListIndex and i not in fv_features):
            continue
        target = copy.deepcopy(fr)
        target.Feature.LookupListIndex = idxs
        target.Feature.LookupCount = len(idxs)
        feature_of_base[i] = target
        feature_map[i] = len(records)
        records.append(target)
    if not feature_of_base:
        print("  [OT合并] %s: 打底 feature 无有效 lookup，保留主来源" % tag)
        return
    main_tbl.FeatureList.FeatureRecord = records
    if base_tbl.ScriptList is not None:
        _merge_script_list(main_tbl, base_tbl.ScriptList, feature_of_base, records)
    if adopt_fv and base_fv is not None:
        fv = copy.deepcopy(base_fv)
        if remap_feature_variations(fv, feature_map):
            raise ValueError("打底 FeatureVariations 引用失效 feature，保留主布局")
        for rec in fv.FeatureVariationRecord:
            fts = rec.FeatureTableSubstitution
            for sub in (fts.SubstitutionRecord if fts else []):
                sub.Feature.LookupListIndex = [lookup_map[i]
                                                for i in sub.Feature.LookupListIndex]
                sub.Feature.LookupCount = len(sub.Feature.LookupListIndex)
        main_tbl.FeatureVariations = fv
        main_tbl.Version = max(main_tbl.Version, 0x00010001)
    elif base_fv is not None:
        print("  [OT合并] 告警: %s 打底 FeatureVariations 不跨来源统一，保留主条件" % tag)
    _coalesce_langsys_features(main_tbl)
    original.__dict__.clear()
    original.__dict__.update(main_tbl.__dict__)
    resort_layout(font)
    print("  [OT合并] %s: 并入 %d 个 lookup、%d 条来源 feature，按 LangSys 归并"
          % (tag, len(added), len(feature_of_base)))


def _merge_script_list(main_tbl, base_script_list, feature_of_base, records):
    """把打底的 ScriptList/LangSys 并入主 (feature 索引重定位到合并后列表)"""
    from fontTools.ttLib.tables import otTables as ot

    pos = {id(fr): i for i, fr in enumerate(records)}
    if main_tbl.ScriptList is None:
        main_tbl.ScriptList = ot.ScriptList()
        main_tbl.ScriptList.ScriptRecord = []
    by_tag = {sr.ScriptTag: sr for sr in main_tbl.ScriptList.ScriptRecord}
    for bsr in base_script_list.ScriptRecord:
        msr = by_tag.get(bsr.ScriptTag)
        if msr is None:
            msr = copy.deepcopy(bsr)
            for lang in lang_systems(msr.Script):
                lang.FeatureIndex = _ordered_unique(
                    pos[id(feature_of_base[i])] for i in lang.FeatureIndex
                    if i in feature_of_base)
                req = getattr(lang, "ReqFeatureIndex", 0xFFFF)
                if req not in (0xFFFF, None):
                    lang.ReqFeatureIndex = (pos[id(feature_of_base[req])]
                                            if req in feature_of_base else 0xFFFF)
            main_tbl.ScriptList.ScriptRecord.append(msr)
            by_tag[bsr.ScriptTag] = msr
            continue
        for lang_tag, b_lang in lang_systems_with_tag(bsr.Script):
            m_lang = find_or_create_lang(msr.Script, lang_tag)
            for fi in b_lang.FeatureIndex:
                fr = feature_of_base.get(fi)
                if fr is None:
                    continue
                mi = pos[id(fr)]
                if mi not in m_lang.FeatureIndex:
                    m_lang.FeatureIndex.append(mi)
            required = feature_of_base.get(
                getattr(b_lang, "ReqFeatureIndex", 0xFFFF))
            if required is not None:
                _merge_required_feature(m_lang, pos[id(required)], records)


def _remap_lookup_glyph_names(font, lookup):
    """把 lookup 中 uniXXXX/cidXXXX 风格字形名重映射为主字体的等价名。

    按码位等价: 打底 CID→name 后叫 uni0041, 但主字体叫 A —
    通过主字体 cmap 反查码位得出主字体实际名, 然后改 lookup 引用。
    深度遍历 (递归处理嵌套的 Coverage/ClassDef/Component 等)。
    """
    from fontTools.pens.basePen import BasePen  # noqa: F401 (占位避免误判)

    # 主字体 cmap: 码位 → 字形名
    cp_to_gn = {}
    if "cmap" in font:
        for t in font["cmap"].tables:
            if hasattr(t, "cmap") and t.cmap:
                for cp, gn in t.cmap.items():
                    cp_to_gn.setdefault(cp, gn)
    alive = set(font.getGlyphOrder())

    def remap(name):
        if not isinstance(name, str):
            return name
        if name in alive:
            return name
        if name.startswith("uni") and len(name) == 7:
            try:
                cp = int(name[3:], 16)
            except ValueError:
                return name
            return cp_to_gn.get(cp, name)
        if name.startswith("u") and len(name) == 6:
            try:
                cp = int(name[1:], 16)
            except ValueError:
                return name
            return cp_to_gn.get(cp, name)
        return name

    # 深度遍历: 处理 otTables 对象 (用 vars 递归), 字形名属性按名称识别
    _remap_obj(font, lookup, remap, seen=set())


def _remap_obj(font, obj, remap, seen=None):
    """递归遍历 otTables 对象, 对字形名引用做 remap。

    识别规则: 值为字符串且属性名含字形语义 (glyph/glyphs/Coverage/ClassDef
    的子项等), 或通用 —— 直接对所有字符串值调用 remap (依赖 remap 的
    "已在 alive 则不变" 短路, 非字形字符串 (tag) 因不在 alive 且非 uni/
    uXXXXX 格式而原样返回, 安全)。
    """
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, str):
        return  # 顶层字符串由调用者处理
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(k, str):
                nk = remap(k)
                if nk != k:
                    del obj[k]
                    obj[nk] = v
                    k = nk
            _remap_obj(font, v, remap, seen)
        return
    if isinstance(obj, list):
        for i, v in enumerate(list(obj)):
            if isinstance(v, str):
                obj[i] = remap(v)
            else:
                _remap_obj(font, v, remap, seen)
        return
    if hasattr(obj, "__dict__"):
        # 注意: 这里**不**单独排序 Coverage —— 改名会改变 GID 顺序, 但 MarkBasePos
        # 等的 Coverage 与并行数组必须同序; 统一交给 resort_layout() 在合并收尾时
        # 按 P4 清单 (Coverage / PairValueRecord / MarkArray / RuleSet …) 处理。
        for k, v in list(vars(obj).items()):
            if k.startswith("_"):
                continue
            if isinstance(v, str):
                nv = remap(v)
                if nv != v:
                    setattr(obj, k, nv)
            else:
                _remap_obj(font, v, remap, seen)


def _collect_strings(obj, names=None, seen=None):
    """收集对象树里的全部字符串 (dict 键 + 值), 返回 set[str]。

    lookup 子表里的字符串**只可能是字形名** —— Coverage.glyphs、
    ClassDef.classDefs 键、SingleSubst.mapping 键值、AlternateSubst.alternates、
    LigatureSubst.ligatures 键与 Ligature.Component、上下文规则的
    Input/Backtrack/LookAhead…… 故无需逐属性枚举 (枚举必漏: 漏掉
    AlternateSubst/LigatureSubst 时校验会"通过", 保存时才 KeyError)。
    Extension 子表 (ExtSubTable) 照常递归。
    """
    if names is None:
        names = set()
    if seen is None:
        seen = set()
    if isinstance(obj, str):
        names.add(obj)
        return names
    if id(obj) in seen:
        return names
    seen.add(id(obj))
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                names.add(k)
            _collect_strings(v, names, seen)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_strings(v, names, seen)
    elif hasattr(obj, "__dict__"):
        for k, v in vars(obj).items():
            if k.startswith("_"):
                continue
            _collect_strings(v, names, seen)
    return names


def _lookup_glyphs_in_font(font, lookup):
    """校验 lookup 引用的所有字形都在主字体中。

    Extension(Ext) 子表必须递归展开 —— 只看外层的话一个字形都收集不到,
    于是"校验通过", 打底已删字形的引用会被原样带进主字体, 保存时才炸。
    """
    alive = set(font.getGlyphOrder())
    try:
        names = set()
        for st in getattr(lookup, "SubTable", []) or []:
            _collect_strings(st, names)
        names.discard("")
        if not names:
            return True  # 无字形引用, 视为安全
        return names <= alive
    except Exception:
        # 校验失败时**跳过**该 lookup: 宁可少一个特性, 也不能产出保存不了的字体
        return False


def merge_ot_features(main_font, base_font, kept_glyphs):
    """对外主入口: 修剪打底布局表并合并进主字体。

    Args:
        main_font: 主字体 TTFont (就地修改)
        base_font: 打底字体 TTFont (不会被修改)
        kept_glyphs: 打底中并入主字体的字形列表

    Returns:
        main_font
    """
    base_pruned = prune_base_layout(base_font, kept_glyphs)
    if base_pruned is None:
        print("  [OT合并] 打底布局修剪失败, 保持主字体布局不变")
        return main_font
    return merge_base_layout(main_font, base_pruned, kept_glyphs)
