# FontMerger 字体合并工具

> **版本:** 0.1.0-alpha1

基于 **fontTools + afdko** 的 Python 字体合并工具包：支持 **静态/可变 × OTF/TTF** 任意组合的多级字体合并，含格式转换、CID 处理、OpenType 特性修剪、Axis 并集、缩放/基线偏移等能力。

---

## 功能总览

| 能力 | 说明 |
|------|------|
| **16 类型合并矩阵** | 静态/可变 × OTF/TTF × 主/打底 的全部 16 种组合（`merge_two` 自动分派） |
| **多级打底** | 主字体 + 1~n 级打底字体依次合并；复杂情况询问只问一次（记忆机制） |
| **格式互转** | CFF↔glyf（三次曲线↔二次曲线），CFF2→CFF（官方 `_convertCFF2ToCFF`）、CFF→CFF2 |
| **CID 合并** | 双 CID 字体 CID 偏移 + 直接 CharString 复制；CID↔name-keyed 转换 |
| **可变字体** | 主 VF 保留可变性输出（CFF2/HVAR/STAT/fvar 完整保留+补全） |
| **Axis 并集** | 主/打底轴空间取并集；varStore(含 GDEF/HVAR/MVAR) 区域恒定轴扩展 |
| **OpenType 特性合并** | 打底 GSUB/GPOS/GDEF 按存活字形修剪（fontTools Subsetter 闭包）；冲突以主为准；字形名深度重映射 |
| **缩放 + 基线偏移** | 关于 (0,0) 点缩放 + 基线偏移（Pen 管线重建轮廓，度量同步） |
| **重叠合并** | 可变→静态实例化后 `removeOverlaps` 布尔合并 |
| **WOFF/WOFF2 解包** | 支持 webfont 直接输入 |
| **命名处理** | 输出家族名 `<主字体> mod`，版权信息合并 |

## 快速开始

```bash
# 交互模式（唯一入口）
python FontMerging.py
```

交互流程：
1. 输入主字体路径 + 缩放倍率(%) + 基线偏移
2. 按 Y 结束前可输入任意级打底字体（各自独立缩放/偏移）
3. 程序自动检测兼容性，提示警告（不兼容可确认继续）
4. 遇到格式/可变性选择时交互询问（同一轮询问只问一次，之后自动复用答案）
5. 输出 `<主字体>_mod.{otf|ttf}`

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
- 第 1 级询问"导出格式"后，第 2 级同类询问自动复用答案（记忆机制）
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

