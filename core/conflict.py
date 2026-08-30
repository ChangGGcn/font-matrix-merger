"""字形冲突检测"""
from ..utils.detect import all_codepoints, glyph_to_codepoints, EXEMPT_GLYPHS


def resolve_conflicts(main_font, base_font):
    """返回 base 中与 main 冲突的字形名集合 (码位或名称冲突)"""
    main_names = set(main_font.getGlyphOrder())
    main_cps = all_codepoints(main_font)
    base_g2c = glyph_to_codepoints(base_font)

    conflicts = set()
    for gn in base_font.getGlyphOrder():
        if gn in main_names:
            if gn not in EXEMPT_GLYPHS:
                conflicts.add(gn)
            continue
        if base_g2c.get(gn, set()) & main_cps:
            conflicts.add(gn)
    return conflicts
