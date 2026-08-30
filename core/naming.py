"""名称表处理: Family 名 + 版权合并"""
COPY_SEP = "\n\n"


def _sanitize_names(font):
    """移除无法编码的 name 记录 (MacRoman 安全问题)"""
    bad = []
    for rec in font["name"].names:
        try:
            rec.toBytes()
        except (UnicodeEncodeError, UnicodeDecodeError):
            bad.append(rec)
    for rec in bad:
        font["name"].names.remove(rec)


def apply_naming(output_font, main_family, all_copyrights):
    new_family = f"{main_family} mod"
    combined = COPY_SEP.join(c for c in all_copyrights if c)

    for record in output_font["name"].names:
        if record.nameID in (1, 16):
            record.string = new_family
        elif record.nameID == 0:
            record.string = combined

    output_font["name"].setName(new_family, 1, 3, 1, 0x0409)
    output_font["name"].setName(new_family, 16, 3, 1, 0x0409)
    output_font["name"].setName(combined, 0, 3, 1, 0x0409)

    _sanitize_names(output_font)
    return output_font
