"""fvar/avar 表合并 (可变字体)"""
import copy
from .base import register
from fontTools.ttLib.tables._f_v_a_r import Axis


@register("fvar")
def merge_fvar(merged, main, bases, added=None):
    if "fvar" not in main or "fvar" not in merged:
        return

    ma = {a.axisTag: a for a in main["fvar"].axes}
    ba_all = {}
    for bf in bases:
        if "fvar" in bf:
            for a in bf["fvar"].axes:
                ba_all[a.axisTag] = a

    all_tags = set(ma.keys()) | set(ba_all.keys())
    new_axes = []
    for tag in sorted(all_tags):
        if tag in ma and tag in ba_all:
            ax = Axis()
            ax.axisTag = tag
            ax.minValue = min(ma[tag].minValue, ba_all[tag].minValue)
            ax.maxValue = max(ma[tag].maxValue, ba_all[tag].maxValue)
            ax.defaultValue = ma[tag].defaultValue
            ax.axisNameID = ma[tag].axisNameID
            new_axes.append(ax)
        elif tag in ma:
            new_axes.append(copy.deepcopy(ma[tag]))
        else:
            new_axes.append(copy.deepcopy(ba_all[tag]))

    merged["fvar"].axes = new_axes


@register("avar")
def merge_avar(merged, main, bases, added=None):
    if "avar" in main:
        return  # 保留主字体的 avar
    for bf in bases:
        if "avar" in bf and "avar" not in merged:
            merged["avar"] = copy.deepcopy(bf["avar"])
            break
