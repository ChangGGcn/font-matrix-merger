"""maxp 资源合并；只统计实际保留且解释器环境兼容的指令。"""
from .base import register


#: 这些解释器容量不会由 maxp.recalc 自动重算。
_HINT_RESOURCE_FIELDS = ("maxZones", "maxTwilightPoints", "maxStorage",
                         "maxFunctionDefs", "maxInstructionDefs",
                         "maxStackElements", "maxSizeOfInstructions")
_GLOBAL_HINT_TABLES = ("fpgm", "prep", "cvt ")


def _program_bytes(font, name):
    """读取已解码字形指令；不改变字体。"""
    if "glyf" not in font:
        return b""
    program = getattr(font["glyf"][name], "program", None)
    return bytes(program.getBytecode()) if program is not None else b""


def _hint_axis_space(font):
    """指令可读取变化轴；轴顺序/范围/avar 不同也不能共用解释器假设。"""
    if "fvar" not in font:
        return ()
    axes = font["fvar"].axes
    segments = font["avar"].segments if "avar" in font else {}
    return tuple((axis.axisTag, axis.minValue, axis.defaultValue,
                  axis.maxValue, tuple(sorted(segments.get(
                      axis.axisTag, {}).items()))) for axis in axes)


def _same_hint_environment(left, right):
    """只认定完整且逐字节相同的静态全局环境兼容。"""
    # cvar 的数值还受轴空间影响，未经重参数化不能判定安全。
    if "cvar" in left or "cvar" in right:
        return False
    if _hint_axis_space(left) != _hint_axis_space(right):
        return False
    for tag in _GLOBAL_HINT_TABLES:
        if (tag in left) != (tag in right):
            return False
        if tag not in left:
            continue
        if tag == "cvt ":
            if tuple(left[tag].values) != tuple(right[tag].values):
                return False
        elif bytes(left[tag].program.getBytecode()) != bytes(
                right[tag].program.getBytecode()):
            return False
    return True


def _merge_hint_resources(merged, sources):
    """已验证环境后，就地把解释器容量扩大到所有保留来源的上界。"""
    if "maxp" not in merged or merged["maxp"].tableVersion != 0x10000:
        return
    table = merged["maxp"]
    for field in _HINT_RESOURCE_FIELDS:
        values = [getattr(table, field, 0)]
        values.extend(getattr(font["maxp"], field, 0) for font in sources
                      if "maxp" in font and
                      font["maxp"].tableVersion == 0x10000)
        setattr(table, field, max(values))
    sizes = [len(_program_bytes(merged, name))
             for name in merged.getGlyphOrder()]
    table.maxSizeOfInstructions = max([table.maxSizeOfInstructions] + sizes)


@register("maxp")
def merge_maxp(merged, main, bases, added=None):
    """就地更新字形数及兼容且实际保留的字节码来源资源。"""
    if "maxp" not in merged:
        return
    alive = set(merged.getGlyphOrder())
    merged["maxp"].numGlyphs = len(alive)
    included = alive - set(main.getGlyphOrder())
    if added is not None:
        included &= set(added)
    if "glyf" not in merged or not included:
        return
    sources = []
    for base in bases:
        names = included & set(base.getGlyphOrder())
        if "glyf" not in base or not names:
            continue
        if not _same_hint_environment(merged, base):
            continue
        if any(_program_bytes(merged, name) and
               _program_bytes(merged, name) == _program_bytes(base, name)
               for name in names):
            sources.append(base)
    if sources:
        _merge_hint_resources(merged, sources)
