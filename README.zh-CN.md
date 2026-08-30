# font-matrix-merger

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![FontTools](https://img.shields.io/badge/fontTools-%E2%89%A54.49-important.svg)]()
[![Version](https://img.shields.io/badge/version-0.1.0--alpha1-orange.svg)]()

[English](README.md) | **简体中文**

**font-matrix-merger** 是一个功能强大的 Python 字体合并库：支持 **静态/可变 × OTF/TTF** 主字体与打底字体的 **全部 16 种组合**，涵盖格式转换、CID-keyed CFF 处理、OpenType 特性合并、可变字体 Axis 并集、缩放与基线偏移，以及多级（n 步）链式合并。

## 项目简介

本库构建于 [**FontTools**](https://github.com/fonttools/fonttools)（MIT 协议）之上——负责全部字形/表级操作、CFF/CFF2 转换、varLib 实例化与子集化；并遵循 [**AFDKO**](https://github.com/adobe-type-tools/afdko)（Adobe Font Development Kit for OpenType，Apache-2.0）的规范——AFDKO 被打包进本项目的 PyInstaller 构建管线，其 CIDKeyed UFO / CIDMap 重映射思路是 CID 合并实现的重要参考。

核心亮点：

- **16 路合并矩阵**：`merge_two()` 对任意主/打底组合自动分派正确策略。
- **多级链式合并**：主字体 + 1~n 级打底逐级合并；格式/导出询问只问一次（答案记忆）。
- **CID 感知**：双 CID 字体通过 CID 偏移 + CharString 物化复制合并；CID↔name-keyed 自动归一。
- **可变字体**：可变主字体输出仍保持可变，主/打底 Axis 取**并集**（fvar/avar/STAT 同步，varStore Region 扩展）。
- **OpenType 合并**：打底 GSUB/GPOS/GDEF 通过 `fontTools.subset` 闭包修剪到存活字形后追加，带 lookup 索引重映射与字形名深度重映射；冲突以主为准。
- **纯 FontTools 管线**：字形注入走官方 TTX XML 往返（`saveXML` → 注入 → `ttx` 编译），绕开 `fontTools.merge` 对 CID-keyed CFF 抛出的 `NotImplementedError`。

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
| **可变字体** | 主 VF 输出保持可变（CFF2/HVAR/STAT/fvar 完整保留并补全） |
| **Axis 并集** | 主/打底轴空间取并集；varStore（含 GDEF/HVAR/MVAR）恒定轴 Region 扩展 |
| **OpenType 特性合并** | 打底 GSUB/GPOS/GDEF 用 Subsetter 闭包修剪；同 tag 冲突以主为准 |
| **缩放 + 基线偏移** | Pen 管线重建轮廓（T2CharStringPen/TTGlyphPen + TransformPen），度量同步 |
| **重叠合并** | 可变→静态实例化后 `removeOverlaps` 布尔合并 |
| **子集化** | `create_glyph_subset` — 按字符集保留字形 |
| **WOFF/WOFF2 解包** | webfont 可直接作为输入 |
| **命名处理** | 输出家族名 `<主字体> mod`，版权信息 `^n^n` 分隔合并 |

### 合并矩阵（5×5）

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
  主字体路径:  test/OpenType/ClassicoURW-Reg.otf
  缩放倍率(%) [100]: 100
  基线偏移 [0]: 0
第 1 级打底字体（Y 结束）:
  路径:  test/otf_variable_fonts/SourceSerif4Variable-Roman.otf
  缩放倍率(%) [100]: 100
  基线偏移 [0]: 0
第 2 级打底字体（Y 结束）:
  路径:  test/TrueType/tt0015m_.ttf
  缩放倍率(%) [100]: 100
  基线偏移 [0]: 0
第 3 级打底字体（Y 结束）:
  路径:  Y

加载字体...
  test/OpenType/ClassicoURW-Reg.otf
    静态OTF, 657 字形
  test/otf_variable_fonts/SourceSerif4Variable-Roman.otf
    可变OTF, 1464 字形
  test/TrueType/tt0015m_.ttf
    静态TTF, 261 字形

兼容性检查...
  [警告] 打底字体为可变字体, 将先实例化为静态再合并
  [警告] 混合轮廓格式: 主字体为CFF, 打底为glyf. 将自动转换打底字体
  [警告] 打底字体为可变字体, 将先实例化为静态再合并
  [警告] UPM不匹配: 主字体1000 vs 打底字体2048. 将自动缩放打底字体

开始合并...

--- 第 1 级 ---
  主: 静态OTF | 打底: 可变OTF
  [CFF2→CFF] 转换完成 (1464 glyphs)
  [重叠合并] 完成 (1464 glyphs)
  [CID归一] 打底字体 CID→name (输出统一为 name-keyed)
  [冲突] 608 个字形
  [新增] 855 个字形
  合并后字形: 1512
  [OT合并] GDEF: 来自打底 (主无, 过滤后 147 个字类)
  [OT合并] GSUB: 追加 10 个打底 feature (主冲突跳过)
  [OT合并] GPOS: 追加 1 个打底 feature (主冲突跳过)

--- 第 2 级 ---
  主: 静态OTF | 打底: 静态TTF
  [询问] 导出为 TTF 还是 OTF？
    1. OTF
    2. TTF
> 1
  [UPM] 缩放打底字体: 2048 → 1000
  [转换] 轮廓格式不同，自动转换打底字体...
  [冲突] 259 个字形
  [新增] 1 个字形
  合并后字形: 1513
  [OT合并] 打底无布局表, 跳过

处理名称...

输出路径 [test/OpenType/ClassicoURW-Reg_mod.otf]: 
完成! test/OpenType/ClassicoURW-Reg_mod.otf
  静态OTF, 1513 字形
```

要点：

- 第 1 级询问的“导出格式”在第 2 级自动复用答案（记忆机制）
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
```

### 测试

`tests/generate_matrix.py` 生成 16 组合完整矩阵；`tests/test_merger.py` 为单元测试。测试需要本地字体集（路径解析于 `tests/../test/`）——**字体本身不随仓库分发**。

## 已知限制

1. **JP（CID CFF2）作主字体**（矩阵 C1/D1）：合并本身成功（约 18,600~18,868 字形），但保存阶段打底拉丁字形在 cmap format 4 的引用偶发不完整；矩阵生成器降级走静态实例化路径。如需真·可变输出，需攻克 CFF2 CID 注入的更深层命名空间问题
2. **Master 级插值合成**（打底字形随打底轴变动）：尚未实现——打底字形按打底默认实例并入，在主 VF 各轴上恒定
3. **OpenType 特性**：追加的打底 feature 所引用字形必须存在于主字体（否则跳过该 feature）；GDEF 冲突以主为准
4. **VORG**：默认轴位置实例化时数值正确；非默认位置需额外重算
5. **多级 OT 特性**：上级已并入的 feature 会在下级被重复检测（幂等，但 lookup 可能冗余）
6. **打包**：仓库根目录即包本身，`pip install` 尚未接线——目前 clone 即用；PyPI 化目录结构在规划中
7. **本地授权字体**（如 Helvetica Now Var、方正、汉仪字体）仅用于本地测试，刻意不包含在本仓库中

## 协议

以 [MIT 协议](LICENSE) 发布。测试用示例字体版权归其各自作者所有。
