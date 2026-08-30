"""hhea/vhea 表合并"""
from .base import register
from ._strategies import first, max_val, min_val


def _merge_hhea_vhea(merged, main, bases, tag):
    if tag not in merged:
        return

    mh = main[tag]
    bh_list = [b[tag] for b in bases if tag in b]
    h = merged[tag]

    h.ascent = max_val([mh.ascent] + [bh.ascent for bh in bh_list])
    h.descent = min_val([mh.descent] + [bh.descent for bh in bh_list])
    h.lineGap = max_val([mh.lineGap] + [bh.lineGap for bh in bh_list])

    if tag == "hhea":
        h.advanceWidthMax = max_val([mh.advanceWidthMax] +
                                    [bh.advanceWidthMax for bh in bh_list])
        h.minLeftSideBearing = min_val([mh.minLeftSideBearing] +
                                       [bh.minLeftSideBearing for bh in bh_list])
        h.minRightSideBearing = min_val([mh.minRightSideBearing] +
                                        [bh.minRightSideBearing for bh in bh_list])
        h.xMaxExtent = max_val([mh.xMaxExtent] +
                               [bh.xMaxExtent for bh in bh_list])
    else:
        h.advanceHeightMax = max_val([mh.advanceHeightMax] +
                                     [bh.advanceHeightMax for bh in bh_list])
        h.minTopSideBearing = min_val([mh.minTopSideBearing] +
                                      [bh.minTopSideBearing for bh in bh_list])
        h.minBottomSideBearing = min_val([mh.minBottomSideBearing] +
                                         [bh.minBottomSideBearing for bh in bh_list])
        h.yMaxExtent = max_val([mh.yMaxExtent] +
                               [bh.yMaxExtent for bh in bh_list])


@register("hhea")
def merge_hhea(merged, main, bases, added=None):
    _merge_hhea_vhea(merged, main, bases, "hhea")


@register("vhea")
def merge_vhea(merged, main, bases, added=None):
    _merge_hhea_vhea(merged, main, bases, "vhea")
