# FontMerger/core - 核心合并模块
from .conflict import resolve_conflicts
from .naming import apply_naming
from .glyph_copy import merge_glyphs_via_ttx, inject_glyphs_xml
from .merger import FontMerger
