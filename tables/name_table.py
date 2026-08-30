"""name 表合并"""
from .base import register


@register("name")
def merge_name(merged, main, bases, added=None):
    """name 表已由 apply_naming 处理，此处仅做安全清理"""
    # 已在 core/naming.py 中完成: Family→"xxx mod", 版权合并
    pass
