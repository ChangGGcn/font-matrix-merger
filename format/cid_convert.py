"""CID ↔ Name-keyed CFF 字体转换

使用 Adobe-Identity-0 ROS，保持 1:1 字形映射。
"""
import copy
from ..utils.detect import is_cff


def _has_ros(font):
    """检查 CFF 字体是否为 CID-keyed (有 ROS)"""
    if "CFF " not in font:
        return False
    td = font["CFF "].cff.topDictIndex[0]
    return hasattr(td, "ROS") and td.ROS is not None


def _is_cid_font(font):
    return is_cff(font) and _has_ros(font)


def name_to_cid(font):
    """将 name-keyed CFF 转为 CID-keyed (Adobe-Identity-0)

    所有字形重命名为 cid00001, cid00002, ... 格式。
    """
    if not is_cff(font) or _has_ros(font):
        return copy.deepcopy(font)  # 已经是 CID 或非 CFF

    result = copy.deepcopy(font)
    order = result.getGlyphOrder()
    cff_td = result["CFF "].cff.topDictIndex[0]

    # 1. 构建 名称↔CID 映射
    name_to_cid_name = {}
    cid_to_name = {}
    for i, gn in enumerate(order):
        cid_name = "cid" + str(i).zfill(5) if i > 0 else ".notdef"
        name_to_cid_name[gn] = cid_name
        cid_to_name[cid_name] = gn

    # 2. 重命名 CharStrings 键
    cs = cff_td.CharStrings
    new_cs = {}
    for gn, cs_obj in cs.charStrings.items():
        new_key = name_to_cid_name.get(gn, gn)
        new_cs[new_key] = cs_obj
    cs.charStrings = new_cs

    # 3. 更新 charset
    cff_td.charset = [name_to_cid_name.get(gn, gn) for gn in order]

    # 4. 设置 ROS (写入 rawDict, 与 __getattr__ 机制一致)
    cff_td.ROS = ("Adobe", "Identity", 0)
    cff_td.rawDict["ROS"] = ("Adobe", "Identity", 0)

    # 5. 创建 FDSelect (所有字形 → fd 0, 简化)
    if not hasattr(cff_td, "FDSelect") or cff_td.FDSelect is None:
        from fontTools.cffLib import FDSelect
        fd_sel = FDSelect()
        fd_sel.format = 0
        fd_sel.gidArray = [0] * len(order)
        cff_td.FDSelect = fd_sel

    # 6. 确保有 FDArray (单 FontDict)
    if not hasattr(cff_td, "FDArray") or cff_td.FDArray is None:
        from fontTools.cffLib import FontDict, PrivateDict
        fd = FontDict()
        fd.Private = cff_td.Private
        if not hasattr(cff_td, 'FDArray') or cff_td.FDArray is None:
            from fontTools.cffLib import FDArrayIndex
            cff_td.FDArray = FDArrayIndex()
        cff_td.FDArray.append(fd)
        cff_td.Private = PrivateDict()

    # 7. 更新 glyphOrder, hmtx, cmap, post
    new_order = [name_to_cid_name.get(gn, gn) for gn in order]
    result.setGlyphOrder(new_order)

    if "hmtx" in result:
        old_metrics = dict(result["hmtx"].metrics)
        result["hmtx"].metrics = {
            name_to_cid_name.get(gn, gn): metrics
            for gn, metrics in old_metrics.items()
        }
    if "vmtx" in result:
        old_metrics = dict(result["vmtx"].metrics)
        result["vmtx"].metrics = {
            name_to_cid_name.get(gn, gn): metrics
            for gn, metrics in old_metrics.items()
        }

    for table in result["cmap"].tables:
        if hasattr(table, "cmap") and table.cmap:
            for cp in list(table.cmap.keys()):
                gn = table.cmap[cp]
                new_gn = name_to_cid_name.get(gn, gn)
                table.cmap[cp] = new_gn
        # format 14 (UVS): uvsDict 中 (uv, glyphName) / (uv, None) 二元组
        if getattr(table, "format", None) == 14 and hasattr(table, "uvsDict"):
            for sel, entries in list(table.uvsDict.items()):
                new_entries = []
                for e in entries:
                    if isinstance(e, tuple) and e[1] is not None:
                        new_entries.append((e[0], name_to_cid_name.get(e[1], e[1])))
                    else:
                        new_entries.append(e)
                table.uvsDict[sel] = new_entries

    # post 表: 名字变了，转 format 3.0 (不存字形名)
    if "post" in result:
        result["post"].formatType = 3.0

    # 更新 maxp
    if "maxp" in result:
        result["maxp"].numGlyphs = len(new_order)

    # 存储反向映射供后续使用
    result._cid_to_name = cid_to_name
    result._name_to_cid = name_to_cid_name

    print(f"  [name→CID] 转换完成 ({len(order)} glyphs, ROS=Adobe-Identity-0)")
    return result


