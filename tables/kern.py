"""kern/kerx 表合并 — 主字体 kern 值优先"""
from .base import register


@register("kern")
def merge_kern(merged, main, bases, added=None):
    if "kern" in main:
        return  # 主字体已有 kern，完整保留
    for bf in bases:
        if "kern" in bf and "kern" not in merged:
            import copy
            merged["kern"] = copy.deepcopy(bf["kern"])
            break
