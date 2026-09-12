"""字形冲突检测"""
from ..utils.detect import (all_codepoints, glyph_to_codepoints, EXEMPT_GLYPHS,
                            is_auto_glyph_name)
from .glyph_rename import alias_name


def resolve_conflicts(main_font, base_font):
    """返回 base 中与 main 冲突的字形名集合 (码位或名称冲突)。

    自动命名字形 (post 3.0 的 glyphNNNNN) 不具标识性 —— 不同字体里的同名
    不代表同源字形, 因此**不计入**冲突, 由 :func:`plan_alias` 改名后加入。
    """
    main_names = set(main_font.getGlyphOrder())
    main_cps = all_codepoints(main_font)
    base_g2c = glyph_to_codepoints(base_font)

    conflicts = set()
    for gn in base_font.getGlyphOrder():
        if gn in main_names:
            if gn not in EXEMPT_GLYPHS and not is_auto_glyph_name(gn):
                conflicts.add(gn)
            continue
        if base_g2c.get(gn, set()) & main_cps:
            conflicts.add(gn)
    return conflicts


def plan_alias(main_font, base_font, tag="b", index=1):
    """规划"重名但不同源"的自动命名字形的别名: {旧名: 新名}。

    post 3.0 字体的 glyphNNNNN 由 fontTools 按序号生成: 两个字体里的
    glyph00554 是**不同字形**。旧逻辑按名字判冲突直接丢弃, 会丢掉大量字形。
    """
    main_names = set(main_font.getGlyphOrder())
    taken = set(main_names)
    ren = {}
    for gn in base_font.getGlyphOrder():
        if gn == ".notdef" or not is_auto_glyph_name(gn):
            continue
        if gn not in main_names:
            continue
        new = alias_name(gn, taken, tag, index)
        ren[gn] = new
        taken.add(new)
    return ren
