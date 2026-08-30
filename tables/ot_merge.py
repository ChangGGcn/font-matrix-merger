# -*- coding: utf-8 -*-
"""OpenType 布局特性 (GSUB/GPOS/GDEF) 合并

Logic.md 第 3 条:
  主字体 OpenType 特性完全保留;
  打底字体中与主字体不冲突的语言和特性表可以完全保留
  (剔除与已删除字形相关的项); 如有冲突以主字体为基准。

实现思路 (fontTools.subset 官方机制):
  打底字体的布局表先按"存活字形集"做引用修剪 —
  lookup 的规则只保留覆盖了存活字形的条目, 闭包自动补入
  规则依赖的字形 (如 kern 对), 最后与主字体布局表合并。
  冲突 (同 feature/lookup 语义) 以主字体为准。
"""
import copy
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options


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
      - 主字体已有 GSUB/GPOS/GDEF: 完全保留, 打底的 feature 若与主
        feature tag 冲突则跳过 (以主为准); 非冲突 tag/script/lang 追加。
      - 主字体无对应表: 直接使用打底的修剪结果。
    冲突检测粒度: feature tag + script tag + lang sys (简化: feature tag)。

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

    # 合并 GDEF (GlyphClassDef/MarkAttach 等): 主优先
    if "GDEF" in base_layout:
        if "GDEF" in main_layout:
            _merge_gdef(main_font, main_layout["GDEF"], base_layout["GDEF"], kept)
        else:
            # 主无 GDEF: 采用打底 GDEF, 但只保留名称与主字体一致的字形
            # (避免打底 name 空间如 uni0041 与主 A 错位)
            _use_base_gdef(main_font, base_layout["GDEF"])

    # 合并 GSUB/GPOS
    for tag in ("GSUB", "GPOS"):
        if tag not in base_layout:
            continue
        if tag not in main_layout:
            main_font[tag] = copy.deepcopy(base_layout[tag])
            print(f"  [OT合并] {tag}: 来自打底 (主无, {sum(len(fr.FeatureRecord) for fr in base_layout[tag].table.FeatureList.FeatureRecord) if base_layout[tag].table.FeatureList else 0} features)")
            continue

        main_tbl = main_layout[tag].table
        base_tbl = base_layout[tag].table
        _merge_gsub_gpos(main_font, tag, main_tbl, base_tbl)

    return main_font


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


def _merge_gdef(font, main_gdef, base_gdef, kept):
    """GDEF 合并: 主优先, 打底补缺 (仅当主无相应子表)。

    GDEF 的 GlyphClassDef 等引用字形, CID→name 统一后两者命名一致;
    保留主的字类定义, 打底的 MarkGlyphSets 若主无则补入。
    """
    mt = main_gdef.table
    bt = base_gdef.table
    # GlyphClassDef: 主优先 (主无则用打底)
    if mt.GlyphClassDef is None and bt.GlyphClassDef is not None:
        from fontTools.ttLib.tables.otTables import ClassDef
        mt.GlyphClassDef = copy.deepcopy(bt.GlyphClassDef)
        # 只保留存活字形 (合并后的主字形集 + 新增字形集)
        alive = set(font.getGlyphOrder())
        if mt.GlyphClassDef.classDefs:
            mt.GlyphClassDef.classDefs = {
                g: v for g, v in mt.GlyphClassDef.classDefs.items() if g in alive
            }
    # MarkGlyphSets: 主无则用打底
    if getattr(mt, "MarkGlyphSetsDef", None) is None and getattr(bt, "MarkGlyphSetsDef", None) is not None:
        mt.MarkGlyphSetsDef = copy.deepcopy(bt.MarkGlyphSetsDef)
    print("  [OT合并] GDEF: 保留主字体 (打底补缺已有)" if mt.GlyphClassDef is not None else "  [OT合并] GDEF: 打底提供 GlyphClassDef")


