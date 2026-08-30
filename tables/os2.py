"""OS/2 表合并"""
from .base import register
from ._strategies import first, max_val, min_val, bitwise_or


def _merge_os2_fs_type(values):
    """最少限制的嵌入权限 (参考 fontTools merge/tables.py)"""
    if not values:
        return 0
    result = bitwise_or(values)
    # Bit 0: Installable. If set, implies Preview & Print, Editable, ReadOnly
    if result & 0x0001:
        result |= 0x000C  # 允许预览打印 + 可编辑
    # Bit 2: No embedding → 清所有嵌入位
    if result & 0x0002:
        for bit in range(0, 10):
            if bit not in (1,):
                result &= ~(1 << bit)
    return result


@register("OS/2")
def merge_os2(merged, main, bases, added=None):
    if "OS/2" not in merged:
        return

    mo = main["OS/2"]
    bos = [b["OS/2"] for b in bases if "OS/2" in b]

    o = merged["OS/2"]
    o.version = max_val([mo.version] + [bo.version for bo in bos])

    if bos:
        o.fsType = _merge_os2_fs_type([mo.fsType] + [bo.fsType for bo in bos])
        o.ulUnicodeRange1 = bitwise_or([mo.ulUnicodeRange1] +
                                       [bo.ulUnicodeRange1 for bo in bos])
        o.ulUnicodeRange2 = bitwise_or([mo.ulUnicodeRange2] +
                                       [bo.ulUnicodeRange2 for bo in bos])
        o.ulUnicodeRange3 = bitwise_or([mo.ulUnicodeRange3] +
                                       [bo.ulUnicodeRange3 for bo in bos])
        o.ulUnicodeRange4 = bitwise_or([mo.ulUnicodeRange4] +
                                       [bo.ulUnicodeRange4 for bo in bos])
        o.ulCodePageRange1 = bitwise_or([mo.ulCodePageRange1] +
                                        [bo.ulCodePageRange1 for bo in bos])
        o.ulCodePageRange2 = bitwise_or([mo.ulCodePageRange2] +
                                        [bo.ulCodePageRange2 for bo in bos])
        o.sTypoAscender = max_val([mo.sTypoAscender] +
                                  [bo.sTypoAscender for bo in bos])
        o.sTypoDescender = min_val([mo.sTypoDescender] +
                                   [bo.sTypoDescender for bo in bos])
        o.sTypoLineGap = max_val([mo.sTypoLineGap] +
                                 [bo.sTypoLineGap for bo in bos])
        o.usWinAscent = max_val([mo.usWinAscent] +
                                [bo.usWinAscent for bo in bos])
        o.usWinDescent = max_val([mo.usWinDescent] +
                                 [bo.usWinDescent for bo in bos])
        o.fsFirstCharIndex = min_val([mo.fsFirstCharIndex] +
                                     [bo.fsFirstCharIndex for bo in bos])
        o.fsLastCharIndex = max_val([mo.fsLastCharIndex] +
                                    [bo.fsLastCharIndex for bo in bos])
        o.sxHeight = max_val([mo.sxHeight] + [bo.sxHeight for bo in bos
                                              if bo.version >= 2])
        o.sCapHeight = max_val([mo.sCapHeight] + [bo.sCapHeight for bo in bos
                                                  if bo.version >= 2])

    o.panose = mo.panose
    o.fsSelection = mo.fsSelection
    o.achVendID = mo.achVendID
