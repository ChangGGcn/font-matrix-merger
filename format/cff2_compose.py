# -*- coding: utf-8 -*-
"""CFF2 blend/vsindex 的跨设计空间重参数化 (阶段 4)

CFF2 把全部可变数据放在 CharStrings 的 `blend` 里 (Private DICT 的 hint 值也
可以带 blend)。操作数布局 (实测与 fontTools 的 program 一致, 用默认点实例化
逐值比对确认):

    [v_1 … v_n, Δ_1(每个 region 一个), …, Δ_n, n, "blend"]

n = 被混合的值个数, Δ 的个数 = 当前 vsindex 指向的 VarData 的 region 数
(`vsindex` 改变当前 VarData; 缺省取 Private DICT 的 `vsindex`, 再缺省为 0)。

于是跨设计空间重参数化与 gvar/ItemVariationStore 是同一套数学:

  * 每个源 region 的 hat 在合并空间展开成 Σ_k w_k·φ_{S_k}(x) + C
    (region_split_plans, constant_column=False: C 由调用方折进 blend 的默认值);
  * VarStore: 每个 VarData 的列 = 各源列展开后的串联, **VarData 序号保持**
    (blend 的 vsindex 因此不需要改写);
  * blend: 默认值 += Σ_j Δ_j·C_j, 增量按权重分配到新列。

`offset_cff2_vsindex()` 用于把打底的引用整体平移到"主字体 VarData 之后"的
位置 (并入别的字体时), 无显式 vsindex 的程序会补一条, 隐式默认不再依赖
Private DICT。
"""
import copy

from fontTools.ttLib.tables import otTables as ot

from .variation_compose import (_make_region, _num_shorts, _store_region_supports,
                                region_split_plans)


def cff2_var_store(font):
    """CFF2 的 otTables.VarStore (无则 None)"""
    if "CFF2" not in font:
        return None
    td = font["CFF2"].cff.topDictIndex[0]
    vsd = getattr(td, "VarStore", None)
    if vsd is None:
        vsd = getattr(td.CharStrings, "varStore", None)
    if vsd is None:
        return None
    if getattr(vsd, "otVarStore", None) is None:
        vsd.decompile()
    return vsd.otVarStore


def set_cff2_var_store(font, ot_var_store):
    """把 otTables.VarStore 写回 CFF2 topDict (CharStrings 共享同一对象)"""
    from fontTools.cffLib import VarStoreData

    td = font["CFF2"].cff.topDictIndex[0]
    vsd = VarStoreData(otVarStore=ot_var_store)
    td.VarStore = vsd
    td.CharStrings.varStore = vsd
    # Private 的 blend 也要用同一个 VarStore 对象 (instancer 会断言同一性)
    for owner in _private_dicts(td):
        owner.vstore = vsd
    return vsd


def _private_dicts(td):
    """topDict 与所有 FDArray 项的 Private DICT (去重)"""
    out = []
    seen = set()
    for owner in [td] + list(getattr(td, "FDArray", []) or []):
        pd = getattr(owner, "Private", None)
        if pd is not None and id(pd) not in seen:
            seen.add(id(pd))
            out.append(pd)
    return out


def _programs(td):
    """所有会出现 blend 的程序对象 (CharStrings + GlobalSubrs + 各 Private.Subrs)"""
    out = []
    cs = td.CharStrings
    out.extend(cs.values() if hasattr(cs, "values") else [cs[n] for n in cs.keys()])
    out.extend(td.GlobalSubrs or [])
    for pd in _private_dicts(td):
        out.extend(getattr(pd, "Subrs", None) or [])
    return out


def _blend_columns(var_store):
    """每个 VarData 的"列布局": (源 region 序号列表, 各列在新表里的起始下标)"""
    layout = []
    for vd in var_store.VarData:
        layout.append([r for r in vd.VarRegionIndex])
    return layout


def _rewrite_deltas(deltas, src_regions, plans, constants):
    """把一行的源增量 (每列一个) 展开到新列: 返回 (常数项, 新增量列表)"""
    const = 0.0
    out = []
    for c, r in enumerate(src_regions):
        d = deltas[c]
        const += d * constants[r]
        for _idx, weight in plans[r]:
            out.append(d * weight)
    return const, out


