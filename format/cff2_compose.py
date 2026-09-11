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


def offset_cff2_vsindex(font, delta):
    """把 CFF2 里的 vsindex 引用整体偏移 delta (并入别的字体前用)。

    没有显式 vsindex 却含 blend 的程序会**补一条** `vsindex` —— 否则它默认取
    Private DICT 的 vsindex (合并后属于主字体, 语义已不同)。
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
    for pd in _private_dicts(td):
        raw = getattr(pd, "rawDict", None)
        if not raw:
            continue
        v = raw.get("vsindex", 0)
        if isinstance(v, list):
            v = v[0]
        raw["vsindex"] = v + delta
        pd.__dict__.pop("vsindex", None)
    return patched
