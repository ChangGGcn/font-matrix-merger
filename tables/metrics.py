"""hmtx/vmtx 表合并"""
from .base import register


@register("hmtx")
def merge_hmtx(merged, main, bases, added=None):
    if "hmtx" not in merged:
        return
    merged_metrics = merged["hmtx"].metrics
    alive = set(merged.getGlyphOrder())
    allowed = alive if added is None else alive & set(added)
    for bf in bases:
        if "hmtx" not in bf:
            continue
        for gn, m in bf["hmtx"].metrics.items():
            if gn in allowed and gn not in merged_metrics:
                merged_metrics[gn] = m


@register("vmtx")
def merge_vmtx(merged, main, bases, added=None):
    if "vmtx" not in merged:
        return
    merged_metrics = merged["vmtx"].metrics
    alive = set(merged.getGlyphOrder())
    allowed = alive if added is None else alive & set(added)
    for bf in bases:
        if "vmtx" not in bf:
            continue
        for gn, m in bf["vmtx"].metrics.items():
            if gn in allowed and gn not in merged_metrics:
                merged_metrics[gn] = m
