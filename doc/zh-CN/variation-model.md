# 变化模型

[English](../en/variation-model.md) | [参数索引](parameter-index.md)

本文说明跨设计空间合成和数学 API。
同源分片并集使用另一条路径，见[分片与验证](subsets-and-verification.md)。
公式描述的是模型，不保证保存后的字体在所有位置都与源字体一致。

## 1. 三种坐标空间

| 空间 | 含义 | 单位 |
| --- | --- | --- |
| `user` | fvar 最小值、默认值和最大值所用的轴值 | 各轴自己的用户单位 |
| `pre` | 以默认值为中心的双段线性归一化坐标 | 归一化坐标，通常位于 `[-1, 1]` |
| `norm` | 经过 avar 段映射后的坐标 | 变体支撑使用的归一化坐标 |

正向过程是 `user → pre → norm`。
`AxisMapping` 通过用户坐标连接合并与源字体的 post-avar 空间。
超出源字体范围的用户坐标会钳制到端点。
单侧轴只覆盖归一化域的一半。

源码：[AxisMapping 与 PiecewiseLinear](../../format/axis_mapping.py#L66)。

## 2. 轴规划与策略

默认 `compose_range="main+extra"` 对共有轴保留主字体的范围和默认值。
它另外加入打底独有轴，并非完整的范围并集。
`"union"` 扩大共有轴的最小值、最大值，但保留主默认值。
`"main"` 只保留主字体的轴及范围。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 作用 |
| --- | --- | --- | --- | --- |
| `compose_variations` | bool | `True` | 在支持的合并路径尝试跨设计空间合成 | False 使用既有的非合成路径 |
| `compose_range` | str | `"main+extra"` | `"main+extra"`、`"union"` 或 `"main"`；范围使用用户单位 | 改变输出设计空间 |
| `compose_fit` | str | `"exact"` | 在映射折点拆分支撑，或使用仅映射端点、峰值的 `"affine"` | affine 可能遗漏中间行为并导致自检失败 |
| `avar_mode` | int | `0` | 0 使用源映射，输出优先主映射；1 忽略打底映射；2 忽略全部 avar | 模式 1 保留主映射；模式 2 删除输出 avar |
| `verify_compose` | bool | `True` | 在抽样位置检查抽样字形 | 合成自检失败会触发既有回退路径 |
| `compose_layout` | bool | `True` | 迁移支持的打底 GDEF/GPOS 变化数据 | False 时打底布局停留在合并默认点实例 |

这些是 [FontMerger 构造器](../../core/merger.py#L559)的选项。
[plan_axis_space](../../format/variation_compose.py#L41) 返回 `(merged_fvar, merged_avar, base_mappings)`，不修改输入。
这些策略与较早的轴并集辅助函数不同。

## 3. 支撑、重定基与幽灵点

支撑表示为 post-avar 归一化坐标中的 `{axis_tag: (lower, peak, upper)}`。
OpenType 会忽略峰值为零或支撑跨越零的轴。
这样的轴不能表达预期的变化 hat。
细化函数跳过被忽略的轴，并将零保留为划分节点。
生成的变化 hat 必须有非零峰值，且不能跨越零。
边界截断的 hat 可以满足 `lower == peak` 或 `peak == upper`。

源默认点与合并默认点不同时需要重定基：

`f(T(x)) = C + Σ weight × supportScalar(x, support)`

`C` 是源数据在合并默认点的贡献。
默认 master 或恒定 region 列必须承载它，且只能计入一次。
剩余各项在该默认点取零。
[refine_support_rebased](../../format/axis_mapping.py#L466) 对每轴细化，再用包含-排除关系组合。

[instance_at_merged_default](../../format/variation_compose.py#L93) 调用 fontTools 时设置 `inplace=False`、`optimize=False`。
其中包含幽灵点对度量的贡献。
[reparametrize_gvar](../../format/variation_compose.py#L121) 重写支撑，并对缩放后的增量取整。
HVAR 可以从结果 gvar 的幽灵点重建。

在支持的单调映射下，精确支撑分解是数学目标。
它不能消除整数取整和保存时的坐标量化。
合并 avar 的平台段可能把一段用户区间压成一个归一化值。
源字体若在这段区间内变化，输出的单个值就无法还原整段变化。
代码会报告 `collapsing_flats()`，不会恢复已被压缩的区分。

## 4. ItemVariationStore 引用

| 字段 | 含义 |
| --- | --- |
| `outer` | VarData 块的序号 |
| `inner` | 该块中的 Item 行号，不是 region 序号 |
| 列 | 一个 region 支撑对应的增量 |

引擎将一行的增量与各 region 标量相乘后求和。
[reparametrize_var_store](../../format/variation_compose.py#L347) 改变 region 和列，保留 VarData 顺序、ItemCount 和行序。
因此重写时不需要改变引用。
后续做 store 并集时追加 VarData 块，平移打底 outer 索引；inner 行号保持不变。

打底布局的静态值先折到合并默认点。
重写后的 store 再去掉这部分贡献，避免重复计入。
其它重写可用所有轴峰值均为零的 region 承载常数。
整数列增量需要取整，拆列后可能产生残差。
本文不声称存在通用的一个字体单位误差上限。

源码：[fold_layout_default 与 transfer_base_layout](../../format/variation_compose.py#L223)、[VarStoreUnion](../../tables/varstore.py)。

## 5. CFF2 与度量边界

CFF2 的 `blend` 将默认操作数与 region 增量组合。
末尾的计数操作数表示参与混合的值数。
当前 `vsindex` 选择 VarData 块和 region 增量数。
隐式选择来自 Private DICT，未给定时为零。

[reparametrize_cff2](../../format/cff2_compose.py#L206) 重写 blend 默认值和列，保留 VarData 序号。
它也处理子程序及支持的 Private DICT blend 值。
store 并集后，[offset_cff2_vsindex](../../format/cff2_compose.py#L388) 平移打底选择，并在必要时补上显式选择。
偏移非零时，它将 Private hint blend 折成默认值，移除 Private 的 `vsindex` 键。
这些 hint 变化不会保留。

跨设计空间 CFF2 路径在注入字形后迁移支持的 HVAR 变化字宽。
[merge_cff2_hvar](../../format/cff2_compose.py#L347) 要求结果已有 HVAR，且打底 store 存在。
它为全部字形重建 advance 映射；没有变化的项使用 `NO_VARIATION_INDEX`。
该路径没有对等的打底 VVAR 迁移。
打底纵向数据可能停留在实例化后的默认值。
同源分片并集另有 HVAR/VVAR 并集路径。

合成不是 glyf/gvar 与 CFF2 变化拓扑之间的通用转换。
失败时，[FontMerger._do_merge](../../core/merger.py#L624) 打印原因，再尝试非合成路径。
布局迁移失败则可能只保留默认实例布局，不放弃整个合并。
解释通过报告前，请先看[验证边界](subsets-and-verification.md#verification-limits)。

## 6. AxisMapping API

导入：`from FontMerger import AxisMapping`。
构造：`AxisMapping(merged_triple, merged_avar, source_triple, source_avar)`。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `merged_triple` | sequence[3] | 必填 | 合并最小值/默认值/最大值，用户单位 | 复制为 tuple |
| `merged_avar` | mapping / None | 必填 | 合并 pre→norm 段映射；假值表示恒等 | 复制为 dict |
| `source_triple` | sequence[3] | 必填 | 源最小值/默认值/最大值，用户单位 | 复制为 tuple |
| `source_avar` | mapping / None | 必填 | 源 pre→norm 段映射；假值表示恒等 | 复制为 dict |

输入应为有效单调轴映射；构造器不是字体校验器。以下方法只读，不修改字体。

| 方法 | 参数 | 类型 / 默认值 | 含义 / 返回 |
| --- | --- | --- | --- |
| `to_source(x)` | `x` | number, 必填 | 合并 norm → 源 norm；在源用户空间钳制，平台逆映射取右端点 |
| `to_merged(y)` | `y` | number, 必填 | 源 norm → 合并 norm；在合并用户空间钳制 |
| `kinks_merged()` | 无 | 无参数 | 新建排序后的合并归一化候选折点 list |
| `collapsing_flats()` | 无 | 无参数 | 新建合并平台段 `(norm, user_lo, user_hi)` list |
| `is_identity()` | 无 | 无参数 | 以三元组/字典精确相等判断的 bool，并非近似函数相等 |
| `__repr__()` | 无 | 无参数 | 显示合并与源三元组的诊断 str |

显式恒等段与缺省映射可能被 `is_identity()` 判断为不同。
源码：[AxisMapping](../../format/axis_mapping.py#L171)。

## 7. PiecewiseLinear API

导入：`from FontMerger import PiecewiseLinear`。
构造：`PiecewiseLinear(points)`。
`identity`、`fvar`、`avar` 是 classmethod，其余所列方法作用于实例。

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `points` | iterable[(number, number)] | 必填 | 单调不减映射的节点；单位取决于映射 | 排序后存入新 xs/ys list；调用方负责有效性 |

| 方法 | 参数 | 类型 / 默认值 | 含义 / 返回 |
| --- | --- | --- | --- |
| `identity()` | 无 | classmethod; 无参数 | 节点为 -1、0、1 的新恒等映射 |
| `fvar(triple)` | `triple` | sequence[3], 必填 | 新归一化→用户映射；单侧轴使用半域 |
| `avar(segments)` | `segments` | mapping / None, 必填 | 新 pre→norm 映射；假值表示恒等 |
| `map(x)` | `x` | number, 必填 | 以输入单位求值；节点域外平移外推，不钳制 |
| `inverse()` | 无 | 无参数 | 新逆映射；平台值选择右端点 |
| `compose(other)` | `other` | PiecewiseLinear, 必填 | `self(other(x))` 的新映射；输入不变 |
| `breakpoints(lo=-1.0, hi=1.0)` | `lo` | number, -1.0 | 输入下界；仅返回内部节点 |
| `breakpoints(lo=-1.0, hi=1.0)` | `hi` | number, 1.0 | 输入上界；以 EPS = `1e-9` 排除端点 |
| `is_identity()` | 无 | 无参数 | 要求恰好为标准三个 x 节点，且 y 在 EPS 内匹配的 bool |
| `__repr__()` | 无 | 无参数 | 列出节点对的诊断 str |

逆映射在平台上不是唯一数学逆。增加共线节点也可能使 `is_identity()` 返回 False。
源码：[PiecewiseLinear](../../format/axis_mapping.py#L66)。

## 8. 根导出的数学函数

以下函数均由包根导出，输入只读，返回新建结果。读取字体可能触发表的惰性加载。

### 8.1 axis_mappings

`axis_mappings(merged_axes, merged_avar, source_axes, source_avar)`

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `merged_axes` | dict | 必填 | 用户单位的 `{tag: (min, default, max)}` | 只读 |
| `merged_avar` | dict / None | 必填 | 合并 `{tag: {pre: norm}}` 段映射 | 只读；None 视为空 |
| `source_axes` | dict | 必填 | 源三元组，用户单位 | 只读 |
| `source_avar` | dict / None | 必填 | 源的分轴段映射 | 只读；None 视为空 |

只为共有轴返回新的 `{tag: AxisMapping}`，不会补入缺轴。
源码: [axis_mappings](../../format/axis_mapping.py#L266).

### 8.2 source_location

`source_location(mapping, x)`

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `mapping` | AxisMapping | 必填 | 一条合并→源轴映射 | 只读 |
| `x` | number | 必填 | 合并 post-avar 归一化坐标 | 只读 |

返回 `mapping.to_source(x)`，包含用户空间钳制。
源码: [source_location](../../format/axis_mapping.py#L284).

### 8.3 refine_support_rebased

`refine_support_rebased(support, mappings, eps=1e-9)`

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `support` | dict | 必填 | 源 post-avar `{tag: (lower, peak, upper)}` | 只读 |
| `mappings` | dict[AxisMapping] | 必填 | 每条有效支撑轴的映射 | 只读 |
| `eps` | number | `1e-9` | 省略微小标量项的无量纲阈值 | 不是字体坐标容差 |

返回 `(C, terms)`，每项为 `(support_dict, weight)`。
eps 默认值来自模块常量 `EPS`。

缺少有效轴映射时抛 `KeyError`。
支撑不可达时返回 `(0.0, [])`。
全部轴均按 OT 语义忽略时，返回 `(1.0, [])`。
源码: [refine_support_rebased](../../format/axis_mapping.py#L466).

### 8.4 evaluate_supports

`evaluate_supports(loc_norm, terms)`

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `loc_norm` | dict | 必填 | 合并 post-avar `{tag: coordinate}` | 只读 |
| `terms` | iterable | 必填 | `(support_dict, weight)` 项 | 遍历并求和 |

返回无量纲加权支撑和，不加入重定基常数；需另行加上 `C`。
源码: [evaluate_supports](../../format/axis_mapping.py#L536).

### 8.5 fvar_triples

`fvar_triples(font)`

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `font` | TTFont | 必填 | 含 fvar 的字体，轴值使用用户单位 | 读取表，返回新字典 |

返回 `{tag: (min, default, max)}`。没有 fvar 时可能抛 `KeyError`。
源码: [fvar_triples](../../format/axis_mapping.py#L544).

### 8.6 avar_segments

`avar_segments(font)`

| 参数 | 类型 | 默认值 | 含义 / 单位 | 所有权 / 副作用 |
| --- | --- | --- | --- | --- |
| `font` | TTFont | 必填 | 需要读取 pre→norm 映射的字体 | 读取表，复制嵌套字典 |

返回 `{tag: {pre: norm}}`，没有 avar 时返回 `{}`。
源码: [avar_segments](../../format/axis_mapping.py#L549).

## 9. 模块高级函数

这些是模块级辅助函数，并非全部由包根导出。完整参数见[参数索引](parameter-index.md)。
会修改字体的函数需要协调 fvar/avar、轮廓、度量和 store；单个函数返回不代表完成合并。

| 模块 | 签名 | 作用 |
| --- | --- | --- |
| [axis_mapping](../../format/axis_mapping.py) | `invert_piecewise(pl, y, flat="left")` | 逐段反解，明确平台端点选择 |
| [axis_mapping](../../format/axis_mapping.py) | `reachable_range(mapping)` | 源归一化空间的可达区间 |
| [axis_mapping](../../format/axis_mapping.py) | `hat_value(x, lower, peak, upper)` | 单轴标量辅助函数 |
| [axis_mapping](../../format/axis_mapping.py) | `support_value(loc_norm, support)` | OT 支撑标量 |
| [axis_mapping](../../format/axis_mapping.py) | `refine_1d(lower, peak, upper, mapping, eps=EPS, shift=0.0)` | 单轴细化 |
| [axis_mapping](../../format/axis_mapping.py) | `refine_support(support, mappings, eps=EPS)` | 不重定基的细化 |
| [axis_mapping](../../format/axis_mapping.py) | `axis_support_at_default(tag, support, mapping)` | 合并默认点的贡献 |
| [variation_compose](../../format/variation_compose.py) | `plan_axis_space(main_font, base_font, range_policy="main+extra", avar_mode=0)` | 读取输入并规划输出轴 |
| [variation_compose](../../format/variation_compose.py) | `merged_default_location(merged_fvar, font=None)` | 默认用户坐标，可投影到指定字体 |
| [variation_compose](../../format/variation_compose.py) | `instance_at_merged_default(font, merged_fvar)` | 返回实例，不就地修改源 |
| [variation_compose](../../format/variation_compose.py) | `reparametrize_gvar(merged_font, source_font, mappings, glyph_names=None, fit="exact")` | 修改目标 gvar |
| [variation_compose](../../format/variation_compose.py) | `fold_layout_default(base_font, mappings)` | 返回已折入默认值的布局副本 |
| [variation_compose](../../format/variation_compose.py) | `transfer_base_layout(b_inst, base_font, mappings, merged_fvar)` | 修改实例化打底的布局 |
| [variation_compose](../../format/variation_compose.py) | `region_split_plans(src_regions, mappings, dst_tags, folded_default=False, eps=1e-4, constant_column=True)` | 构造 region 列计划 |
| [variation_compose](../../format/variation_compose.py) | `reparametrize_var_store(var_store, mappings, src_tags, dst_tags=None, folded_default=False, eps=1e-4)` | 返回重写 store 和报告 |
| [cff2_compose](../../format/cff2_compose.py) | `cff2_var_store(font)` | 读取 CFF2 store，无则 None |
| [cff2_compose](../../format/cff2_compose.py) | `set_cff2_var_store(font, ot_var_store)` | 修改 CFF2 引用，使其共享一个 store |
| [cff2_compose](../../format/cff2_compose.py) | `reparametrize_cff2(font, mappings, src_tags, dst_tags=None, eps=1e-4)` | 修改 CFF2 blend 和 store |
| [cff2_compose](../../format/cff2_compose.py) | `is_cff2_variable(font)` | 检查 CFF2、fvar 与 store 存在性 |
| [cff2_compose](../../format/cff2_compose.py) | `merge_cff2_var_stores(main_font, base_font, main_mappings, main_tags, dst_tags)` | 修改两字体的 CFF2 store 引用 |
| [cff2_compose](../../format/cff2_compose.py) | `reparametrize_hvar(font, mappings, src_tags, dst_tags, folded_default)` | 修改 HVAR region |
| [cff2_compose](../../format/cff2_compose.py) | `merge_cff2_hvar(result, base_store, base_map, added_names)` | 修改结果 HVAR 和 advance 映射 |
| [cff2_compose](../../format/cff2_compose.py) | `offset_cff2_vsindex(font, delta)` | 修改 vsindex，将支持的 Private hint 变化折为默认值 |

## 10. 示例

下例不使用字体文件，只检查数学映射的选定点，不验证保存后的字体。

~~~python
from fontTools.varLib.models import supportScalar
from FontMerger import (
    AxisMapping, PiecewiseLinear, evaluate_supports,
    refine_support_rebased, source_location,
)

mapping = AxisMapping((100, 400, 900), None, (200, 400, 800), None)
support = {"wght": (0.0, 0.5, 1.0)}
constant, terms = refine_support_rebased(support, {"wght": mapping})
for x in (-1.0, -0.5, 0.0, 0.25, 0.5, 0.75, 1.0):
    expected = supportScalar(
        {"wght": source_location(mapping, x)}, support, ot=True
    )
    actual = constant + evaluate_supports({"wght": x}, terms)
    assert abs(actual - expected) < 1e-7

identity = PiecewiseLinear.identity()
assert identity.map(0.0) == 0.0
~~~

从调用方提供的字体读取映射：

~~~python
from FontMerger import load_font, fvar_triples, avar_segments, axis_mappings

main_font = load_font("Main.ttf")
base_font = load_font("Base.ttf")
mappings = axis_mappings(
    fvar_triples(main_font), avar_segments(main_font),
    fvar_triples(base_font), avar_segments(base_font),
)
~~~

第二例的两份输入必须有 fvar。结果只含共有轴，不规划新轴，也不修改字体。
