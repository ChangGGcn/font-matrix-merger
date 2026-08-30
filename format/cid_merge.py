"""CID 字体合并: 通过 CID 重映射解决双 CID 名称冲突

核心思路 (参考 Adobe CIDKeyedUFOGuide):
  CID-keyed UFO 通过 com.adobe.type.postscriptCIDMap 将任意字形名映射到 CID 号。
  当两个 Adobe-Identity-0 CID 字体 CIDs 重叠时, 将打底字体的 CID 号偏移, 避免冲突。
"""
import copy
from fontTools.ttLib import TTFont
from io import BytesIO
from ..utils.detect import is_cff


def _has_ros(font):
    if "CFF " not in font: return False
    td = font["CFF "].cff.topDictIndex[0]
    return hasattr(td, "ROS") and td.ROS is not None


def _get_max_cid(font):
    """获取字体中最大的 CID 号"""
    td = font["CFF "].cff.topDictIndex[0]
    max_cid = 0
    for gn in td.charset:
        if gn.startswith("cid"):
            try:
                cid = int(gn[3:])
                max_cid = max(max_cid, cid)
            except ValueError:
                pass
    return max_cid


def shift_cid_range(font, offset):
    """将 CID 字体的所有 CID 号偏移 offset, 避免与另一个 CID 字体重叠

    修改: charset名, CharStrings键, glyphOrder, hmtx键, cmap映射
    保持: 字形轮廓数据不变, ROS不变
    """
    if not _has_ros(font):
        return font

    td = font["CFF "].cff.topDictIndex[0]
    order = font.getGlyphOrder()

    def rename(gn):
        if gn.startswith("cid"):
            try:
                n = int(gn[3:])
                return f"cid{n + offset:05d}"
            except ValueError:
                pass
        return gn

    mapping = {gn: rename(gn) for gn in order}
    new_order = [mapping[gn] for gn in order]

    # CharStrings
    cs = td.CharStrings
    cs.charStrings = {mapping.get(k, k): v for k, v in cs.charStrings.items()}

    # charset
    td.charset = new_order
    font.setGlyphOrder(new_order)

    # hmtx
    if "hmtx" in font:
        font["hmtx"].metrics = {mapping.get(k, k): v
                                for k, v in font["hmtx"].metrics.items()}
    # vmtx (CFF CID 纵横字体常见)
    if "vmtx" in font:
        font["vmtx"].metrics = {mapping.get(k, k): v
                                for k, v in font["vmtx"].metrics.items()}

    # cmap
    for table in font["cmap"].tables:
        if hasattr(table, "cmap") and table.cmap:
            pass  # cmap maps codepoint→name, names already updated

    if "maxp" in font:
        font["maxp"].numGlyphs = len(new_order)

    print(f"  [CID偏移] +{offset} ({len(order)} glyphs)")
    return font


def _materialize_charstrings(font):
    """将 indexed CharStrings (charStringsAreIndexed=1) 转为非 indexed 对象字典。

    fontTools 从文件读 CFF 时 charStrings 存的是 index (int),
    __getitem__ 会把 index 转成 T2CharString 对象。
    直接向 charStrings 字典写入对象会导致 getItemAndSelector 用对象当索引。
    物化时把每个对象的 fdSelectIndex 与 Private 绑定 (编译时用于重建 FDSelect)。
    """
    td = font["CFF "].cff.topDictIndex[0]
    cs = td.CharStrings
    if not cs.charStringsAreIndexed:
        return
    order = font.getGlyphOrder()
    # 从 indexed fdSelect 获取 gid→fd 映射
    fd_map = None
    csi = getattr(cs, "charStringsIndex", None)
    if csi is not None and getattr(csi, "fdSelect", None) is not None:
        fd_map = list(csi.fdSelect)
    objs = {}
    for i, gn in enumerate(order):
        try:
            obj = cs[gn]
        except Exception:
            obj = cs.charStrings[gn]
        # 绑定 fd + Private (编译时 getChildren 会读 fdSelectIndex)
        if fd_map is not None and i < len(fd_map):
            fd = fd_map[i]
            obj.fdSelectIndex = fd
            try:
                obj.private = td.FDArray[fd].Private
            except Exception:
                pass
        objs[gn] = obj
    cs.charStrings = objs
    cs.charStringsAreIndexed = 0
    # fdSelect 重绑定到非 indexed 形态 (getItemAndSelector 需要)
    cs.fdSelect = fd_map if fd_map is not None else None