def cid_to_name(font):
    """将 CID-keyed CFF 转回 name-keyed (仅限单 FD 字体, 通过 cmap 反查名称)"""
    if not _is_cid_font(font):
        return copy.deepcopy(font)  # 不是 CID 或非 CFF

    result = copy.deepcopy(font)
    cff_td = result["CFF "].cff.topDictIndex[0]
    order = result.getGlyphOrder()

    # 从 cmap 反查: 对每个 CID, 找其 Unicode → 生成 uniXXXX 名称
    # 如果没有 Unicode 映射, 保留 CID 名称
    cp_to_cid = {}
    for table in result["cmap"].tables:
        if hasattr(table, "cmap") and table.cmap:
            for cp, gn in table.cmap.items():
                if gn in order:
                    cp_to_cid[cp] = gn

    cid_to_uni = {}
    for cp, cid_name in cp_to_cid.items():
        uni_name = f"uni{cp:04X}"
        cid_to_uni[cid_name] = uni_name

    # 确保唯一性
    used = set()
    final_names = {}
    for cid_name in order:
        if cid_name in cid_to_uni:
            base = cid_to_uni[cid_name]
            name = base
            n = 1
            while name in used:
                name = f"{base}.{n}"
                n += 1
            final_names[cid_name] = name
            used.add(name)
        else:
            final_names[cid_name] = cid_name  # 保留原名

    # 重命名 CharStrings
    cs = cff_td.CharStrings
    new_cs = {}
    for gn, cs_obj in cs.charStrings.items():
        new_cs[final_names.get(gn, gn)] = cs_obj
    cs.charStrings = new_cs

    # 更新 charset
    cff_td.charset = [final_names.get(gn, gn) for gn in order]

    # 移除 ROS (rawDict + 实例属性都必须删, 否则 __getattr__ 会读回)
    if "ROS" in cff_td.rawDict:
        del cff_td.rawDict["ROS"]
    vars(cff_td).pop("ROS", None)

    # 移除 FDSelect/FDArray, 合并 Private 回 TopDict
    if hasattr(cff_td, 'FDArray') and cff_td.FDArray and len(cff_td.FDArray) > 0:
        if hasattr(cff_td.FDArray[0], 'Private') and cff_td.FDArray[0].Private:
            cff_td.Private = cff_td.FDArray[0].Private

    if "FDSelect" in cff_td.rawDict:
        del cff_td.rawDict["FDSelect"]
    vars(cff_td).pop("FDSelect", None)
    if "FDArray" in cff_td.rawDict:
        del cff_td.rawDict["FDArray"]
    vars(cff_td).pop("FDArray", None)

    new_order = [final_names.get(gn, gn) for gn in order]
    result.setGlyphOrder(new_order)

    if "hmtx" in result:
        old_m = dict(result["hmtx"].metrics)
        result["hmtx"].metrics = {
            final_names.get(gn, gn): metrics
            for gn, metrics in old_m.items()
        }
    if "vmtx" in result:
        old_m = dict(result["vmtx"].metrics)
        result["vmtx"].metrics = {
            final_names.get(gn, gn): metrics
            for gn, metrics in old_m.items()
        }

    for table in result["cmap"].tables:
        if hasattr(table, "cmap") and table.cmap:
            for cp in list(table.cmap.keys()):
                gn = table.cmap[cp]
                table.cmap[cp] = final_names.get(gn, gn)
        # format 14 (UVS): uvsDict 中 (uv, glyphName) / (uv, None) 二元组
        if getattr(table, "format", None) == 14 and hasattr(table, "uvsDict"):
            for sel, entries in list(table.uvsDict.items()):
                new_entries = []
                for e in entries:
                    if isinstance(e, tuple) and e[1] is not None:
                        new_entries.append((e[0], final_names.get(e[1], e[1])))
                    else:
                        new_entries.append(e)
                table.uvsDict[sel] = new_entries

    if "post" in result:
        result["post"].formatType = 3.0

    if "maxp" in result:
        result["maxp"].numGlyphs = len(new_order)

    print(f"  [CID→name] 转换完成 ({len(order)} glyphs)")
    return result


def ensure_cid_format(font):
    """确保字体为 CID-keyed 格式"""
    if _is_cid_font(font):
        return font
    if is_cff(font):
        return name_to_cid(font)
    return font  # TTF/glyf, 无需转换


def ensure_name_format(font):
    """确保字体为 name-keyed 格式"""
    if not _is_cid_font(font):
        return font
    return cid_to_name(font)
