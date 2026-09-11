"""FontMerger — 字体合并工具包

支持静态/可变 OTF/TTF 的任意组合合并，含多级打底；以及同一可变字体
按 unicode-range 切出的分片的**保特性并集**合并。

用法:
    from FontMerger import FontMerger, merge_fonts, merge_subsets

    merger = FontMerger()
    result = merger.merge_two(main_font, base_font)
    result.save("merged.otf")

    # 或一行调用 (异源字体)
    result = merge_fonts(main_font, [base1, base2])

    # 同源分片 (webfont unicode-range 分片) → 保 gvar/布局特性的并集
    result = merge_subsets(subset_paths, out_path="Merged.ttf", tag="ja",
                           verify=True)
    result.subset_merger.glyph_map()      # 源字形 → 合并后 GID
"""

__version__ = "0.1.0-alpha1"

from .core.merger import FontMerger
from .core.conflict import resolve_conflicts, plan_alias
from .core.naming import apply_naming
from .core.glyph_copy import merge_glyphs_via_ttx
from .core.glyph_rename import rename_glyphs, renamed_copy, alias_name
from .core.subset_merge import SameSourceSubsetMerger, load_subsets, merge_subsets
from .core.verify import verify_merge
from .format.converter import glyf_to_cff, cff_to_glyf, convert_font_format
from .format.subsetter import create_glyph_subset
from .format.static_extract import variable_to_static
from .format.transform import apply_scale_offset, scale_font
from .format.vf_axes import union_axes, axis_union_merge
from .format.webfont import unwrap_webfont
from .tables.base import merge_all_tables
from .tables.ot_merge import merge_ot_features, prune_base_layout
from .tables.layout_union import (LayoutUnion, layout_glyph_names,
                                   offset_var_devices, remap_glyph_names,
                                   resort_layout)
from .tables.varstore import VarStoreUnion
from .tables.name_table import complete_vf_name_table
from .tables.head import fix_head_flags
from .utils.detect import (is_cff, is_ttf, is_variable, type_label,
                            all_codepoints, glyph_to_codepoints,
                            get_copyrights, get_family, EXEMPT_GLYPHS,
                            axis_space, is_same_source, is_auto_glyph_name,
                            AUTO_GLYPH_RE)
from .utils.save import save_font, assert_sfnt, SFNT_MAGICS

import copy as _copy
from pathlib import Path as _Path
import os as _os
import sys as _sys

SUPPORTED_EXTS = {".ttf", ".otf", ".woff", ".woff2"}
COLLECTION_EXTS = {".ttc", ".otc"}


#: 非交互模式的默认回答 (键为 FontMerger.ask 的 key)
DEFAULT_ANSWERS = {
    "sOTF_sTTF": "OTF", "sTTF_sOTF": "TTF",
    "vOTF_sTTF2": "TTF", "vTTF_sOTF2": "TTF",
    "vOTF_sOTF": "可变", "vOTF_sTTF": "可变",
    "vTTF_sOTF": "可变", "vTTF_sTTF": "可变",
    "vOTF_vTTF": "OTF", "vTTF_vOTF": "TTF",
}


def load_font(source):
    """按路径/对象加载字体; WOFF/WOFF2 自动解包 (清 flavor)"""
    from fontTools.ttLib import TTFont

    if not isinstance(source, (str, _Path)):
        return source
    ext = _os.path.splitext(str(source))[1].lower()
    if ext in (".woff", ".woff2"):
        return unwrap_webfont(str(source))
    return TTFont(str(source))


def merge_fonts(main_font, base_fonts, interactive=False, answers=None):
    """便捷函数: 合并主字体和多个打底字体

    参数:
        main_font: 主字体 (TTFont 或路径)
        base_fonts: 打底字体列表 (TTFont 或路径)
        interactive: 是否交互式询问 (默认 False，使用默认策略)
        answers: 预置回答字典 {ask key: 答案}，覆盖 DEFAULT_ANSWERS。
                 例如 {"vOTF_sOTF": "静态"} 强制可变主字体走静态路径。

    返回:
        合并后的 TTFont (flavor 已清空 — 可直接 save 为 .ttf/.otf)
    """
    main_font = load_font(main_font)
    resolved = [load_font(bf) for bf in base_fonts]

    merger = FontMerger()
    if not interactive:
        merger.mem = dict(DEFAULT_ANSWERS)
        if answers:
            merger.mem.update(answers)
    elif answers:
        merger.mem.update(answers)

    all_cr = get_copyrights(main_font, *resolved)
    family = get_family(main_font)

    current = _copy.deepcopy(main_font)
    for bf in resolved:
        current = merger.merge_two(current, bf)

    current = apply_naming(current, family, all_cr)
    # 输入若来自 woff2, deepcopy 会保留 flavor; 输出语义是桌面字体
    current.flavor = None
    return current
