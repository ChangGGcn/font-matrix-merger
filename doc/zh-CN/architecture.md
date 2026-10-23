# 架构：合并路径、流程与数据不变量

本文对应 **v0.2.1**。默认值与支持行为以源码为准。
源码链接按仓库目录给出。运行 ZIP 含本文档与运行库，不收录仅仓库可用的 `tests/`、`build/` 目录；本文提到这些目录时只写代码路径并标注“仅仓库”，不生成相对链接。

相关文档：[使用指南](usage.md)、[合并 API](merge-api.md)、[轴映射与可变数据合成](variation-model.md)、[同源分片与验证](subsets-and-verification.md)、[支持边界与故障排查](limitations.md)、[模块与脚本参考](script-reference.md)。

## 1. 定位与入口

库处理两类任务，二者实现不同，不共享合并流程。

| 入口 | 用途 | 返回与所有权 |
| --- | --- | --- |
| `FontMerger.merge_two(main, base)` | 异源字体合并一级 | 返回 `TTFont`；不做命名、不保存；旧轴并集回退路径可能就地修改主字体，需保留输入时传副本 |
| `merge_fonts(main, bases, interactive=False, answers=None)` | 一行完成多级异源合并 | 先 `deepcopy` 主字体，逐级 `merge_two`，最后命名并清 `flavor`；返回 `TTFont`，不保存 |
| `merge_subsets(subsets, out_path=None, ...)` | 同源 webfont 分片并集 | 就地修改 `subsets[0]` 作为结果；`out_path` 为 `None` 时不保存；`verify=True` 失败抛 `AssertionError` |
| `apply_naming(font, main_family, all_copyrights)` | 就地生成修改版名称 | 返回同一 `TTFont`；`merge_two` 不调用它 |

入口参数与默认值：

| 函数 | 形参 | 类型 | 默认值 | 含义、单位与副作用 |
| --- | --- | --- | --- | --- |
| `merge_two` | `main`, `base` | `TTFont` | 无（必填） | 输入字体对象；旧轴并集回退路径可能就地修改 `main` |
| `merge_fonts` | `main_font` | `TTFont` 或路径 | 无 | 读取后深拷贝主字体 |
| | `base_fonts` | `list` | 无 | 打底字体或路径列表，顺序即优先级 |
| | `interactive` | `bool` | `False` | 是否交互询问；`False` 时使用 `DEFAULT_ANSWERS` |
| | `answers` | `dict` 或 `None` | `None` | 覆盖询问答案，键为 `ask` key |
| `merge_subsets` | `subsets` | `list` | 无（必填） | 分片路径或字体；`subsets[0]` 会被就地修改 |
| | `out_path` | `str` 或 `None` | `None` | 输出文件系统路径；`None` 时不落盘 |
| | `tag` | `str` | `"s"` | 别名前缀，无单位 |
| | `output_flavor` | `str` 或 `None` | `None` | `None` 时若 `out_path` 给定则按扩展名推断；`out_path` 为 `None` 时不处理 `flavor`，结果可能保留输入字体的容器标记（例如传入的 TTFont 仍是 woff2）。`"woff"`/`"woff2"` 显式选择 web 容器 |
| | `complete_name_table` | `bool` | `True` | 补 nameID 16/17/25 与实例 PostScript 名 |
| | `fix_head_flags` | `bool` | `True` | 清 `head.flags` 的 WOFF2 残留位 |
| | `verify` | `bool` | `False` | 合并后运行 `verify_merge()`；失败抛 `AssertionError` |
| | `verbose` | `bool` | `True` | 日志开关 |
| `apply_naming` | `output_font` | `TTFont` | 无（必填） | 就地修改并返回同一对象 |
| | `main_family` | `str` 或带语言的族名 | 无 | 主族名来源 |
| | `all_copyrights` | `list` | 无 | 版权文本列表，按语言合并 |

以上参数没有长度或坐标单位；`out_path` 使用文件系统路径。`apply_naming()` 遇到无法编码的 name 记录时会迁到同语言 Unicode 记录；无法确定语言时抛 `ValueError`。其余返回与异常见表中说明和下文各节。

命令行入口 `FontMerging.py` 只提供交互模式，不接受位置参数；非交互调用请用库 API。

最小库调用，所有导入均已列出：

```python
from FontMerger import (FontMerger, apply_naming, get_copyrights,
                        get_family, load_font, save_font)

main = load_font("Main.ttf")
base = load_font("Base.ttf")
merged = FontMerger().merge_two(main, base)
merged = apply_naming(merged, get_family(main), get_copyrights(main, base))
save_font(merged, "Merged.ttf")
```