def _rewrite_program(program, layout, plans, constants, new_widths):
    """重写一个程序里的所有 blend (返回新 program)。

    Args:
        program: 原 program 列表
        layout: [(源 region 序号, 该 VarData 的列数), ...] 按 VarData 序号
        plans/constants: region_split_plans 的结果
        new_widths: 每个 VarData 新列数
    """
    out = []
    vsindex = 0
    i = 0
    n_tok = len(program)
    while i < n_tok:
        tok = program[i]
        if tok == "vsindex":
            out.append(program[i])          # 操作数已在前一项
            vsindex = program[i - 1]
            i += 1
            continue
        if tok != "blend":
            out.append(tok)
            i += 1
            continue
        n = out.pop()                       # 被混合的值个数
        src_regions, n_cols = layout[vsindex]
        n_ops = n * (n_cols + 1)
        block = out[len(out) - n_ops:]
        del out[len(out) - n_ops:]
        defaults = block[:n]
        deltas = block[n:]
        rewritten = [_rewrite_deltas(deltas[b * n_cols:(b + 1) * n_cols],
                                     src_regions, plans, constants)
                     for b in range(n)]
        # blend 操作数顺序: 默认值在前, 随后每个值一个增量块 (最后才是 n blend)
        out.extend(defaults[b] + rewritten[b][0] for b in range(n))
        for _const, new_d in rewritten:
            out.extend(new_d)
        out.append(n)
        out.append("blend")
        i += 1
    return out


def _private_arg_types():
    """Private DICT 各键的 argType (delta / number / SID …)"""
    from fontTools.cffLib import privateDictOperators

    out = {}
    for entry in privateDictOperators:
        if len(entry) >= 3 and isinstance(entry[1], str) and isinstance(entry[2], str):
            out[entry[1]] = entry[2]
    return out


def _rewrite_private(pd, layout, plans, constants):
    """Private DICT 的 blend 值 (hint 数据) 重写。

    两种形态 (由 argType 决定, 不能只看形状 —— 普通 delta 表也是平铺列表):
      * argType="delta" (BlueValues/OtherBlues/StemSnapH/V):
        [[默认值, Δ…], …] —— 每个值一项;
      * argType="number" (BlueScale/StdHW/StdVW):
        [默认值, Δ…] —— 单值 blend 就是平铺列表 (arg_number 里写 n=1 的 blend)。
    """
    raw = getattr(pd, "rawDict", None)
    if not raw:
        return 0
    arg_types = _private_arg_types()
    vsindex = raw.get("vsindex", 0)
    if isinstance(vsindex, list):
        vsindex = vsindex[0]
    if vsindex >= len(layout):
        return 0
    src_regions, n_cols = layout[vsindex]
    n_masters = n_cols + 1
    touched = 0
    for name, value in list(raw.items()):
        if not isinstance(value, list) or not value:
            continue
        arg_type = arg_types.get(name)
        if arg_type == "delta" and isinstance(value[0], list):
            if len(value[0]) != n_masters:
                continue
            new_value = []
            for entry in value:
                const, new_d = _rewrite_deltas(entry[1:], src_regions, plans,
                                               constants)
                new_value.append([entry[0] + const] + new_d)
        elif (arg_type == "number" and not isinstance(value[0], list)
                and len(value) == n_masters):
            const, new_d = _rewrite_deltas(value[1:], src_regions, plans,
                                           constants)
            new_value = [value[0] + const] + new_d
        else:
            continue
        raw[name] = new_value
        pd.__dict__.pop(name, None)          # 清掉已转换的缓存值
        touched += 1
    return touched


