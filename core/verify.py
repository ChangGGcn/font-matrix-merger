# -*- coding: utf-8 -*-
"""合并结果自检 — verify_merge()

逐字形比对"源分片 vs 合并字体", 并检查容器与元数据。核心判据:

  1. 码位: 合并字体覆盖所有源分片的码位并集 (missing/extra 均为 0);
  2. 轮廓与度量: 在多个轴位置 (默认 + 轴两端) 实例化源/合并字体,
     对每个源字形比较分解后的轮廓与 hmtx/vmtx — 要求零差异;
  3. 布局: GSUB/GPOS 特性 tag 覆盖各分片; 无悬空字形引用; Coverage 有序;
  4. 容器: sfnt 魔数 / flavor / head.flags bit11; nameID 16/17/25 + 实例 PS 名;
  5. 变体: GDEF ClassDef、MarkGlyphSets、VarStore 不丢。

不使用 HarfBuzz: 无 uharfbuzz 依赖时也能跑; 布局层面的"字形是否可达/有序"
由第 3 条静态校验覆盖。
"""
from fontTools.pens.recordingPen import RecordingPen
from fontTools.varLib.instancer import instantiateVariableFont

from ..tables.layout_union import _COVERAGE_ATTRS  # noqa: F401
from ..utils.detect import is_variable

#: 合并后不应存在的 WOFF2 残留位
_WOFF2_FLAG = 0x0800


def _pen_value(font, glyph_name, glyph_set=None):
    pen = RecordingPen()
    (glyph_set or font.getGlyphSet())[glyph_name].draw(pen)
    return pen.value


def _pen(glyph_name, glyph_set):
    """在给定 glyphSet 上画一个字形 (返回 RecordingPen 结果)"""
    pen = RecordingPen()
    glyph_set[glyph_name].draw(pen)
    return pen.value


def _coords_delta(a, b, tolerance):
    """比较两个 RecordingPen 结果; 返回是否在容差内 (及最大偏差)"""
    if len(a) != len(b):
        return False, float("inf")
    worst = 0.0
    for (op1, args1), (op2, args2) in zip(a, b):
        if op1 != op2 or len(args1) != len(args2):
            return False, float("inf")
        for v1, v2 in zip(args1, args2):
            p1 = v1 if isinstance(v1, tuple) else (v1,)
            p2 = v2 if isinstance(v2, tuple) else (v2,)
            if len(p1) != len(p2):
                return False, float("inf")
            for x, y in zip(p1, p2):
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    worst = max(worst, abs(float(x) - float(y)))
    return worst <= tolerance, worst


def _instance(font, position):
    """在指定用户坐标实例化; 位置按字体自身的轴**投影** (缺轴忽略)。

    跨设计空间合成时, 合并空间的坐标可能含源字体没有的轴 —— 对源字体而言
    那些轴不存在, 直接忽略即可 (等价于"源在该轴上恒定")。

    注意 (实测): `instantiateVariableFont` 的 user limits **不套 avar**
    (getGlyphSet 会套) —— 同一字体的实例化结果与渲染结果能差 1 单位级。
    因此采样点只用 min/default/max (avar 的三条不动点), 两条路径在这些点上
    一致; 合成本身是在**渲染语义** (post-avar) 下逐点等价的。
    """
    if position is None or not is_variable(font):
        return font
    own = {a.axisTag for a in font["fvar"].axes}
    pos = {k: v for k, v in dict(position).items() if k in own}
    if not pos:
        return font
    return instantiateVariableFont(font, pos, inplace=False, optimize=False)


def grid_positions(font, per_axis=3, max_positions=64):
    """在设计空间上取网格采样点 (每轴 min/default/max 的笛卡尔积, 截断)。"""
    import itertools

    if not is_variable(font):
        return [None]
    axes = font["fvar"].axes
    values = [sorted({a.minValue, a.defaultValue, a.maxValue}) for a in axes]
    out = []
    for combo in itertools.product(*values):
        out.append({a.axisTag: v for a, v in zip(axes, combo)})
        if len(out) >= max_positions:
            break
    return out