命名所有权：`merge_two()` 生成合并字体但不生成修改版名称；`merge_subsets()` 不调用 `apply_naming()`（不改 Family 的 `mod` 后缀、不做版权合并），但默认 `complete_name_table=True` 会补 nameID 16/17/25 与实例 PostScript 名，默认 `fix_head_flags=True` 会清 `head.flags` 的 WOFF2 位。修改版命名由 CLI、`merge_fonts()` 或调用方在合并后调用 `apply_naming()` 完成。`apply_naming()` 只改身份字段（nameID 1、2、3、4、6、16、17 与版权 ID 0），不改版本、厂商、商标、授权记录与 VF 的轴/实例名称。

## 2. 两条互不复用的路径

### 2.1 异源路径

入口是 [`core/merger.py`](../../core/merger.py) 的 `FontMerger.merge_two()`。一次调用只合并一个打底字体；多级打底由调用方循环，上一级结果作为下一级主字体。

该路径按主/打底的“静态或可变”与“glyf 或 CFF/CFF2”分类，共 4×4 种组合，方法分派见 `merge_two()` 与 `_sOTF_sOTF()`、`_vTTF_vTTF()` 等 16 个方法。主字体可变且打底是静态时，用户可在问答中选择可变或静态输出：选可变保留主 VF，选静态先实例化主字体。主/打底都可变时默认保留主 VF，并先尝试跨设计空间合成；合成不受支持或失败才回退为“打底按默认实例化”。

### 2.2 同源分片路径

入口是 [`core/subset_merge.py`](../../core/subset_merge.py) 的 `merge_subsets()`，实现类为 `SameSourceSubsetMerger`。

该路径不调用 `merge_two()`。`merge_two()` 对可变×可变输入在支持条件下会先尝试跨设计空间合成：主 VF 保留，打底增量重参数化到合并空间；glyf 字形走对象级复制，CFF/CFF2 走 TTX。只有合成不受支持或自检失败时才回退为实例化打底，此时打底变化数据可能丢失。同源分片共享同一轴空间，不需要合成或轴并集，直接并集即可保留各分片的 `gvar` 与布局数据，因此这类输入应使用 `merge_subsets()`。

同源判定由 [`utils/detect.py`](../../utils/detect.py) 的 `is_same_source()` 给出：至少 2 个字体，全部含 `fvar`，轴集合与 min/default/max 完全一致，轮廓技术一致。`merge_subsets()` 在只有 1 个分片时把它作为基底处理；2 个及以上才做同源校验。CFF/CFF2 分支要求分片是 CFF2，纯 CFF1 分片会被拒绝。CFF2 分片还要求共享同一 VarStore 与 GlobalSubrs 结构（见第 8 节）。

## 3. 16 组合矩阵

分类依据：`is_variable()` 判断是否有 `fvar`；`is_ttf()` 判断是否有 `glyf`；否则按 CFF/CFF2 处理。矩阵行为主字体，列为打底字体。

| 主字体 \ 打底字体 | 静态 OTF（CFF） | 静态 TTF（glyf） | 可变 OTF（CFF/CFF2） | 可变 TTF（glyf） |
| --- | --- | --- | --- | --- |
| 静态 OTF | CFF glyph 经 TTX 注入；输出 CFF | 打底转 CFF 后注入；输出 CFF；询问 TTF/OTF 仅记录 | 打底按默认实例化，必要时 CFF2→CFF；输出静态 CFF | 打底实例化后转 CFF；输出静态 CFF |
| 静态 TTF | 打底转 glyf 后注入；输出 TTF；询问 TTF/OTF 仅记录 | glyf 对象级复制；输出 TTF | 打底实例化后转 glyf；输出静态 TTF | 打底实例化后 glyf 对象复制；输出静态 TTF |
| 可变 OTF | 询问“可变/静态”：静态则实例化主字体；可变则保留主 VF，打底静态字形按默认轮廓并入 | 同左，打底先转 CFF/CFF2 | 先尝试 CFF2 可变数据合成；失败回退轴并集并把打底实例化；输出保持 VF | 跨轮廓可变数据合成不支持；回退轴并集并把打底实例化、转轮廓；输出保持 VF，打底字形静态 |
| 可变 TTF | 询问“可变/静态”：静态则实例化主字体；可变则保留主 VF，打底静态字形按默认轮廓并入 | 同左，打底保持 glyf | 跨轮廓可变数据合成不支持；回退轴并集并把打底实例化、转 glyf；输出保持 VF，打底字形静态 | 先尝试 gvar 可变数据合成；失败回退轴并集并把打底实例化；同轴空间时按 1:1 搬运 gvar；输出保持 VF |