def reparametrize_cff2(font, mappings, src_tags, dst_tags=None, eps=1e-4):
    """就地把 CFF2 的可变数据重参数化到合并轴空间。

    Returns:
        report = {"var_data": n, "columns": (in, out), "blends": n, "private": n,
                  "changed": bool}
    """
    report = {"var_data": 0, "columns": (0, 0), "blends": 0, "private": 0,
              "changed": False}
    store = cff2_var_store(font)
    if store is None:
        return report
    dst_tags = list(dst_tags if dst_tags is not None else src_tags)
    src_regions = _store_region_supports(store, src_tags)
    plans, new_regions, constants = region_split_plans(
        src_regions, mappings, dst_tags, constant_column=False, eps=eps)

    layout = []
    new_var_data = []
    for vd in store.VarData:
        src_index = list(vd.VarRegionIndex)
        cols = [idx for r in src_index for idx, _w in plans[r]]
        layout.append((src_index, len(src_index)))
        nvd = ot.VarData()
        nvd.VarRegionIndex = cols
        nvd.VarRegionCount = len(cols)
        items = list(getattr(vd, "Item", None) or [])
        nvd.ItemCount = len(items)
        nvd.Item = []
        nvd.NumShorts = 0
        if items:                            # 少数 CFF2 字体 VarData 带行数据
            rows = []
            for item in items:
                row = []
                for c, r in enumerate(src_index):
                    val = item[c] if c < len(item) else 0
                    row.extend(int(round(val * w)) for _idx, w in plans[r])
                rows.append(row)
            nvd.Item = rows
            nvd.NumShorts = _num_shorts(rows, getattr(vd, "NumShorts", 0) or 0)
        report["columns"] = (report["columns"][0] + len(src_index),
                             report["columns"][1] + len(cols))
        new_var_data.append(nvd)

    out = ot.VarStore()
    out.Format = 1
    vrl = ot.VarRegionList()
    vrl.RegionAxisCount = max(1, len(dst_tags))
    vrl.RegionCount = len(new_regions)
    vrl.Region = [_make_region(sup, dst_tags) for sup in new_regions]
    out.VarRegionList = vrl
    out.VarData = new_var_data
    out.VarDataCount = len(new_var_data)
    report["var_data"] = len(new_var_data)

    td = font["CFF2"].cff.topDictIndex[0]
    for obj in _programs(td):
        obj.decompile()
        n_blend = obj.program.count("blend")
        if not n_blend:
            continue
        obj.setProgram(_rewrite_program(obj.program, layout, plans, constants,
                                        None))
        report["blends"] += n_blend
    for pd in _private_dicts(td):
        report["private"] += _rewrite_private(pd, layout, plans, constants)
    set_cff2_var_store(font, out)
    report["changed"] = True
    return report


def is_cff2_variable(font):
    """CFF2 且带可变数据 (VarStore)"""
    return "CFF2" in font and "fvar" in font and cff2_var_store(font) is not None


def merge_cff2_var_stores(main_font, base_font, main_mappings, main_tags,
                          dst_tags):
    """把打底 (已重参数化) 的 CFF2 VarStore 并入主字体, 并平移打底的 vsindex。

    主字体的 VarStore 先按合并轴空间重算 (轴数/范围变了就必须算, 否则
    RegionAxisCount 与 fvar 不一致); 再与打底的 VarData 拼接 (主的在前),
    打底所有 vsindex 引用加上基址偏移。

    Returns:
        {"offset": 打底 VarData 基址, "main_changed": bool, "columns": (主, 打底)}
    """
    from ..tables.varstore import VarStoreUnion

    main_store = cff2_var_store(main_font)
    base_store = cff2_var_store(base_font)
    if main_store is None or base_store is None:
        return {"offset": 0, "main_changed": False, "columns": (0, 0)}
    changed = list(main_tags) != list(dst_tags) or any(
        not m.is_identity() for m in main_mappings.values())
    if changed:
        reparametrize_cff2(main_font, main_mappings, main_tags, dst_tags)
        main_store = cff2_var_store(main_font)
    elif any(tag not in main_tags for tag in dst_tags):
        # 只是尾部新增轴: 直接给每个 region 追加恒定轴 (省一次全量 blend 重写)
        from .vf_axes import _extend_region_list

        _extend_region_list(main_store.VarRegionList,
                            len(dst_tags) - len(main_tags))
    union = VarStoreUnion()
    union.add(main_store)
    offset = union.add(base_store)
    merged_store = union.build()
    set_cff2_var_store(main_font, merged_store)
    # 打底字体自己也换成同一个并集 store —— 它的 vsindex 已经平移到 offset,
    # 若仍留着只有 1 个 VarData 的老 store, 任何"就地求值"的代码 (子集化里的
    # remove_unused_subroutines、绘制) 都会 IndexError。
    set_cff2_var_store(base_font, copy.deepcopy(merged_store))
    offset_cff2_vsindex(base_font, offset)
    return {"offset": offset, "main_changed": changed,
            "columns": (sum(len(vd.VarRegionIndex) for vd in main_store.VarData),
                        sum(len(vd.VarRegionIndex) for vd in base_store.VarData))}


