"""字形冲突规划：主码位优先，打底独有码位与组件/UVS 闭包保留。

对外仍返回冲突集合或别名字典；规划不修改输入字体。
"""
from ..utils.detect import EXEMPT_GLYPHS, is_auto_glyph_name
from .glyph_copy import _unicode_cmap
from .glyph_rename import alias_name


def _uvs_glyphs(main_font, base_font):
    """返回主字体未占用 UVS 所需的打底字形（含默认 UVS）。"""
    occupied = set()
    if "cmap" in main_font:
        for st in main_font["cmap"].tables:
            if st.format == 14:
                for selector, entries in st.uvsDict.items():
                    occupied.update((selector, cp) for cp, gn in entries)
    required = set()
    ordinary = _unicode_cmap(base_font)
    if "cmap" in base_font:
        for st in base_font["cmap"].tables:
            if st.format == 14:
                for selector, entries in st.uvsDict.items():
                    for cp, gn in entries:
                        if (selector, cp) not in occupied:
                            target = ordinary.get(cp) if gn is None else gn
                            if target is not None:
                                required.add(target)
    return required


def resolve_conflicts(main_font, base_font):
    """返回不应复制的打底字形名集合，不修改字体。

    有独有码位的字形不可因部分码位冲突整形删除；组件与 UVS 引用的
    字形即使普通码位全部冲突也保留。重名应先经 plan_alias 处理。
    """
    main_names = set(main_font.getGlyphOrder())
    main_cps = set(_unicode_cmap(main_font))
    base_g2c = {}
    if "cmap" in base_font:
        for st in base_font["cmap"].tables:
            if st.format == 14:
                continue
            for cp, gn in getattr(st, "cmap", {}).items():
                if st.isUnicode():
                    base_g2c.setdefault(gn, set()).add(cp)
                else:
                    # 非 Unicode 编码不与 Unicode 码位共用冲突域。
                    base_g2c.setdefault(gn, set())
    required = _uvs_glyphs(main_font, base_font)
    order = base_font.getGlyphOrder()
    required.update(gn for gn in order if gn not in main_names
                    and (not base_g2c.get(gn)
                         or base_g2c[gn] - main_cps))
    if "glyf" in base_font:
        pending = list(required)
        seen = set()
        while pending:
            gn = pending.pop()
            if gn in seen or gn not in base_font["glyf"].glyphs:
                continue
            seen.add(gn)
            glyph = base_font["glyf"][gn]
            if glyph.isComposite():
                for comp in glyph.components:
                    if comp.glyphName not in required:
                        required.add(comp.glyphName)
                        pending.append(comp.glyphName)
    return {gn for gn in order if gn != ".notdef"
            and not (gn in main_names
                     and (gn in EXEMPT_GLYPHS or is_auto_glyph_name(gn)))
            and (gn in main_names or gn not in required)}


def _plan_merge_aliases(main_font, base_font, tag="b", index=1):
    """内部规划所有打底重名字形的别名字典，不修改字体。

    名字相同不证明来源相同；保留所有非 .notdef 重名字形的独立身份，
    包括手工名字、序号名和仅被组件/布局/UVS 引用的字形。
    """
    main_names = set(main_font.getGlyphOrder())
    taken = main_names | set(base_font.getGlyphOrder())
    ren = {}
    for gn in base_font.getGlyphOrder():
        if gn == ".notdef" or gn not in main_names:
            continue
        new = alias_name(gn, taken, tag, index)
        ren[gn] = new
        taken.add(new)
    return ren


def plan_alias(main_font, base_font, tag="b", index=1):
    """兼容公共契约：只返回重名自动命名字形的别名字典。"""
    aliases = _plan_merge_aliases(main_font, base_font, tag, index)
    return {gn: new for gn, new in aliases.items() if is_auto_glyph_name(gn)}
