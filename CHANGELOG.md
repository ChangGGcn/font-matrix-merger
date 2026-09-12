# Changelog

All notable changes to **font-matrix-merger** are documented in this file.
本文件记录 **font-matrix-merger** 的全部重要变更。

- Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)；格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)。
- Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)；版本号遵循[语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。
- **Bilingual convention / 双语约定**：每次更新都用中英双语写 —— 同一条目先 `### English` 后 `### 简体中文`，结构与细节保持一致（同一个 `## [版本]` 段落内）。

## [Unreleased]

### English

#### Added
- `build/make_release_zip.py` — reproducible **source-only** release packaging: it collects the tracked `*.py` files plus `README.md`, `README.zh-CN.md`, `LICENSE` and `CHANGELOG.md` into `dist/font-matrix-merger-v<version>.zip` (version read from `__init__.py`; zip timestamps pinned to the `HEAD` commit time so rebuilds are byte-identical; font binaries rejected defensively).

#### Changed
- Source-only release archives now include `CHANGELOG.md`.

### 简体中文

#### 新增
- `build/make_release_zip.py` —— 可复现的**仅源码**发布打包：把已跟踪的 `*.py` 与 `README.md`、`README.zh-CN.md`、`LICENSE`、`CHANGELOG.md` 收进 `dist/font-matrix-merger-v<版本>.zip`（版本号取自 `__init__.py`；zip 内时间戳固定为 `HEAD` 提交时间，重复打包字节一致；并防御性拒绝字体二进制）。

#### 变更
- 仅源码发布包开始包含 `CHANGELOG.md`。

<!-- 新条目请按上方双语结构追加 / append new entries in the same bilingual structure -->

## [0.1.1] — 2026-09-12

### English

#### Added
- **Cross-design-space composition** (stages 0–4): the base font's variation data is now *composed* into the merged font instead of being frozen at the base's default instance.
  - `format/axis_mapping.py` — three-layer normalization (user → pre-avar → post-avar), `avar` composition, exact hat decomposition and re-basing (the missing default master is interpolated through phantom points).
  - `format/variation_compose.py` — glyf/`gvar` deltas re-parameterized into the merged normalized space (base-only axes, different axis ranges and different `avar` maps included), plus re-parameterization of the main font's own `ItemVariationStore`.
  - `format/cff2_compose.py` — CFF2 `blend`/`vsindex` rewriting, `VarStore` union and `HVAR` re-attachment by glyph name (CFF2×CFF2 merges).
  - Layout variation transfer — the base's `GDEF` `ItemVariationStore` and `GPOS` `VariationIndex` devices are re-parameterized and merged; rows are preserved, so no reference needs rewriting.
- `verify_composition()` — grid self-check that compares rendered outlines/metrics glyph by glyph, with a transparent fallback to the legacy "instance the base at its default" behaviour when it fails.
- `FontMerger` policy parameters: `compose_variations`, `compose_range` (`"main+extra"` default; `"union"`/`"main"` advanced), `compose_fit` (`"exact"` default; `"affine"` advanced), `avar_mode` (0/1/2), `verify_compose`, `compose_layout`.
- `merge_subsets()` — rebuild one variable font from the per-`unicode-range` webfont subsets of a single VF (glyf **and** CFF2), keeping `gvar`/blends, `hmtx`/`vmtx`, `cmap`, layout lookups, GDEF `ItemVariationStore`/`MarkGlyphSetsDef` and `HVAR`/`VVAR`; `verify_merge()` self-check plus a per-subset source → merged GID map.
- CFF2 subset union; `MarkGlyphSetsDef` / `FeatureVariations` union preservation.
- New tests: `tests/test_axis_mapping.py`, `tests/test_cff2_compose.py`, `tests/test_subset_merge.py`, `tests/cff2_fixture.py`.

#### Changed
- A variable base whose axis space already matches keeps its `gvar` deltas (previously the base was always instanced to a static font).
- `.gitignore` now rejects font binaries (`*.ttf`, `*.otf`, `*.ttc`, `*.otc`, `*.woff`, `*.woff2`, `*.eot`, `*.dfont`, `*.pfb`, `*.pfa`, `*.pfr`, `*.bdf`, `*.pcf`) and `*.ttx` intermediates; the repository ships source only.
- `.gitattributes` — LF normalization for all text files.
- README (English + 简体中文) documents the composition parameters and the revised known limitations.
- Version `0.1.0-alpha1` → `0.1.1`.

#### Fixed
- A hat that straddles the normalized default (`lower < 0 < upper`) is ignored by the OT engine; `refine_1d()` now keeps `0` as a node so decomposition never emits one (0.625-unit deviation before the fix).
- `RegionAxisCount` no longer mismatches the merged `fvar` axis count (invalid font), and the main font's own var stores are re-parameterized instead of being reinterpreted in the wrong normalized space.
- `_extend_avar_axes()` wrote `table.AxisSegmentMap`, which `table__a_v_a_r.compile()` ignores — saving a font with a newly added axis raised `KeyError: '<axis tag>'`.
- `verify_composition()` compares `getGlyphSet()` render semantics; `instantiateVariableFont()`'s user limits do not apply `avar`, which produced false positives (1.58 units measured).
- `offset_var_devices()` skips `NO_VARIATION_INDEX` (0xFFFF/0xFFFF) devices; `_check_var_stores()` validates `RegionAxisCount`, `VarRegionIndex` and `VariationIndex` bounds.
- Generic merge path: same-tag features are **unioned** instead of skipped, no dangling layout references, glyph names survive the post-3.0 TTX roundtrip, new glyphs get `vmtx` defaults, and UPM is normalized before composition.

#### Tests
`test_merger` 21 + `test_axis_mapping` 13 + `test_subset_merge` 8 + `test_cff2_compose` 4 = **46 passing**. Test fonts are not distributed; suites skip when a font is missing.

### 简体中文

#### 新增
- **跨设计空间合成**（阶段 0–4）：打底字体的可变数据不再被冻结在默认实例，而是**合成进合并字体**。
  - `format/axis_mapping.py` —— 三层归一化（user → pre-avar → post-avar）、`avar` 复合、hat 精确分解与重定基（缺的默认 master 由幽灵点插值补出）。
  - `format/variation_compose.py` —— glyf/`gvar` 增量重参数化到合并归一化空间（支持打底独有轴、不同轴范围与不同 `avar`），并同步重算主字体自己的 `ItemVariationStore`。
  - `format/cff2_compose.py` —— CFF2 `blend`/`vsindex` 重写、`VarStore` 并集、按字形名重接 `HVAR`（CFF2×CFF2 合并）。
  - 布局变化数据搬运 —— 打底的 `GDEF` `ItemVariationStore` 与 `GPOS` `VariationIndex` 设备重参数化后并入；**行保持**，因此引用无需重写。
- `verify_composition()` —— 网格自检：逐字形比对渲染后的轮廓/度量，不通过则透明回退到旧的“打底按默认实例化”行为。
- `FontMerger` 策略参数：`compose_variations`、`compose_range`（默认 `"main+extra"`，`"union"`/`"main"` 为高级参数）、`compose_fit`（默认 `"exact"`，`"affine"` 为高级参数）、`avar_mode`（0/1/2）、`verify_compose`、`compose_layout`。
- `merge_subsets()` —— 把同一可变字体按 `unicode-range` 切出的 webfont 分片并回**一个**可变字体（**glyf 与 CFF2**），保留 `gvar`/blend、`hmtx`/`vmtx`、`cmap`、布局 lookup、GDEF `ItemVariationStore`/`MarkGlyphSetsDef`、`HVAR`/`VVAR`；配套 `verify_merge()` 自检与“源字形 → 合并后 GID”映射。
- CFF2 分片并集；`MarkGlyphSetsDef` / `FeatureVariations` 并集保留。
- 新增测试：`tests/test_axis_mapping.py`、`tests/test_cff2_compose.py`、`tests/test_subset_merge.py`、`tests/cff2_fixture.py`。

#### 变更
- 轴空间本就一致的打底会保留 `gvar` 增量（此前打底一律被实例化成静态字体）。
- `.gitignore` 拦截字体二进制（`*.ttf`、`*.otf`、`*.ttc`、`*.otc`、`*.woff`、`*.woff2`、`*.eot`、`*.dfont`、`*.pfb`、`*.pfa`、`*.pfr`、`*.bdf`、`*.pcf`）与 `*.ttx` 中间产物；仓库只发布源码。
- `.gitattributes` —— 文本文件统一 LF。
- README（English + 简体中文）补充合成参数与修订后的已知限制。
- 版本号 `0.1.0-alpha1` → `0.1.1`。

#### 修复
- 跨越归一化默认点的 hat（`lower < 0 < upper`）会被 OT 引擎整条忽略；`refine_1d()` 现在保留 `0` 作为节点，分解不再产生这类 hat（修复前实测偏差 0.625）。
- 新轴并入后 `RegionAxisCount` 与 fvar 轴数不一致（非法字体）的问题；主字体自己的 varStore 改为重参数化，而不是在错误的归一化空间里被解释。
- `_extend_avar_axes()` 写的是 `table.AxisSegmentMap`，而 `table__a_v_a_r.compile()` 并不读它 —— 曾导致新增轴保存时 `KeyError: '<轴 tag>'`。
- `verify_composition()` 改用 `getGlyphSet()` 渲染语义比对：`instantiateVariableFont()` 的 user limits 不套 `avar`，会产生假阳性（实测 1.58 单位）。
- `offset_var_devices()` 跳过 `NO_VARIATION_INDEX`（0xFFFF/0xFFFF）设备；`_check_var_stores()` 校验 `RegionAxisCount`、`VarRegionIndex` 与 `VariationIndex` 越界。
- 通用路径：同 tag feature 改为 **lookup 并集**（不再整条跳过）、消除悬空布局引用、post-3.0 TTX 往返后字形名不丢、新增字形补 `vmtx` 默认值、合成前先做 UPM 归一。

#### 测试
`test_merger` 21 + `test_axis_mapping` 13 + `test_subset_merge` 8 + `test_cff2_compose` 4 = **46 全通过**。测试字体不随仓库分发，缺字体时自动 SKIP。

## [0.1.0-alpha1] — 2026-08-30

### English

#### Added
- 16-way merge matrix (`merge_two()` auto-dispatches for every static/variable × OTF/TTF main/base combination), the one-line `merge_fonts()` helper, and multi-level chained merges.
- Format conversion: CFF↔glyf (cubic↔quadratic), CFF2↔CFF, UPM scaling and baseline offsets.
- CID-keyed CFF support: dual-CID offset merge with materialized CharStrings, CID↔name-keyed normalization, cmap format 14 UVS.
- OpenType merging: base GSUB/GPOS/GDEF pruned with the `fontTools.subset` closure and appended with lookup-index + deep glyph-name remapping; conflicts resolve in favor of the main font.
- Variable fonts: axis union (fvar/avar/STAT kept in sync, varStore regions extended); a variable main font stays variable.
- Interactive CLI (`FontMerging.py`, answer memorization), conflict resolution/aliasing, naming and metadata merge, `save_font()` save guard.
- Bilingual documentation (English + 简体中文), PyInstaller build pipeline (`build/`), unit tests and the 16-combination matrix generator.
- MIT license; test fonts are OFL or local-only and are never distributed.

### 简体中文

#### 新增
- 16 路合并矩阵（`merge_two()` 对 静态/可变 × OTF/TTF 的主/打底组合自动分派）、一行快捷函数 `merge_fonts()`、多级链式合并。
- 格式转换：CFF↔glyf（三次↔二次曲线）、CFF2↔CFF、UPM 缩放与基线偏移。
- CID-keyed CFF 支持：双 CID 偏移合并 + CharString 物化复制、CID↔name-keyed 归一、cmap format 14 UVS。
- OpenType 合并：打底 GSUB/GPOS/GDEF 经 `fontTools.subset` 闭包修剪后追加，带 lookup 索引与字形名深度重映射；冲突以主字体为准。
- 可变字体：Axis 并集（fvar/avar/STAT 同步、varStore Region 扩展）；可变主字体输出仍保持可变。
- 交互式 CLI（`FontMerging.py`，答案记忆）、冲突处理/别名、命名与元数据合并、`save_font()` 保存防护。
- 双语文档（English + 简体中文）、PyInstaller 构建管线（`build/`）、单元测试与 16 组合矩阵生成器。
- MIT 协议；测试字体为 OFL 或仅本地存在，绝不随仓库分发。

[Unreleased]: https://github.com/ChangGGcn/font-matrix-merger/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/ChangGGcn/font-matrix-merger/compare/v0.1.0-alpha1...v0.1.1
[0.1.0-alpha1]: https://github.com/ChangGGcn/font-matrix-merger/releases/tag/v0.1.0-alpha1
