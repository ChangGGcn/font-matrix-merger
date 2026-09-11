"""字体类型检测工具"""
import re

#: post 3.0 字体在加载时由 fontTools 生成的"序号名" (glyph00001…)。
#: 这类名字**不具标识性**: 不同字体里同名不代表同源字形。
AUTO_GLYPH_RE = re.compile(r"^glyph\d{5}$")


def is_auto_glyph_name(name):
    """是否为 fontTools 为 post 3.0 字体生成的序号名 (glyphNNNNN)"""
    return bool(AUTO_GLYPH_RE.match(name))


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


def axis_space(font):
    """可变字体的轴空间: {axisTag: (min, default, max)}; 非可变字体返回 {}"""
    if not is_variable(font):
        return {}
    return {a.axisTag: (a.minValue, a.defaultValue, a.maxValue)
            for a in font["fvar"].axes}


def is_same_source(fonts):
    """判断一组字体是否为"同一可变字体按 unicode-range 切出的分片" (同源分片)。

    判定条件 (合并策略选择的依据):
      1. 数量 ≥ 2, 且都存在 fvar (可变字体);
      2. 所有字体的轴集合与 min/default/max 完全一致;
      3. 轮廓格式一致 (同为 glyf 或同为 CFF2)。

    同源分片可以用"并集"策略合并: 不需要实例化, 不需要轴并集,
    每个分片的 gvar/HVAR/VVAR/布局表都能原样保留。
    """
    fonts = list(fonts)
    if len(fonts) < 2:
        return False
    if not all(is_variable(f) for f in fonts):
        return False
    ref_axes = axis_space(fonts[0])
    if not ref_axes:
        return False
    for f in fonts[1:]:
        if axis_space(f) != ref_axes:
            return False
    if len({is_cff(f) for f in fonts}) != 1:
        return False
    if len({is_ttf(f) for f in fonts}) != 1:
        return False
    return True


EXEMPT_GLYPHS = {".notdef", ".null", "nonmarkingreturn"}
