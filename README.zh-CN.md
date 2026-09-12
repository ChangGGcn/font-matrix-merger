# font-matrix-merger

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![FontTools](https://img.shields.io/badge/fontTools-%E2%89%A54.49-important.svg)]()
[![Version](https://img.shields.io/badge/version-0.1.1-blue.svg)]()

[English](README.md) | **简体中文**

**font-matrix-merger** 是一个功能强大的 Python 字体合并库：支持 **静态/可变 × OTF/TTF** 主字体与打底字体的 **全部 16 种组合**，涵盖格式转换、CID-keyed CFF 处理、OpenType 特性合并、可变字体 Axis 并集、缩放与基线偏移，以及多级（n 步）链式合并。

## 项目简介

本库构建于 [**FontTools**](https://github.com/fonttools/fonttools)（MIT 协议）之上——负责全部字形/表级操作、CFF/CFF2 转换、varLib 实例化与子集化；并遵循 [**AFDKO**](https://github.com/adobe-type-tools/afdko)（Adobe Font Development Kit for OpenType，Apache-2.0）的规范——AFDKO 被打包进本项目的 PyInstaller 构建管线，其 CIDKeyed UFO / CIDMap 重映射思路是 CID 合并实现的重要参考。

核心亮点：

- **16 路合并矩阵**：`merge_two()` 对任意主/打底组合自动分派正确策略。
- **多级链式合并**：主字体 + 1~n 级打底逐级合并；格式/导出询问只问一次（答案记忆）。
- **CID 感知**：双 CID 字体通过 CID 偏移 + CharString 物化复制合并；CID↔name-keyed 自动归一。
- **可变字体**：可变主字体输出仍保持可变，主/打底 Axis 取**并集**（fvar/avar/STAT 同步，varStore Region 扩展）。
- **跨设计空间合成**：打底可变时，其逐字形增量会被**重参数化到合并后的归一化空间**（`format/axis_mapping.py`），使合并字形在任意位置都与打底在该位置的实例逐点一致——支持打底独有轴、不同轴范围与不同 `avar`。打底默认点与合并默认点不重合时，缺的 master 由幽灵点插值补出并重定基；网格自检（`verify_composition`）不通过则回退到旧的"按打底默认实例化"行为。同一套数学还覆盖 **CFF2 打底**（`format/cff2_compose.py`：逐条重写 `blend`/`vsindex`，并集 `VarStore`，按字形名重接打底 `HVAR`）与打底的**布局变化数据**（`GDEF` `ItemVariationStore` + `GPOS` `VariationIndex` 设备）。
- **OpenType 合并**：打底 GSUB/GPOS/GDEF 通过 `fontTools.subset` 闭包修剪到存活字形后追加，带 lookup 索引重映射与字形名深度重映射；冲突以主为准。
- **纯 FontTools 管线**：字形注入走官方 TTX XML 往返（`saveXML` → 注入 → `ttx` 编译），绕开 `fontTools.merge` 对 CID-keyed CFF 抛出的 `NotImplementedError`。
- **同源分片并集**：`merge_subsets()` 把同一可变字体按 `unicode-range` 切出的 webfont 分片**保特性**并回一个可变字体——**glyf 与 CFF2** 轮廓、`gvar`/CFF2 blend（`vsindex` + FDSelect/FDArray）、`hmtx`/`vmtx`、`cmap`、GSUB/GPOS lookup（同 tag **并集**）、GDEF `ItemVariationStore`/`MarkGlyphSetsDef`、`HVAR`/`VVAR` 全部保留，字重插值与 `vert`/`vrt2`/`kern`/`mark` 不丢。
- **合并自检**：`verify_merge()` 在多个轴位置实例化源分片与合并结果，逐字形比对轮廓/度量，并断言码位、特性、布局完整性与容器元数据。
- **产物保存防护**：所有保存点走 `save_font()`——清 `flavor` + 校验 sfnt 魔数；woff2 载入的字体不会再被写成"名为 .ttf、实为 `wOF2`"的文件。

### 目录结构

```
FontMerger/
├── FontMerging.py           # 交互式 CLI 主入口
├── __init__.py              # 公共 API 导出
├── core/                    # 16 路分派、TTX 字形注入、冲突检测、命名
├── format/                  # 静态提取、CFF↔glyf、CID、Axis 并集、变换、子集、webfont
├── tables/                  # 逐表合并注册表 + GSUB/GPOS/GDEF 合并
├── tests/                   # 16 矩阵生成器 + 单元测试
└── build/                   # PyInstaller 打包（捆绑 FontTools + AFDKO）
```

## 功能介绍

| 能力 | 说明 |
|---|---|
| **16 类型合并矩阵** | 静态/可变 × OTF/TTF × 主/打底的全部 16 种组合（`merge_two` 自动分派） |
| **多级打底** | 主字体 + 1~n 级打底依次合并；每级可独立缩放/基线偏移 |
| **格式互转** | CFF↔glyf（三次曲线↔二次曲线），CFF2→CFF（官方 `_convertCFF2ToCFF`）、CFF→CFF2 |
| **CID 合并** | 双 CID：CID 偏移 + CharString 物化直接复制；CID↔name-keyed 转换（含 cmap format 14 UVS） |
| **可变字体** | 主 VF 输出保持可变（CFF2/HVAR/STAT/fvar 完整保留并补全）；主/打底轴空间与 `avar` 一致时，打底字形的 `gvar` 增量一并保留（HVAR 由幽灵点重建） |
| **跨设计空间合成** | 打底的可变数据——`gvar` 增量、**CFF2 `blend`/`vsindex`**（含 `VarStore`/`HVAR` 并集）与布局变化数据（`GDEF` `ItemVariationStore` + `GPOS` `VariationIndex` 设备）——都重参数化到合并归一化空间（hat 精确分解），支持打底独有轴、不同范围/`avar`（用户空间钳制 + 精确拆 hat）；varStore **行保持** → 所有 `(outer, inner)` 引用无需重写；主字体自己的 varStore 同步重算；带自检门控与回退；策略参数 `compose_variations`/`compose_range`/`compose_fit`/`avar_mode`/`compose_layout` |
| **Axis 并集** | 主/打底轴空间取并集；varStore（含 GDEF/HVAR/MVAR）恒定轴 Region 扩展 |
| **OpenType 特性合并** | 打底 GSUB/GPOS/GDEF 用 Subsetter 闭包修剪后追加；同 tag feature **并成一条记录**，打底 Script/LangSys 一并并入（追加的 feature 才可达），FeatureList 重排后重写 `FeatureVariations` 索引，GDEF 字类/VarStore/MarkGlyphSets 取并集并重映射 `LookupFlag` bit4 的 `MarkFilteringSet` |
| **缩放 + 基线偏移** | Pen 管线重建轮廓（T2CharStringPen/TTGlyphPen + TransformPen），度量同步 |
| **重叠合并** | 可变→静态实例化后 `removeOverlaps` 布尔合并 |
| **子集化** | `create_glyph_subset` — 按字符集保留字形 |
| **WOFF/WOFF2 解包** | webfont 可直接作为输入 |
| **同源分片并集** | `merge_subsets()`：同一 VF 的 `unicode-range` 分片对象级并集（不走 TTX）；**glyf + CFF2**（CharStrings/FDSelect/FDArray 并集，CFF2 `blend`/`vsindex` 原样保留）、feature/Script/GDEF VarStore/MarkGlyphSets 并集、FeatureVariations 索引重写、HVAR 重建（glyf）或 HVAR VarStore 并集（CFF2）、VVAR 重定位、cmap 统一、name 补全 |
| **合并自检** | `verify_merge()`：多轴位置逐字形轮廓/度量比对 + cmap/特性/布局完整性/容器断言 |
| **保存防护** | `save_font()`：清 `flavor`、校验 sfnt 魔数；`head.flags` 清 WOFF2 残留位、补 nameID 16/17/25 与实例 PS 名 |
| **glyf 快速注入** | `glyf`+`glyf` 合并改为对象级逐字形复制，不再整字体 TTX 往返（给 25k 字形主字体加 135 个字形：153s → 3.7s）；CFF/CFF2/CID 仍走 TTX 管线 |
| **命名处理** | 输出家族名 `<主字体> mod`，版权信息 `^n^n` 分隔合并 |

### 合并矩阵（4×4）

主/打底各按 `静态/可变 × OTF/TTF` 分类，共 16 种组合的语义定义；**行 = 主字体类型，列 = 打底字体类型。**

| | 静态OTF打底 | 静态TTF打底 | 可变OTF打底 | 可变TTF打底 |
| :--- | :--- | :--- | :--- | :--- |
| **静态OTF为主** | *通用*：多级打底合并、各字体独立缩放/基线偏移 | 询问用户导出为 TTF 还是 OTF | 将打底中与主字体已有字形**码位或名称**相同的字形删除；其余字形 + 仅与剩余字形相关的 OpenType 特性并入主字体（打底自动实例化为默认实例） | 将 OTF 中字形转换为二次曲线；随后同“可变OTF为主，静态OTF打底” |
| **静态TTF为主** | 询问用户导出为 TTF 还是 OTF | *通用* | 将 TTF 中字形转换为三次曲线；随后同“可变OTF为主，静态OTF打底” | 同“可变OTF为主，静态OTF打底” |
| **可变OTF为主** | 询问导出为可变还是静态：① 静态 → 插值得到与主字体轴值相同的静态字体，按静态处理；② 可变 → 删打底冲突字形，主字形加入可变OTF默认 Master，主字体 OpenType 特性插入各 Master | 同左（静态路径） | *Master 处理*：删打底各 Master 中冲突字形；打底各 Master 并入主——轴值相同则在主 Master 中增添字形与特性，轴值不同则新建 Master；*Axis 处理*：Axis 上下限取并集，打底独有 Axis 加入（缺失 Master 补默认值） | 询问导出为 TTF 还是 OTF；随后同“可变OTF为主，可变OTF打底” |
| **可变TTF为主** | 询问导出为可变还是静态（同“可变OTF为主”；可变路径主字形转二次曲线后同左） | 同左（静态路径） | 询问导出为 TTF 还是 OTF；随后同“可变OTF为主，可变OTF打底” | 同“可变OTF为主，可变OTF打底” |

### 通用规则（所有组合）

1. **多级打底**：主字体与前 (n−1) 级打底字体的结果作为第 n 级的“主字体”；已询问过的复杂情况不再询问（记忆）
2. **名称**：Family 名改为 `<主字体名称> mod`；版权信息写入所有版权字段（`^n^n` 分隔）；其余信息与主字体相同
3. **OpenType 特性**：主字体特性完全保留；打底与主不冲突的语言/特性表可完全保留（剔除与已删除字形相关的项）；冲突以主为准
4. **字形保留**：主字体所有字形保留；打底仅“码位与名称均不与主字体冲突”的字形并入
5. **输入格式**：WOFF/WOFF2 自动解包；TTC/OTC 需先解包；其他格式拒绝

> **当前实现状态**：可变主字体的“② 可变路径”已支持（主 VF 保留输出 + Axis 并集 + 打底字形按默认实例并入）；“Master 处理”的逐轴插值合成（打底字形随打底轴变动）尚未实现。

## 快速开始

环境要求：**Python ≥ 3.8**，**FontTools ≥ 4.49**。

```bash
git clone https://github.com/ChangGGcn/font-matrix-merger.git
cd font-matrix-merger
pip install "fonttools>=4.49"

# 交互式 CLI
python FontMerging.py
```

CLI 为交互式：依次输入主字体（缩放% + 基线偏移）、任意级打底字体（`Y` 结束），兼容性警告按 `y` 确认继续，最终输出 `<主字体>_mod.{otf|ttf}`。

### 三字体输入输出样例（主 + 两级打底）

```
========================================================
  FontMerger 字体合并工具
  支持: 静态/可变 x OTF/TTF x 多级打底 x WOFF/WOFF2
========================================================

请输入主字体（拖入文件或输入路径）:
  主字体路径:  test/OpenType/LibreCaslonText-Regular.otf
  缩放倍率(%) [100]: 100
  基线偏移 [0]: 0
第 1 级打底字体（Y 结束）:
  路径:  test/otf_variable_fonts/SourceSerif4Variable-Roman.otf
  缩放倍率(%) [100]: 100
  基线偏移 [0]: 0
第 2 级打底字体（Y 结束）:
  路径:  test/TrueType/LXGWWenKaiTC-Regular.ttf
  缩放倍率(%) [100]: 100
  基线偏移 [0]: 0
第 3 级打底字体（Y 结束）:
  路径:  Y

加载字体...
  test/OpenType/LibreCaslonText-Regular.otf
    静态OTF, 537 字形
  test/otf_variable_fonts/SourceSerif4Variable-Roman.otf
    可变OTF, 1464 字形
  test/TrueType/LXGWWenKaiTC-Regular.ttf
    静态TTF, 25764 字形

兼容性检查...
  [警告] 打底字体为可变字体, 将先实例化为静态再合并
  [警告] 混合轮廓格式: 主字体为CFF, 打底为glyf. 将自动转换打底字体
  [警告] 主字体为可变字体, 将先实例化为静态再合并

开始合并...

--- 第 1 级 ---
  主: 静态OTF | 打底: 可变OTF
  [CFF2→CFF] 转换完成 (1464 glyphs)
  [重叠合并] 完成 (1464 glyphs)
  [CID归一] 打底字体 CID→name (输出统一为 name-keyed)
  [CID→name] 转换完成 (1464 glyphs)
  [冲突] 409 个字形
  [新增] 1054 个字形
  合并后字形: 1591
  [OT合并] GDEF: 来自打底 (主无, 过滤后 200 个字类)
  [OT合并] GSUB: 追加 10 个打底 feature (主冲突跳过)
  [OT合并] GPOS: 追加 2 个打底 feature (主冲突跳过)

--- 第 2 级 ---
  主: 静态OTF | 打底: 静态TTF
  [询问] 导出为 TTF 还是 OTF？
    1. OTF
    2. TTF
> 1
  [转换] 轮廓格式不同，自动转换打底字体...
  [冲突] 915 个字形
  [新增] 24848 个字形
  [分块] 5 块, 每块 ≤5000 字形
  [OT合并] GSUB: 追加 2 个打底 feature (主冲突跳过)
  [OT合并] GPOS: 追加 3 个打底 feature (主冲突跳过)

处理名称...

输出路径 [test/OpenType/LibreCaslonText-Regular_mod.otf]: 
完成! test/OpenType/LibreCaslonText-Regular_mod.otf
  静态OTF, 26439 字形
```

要点：

- 导出格式类询问只问一次，后续级自动复用答案（记忆机制）
- 每级打底可独立指定缩放倍率与基线偏移
- 兼容性警告仅提示，`y` 可确认继续

### 编程接口

```python
from FontMerger import FontMerger, apply_naming, get_family, get_copyrights
from FontMerger.format.static_extract import variable_to_static
from fontTools.ttLib import TTFont

merger = FontMerger()
# 预设询问答案（非交互）
merger.mem = {"sOTF_sTTF": "OTF", "vOTF_sOTF": "可变"}

# 逐级合并
r = merger.merge_two(main_font, base_font)
r = apply_naming(r, get_family(main_font), get_copyrights(main_font, base_font))
r.save("merged.otf")

# 或一行快捷函数
from FontMerger import merge_fonts
result = merge_fonts("main.otf", ["base1.otf", "base2.ttf"])

# 显式预设询问答案（非交互）
result = merge_fonts("main.otf", ["base.otf"], answers={"vOTF_sOTF": "静态"})
```

#### 跨设计空间合成参数

主/打底同为可变但**轴集合/范围或 `avar` 不同**时，打底增量必须先重参数化到合并
归一化空间。以下参数是该步骤的策略开关，默认值即"最还原设计师意图"的推荐值：

| 参数 | 默认 | 含义 |
| --- | --- | --- |
| `compose_variations` | `True` | 总开关。合成结果若通不过网格自检，会**自动回退**到旧行为（打底按默认实例化）并告警，因此开启它不会产出比原来更差的字体 |
| `compose_range` | `"main+extra"` | 合并后各轴取什么范围：`"main+extra"` = 共有轴沿用**主字体**范围，仅打底有的轴按打底范围新增；`"union"` = 取二者最宽（外插误差更大，剪枝前元组数最多可达 ×28）；`"main"` = 只用主字体轴，打底独有轴被钳掉 |
| `compose_fit` | `"exact"` | `"exact"` = 打底元组精确拆到合并节点栅格上（逐点一致，元组更多）；`"affine"` = 在合并空间为每个元组拟合单个 hat（更紧凑，但实测偏差约 6 单位，通常被自检拒绝） |
| `avar_mode` | `0` | `0` = 保留主字体 `avar`（最还原主字体设计师意图；默认点不同时用幽灵点插值补 master）；`1` = 弃用打底 `avar`、两者共用主字体 `avar`；`2` = 输出完全不带 `avar`（主字体 `avar` 把某段用户区间压成一个点时，可借此恢复打底的增量） |
| `verify_compose` | `True` | 采用合成结果前，在合并轴的小网格上跑 `verify_composition()` 自检；不通过则告警并回退 |
| `compose_layout` | `True` | 打底的**布局**变化数据（`GDEF` `ItemVariationStore` + `GPOS` `VariationIndex` 设备）一并重参数化并入，打底的 kerning/mark/anchor 变化在合并字体里继续生效；varStore 行保持 → 引用无需重写。关闭则回到旧行为（打底布局冻结在合并默认点） |

```python
# 跨设计空间合并：打底带来自己的轴与 avar
merger = FontMerger(compose_variations=True, compose_range="main+extra", avar_mode=0)
r = merger.merge_two("ZedText-VF.ttf", "InterVariable.ttf")
```

### 同源分片并集（`merge_subsets`）

当一个可变字体以 N 个 webfont 分片发布（每个 `@font-face` 一个 `unicode-range`），
用通用的可变×可变路径并回时，每个打底分片都会被实例化成静态字体——`gvar`/`HVAR`/`VVAR`
以及除第一个分片外所有分片的 `vert`/`vrt2`/`kern`/`mark` 都会丢失。
`merge_subsets()` 走并集路径：不实例化、不做轴并集，每个分片的字形、增量与 lookup 原样保留。

```python
from FontMerger import merge_subsets, verify_merge

paths = sorted(glob("webfont/ja-v2/*.woff2"))      # subsets[0] 作基底

merged = merge_subsets(paths, out_path="OpenAISansJP-Merged.ttf", tag="ja",
                       complete_name_table=True, fix_head_flags=True)

# 自检: 在默认/轴两端实例化源分片与合并结果逐字形比对
report = verify_merge(paths, merged,
                      glyph_map=merged.subset_merger.glyph_map())
assert report["ok"], report["failures"]

# 源字形名 → 合并后 GID（重排之后），按分片
gmap = merged.subset_merger.glyph_map()
```

也可以一次调用完成（内置自检）：

```python
merged = merge_subsets(paths, out_path="Merged.ttf", tag="ja", verify=True)
```

### 测试

`tests/generate_matrix.py` 生成 16 组合完整矩阵；`tests/test_merger.py` 为单元测试，`tests/test_subset_merge.py` 覆盖同源分片并集。分片用例用 `pyftsubset` 现场生成夹具（`tests/subset_fixture.py`），不需要随仓库分发任何 webfont 分片。测试需要本地字体集（路径解析于 `tests/../test/`）——**字体本身不随仓库分发**。样例所用的 [Google Fonts OFL 字体](https://fonts.google.com/)（Libre Caslon Text、LXGW WenKai TC、Source Serif/Source Han、Zed Text）可自由下载；**商业授权**测试字体通过本地不入库文件 `tests/local_fonts.py` 映射（模板：`tests/local_fonts.example.py`），任一字体缺失时对应用例自动跳过。

## 已知限制

1. **JP（CID CFF2）作主字体**（矩阵 C1/D1）：合并本身成功（约 18,600~18,868 字形），但保存阶段打底拉丁字形在 cmap format 4 的引用偶发不完整；矩阵生成器降级走静态实例化路径。如需真·可变输出，需攻克 CFF2 CID 注入的更深层命名空间问题
2. **跨设计空间的字形增量**：主/打底同为可变且**轴空间与 `avar` 完全一致**时（`axes_compatible()` 判定），打底 `gvar` 增量 1:1 搬入并用幽灵点重建 `HVAR`；轴空间不一致（轴集合/范围或 avar 不同）时走**合成**路径——由 `format/axis_mapping.py` 把打底增量重参数化到合并归一化空间，经 `verify_composition` 网格自检（容差 1 单位）通过才采用，否则透明回退到"打底按默认实例化"。该路径目前的缺口：(a) 要求主/打底的可变数据在**同一种轮廓技术**里：`glyf` 组合需要两边都有 `gvar`，CFF2 组合需要两边都有带 `VarStore` 的 `CFF2`（`glyf`↔`CFF2` 混搭、或变化数据在别的表里，仍回退实例化）；CFF2 路径里打底 `HVAR` 按字形名并入，而 `VVAR` 与 Private 的 hint 变化保持静态（hint 的 blend 折成默认值）；(b) 合并后的 `avar` 是主字体的，若主轴把某段用户区间压成归一化空间的一个点（`collapsing_flats()`），打底在该区间的增量在 OT 模型下无法逐点还原——检测到会告警并保留主字体行为（可传 `avar_mode=2` 丢弃 `avar` 以恢复打底增量，代价是改变主字体的插值）；(c) 打底的布局变化数据也会搬入（`transfer_base_layout()`：`GDEF` `ItemVariationStore` + `GPOS` `VariationIndex`），但 VariationIndex 的增量是整数，重参数化后的列要取整，所以 kerning/anchor 变化可能有至多约 1 单位的偏差（实测 UPM 1000 下 Inter 的 kerning 为 0.70 单位）——可传 `compose_layout=False` 保持旧行为（打底布局冻结在合并默认点）；(d) 主字体自己的 varStore 只在轴空间真的变化时（`compose_range="union"`/`"main"` 或 `avar_mode != 0`）才重参数化，此时默认点的那一项由"恒定 region"（全轴峰值 0）承载
3. **OpenType 特性**：追加的打底 feature 所引用字形必须存在于主字体（否则跳过该 lookup）。同 tag feature 并成一条记录；打底 Script/LangSys 一并并入（否则追加的 feature 不可达）；FeatureList 重排后重写 `FeatureVariations` 的 FeatureIndex（表本身保留，无法映射的记录才会被丢）；GDEF `GlyphClassDef`/`MarkAttachClassDef`/`MarkGlyphSetsDef` 与 `ItemVariationStore` 均取并集，并重映射 `LookupFlag` bit4 的 `MarkFilteringSet`。异源路径不并入**打底字体自己的** `FeatureVariations`（只保留主字体的）
4. **VORG**：默认轴位置实例化时数值正确；非默认位置需额外重算
5. **多级 OT 特性**：上级已并入的 feature 会在下级被重复检测（幂等，但 lookup 可能冗余）
6. **打包**：仓库根目录即包本身，`pip install` 尚未接线——目前 clone 即用；PyPI 化目录结构在规划中
7. **本地授权字体**仅用于本地测试，刻意不包含在本仓库中（真实路径见未入库的 `tests/local_fonts.py`）；文档样例中出现的字体均为 OFL 开源授权。
8. **`merge_subsets()` 的 CFF2 边界**：glyf 与 CFF2 分片都支持，但 CFF2 要求各分片共享同一 **VarStore / GlobalSubrs** 结构（pyftsubset 会原样保留）；FDArray 的差异由 FD 级并集处理。若某个工具逐分片重建/重编号了 CFF2 VarStore，则 `blend`/`vsindex` 需要重写——该路径会明确报错而不是产出坏字体。CFF 与 CFF2 混合分片不支持。
9. **自动名字形一律加别名**：post 3.0 的序号名（`glyphNNNNN`）在分片间同名但不同源，故一律改名保留——同一无码位字形被多个分片保留时会多出一份内容相同的副本，用少量体积换取"绝不混淆两个不同字形"。

## 协议

以 [MIT 协议](LICENSE) 发布。测试用示例字体版权归其各自作者所有。
