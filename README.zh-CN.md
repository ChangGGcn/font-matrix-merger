# font-matrix-merger

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![FontTools](https://img.shields.io/badge/fontTools-%E2%89%A54.49-important.svg)]()
[![Version](https://img.shields.io/badge/version-0.2.1-blue.svg)]()

[English](README.md) | **简体中文**

font-matrix-merger 是基于 [FontTools](https://github.com/fonttools/fonttools) 的字体合并 Python 库，参考了 [AFDKO](https://github.com/adobe-type-tools/afdko) 的 CID 处理思路，不依赖 AFDKO。本库采用 [MIT License](LICENSE)，发布历史见 [CHANGELOG.md](CHANGELOG.md)。

完整用法、参数与实现说明见[技术文档](doc/README.zh-CN.md)。

## 核心亮点

- **16 路合并矩阵**：主、打底各按静态/可变与 glyf/CFF（含 CFF2）分类，形成 16 种组合，支持 TTF、OTF、WOFF/WOFF2 输入

- **多级 fallback 合并**：支持 ≥ 2 款字体按优先级逐级补齐码位

- **缩放 + 基线偏移**： 保留坐标、可变拓扑并同步纵向原点与度量；非恒等变换明确移除不安全 hinting 和像素缓存

- **CID 字体支持**：双 CID 字体通过 CID 偏移 + CharString 物化复制合并；CID ↔ name-keyed 自动归一

- **可变字体支持**：选择可变输出时保留主字体可变性；默认保留主轴范围并加入打底独有轴，可配置共有轴范围并集

- **跨设计空间合成**：在支持的轮廓技术和轴空间内，将打底的可变增量重参数化到合并空间，并做网格自检；失败时告警并回退，支持边界见技术文档

- **OpenType 特性合并**：GSUB/GPOS/GDEF 通过 `fontTools.subset` 闭包修剪到存活字形后追加，带 lookup 索引重映射与字形名深度重映射；冲突以主字体为准

- **同源分片并集**：把同一可变字体按 `unicode-range` 切出的 webfont 分片**保特性**并回一个可变字体

- **合并自检**：在多个轴位置实例化源分片与合并结果，逐字形比对轮廓/度量，并检查码位、特性、布局完整性与容器元数据

- **产物保存防护**：`save_font()` 清理 `flavor` 并校验 sfnt 魔数，避免把 WOFF2 内容误存为扩展名为 `.ttf` 的桌面字体

## 目录结构

```
FontMerger/
├── FontMerging.py           # 交互式 CLI 主入口
├── __init__.py              # 公共 API 导出
├── CHANGELOG.md             # 发布历史
├── core/                    # 16 路分派、TTX 字形注入、冲突检测、命名
├── format/                  # 静态提取、CFF↔glyf、CID、Axis 并集、变换、子集、webfont
├── tables/                  # 逐表合并注册表 + GSUB/GPOS/GDEF 合并
├── doc/                     # 公开双语技术文档
├── tests/                   # 16 矩阵生成器 + 单元测试
└── build/                   # PyInstaller 打包 + 仅源码发布包（make_release_zip.py）
```

## 快速开始

### 安装

环境要求：**Python ≥ 3.8**，**FontTools ≥ 4.49**。

```bash
git clone https://github.com/ChangGGcn/font-matrix-merger.git FontMerger
cd FontMerger
pip install "fonttools>=4.49"
```

### 交互式 CLI

```
# 交互式 CLI
python FontMerging.py
```

CLI 为交互式：依次输入主字体（缩放% + 基线偏移）、任意级打底字体（`Y` 结束），兼容性警告仅提示、不兼容时询问 `y`/`N`，最终输出 `<主字体>_mod.{otf|ttf}`。

### 后端接口

```python
from FontMerger import merge_fonts, save_font

result = merge_fonts("Main.otf", ["Base-One.otf", "Base-Two.ttf"])
save_font(result, "Merged.otf")

# 显式选择静态输出；答案覆盖非交互默认策略
result = merge_fonts(
    "Main-VF.otf", ["Base.otf"], answers={"vOTF_sOTF": "静态"}
)
```

`merge_fonts()` 返回字体而不落盘。逐级合并、所有权及完整参数见[合并 API](doc/zh-CN/merge-api.md)。从源码使用时，需让 `FontMerger` 的父目录位于 Python 搜索路径。

### 同源分片并集（`merge_subsets`）

当一个可变字体以 N 个 webfont 分片发布，走并集路径：不实例化、不做轴并集，每个分片的字形、增量与 lookup 原样保留。

```python
from glob import glob
from FontMerger import merge_subsets, verify_merge

paths = sorted(glob("webfont/ja-v2/*.woff2"))      # subsets[0] 作基底

merged = merge_subsets(paths, out_path="Merged-JP.ttf", tag="ja",
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

完整示例与参数见[同源分片和验证](doc/zh-CN/subsets-and-verification.md)。运行 ZIP 包含 `doc/`，不含仅用于源码仓库的 `tests/` 和 `build/`。

## 已知限制

1. **CID CFF2 作主字体**：合并本身成功，但保存阶段打底拉丁字形在 cmap format 4 的引用偶发不完整；矩阵生成器降级走静态实例化路径。如需真·可变输出，需攻克 CFF2 CID 注入的更深层命名空间问题

2. **跨设计空间的字形增量**：已知以下 4 个限制：

- (a) 要求主/打底的可变数据在**同一种轮廓技术**里

- (b) 合并后的 `avar` 是主字体的，若主轴把某段用户区间压成归一化空间的一个点（`collapsing_flats()`），打底在该区间的增量在 OT 模型下无法逐点还原，检测到会告警并保留主字体行为

- (c) 打底的布局变化数据也会搬入，但 VariationIndex 的增量是整数，重参数化后的列要取整，所以 kerning/anchor 变化可能有至多约 1 单位的偏差

- (d) 主字体自己的 varStore 只在轴空间真的变化时（`compose_range="union"`/`"main"` 或 `avar_mode != 0`）才重参数化，此时默认点的那一项由"恒定 region"（全轴峰值 0）承载

3. **OpenType 特性**：追加的打底 feature 所引用字形必须存在于合并字体（否则跳过该 lookup）。同 tag feature 仅在同一 Script/LangSys 内并集，不跨脚本串用

4. **VORG**：默认轴位置实例化时数值正确；非默认位置需额外重算

5. **多级 OT 特性**：上级已并入的 feature 会在下级被重复检测（幂等，但 lookup 可能冗余）

6. **打包**：仓库根目录即包本身，`pip install` 尚未接线，目前 clone 即用；PyPI 化目录结构在规划中

7. **`merge_subsets()` 的 CFF2 边界**：glyf 与 CFF2 分片都支持，但 CFF2 要求各分片共享同一 **VarStore / GlobalSubrs** 结构（pyftsubset 会原样保留）；FDArray 的差异由 FD 级并集处理

8. **自动名字形一律加别名**：post 3.0 的序号名（`glyphNNNNN`）在分片间同名但不同源，故一律改名保留。同一无码位字形被多个分片保留时会多出一份内容相同的副本，用少量体积换取"绝不混淆两个不同字形"。

[限制说明](doc/zh-CN/limitations.md)区分未支持场景、主动降级与验证范围。

## 协议

[MIT License](LICENSE)

Copyright (c) 2026 cHAnGe