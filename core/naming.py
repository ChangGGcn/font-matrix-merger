"""就地更新修改版名称，保留语言、RIBBI 与来源记录。

只派生身份相关字段，不升版本、不重建 VF 的轴/实例名称；编码失败时
仅将本次改写字段迁到同语言 Unicode 记录，绝不扫描删除无关元数据。
"""
import hashlib
import unicodedata

from fontTools.ttLib.tables._n_a_m_e import makeName

from ..utils.detect import (_localized_records, _name_language,
                            _WINDOWS_LANGUAGES)

COPY_SEP = "\n\n"
#: 仅这些记录参与重命名；授权、商标、厂商与自定义 ID 原样保留。
_IDENTITY_IDS = (1, 2, 3, 4, 6, 16, 17)


def _groups(records):
    """按平台/编码/语言收集，输入已按确定顺序排序。"""
    result = {}
    for name_id, platform, encoding, language, text in records:
        result.setdefault((platform, encoding, language), {}).setdefault(
            name_id, text)
    return result


def _lookup(groups, key, name_id, default=None):
    """优先同编码记录，再取同语言记录，不把其它语言当成翻译。"""
    if name_id in groups.get(key, {}):
        return groups[key][name_id]
    for other in sorted(groups):
        if _name_language(other) == _name_language(key):
            if name_id in groups[other]:
                return groups[other][name_id]
    return default


def _modified(family):
    """重入时不叠加 mod，保持已有默认后缀。"""
    return family if family.endswith(" mod") else family + " mod"


def _unique_parts(texts):
    """保留来源顺序，并去除跨平台重复版权及重入时的重复段落。"""
    result = []
    for text in texts:
        for part in text.split(COPY_SEP):
            if part and part not in result:
                result.append(part)
    return COPY_SEP.join(result)


def _set_name(table, text, name_id, key):
    """改写字段编码不兼容时迁到同语言 Windows Unicode，不丢文本。"""
    record = makeName(text, name_id, *key)
    try:
        record.toBytes()
    except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
        locale = _name_language(key)
        language_ids = sorted(k for k, v in _WINDOWS_LANGUAGES.items()
                              if v == locale)
        if not language_ids:
            raise ValueError("name 字段编码失败且无法确定 Unicode 语言")
        target = (3, 1, language_ids[0])
        table.removeNames(nameID=name_id, platformID=key[0],
                          platEncID=key[1], langID=key[2])
        table.setName(text, name_id, *target)
        print("  [命名警告] nameID %d 编码不兼容，迁到同语言 Unicode"
              % name_id)
    else:
        table.setName(text, name_id, *key)


def _postscript_name(family, style):
    """以原 Unicode 字符串摘要避免清洗/截断碰撞，输出至多 63 字节。"""
    identity = family + "\0" + style
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    ascii_name = unicodedata.normalize("NFKD", family + "-" + style)
    ascii_name = "".join(c for c in ascii_name
                         if 33 <= ord(c) <= 126 and c not in "[](){}<>/%")
    return (ascii_name or "Font-mod")[:50] + "-" + digest


def apply_naming(output_font, main_family, all_copyrights):
    """就地按原语言派生修改版名称，兼容原 str/list 参数与返回字体。

    Args:
        output_font: 待命名的 TTFont，保留其来源与 VF 自定义名称。
        main_family: 首选族名 str；get_family 的值可携带各语言原族名。
        all_copyrights: 版权 list；普通字符串按未标注语言的补充文本处理。
    Returns:
        原 output_font；版本、厂商、商标、授权及 fvar/STAT 不变。
    """
    table = output_font["name"]
    records = _localized_records(output_font, _IDENTITY_IDS + (0,))
    groups = _groups(records)
    source = _groups(getattr(main_family, "_name_records", ()))
    family_groups = source or groups
    english_key = (3, 1, 0x0409)
    groups.setdefault(english_key, {})
    family = _modified(str(main_family))
    style_records = (_localized_records(output_font, (17,)) or
                     _localized_records(output_font, (2,)))
    fallback_style = style_records[0][-1] if style_records else "Regular"
    primary_style = _lookup(groups, english_key, 17,
                            _lookup(groups, english_key, 2, fallback_style))
    ps_name = _postscript_name(family, primary_style)

    # 普通 list 的每个 str 元素仍可携带来源语言，list()、切片不会丢元数据。
    rights = {}
    plain_rights = []
    for value in all_copyrights:
        localized = getattr(value, "_name_records", ())
        if localized:
            for _, platform, encoding, language, text in localized:
                key = (platform, encoding, language)
                rights.setdefault(_name_language(key), []).append(text)
                groups.setdefault(key, {})
        elif value:
            plain_rights.append(str(value))

    # 所有语言版权都保留，包括只有打底字体具有的语言；不造英文翻译。
    for key in sorted(groups):
        texts = []
        existing = _lookup(groups, key, 0)
        if existing:
            texts.append(existing)
        texts.extend(rights.get(_name_language(key), ()))
        texts.extend(plain_rights)
        if texts:
            _set_name(table, _unique_parts(texts), 0, key)

    for key in sorted(groups):
        # 仅有版权的语言不凭空补出英文族名；英文默认记录则始终存在。
        if key != english_key and not any(
                n in groups[key] for n in _IDENTITY_IDS):
            continue
        old_typo = _lookup(family_groups, key, 16)
        old_legacy = _lookup(family_groups, key, 1)
        locale = _name_language(key)
        is_english = isinstance(locale, str) and locale.split("-")[0] == "en"
        local_family = family if is_english or key == english_key else (
            _modified(old_typo or old_legacy or str(main_family)))
        legacy = local_family
        # 保留非 RIBBI 字重的旧式独立家族，避免多个 Regular 被折成同组。
        if old_typo and old_legacy and old_typo != old_legacy:
            if old_legacy.startswith(old_typo + " "):
                legacy += old_legacy[len(old_typo):]
            else:
                legacy = _modified(old_legacy)
        style = _lookup(groups, key, 2, primary_style)
        typo_style = _lookup(groups, key, 17, style)
        full_name = local_family + " " + typo_style
        if typo_style == "Regular":
            full_name = legacy
        unique_id = _lookup(groups, key, 3, "")
        marker = ";mod;"
        unique_id = unique_id.split(marker)[0] + marker + ps_name
        for name_id, text in ((1, legacy), (16, local_family),
                              (17, typo_style), (4, full_name),
                              (6, ps_name), (3, unique_id)):
            _set_name(table, text, name_id, key)
        if _lookup(groups, key, 2) is None:
            _set_name(table, style, 2, key)

    # CFF1 的 Name INDEX 也是 PS 身份，不能留下与 nameID 6 冲突的旧名。
    # CFF2 没有该身份字段，且不碰其轴/实例相关名称。
    if "CFF " in output_font:
        cff = output_font["CFF "].cff
        cff.fontNames = [ps_name]
        top = cff.topDictIndex[0]
        full_name = table.getName(4, *english_key).toUnicode()
        for attribute, text in (("FamilyName", family),
                                ("FullName", full_name)):
            # CFF 字符串不承载 Unicode 翻译，使用合法 PS 标识作为后备。
            if not text.isascii():
                text = ps_name
            setattr(top, attribute, text)
    return output_font
