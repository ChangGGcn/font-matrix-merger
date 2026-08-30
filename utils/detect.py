"""字体类型检测工具"""


def is_cff(font):
    return ("CFF " in font) or ("CFF2" in font)


def is_ttf(font):
    return "glyf" in font


def is_variable(font):
    return "fvar" in font


def type_label(font):
    v = "可变" if is_variable(font) else "静态"
    o = "OTF" if is_cff(font) else "TTF"
    return f"{v}{o}"


def all_codepoints(font):
    cps = set()
    for t in font["cmap"].tables:
        if hasattr(t, "cmap") and t.cmap:
            cps.update(t.cmap.keys())
    return cps


def glyph_to_codepoints(font):
    m = {}
    for t in font["cmap"].tables:
        if hasattr(t, "cmap") and t.cmap:
            for cp, gn in t.cmap.items():
                m.setdefault(gn, set()).add(cp)
    return m


def get_copyrights(*fonts):
    result = []
    for f in fonts:
        for r in f["name"].names:
            if r.nameID == 0:
                result.append(r.toUnicode())
                break
    return result


def get_family(font):
    for r in font["name"].names:
        if r.nameID in (1, 16):
            return r.toUnicode()
    return "Font"


EXEMPT_GLYPHS = {".notdef", ".null", "nonmarkingreturn"}
