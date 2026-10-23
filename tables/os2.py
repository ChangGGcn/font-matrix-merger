"""OS/2 表合并：设计身份以主字体为准，派生字段按实际数据重算。"""
import copy

from .base import register
from ._strategies import bitwise_or
from .metadata_recalc import _recalc_os2


def _merge_os2_fs_type(values):
    """保持既有嵌入权限合并策略，不在元数据修复中改变用户策略。"""
    if not values:
        return 0
    result = bitwise_or(values)
    if result & 0x0001:
        result |= 0x000C
    if result & 0x0002:
        for bit in range(0, 10):
            if bit != 1:
                result &= ~(1 << bit)
    return result


@register("OS/2")
def merge_os2(merged, main, bases, added=None):
    """就地合并 OS/2；保留主表版本，不凭打底版本制造缺字段。"""
    if "OS/2" not in merged or "OS/2" not in main:
        return
    mo = main["OS/2"]
    alive = set(merged.getGlyphOrder())
    included = alive if added is None else alive & set(added)
    bos = [base["OS/2"] for base in bases if "OS/2" in base
           and included & (set(base.getGlyphOrder()) -
                           set(main.getGlyphOrder()))]
    table = merged["OS/2"]
    if bos:
        table.fsType = _merge_os2_fs_type([mo.fsType] +
                                         [bo.fsType for bo in bos])
        for field in ("sTypoAscender", "sTypoLineGap",
                      "usWinAscent", "usWinDescent"):
            setattr(table, field, max([getattr(mo, field)] +
                                     [getattr(bo, field) for bo in bos]))
        table.sTypoDescender = min([mo.sTypoDescender] +
                                   [bo.sTypoDescender for bo in bos])
        table.usFirstCharIndex = min([mo.usFirstCharIndex] +
                                     [bo.usFirstCharIndex for bo in bos])
        table.usLastCharIndex = max([mo.usLastCharIndex] +
                                    [bo.usLastCharIndex for bo in bos])
        if table.version >= 2:
            for field in ("sxHeight", "sCapHeight"):
                values = [getattr(source, field) for source in [mo] + bos
                          if hasattr(source, field)]
                if values:
                    setattr(table, field, max(values))
    table.panose = copy.deepcopy(mo.panose)
    table.fsSelection = mo.fsSelection
    table.achVendID = mo.achVendID
    _recalc_os2(merged)
