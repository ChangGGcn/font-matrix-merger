"""head 表合并"""
from .base import register
from ._strategies import (first, max_val, min_val, bitwise_or, bitwise_and,
                           current_time, equal, sum_vals)
from fontTools.ttLib import getTableClass
import copy


@register("head")
def merge_head(merged, main, bases, added=None):
    if "head" not in merged:
        return

    main_h = main["head"]
    base_hs = [b["head"] for b in bases if "head" in b]

    h = merged["head"]
    h.tableVersion = max_val([main_h.tableVersion] +
                             [bh.tableVersion for bh in base_hs])

    h.fontRevision = max_val([main_h.fontRevision] +
                             [bh.fontRevision for bh in base_hs])

    # 边界取并集
    h.xMin = min_val([main_h.xMin] + [bh.xMin for bh in base_hs])
    h.yMin = min_val([main_h.yMin] + [bh.yMin for bh in base_hs])
    h.xMax = max_val([main_h.xMax] + [bh.xMax for bh in base_hs])
    h.yMax = max_val([main_h.yMax] + [bh.yMax for bh in base_hs])

    h.unitsPerEm = main_h.unitsPerEm
    h.created = current_time()
    h.modified = current_time()
    h.macStyle = main_h.macStyle

    if base_hs:
        h.lowestRecPPEM = max_val([main_h.lowestRecPPEM] +
                                  [bh.lowestRecPPEM for bh in base_hs])
