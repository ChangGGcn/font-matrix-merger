# 辅助 API 参考

[English](../en/helper-api.md) | **简体中文**

本页记录合并入口之外的包级导出。内容对应 v0.2.1；下文的默认值、返回值与副作用取自当前源码文件，不沿用旧 README 的描述。

覆盖与分工：

- [合并 API](merge-api.md) 记录 `load_font`、`merge_fonts`、`FontMerger` 与 `DEFAULT_ANSWERS`。
- [轴映射与可变数据合成](variation-model.md) 记录 `AxisMapping`、`PiecewiseLinear`、`axis_mappings`、`evaluate_supports`、`refine_support_rebased`、`source_location`、`fvar_triples` 与 `avar_segments`。
- [同源分片与验证](subsets-and-verification.md) 记录 `SameSourceSubsetMerger`、`load_subsets`、`merge_subsets` 与 `verify_merge`。
- 本页记录其余全部包级导出：冲突规划、字形复制与改名、命名、格式转换、子集、变换、Axis 并集、表与布局辅助、name/head 补全、检测工具、保存防护与包常量。

运行库源码使用相对链接，例如 [core/merger.py](../../core/merger.py)；这些链接在仓库与运行 ZIP 内都能解析。运行 ZIP 包含根模块、core/、format/、tables/、utils/、两版 README、CHANGELOG.md、LICENSE 与 doc/*.md；不包含 tests/ 与 build/。这两棵树仅存在于仓库，因此本文只以代码路径形式提及，不做相对链接。私有工程笔记不属于公开文档。

条目格式：签名、参数（类型、默认值、单位或含义）、返回值、就地修改、异常。除非明确写明返回副本，输入均按借用处理。

## 1. 冲突规划

仓库源码：[core/conflict.py](../../core/conflict.py)。

### `resolve_conflicts(main_font, base_font)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | 必填 | 主字体，只读。 |
| `base_font` | `TTFont` | 必填 | 打底字体，只读。 |

返回：`set[str]`，给出不应复制的打底字形名。保留条件只适用于名字不在主字体中的打底字形，或已经改成不同名字的字形。满足该前提时，字形拥有主字体没有的 Unicode 码位、被未冲突的 UVS 序列引用、完全没有 Unicode cmap 条目，或是另一个保留打底字形的组件，会被保留。仍与主字体同名的普通手工名无论码位如何都会被报告删除；自动名与豁免名另行处理，`.notdef` 从不出现在结果中。函数只做字形级冲突判断，不加别名，也不修改字体。

修改：无。异常：无显式声明；缺少 `cmap` 或 `glyf` 表的情况由实现处理。

调用前必须先消歧。自动名（`glyphNNNNN`）可以先用 `plan_alias`；普通同名手工字形必须用 `rename_glyphs` 或 `renamed_copy` 显式改名。常规合并使用 `FontMerger.merge_two`，它内部有更宽的规划器。未消歧时，同名的普通手工字形即使有独有码位也会被报告删除。

### `plan_alias(main_font, base_font, tag='b', index=1)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | 必填 | 主字体，只读。 |
| `base_font` | `TTFont` | 必填 | 打底字体，只读。 |
| `tag` | `str` | `'b'` | 别名前缀，插入 `{tag}{index:03d}.{name}`。 |
| `index` | `int` | `1` | 别名模板中的序号。 |

返回：`dict[str, str]`，把打底旧名映射到别名。只包含形如 `glyphNNNNN` 的自动名冲突；普通手工名不包含。合并器内部另有更宽的规划函数用于自身冲突处理，此处保留 `plan_alias` 的历史公共契约。手工同名需要显式 `rename_glyphs` 或 `renamed_copy`，或使用 `FontMerger.merge_two`；单靠公共 `plan_alias` 不能消除风险。

修改：无。异常：无。

## 2. 字形改名

仓库源码：[core/glyph_rename.py](../../core/glyph_rename.py)。

### `alias_name(name, taken, tag='b', index=1)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | 原字形名。 |
| `taken` | `str` 容器 | 必填 | 不能复用的名字集合；只做成员测试。 |
| `tag` | `str` | `'b'` | 前缀。 |
| `index` | `int` | `1` | 序号；格式为 `{tag}{index:03d}.{name}`，候选名已存在时追加 `_n`。 |

返回：新的 `str`。修改：无。异常：无。

### `rename_glyphs(font, mapping)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `font` | `TTFont` | 必填 | 就地修改的字体。 |
| `mapping` | `dict[str, str]` | 必填 | 旧名到新名；值等于键的条目被忽略。 |

返回：同一个 `font`。就地修改 `font`：字形序、`glyf` 字形与复合组件、CFF/CFF2 的 charstring、charset 与 FDSelect 映射、`hmtx`/`vmtx` 度量、全部 cmap 子表（含 format 14 项）、VORG 记录、HVAR/VVAR DeltaSetIndexMap，以及 GSUB/GPOS/GDEF 中的字形引用。改动字形序前会先解压惰性 `gvar`。

异常：`ValueError`，映射会产生重复字形名时抛出。

### `renamed_copy(font, mapping)`

参数：`font`（`TTFont`，只读）；`mapping`（`dict[str, str]`）。返回：应用 `rename_glyphs` 后的深拷贝。修改：无。异常：与 `rename_glyphs` 相同的 `ValueError`。空映射也返回深拷贝。

## 3. 命名

仓库源码：[core/naming.py](../../core/naming.py) 与 [utils/detect.py](../../utils/detect.py)。

### `apply_naming(output_font, main_family, all_copyrights)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `output_font` | `TTFont` | 必填 | 就地修改的字体。 |
| `main_family` | `str` | 必填 | 首选族名。`get_family` 的返回值是携带各语言 name 记录的 `str` 子类；普通 `str` 也可接受。 |
| `all_copyrights` | `list[str]` | 必填 | 版权字符串。`get_copyrights` 的返回值是携带语言记录的 `str` 子类；普通字符串按未标注语言的补充文本处理。 |

返回：同一个 `output_font`。就地修改 `name` 表：族名追加一次 `\" mod\"` 后缀（重复调用不叠加），按现有记录派生各语言的身份记录（1、2、3、4、6、16、17），版权记录（0）保留所有语言且合并不新增翻译，PostScript 名由族名与样式加哈希后缀确定。CFF1 的 `fontNames`、`FamilyName` 与 `FullName` 与 PostScript/族名身份同步。版本、PANOSE、厂商、商标等记录不改写；CFF2 轴与实例命名不重建。

异常：字段无法编码且找不到等价 Unicode 语言时抛 `ValueError`；fontTools 的 name 记录错误可能向外传播。

### `get_family(font)`

参数：`font`（`TTFont`，只读）。返回：首选族名 `str`。实现优先英文记录，同语言内优先 nameID 16，其次 nameID 1，并按确定的平台与语言规则决出并列项。找到记录时返回携带全部可解码族名记录的 `str` 子类（私有 `_name_records`），比较、切片与格式化行为仍是普通 `str`；无可解码记录时返回普通字符串 `'Font'`。

修改：无。异常：无；无法解码的记录告警后跳过。

### `get_copyrights(*fonts)`

参数：任意数量 `TTFont`，只读。返回：`list[str]`，按输入顺序为每个存在可解码 nameID 0 记录的字体提供一个元素；没有该记录的字体不产生元素，因此列表可能比参数少。每个元素是携带该版权全部语言记录的 `str` 子类（私有 `_name_records`）。

修改：无。异常：无；解码失败告警后跳过。

## 4. 字形注入

仓库源码：[core/glyph_copy.py](../../core/glyph_copy.py)。

### `merge_glyphs_via_ttx(main_font, base_font, glyphs_to_add, use_ttx=None)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | 必填 | 所有未复制结构的来源；内容不被修改。 |
| `base_font` | `TTFont` | 必填 | 被复制字形、度量、cmap 项与变化数据的来源；按只读处理，可能发生惰性解压。 |
| `glyphs_to_add` | `str` 可迭代对象 | 必填 | 请求复制的字形名；组件与依赖闭包由内部补齐。 |
| `use_ttx` | `bool` 或 `None` | `None` | `None` 时任一字体含 CFF/CFF2 走 TTX，双方都是 `glyf` 时走对象复制；`True` 强制 TTX；双方都有 `glyf` 时 `False` 强制对象复制。 |

返回：新的 `TTFont`。工作副本会剥离打底布局表，布局特性应由 `merge_ot_features` 单独合并。复制字形的 cmap 项会补入，结果对象附带一份仅供内存使用的来源映射，用于分块同源复制；该映射不会写进字体文件。

修改：输入字体内容不被编辑。函数写临时 TTX 文件并在返回前清理。异常：缺打底组件或注入字形无法编译时抛 `ValueError`；子进程与 TTX 错误向外传播；不返回部分字体。

## 5. 轮廓转换与静态实例

仓库源码：[format/converter.py](../../format/converter.py) 与 [format/static_extract.py](../../format/static_extract.py)。

### `glyf_to_cff(font)`

参数：`font`（`TTFont`，只读）。返回：新的 CFF 轮廓 `TTFont`，`sfntVersion='OTTO'`。输入不被修改，转换在深拷贝上进行；已是 CFF 的输入返回未改动的深拷贝。

返回值上的行为与副作用：移除 TrueType hinting，逐字形用三次曲线近似转成 Type 2 charstring，深拷贝非轮廓表，并应用 Windows/Office 兼容修复（CFF `Weight`、RIBBI nameID 2、nameID 16/17、下划线默认值、OS/2 v3 字段、checksum 归零）。删除清单中的 DSIG、PCLT、LTSH、hdmx、VDMX、meta、trak 会被去掉。

异常：字体仍含可变表（`fvar`、`gvar`、`HVAR`、`VVAR`、`MVAR` 或 `cvar`）时抛 `ValueError`；任一字形无法转换时也抛 `ValueError`。

### `cff_to_glyf(font)`

参数：`font`（`TTFont`，只读）。返回：新的 glyf 轮廓 `TTFont`。已是 glyf 的输入返回未改动的深拷贝。

返回值上的行为与副作用：移除 hinting，用 `Cu2QuPen(max_err=1.0)` 近似三次曲线，重算字形边界，构建 `loca` 与 TrueType `maxp` 1.0，保留 `post` 2.0 字形名，修正 `hhea.numberOfHMetrics`，并删除 `cvt `/`fpgm`/`prep`/`gasp`/`VORG`/`DSIG`。删除 VORG 前把显式原点折进 `vmtx` 的 top side bearing。

异常：可变字体输入或字形转换失败时抛 `ValueError`；不伪造空字形。

### `convert_font_format(font, to_cff)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `font` | `TTFont` | 必填 | 输入字体，只读。 |
| `to_cff` | `bool` | 必填 | `True` 输出 CFF，`False` 输出 glyf。 |

返回：新的 `TTFont`。输入已是目标轮廓技术时返回未改动的深拷贝，否则委托 `glyf_to_cff` 或 `cff_to_glyf`。修改：无。异常：被委托函数的 `ValueError`。

### `variable_to_static(font, remove_overlaps=False)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `font` | `TTFont` | 必填 | 输入字体，只读。 |
| `remove_overlaps` | `bool` | `False` | 是否再执行 fontTools 布尔并集去重叠；该操作会改写轮廓，保真比对默认关闭。 |

返回：新的 `TTFont`。非可变输入返回深拷贝。可变输入按每个轴的默认值实例化；CFF2 输出转成 CFF，再保存并重载一次以统一表视图。实例化抛错时记录 `[警告] 实例化失败` 并返回原字体的深拷贝，结果可能仍是可变字体。去重叠失败会告警并跳过。

修改：无。异常：实例化失败路径不抛；其他 fontTools 错误不做转换。

## 6. 缩放与基线偏移

仓库源码：[format/transform.py](../../format/transform.py)。

### `scale_font(font, scale, baseline_offset)`

| 参数 | 类型 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| `font` | `TTFont` | 必填 | 无 | 就地修改并返回的字体。 |
| `scale` | `float` | 必填 | 倍率 | `1.0` 为恒等，`1.1` 为 110%。必须是有限正数。 |
| `baseline_offset` | `float` | 必填 | 字体设计单位 | 纵向偏移，向上为正。必须是有限数。 |

返回：同一个 `font`。`scale == 1.0` 且偏移为 `0` 时立即返回。其他组合会移除 hinting 与过期像素缓存（cvt/cvar/fpgm/prep/gasp/hdmx/LTSH/VDMX/DSIG），应用仿射变换，更新纵向原点、`VORG`、`hmtx`/`vmtx`、head 边界与纵向度量，并保持 `head.unitsPerEm` 不变。

异常：缩放非有限或非正、偏移非有限、无法识别轮廓格式，或字体含 `VARC` 表时抛 `ValueError`。

### `apply_scale_offset(font, scale_percent, baseline_offset)`

| 参数 | 类型 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| `font` | `TTFont` | 必填 | 无 | 就地修改并返回的字体。 |
| `scale_percent` | `float` | 必填 | 百分比 | `100.0` 为恒等；除以 100 转成倍率。 |
| `baseline_offset` | `float` | 必填 | 字体设计单位 | 向上为正。 |

返回：同一个 `font`，实现为 `scale_font(font, scale_percent / 100.0, baseline_offset)`。修改与异常同 `scale_font`。

## 7. 子集与 webfont 输入

仓库源码：[format/subsetter.py](../../format/subsetter.py) 与 [format/webfont.py](../../format/webfont.py)。

### `create_glyph_subset(font, glyph_names, strip_layout=True)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `font` | `TTFont` | 必填 | 源字体，不修改。 |
| `glyph_names` | `str` 可迭代对象 | 必填 | 请求的字形名。`.notdef` 始终保留；缺失名字告警后忽略，与历史接口一致。 |
| `strip_layout` | `bool` | `True` | 子集化前移除 GSUB、GPOS、GDEF、BASE、VORG、JSTF。`False` 保留布局表，让 Subsetter 把布局输出字形纳入闭包。 |

返回：由 fontTools `Subsetter` 同步裁剪的新 `TTFont`。组件、布局输出与度量闭包由 Subsetter 处理。Subsetter 默认删表清单中的表（例如 DSIG、JSTF、LTSH 及旧的位图或 Graphite 表）会以 `[子集警告]` 行提示后删除；其他结构性失败向外传播。

修改：输入不变。异常：除已告警的缺失名字外，`Subsetter` 或 fontTools 错误会抛出。

### `unwrap_webfont(path)`

参数：`path`（`str` 或路径对象）。返回：从 WOFF/WOFF2 文件加载、`flavor = None` 的新 `TTFont`。修改：无。异常：fontTools 加载错误。

## 8. Axis 并集与可变数据搬运工具

仓库源码：[core/merger.py](../../core/merger.py) 与 [format/vf_axes.py](../../format/vf_axes.py)。合成数学本身见[轴映射与可变数据合成](variation-model.md)。

### `axes_compatible(main_font, base_font)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | 必填 | 主字体，只读。 |
| `base_font` | `TTFont` | 必填 | 打底字体，只读。 |

返回：`bool`。仅当两个字体都为可变、都使用 `glyf` 轮廓、fvar 轴列表在顺序、tag 与 min/default/max 上完全一致，且 avar 分段映射一致时才为 `True`。这是 `transfer_glyph_variations` 进行 gvar 增量 1:1 搬运的前提。

修改：无。异常：无显式声明。

### `transfer_glyph_variations(result, base_var, glyph_names)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `result` | `TTFont` | 必填 | 合并结果字体，就地修改。 |
| `base_var` | `TTFont` | 必填 | 可变打底字体，只读。 |
| `glyph_names` | `str` 可迭代对象 | 必填 | 需要复制 gvar 增量的字形。 |

返回：`int`，实际复制了增量的字形数。没有打底增量、或任一元组的轴数与结果 fvar 不同时，跳过该字形。结果的 gvar 条目为深拷贝。至少复制一个字形时，用 fontTools `varLib.hvar.add_HVAR` 从幽灵点重建 HVAR；重建失败以 `[增量]` 告警，不抛出。

修改：就地修改 `result`（gvar 条目，可能还有 HVAR）。异常：无显式声明；HVAR 重建错误被捕获。

### `union_axes(main_font, base_font)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | 必填 | 就地修改；必须含 `fvar` 才会变化。 |
| `base_font` | `TTFont` | 必填 | 只读；其轴范围与独有轴并入主字体。 |

返回：新增轴的 `list[tuple[str, float, float, float]]`，元素为 `(axisTag, min, default, max)`；任一方非可变时返回空列表。就地修改主字体：共有轴范围取并集但保留主默认值，打底独有轴追加，STAT 轴记录、fvar 实例坐标、avar 恒等段与 ItemVariationStore region 列表同步。VarStore 扩展失败只记录日志，不抛出。

异常：除未捕获的 fontTools 表错误外，无显式异常。

### `axis_union_merge(main_font, base_font)`

两个参数都是 `TTFont`：`main_font` 就地修改且必须含 `fvar`，`base_font` 只读。返回值与异常同 `union_axes`；这是同一操作的公共包装入口。

## 9. 表级合并入口

仓库源码：[tables/base.py](../../tables/base.py) 与 [tables/ot_merge.py](../../tables/ot_merge.py)。

### `merge_all_tables(merged_font, main_font, base_fonts, added_glyphs=None)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `merged_font` | `TTFont` | 必填 | 结果字体，由注册的处理器就地修改。 |
| `main_font` | `TTFont` | 必填 | 主字体，只读。 |
| `base_fonts` | `TTFont` 可迭代对象 | 必填 | 打底字体，只读。 |
| `added_glyphs` | `str` 可迭代对象或 `None` | `None` | 传给每个处理器的可选新增字形名集合。 |

返回：`None`。函数遍历结果字体与全部打底字体表 tag 的并集（跳过 `GlyphOrder`），按排序后的 tag 调用 `register(tag)` 注册的处理器。单个表的异常会被捕获，打印 `[表合并警告]` 与 traceback，其余表继续。

重要边界：本入口不被 `merge_two` 调用。它会重放已注册的 `fvar` 与 OpenType 处理器，不是合并收尾器。合并器改用 `merge_ot_features`、表策略步骤与元数据重算器。当前注册 tag：`GDEF`、`GPOS`、`GSUB`、`OS/2`、`avar`、`cmap`、`fvar`、`head`、`hhea`、`hmtx`、`kern`、`maxp`、`name`、`post`、`vhea`、`vmtx`。

### `prune_base_layout(base_font, kept_glyphs)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `base_font` | `TTFont` | 必填 | 只读；在深拷贝上修剪。 |
| `kept_glyphs` | `str` 可迭代对象 | 必填 | 合并后存活的打底字形；`.notdef` 自动加入。 |

返回：只含 GSUB/GPOS/GDEF 的新 `TTFont`，用 fontTools Subsetter 闭包修剪；Subsetter 失败时返回 `None` 并打印 `[OT修剪]` 警告。结果的字形序是修剪后的顺序，供后续引用检查。

修改：输入不变。异常：修剪失败路径不抛。

### `merge_ot_features(main_font, base_font, kept_glyphs)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | 必填 | 就地合并；其布局优先。 |
| `base_font` | `TTFont` | 必填 | 只读。 |
| `kept_glyphs` | `str` 可迭代对象 | 必填 | 已复制进结果的打底字形。 |

返回：同一个 `main_font`。函数把打底布局修剪到 `kept_glyphs`，按主优先合并存活 lookup 与 feature，重映射索引与字形名，并同步 GDEF 字类、VariationIndex 偏移与 mark 集合索引。修剪失败时记录 `[OT合并] 打底布局修剪失败`，主布局保持不变。

异常：打底 FeatureVariations 条件不兼容或布局引用悬空时抛 `ValueError`；fontTools 错误可能向外传播。

## 10. 布局对象辅助

仓库源码：[tables/layout_union.py](../../tables/layout_union.py) 与 [tables/varstore.py](../../tables/varstore.py)。这些函数操作 fontTools otTables 对象，自身不校验整个字体。

### `layout_glyph_names(font)`

参数：`font`（`TTFont`，只读）。返回：GSUB、GPOS 或 GDEF 引用到的字形名 `set[str]`。修改：无。异常：无显式声明。

### `remap_glyph_names(obj, ren, seen=None)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `obj` | otTables 对象、`dict` 或 `list` | 必填 | 就地修改的对象树。 |
| `ren` | `dict[str, str]` | 必填 | 旧名到新名；未匹配的字符串保持原样。 |
| `seen` | `set` 或 `None` | `None` | 内部递归保护，调用方不传。 |

返回：`None`。就地修改对象树。异常：无显式声明。

### `offset_var_devices(obj, delta, seen=None)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `obj` | otTables 对象、`dict` 或 `list` | 必填 | 就地修改的对象树。 |
| `delta` | `int` | 必填 | 加到每个 VariationIndex outer 索引上的值。 |
| `seen` | `set` 或 `None` | `None` | 内部递归保护。 |

返回：`None`。只修改 `DeltaFormat == 0x8000` 的设备；`NO_VARIATION_INDEX` 哨兵跳过。异常：无显式声明。

### `remap_feature_variations(fv, index_map)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `fv` | FeatureVariations 对象或 `None` | 必填 | 就地修改；`None` 立即返回。 |
| `index_map` | `dict[int, int]` | 必填 | 旧 FeatureIndex 到新 FeatureIndex。 |

返回：`bool`。`True` 表示至少一条替换记录引用了映射中不存在的 FeatureIndex，该变体已失效，调用方应拒绝或丢弃；`False` 表示所有索引都已重写。就地修改 `fv`。异常：无显式声明。

### `resort_layout(font)`

参数：`font`（`TTFont`，就地修改）。返回：同一个 `font`。按当前字形序排序 Coverage 及其并行数组，包括 PairValueRecord 顺序与 GDEF MarkGlyphSets、AttachList、LigCaretList 的 coverage。异常：无显式声明。

### `LayoutUnion(tag)`

| 成员 | 参数 | 返回 | 就地修改 | 异常 |
| --- | --- | --- | --- | --- |
| `__init__(tag)` | `tag`：`str`，必填，`'GSUB'` 或 `'GPOS'` | 收集器对象 | 建立空状态 | 其他 tag 抛 `ValueError` |
| `add_from(base_table, ren, var_offset=0, mark_set_remap=())` | `base_table`：otTables GSUB/GPOS；`ren`：`dict[str,str]`；`var_offset`：`int`，默认 `0`；`mark_set_remap`：`int` 序列，默认 `()` | `None` | 只改收集器状态；输入表被深拷贝 | FeatureVariations 条件不一致或内部引用无效时抛 `ValueError` |
| `finalize()` | 无 | 新的 otTables GSUB/GPOS 表；没有 feature 时返回 `None` | 无 | 无显式声明 |

`add_from` 参数语义：

- `base_table`：来源 otTables GSUB 或 GPOS 表。函数先深拷贝，不修改调用方传入的表。
- `ren`：字形名映射（旧名到新名），应用于复制后的 lookup 与 FeatureVariations 中的 lookup。未列出的名字保持不变。
- `var_offset`：本来源 GDEF VarData 在并集中的 outer 基址。它会被加到复制后 lookup 里每个 VariationIndex 的 outer 索引；`NO_VARIATION_INDEX` 保持不变。本来源没有 GDEF VarData 时传 `0`。
- `mark_set_remap`：本来源局部 MarkGlyphSetsDef 索引到并集索引的映射。只对 LookupFlag 置了 bit 4 的 lookup 生效；传空序列表示不做重映射。

`add_from` 还会重映射 feature 索引、script 与 language system。`finalize` 按 language system 归并 feature 后返回表对象，不把表装入字体。

### `MarkGlyphSetUnion()`

| 成员 | 参数 | 返回 | 就地修改 | 异常 |
| --- | --- | --- | --- | --- |
| `add(mark_glyph_sets, remap_name=None, alive=None, order_index=None)` | `mark_glyph_sets`：MarkGlyphSetsDef 或 `None`；`remap_name`：`dict[str,str]` 或 `None`；`alive`：`set[str]` 或 `None`；`order_index`：`dict[str,int]` 或 `None` | `list[int]`，局部集合索引到并集索引 | 收集器状态 | 无显式声明 |
| `build(order_index=None)` | `order_index` 可选字形序映射 | `otTables.MarkGlyphSetsDef`；空并集返回 `None` | 无 | 无显式声明 |

相同内容的集合会去重。`add` 对 `None` 输入返回 `[]`。对象至少持有一个集合时为真。

`add` 参数语义：

- `mark_glyph_sets`：要并入的一份 MarkGlyphSetsDef。传 `None` 时返回 `[]`，收集器状态不变。
- `remap_name`：字形名映射（旧名到新名），在筛选与排序之前应用。传 `None` 时名字保持不变。
- `alive`：存活字形集合。传 `None` 表示不筛选；给集合时，先应用 `remap_name`，再把每个复制 coverage 中不在集合内的字形删掉。
- `order_index`：字形名到 GID 的映射，用于排序。传 `None` 时按字典序排序；提供映射时按 GID 排序，映射中缺失的名字排在末尾。返回列表为每个输入 coverage 给出一个并集索引。

`build` 参数语义：`order_index=None` 时按每个已存 coverage 的当前顺序写出；提供映射时按 GID 排序，缺键名字排在末尾。`build` 对空并集返回 `None`，且不修改收集器。

### `VarStoreUnion()`

| 成员 | 参数 | 返回 | 就地修改 | 异常 |
| --- | --- | --- | --- | --- |
| `add(var_store)` | `var_store`：otTables VarStore 或 `None` | `int`，新增 VarData 的基址偏移；`None` 返回 `0` | 收集器状态；复制 VarData 条目 | 无显式声明 |
| `build()` | 无 | `otTables.VarStore`；无数据返回 `None` | 无 | 无显式声明 |

Region 按 start/peak/end 三元组去重，VarData 行依次追加，其 `VarRegionIndex` 重映射到并集 region 表。对象至少持有一个 VarData 时为真。

## 11. name 与 head 补全

仓库源码：[tables/name_table.py](../../tables/name_table.py) 与 [tables/head.py](../../tables/head.py)。

### `complete_vf_name_table(font, platformID=3, platEncID=1, langID=0x409)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `font` | `TTFont` | 必填 | 就地修改。 |
| `platformID` | `int` | `3` | 新记录的平台 ID，默认 Windows。 |
| `platEncID` | `int` | `1` | 平台编码 ID，默认 Unicode BMP。 |
| `langID` | `int` | `0x409` | 语言 ID，默认英语（美国）。 |

返回：同一个 `font`。缺少 `fvar` 或 `name` 时不做任何事。缺 nameID 16（排印族名）与 17（排印子族名）时补上，缺 nameID 25（可变字体 PostScript 名前缀）时补上，并为 `postscriptNameID` 为 `0xFFFF` 或 `None` 的每个 fvar 实例补 PostScript 名记录。nameID 1 缺失时不补 nameID 16。现有记录不删除。新记录只写到 `platformID`、`platEncID`、`langID` 指定的组合；该组合无需事先存在，因此可能为字体原先没有的平台或语言新增一组记录。取值使用 fontTools `getDebugName`，它可能返回其它平台或语言的记录；nameID 2 或实例子族名缺失时使用字面回退 `'Regular'`，PostScript 前缀与族名都缺失时前缀回退为 `'Font'`。这些回退值不是从字体读取的。本函数不等同于 `apply_naming` 的逐语言处理：它补一组指定记录，不为每个现有语言派生受保护的名称。

异常：所需记录无法读取或写入时，fontTools name 表错误向外传播。

### `fix_head_flags(font)`

参数：`font`（`TTFont`，就地修改）。返回：同一个 `font`。清除 WOFF2 残留 bit 11，设置 bit 0 与 bit 1（基线在 y=0、左边距在 x=0）。没有 `head` 表时不做任何事。异常：无显式声明。

## 12. 检测工具

仓库源码：[utils/detect.py](../../utils/detect.py)。

### `is_cff(font)`
参数：`font`（`TTFont`，只读）。返回：`bool`，存在 `CFF ` 或 `CFF2` 表时为 `True`。修改：无。异常：无。

### `is_ttf(font)`
参数：`font`（`TTFont`）。返回：`bool`，存在 `glyf` 表时为 `True`。修改：无。异常：无。

### `is_variable(font)`
参数：`font`（`TTFont`）。返回：`bool`，存在 `fvar` 表时为 `True`。修改：无。异常：无。

### `type_label(font)`
参数：`font`（`TTFont`）。返回：中文状态标签，例如 `'静态TTF'` 或 `'可变OTF'`；CFF/CFF2 记为 OTF，`glyf` 记为 TTF。修改：无。异常：无。

### `all_codepoints(font)`
参数：`font`（`TTFont`）。返回：`set[int]`，包含所有提供 `cmap` 映射的 cmap 子表中的全部码位；Unicode 与非 Unicode 子表都计入。修改：无。异常：无。

### `glyph_to_codepoints(font)`
参数：`font`（`TTFont`）。返回：`dict[str, set[int]]`，把每个字形名映射到所有 cmap 子表中出现的全部码位。修改：无。异常：无。

### `axis_space(font)`
参数：`font`（`TTFont`）。返回：`dict[str, tuple[float, float, float]]`，轴 tag 映射到 `(min, default, max)`；非可变字体返回 `{}`。修改：无。异常：无。

### `is_same_source(fonts)`
参数：`fonts`（`TTFont` 可迭代对象）。返回：`bool`。条件为：至少两个字体、全部含 `fvar`、轴三元组完全一致、轮廓技术一致（全 CFF 或全 glyf）。这是 webfont 分片的结构检查，不证明它们同源。修改：无。异常：无。

### `is_auto_glyph_name(name)`
参数：`name`（`str`）。返回：`bool`，fontTools post 3.0 的 `glyphNNNNN` 序号形式返回 `True`。修改：无。异常：无。

### 模块常量

- `AUTO_GLYPH_RE`：编译后的正则 `^glyph\d{5}$`，供 `is_auto_glyph_name` 使用。
- `EXEMPT_GLYPHS`：`{'.notdef', '.null', 'nonmarkingreturn'}`。

## 13. 保存防护

仓库源码：[utils/save.py](../../utils/save.py)。

### `save_font(font, path, flavor=None, recalcTimestamp=None)`

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `font` | `TTFont` | 必填 | 被保存的字体；其 `flavor` 属性会设为参数值。 |
| `path` | `str` 或 `Path` | 必填 | 输出路径，直接传给 `TTFont.save`；不创建父目录。 |
| `flavor` | `None`、`'woff'` 或 `'woff2'` | `None` | 输出容器。`None` 表示桌面 sfnt。该值不从扩展名推断；路径以 `.woff2` 结尾而 `flavor=None` 时写出的仍是桌面 sfnt 字节。 |
| `recalcTimestamp` | `None` | `None` | 只有 `None` 有效。它调用 `font.save(path)`，使用 fontTools 当前签名。传入 `True` 或 `False` 会把不支持的参数转给 `TTFont.save`，在写出文件前抛 `TypeError`。 |

返回：`(path, magic)`。`path` 为传入的路径对象；`magic` 为写文件后读回的前四字节。`flavor is None` 时，若魔数不在 `SFNT_MAGICS` 中则抛 `ValueError`；请求 web 容器时返回容器魔数，不做 sfnt 断言。

异常：桌面魔数非法时抛 `ValueError`；`recalcTimestamp` 非 `None` 时抛 `TypeError`；fontTools 保存错误向外传播。

`recalcTimestamp` 参数保留在签名中用于兼容，但当前只有 `None` 可用。要控制时间戳重算，请先设置 `font.recalcTimestamp` 属性，再用默认 `None` 调用 `save_font`；fontTools 把该属性保存在 `TTFont` 实例上，并在保存时读取。模块级辅助函数 `FontMerger.utils.save.default_flavor_for(path)` 把 `.woff2` 映射为 `'woff2'`、`.woff` 映射为 `'woff'`，其他扩展名映射为 `None`。它没有从包根再导出，调用方可用它显式实现按扩展名推断。

### `assert_sfnt(path)`
参数：`path`（`str` 或 `Path`）。返回：文件前四字节。异常：魔数不在 `SFNT_MAGICS` 中时抛 `ValueError`，消息提示 WOFF/WOFF2 应显式传入 web flavor。

### `SFNT_MAGICS`
可接受 sfnt 魔数的元组：`b'\x00\x01\x00\x00'`（TrueType 轮廓）、`b'OTTO'`（CFF 轮廓）与 `b'true'`（Apple TrueType）。

## 14. 包常量

- `SUPPORTED_EXTS`：`{'.ttf', '.otf', '.woff', '.woff2'}`。CLI 用于校验输入扩展名。
- `COLLECTION_EXTS`：`{'.ttc', '.otc'}`。CLI 用于拒绝字体集。
- `DEFAULT_ANSWERS`：交互默认答案，见[合并 API](merge-api.md)。

## 15. 副作用汇总

| 函数或类 | 返回新字体 | 就地修改输入字体 |
| --- | --- | --- |
| `rename_glyphs`、`apply_naming`、`scale_font`、`apply_scale_offset`、`union_axes`、`axis_union_merge`、`merge_ot_features`、`complete_vf_name_table`、`fix_head_flags` | 否 | 是 |
| `merge_glyphs_via_ttx`、`glyf_to_cff`、`cff_to_glyf`、`convert_font_format`、`variable_to_static`、`create_glyph_subset`、`renamed_copy`、`unwrap_webfont` | 是 | 否 |
| `save_font` | 否 | 写文件并设置 `font.flavor` |
| `merge_all_tables` | 否 | 是（通过处理器） |
| `prune_base_layout` | 是 | 否 |
| `resolve_conflicts`、`plan_alias`、`alias_name`、`get_family`、`get_copyrights`、`is_cff`、`is_ttf`、`is_variable`、`type_label`、`all_codepoints`、`glyph_to_codepoints`、`axis_space`、`is_same_source`、`is_auto_glyph_name`、`layout_glyph_names` | 否 | 否 |

这些辅助函数有意不保证的行为见[支持边界](limitations.md)。