矩阵说明：

- 输出轮廓格式由主字体决定。跨格式单元格里的“导出 TTF/OTF”询问会被记忆，但当前实现不据此转换结果；真正改变代码路径的是“可变/静态”询问。`DEFAULT_ANSWERS` 中相关键见 [`__init__.py`](../../__init__.py)。
- 静态主字体与可变打底：打底只按默认实例合并，新增字形不随轴变化。
- 可变主字体与静态打底：用户选择可变输出时主 VF 保持原轴空间；选择静态则先实例化主字体。打底字形静态，不会因打底而新增轴。
- 可变主与可变打底：合成仅覆盖同一种轮廓技术，且双方都有对应变化数据（glyf 需 `gvar`，CFF2 需带 VarStore 的 CFF2）。合成要过 `verify_composition()` 抽样自检；不通过或抛异常时回退旧路径。旧路径先做轴并集，再实例化打底；轴空间与 `avar` 完全一致时，glyf 打底可按 `transfer_glyph_variations()` 1:1 搬运增量。CFF2 打底没有幽灵点 1:1 搬运路径，合成失败后其变化数据不保留。
- 输入 `.woff`/`.woff2` 由 `load_font()` 自动解包并清 `flavor`；`.ttc`/`.otc` 在 CLI 中被拒绝，需要先解包。支持的输入扩展名见 `SUPPORTED_EXTS` 与 `COLLECTION_EXTS`。

## 4. 单级异源合并流程

### 4.1 分派与回退

`merge_two()` 只做分类与分派，业务逻辑在 `_do_merge()` 与 `_do_merge_once()`。

合成路径的失败点包括：

- 轴空间规划返回 `None`，`_apply_axis_plan()` 外层抛 `RuntimeError`；
- 合并默认点实例化、布局变化搬运或 CFF2 合成抛异常；
- `verify_composition()` 自检失败。

任一异常被 `_do_merge()` 捕获，打印 `[合成] 回退到默认实例合并: <原因>`，再以 `compose=False` 重跑。回退是信息损失路径：打底字形停在默认实例，除非轴空间与 `avar` 完全一致且随后执行 1:1 gvar 搬运。

### 4.2 `_do_merge_once()` 的步骤

1. 预处理。合成路径先 `deepcopy` 主字体，归一打底 UPM，调用 `_apply_axis_plan()`，用 `instance_at_merged_default()` 得到合并默认点上的打底，再按开关执行 `transfer_base_layout()` 与 `_compose_cff2_base()`。旧路径执行 `union_axes()` 与 `_reparametrize_main_after_union()`，并判断 `axes_compatible()`；不一致时放弃增量搬运并实例化打底。
2. UPM 归一。主/打底 `head.unitsPerEm` 不同时调用 `_normalize_upm()`：用官方 `scale_upem()` 缩放打底，移除旧 hinting 环境，并用缩放前快照修正 VORG 逐字形 override。
3. CID 归一。按主/打底是否 CID 分四种分支处理，见表 4.3。
4. 轮廓格式对齐。glyf 与 CFF 不同则转换打底；CFF2 主与 CFF 打底、或 CFF 主与 CFF2 打底时，先对齐 CFF 版本。
5. 冲突与别名。`_plan_merge_aliases()` 为所有同名打底字形（`.notdef` 除外）生成别名，`renamed_copy()` 同步全部按名索引的结构；`resolve_conflicts()` 计算应丢弃的冲突集合；`to_add` 为空时诊断原因、合并 cmap 并进入收尾。
6. 字形注入。glyf+glyf 走 `merge_glyphs_object()`；CFF/CFF2/CID 走 `merge_glyphs_via_ttx()`；候选超过 5000 个时走 `_chunked_merge()`。注入失败打印原因并抛 `RuntimeError`，不返回缺码位的部分字体。
7. 可变数据收尾。`_finish_variable_merge()` 先接入打底 CFF2 HVAR，再按是否有合成计划选择 `reparametrize_gvar()`（并重建 HVAR）或 `transfer_glyph_variations()`；合成计划存在且开启 `verify_compose` 时执行抽样自检。
8. 打底布局合并。`_merge_base_layout_once()` 调用 `merge_ot_features()`；布局合并失败只告警，不改变已完成的字形。
9. 收尾。`_finalize_merge()` 统一普通、空新增、分块与 CID 出口，见第 9 节。

