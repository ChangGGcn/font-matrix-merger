"""表级合并调度器

遍历合并后字体的所有表，对每个表调用对应的合并模块。
注册机制: 每个表模块通过 @register(table_tag) 装饰器注册。
"""

TABLE_MERGE_REGISTRY = {}


def register(tag):
    """装饰器: 将函数注册为某个表的合并处理器"""
    def wrapper(func):
        TABLE_MERGE_REGISTRY[tag] = func
        return func
    return wrapper


def merge_all_tables(merged_font, main_font, base_fonts, added_glyphs=None):
    """
    对 merged_font 的每个表执行合并策略。

    参数:
        merged_font: 已含合并后字形的 TTFont
        main_font: 主字体
        base_fonts: 打底字体列表
        added_glyphs: 新增字形名集合 (可选)
    """
    all_tags = set(merged_font.keys())
    for bf in base_fonts:
        all_tags.update(bf.keys())
    all_tags.discard("GlyphOrder")

    for tag in sorted(all_tags):
        if tag in TABLE_MERGE_REGISTRY:
            try:
                TABLE_MERGE_REGISTRY[tag](merged_font, main_font, base_fonts,
                                          added_glyphs)
            except Exception as e:
                import traceback
                print(f"  [表合并警告] {tag}: {e}")
                traceback.print_exc()
