"""FontMerger — 字体合并工具包

支持静态/可变 OTF/TTF 的任意组合合并，含多级打底。

用法:
    from FontMerger import FontMerger, merge_fonts

    merger = FontMerger()
    result = merger.merge_two(main_font, base_font)
    result.save("merged.otf")

    # 或一行调用
    result = merge_fonts(main_font, [base1, base2])
"""

__version__ = "0.1.0-alpha1"

from .core.merger import FontMerger
from .core.conflict import resolve_conflicts
from .core.naming import apply_naming
from .core.glyph_copy import merge_glyphs_via_ttx
from .format.converter import glyf_to_cff, cff_to_glyf, convert_font_format
from .format.subsetter import create_glyph_subset
from .format.static_extract import variable_to_static
from .format.transform import apply_scale_offset, scale_font
from .format.vf_axes import union_axes, axis_union_merge
from .format.webfont import unwrap_webfont
from .tables.base import merge_all_tables
from .tables.ot_merge import merge_ot_features, prune_base_layout
from .utils.detect import (is_cff, is_ttf, is_variable, type_label,
                            all_codepoints, glyph_to_codepoints,
                            get_copyrights, get_family, EXEMPT_GLYPHS)

import copy as _copy
from pathlib import Path as _Path
import os as _os
import sys as _sys

SUPPORTED_EXTS = {".ttf", ".otf", ".woff", ".woff2"}
COLLECTION_EXTS = {".ttc", ".otc"}


def merge_fonts(main_font, base_fonts, interactive=False):
    """便捷函数: 合并主字体和多个打底字体

    参数:
        main_font: 主字体 (TTFont 或路径)
        base_fonts: 打底字体列表 (TTFont 或路径)
        interactive: 是否交互式询问 (默认 False，使用默认策略)

    返回:
        合并后的 TTFont
    """
    from fontTools.ttLib import TTFont

    if isinstance(main_font, (str, _Path)):
        main_font = TTFont(str(main_font))

    resolved = []
    for bf in base_fonts:
        if isinstance(bf, (str, _Path)):
            resolved.append(TTFont(str(bf)))
        else:
            resolved.append(bf)

    merger = FontMerger()
    if not interactive:
        merger.mem = {
            "sOTF_sTTF": "OTF", "sTTF_sOTF": "TTF",
            "vOTF_sTTF2": "TTF", "vTTF_sOTF2": "TTF",
            "vOTF_sOTF": "可变", "vOTF_sTTF": "可变",
            "vTTF_sOTF": "可变", "vTTF_sTTF": "可变",
            "vOTF_vTTF": "OTF", "vTTF_vOTF": "TTF",
        }

    all_cr = get_copyrights(main_font, *resolved)
    family = get_family(main_font)

    current = _copy.deepcopy(main_font)
    for bf in resolved:
        current = merger.merge_two(current, bf)

    current = apply_naming(current, family, all_cr)
    return current
