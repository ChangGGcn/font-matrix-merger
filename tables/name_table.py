"""name 表合并"""
from .base import register


@register("name")
def merge_name(merged, main, bases, added=None):
    """name 表已由 apply_naming 处理，此处仅做安全清理"""
    # 已在 core/naming.py 中完成: Family→"xxx mod", 版权合并
    pass


def complete_vf_name_table(font, platformID=3, platEncID=1, langID=0x409):
    """补全可变字体在 Windows/macOS 上必需的 name 记录。

    分片字体 (pyftsubset 产物) 只保留被引用的 name ID — 通常只剩 0–6、
    轴名 (271) 与实例子族名 (272–276)。可变字体还需要:

      * nameID 16/17 — Typographic Family / Subfamily
        (windows-font-fixing: "Always set nameID 16 even when equal to nameID 1");
      * nameID 25 — Variations PostScript Name Prefix (可变字体必需,
        否则各命名实例拿不到唯一 PS 名);
      * 每个命名实例的 PostScript 名 (fvar postscriptNameID 为 0xFFFF 时补建)。

    所有字符串都从字体自身的 name 记录推导, 不凭空编造;
    只写 Windows 平台 (3,1,0x409) 记录, 不新增 Mac 平台记录。
    """
    if "fvar" not in font or "name" not in font:
        return font

    name = font["name"]
    family = name.getDebugName(1)
    default_sub = name.getDebugName(2) or "Regular"
    ps_name = name.getDebugName(6)

    # PS 名前缀: 去掉 "-<默认子族名>" (例: MyFontVariable-Regular → MyFontVariable)
    sub_nospace = default_sub.replace(" ", "")
    prefix = ps_name or ""
    if ps_name and sub_nospace and ps_name.endswith("-" + sub_nospace):
        prefix = ps_name[: -(len(sub_nospace) + 1)]
    elif ps_name and "-" in ps_name:
        prefix = ps_name.split("-")[0]
    if not prefix:
        prefix = (family or "Font").replace(" ", "")

    if family and name.getDebugName(16) is None:
        name.setName(family, 16, platformID, platEncID, langID)
    if name.getDebugName(17) is None:
        name.setName(default_sub, 17, platformID, platEncID, langID)
    if name.getDebugName(25) is None:
        name.setName(prefix, 25, platformID, platEncID, langID)

    next_id = max(r.nameID for r in name.names) + 1
    for inst in font["fvar"].instances:
        if getattr(inst, "postscriptNameID", 0xFFFF) in (0xFFFF, None):
            sub = name.getDebugName(inst.subfamilyNameID) or "Regular"
            name.setName(f"{prefix}-{sub.replace(' ', '')}",
                         next_id, platformID, platEncID, langID)
            inst.postscriptNameID = next_id
            next_id += 1
    return font