### 4.3 CID 分支

| 情形 | 处理 | 返回 |
| --- | --- | --- |
| 主 CID + 打底 CID | `cid_ufo_style_merge()`：`shift_cid_range()` 偏移打底 CID，保留主 CID 名字空间；复制 CharString 对象，追加打底 FDArray 并绑定各来源 Private；同步 cmap/UVS；保存并重载 | 进入 `_finalize_merge()` |
| 主 CID + 打底 name-keyed | 打底必要时先转 CFF，`ensure_cid_format()` 后走双 CID 路径 | 进入 `_finalize_merge()` |
| 主 CFF2（非 CID）+ 打底 CID | 打底 CFF 反子程序化后 `convertCFFToCFF2()`，保留 FDArray；继续常规注入 | 继续主流程 |
| 主 name-keyed CFF + 打底 CID | `cid_to_name()` 将打底统一为 name-keyed | 继续主流程 |

静态双 CID 路径不再压平到首个 FD，也不要求先把 CID 转 name-keyed。`cid_to_name()` 仍用于上述 name-keyed 归一分支。CID-keyed CFF2 作为主字体的可变输出保存问题与静态 CID/CFF 合并是两件不同的事，见 [支持边界](limitations.md)。

### 4.4 对象级复制与 TTX 往返

| 条件 | 路径 | 关键行为 |
| --- | --- | --- |
| 主/打底都是 glyf | `merge_glyphs_object()` | 逐字形深拷贝；组件依赖闭包；同名组件先改名；`hmtx`/`vmtx`/`gvar` 同步；`HVAR`/`VVAR` 映射补 `NO_VARIATION_INDEX`；cmap 并集 |
| CFF/CFF2/CID | `merge_glyphs_via_ttx()` | 剥离打底 OT 表；主/打底 `saveXML`；`inject_glyphs_xml()` 注入 CharStrings、FDArray、glyf、度量、VarIdxMap、maxp；子进程 `fontTools ttx` 编译；按注入前的 GlyphOrder 恢复字形名 |
| 候选字形超过 5000 | `_chunked_merge()` | 按 5000 分块注入；分块前要求同名归一已完成；任一块失败即抛错，不返回部分结果；全部完成后只执行一次可变收尾、布局合并与收尾 |

TTX 路径的关键约束是 post 3.0 二进制不保存字形名。注入函数返回目标 GlyphOrder，重载后必须按位置恢复，否则 cmap 与布局引用会对不上（`core/glyph_copy.py` 内注释）。

## 5. 字形身份、冲突与映射

### 5.1 主优先与部分码位冲突

- 主字体字形与码位映射全部保留。合并结果不允许打底覆盖主映射；`assert_cmap_union()` 会检查 Unicode 码位并集、主映射优先与 UVS 并集。
- 打底字形的去留有条件：有主字体未占用的码位、无码位、被组件闭包或 UVS 需要时保留；码位全部与主冲突且无其它依赖时丢弃。实现见 `resolve_conflicts()`。
- 同名字形不代表同轮廓。所有同名打底字形（`.notdef` 除外）先由 `_plan_merge_aliases()` 改名，再进入冲突判定；公共 `plan_alias()` 仅为兼容旧契约返回自动名字形的别名，不承担完整合并规划。
- 复合字形按组件闭包复制。组件在打底中缺失时明确抛错；组件的同名冲突同样先改名，不借用主字体轮廓（`_prepare_glyph_copy()`）。
- UVS 依赖的字形即使普通码位全部冲突也保留。异源合并入口的 `validate_input_uvs()` 会拒绝悬空 UVS 字形与非法默认 UVS。

### 5.2 改名同步范围

`rename_glyphs()` 一次更新所有按字形名索引的结构：GlyphOrder、glyf（含复合组件）、CFF/CFF2 CharStrings 与 charset、hmtx/vmtx、cmap 与 format 14 UVS、HVAR/VVAR DeltaSetIndexMap、VORG，以及 GSUB/GPOS/GDEF 的全部字形引用。gvar 在改名前物化，避免惰性解码基于旧名字。

### 5.3 cmap 与 format 0

`_copy_cmap_mappings()` 就地合并映射，行为包括：

- 主映射优先；Unicode 子表按格式范围同步（format 4 使用 U+FFFE 上限，format 12/13 支持全范围）。
- 非 Unicode 子表保持独立编码域，不把 Unicode 并集写进去。
- 所有 format 0 子表在任一实际映射 GID 大于 255 时升级为同平台/编码/语言的 format 6，保留原映射；GID 等于 255 仍合法。这样避免旧格式保存时的 8 位溢出。
- UVS 按 selector 并集；默认 UVS 在主映射不同且来源字形可保留时转为显式条目。