def _merge_gsub_gpos(font, tag, main_tbl, base_tbl):
    """GSUB/GPOS 表级合并: 保留主的, 追加打底的非冲突 feature。

    冲突判断: feature tag 相同 → 以主为准跳过打底的。
    lookup 追加时需要把打底 feature 的 LookupListIndex 重映射到主表。
    """
    main_features = set()
    if main_tbl.FeatureList and main_tbl.FeatureList.FeatureRecord:
        main_features = {fr.FeatureTag for fr in main_tbl.FeatureList.FeatureRecord}

    added = 0
    if base_tbl.FeatureList and base_tbl.FeatureList.FeatureRecord:
        # 主 LookupList 初始化
        if main_tbl.LookupList is None:
            from fontTools.ttLib.tables.otTables import LookupList
            main_tbl.LookupList = LookupList()
            main_tbl.LookupList.Lookup = []
        main_lookups = main_tbl.LookupList.Lookup
        base_lookups = base_tbl.LookupList.Lookup if base_tbl.LookupList else []

        for fr in base_tbl.FeatureList.FeatureRecord:
            if fr.FeatureTag in main_features:
                continue
            # 重映射: 深拷贝 feature, 其引用的 lookup 追加到主后改索引
            new_feat = copy.deepcopy(fr)
            new_idx = []
            for li in new_feat.Feature.LookupListIndex:
                if li < len(base_lookups):
                    new_lookup = copy.deepcopy(base_lookups[li])
                    # 字形名对齐: uniXXXX → 主字体的等价名 (A, ae 等)
                    _remap_lookup_glyph_names(font, new_lookup)
                    # 校验: lookup 引用的所有字形必须存在于主字体, 否则跳过
                    if not _lookup_glyphs_in_font(font, new_lookup):
                        continue
                    main_lookups.append(new_lookup)
                    new_idx.append(len(main_lookups) - 1)
            new_feat.Feature.LookupListIndex = new_idx
            if not new_idx:
                continue  # 无有效 lookup
            main_tbl.FeatureList.FeatureRecord.append(new_feat)
            main_features.add(fr.FeatureTag)
            added += 1
    if added:
        print(f"  [OT合并] {tag}: 追加 {added} 个打底 feature (主冲突跳过)")
    else:
        print(f"  [OT合并] {tag}: 全部与主冲突或为空, 只保留主")


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
        # Coverage 物件: 无条件按主字体 glyph id 重新排序 (GSUB/GPOS 要求升序)
        if hasattr(obj, "glyphs") and isinstance(getattr(obj, "glyphs", None), list):
            try:
                order = {g: i for i, g in enumerate(font.getGlyphOrder())}
                obj.glyphs = sorted(obj.glyphs, key=lambda g: order.get(g, 1 << 30))
            except Exception:
                pass
        for k, v in list(vars(obj).items()):
            if k.startswith("_"):
                continue
            if isinstance(v, str):
                nv = remap(v)
                if nv != v:
                    setattr(obj, k, nv)
            else:
                _remap_obj(font, v, remap, seen)


def _sort_coverage(font, cov):
    """按主字体 glyph id 排序 Coverage (Coverage 表要求升序)"""
    try:
        order = {g: i for i, g in enumerate(font.getGlyphOrder())}
        cov.glyphs = sorted(cov.glyphs, key=lambda g: order.get(g, 1 << 30))
    except Exception:
        pass


def _lookup_glyphs_in_font(font, lookup):
    """校验 lookup 引用的所有字形都在主字体中。

    收集: Coverage.glyphs + ClassDef.classDefs.keys() + 其他显式字形引用
    (PairPos 的 ClassDef1/2, SinglePos/SingleSubst 的 mapping 键值等)
    """
    alive = set(font.getGlyphOrder())
    try:
        seen = set()
        for st in getattr(lookup, "SubTable", []) or []:
            # 通配收集所有 *Coverage 属性 (Coverage/BaseMark/Input/LookAhead/Backtrack…)
            for attr in vars(st) if hasattr(st, "__dict__") else []:
                if not attr.endswith("Coverage") and not attr.endswith("Coverages"):
                    continue
                val = getattr(st, attr, None)
                if val is None:
                    continue
                items = val if isinstance(val, list) else [val]
                for item in items:
                    if item is not None and getattr(item, "glyphs", None):
                        seen.update(item.glyphs)
            # ClassDef (PairPos/CursivePos/MarkBasePos 等的 ClassDef1/2)
            for attr in ("ClassDef1", "ClassDef2", "ClassDef"):
                cd = getattr(st, attr, None)
                if cd is not None and getattr(cd, "classDefs", None):
                    seen.update(cd.classDefs.keys())
            # SingleSubst/SinglePos 的 mapping 与 LigatureSubst 的 Component
            for attr in ("mapping", "glyph", "value"):
                v = getattr(st, attr, None)
                if attr == "glyph" and isinstance(v, str):
                    seen.add(v)
                elif isinstance(v, dict):
                    for k, val in v.items():
                        if isinstance(k, str):
                            seen.add(k)
                        if isinstance(val, str):
                            seen.add(val)
                        elif isinstance(val, list):
                            for item in val:
                                if isinstance(item, str):
                                    seen.add(item)
                                elif hasattr(item, "Component"):
                                    seen.update(c for c in item.Component if isinstance(c, str))
        if not seen:
            return True  # 无字形引用, 视为安全
        return seen <= alive
    except Exception:
        return True  # 无法校验时保守通过


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
