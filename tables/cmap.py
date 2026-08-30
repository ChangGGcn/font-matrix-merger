"""cmap 表合并"""
from .base import register
from ..core.glyph_copy import _copy_cmap_mappings


@register("cmap")
def merge_cmap(merged, main, bases, added=None):
    """cmap 表: 字形层面的映射已在 glyph_copy 中处理"""
    if added is None or "cmap" not in merged:
        return
    for bf in bases:
        _copy_cmap_mappings(merged, bf, added)
