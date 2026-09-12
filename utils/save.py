"""产物保存防护

fontTools 的 TTFont 会记住加载时的容器格式 (flavor) —
从 .woff2 载入的字体, `font.save("x.ttf")` 写出的其实是**扩展名为 .ttf 的
WOFF2 文件** (魔数 wOF2), Windows 无法安装, 不认 woff2 的工具会报
"name/head/OS/2 表缺失"。因此所有保存点统一走 :func:`save_font`:
保存前清 flavor、保存后校验 sfnt 魔数。
"""
import os

#: 合法 sfnt 魔数: TrueType 轮廓 / CFF 轮廓 / Apple 'true'
SFNT_MAGICS = (b"\x00\x01\x00\x00", b"OTTO", b"true")


def read_magic(path):
    """读取文件前 4 字节 (魔数)"""
    with open(path, "rb") as fh:
        return fh.read(4)


def assert_sfnt(path):
    """断言输出文件是 sfnt 容器 (TTF/OTF), 返回其魔数"""
    magic = read_magic(path)
    if magic not in SFNT_MAGICS:
        raise ValueError(
            "输出文件不是 sfnt (TTF/OTF) 容器: {} 魔数 {!r}. "
            "若需 WOFF/WOFF2 请显式传入 flavor='woff2'".format(path, magic))
    return magic


def save_font(font, path, flavor=None, recalcTimestamp=None):
    """保存字体, 统一处理容器格式与产物校验。

    Args:
        font: TTFont
        path: 输出路径
        flavor: None = 桌面 sfnt (.ttf/.otf); "woff"/"woff2" = web 字体
        recalcTimestamp: 传给 TTFont.save

    Returns:
        (path, magic) — 魔数仅在桌面输出时校验; web 输出返回容器魔数
    """
    font.flavor = flavor
    if recalcTimestamp is None:
        font.save(path)
    else:
        font.save(path, recalcTimestamp=recalcTimestamp)
    magic = read_magic(path)
    if flavor is None and magic not in SFNT_MAGICS:
        raise ValueError(
            "输出文件不是 sfnt (TTF/OTF) 容器: {} 魔数 {!r}".format(path, magic))
    return path, magic


def default_flavor_for(path):
    """按扩展名推断输出容器: .woff/.woff2 → 对应 flavor, 其余 → None"""
    ext = os.path.splitext(str(path))[1].lower()
    if ext == ".woff2":
        return "woff2"
    if ext == ".woff":
        return "woff"
    return None
