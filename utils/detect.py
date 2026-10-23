"""字体类型检测工具"""
import re

from fontTools.ttLib.tables._n_a_m_e import (
    _MAC_LANGUAGES, _WINDOWS_LANGUAGES,
)

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


class _LocalizedText(str):
    """保留 str 行为，同时携带原 name 记录供内部命名流程使用。"""

    def __new__(cls, value, records=()):
        result = str.__new__(cls, value)
        result._name_records = tuple(records)
        return result


def _name_language(key):
    """将已知平台语言号归一；未知语言保留平台与语言号，不猜英文。"""
    platform, encoding, language = key
    if platform == 3:
        return _WINDOWS_LANGUAGES.get(language, (platform, language))
    if platform == 1:
        return _MAC_LANGUAGES.get(language, (platform, language))
    return (platform, language)


def _name_priority(record):
    """英文优先，其次排印族名；排序不依赖表内记录次序。"""
    name_id, platform, encoding, language, text = record
    locale = _name_language((platform, encoding, language))
    english = isinstance(locale, str) and locale.split("-")[0] == "en"
    return (not english, name_id != 16, platform != 3,
            platform, language, encoding, text)


def _localized_records(font, name_ids):
    """读取指定 ID 的所有可解码记录；坏记录告警后保留其余记录。"""
    records = []
    for record in font["name"].names:
        if record.nameID not in name_ids:
            continue
        try:
            text = record.toUnicode()
        except (UnicodeDecodeError, UnicodeEncodeError, LookupError):
            print("  [命名警告] 无法解码 nameID %d，改用其余记录"
                  % record.nameID)
            continue
        records.append((record.nameID, record.platformID,
                        record.platEncID, record.langID, text))
    return sorted(set(records), key=_name_priority)


def get_copyrights(*fonts):
    """返回每个字体一条首选版权的 list；str 元素内部携带全部语言。"""
    result = []
    for font in fonts:
        records = _localized_records(font, (0,))
        if records:
            result.append(_LocalizedText(records[0][-1], records))
    return result


def get_family(font):
    """返回确定的首选族名 str：英文优先、同语言内优先 nameID 16。"""
    records = _localized_records(font, (1, 16))
    return _LocalizedText(records[0][-1], records) if records else "Font"


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
