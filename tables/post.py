"""post 表合并"""
from .base import register
from ._strategies import first, max_val, min_val


@register("post")
def merge_post(merged, main, bases, added=None):
    if "post" not in merged:
        return

    mp = main["post"]
    bps = [b["post"] for b in bases if "post" in b]

    p = merged["post"]
    # 主字体的格式特定值保留
    p.underlinePosition = mp.underlinePosition
    p.underlineThickness = mp.underlineThickness

    if bps:
        p.isFixedPitch = min_val([mp.isFixedPitch] +
                                 [bp.isFixedPitch for bp in bps])
        p.minMemType42 = max_val([mp.minMemType42] +
                                 [bp.minMemType42 for bp in bps])
        p.maxMemType42 = 0
        p.minMemType1 = max_val([mp.minMemType1] +
                                [bp.minMemType1 for bp in bps])
        p.maxMemType1 = 0