# 合并
r = merger.merge_two(main_font, base_font)          # 逐级
r = apply_naming(r, get_family(main_font), get_copyrights(main_font, base_font))
r.save("merged.otf")
```

## 合并矩阵（5×5）

主/打底各按 `静态/可变 × OTF/TTF` 分类，共 16 种组合的语义定义；行 = 主字体类型，列 = 打底字体类型。

|         | 静态OTF打底 | 静态TTF打底 | 可变OTF打底 | 可变TTF打底 |
| :------ | :---------- | :---------- | :---------- | :---------- |
| **静态OTF为主** | **通用**：多级打底合并、各字体独立缩放/基线偏移 | 询问用户导出为 TTF 还是 OTF | 将打底中与主字体已有字形**码位或名称**相同的字形删除；其余字形 + 仅与剩余字形相关的 OpenType 特性并入主字体（打底自动实例化为默认实例） | 将 OTF 中字形转换为二次曲线；随后同"可变OTF为主，静态OTF打底" |
| **静态TTF为主** | 询问用户导出为 TTF 还是 OTF | **通用** | 将 TTF 中字形转换为三次曲线；随后同"可变OTF为主，静态OTF打底" | 同"可变OTF为主，静态OTF打底" |
| **可变OTF为主** | 询问导出为可变还是静态：① 静态 → 插值得到与主字体轴值相同的静态字体，按静态处理；② 可变 → 删打底冲突字形，主字形加入可变OTF默认 Master，主字体 OpenType 特性插入各 Master | 同左（静态路径） | **Master 处理**：删打底各 Master 中冲突字形；打底各 Master 并入主——轴值相同则在主 Master 中增添字形与特性，轴值不同则新建 Master；**Axis 处理**：Axis 上下限取并集，打底独有 Axis 加入（缺失 Master 补默认值） | 询问导出为 TTF 还是 OTF；随后同"可变OTF为主，可变OTF打底" |
| **可变TTF为主** | 询问导出为可变还是静态（同"可变OTF为主"；可变路径主字形转二次曲线后同左） | 同左（静态路径） | 询问导出为 TTF 还是 OTF；随后同"可变OTF为主，可变OTF打底" | 同"可变OTF为主，可变OTF打底" |

### 通用规则（所有组合）

1. **多级打底**：主字体与前 (n−1) 级打底字体的结果作为第 n 级的"主字体"；已询问过的复杂情况不再询问（记忆）
2. **名称**：Family 名改为 `<主字体名称> mod`；版权信息写入所有字体版权（`^n^n` 分隔）；其余信息与主字体相同
3. **OpenType 特性**：主字体特性完全保留；打底与主不冲突的语言/特性表可完全保留（剔除与已删除字形相关的项）；冲突以主为准
4. **字形保留**：主字体所有字形保留；打底仅"码位与名称均不与主字体冲突"的字形并入
5. 输入 WOFF/WOFF2 自动解包；TTC/OTC 提示先解包；其他格式拒绝

> **当前实现状态**（见"已知限制"）：可变主字体的"② 可变路径"已支持（主 VF 保留输出 + Axis 并集 + 打底字形并入）；"Master 处理"的逐轴插值合成尚未实现（打底字形统一取默认实例并入）。

## 架构

```
FontMerger/
├── FontMerging.py           # 交互式 CLI 主入口
├── __init__.py              # 公共 API 导出
├── core/
│   ├── merger.py            # 16 路分派 + _do_merge 编排（CID/格式/轴并集/OT合并）
│   ├── glyph_copy.py        # TTX XML 往返注入（CharString/glyf/hmtx/vmtx/HVAR）
│   ├── conflict.py          # 码位/名称冲突检测
│   └── naming.py            # 输出命名与版权处理
├── format/
│   ├── static_extract.py    # 可变→静态（CFF2→CFF + 重叠合并 + VORG 保留）
│   ├── converter.py         # glyf↔CFF 转换
│   ├── cid_convert.py       # CID↔name-keyed（rawDict 同步、vmtx、format14 UVS）
│   ├── cid_merge.py         # 双 CID 合并（CID 偏移 + CharString 物化复制）
│   ├── vf_axes.py           # Axis 并集（fvar/avar/STAT/varStore 同步）
│   ├── transform.py         # 缩放+基线偏移（Pen 管线）
│   ├── subsetter.py         # 字形子集化
│   └── webfont.py           # WOFF/WOFF2 解包
├── tables/
│   ├── ot_merge.py          # GSUB/GPOS/GDEF 修剪+合并（Subsetter 闭包）
│   └── base.py              # 逐表 merge 注册表（os2/head/post/hhea... 策略）
├── tests/
│   ├── generate_matrix.py   # 16 组合矩阵生成（v2 真路径）
│   └── test_merger.py       # 核心测试
└── build/                   # PyInstaller 打包配置
```

## 关键设计决策

### 1. TTX 往返注入（而非 fontTools.merge）
`fontTools.merge` 对 CID-keyed CFF 抛 `NotImplementedError`，故用 `saveXML → 注入字形 XML → ttx 编译` 的官方流程，对 CID/命名空间差异有完全控制。

### 2. CID 统一策略
- 双 CID（Adobe-Identity-0）：打底 CID 偏移（+主 max CID + 间隙），CharString 物化后直接复制 — 参考 afdko CIDKeyed UFO 的 CIDMap 重映射思想
- 单 CID：输出统一 name-keyed（消除 ROS/FDSelect 命名空间冲突）
- 关键坑：fontTools `BaseDict.__getattr__` 从 `rawDict` 读回，删除 ROS/FDArray 必须同时清 `rawDict`

### 3. OpenType 特性合并
- 打底布局表用 `fontTools.subset.Subsetter` 闭包修剪到"仅与存活字形相关"
- lookup 追加时做索引重映射 + 字形引用校验（`uni0041`→`A`、`cidXXXX`→主等价名按码位映射）
- 冲突（同 feature tag）以主为准

### 4. Axis 并集
- 共有轴取上下限并集；打底独有轴加入（fvar/avar/STAT 同步）
- **varStore 必须同步**：CFF2/HVAR/MVAR/GDEF 每个 Region 追加恒定轴坐标 (0,0,0)，否则编译报 `RegionAxisCount` 不匹配

### 5. 字体变换
- 缩放/基线偏移用 `T2CharStringPen`/`TTGlyphPen` + `TransformPen` 重建轮廓（与 ufo2ft/varLib 同款官方管线）
- CFF 先 `desubroutinize`；CFF2 先实例化展开 blend
- 度量表（hmtx/vmtx/OS2/head/post/VORG）同步缩放

## 测试与验证

### 16 矩阵验证（`tests/generate_matrix.py`）
```
A1-A4  静态+静态    → static
B1-B4  静态+可变    → static（打底自动实例化）
C1     JP+拉丁(CID) → static（JP CID CFF2 主降级路径）
C2-C4  可变+静态    → VAR（保留主 VF 轴）
D1     JP+Serif    → static（JP CID CFF2 主降级路径）
D2-D4  可变+可变    → VAR（Axis 并集，如 wght[50,1000] opsz[4,60] wdth[50,100]）
```

### HarfBuzz shaping 验证
合并字体与主字体 kern/liga 逐项对比：
- kern：`AVAT` on/off advance 与主**完全一致**（主优先语义正确）
- liga：`ffi` 1 字形 vs 3 字形（连字生效）
- 多级合并（主+2 打底）：kern/liga 均正确，GSUB/GPOS/GDEF 编译通过

### 覆盖的难点案例
- 双 CID 大字体合并（17944 字形 JP + 1464 字形 Serif）
- CFF2 ↔ CFF 版本对齐（FDArray 重映射、HVAR VarIdxMap 补条目）
- format 14 cmap (UVS) 重命名
- 双 CFF2 合并的 vmtx 默认值补齐

## 已知限制

1. **JP（CID CFF2）作主字体**（C1/D1）：合并**可成功**（18600/18868 字形），但保存阶段打底 latin 的 cmap format 4 引用偶发不完整，矩阵采用**实例化静态路径**降级；如需真·可变输出需攻克 CFF2 CID 注入的更深层命名空间问题
2. **Master 级插值合并**（打底字形随打底轴变动的融合）：当前实现为"打底默认实例并入主 VF"（打底字形在主 VF 各轴恒定），未做 varLib.build 式的多 Master 合成
3. **OT 特性**：GSUB/GPOS 追加的打底 feature 引用的所有字形须存在于主字体（否则跳过）；GDEF 主优先
4. **VORG**：默认轴位置实例化时 VORG 值不变（正确）；非默认位置需额外重算
5. **多级打底的 OT 特性**：逐级合并时上级已并入的 feature 会被下级重复检测（幂等，但 lookup 可能冗余）

## 依赖

- Python ≥ 3.8
- fontTools ≥ 4.49（`CFFToCFF2`、`scaleUpem`、`subset` 闭包）
- 可选：afdko（未作为运行时依赖；`cid_convert` 参考其 CIDKeyed UFO 规范）

## 打包

```bash
# PyInstaller（见 build/merge_fonts.spec）
pyinstaller build/merge_fonts.spec
```

## License

MIT（示例字体 Copyright 归各自作者，仅测试用）
