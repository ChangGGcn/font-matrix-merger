# -*- coding: utf-8 -*-
"""CFF2 分片并集 — 同源 CFF2 可变字体的 unicode-range 分片合并

CFF2 的逐字形数据在 CharStrings, 用 blend + vsindex 引用 CFF2 自己的
ItemVariationStore; 字形还通过 FDSelect 关联 FDArray 的 Private
(hint/blend 数据 + 局部子程序)。CFF2 **没有 charset 表**: 字形序由外层
(maxp/post/cmap) 决定, 编译时按 top.charset 的顺序取 CharStrings[name]
(见 fontTools cffLib.TopDictCompiler.getChildren), 所以并集里只要让
charset / FDSelect.gidArray 与字形序同步即可。

同源分片 (同一源字体 pyftsubset 切出) 的 FDArray / VarStore / GlobalSubrs
逐一相同 —— 这是能"零重定位"并集的前提, 本模块用结构签名严格校验:
  * FDArray: 每个 FD 的 Private rawDict + 局部子程序程序表;
  * GlobalSubrs: 每个子程序的程序表;
  * VarStore: region 表 + 每个 VarData 的 (VarRegionIndex, ItemCount, 增量表)。

三者任一不同, 就必须做 VarData/子程序基址重定位 + Private blend 的 vsindex
重写; 那属于另一条实现路径, 本模块**明确拒绝**而不是产出坏字体
(IncompatibleCFF2Error), 由调用方决定是否退回静态路径。

参考实现: fontTools.cffLib (CharStrings/FDSelect/VarStoreData 官方 API),
fontTools.subset.cff (desubroutinize 的用法), CFF2 规范 (vsindex/blend 语义)。
"""
import copy

from fontTools.cffLib import VarStoreData


class IncompatibleCFF2Error(ValueError):
    """分片之间 CFF2 结构不一致, 无法零重定位并集"""


def _program_key(charstring):
    """T2CharString 的程序表 (数字/运算符列表)"""
    try:
        return tuple(charstring.program)
    except AttributeError:
        return ("<no-program>",)


def subrs_signature(index):
    """子程序索引签名: 每个子程序的程序表"""
    if index is None:
        return ()
    return tuple(_program_key(cs) for cs in index)


def _value_key(value, depth=0):
    """Private rawDict 值的可比较签名 (容忍 blend charstring / 嵌套列表)"""
    if depth > 8:
        return "<deep>"
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_value_key(v, depth + 1) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _value_key(v, depth + 1)) for k, v in value.items()))
    if hasattr(value, "program"):
        return ("program", tuple(value.program))
    if hasattr(value, "rawDict"):
        return ("dict", _value_key(value.rawDict, depth + 1))
    return repr(value)


def fdarray_signature(top):
    """FDArray 签名: 每个 FD 的 (Private, 局部子程序)"""
    fds = []
    for fd in getattr(top, "FDArray", []) or []:
        priv = getattr(fd, "Private", None)
        if priv is None:
            fds.append(None)
            continue
        fds.append((_value_key(priv.rawDict or {}),
                    subrs_signature(getattr(priv, "Subrs", None))))
    return tuple(fds)


def varstore_signature(var_store_data):
    """ItemVariationStore 签名 (None 表示无)"""
    if var_store_data is None:
        return None
    ot_vs = getattr(var_store_data, "otVarStore", None)
    if ot_vs is None:
        return None
    regions = tuple(
        tuple((a.StartCoord, a.PeakCoord, a.EndCoord) for a in region.VarRegionAxis)
        for region in ot_vs.VarRegionList.Region)
    var_data = tuple(
        (tuple(vd.VarRegionIndex), getattr(vd, "VarRegionCount", None),
         _deltas_key(vd))
        for vd in ot_vs.VarData)
    return (ot_vs.VarRegionList.RegionAxisCount, regions, var_data)


def _deltas_key(var_data):
    """VarData 的增量表签名。

    CFF2 的 VarStore 通常只用来提供 region 定义 (blend 的增量直接写在
    charstring 里), 此时 Item 为空; 但仍要参与比较, 以防被重构过。
    不同 fontTools 版本里该字段叫 Item 或 ItemVariationData。
    """
    items = getattr(var_data, "Item", None)
    if items is None:
        items = getattr(var_data, "ItemVariationData", None)
    if not items:
        return ()
    return tuple(tuple(x) if isinstance(x, (list, tuple)) else x for x in items)


def fd_key(fd):
    """单个 FD 的签名 (Private rawDict + 局部子程序)"""
    priv = getattr(fd, "Private", None)
    if priv is None:
        return None
    return (_value_key(priv.rawDict or {}),
            subrs_signature(getattr(priv, "Subrs", None)))


