"""GSUB/GPOS/GDEF 表合并 — 主字体全部保留，打底字体不冲突项追加"""
from .base import register


@register("GSUB")
def merge_gsub(merged, main, bases, added=None):
    _merge_otl(merged, main, bases, "GSUB")


@register("GPOS")
def merge_gpos(merged, main, bases, added=None):
    _merge_otl(merged, main, bases, "GPOS")


@register("GDEF")
def merge_gdef(merged, main, bases, added=None):
    _merge_otl(merged, main, bases, "GDEF")


def _merge_otl(merged, main, bases, tag):
    """OT 布局表合并: 主字体已有则完全保留"""
    if tag in main:
        return  # 主字体已有，完整保留 (已在 merged 中)
    # 主字体没有，从打底字体中取第一个有的
    for bf in bases:
        if tag in bf and tag not in merged:
            import copy
            merged[tag] = copy.deepcopy(bf[tag])
            break