def reparametrize_hvar(font, mappings, src_tags, dst_tags, folded_default):
    """把字体自己的 HVAR ItemVariationStore 重参数化 (VarIdxMap 的 (outer,行)
    引用保持 → 只需换 region/列, 引用不用动)"""
    from .variation_compose import reparametrize_var_store

    if "HVAR" not in font:
        return None
    table = font["HVAR"].table
    store = getattr(table, "VarStore", None)
    if store is None:
        return None
    new_store, report = reparametrize_var_store(store, mappings, src_tags,
                                                dst_tags,
                                                folded_default=folded_default)
    table.VarStore = new_store
    return report


def merge_cff2_hvar(result, base_store, base_map, added_names):
    """把打底的 HVAR 变化并入合并结果 (AdvWidthMap 按字形名重建)。

    打底的 hmtx 静态值已由"合并默认点实例化"折好, 所以传进来的 base_store 应是
    folded_default=True 的重参数化结果 (只保留默认点之外的变化量)。

    VarIdxMap.preWrite 会对**每个**字形取 mapping[g], 所以这里必须为结果字体的
    全部字形给出一项 (缺省 NO_VARIATION_INDEX); 只有真正来自打底的字形才用打底
    的映射 (同名冲突时结果里是主字体的字形)。
    """
    from ..tables.varstore import VarStoreUnion

    if "HVAR" not in result or base_store is None:
        return None
    hvar = result["HVAR"].table
    union = VarStoreUnion()
    union.add(getattr(hvar, "VarStore", None))
    offset = union.add(base_store)
    hvar.VarStore = union.build()
    current = dict(getattr(hvar.AdvWidthMap, "mapping", {}) or {})
    added = set(added_names)
    mapping = {}
    n_added = 0
    for gn in result.getGlyphOrder():
        varidx = None
        if gn in added:
            varidx = base_map.get(gn)
            if varidx is not None and varidx != 0xFFFFFFFF:
                varidx = (((varidx >> 16) + offset) << 16) | (varidx & 0xFFFF)
                n_added += 1
            else:
                varidx = None
        if varidx is None:
            varidx = current.get(gn, 0xFFFFFFFF)
        mapping[gn] = varidx
    new_map = ot.VarIdxMap()
    new_map.mapping = mapping
    hvar.AdvWidthMap = new_map
    return {"offset": offset, "glyphs": n_added}


def offset_cff2_vsindex(font, delta):
    """把 CFF2 里的 vsindex 引用整体偏移 delta (并入别的字体前用)。

    没有显式 vsindex 却含 blend 的程序会**补一条** `vsindex` —— 否则它默认取
    Private DICT 的 vsindex (合并后属于主字体, 语义已不同)。

    Private DICT 自己的 blend 值 (hint 数据) 没有显式 vsindex 可写: fontTools 的
    CFF2 instancer 假定"Private 没有 vsindex 键" (varLib/cff.py 的注释),
    并且它读 `private.vsindex` 时按列表处理 (instancer 的 values[0])。
    因此这里把 Private 的 blend 值**折成默认值** (丢掉 hint 的变化) —— 与
    "丢 hint 可行"的既定取舍一致, 也避开这个坑。
    """
    if not delta:
        return 0
    td = font["CFF2"].cff.topDictIndex[0]
    patched = 0
    for obj in _programs(td):
        obj.decompile()
        program = obj.program
        if "blend" not in program:
            continue
        if "vsindex" in program:
            out = []
            for tok in program:
                if tok == "vsindex":
                    out.append(out.pop() + delta)
                out.append(tok)
            obj.setProgram(out)
        else:
            pd = getattr(obj, "private", None)
            base = getattr(pd, "vsindex", 0) if pd is not None else 0
            obj.setProgram([base + delta, "vsindex"] + list(program))
            patched += 1
    arg_types = _private_arg_types()
    for pd in _private_dicts(td):
        raw = getattr(pd, "rawDict", None)
        if not raw:
            continue
        for name, value in list(raw.items()):
            if not isinstance(value, list) or not value:
                continue
            arg_type = arg_types.get(name)
            if arg_type == "delta" and isinstance(value[0], list):
                raw[name] = [entry[0] for entry in value]     # 折成默认值
                pd.__dict__.pop(name, None)
            elif arg_type == "number" and not isinstance(value[0], list):
                raw[name] = value[0]
                pd.__dict__.pop(name, None)
        raw.pop("vsindex", None)          # 不能给 Private 写 vsindex (见 docstring)
        pd.__dict__.pop("vsindex", None)
    return patched
