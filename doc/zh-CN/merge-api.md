# 合并 API 与策略参数

[English](../en/merge-api.md) | **简体中文**

本页说明加载字体、合并一个或多个打底字体、控制可变字体合成策略的入口：`load_font`、`merge_fonts`、`FontMerger` 和 `DEFAULT_ANSWERS`。内容对应 v0.2.1；行为以 [__init__.py](../../__init__.py) 与 [core/merger.py](../../core/merger.py) 的代码为准。本文只描述实现实际检查过的结果，不承诺更多。

相关页面：[使用指南](usage.md) 介绍安装、CLI 与完整示例；[辅助 API](helper-api.md) 介绍改名、命名、格式、布局与保存函数；[同源分片与验证](subsets-and-verification.md) 介绍 `merge_subsets` 与 `verify_merge`；[轴映射与可变数据合成](variation-model.md) 介绍合成数学；[支持边界](limitations.md) 说明适用范围。

运行库源码使用相对链接，例如 [core/merger.py](../../core/merger.py)；这些链接在仓库与运行 ZIP 内都能解析。运行 ZIP 包含根模块、core/、format/、tables/、utils/、两版 README、CHANGELOG.md、LICENSE 与 doc/*.md；不包含 tests/ 与 build/。这两棵树仅存在于仓库，因此本文只以代码路径形式提及，不做相对链接。

## 1. 字体输入与所有权

| 入口 | 接受 | 返回 |
| --- | --- | --- |
| `load_font(source)` | 路径（`str` 或 `pathlib.Path`）或已有 `TTFont` | `TTFont`；传入 `TTFont` 时返回同一对象 |
| `FontMerger.merge_two(m, b)` | 两个 `TTFont`；不解析路径 | 合并后的 `TTFont`（新对象） |
| `merge_fonts(main_font, base_fonts, ...)` | 主字体与每个打底字体的路径或 `TTFont` | 合并后的 `TTFont`，`flavor` 已清空 |

TTC/OTC 字体集不在支持范围内：CLI 拒绝 `.ttc` 与 `.otc`；`load_font` 对其他路径直接交给 fontTools，不做字体集索引处理。WOFF/WOFF2 由 `load_font`（以及 CLI）接受，解包后清空 `flavor`。

### 1.1 `load_font(source)`

签名：`load_font(source)`（[__init__.py](../../__init__.py)）。

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `source` | `str`、`pathlib.Path` 或 `TTFont` | 必填 | 要加载的路径，或已加载的字体对象。 |

返回值

- `.woff` 或 `.woff2` 路径：经 `FontMerger.format.webfont.unwrap_webfont` 加载的新 `TTFont`，且 `font.flavor = None`。
- 其他路径：由 `fontTools.ttLib.TTFont(path)` 构建的新 `TTFont`。此处不校验扩展名，扩展名校验与拒绝发生在 CLI。
- 其他对象：原样返回，不复制。

异常：`TTFont` 抛出的错误（文件缺失、无法读取或字体损坏）。函数不保存、不修改字体，也不解析字体集索引。

示例：

```python
from FontMerger import load_font

main = load_font("Main.ttf")
base = load_font("Base.woff2")  # 加载后 flavor 已清空
```

### 1.2 所有权规则

| 函数 | 是否可能修改传入的主字体 | 是否可能修改传入的打底字体 |
| --- | --- | --- |
| `load_font` | 否 | 否 |
| `merge_fonts` | 否；合并前深拷贝 `main_font` | 不打算修改内容；内部分支使用副本 |
| `FontMerger.merge_two` | 可能，见 3.3 节的可变×可变回退路径 | 不打算修改内容；fontTools 可能惰性解压表 |

`merge_two` 在转换、实例化与 CID 归一分支中复制或替换工作用的打底字体。原始打底对象只用于只读规划，fontTools 可能对其惰性解压。两个输入都按借用处理；同一对象还要复用时请传副本。

## 2. `merge_fonts(main_font, base_fonts, interactive=False, answers=None)`

签名：`merge_fonts(main_font, base_fonts, interactive=False, answers=None)`（[__init__.py](../../__init__.py)）。

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `main_font` | 路径（`str`/`Path`）或 `TTFont` | 必填 | 主字体，经 `load_font` 加载。 |
| `base_fonts` | 路径或 `TTFont` 的可迭代对象 | 必填 | 按合并顺序排列的打底字体，每个经 `load_font` 加载。 |
| `interactive` | `bool` | `False` | 为 `False` 时用 `DEFAULT_ANSWERS` 预填 `FontMerger.mem`，不会阻塞提问；为 `True` 时缺失答案从 stdin 询问。 |
| `answers` | `dict[str, str]` 或 `None` | `None` | 与 `DEFAULT_ANSWERS` 同键的答案覆盖。非交互模式在默认值之后覆盖；交互模式只并入空记忆。 |

返回：合并后的 `TTFont`。函数深拷贝加载后的主字体，逐级调用 `merge_two` 合并每个打底，再用 `get_family(main_font)` 与 `get_copyrights(main_font, *base_fonts)` 的结果调用 `apply_naming`，清空 `flavor` 后返回。函数不保存文件。

异常：`load_font`、`merge_two`、`apply_naming` 能抛出的错误都会向外传播，包括无效输入 UVS 的 `ValueError`、字形注入失败的 `RuntimeError`、最终不变量失败的 `AssertionError` 与 fontTools 错误。`merge_two` 内部的合成失败会记录日志并走回退；只有回退也失败才会抛出。

示例：

```python
from FontMerger import merge_fonts, save_font

merged = merge_fonts("Main.ttf", ["Base.ttf"], answers={"vOTF_sOTF": "可变"})
save_font(merged, "Merged.ttf")  # merge_fonts 不落盘
```

第二个打底作为再下一级合并：

```python
from FontMerger import merge_fonts

merged = merge_fonts("Main.ttf", ["Base.ttf", "Base2.ttf"])
```

`answers` 的值必须是该键交互选项中的字符串。可变/静态四个键按 `"静态"` 比较；其他任何字符串都会保持可变路径，因此请准确使用 `"可变"` 或 `"静态"`。

## 3. `FontMerger` 对象

### 3.1 `FontMerger(compose_variations=True, compose_range="main+extra", compose_fit="exact", avar_mode=0, verify_compose=True, compose_layout=True)`

仓库源码：[core/merger.py](../../core/merger.py)。返回合并器对象。构造过程不读写字体文件。对象持有公开字典 `mem`，初始为空，用于保存交互答案。

| 参数 | 类型 | 默认值 | 允许值 | 含义 |
| --- | --- | --- | --- | --- |
| `compose_variations` | `bool` | `True` | `True`/`False` | 是否把可变打底合成进合并轴空间的总开关。`False` 走传统路径。 |
| `compose_range` | `str` | `"main+extra"` | `"main+extra"`、`"union"`、`"main"` | 共有轴的范围策略。`"main+extra"` 保留主范围并新增打底独有轴；`"union"` 取两者最宽范围；`"main"` 只保留主轴。 |
| `compose_fit` | `str` | `"exact"` | `"exact"`、`"affine"` | `"exact"` 精确重定基元组；`"affine"` 为每个元组拟合一个 hat，存在已知偏差，真实字体上通常被自检拒绝。 |
| `avar_mode` | `int` | `0` | `0`、`1`、`2` | `0` 尊重主 `avar`；`1` 忽略打底 `avar`、共用主 `avar`；`2` 输出不带 `avar`。 |
| `verify_compose` | `bool` | `True` | `True`/`False` | 接受合成轮廓与字宽数据前，做抽样网格比对；不通过时执行文档中的回退。 |
| `compose_layout` | `bool` | `True` | `True`/`False` | 同时重参数化打底的 GDEF ItemVariationStore 与 GPOS VariationIndex 设备。`False` 时打底布局变化冻结在合并默认点。 |

这六个参数仅当主字体与打底字体都为可变时使用，不改变静态合并、命名或保存。定点取整影响见第 6 节。

### 3.2 `ask(self, key, q, opts=None)`

签名：`ask(key, q, opts=None)`。

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `key` | `str` | 必填 | 记忆键；调用方同时用它作为 `DEFAULT_ANSWERS` 的键。 |
| `q` | `str` | 必填 | 打印到 stdout 的问题。 |
| `opts` | `list[str]` 或 `None` | `None` | 给出时调用方打印选项，答案必须是其中一个，按从 1 开始的序号选择；为 `None` 时返回自由文本。 |

返回：保存的答案字符串。若 `self.mem` 已含 `key`，直接返回存储值且不提问；否则阻塞在 `input()`，把答案写入 `self.mem` 后返回。函数会打印 `[询问]` 或 `[记忆]` 行。

异常：不捕获 `input()` 的 `EOFError` 或 `KeyboardInterrupt`。显示问题时没有默认值。

### 3.3 `merge_two(m, b)`

签名：`merge_two(m, b)`。两个参数都是 `TTFont`，不接受路径。

| 参数 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `m` | `TTFont` | 必填 | 主字体，其字形与 Unicode 映射优先。 |
| `b` | `TTFont` | 必填 | 打底字体，只复制通过冲突规划的字形与映射。 |

返回：单级合并后的 `TTFont`。函数不做命名、不保存、也不清空 `flavor`。

行为：

1. 校验两个输入的默认 UVS 与显式 UVS 字形引用。默认 UVS 项的基础码位若没有普通 Unicode 映射，会在任何合并工作前抛出 `ValueError`。
2. 按四项属性分派：主字体静态/可变、主字体 CFF/glyf、打底字体静态/可变、打底字体 CFF/glyf。
3. 打底为可变时，先按六个策略参数尝试合成路径；该路径抛错或抽样自检不通过时，回退到按默认轴值实例化打底。
4. 归一 UPM、CID 格式、轮廓格式与字形重名，注入字形，合并修剪后的打底布局特性，然后运行收尾。收尾协调 hinting、小表策略、官方元数据重算、布局排序，以及 Unicode/UVS 与结构不变量。

输入副作用：

- 可变×可变路径中，当合成被关闭或抛错并走回退时，`m` 可能被就地扩展（fvar/avar/varStore 更新）。需要保留原对象时传副本。合成路径开头会深拷贝 `m`。
- 打底按只读处理。转换、实例化与 CID 归一分支都在副本上工作；fontTools 可能对任一输入惰性解压表。
- 提问时 `self.mem` 可能增加答案。

异常：

| 异常 | 触发情况 |
| --- | --- |
| `ValueError` | 输入含非法默认 UVS 或悬空 UVS 字形；可变字体跨轮廓技术转换不受支持；其他显式校验失败。 |
| `RuntimeError` | 字形注入失败；合并器拒绝返回不完整字体。 |
| `AssertionError` | 最终码位、UVS 或结构不变量失败。 |
| fontTools 错误 | 合并器未转换的坏表或编译/保存错误。 |

合成失败会以 `[合成] 回退到默认实例合并: ...` 记录并由回退处理；只有回退路径也失败才会抛出。

## 4. 分派与问答实际效果

| 主字体类型 | 打底类型 | 路径 | 询问 | 答案的实际效果 |
| --- | --- | --- | --- | --- |
| 静态 | 静态 | 需要时把打底转换为主字体轮廓格式，再合并 | 两者轮廓格式不同时询问 `sOTF_sTTF` 或 `sTTF_sOTF` | 仅写入 `mem`；当前代码不据此分支，输出轮廓跟随主字体。 |
| 静态 | 可变 | 按默认轴值实例化打底，再合并 | 无 | 不适用 |
| 可变 | 静态 | 保留或实例化主可变字体，再合并 | `vOTF_sOTF` / `vOTF_sTTF` / `vTTF_sOTF` / `vTTF_sTTF`；选择 `"静态"` 后还会问 `vOTF_sTTF2` 或 `vTTF_sOTF2` | `"静态"` 实例化主字体；其他值保持可变。第二个问题仅记录，当前代码不据此分支。 |
| 可变 | 可变 | 先尝试合成，再走传统回退 | `vOTF_vTTF` 或 `vTTF_vOTF`；`vOTF_vOTF` 与 `vTTF_vTTF` 不问 | 仅写入 `mem`；当前代码不据此分支。合并输出轮廓跟随主字体。 |

所有分支共用冲突规划：主字体保留字形与 Unicode 映射；打底字形只有码位或闭包需求通过时才复制；与主字体同名的打底字形加别名；打底布局特性修剪到存活字形后按主优先合并。

## 5. `DEFAULT_ANSWERS`

`DEFAULT_ANSWERS` 位于 [__init__.py](../../__init__.py)，是模块级字典，键为问题键，值为默认答案。完整内容：

```python
DEFAULT_ANSWERS = {
    "sOTF_sTTF": "OTF", "sTTF_sOTF": "TTF",
    "vOTF_sTTF2": "TTF", "vTTF_sOTF2": "TTF",
    "vOTF_sOTF": "可变", "vOTF_sTTF": "可变",
    "vTTF_sOTF": "可变", "vTTF_sTTF": "可变",
    "vOTF_vTTF": "OTF", "vTTF_vOTF": "TTF",
}
```

| 键 | 默认值 | 问题文本 | 选项 | 当前效果 |
| --- | --- | --- | --- | --- |
| `sOTF_sTTF` | `"OTF"` | 导出为 TTF 还是 OTF？ | `"OTF"`、`"TTF"` | 仅记录；输出跟随主字体。 |
| `sTTF_sOTF` | `"TTF"` | 导出为 TTF 还是 OTF？ | `"TTF"`、`"OTF"` | 仅记录；输出跟随主字体。 |
| `vOTF_sOTF` | `"可变"` | 导出为可变/静态？ | `"可变"`、`"静态"` | 生效。`"静态"` 在合并前实例化主字体。 |
| `vOTF_sTTF` | `"可变"` | 导出为可变/静态？ | `"可变"`、`"静态"` | 生效。`"静态"` 实例化主字体。 |
| `vOTF_sTTF2` | `"TTF"` | TTF/OTF？ | `"TTF"`、`"OTF"` | 仅记录；静态路径返回基于 CFF 的实例。 |
| `vTTF_sOTF` | `"可变"` | 导出为可变/静态？ | `"可变"`、`"静态"` | 生效。`"静态"` 实例化主字体。 |
| `vTTF_sOTF2` | `"TTF"` | TTF/OTF？ | `"TTF"`、`"OTF"` | 仅记录；静态路径返回基于 glyf 的实例。 |
| `vTTF_sTTF` | `"可变"` | 导出为可变/静态？ | `"可变"`、`"静态"` | 生效。`"静态"` 实例化主字体。 |
| `vOTF_vTTF` | `"OTF"` | OTF/TTF？ | `"OTF"`、`"TTF"` | 仅记录；输出跟随主字体（CFF）。 |
| `vTTF_vOTF` | `"TTF"` | TTF/OTF？ | `"TTF"`、`"OTF"` | 仅记录；输出跟随主字体（glyf）。 |

其中六个键仍会提问并保存，以兼容 CLI，但当前分派代码不读取它们。只有四个可变/静态键影响控制流。预填答案时请使用上表的精确选项字符串；四个控制键的判断是 `answer == "静态"`。

非交互预填：

```python
from FontMerger import DEFAULT_ANSWERS, FontMerger

merger = FontMerger()
merger.mem = dict(DEFAULT_ANSWERS)
merger.mem["vOTF_sOTF"] = "静态"
```

`merge_fonts(..., interactive=False, answers={...})` 先复制 `DEFAULT_ANSWERS`，再应用 `answers`。`interactive=True` 只保留显式给出的答案，其余必需键都会阻塞在 stdin。

## 6. 合并保证与不保证的内容

出口处检查并保证：

- 主字体与打底字体的 Unicode 码位构成受检查的并集；共享码位保留主映射。
- UVS 序列构成受检查的并集；默认 UVS 项按有效字形解析，不只看它的 `None` 形态。
- 主字体字形不会被同名打底字形替换；重名打底字形加别名，同时重映射其组件与 UVS 引用。
- 打底布局特性修剪到存活字形；冲突以主字体为准。
- 最终结构检查字形序、度量覆盖、cmap/UVS 引用、布局索引与可变存储结构。

不保证：

- 每个轴位置逐点相等。可变合成只在抽样网格通过后才被接受（`verify_composition`，本调用点 `max_positions=4`，轮廓容差 1.0 字体单位，字宽容差 3.0 单位）；不通过时回退为按打底默认实例化。
- 保留全部打底特性。打底 lookup 只有引用字形全部存活才保留；主字体冲突优先；打底 FeatureVariations 不与已有主 FeatureVariations 跨来源拼接。
- 整数变化数据无损。GDEF 与 GPOS VariationIndex 增量是整数，重参数化后的列要取整；实测 UPM 1000 下 kerning 变化偏差约 0.70 字体单位。CFF2 HVAR 字宽同样取整。
- 在所有引擎或栅格器中渲染一致。fontTools 序列化与抽样轮廓比对不验证栅格器。

## 7. 调用方会看到的错误

| 情况 | 表现 |
| --- | --- |
| 输入含非法默认 UVS（基础码位无普通映射） | 合并前由 `merge_two` 抛出 `ValueError` |
| 输入含悬空显式 UVS 字形 | `merge_two` 抛出 `ValueError` |
| 字形注入失败 | `RuntimeError`（不返回部分字体） |
| 最终码位/UVS/结构不变量失败 | `AssertionError` |
| 合成路径异常 | 记录日志并回退；除非回退也失败，否则不抛出 |
| 文件缺失或字体损坏 | 向外传播 fontTools 异常 |

支持输入矩阵与已知缺口见[支持边界](limitations.md)。