### 5.4 UPM 变换

UPM 不同只在打底侧处理，主字体 UPM 不变。`_normalize_upm()` 调用官方 `scale_upem()`，并处理官方版本可能遗漏的 VORG 逐字形 override。缩放前先移除打底 hinting 与像素缓存，避免指令继续引用旧设计单位。CLI 的缩放倍率与基线偏移是另一条路径，见 `scale_font()`。

## 6. 可变数据合成

### 6.1 归一化与 OT 语义

- 三层坐标：`user --fvar 归一化--> pre --avar--> norm`。OT 变体数据（gvar tuple 支撑、VarStore region、HVAR/VVAR 映射）的峰值在 post-avar 的 norm 空间。实现见 [`format/axis_mapping.py`](../../format/axis_mapping.py) 的 `PiecewiseLinear` 与 `AxisMapping`。
- `supportScalar` 语义：峰值 0 的轴被忽略；`lower < 0 < upper` 的支撑会被整条忽略；hat 不跨 0；合并域边界截断用半 hat。`refine_1d()` 保留 0 作为节点，`refine_support_rebased()` 处理默认点不重合的常数项。
- gvar 一个字形可有多个 tuple，渲染时按权重求和，因此源 tuple 可拆成多个合并空间 tuple。`reparametrize_gvar()` 执行该拆分并保留幽灵点。
- `VariationIndex` 的 `(outer, inner)` 是（VarData 序号，**行号**），不是 region 序号。`reparametrize_var_store()` 保持 ItemCount 与行序，只重分配列，因此引用无需改写；并集时只平移 outer 基址（`VarStoreUnion`）。
- CFF2 的 blend 操作数顺序为“默认值，增量块，数量，blend”；增量块个数由当前 `vsindex` 指向的 VarData region 数决定。`reparametrize_cff2()` 重写 CharStrings、GlobalSubrs 与 Private Subrs，并保持 VarData 序号；`merge_cff2_var_stores()` 拼接并集后由 `offset_cff2_vsindex()` 平移打底引用。
- HVAR/VVAR 的 `AdvWidthMap` 等是按字形名索引的 DeltaSetIndexMap。`VarIdxMap.preWrite` 要求覆盖全部字形，无增量字形必须显式给 `NO_VARIATION_INDEX`；CFF2 合成由 `merge_cff2_hvar()` 按字形名重建映射。
- `instantiateVariableFont()` 的用户坐标限制不套 `avar`，`getGlyphSet(location=...)` 会套 `avar`。自检采样点因此只用各轴 min/default/max（`avar` 的不动点）；比较用 `getGlyphSet()` 语义（`core/verify.py` 的 `_instance()` 与 `verify_composition()`）。

### 6.2 策略参数

参数定义在 [`core/merger.py`](../../core/merger.py) 的 `FontMerger.__init__()`。

| 形参 | 类型 | 默认值 | 含义与影响 |
| --- | --- | --- | --- |
| `compose_variations` | `bool` | `True` | 是否尝试跨设计空间合成；关闭时直接走旧的实例化/轴并集路径 |
| `compose_range` | `str` | `"main+extra"` | 合并轴范围策略。`"main+extra"`：共有轴用主范围，打底独有轴按打底范围加入；`"union"`：共有轴取两者最宽；`"main"`：只保留主轴 |
| `compose_fit` | `str` | `"exact"` | `"exact"` 精确拆分 hat；`"affine"` 只映射支撑端点与峰，体积更小但存在已知偏差，需以自检结果为准 |
| `avar_mode` | `int` | `0` | `0`：保留主 avar，打底数据经用户空间映射；`1`：忽略打底 avar；`2`：输出不使用 avar，移除 avar 表 |
| `verify_compose` | `bool` | `True` | 合成后是否运行 `verify_composition()`；失败抛异常并触发回退 |
| `compose_layout` | `bool` | `True` | 是否搬运打底的布局变化数据（GDEF ItemVariationStore 与 GPOS VariationIndex）；关闭时打底布局冻结在默认点 |

参数只影响合并策略，不改变输入字体对象；副作用仅限本次调用。返回类型与异常：`merge_two()` 返回 `TTFont`；合成失败回退，普通路径的结构自检失败或注入失败会抛出异常。

### 6.3 合成数据流

合成路径的主要步骤与代码位置：

