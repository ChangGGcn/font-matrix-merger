"""合并后小表策略，不重放轮廓/变化数据/OT 布局注册表。

签名和设备缓存不能沿用；kern 仅并入安全的标准水平格式 0；
VORG 按最终存活字形的原点并集，不能把打底默认原点套给主字体。
"""
import copy
import math

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import newTable


#: 设备缓存依赖完整字形集合和 hinting，无法靠源表大小决定有效性。
TABLE_POLICY = {"DSIG": "drop", "hdmx": "drop", "LTSH": "drop",
                "VDMX": "drop", "kern": "union-safe", "VORG": "union",
                "gasp": "keep-main", "meta": "keep-main",
                "trak": "keep-main"}


def _union_kern(result, main, bases, added):
    """就地并集存活字形的水平 kern；冲突无论跨子表与否都以主为准。"""
    alive = set(result.getGlyphOrder())
    old = set(main.getGlyphOrder())
    table = copy.deepcopy(result["kern"]) if "kern" in result else None
    if table is not None and table.version != 0:
        print("  [表策略警告] kern 非标准版本，保留主表，不混入打底子表")
        return
    existing = set()
    if table is not None:
        for subtable in table.kernTables:
            pairs = getattr(subtable, "kernTable", None)
            if pairs is not None:
                subtable.kernTable = {pair: value
                                      for pair, value in pairs.items()
                                      if set(pair) <= alive}
                existing.update(subtable.kernTable)
    count = 0
    for base in bases:
        owned = (set(base.getGlyphOrder()) - old) & added & alive
        if "kern" not in base or not owned:
            continue
        if base["kern"].version != 0:
            print("  [表策略警告] 打底 kern 版本未知，不混入主表")
            continue
        for subtable in base["kern"].kernTables:
            if (getattr(subtable, "format", None) != 0 or
                    getattr(subtable, "coverage", None) != 1):
                print("  [表策略警告] 打底 kern 非标准水平加法格式，跳过")
                continue
            pairs = {pair: value for pair, value in
                     subtable.kernTable.items()
                     if set(pair) <= alive and set(pair) & owned and
                     pair not in existing}
            if not pairs:
                continue
            if table is None:
                table = newTable("kern")
                table.version = 0
                table.kernTables = []
            copied = copy.deepcopy(subtable)
            copied.kernTable = pairs
            table.kernTables.append(copied)
            existing.update(pairs)
            count += len(pairs)
    if table is not None:
        result["kern"] = table
    if count:
        print("  [表策略] kern 并入 %d 对存活字形，冲突保留主值" % count)


def _metric_origin(font, name, glyphs):
    """从最终轮廓和 vmtx 求无 VORG 时的默认原点语义。"""
    if "vmtx" not in font or name not in font["vmtx"].metrics:
        raise ValueError("缺少可恢复原点的 vmtx")
    pen = BoundsPen(glyphs)
    glyphs[name].draw(pen)
    ymax = math.ceil(pen.bounds[3]) if pen.bounds is not None else 0
    return ymax + font["vmtx"].metrics[name][1]


def _union_vorg(result, main, bases, added):
    """就地保留每个字形自己的原点，缺少可靠度量则保守不采用打底表。"""
    if "CFF " not in result and "CFF2" not in result:
        if "VORG" in result:
            del result["VORG"]
            print("  [表策略] 非 CFF 轮廓删除 VORG")
        return
    relevant = [base for base in bases if added & set(base.getGlyphOrder())]
    current = result["VORG"] if "VORG" in result else None
    candidates = [base for base in relevant if "VORG" in base]
    if current is None and not candidates:
        return
    old = set(main.getGlyphOrder())
    owners = {}
    for base in relevant:
        for name in added & set(base.getGlyphOrder()):
            owners.setdefault(name, base)
    template = current if current is not None else candidates[0]["VORG"]
    table = copy.deepcopy(template)
    table.VOriginRecords = {}
    glyphs = result.getGlyphSet()
    origins = {}
    try:
        for name in result.getGlyphOrder():
            if name in old:
                origin = (current[name] if current is not None else
                          _metric_origin(result, name, glyphs))
            else:
                owner = owners.get(name)
                if owner is not None and "VORG" in owner:
                    origin = owner["VORG"][name]
                else:
                    origin = _metric_origin(result, name, glyphs)
            origins[name] = origin
    except Exception as error:
        print("  [表策略警告] VORG 原点并集失败，保留主表而不套用打底默认值: %s" %
              error)
        return
    for name, origin in origins.items():
        table[name] = origin
    table.numVertOriginYMetrics = len(table.VOriginRecords)
    result["VORG"] = table
    print("  [表策略] VORG 保留 %d 个字形原点，显式记录 %d 条" %
          (len(origins), len(table.VOriginRecords)))


def apply_table_policy(result, main, bases, added):
    """就地处理签名、设备缓存、kern、VORG；不改输入，不返回字体。

    Args:
        result: 字形/变换已完成的最终 TTFont。
        main: 本级注入前主字体。
        bases: 实际复制字形的打底列表，按主优先次序排列。
        added: 最终字形差集，含组件及布局闭包，不是仅编码字形集合。
    Returns:
        None；未知设备缓存显式丢弃，其余不盲目拷贝。
    """
    bases = list(bases)
    actual = ((set(result.getGlyphOrder()) - set(main.getGlyphOrder())) &
              set(added))
    for tag in ("DSIG", "hdmx", "LTSH", "VDMX"):
        present = tag in result or any(tag in base for base in bases)
        if tag in result:
            del result[tag]
        if present:
            reason = "字体已修改，原签名失效" if tag == "DSIG" else (
                "依赖原字形集合及栅格程序，不复制过期设备缓存")
            print("  [表策略] %s 删除/不采用：%s" % (tag, reason))
    _union_kern(result, main, bases, actual)
    _union_vorg(result, main, bases, actual)
    for tag in ("meta", "trak", "gasp"):
        if tag not in result and any(tag in base for base in bases):
            print("  [表策略警告] 打底独有 %s，保留主策略，不盲目复制" % tag)