class FDUnion:
    """FDArray 并集: 内容相同的 FD 复用, 不同的追加。

    pyftsubset 会按分片实际用到的 FD 剪裁 FDArray (CJK 源字体常有十几个 FD,
    分片只保留用到的那几个), 所以分片之间 FD 数量/编号都可能不同。
    Lookup 侧的 FDSelect 是**下标**, 因此必须给出 局部 FD → 合并 FD 的映射。
    """

    def __init__(self, merged_top):
        self.top = merged_top
        self.keys = [fd_key(fd) for fd in (getattr(merged_top, "FDArray", []) or [])]
        self.var_store = getattr(merged_top, "VarStore", None)

    def add(self, base_top):
        """并入打底 FDArray, 返回 局部索引 → 合并索引 的列表"""
        remap = []
        for fd in (getattr(base_top, "FDArray", []) or []):
            key = fd_key(fd)
            idx = None
            for i, k in enumerate(self.keys):
                if k == key:
                    idx = i
                    break
            if idx is None:
                new_fd = copy.deepcopy(fd)
                priv = getattr(new_fd, "Private", None)
                if priv is not None and self.var_store is not None:
                    # Private 的 blend 也要用合并字体的 VarStore 对象
                    # (instancer 断言 private.vstore.otVarStore is <字体 VarStore>)
                    priv.vstore = self.var_store
                self.top.FDArray.append(new_fd)
                idx = len(self.keys)
                self.keys.append(key)
            remap.append(idx)
        return remap


def cff2_key(font):
    """字体 CFF2 结构签名 (GlobalSubrs, VarStore) —— FDArray 由 FDUnion 处理"""
    cff = font["CFF2"].cff
    top = cff.topDictIndex[0]
    return (subrs_signature(cff.GlobalSubrs),
            varstore_signature(getattr(top, "VarStore", None)))


def check_cff2_compatible(main_font, base_font):
    """校验打底分片能否并入主分片 (FDArray 差异可处理, VarStore/子程序不可)。

    VarStore 必须结构相同 (同源分片 pyftsubset 不会重构它): CharStrings 与
    Private 里的 blend 增量都按 vsindex/VarData 编号引用它, 编号一变就要
    重写所有 blend 数据, 属于另一条实现路径 —— 这里明确拒绝。

    Returns:
        (ok: bool, reason: str)
    """
    if "CFF2" not in main_font or "CFF2" not in base_font:
        return False, "主/打底不是 CFF2"
    mk, bk = cff2_key(main_font), cff2_key(base_font)
    for i, name in enumerate(("GlobalSubrs", "VarStore")):
        if mk[i] != bk[i]:
            return False, ("%s 结构不一致 (分片的 CFF2 被重构过: 需要 "
                           "VarData/子程序基址重定位)" % name)
    return True, ""


def copy_glyphs(merged_font, base_font, pairs, fd_map=None):
    """把打底 CFF2 的指定字形复制进合并字体 (结构已验证一致, 无重定位)。

    Args:
        merged_font: 目标 TTFont (就地修改, 已含主分片)
        base_font: 打底 TTFont
        pairs: [(打底字形名, 合并后字形名)] —— 顺序即字形序 (别名/去重已定)
        fd_map: 打底 FD 索引 → 合并 FD 索引 (None = 索引不变)

    Returns:
        实际复制的最终字形名列表
    """
    merged_cff = merged_font["CFF2"].cff
    merged_top = merged_cff.topDictIndex[0]
    base_top = base_font["CFF2"].cff.topDictIndex[0]
    base_order = base_top.charset
    base_gid = {gn: i for i, gn in enumerate(base_order)}
    base_fdselect = base_top.FDSelect.gidArray

    merged_cs = merged_top.CharStrings
    indexed = getattr(merged_cs, "charStringsAreIndexed", False)

    added = []
    for old, new in pairs:
        if old not in base_gid:
            continue
        fd_index = base_fdselect[base_gid[old]]
        if fd_map:
            fd_index = fd_map[fd_index] if fd_index < len(fd_map) else 0
        cs = copy.deepcopy(base_top.CharStrings[old])
        cs.globalSubrs = merged_cff.GlobalSubrs
        # 关键: 复制的 charstring 必须挂到**合并字体**的 FD Private 上。
        # 否则它的 private.vstore 仍指向打底字体的 VarStore 对象, 而
        # fontTools 的 instancer 断言 cs.private.vstore.otVarStore is
        # <字体的 VarStore> —— 结构一致但对象不同会直接 assert 失败。
        fds = getattr(merged_top, "FDArray", None)
        if fds and fd_index < len(fds) and getattr(fds[fd_index], "Private", None) is not None:
            cs.private = fds[fd_index].Private
        if indexed:
            # decompile 出来的 CharStrings 是 (名 → 索引) + 索引表;
            # 在索引表尾部追加即新字形 (编译器按 charset 顺序按名取)
            merged_cs.charStrings[new] = len(merged_cs.charStringsIndex)
            merged_cs.charStringsIndex.append(cs)
        else:
            merged_cs.charStrings[new] = cs
        merged_top.FDSelect.append(base_fdselect[base_gid[old]])
        added.append(new)
    return added


def sync_glyph_order(font):
    """把 CFF2 的 charset / FDSelect 与当前字形序对齐 (编译前必须做)。"""
    top = font["CFF2"].cff.topDictIndex[0]
    order = font.getGlyphOrder()
    top.charset = list(order)
    fdselect = top.FDSelect
    if len(fdselect) != len(order):
        raise IncompatibleCFF2Error(
            "FDSelect 长度 %d 与字形数 %d 不一致" % (len(fdselect), len(order)))
    return font


def set_var_store(top, ot_var_store):
    """把 otTables.VarStore 写回 CFF2 topDict (VarStoreData 会按需重新编译)"""
    if ot_var_store is None:
        return
    top.VarStore = VarStoreData(otVarStore=ot_var_store)