| 步骤 | 关键函数 | 结果 |
| --- | --- | --- |
| 规划轴空间 | `plan_axis_space()` | 合并 fvar/avar 与“合并空间到打底空间”的映射 |
| 扩主字体并重算主数据 | `_apply_axis_plan()`、`reparametrize_gvar()`、`reparametrize_var_store()`、`_copy_axis_records()` | 主 fvar/avar/STAT/name 更新；主自身 gvar 与 GDEF/HVAR/VVAR/MVAR/BASE VarStore 跟随新空间 |
| 打底默认点实例 | `instance_at_merged_default()` | 打底在合并默认点的静态轮廓、度量与布局静态值 |
| 布局变化搬运 | `transfer_base_layout()`、`fold_layout_default()` | 打底 GDEF VarStore 与 GPOS VariationIndex 重参数化，行保持 |
| gvar 重参数化 | `reparametrize_gvar()` | 新字形按合并空间拆 tuple，并重建 HVAR |
| CFF2 重参数化 | `reparametrize_cff2()`、`merge_cff2_var_stores()`、`merge_cff2_hvar()` | blend/vsindex、VarStore 与打底 HVAR 并入 |
| 自检 | `verify_composition()` | 网格点上比对新增字形与打底、主字形与主字体；失败抛 `AssertionError` |

自检只覆盖抽样网格与抽样字形，不是所有轴位置的逐点证明。默认容差：轮廓 1 字体单位，字宽默认同轮廓容差；主流程调用时字宽容差为 3.0。CFF2 测试使用轮廓 0.01、字宽 4 的容差，原因是 blend 定点化与 HVAR 整数取整。整数残差与平台段限制见 [支持边界](limitations.md)。

### 6.4 回退与传统路径

合成失败后执行旧路径：

- `union_axes()` 就地把打底独有轴与更宽范围并入主字体，`_reparametrize_main_after_union()` 重算主 VarStore；
- `axes_compatible()` 检查轴空间与 avar 是否完全一致。一致时 glyf 打底仍可走 `transfer_glyph_variations()` 1:1 搬运 gvar 并重建 HVAR；CFF2 打底没有该路径；不一致时放弃增量搬运；
- 打底 `variable_to_static()` 到默认实例后合并。

这条路径会就地修改主字体。旧路径的输出仍是 VF，但打底字形的变化数据可能丢失。合并 avar 把一段用户区间压成一个归一化点时，`collapsing_flats()` 会报告不可逐点还原的区间，日志以 `[告警]` 打印；`avar_mode=2` 可放弃 avar 换取打底变化，但会改变主字体的插值语义。

## 7. 布局合并

### 7.1 异源路径

入口为 `merge_ot_features()`，由 `_merge_base_layout_once()` 调用。

1. `prune_base_layout()` 用官方 `Subsetter` 以存活字形为输入做闭包和布局修剪，只取回 GSUB/GPOS/GDEF。
2. GDEF 合并：GlyphClassDef 与 MarkAttachClassDef 主优先、打底补缺；MarkGlyphSetsDef 并集并重映射 LookupFlag bit4 的索引；GDEF VarStore 做 region/VarData 并集，打底 GPOS VariationIndex 的 outer 加基址。
3. GSUB/GPOS 合并：按源顺序复制打底 lookup 图，先校验全部引用字形存在，再建立完整的旧到新 lookup 索引映射，补齐嵌套上下文闭包。引用失效 lookup 的上下文规则整条删除，而不是删空动作后误变成 ignore 规则。同 tag feature 只在同一 Script/LangSys 内做 lookup 并集，主来源的参数与必需特性优先；打底 ScriptList/LangSys 并入，FeatureList 重新排序并重写所有 feature 索引。
4. FeatureVariations：主对应表不存在或为空（无 lookup 与 feature）时，合法的打底表（含 FV）可整体采用；否则不跨来源拼接打底 FV，保留主条件。打底 FV 引用失效 lookup 或 feature 时拒绝该表合并并保留主布局。
5. 收尾调用 `resort_layout()`，修复 Coverage 与并行数组的同序不变量。

### 7.2 同源并集路径

同源路径使用 `LayoutUnion`，逐分片 `add_from()`，最后 `finalize()`。

- 每个分片的 lookup 全部追加，字形名按该分片的改名表重映射，VariationIndex 按 GDEF VarData 基址偏移。
- 同 tag feature 在同一 LangSys 内归并，并保留必需特性。
- FeatureVariations 要求各分片条件集合与顺序严格一致，否则抛 `ValueError` 拒绝有损并集；相同位置的条件记录归并，空替换也保留。
- 最后按 tag 排序 FeatureList，重写默认、必需与 FV 的 feature 索引，并调用 `resort_layout()`。

