"""maxp 表合并"""
from .base import register


@register("maxp")
def merge_maxp(merged, main, bases, added=None):
    if "maxp" not in merged:
        return
    merged["maxp"].numGlyphs = len(merged.getGlyphOrder())
