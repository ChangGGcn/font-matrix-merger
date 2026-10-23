# Changelog

All notable changes to **font-matrix-merger** are documented in this file.
本文件记录 **font-matrix-merger** 的全部重要变更。

- Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)；格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)。
- Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)；版本号遵循[语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。
- **Bilingual convention / 双语约定**：每次更新都用中英双语写 —— 同一条目先 `### English` 后 `### 简体中文`，结构与细节保持一致（同一个 `## [版本]` 段落内）。

## [Unreleased]

### English

### 简体中文

## [0.2.1] — 2026-10-24

### English

#### Added
- Public technical documentation under `doc/en/` and `doc/zh-CN/`, with usage, complete API parameters, variation/subset models, architecture, script reference and support boundaries. Both languages are included in the runtime ZIP.
- An explicit `--preview` ZIP option includes untracked public Markdown for review without staging or publishing; preview filenames end in `-review.zip`.

#### Changed
- Version **0.2.1**, published as a normal GitHub release. The runtime ZIP now includes the bilingual technical manual alongside the library, CLI and root documentation.
- Shorten the English README to follow the author-edited Chinese version. Move detailed material into topic pages, correct dependency/import examples and replace unsupported guarantees with source-backed support conditions.
- Rename private engineering documents from `docs/` to `devdocs/`. Keep that directory, root AGENTS and `README.zh-CN.md.backup` out of Git and release archives.

#### Validation
- The local v0.2.1 regression run passes 157/157 cases with 0 skips. The 20-file bilingual manual has no missing local links; 38 Python examples pass syntax checks, and both README workflows run from the extracted review ZIP using synthetic fonts. Runtime code is unchanged except for the version string.

### 简体中文

#### 新增
- 在 `doc/en/` 与 `doc/zh-CN/` 新增公开技术文档，涵盖使用方法、完整 API 参数、可变/分片模型、架构、脚本参考及支持边界。两种语言均随运行 ZIP 发布。
- 增加显式 `--preview` 审核选项，无需暂存或发布即可收录未跟踪的公开 Markdown，预览包名以 `-review.zip` 结尾。

#### 变更
- 版本 **0.2.1**，作为 GitHub 正式版本发布。运行 ZIP 在库、CLI 与根文档之外收录双语技术手册。
- 以作者修改的中文版本为参照精简英文 README，将详细内容迁至分主题文档，修正依赖/导入示例，并把缺乏支持的保证改为源码可核实的条件说明。
- 私有工程文档从 `docs/` 迁至 `devdocs/`，继续排除该目录、根 AGENTS 和 `README.zh-CN.md.backup`，不提交、不打包。

#### 验证
- 本地 v0.2.1 回归 157/157 通过，0 跳过；20 份双语手册无缺失本地链接，38 个 Python 示例通过语法检查，两版 README 的流程均使用合成字体从解压审核包执行通过。运行库仅更新版本字符串。

## [0.2.0] — 2026-10-24

> GitHub pre-release / GitHub 预发布

### English

#### Added
- Mandatory heterogeneous-merge exit checks for Unicode/UVS union, main-map priority, glyph/metric references and nested layout indices.
- `tests/run_regressions.py` runs the original four suites and synthetic regressions with explicit skip counts and preserved temporary logs; `--engines` adds optional tests against existing HarfBuzz/FreeType system libraries via standard-library ctypes (no package installation).
- `build/make_release_zip.py` — reproducible **source-only** release packaging: it collects the tracked Python runtime modules and CLI plus the root `README.md`, `README.zh-CN.md`, `LICENSE` and `CHANGELOG.md` into `dist/font-matrix-merger-v<version>.zip` (version read from `__init__.py`; zip timestamps pinned to the `HEAD` commit time so rebuilds are byte-identical; font binaries rejected defensively).

#### Changed
- Version **0.2.0**, published as a GitHub **pre-release**. The runtime ZIP uses an importable `FontMerger/` root and contains only the Python library/CLI, both READMEs, CHANGELOG and original LICENSE; tests, build scripts and private docs are excluded. The repository still includes its tests and development tools.
- Source-only release archives now include `CHANGELOG.md`.
- Build pipeline: `build/build_exe.py` and the PyInstaller spec were rewritten to target the in-repo entry `FontMerging.py` (the spec is now `build/font_merger.spec`), dropping the old external `../merge_fonts.py` and the afdko collection; the script gained `--check / --install / --clean` and writes to `build/dist/` + `build/build/` (both gitignored).
- Engineering docs (`docs/` and the root `AGENTS.md`) are kept **local-only**: they are listed in `.gitignore` and excluded from release archives.
- The READMEs no longer name any specific typeface (CLI sample paths and the `merge_subsets` output name are neutral placeholders), and test comments/docstrings no longer hard-code licensed font paths: every licensed font is resolved through the non-committed `tests/local_fonts.py` (the `vf_ttf_cjk` role was added to the template). Code comments now use placeholder names in examples as well.

#### Fixed
- Legacy/non-Unicode cmap format 0 tables (including Macintosh Roman) now upgrade to format 6 when merged glyph IDs exceed 255, preserving their platform, encoding, language and original mapping domain. This fixes the Windows save-time `OverflowError: unsigned byte integer is greater than maximum` without deleting legacy mappings or requiring a fontTools upgrade.
- Partial codepoint conflicts no longer discard base-only mappings; aliases, composite dependencies and default/non-default UVS keep their source identity. Unicode subtables are harmonized by format range, new wide-cmap tables support repeated TTX injection, and the XML glyph-name set is built once.
- Dual-CID merges preserve decoded cmap/UVS references, FDArray/FDSelect and per-source Private dictionaries instead of flattening everything onto the first FD.
- Contextual GSUB/GPOS nested lookup references use a complete old-to-new map and dependency closure; same-tag features are combined within each Script/LangSys, with required-feature/parameter/variation safeguards and correctly paired Coverage arrays.
- Merge finalization recalculates OS/2 statistics, bounds and metrics without replaying the independent table registry. Invalid signatures/device caches are explicitly dropped; compatible hinting bundles and maxp interpreter resources stay together, while unsafe new glyph programs are stripped with warnings.
- Localized family/copyright records are retained; full, typographic, unique and PostScript names are synchronized without changing source versions, public list/string contracts or attribution records.
- Scale/offset transforms distinguish vertical positions from lengths, synchronize vmtx/VORG and preserve glyf/gvar/CFF2 variation structure. Non-identity transforms explicitly dehint rather than restoring unsafe bytecode. UPM normalization fixes omitted VORG overrides without double-scaling other metrics; CFF-to-glyf builds maxp 1.0 and rejects unsupported variable-outline conversion.
- `create_glyph_subset()` now uses the official Subsetter to synchronize component/layout closure and retain selected encoded empty glyphs, explicitly warning about dropped unsupported/cache/signature tables and ignored missing requests. Ordinary/chunked injection failure raises instead of returning an apparently successful partial font; composition retains its existing fallback. The variable-outline regression now compares decomposed geometry exactly instead of component-name labels, retaining all six original assertions and adding a wrong-component negative control.
- Documentation and test comments no longer mislabel a commercially licensed third-party test font as an OFL Google Font, and the composition example uses neutral placeholder file names instead of naming licensed fonts.
- Documentation accuracy pass: the pipeline bullet now says CFF/CFF2/CID injection uses the TTX roundtrip while `glyf` merges take the object-level fast path; the stale "master-level composition not implemented" note is replaced by the v0.1.1 behaviour; the merge matrix now explains that the TTF/OTF question is recorded but the output format follows the main font; `tables/varstore.py`'s docstring now states that a `VariationIndex` inner index is a **row** (not a region). Also removed the last PEP 701 f-string (Python 3.8 compatibility) and corrected `FontMerging.py`'s usage text (there is no command-line mode).

#### Tests
- Original suites: 46/46; new synthetic regressions: 105/105; optional real-engine tests: 6/6. Final unified run: **157/157 passed, 0 skipped**. Windows Python 3.10.11 / fontTools 4.61.0 also passes the 21 cmap cases and the reported complete CLI save/reload scenario. Existing variation-test assertions are unchanged; Python 3.8 AST checks and diff whitespace checks pass (no Python 3.8 runtime or Windows rasterizer claim).

### 简体中文

#### 新增
- 为异源合并成功出口增加强制检查：Unicode/UVS 并集、主映射优先、字形/度量引用及布局内部索引。
- `tests/run_regressions.py` 统一原四套和合成回归，单列 SKIP 并保留完整临时日志；`--engines` 用标准库 ctypes 对照现有系统 HarfBuzz/FreeType，不安装依赖。
- `build/make_release_zip.py` —— 可复现的**仅源码**发布打包：把已跟踪的 Python 运行库和 CLI 与根目录 `README.md`、`README.zh-CN.md`、`LICENSE`、`CHANGELOG.md` 收进 `dist/font-matrix-merger-v<版本>.zip`（版本号取自 `__init__.py`；zip 内时间戳固定为 `HEAD` 提交时间，重复打包字节一致；并防御性拒绝字体二进制）。

#### 变更
- 版本 **0.2.0**，GitHub 标记为 **pre-release**。运行 ZIP 使用可导入的 `FontMerger/` 根目录，只收 Python 库/CLI、两版 README、CHANGELOG 和原 LICENSE；排除测试、构建脚本及私有文档。仓库仍保留测试与开发工具。
- 仅源码发布包开始包含 `CHANGELOG.md`。
- 构建管线：重写 `build/build_exe.py` 与 PyInstaller spec，指向仓库内入口 `FontMerging.py`（spec 更名为 `build/font_merger.spec`），去掉旧的仓库外 `../merge_fonts.py` 与 afdko 收集；脚本新增 `--check / --install / --clean`，产物输出到 `build/dist/` 与 `build/build/`（均已 gitignore）。
- 工程文档（`docs/` 与根 `AGENTS.md`）改为**仅本地**：加入 `.gitignore`，不随仓库/发布包分发。
- 两个 README 不再出现任何具体字体名（CLI 样例路径与 `merge_subsets` 输出名改为中性占位）；测试注释/docstring 不再硬编码授权字体路径——所有授权字体统一经不入库的 `tests/local_fonts.py` 解析（模板新增 `vf_ttf_cjk` 角色）；代码注释中的示例名也改为占位符。

#### 修复
- 旧编码/非 Unicode 的 cmap format 0（含 Macintosh Roman）在合并后字形编号超过 255 时升级为 format 6，保留平台、编码、语言和原编码域，修复 Windows 保存时的 `OverflowError: unsigned byte integer is greater than maximum`；不删除旧映射，也无需升级 fontTools。
- 部分码位冲突不再丢掉打底独有码位；别名、组件依赖及默认/非默认 UVS 保留来源身份。Unicode 子表按格式范围同步，新宽码位子表支持多次 TTX 注入，XML 字形名集合仅构造一次。
- 双 CID 合并同步已解码 cmap/UVS，保留 FDArray/FDSelect 与各来源 Private 字典，不再压平到首个 FD。
- 上下文 GSUB/GPOS 内部 lookup 使用完整旧→新映射和依赖闭包；同 tag 特性只在同一 Script/LangSys 内并集，保留必需特性/参数/变化语义，并同步 Coverage 的并行数组。
- 合并收尾重算 OS/2 统计、包围盒和度量，不重放独立表注册表。明确删除失效签名/设备缓存；兼容 hinting 程序与 maxp 资源成套保留，不安全的新增字形指令剥离并告警。
- 保留各语言族名/版权；同步全名、排印名、唯一标记与 PostScript 名，不擅改来源版本、公共 list/string 契约或归属记录。
- 缩放/偏移区分纵向位置与长度，同步 vmtx/VORG，保留 glyf/gvar/CFF2 可变结构；非恒等变换明确去 hint，不盲目恢复旧字节码。UPM 归一修正遗漏的 VORG override 且不重复缩度量；CFF→glyf 重建 maxp 1.0，拒绝未支持的跨轮廓可变转换。
- `create_glyph_subset()` 改用官方 Subsetter 同步组件/布局闭包，保留已选编码空字形；删除不支持表/缓存/签名或忽略缺失请求均明确告警。普通/分块注入失败抛错，不再返回貌似成功的部分字体；合成仍保留原有回退。可变轮廓回归改为严格比较分解几何而非组件名字，保留全部六条原断言，并补错误组件负对照。
- 文档与测试注释不再把某个商业授权的第三方测试字体误标为 OFL / Google Fonts；合成示例改用中性占位文件名，不再点名授权字体。
- 文档准确性修正：管线条目改为“CFF/CFF2/CID 走 TTX 往返、`glyf` 合并走对象级快路径”；删掉过时的“master-level composition 未实现”表述（v0.1.1 已实现）；合并矩阵下方补充说明“TTF/OTF 询问仅记录，输出格式由主字体决定”；`tables/varstore.py` docstring 更正为 `VariationIndex` 的 inner 是**行号**（不是 region）。同时移除最后一处 PEP 701 f-string（恢复 Python 3.8 兼容），并修正 `FontMerging.py` 的用法说明（不存在命令行模式）。

#### 测试
- 原套件 46/46；新增合成回归 105/105；可选真实引擎测试 6/6。最终统一运行 **157/157 通过，0 跳过**；Windows Python 3.10.11 / fontTools 4.61.0 另通过 21 条 cmap 回归与用户原始 CLI 保存重载场景；原可变轮廓断言不变，Python 3.8 AST 与 diff 空白检查通过（不冒称已在 Python 3.8 解释器或 Windows 栅格器实跑）。

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

[Unreleased]: https://github.com/ChangGGcn/font-matrix-merger/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/ChangGGcn/font-matrix-merger/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/ChangGGcn/font-matrix-merger/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/ChangGGcn/font-matrix-merger/compare/v0.1.0-alpha1...v0.1.1
[0.1.0-alpha1]: https://github.com/ChangGGcn/font-matrix-merger/releases/tag/v0.1.0-alpha1