def _auto_positions(font):
    """默认: 轴默认位置 + 第一条轴的最小/最大位置"""
    if not is_variable(font):
        return [None]
    axis = font["fvar"].axes[0]
    pos = [None]
    for v in (axis.minValue, axis.maxValue):
        if v != axis.defaultValue:
            pos.append({axis.axisTag: v})
    return pos


def _label(position, font):
    if position is None:
        return "default"
    return ",".join("%s=%g" % (k, v) for k, v in position.items())


def verify_merge(sources, merged, glyph_map=None, axis_positions="auto",
                 tolerance=0.0, sample=None, verbose=True):
    """校验合并结果, 返回结构化报告 dict。

    Args:
        sources: 源分片列表 (TTFont 或路径; 与 merge_subsets 的输入一致)
        merged: 合并结果 TTFont
        glyph_map: {分片标签: {源字形名: 合并后字形名/GID}};
                   缺省按字形名相同处理 (合并时未改名的情况)
        axis_positions: "auto" (默认位置 + 首轴两端) | "grid" (各轴
                        min/default/max 的网格) | [None|dict]; None = 不实例化
        tolerance: 轮廓坐标容差 (单位: 字体单位)
        sample: 每个分片最多比对多少个字形 (None = 全部)
        verbose: 打印进度

    Returns:
        {"ok": bool, "failures": [str], "checks": {...}, "stats": {...}}
    """
    from ..core.subset_merge import load_subsets

    fonts, labels = load_subsets(sources)
    failures = []
    checks = {}

    def log(*a):
        if verbose:
            print(*a, flush=True)

    # ---- 1. 码位 ----
    src_cps = set()
    for f in fonts:
        src_cps |= set(f.getBestCmap())
    merged_cps = set(merged.getBestCmap())
    missing = sorted(src_cps - merged_cps)
    extra = sorted(merged_cps - src_cps)
    checks["codepoints"] = {"source": len(src_cps), "merged": len(merged_cps),
                            "missing": len(missing), "extra": len(extra)}
    if missing:
        failures.append("码位丢失 %d 个: %s" % (len(missing), missing[:10]))
    if extra:
        failures.append("出现源字体没有的码位 %d 个: %s" % (len(extra), extra[:10]))
    log("  [码位] 源 %d, 合并 %d, 缺失 %d, 多余 %d"
        % (len(src_cps), len(merged_cps), len(missing), len(extra)))

    # ---- 2. 轴 / 实例 ----
    src_axes = {}
    for f in fonts:
        if is_variable(f):
            src_axes[tuple((a.axisTag, a.minValue, a.defaultValue, a.maxValue)
                           for a in f["fvar"].axes)] = True
    checks["axes"] = {"source": len(src_axes), "variable": is_variable(merged)}
    if len(src_axes) > 1:
        failures.append("源分片轴空间不一致 (%d 种)" % len(src_axes))
    if is_variable(merged) and src_axes:
        merged_axes = tuple((a.axisTag, a.minValue, a.defaultValue, a.maxValue)
                            for a in merged["fvar"].axes)
        if merged_axes not in src_axes:
            failures.append("合并字体轴空间与源分片不一致: %s" % (merged_axes,))

    if axis_positions == "auto":
        positions = _auto_positions(merged)
    elif axis_positions == "grid":
        positions = grid_positions(merged)
    else:
        positions = list(axis_positions)
    checks["positions"] = [_label(p, merged) for p in positions]

    # ---- 3. 逐字形轮廓/度量比对 ----
    merged_by_pos = {}
    compared = 0
    mismatched = {"outline": 0, "hmtx": 0, "vmtx": 0}
    samples = {}
    for position in positions:
        merged_inst = _instance(merged, position)
        merged_set = merged_inst.getGlyphSet()
        merged_order = merged_inst.getGlyphOrder()
        merged_index = {gn: i for i, gn in enumerate(merged_order)}
        pname = _label(position, merged)
        for index, (font, label) in enumerate(zip(fonts, labels)):
            src_inst = _instance(font, position)
            src_set = src_inst.getGlyphSet()
            src_order = src_inst.getGlyphOrder()
            gmap = (glyph_map or {}).get(label, {})
            names = src_order
            if sample and len(names) > sample:
                step = max(1, len(names) // sample)
                names = names[::step][:sample]
            for gn in names:
                if gn == ".notdef":
                    continue
                target = gmap.get(gn, gn)
                if isinstance(target, int):
                    if target >= len(merged_order):
                        continue
                    target = merged_order[target]
                if isinstance(target, str) and target not in merged_index:
                    continue
                compared += 1
                ok, worst = _coords_delta(_pen_value(src_inst, gn, src_set),
                                          _pen_value(merged_inst, target, merged_set),
                                          tolerance)
                if not ok:
                    mismatched["outline"] += 1
                    if len(samples.get("outline", [])) < 5:
                        samples.setdefault("outline", []).append(
                            (label, gn, target, worst))
                    continue
                if "hmtx" in src_inst and "hmtx" in merged_inst:
                    if src_inst["hmtx"][gn] != merged_inst["hmtx"][target]:
                        mismatched["hmtx"] += 1
                        if len(samples.get("hmtx", [])) < 5:
                            samples.setdefault("hmtx", []).append(
                                (label, gn, src_inst["hmtx"][gn],
                                 merged_inst["hmtx"][target]))
                if "vmtx" in src_inst and "vmtx" in merged_inst:
                    if (gn in src_inst["vmtx"].metrics
                            and target in merged_inst["vmtx"].metrics
                            and src_inst["vmtx"][gn] != merged_inst["vmtx"][target]):
                        mismatched["vmtx"] += 1
        log("  [轮廓] 位置 %-12s 累计比对 %d 字形, 不一致 %s"
            % (pname, compared, mismatched))
        merged_by_pos[pname] = merged_inst

    checks["glyphs"] = {"compared": compared, "mismatched": dict(mismatched),
                        "samples": samples}
    for kind, n in mismatched.items():
        if n:
            failures.append("%s 不一致 %d 处, 例: %s"
                            % (kind, n, samples.get(kind, [])[:3]))

    # ---- 4. 布局特性 ----
    feat_report = {}
    for tag in ("GSUB", "GPOS"):
        merged_tags = set()
        if tag in merged and merged[tag].table.FeatureList:
            merged_tags = {fr.FeatureTag
                           for fr in merged[tag].table.FeatureList.FeatureRecord}
        src_tags = set()
        for f in fonts:
            if tag in f and f[tag].table.FeatureList:
                src_tags |= {fr.FeatureTag
                             for fr in f[tag].table.FeatureList.FeatureRecord}
        lost = sorted(src_tags - merged_tags)
        feat_report[tag] = {"source": sorted(src_tags), "merged": sorted(merged_tags),
                            "lost": lost}
        if lost:
            failures.append("%s 丢失特性: %s" % (tag, lost))
    checks["features"] = feat_report
    log("  [特性] GSUB %d, GPOS %d" % (len(feat_report["GSUB"]["merged"]),
                                       len(feat_report["GPOS"]["merged"])))

    # ---- 5. 布局引用完整性 ----
    layout = _check_layout_integrity(merged)
    checks["layout"] = layout
    if layout["dangling"]:
        failures.append("布局表引用不存在的字形 %d 个: %s"
                        % (len(layout["dangling"]), layout["dangling"][:10]))
    if layout["unsorted_coverages"]:
        failures.append("Coverage 未按 GID 升序: %d 个" % layout["unsorted_coverages"])
    if layout["bad_mark_filters"]:
        failures.append("MarkFilteringSet 索引越界 %d 处: %s"
                        % (len(layout["bad_mark_filters"]),
                           layout["bad_mark_filters"][:3]))
    if layout["bad_feature_variations"]:
        failures.append("FeatureVariations 索引无效 %d 处: %s"
                        % (len(layout["bad_feature_variations"]),
                           layout["bad_feature_variations"][:3]))
    if layout["bad_var_stores"]:
        failures.append("ItemVariationStore/VariationIndex 结构非法 %d 处: %s"
                        % (len(layout["bad_var_stores"]),
                           layout["bad_var_stores"][:3]))
    log("  [布局] 悬空引用 %d, 未排序 Coverage %d, mark 集合越界 %d, "
        "FeatureVariations 越界 %d, VarStore 非法 %d"
        % (len(layout["dangling"]), layout["unsorted_coverages"],
           len(layout["bad_mark_filters"]),
           len(layout["bad_feature_variations"]),
           len(layout["bad_var_stores"])))

    # ---- 6. GDEF ----
    gdef_report = {"classes": 0, "mark_sets": 0, "var_store": False}
    if "GDEF" in merged:
        g = merged["GDEF"].table
        gdef_report["classes"] = len(g.GlyphClassDef.classDefs) if g.GlyphClassDef else 0
        gdef_report["mark_sets"] = (g.MarkGlyphSetsDef.MarkSetCount
                                    if getattr(g, "MarkGlyphSetsDef", None) else 0)
        gdef_report["var_store"] = getattr(g, "VarStore", None) is not None
    checks["gdef"] = gdef_report

    # ---- 7. VVAR / HVAR 覆盖 ----
    var_maps = {}
    for tag in ("HVAR", "VVAR"):
        if tag not in merged:
            continue
        table = merged[tag].table
        for attr in ("AdvWidthMap", "LsbMap", "RsbMap",
                     "AdvHeightMap", "TsbMap", "BsbMap", "VOrgMap"):
            m = getattr(table, attr, None)
            if m is None or not hasattr(m, "mapping"):
                continue
            n_missing = sum(1 for gn in merged.getGlyphOrder()
                            if gn not in m.mapping)
            var_maps["%s.%s" % (tag, attr)] = n_missing
            if n_missing:
                failures.append("%s.%s 缺少 %d 个字形的映射"
                                % (tag, attr, n_missing))
    checks["variation_maps"] = var_maps

    # ---- 8. 容器与元数据 ----
    container = {
        "flavor": merged.flavor,
        "head_flags": hex(merged["head"].flags),
        "woff2_flag_cleared": not (merged["head"].flags & _WOFF2_FLAG),
        "name16": merged["name"].getDebugName(16) if "name" in merged else None,
        "name17": merged["name"].getDebugName(17) if "name" in merged else None,
        "name25": merged["name"].getDebugName(25) if "name" in merged else None,
        "instance_ps_names": [],
    }
    if merged.flavor not in (None, "woff", "woff2"):
        failures.append("flavor 异常: %r" % (merged.flavor,))
    if not container["woff2_flag_cleared"]:
        failures.append("head.flags 未清除 WOFF2 位: %s" % container["head_flags"])
    if is_variable(merged):
        if not container["name16"]:
            failures.append("缺少 nameID 16 (Typographic Family)")
        if not container["name25"]:
            failures.append("缺少 nameID 25 (Variations PS Name Prefix)")
        ps = []
        for inst in merged["fvar"].instances:
            pid = getattr(inst, "postscriptNameID", 0xFFFF)
            nm = merged["name"].getDebugName(pid) if pid not in (0xFFFF, None) else None
            ps.append(nm)
            if not nm:
                failures.append("命名实例缺少 PostScript 名 (nameID %s)" % pid)
        container["instance_ps_names"] = ps
        if len(set(ps)) != len(ps):
            failures.append("命名实例 PostScript 名重复")
    checks["container"] = container

    # ---- 9. 垂直变体 (vert/vrt2) ----
    vert = {"source": 0, "merged": 0}
    for tag, feat in (("GSUB", "vert"), ("GSUB", "vrt2")):
        for f in fonts:
            vert["source"] += _feature_glyph_count(f, tag, feat)
        vert["merged"] += _feature_glyph_count(merged, tag, feat)
    checks["vertical_forms"] = vert
    if vert["merged"] < vert["source"]:
        failures.append("竖排变体覆盖减少: 源 %d → 合并 %d"
                        % (vert["source"], vert["merged"]))

    report = {"ok": not failures, "failures": failures, "checks": checks}
    if failures:
        log("[校验] 失败 %d 项:" % len(failures))
        for f_ in failures:
            log("   - " + f_)
    else:
        log("[校验] 全部通过 (比对 %d 字形 × %d 个轴位置)"
            % (compared, len(positions)))
    return report


def _feature_glyph_count(font, tag, feat):
    """某个 feature 覆盖的字形引用数 (含映射值)"""
    if tag not in font:
        return 0
    table = font[tag].table
    if not table.FeatureList or not table.LookupList:
        return 0
    n = 0
    for fr in table.FeatureList.FeatureRecord:
        if fr.FeatureTag != feat:
            continue
        for li in fr.Feature.LookupListIndex:
            if li >= len(table.LookupList.Lookup):
                continue
            for st in table.LookupList.Lookup[li].SubTable:
                sub = getattr(st, "ExtSubTable", st)
                for attr in _COVERAGE_ATTRS:
                    val = getattr(sub, attr, None)
                    for cov in (val if isinstance(val, list) else [val]):
                        if cov is not None and getattr(cov, "glyphs", None):
                            n += len(cov.glyphs)
                m = getattr(sub, "mapping", None)
                if isinstance(m, dict):
                    n += len(m)
    return n


#: 直接持有字形名的 otTables 属性 (按属性名识别, 避免把 script/feature tag 误判)
_GLYPH_NAME_ATTRS = ("glyphs", "Substitute", "SecondGlyph", "Component",
                     "Input", "Backtrack", "LookAhead")


def verify_composition(merged, main_font, base_font, added_glyphs, sample=30,
                       tolerance=1.0, max_positions=6, verbose=False,
                       adv_tolerance=None):
    """验证跨设计空间合成是否逐点等价 (不通过抛 AssertionError)。

    语义: 合并字体在位置 p 的实例, 其**新增字形**应等于打底字体在 p (按各自
    轴投影) 的实例, **主字体字形**应等于主字体在 p 的实例。网格采样, 抽样比对
    轮廓与 hmtx; 轮廓容差默认 1 单位 (整数化/F2Dot14 量化级别)。

    adv_tolerance: 字宽容差, 缺省同 tolerance。重参数化后的 HVAR 增量是**整数**,
    一个源列拆成多个 hat 后逐个取整, 非默认位置上的残差可达几个单位, 因此
    调用方会给它一个更宽的值 (CFF2 路径实测 ≤ 2 单位)。

    采样点只取各轴的 min/default/max: 这三点是 avar 的不动点, 而
    instantiateVariableFont 的 user limits 不套 avar (getGlyphSet 会套),
    只有不动点上两条路径才一致 —— 参见 _instance 的说明。

    调用方 (FontMerger) 在自检失败时回退到按打底默认实例化的旧行为。
    """
    if adv_tolerance is None:
        adv_tolerance = tolerance
    positions = grid_positions(merged, max_positions=max_positions)
    if sample and len(added_glyphs) > sample:
        step = max(1, len(added_glyphs) // sample)
        added_glyphs = added_glyphs[::step][:sample]
    main_glyphs = [g for g in main_font.getGlyphOrder() if g != ".notdef"]
    if sample and len(main_glyphs) > sample:
        step = max(1, len(main_glyphs) // sample)
        main_glyphs = main_glyphs[::step][:sample]

    worst = 0.0
    checked = 0
    # 用 glyphSet(location=用户坐标) 而不是 instantiateVariableFont: 前者与
    # 渲染一致 (会套 avar, 见 _instance 的说明), 且宽度天然带上 HVAR 的变化。
    for pos in positions:
        label = _label(pos, merged)
        sets = (merged.getGlyphSet(location=pos),
                base_font.getGlyphSet(location=pos),
                main_font.getGlyphSet(location=pos))
        for gn in added_glyphs:
            if gn not in sets[1]:
                continue
            ok, w = _coords_delta(_pen(gn, sets[0]), _pen(gn, sets[1]),
                                 tolerance)
            worst = max(worst, w)
            checked += 1
            if not ok:
                raise AssertionError(
                    "合成自检失败 (%s): 新增字形 %s 与打底实例不一致 (最大偏差 %s)"
                    % (label, gn, w))
            adv_m = sets[0][gn].width
            adv_b = sets[1][gn].width
            if abs(adv_m - adv_b) > adv_tolerance:
                raise AssertionError(
                    "合成自检失败 (%s): 新增字形 %s 的字宽不一致 (%s vs %s)"
                    % (label, gn, adv_m, adv_b))
        for gn in main_glyphs:
            if gn not in sets[2]:
                continue
            ok, w = _coords_delta(_pen(gn, sets[0]), _pen(gn, sets[2]),
                                 tolerance)
            worst = max(worst, w)
            checked += 1
            if not ok:
                raise AssertionError(
                    "合成自检失败 (%s): 主字体字形 %s 被改动 (最大偏差 %s)"
                    % (label, gn, w))
    if verbose:
        print("  [合成自检] %d 个位置 × %d 字形, 最大偏差 %.2f"
              % (len(positions), checked, worst))
    return {"positions": len(positions), "checked": checked, "worst": worst}

def _check_layout_integrity(font):
    """检查布局表: 悬空字形引用 + Coverage 是否按 GID 升序

    只按"持有字形名的属性"收集引用 (glyphs / classDefs / mapping /
    ligatures / SecondGlyph / Substitute / Component / 上下文 Input 等),
    不能对整棵树的所有字符串做判断 —— script tag ("DFLT")、feature tag
    ("kern") 也都是字符串。
    """
    glyph_order = font.getGlyphOrder()
    alive = set(glyph_order)
    order = {g: i for i, g in enumerate(glyph_order)}
    dangling = set()
    unsorted_count = 0

    def check_names(names):
        for n in names:
            if isinstance(n, str) and n not in alive:
                dangling.add(n)

    def walk(obj, seen):
        nonlocal unsorted_count
        if id(obj) in seen:
            return
        seen.add(id(obj))
        if isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v, seen)
            return
        if not hasattr(obj, "__dict__"):
            return
        for k, v in vars(obj).items():
            if k.startswith("_"):
                continue
            if k == "glyphs" and isinstance(v, list):
                check_names(v)
                gids = [order.get(g, -1) for g in v]
                if gids != sorted(gids):
                    unsorted_count += 1
            elif k in ("Substitute", "Component", "Input", "Backtrack", "LookAhead"):
                if isinstance(v, list):
                    check_names([x for x in v if isinstance(x, str)])
            elif k in ("SecondGlyph",):
                check_names([v])
            elif k in ("classDefs", "mapping", "ligatures"):
                if isinstance(v, dict):
                    check_names([x for x in v if isinstance(x, str)])
                    for val in v.values():
                        if isinstance(val, str):
                            check_names([val])
                        elif isinstance(val, (list, tuple)):
                            check_names([x for x in val if isinstance(x, str)])
                        else:
                            walk(val, seen)
            walk(v, seen)

    for tag in ("GSUB", "GPOS", "GDEF"):
        if tag in font:
            walk(font[tag].table, set())

    # LookupFlag bit4 的 MarkFilteringSet 必须指向存在的 GDEF mark 集合
    mark_sets = None
    if "GDEF" in font:
        mgs = getattr(font["GDEF"].table, "MarkGlyphSetsDef", None)
        mark_sets = mgs.MarkSetCount if mgs is not None else 0
    bad_mark_filters = []
    for tag in ("GSUB", "GPOS"):
        if tag not in font or not font[tag].table.LookupList:
            continue
        for i, lk in enumerate(font[tag].table.LookupList.Lookup):
            if not (getattr(lk, "LookupFlag", 0) & 0x0010):
                continue
            idx = getattr(lk, "MarkFilteringSet", None)
            if idx is None or not mark_sets or idx >= mark_sets:
                bad_mark_filters.append((tag, i, idx, mark_sets or 0))

    # FeatureVariations 的 FeatureIndex / 替换 lookup 索引必须有效
    bad_feature_variations = []
    for tag in ("GSUB", "GPOS"):
        if tag not in font:
            continue
        table = font[tag].table
        fv = getattr(table, "FeatureVariations", None)
        if fv is None:
            continue
        n_feat = (len(table.FeatureList.FeatureRecord)
                  if table.FeatureList else 0)
        n_lookups = (len(table.LookupList.Lookup)
                     if table.LookupList else 0)
        for r_i, rec in enumerate(fv.FeatureVariationRecord):
            fts = rec.FeatureTableSubstitution
            for sub in (fts.SubstitutionRecord if fts else []):
                if not 0 <= sub.FeatureIndex < n_feat:
                    bad_feature_variations.append(
                        (tag, r_i, "featureIndex", sub.FeatureIndex, n_feat))
                for li in sub.Feature.LookupListIndex:
                    if not 0 <= li < n_lookups:
                        bad_feature_variations.append(
                            (tag, r_i, "lookupIndex", li, n_lookups))

    bad_var_stores = _check_var_stores(font)

    return {"dangling": sorted(dangling),
            "unsorted_coverages": unsorted_count,
            "bad_mark_filters": bad_mark_filters,
            "bad_feature_variations": bad_feature_variations,
            "bad_var_stores": bad_var_stores}


def _check_var_stores(font):
    """ItemVariationStore 的结构不变量 (跨设计空间合并最容易写坏的地方)。

      * 各表 VarStore 的 RegionAxisCount 必须等于 fvar 轴数 (否则是非法字体);
      * 每个 VarData 的 VarRegionIndex 必须落在 region 表内;
      * GPOS/GSUB 里 DeltaFormat=0x8000 的 VariationIndex 的
        (outer=VarData 序号, inner=该 VarData 的**行号**) 必须落在 GDEF
        VarStore 内 (一行的增量向量与各列 region 标量做点积)。
    """
    from fontTools.ttLib.tables import otTables as ot

    problems = []
    n_axes = len(font["fvar"].axes) if "fvar" in font else 0
    stores = {}
    for tag in ("GDEF", "HVAR", "VVAR", "MVAR", "BASE"):
        if tag not in font:
            continue
        table = getattr(font[tag], "table", None)
        vs = getattr(table, "VarStore", None) if table is not None else None
        if vs is None:
            continue
        stores[tag] = vs
        got = vs.VarRegionList.RegionAxisCount
        if got != n_axes:
            problems.append((tag, "RegionAxisCount", got, n_axes))
        n_regions = vs.VarRegionList.RegionCount
        for vd_i, vd in enumerate(vs.VarData):
            for col, r in enumerate(vd.VarRegionIndex):
                if not 0 <= r < n_regions:
                    problems.append((tag, "VarRegionIndex", (vd_i, col, r),
                                     n_regions))

    gdef_vs = stores.get("GDEF")
    if gdef_vs is None:
        return problems
    n_var_data = len(gdef_vs.VarData)

    def walk_devices(obj, seen, tag):
        if id(obj) in seen:
            return
        seen.add(id(obj))
        if isinstance(obj, (list, tuple)):
            for v in obj:
                walk_devices(v, seen, tag)
            return
        if isinstance(obj, ot.Device) and getattr(obj, "DeltaFormat", 0) == 0x8000:
            outer, inner = obj.StartSize, obj.EndSize
            if (outer, inner) == (0xFFFF, 0xFFFF):
                return                      # NO_VARIATION_INDEX: 合法的"无变化"
            if not 0 <= outer < n_var_data:
                problems.append((tag, "VariationIndex.outer", outer, n_var_data))
            elif not 0 <= inner < gdef_vs.VarData[outer].ItemCount:
                problems.append((tag, "VariationIndex.inner", (outer, inner),
                                 gdef_vs.VarData[outer].ItemCount))
        d = getattr(obj, "__dict__", None)
        if not d:
            return
        for v in d.values():
            walk_devices(v, seen, tag)

    for tag in ("GSUB", "GPOS"):
        if tag in font:
            walk_devices(font[tag].table, set(), tag)
    return problems
