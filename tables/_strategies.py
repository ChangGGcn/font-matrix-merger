"""表合并策略函数 — 参考 fontTools merge/tables.py"""


def first(values, default=None):
    """取主字体（第一个）的值"""
    return values[0] if values else default


def max_val(values, default=0):
    """取最大值"""
    return max(v for v in values if v is not None) if values else default


def min_val(values, default=0):
    """取最小值"""
    return min(v for v in values if v is not None) if values else default


def bitwise_or(values):
    """按位或"""
    result = 0
    for v in values:
        if v is not None:
            result |= v
    return result


def bitwise_and(values):
    """按位与"""
    if not values:
        return 0
    result = values[0]
    for v in values[1:]:
        if v is not None:
            result &= v
    return result


def sum_vals(values):
    """求和"""
    return sum(v for v in values if v is not None)


def sum_lists(lists):
    """列表拼接"""
    result = []
    for lst in lists:
        if lst:
            result.extend(lst)
    return result


def sum_dicts(dicts):
    """字典合并 (后面的覆盖前面的)"""
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def current_time(_=None):
    """当前时间戳 (用于 head.created/modified)"""
    import time
    return int(time.time())


def equal(values):
    """断言所有值相等，返回第一个值"""
    if len(values) <= 1:
        return values[0] if values else None
    ref = values[0]
    for v in values[1:]:
        if v is not None and ref is not None and v != ref:
            raise ValueError(f"Values differ: {ref} vs {v}")
    return ref


def recalculate(_=None):
    """占位: 将在编译时重新计算"""
    return 0