def merge_cid_fonts(main_font, base_font, added_glyphs):
    """合并两个 CID 字体: 直接复制 CharString 对象 (绕过 TTX)

    适用于双 CID 字体, 打底 CID 已偏移以避免名称冲突。
    """
    # Desubroutinize both for safe charstring copying
    main_font["CFF "].cff.desubroutinize()
    base_font["CFF "].cff.desubroutinize()

    # 物化 charstrings (indexed → 对象字典), 复制对象才安全
    _materialize_charstrings(main_font)
    _materialize_charstrings(base_font)

    main_cs = main_font["CFF "].cff[0].CharStrings
    base_cs = base_font["CFF "].cff[0].CharStrings
    main_td = main_font["CFF "].cff[0]
    base_td = base_font["CFF "].cff[0]

    # 直接复制 CharString 对象 (与 fontTools Merger 相同的方式)
    copied = 0
    for gn in added_glyphs:
        if gn in base_cs.charStrings and gn not in main_cs.charStrings:
            main_cs.charStrings[gn] = base_cs.charStrings[gn]
            copied += 1

    # 更新 charset (合并)
    main_order = list(main_font.getGlyphOrder())
    for gn in added_glyphs:
        if gn not in main_order:
            main_order.append(gn)
    main_font.setGlyphOrder(main_order)
    main_td.charset = main_order
    main_font["maxp"].numGlyphs = len(main_order)

    # 更新 hmtx
    for gn in added_glyphs:
        if "hmtx" in base_font and gn in base_font["hmtx"].metrics:
            if gn not in main_font["hmtx"].metrics:
                main_font["hmtx"].metrics[gn] = base_font["hmtx"].metrics[gn]

    # 更新 vmtx (纵向度量): 与 glyphOrder 对齐, 缺失字形补默认值 (0, 0)
    if "vmtx" in main_font:
        for gn in added_glyphs:
            if gn not in main_font["vmtx"].metrics:
                if "vmtx" in base_font and gn in base_font["vmtx"].metrics:
                    main_font["vmtx"].metrics[gn] = base_font["vmtx"].metrics[gn]
                else:
                    main_font["vmtx"].metrics[gn] = main_font["vmtx"].metrics.get(
                        ".notdef", (0, 0)
                    ) if ".notdef" in main_font["vmtx"].metrics else (0, 0)

    # 更新 cmap
    for table in base_font["cmap"].tables:
        if hasattr(table, "cmap") and table.cmap:
            for cp, gn in table.cmap.items():
                if gn in added_glyphs:
                    for rt in main_font["cmap"].tables:
                        if (hasattr(rt, "cmap") and rt.format == table.format
                                and cp not in rt.cmap):
                            rt.cmap[cp] = gn

    print(f"  [CID直接合并] 复制 {copied} 个字形")
    return main_font


def cid_ufo_style_merge(main_font, base_font):
    """仿 UFO CIDMap 重映射合并:
    1. 将 base 的 CID 号偏移到 main 的 CID 范围之后
    2. 直接复制 CharString 对象 (无需 TTX)
    """
    max_cid_main = _get_max_cid(main_font)
    offset = max_cid_main + 100  # 留 100 个 CID 的间隙

    base_shifted = copy.deepcopy(base_font)
    shift_cid_range(base_shifted, offset)

    # 冲突检测 (使用偏移后的名称)
    from ..core.conflict import resolve_conflicts
    conflicts = resolve_conflicts(main_font, base_shifted)
    main_names = set(main_font.getGlyphOrder())
    to_add = [gn for gn in base_shifted.getGlyphOrder()
              if gn not in conflicts and gn not in main_names]

    print(f"  [CID合并] 主字体 max CID={max_cid_main}, 打底偏移+{offset}")
    print(f"  [CID合并] 冲突: {len(conflicts)}, 新增: {len(to_add)}")

    if not to_add:
        return main_font

    result = copy.deepcopy(main_font)
    result = merge_cid_fonts(result, base_shifted, to_add)

    # 合并后转 name-keyed: 移除 ROS, CID→uniXXXX (避免 CID 编译问题)
    from .cid_convert import cid_to_name
    result = cid_to_name(result)

    # save→reload 重建所有表, 消除 deepcopy/物化后的对象状态不一致
    # (hmtx/vmtx 键集与 glyphOrder 必须以编译器视图完全一致)
    stream = BytesIO()
    try:
        result.save(stream)
        stream.seek(0)
        result = TTFont(stream, recalcTimestamp=False, recalcBBoxes=False)
    except Exception as e:
        print(f"  [CID合并] save→reload 失败, 保留内存态: {e}")

    return result
