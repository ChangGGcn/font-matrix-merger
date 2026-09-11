"""可变字体 → 静态实例提取 (含 CFF2→CFF 转换 + 重叠轮廓合并)

使用 fontTools 内置的 _convertCFF2ToCFF 正确处理 CID/FDSelect。
"""
import copy
from io import BytesIO
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from ..utils.detect import is_variable


def variable_to_static(font, remove_overlaps=False):
    """从可变字体生成静态实例。CFF2 自动转换为 CFF (支持 CID)。

    Args:
        font: 可变字体 (TTFont)
        remove_overlaps: 是否布尔合并重叠轮廓。
            默认 False —— 布尔并集需要 pathops 依赖且会**改写轮廓**,
            对"保真合并/对照验证"类任务会引入偏差;
            仅在确有渲染问题 (重叠区域填充异常) 时显式开启。
    """
    if not is_variable(font):
        return copy.deepcopy(font)

    axes = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
    try:
        # VORG/VVAR 警告抑制: 我们实例化到"默认轴位置", VORG 是静态表,
        # 其记录值在默认位置无需变化 — 警告属保守提示, 功能上无影响。
        # 只过滤该条消息 (保留其他日志)。
        import logging
        _VORG_MSG = "VORG table not yet updated"
        _orig_filter = None
        logger = logging.getLogger("fontTools.varLib.instancer")
        if hasattr(logger, "filters"):
            class _VorgFilter(logging.Filter):
                def filter(self, record):
                    return _VORG_MSG not in record.getMessage()
            _orig_filter = logger.filters
            logger.filters = [_VorgFilter()] + list(logger.filters)
        try:
            result = instantiateVariableFont(font, axes, inplace=False)
        finally:
            if _orig_filter is not None:
                logger.filters = _orig_filter
    except Exception as e:
        print(f"  [警告] 实例化失败: {e}")
        return copy.deepcopy(font)

    _had_cff2 = "CFF2" in result

    # CFF2 → CFF 转换 (使用 fontTools 内置函数，支持 CID/FDSelect)
    if _had_cff2:
        try:
            from fontTools.cffLib.CFF2ToCFF import _convertCFF2ToCFF
            from fontTools.ttLib.tables.C_F_F_ import table_C_F_F_

            _convertCFF2ToCFF(result["CFF2"].cff, result)
            cff_data = result["CFF2"].cff
            del result["CFF2"]
            cff_table = table_C_F_F_("CFF ")
            cff_table.cff = cff_data
            result["CFF "] = cff_table

            # 清理 CFF2/VF 专用表 (VORG 保留: 它是静态竖排原点, CFF 也使用;
            # 默认轴位置实例化时 VORG 值不变, 删除会导致 CJK 竖排原点丢失)
            for tag in ("HVAR", "VVAR", "MVAR", "STAT",
                        "fvar", "avar", "gvar", "cvar"):
                if tag in result:
                    del result[tag]

            result.recalcBBoxes = False
            print(f"  [CFF2→CFF] 转换完成 ({len(result.getGlyphOrder())} glyphs)")
        except Exception as e:
            print(f"  [警告] CFF2→CFF 转换失败: {e}")
            import traceback; traceback.print_exc()

    # CFF2→CFF 转换后表间名称不一致 (CID vs name-keyed): 需要 save→reload
    # 消除不一致 (参考 fontTools CFF2ToCFF CLI 模式)。与是否布尔合并无关。
    if _had_cff2:
        try:
            stream = BytesIO()
            result.save(stream)
            stream.seek(0)
            result = TTFont(stream, recalcTimestamp=False, recalcBBoxes=False)
        except Exception as e:
            print(f"  [警告] CFF2→CFF 归一失败: {e}")

    # 布尔合并重叠轮廓 (解决插值后重叠区域的渲染问题; 会改写轮廓, 默认关闭)
    if remove_overlaps:
        try:
            from fontTools.ttLib.removeOverlaps import removeOverlaps

            removeOverlaps(result, ignoreErrors=True)
            print(f"  [重叠合并] 完成 ({len(result.getGlyphOrder())} glyphs)")
        except Exception as e:
            print(f"  [警告] 重叠合并失败: {e}")

    return result
