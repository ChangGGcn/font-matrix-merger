# 分片与验证

[English](../en/subsets-and-verification.md) | [变化模型](variation-model.md) | [参数索引](parameter-index.md)

## 1. 使用范围

同源并集用于同一可变字体的 unicode-range 分片，不做跨设计空间轴规划。
多片输入的 [is_same_source](../../utils/detect.py#L122) 检查 fvar 轴空间与轮廓类型。
这不是来源鉴定，也不证明 avar、hinting 或其它表内容一致。
输入顺序决定基底及冲突时保留的先到记录。

支持 glyf/gvar 与满足结构条件的 CFF2 分片。
CFF2 要求兼容的 VarStore / GlobalSubrs；FDArray 按内容并集。
不兼容结构会明确拒绝，不声称任意 CFF2 分片都能保留全部特性。
多个分片都提供 FeatureVariations 时，其条件序列内容与顺序必须一致。
[LayoutUnion.add_from](../../tables/layout_union.py#L621) 对不一致序列抛 ValueError，不做有损条件拼接。

源码：[SameSourceSubsetMerger](../../core/subset_merge.py#L91)、[CFF2 兼容检查](../../format/cff2_union.py)。

## 2. load_subsets

`load_subsets(subsets)`，从包根导入。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `subsets` | iterable[path / TTFont] | 必填 | 按合并顺序排列的混合输入序列 | 路径会打开；对象原样复用 |

返回 `(fonts, labels)` 两个 list。
路径由根 `load_font` 读取；WOFF/WOFF2 会解包并清 flavor。
路径标签是 basename；对象标签为 `subset000`、`subset001` 等。
同 basename 的路径会产生重复标签，后续 glyph_map 的后项会覆盖前项。
请使用唯一文件名，或在底层 merge 中传入唯一自定义标签。
加载错误直接向上传播。
源码：[load_subsets](../../core/subset_merge.py#L708)。

## 3. SameSourceSubsetMerger

### 3.1 构造与状态

`SameSourceSubsetMerger(tag="s", verbose=True)`。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `tag` | str | `"s"` | 别名前缀；假值改为 "s" | 保存在合并器 |
| `verbose` | bool | `True` | 打印此合并器进度 | 不控制全部下层输出 |

返回保存并集状态的合并器，不打开字体文件。
每次独立合并应使用新实例；merge 不重置累积状态。
构造器本身不执行验证或保存。

### 3.2 rename_map

静态方法：`rename_map(base, main_names, tag, index, layout_names=frozenset())`。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `base` | TTFont | 必填 | 一个源分片 | 只读字形序 |
| `main_names` | set[str] | 必填 | 结果已占用的字形名 | 复制为工作 set |
| `tag` | str | 必填 | 别名前缀 | 只读 |
| `index` | int | 必填 | 别名中的分片编号 | 只读 |
| `layout_names` | set-like[str] | `frozenset()` | 本分片布局引用的字形名 | 只读；默认空 |

返回仅包含需要别名项的 `{old_name: new_name}`，不修改字体。
.notdef 不改名。自动序号名始终分配别名。
普通重名只有被该分片布局引用时才保留为别名，其余回落到已有同源字形。
源码：[rename_map](../../core/subset_merge.py#L151)。

### 3.3 merge

`merge(subsets, labels=None)`。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `subsets` | iterable[TTFont] | 必填 | 非空有序分片序列；多片时须通过同源检查 | 首字体就地修改；其它字体可能惰性加载或解码 |
| `labels` | sequence[str] / None | `None` | 每片一个唯一标签；None/假值生成 "0"、"1" 等 | 复制为 list；调用方负责长度与输入一致 |

返回已就地修改的首个 TTFont。
它合并轮廓、度量、支持的变化数据与布局，重排 GID，再同步相关表。
底层方法不补完整名称、不清保存标志、不附加 subset_merger 属性、不调用 verify_merge，也不保存文件。
空输入抛 ValueError；非同源多片输入抛 ValueError；不支持的 CFF/CFF2 结构可抛 NotImplementedError。
FV 条件不兼容可抛 ValueError。异常前可能已修改首字体，不承诺事务回滚。
源码：[merge](../../core/subset_merge.py#L181)。

### 3.4 glyph_map

`glyph_map()` 无参数，返回 `{label: {source_name: result_GID}}`。
GID 是根据 merge 记录的 final_order 生成的整数，不是字形名。
返回值包含 .notdef；验证器会跳过该字形。
外部再次重排结果后，不得继续使用这些旧 GID。
源码：[glyph_map](../../core/subset_merge.py#L606)。

### 3.5 log

`log(*args)` 接受任意位置参数，无额外默认值。
verbose 为真时调用 `print(*args, flush=True)`，否则不输出；返回 None。
它控制本合并器的消息，不控制下层所有打印。
源码：[log](../../core/subset_merge.py#L117)。

## 4. merge_subsets

`merge_subsets(subsets, out_path=None, tag="s", output_flavor=None, complete_name_table=True, fix_head_flags=True, verify=False, verbose=True, **verify_kwargs)`。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `subsets` | iterable[path / TTFont] | 必填 | 有序同源分片，不是不同字族 | 复用对象；subsets[0] 就地修改 |
| `out_path` | path / None | `None` | 输出路径；None 不落盘 | 通过 save_font 写文件 |
| `tag` | str | `"s"` | 别名前缀 | 传给新合并器 |
| `output_flavor` | str / None | `None` | 有 out_path 时 None 按扩展名推断；显式 "woff"/"woff2" 覆盖推断 | out_path 为 None 时不会赋给返回字体 |
| `complete_name_table` | bool | `True` | 补 nameID 16/17/25 与命名实例 PS 名 | 修改结果名称及实例数据 |
| `fix_head_flags` | bool | `True` | 清理 head.flags 的 WOFF2 残留 bit 11 | 修改结果 head |
| `verify` | bool | `False` | 保存前运行 verify_merge；失败抛 AssertionError | 存在下述源对象及标签边界 |
| `verbose` | bool | `True` | 控制合并器进度消息 | 不转发为 verify_merge.verbose |
| `**verify_kwargs` | keyword arguments | `{}` | verify=True 时转发附加验证选项 | 可直接使用 axis_positions、tolerance、sample |

返回合并后的 TTFont，并附上 `result.subset_merger`。
有 out_path 时，None 根据后缀推断 flavor：.woff→woff、.woff2→woff2，其它→桌面 sfnt。
显式 flavor 覆盖后缀推断；无 out_path 时，本函数不应用 output_flavor。
保存、压缩或校验错误会传播。空输入在包装器进度参数求值时可能先抛 IndexError。

verify_kwargs 只在 verify=True 时使用。未知关键字会由 verify_merge 拒绝。
不要传 sources、merged 或 glyph_map，它们已由包装器提供。
verbose 是包装器自身参数，不会作为验证选项转发；内置验证仍按自己的 verbose=True 打印。
需要安静验证或自定义映射时，独立调用 verify_merge。

**内置验证的当前边界：** 首字体在验证前已经修改，不能作为未修改的主参考。
路径在包装器中先转成对象，内置 verify_merge 再次加载这些对象时生成 subset000 等标签。
而 merger 的 glyph_map 保留原路径 basename；两者可能不匹配。
因此 verify=True 不是独立的完整源对照。下文示例保留原路径或原始副本再校验。
源码：[merge_subsets](../../core/subset_merge.py#L723)。

## 5. verify_merge

`verify_merge(sources, merged, glyph_map=None, axis_positions="auto", tolerance=0.0, sample=None, verbose=True)`，从包根导入。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `sources` | iterable[path / TTFont] | 必填 | 原始分片，宜使用未修改副本或原路径 | 通过 load_subsets 加载；该处不深拷贝对象 |
| `merged` | TTFont | 必填 | 待检查结果；此处不接受路径 | 除表加载外只读 |
| `glyph_map` | dict / None | `None` | `{label: {source_name: result_name_or_GID}}` | 标签须与本次 load_subsets 一致 |
| `axis_positions` | str / iterable | `"auto"` | "auto"、"grid" 或 None/用户坐标 dict 的列表 | 不实例化用 [None]；裸 None 会抛 TypeError |
| `tolerance` | number | `0.0` | 轮廓数值坐标的绝对容差，字体单位 | hmtx/vmtx 仍严格比较 tuple |
| `sample` | int / None | `None` | 每片最多抽取这些源名，之后跳过 .notdef | 确定性步长；None/0 不限数量 |
| `verbose` | bool | `True` | 打印验证进度及失败信息 | 独立于 merge_subsets.verbose |

"auto" 使用默认位置及第一条轴的非默认最小/最大位置，不逐轴检查所有端点。
"grid" 使用各轴 min/default/max 网格，默认最多 64 个位置。
自定义 dict 使用用户坐标；缺省轴留在默认值，不属于源字体的轴由实例化辅助函数投影掉。

返回 `{"ok": bool, "failures": list[str], "checks": dict}`；当前没有顶层 stats。
checks 包含码位、轴、位置、抽样轮廓/度量、特性、布局引用、GDEF、variation maps、容器和竖排引用计数。
轮廓不匹配会跳过该字形后续度量比较。
普通检查失败写入 failures，不自动抛 AssertionError；加载或实例化等操作错误仍可抛出。
源码：[verify_merge](../../core/verify.py#L112)。

## 6. verify_composition

此函数不由包根导出：`from FontMerger.core.verify import verify_composition`。
`verify_composition(merged, main_font, base_font, added_glyphs, sample=30, tolerance=1.0, max_positions=6, verbose=False, adv_tolerance=None)`。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `merged` | TTFont | 必填 | 目标设计空间中的合成结果 | 读取 glyphSet |
| `main_font` | TTFont | 必填 | 字形名、单位对应的主参考字体 | 不就地修改 |
| `base_font` | TTFont | 必填 | 字形名、单位对应的打底参考字体 | 不就地修改 |
| `added_glyphs` | sequence[str] | 必填 | 从打底新增的字形名；须支持 len 和切片 | 局部抽样；源中缺名则跳过 |
| `sample` | int / None | `30` | 新增名、主字形名分别抽样的上限 | 确定性步长；None/0 取消上限 |
| `tolerance` | number | `1.0` | 轮廓数值坐标的绝对容差，字体单位 | 单独覆盖字宽容差后不再控制字宽 |
| `max_positions` | int | `6` | min/default/max 笛卡尔网格位置上限 | 截断枚举，不保证覆盖所有位置 |
| `verbose` | bool | `False` | 打印成功摘要 | False 时断言仍抛错 |
| `adv_tolerance` | number / None | `None` | 打底新增字形的 advance 字宽容差，字体单位 | None 使用 tolerance；此处不单独检查主字形宽度 |

使用 `getGlyphSet(location=...)` 读取渲染语义下的轮廓及字宽。
新增字形的轮廓、advance 字宽与打底比较；主字形只比较轮廓。
失败抛 AssertionError；成功返回 `{"positions": n, "checked": n, "worst": value}`。
checked 是跨位置的实际比较次数，worst 只记录最大轮廓数值偏差，不包含字宽误差。
它不替代布局完整性、特性行为、垂直度量或光栅器检查。

主流程 verify_compose 默认 True，与 merge_subsets 的 verify=False 不同。
[FontMerger 的调用处](../../core/merger.py#L426) 使用 max_positions=4、adv_tolerance=3.0，其余保持本函数默认值。
合成自检失败向上传播后触发非合成回退，并非返回“已验证的合成结果”。
源码：[verify_composition](../../core/verify.py#L408)。

## 7. grid_positions

模块导入：`from FontMerger.core.verify import grid_positions`。
`grid_positions(font, per_axis=3, max_positions=64)`。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `font` | TTFont | 必填 | 以其 fvar 轴序定义网格的字体 | 只读；静态输入返回 [None] |
| `per_axis` | int | `3` | 保留参数；当前实现未读取 | 改变它不改变采样密度 |
| `max_positions` | int | `64` | 笛卡尔枚举的位置上限，应使用正值 | 追加位置后才判断截断，不是校验参数 |

返回位置 list。可变输入使用 fvar 轴序及每轴去重排序后的 min/default/max 值做笛卡尔积。
达到上限就截断，截断网格不保证包含默认点或每条轴的两端。
当前 per_axis 不生效，不能通过它增加中间采样点；需要中间点时给 verify_merge 传自定义位置。
源码：[grid_positions](../../core/verify.py#L78)。

<a id="verification-limits"></a>
## 8. 验证边界

- **标签与 GID：** verify_merge 用 load_subsets 重新生成标签后查 glyph_map。路径与对象标签不同；自定义标签需重新对齐。没有映射时按同名字形比较，不会按分片序号自动匹配。
- **跳过目标：** 缺失名称或超出范围的 GID 可被跳过，不一定形成失败；结合 checks["glyphs"]["compared"] 判断实际覆盖。必须使用有效非负 GID。
- **未修改源：** 首分片就地修改会弱化对照。需要独立证据时保留路径或合并前深拷贝。
- **原始绘图记录：** 当前使用 raw RecordingPen，不保证递归分解组件。比较器检查操作、数值和参数形状，但不比较非数值组件名称。不能据此保证任意复合字形几何一致。
- **布局：** 特性 tag、引用和排序检查不是 shaping 对照。GDEF 部分字段只是汇总，不证明每个源记录逐项保留。
- **取样：** 网格会截断，glyph sample 会抽样，均不覆盖连续设计空间。浮点求值、整数度量和保存量化的语义也不同。
- **文件：** verify_merge 接受内存字体，不读取输出文件魔数；保存后的容器检查由 save_font 负责。name17 等记录可出现在报告中，但并非全部成为失败判据。

这些限制来自 [RecordingPen 比较器](../../core/verify.py#L26)和 [verify_merge 目标选择](../../core/verify.py#L179)。
源码仓库中的 tests/ 与 build/ 不包含在公开 ZIP 中；本文不依赖这些目录才能运行库 API。

## 9. 示例

两个文件名代表同一可变字体的分片，不是任意两款字体。
下例重新打开原路径，使验证标签与合并映射一致，也避免首分片已修改的问题。
这些是调用示例，本次文档审核不运行真实字体。

~~~python
from FontMerger import merge_subsets, verify_merge, save_font

paths = ["Main.ttf", "Base.ttf"]
merged = merge_subsets(paths, tag="part", verify=False, verbose=False)
report = verify_merge(
    paths, merged,
    glyph_map=merged.subset_merger.glyph_map(),
    axis_positions="grid", tolerance=0.0, sample=None, verbose=False,
)
if not report["ok"]:
    raise AssertionError(report["failures"])
save_font(merged, "Merged.ttf")
~~~

底层对象用法需要自行补元数据，并将自定义标签对齐到验证器的对象标签：

~~~python
import copy
from FontMerger import (
    SameSourceSubsetMerger, load_subsets, verify_merge,
    complete_vf_name_table, fix_head_flags,
)

fonts, labels = load_subsets(["Main.ttf", "Base.ttf"])
originals = copy.deepcopy(fonts)
state = SameSourceSubsetMerger(tag="part", verbose=False)
merged = state.merge(fonts, labels=labels)
complete_vf_name_table(merged)
fix_head_flags(merged)

_, verification_labels = load_subsets(originals)
by_source_label = state.glyph_map()
aligned_map = {
    verify_label: by_source_label[source_label]
    for source_label, verify_label in zip(labels, verification_labels)
}
report = verify_merge(
    originals, merged, glyph_map=aligned_map, verbose=False,
)
if not report["ok"]:
    raise AssertionError(report["failures"])
~~~