### 7.3 排序与引用不变量

布局剪裁或 GID 变化后必须保持：

- Coverage 按 GID 升序，PairPos Format 1 的 PairValueRecord 按第二字形 GID 升序，MarkBase/MarkLig/MarkMark 的 Coverage 与并行数组同序；
- Context/ChainContext Format 1 的 Coverage 与 RuleSet 同序，ReverseChainSingleSubst 的 Coverage 与 Substitute 同序；
- LookupFlag bit4 的 MarkFilteringSet 指向存在的 GDEF mark 集合；
- FeatureList 重排后，ScriptList/LangSys 的 FeatureIndex、FeatureVariations 的 FeatureIndex 与替换 lookup 索引都有效。

`resort_layout()`（`tables/layout_union.py`）是统一收尾。结构检查由 `_check_layout_integrity()` 与 `_check_lookup_references()` 完成。

## 8. 同源分片并集

`merge_subsets()` 的输入顺序即合并顺序，`subsets[0]` 是基底并会被就地修改。核心步骤：

1. 强制加载逐字形表；glyf 调 `ensureDecompiled()`，防止复合组件仍持有旧 GID。
2. 同源校验：`is_same_source()`；CFF2 额外 `check_cff2_compatible()` 校验 GlobalSubrs 与 VarStore 结构。
3. 逐分片 `rename_map()`：自动名 `glyphNNNNN` 与“被该分片布局引用的同名重名”加别名；其余重名视为同源字形去重。
4. GDEF 先处理：VarStore 并集返回基址，MarkGlyphSets 并集返回索引映射；GPOS VariationIndex 依赖该基址。
5. 逐字形复制轮廓与度量：glyf 复制 glyf/hmtx/vmtx/gvar；CFF2 复制 CharStrings 与 FDSelect，FDArray 按内容去重（`FDUnion`）。
6. cmap 并集，`_harmonize_cmap()` 让每个 Unicode 子表按自身格式上限覆盖全部码位。
7. GSUB/GPOS 用 `LayoutUnion` 追加并重映射。
8. 布局在字形重排前 finalize；随后按码位重排 GID，`resort_layout()`；CFF2 再 `sync_glyph_order()` 同步 charset/FDSelect。
9. HVAR/VVAR：glyf 路径由合并后 gvar 幽灵点重建 HVAR；CFF2 与 VVAR 走 VarStore 并集与 DeltaSetIndexMap 重定位，缺失映射补 `NO_VARIATION_INDEX`。
10. 重算 head/hhea/vhea/maxp/OS/2 度量；补 nameID 16/17/25 与实例 PS 名；清 `head.flags` 的 WOFF2 残留位。
11. 可选 `verify_merge()`；`save_font()` 落盘；结果挂 `subset_merger`，`glyph_map()` 返回每个分片的源字形到合并后 GID。

CFF2 同源并集要求分片共享 VarStore 与 GlobalSubrs；FDArray 差异由 FD 级并集处理；CFF 与 CFF2 混合分片不支持。结构被重构过的输入会抛 `IncompatibleCFF2Error`，不产出坏字体。

## 9. 收尾与不变量

`_finalize_merge()` 在普通、空新增、分块与 CID 出口统一执行：

| 阶段 | 函数 | 作用 |
| --- | --- | --- |
| hinting | `apply_hinting_policy()` | 兼容全局程序时扩大 maxp 资源；旧字体完全无解释器环境时可整体采用打底程序并告警；否则剥离新字形指令 |
| 表策略 | `apply_table_policy()` | 删除失效 DSIG/hdmx/LTSH/VDMX；安全并集标准 kern；CFF 的 VORG 按字形原点并集，无法恢复原点时保留主表并告警；meta/trak/gasp 保留主策略并在打底独有时告警 |
| 元数据 | `recalc_after_merge()` | 清理非存活度量；重算 head 包围盒、maxp、hhea/vhea、OS/2 范围与平均字宽；Win 度量只扩不缩 |
| 布局排序 | `resort_layout()` | 修复 Coverage 与并行数组顺序 |
| 结构自检 | `assert_cmap_union()`、`assert_font_structure()` | Unicode/UVS 精确并集、主映射优先、字形/度量/布局/VarStore 引用完整 |

库内保存点统一走 `save_font()`：保存前设置 `flavor`，保存后校验 sfnt 魔数，避免把 WOFF2 载入的字体写成扩展名为 `.ttf` 的 `wOF2` 文件。`merge_two()` 本身不保存，调用方应使用 `save_font()` 或自行处理 `flavor`。

