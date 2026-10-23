"""异源合并出口自检：码位不丢失、主映射优先、引用保持完整。

与轮廓抽样自检不同，这些检查不引入开关或可选依赖。失败向上抛出，
由合成路径既有回退处理；普通路径不得把不完整产物当作成功返回。
"""


def unicode_cmap(font):
    """按 fontTools 首选子表取映射，再补其余 Unicode 子表的独有码位。"""
    if "cmap" not in font:
        return {}
    result = dict(font.getBestCmap() or {})
    for table in font["cmap"].tables:
        if table.format == 14 or not table.isUnicode():
            continue
        for cp, name in (getattr(table, "cmap", None) or {}).items():
            result.setdefault(cp, name)
    return result


def assert_cmap_union(result, main, base, check_main=True, base_mapping=None):
    """检查 Unicode 码位精确并集，且默认不允许打底覆盖主映射。

    CID 名字空间整体重写时由调用方传 check_main=False；码位、子表与
    字形引用检查仍然执行，不把非 Unicode 编码当作 Unicode 码位。
    """
    main_map = unicode_cmap(main)
    expected = set(main_map) | set(unicode_cmap(base))
    actual = unicode_cmap(result)
    missing = expected - set(actual)
    extra = set(actual) - expected
    assert not (missing or extra), (
        "合并码位不变量失败：缺失 %d，多出 %d；首批缺失 %s"
        % (len(missing), len(extra),
           ["U+%04X" % cp for cp in sorted(missing)[:12]]))
    if check_main:
        changed = [cp for cp, name in main_map.items()
                   if actual.get(cp) != name]
        assert not changed, (
            "主字体码位映射被覆盖：%d 个，首批 %s"
            % (len(changed),
               ["U+%04X" % cp for cp in sorted(changed)[:12]]))
    expected_uvs = _uvs_map(main)
    for key, name in _uvs_map(base).items():
        expected_uvs.setdefault(key, (base_mapping or {}).get(name, name))
    actual_uvs = _uvs_map(result)
    assert set(actual_uvs) == set(expected_uvs), "合并 UVS 序列并集不同步"
    if check_main:
        assert actual_uvs == expected_uvs, "合并 UVS 字形映射被覆盖或丢失"
    return True


def _uvs_map(font):
    """读取 selector/base-codepoint 到非默认字形或 None 的映射。"""
    result = {}
    ordinary = unicode_cmap(font)
    for table in font["cmap"].tables if "cmap" in font else []:
        if table.format == 14:
            for selector, pairs in getattr(table, "uvsDict", {}).items():
                for cp, name in pairs:
                    # 默认 UVS 与显式指向同字形是同一种语义。
                    target = ordinary.get(cp) if name is None else name
                    result.setdefault((selector, cp), target)
    return result


def validate_input_uvs(font, label):
    """输入有非法 UVS 时明确拒绝，不等到并集检查再报产物缺失。"""
    ordinary = unicode_cmap(font)
    alive = set(font.getGlyphOrder())
    for table in font["cmap"].tables if "cmap" in font else []:
        if table.format != 14:
            continue
        for selector, entries in table.uvsDict.items():
            for cp, name in entries:
                if name is None and cp not in ordinary:
                    raise ValueError(
                        "输入%s含非法默认 UVS：U+%04X U+%04X 无普通映射"
                        % (label, cp, selector))
                if name is not None and name not in alive:
                    raise ValueError("输入%s含悬空 UVS 字形" % label)


def assert_font_structure(font):
    """检查字形/度量、Unicode 与 UVS 引用、布局和可变表结构。"""
    order = font.getGlyphOrder()
    alive = set(order)
    assert len(order) == len(alive), "字形序中存在重复名称"
    assert not order or order[0] == ".notdef", "首字形不是 .notdef"
    if "maxp" in font:
        assert font["maxp"].numGlyphs == len(order), "maxp 字形数不同步"
    if "glyf" in font:
        assert set(font["glyf"].glyphs) == alive, "glyf 与字形序不一致"
        font["glyf"].ensureDecompiled()
        for name in order:
            glyph = font["glyf"][name]
            if glyph.isComposite():
                assert all(c.glyphName in alive for c in glyph.components), (
                    "复合字形含悬空组件：%s" % name)
    for tag in ("hmtx", "vmtx"):
        if tag in font:
            assert alive <= set(font[tag].metrics), (
                "%s 缺少字形度量" % tag)
    full = unicode_cmap(font)
    assert set(full.values()) <= alive, "Unicode cmap 含悬空字形"
    for table in font["cmap"].tables if "cmap" in font else []:
        if table.format == 14:
            for selector, pairs in getattr(table, "uvsDict", {}).items():
                seen = set()
                for cp, name in pairs:
                    assert cp not in seen, "同一变体序列重复定义"
                    seen.add(cp)
                    if name is None:
                        assert cp in full, (
                            "默认 UVS 基础码位缺失：U+%04X" % cp)
                    assert name is None or name in alive, (
                        "UVS 含悬空字形：U+%04X U+%04X" % (cp, selector))
            continue
        if not table.isUnicode():
            continue
        mapping = getattr(table, "cmap", None) or {}
        limit = {0: 0xFF, 2: 0xFFFF, 4: 0xFFFE,
                 6: 0xFFFF}.get(table.format, 0x10FFFF)
        wanted = {cp: name for cp, name in full.items() if cp <= limit}
        assert mapping == wanted, (
            "Unicode 子表不同步：(%d, %d, format %d)"
            % (table.platformID, table.platEncID, table.format))
    if "avar" in font and "fvar" in font:
        tags = {axis.axisTag for axis in font["fvar"].axes}
        assert tags <= set(font["avar"].segments), "avar 缺少轴映射"
    from .verify import _check_layout_integrity
    report = _check_layout_integrity(font)
    for key, failures in report.items():
        assert not failures, "布局/变化数据结构错误：%s=%s" % (key, failures)
    return True
