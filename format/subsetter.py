"""子集提取：由 fontTools 统一维护轮廓组件、布局与逐字形表闭包。

仅改 GlyphOrder 会留下悬空组件和布局引用；使用官方 Subsetter 对各表
同步裁剪。调用方字体不变；不支持安全裁剪的表/失效缓存明确告警删除，
缺失请求名按旧接口忽略并告警，其余处理失败直接抛出。
"""
import copy

from fontTools.subset import Options, Subsetter


def create_glyph_subset(font, glyph_names, strip_layout=True):
    """提取指定字形及必要组件；可选保留其布局替换输出闭包。

    Args:
        font: 源 TTFont，不会被就地修改。
        glyph_names: 字形名可迭代对象；始终保留 .notdef。
        strip_layout: 默认移除布局，False 时保留所有适用特性。

    Returns:
        使用官方闭包同步的 TTFont；失效缓存/签名及不支持表会告警删除。
    """
    requested = list(glyph_names)
    missing = set(requested) - set(font.getGlyphOrder())
    if missing:
        print("  [子集警告] %d 个请求字形不存在，按既有接口忽略并保留 .notdef"
              % len(missing))
    sub = copy.deepcopy(font)
    options = Options()
    options.notdef_glyph = True
    options.notdef_outline = True
    options.recommended_glyphs = False
    options.glyph_names = True
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.name_languages = ["*"]
    options.ignore_missing_glyphs = True
    if strip_layout:
        for tag in ("GSUB", "GPOS", "GDEF", "BASE", "VORG", "JSTF"):
            if tag in sub:
                del sub[tag]
    dropped = sorted(set(options.drop_tables) & set(sub.keys()))
    if dropped:
        print("  [子集警告] 删除失效缓存/签名或无安全裁剪实现的表：%s"
              % ", ".join(dropped))
    subsetter = Subsetter(options=options)
    subsetter.populate(glyphs=requested)
    subsetter.subset(sub)
    return sub