输入所有权汇总：

| 函数 | 是否修改输入 |
| --- | --- |
| `merge_two()` | 正常路径返回新字体；旧轴并集回退路径会修改主字体 |
| `merge_fonts()` | 先深拷贝主字体；不修改调用方传入的 TTFont |
| `merge_subsets()` | 修改 `subsets[0]` |
| `scale_font()` / `apply_scale_offset()` | 就地修改并返回同一 `TTFont`；`scale=1` 且 `baseline_offset=0` 时原样返回；参数非法或字体含 VARC 时抛 `ValueError` |
| `union_axes()` | 就地修改 main |
| `rename_glyphs()` / `apply_naming()` | 就地修改 |

## 10. 模块、依赖与扩展点

分层方向：

```text
__init__.py / FontMerging.py
        |
        v
      core/  --->  format/  --->  utils/
        |  \-->  tables/
        \---->  utils/
```

模块职责摘要：

| 层 | 主要文件 | 职责 |
| --- | --- | --- |
| 入口 | `__init__.py`、`FontMerging.py` | 导出、加载、便捷 API、交互 CLI |
| core | `merger.py`、`glyph_copy.py`、`glyph_rename.py`、`conflict.py`、`naming.py`、`subset_merge.py`、`verify.py`、`hinting_policy.py`、`table_policy.py`、`invariants.py` | 分派、合成/回退、注入、改名、命名、自检、收尾策略 |
| format | `axis_mapping.py`、`variation_compose.py`、`cff2_compose.py`、`cff2_union.py`、`vf_axes.py`、`converter.py`、`static_extract.py`、`cid_convert.py`、`cid_merge.py`、`transform.py`、`subsetter.py`、`webfont.py` | 轴数学、可变数据重参数化、轮廓与格式转换、CID、缩放、子集 |
| tables | `ot_merge.py`、`layout_union.py`、`varstore.py`、`metadata_recalc.py`、`maxp.py`、`base.py`、其余单表处理器 | 布局并集、VarStore 并集、元数据重算、表注册表 |
| utils | `detect.py`、`save.py` | 类型/同源检测、保存防护 |

已知依赖例外（现状，不作为新增依赖的理由）：

| 例外 | 代码位置 | 说明 |
| --- | --- | --- |
| `tables/` → `core/` | `tables/cmap.py` 模块级导入 `..core.glyph_copy._copy_cmap_mappings` | 旧表注册表路径的遗留反向依赖 |
| `format/` → `tables/` | `format/cff2_compose.py` 函数内导入 `..tables.varstore.VarStoreUnion` | CFF2 合成复用 ItemVariationStore 并集 |
| `format/` → `core/` | `format/cid_merge.py` 函数内导入 `..core.glyph_copy._copy_cmap_mappings` 与 `..core.conflict.resolve_conflicts` | CID 合并复用冲突判定与 cmap 同步 |
| `format/` → `tables/` | `format/cid_merge.py` 函数内导入 `..tables.layout_union.remap_glyph_names` | 改名同步布局引用 |

独立表注册表：`tables/base.py` 的 `merge_all_tables()` 与 `TABLE_MERGE_REGISTRY` 仍可作为独立 API 调用，但主流程不调用它。主流程的收尾由第 9 节的显式策略函数完成。新增 `@register` 处理器不会自动进入主流程；要接入主流程需在 `_do_merge_once()` 的出口或 `_finalize_merge()` 中显式接线，并补充回归。旧注册表若被外部调用，会对已合成的 fvar/OT 表重复处理，不应作为收尾入口。

扩展点：

- 新增单表收尾策略：在 `core/table_policy.py` 或 `tables/metadata_recalc.py` 增加显式步骤，再由 `_finalize_merge()` 调用；不要依赖未接线的注册表。
- 新增布局结构：在 `tables/layout_union.py` 的 Coverage 属性与 `_fix_subtable_order()` 中加入对应分支，并在 `_check_layout_integrity()` 增加引用检查。
- 新增轮廓技术或可变数据：参考 `format/cff2_union.py` 的结构签名与 `format/cff2_compose.py` 的重参数化；合成失败必须保持“抛异常后回退”的契约。
- 新增公共参数：同步 `FontMerger.__init__()`、`__init__.py` 导出、[合并 API](merge-api.md) 与本页参数表。

源码定位优先按函数名检索，行号可能随版本变化。完整签名见[参数索引](parameter-index.md)。
