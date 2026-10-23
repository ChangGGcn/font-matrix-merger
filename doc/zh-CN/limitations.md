# 支持边界与故障排查

本文对应 **v0.2.1**。默认值、容差与行为以源码为准。本轮验证和历史测量在下文分开记录。
引用源码时使用仓库相对链接。运行 ZIP 含本文档和运行库，不含 `tests/`、`build/`；本文提到这些目录时只写代码路径并标注“仅仓库”，不生成相对链接。

相关文档：[安装与使用](usage.md)、[合并 API](merge-api.md)、[架构](architecture.md)、[轴映射与可变数据合成](variation-model.md)、[同源分片与验证](subsets-and-verification.md)、[模块与脚本参考](script-reference.md)。

## 1. 支持条件

### 1.1 输入与运行环境

- 输入容器：静态 TTF（glyf）、静态 OTF（CFF）、可变 TTF（gvar）、可变 OTF（CFF2），以及 WOFF/WOFF2。WOFF/WOFF2 由 `load_font()` 解开并清 `flavor`。
- TTC/OTC 不在 CLI 支持范围，需要先解包。CLI 只接受 `.ttf`、`.otf`、`.woff`、`.woff2`（`SUPPORTED_EXTS`）；集合扩展名（`COLLECTION_EXTS`）会提示先解包。
- 声明基线为 Python ≥ 3.8、fontTools ≥ 4.49。Python 3.8 只做过语法层面的 AST 检查，没有在 3.8 解释器上实际运行。历史 v0.2.0 原生 Windows 验证使用 Python 3.10.11 与 fontTools 4.61.0。
- WOFF 读取/写入使用标准 zlib，不需要 `brotli`；只有 WOFF2 读取/写入需要可选的 `brotli`，缺失时 WOFF2 相关功能不可用。
- 当前没有 `pyproject.toml` 或 `setup.py`，不能 `pip install`。仓库根目录本身是 `FontMerger` 包，导入时父目录必须在 `sys.path`；运行 ZIP 使用可导入的 `FontMerger/` 根目录。
- CLI 是纯交互模式，不接受位置参数；脚本化请使用库 API。
- 运行 ZIP 不包含 `tests/` 与 `build/`。本文只用代码路径提到这些目录，不生成相对链接，避免离线 ZIP 内出现悬空链接。

### 1.2 合并组合与策略条件

- 异源合并覆盖主/打底“静态或可变”与“glyf 或 CFF/CFF2”的 4×4 组合。输出轮廓格式由主字体决定；TTF/OTF 导出询问仅记录，不改变结果。
- 静态主字体与可变打底：打底按默认实例合并，新增字形不随轴变化。
- 可变主字体与静态打底：用户选择可变输出时主 VF 保持原轴空间；选择静态则先实例化主字体。打底字形静态，不新增轴。
- 可变主与可变打底的跨设计空间合成要求两边是同一种轮廓技术，并且有对应变化数据：glyf 需要 `gvar`，CFF2 需要带 VarStore 的 CFF2。合成必须通过 `verify_composition()` 抽样自检，失败回退旧路径。
- 同源分片并集：1 个分片时作为基底处理；2 个及以上要求全部分片可变，`fvar` 轴集合与 min/default/max 完全一致，轮廓技术一致。CFF/CFF2 分支要求分片是 CFF2，纯 CFF1 分片会被拒绝。CFF2 还要求分片共享同一 VarStore 与 GlobalSubrs 结构；FDArray 差异可由 FD 级并集处理。
- 同源分片的 FeatureVariations 要求条件集合与顺序严格一致；不一致时抛 `ValueError`，不做有损拼接。
- CID 处理按组合分支进行。静态双 CID 合并保留 CID 名字空间、FDArray/FDSelect 与各来源 Private，不再压平到首个 FD；`cid_to_name()` 只用于 name-keyed 归一分支。
- 输入所有权：`merge_two()` 的旧轴并集回退路径会就地修改主字体；`merge_subsets()` 修改 `subsets[0]`；`scale_font()`/`apply_scale_offset()` 就地缩放/偏移并返回同一 `TTFont`，`scale=1` 且 `baseline_offset=0` 时原样返回，参数非法或字体含 VARC 时抛 `ValueError`；`union_axes()`、`rename_glyphs()`、`apply_naming()` 就地修改。需要保留输入时由调用方 `deepcopy`；`merge_fonts()` 会先深拷贝主字体。

## 2. 已知不支持或明确拒绝

以下边界是当前实现的有意选择，不应被文档或调用方描述为“已支持”。

1. **打包与 CI**：没有 pip 安装、没有 `pyproject.toml`、没有 CI。导入依赖包目录名与父目录 `sys.path`。见 [`__init__.py`](../../__init__.py) 与 [`FontMerging.py`](../../FontMerging.py)。
2. **CLI 位置参数**：`FontMerging.py` 只运行交互流程；没有命令行参数解析。见 [`FontMerging.py`](../../FontMerging.py)。
3. **集合字体**：TTC/OTC 需要先解包。扩展名集合见 [`__init__.py`](../../__init__.py)。
4. **跨轮廓可变数据合成**：glyf 主与 CFF2 打底、CFF2 主与 glyf 打底不支持逐点合成。失败时回退轴并集与打底默认实例化，打底字形可能失去轴变化。见 [`core/merger.py`](../../core/merger.py) 的 `_do_merge()` 与 [`format/variation_compose.py`](../../format/variation_compose.py)。
5. **CFF2 打底的 VVAR 与 Private hint 变化**：当前只按字形名并入打底 HVAR；VVAR 与 Private hint 的 blend 保持静态，hint 的 blend 会折成默认值。见 [`format/cff2_compose.py`](../../format/cff2_compose.py) 的 `merge_cff2_hvar()` 与 `offset_cff2_vsindex()`。
6. **异源路径的打底 FeatureVariations**：主对应表不存在或为空（无 lookup 与 feature）时，才可能整体采用合法的打底表（含 FV）；否则不跨来源拼接打底 FV，保留主条件。打底 FV 引用失效 lookup 或 feature 时拒绝该表合并。见 [`tables/ot_merge.py`](../../tables/ot_merge.py) 的 `merge_base_layout()`。
7. **同源分片 FV 条件不一致**：条件集合或顺序不同直接拒绝，不尝试重排或有损合并。CFF 与 CFF2 混合分片不支持；CFF2 VarStore 被逐片重建或重编号的输入会抛 `IncompatibleCFF2Error`。见 [`tables/layout_union.py`](../../tables/layout_union.py) 的 `LayoutUnion.add_from()` 与 [`format/cff2_union.py`](../../format/cff2_union.py) 的 `check_cff2_compatible()`。
8. **CID-keyed CFF2 作主字体的真·可变输出**：矩阵生成器（仅仓库的 `tests/generate_matrix.py`，代码路径，不生成链接）对 C1/D1 仍走静态实例化路径，保存阶段打底拉丁字形在 cmap format 4 的引用问题仍未解决。这与静态双 CID 合并是两个问题；静态 CID/CFF 合并由 [`format/cid_merge.py`](../../format/cid_merge.py) 的 `cid_ufo_style_merge()` 保留 CID 与 FD 结构，并有保存重载回归。
9. **未知 kern 格式**：旧式 `kern` 表只合并标准版本 0、子表 format 0、coverage 1 的水平字对。其它版本或格式跳过并告警；主表优先。异源 GPOS 不做通用跨来源码位统一，避免同一字对被定位两次。见 [`core/table_policy.py`](../../core/table_policy.py) 的 `_union_kern()` 与 [`tables/ot_merge.py`](../../tables/ot_merge.py) 的 `_merge_gsub_gpos()`。
10. **VORG 非默认轴位置**：默认轴位置实例化时数值正确；非默认位置需要额外重算。缺少 `vmtx` 等无法恢复原点的字形时，保留主 VORG 而不套用打底默认值。见 [`core/table_policy.py`](../../core/table_policy.py) 的 `_union_vorg()` 与 [`format/static_extract.py`](../../format/static_extract.py) 的 `variable_to_static()`。
11. **渲染与排版等价**：验证使用 fontTools 的 `getGlyphSet()` 与 RecordingPen 比较轮廓和度量，不等于 HarfBuzz 排版结果或 FreeType/Windows 栅格结果。可选的系统引擎测试只覆盖少量合成场景，不是完整引擎矩阵。见 [`core/verify.py`](../../core/verify.py) 的 `verify_merge()` 与 `verify_composition()`。
12. **验证范围**：`verify_merge()` 与 `verify_composition()` 使用抽样字体与抽样轴位置；不是所有轴位置、所有文本片段、所有特性的逐点证明。采样参数见 [`core/verify.py`](../../core/verify.py) 的 `grid_positions()` 与 `_auto_positions()`。
13. **Python 3.8 运行时**：只有语法检查，没有 3.8 解释器实跑。声明的运行基线不等于跨版本实测保证。历史检查记录见 [`CHANGELOG.md`](../../CHANGELOG.md)。
14. **`save_font(..., recalcTimestamp=非 None)` 的接口边界**：当前 [`utils/save.py`](../../utils/save.py) 的 `save_font()` 会把 `recalcTimestamp` 交给 `TTFont.save()`，但当前 fontTools 的 `TTFont.save()` 签名只接受 `file` 与 `reorderTables`，不接受该关键字；传入非 `None` 值会抛 `TypeError`。请保持 `recalcTimestamp=None`；本轮不修改运行代码。

已修复的历史问题（不属于未支持清单）：format 0 溢出。当前 [`core/glyph_copy.py`](../../core/glyph_copy.py) 的 `_copy_cmap_mappings()` 会在实际 GID 超过 255 时把 format 0 升级为 format 6，保留原映射；旧 `OverflowError` 是历史问题，不是当前未修限制。

## 3. 降级与信息损失

以下路径会继续产出字体，但行为有损失或降级，日志会给出对应标签。

| 场景 | 行为与日志 | 影响 |
| --- | --- | --- |
| 跨设计空间合成失败（[`core/merger.py`](../../core/merger.py) `_do_merge`） | 打印 `[合成] 回退到默认实例合并: <原因>`，走旧路径 | 打底字形停在默认实例；仅 glyf 打底且轴空间与 avar 完全一致时可能执行 1:1 gvar 搬运，CFF2 打底没有该路径 |
| 打底布局变化未搬运（[`format/variation_compose.py`](../../format/variation_compose.py) `transfer_base_layout`） | 打印 `[合成] 打底布局变化数据未并入 (保留默认实例)` 或 `[OT合并] 跳过...` | 打底 kerning/anchor 变化冻结在默认点 |
| `compose_layout=False` | 不搬运 GDEF ItemVariationStore 与 GPOS VariationIndex | 布局变化不随轴变化 |
| CFF2 打底 VVAR / Private hint（[`format/cff2_compose.py`](../../format/cff2_compose.py)） | 只并入 HVAR；hint blend 折默认值 | 纵向变化与 Private hint 变化丢失 |
| hinting 环境不兼容（[`core/hinting_policy.py`](../../core/hinting_policy.py)） | 打印 `[指令警告] ... 剥离 N 个新增字形的指令` | 新增字形失去 small-size hinting；主字体程序保留 |
| 非恒等缩放/基线偏移或 UPM 变化（[`format/transform.py`](../../format/transform.py) `_remove_hinting`） | `_remove_hinting()` 删除字形指令、全局程序与像素缓存表（cvt/cvar/fpgm/prep/gasp/hdmx/LTSH/VDMX/DSIG） | 小字号 hinting 与像素缓存行为消失，轮廓与度量按设计单位变换 |
| Win 度量扩大（[`tables/metadata_recalc.py`](../../tables/metadata_recalc.py) `_recalc_bounds`） | 打印 `[元数据] Win 度量扩大为 ...` | 覆盖全部默认轮廓，行高可能增大 |
| kern 格式未知或非标准（[`core/table_policy.py`](../../core/table_policy.py) `_union_kern`） | 打印 `[表策略警告] ...` 并跳过该来源 | 该来源的 kern 不进入合并结果 |
| VORG 原点无法恢复（[`core/table_policy.py`](../../core/table_policy.py) `_union_vorg`） | 打印 `[表策略警告] VORG 原点并集失败，保留主表...` | 不采用打底默认原点，避免错位 |
| 自动名或同名冲突（[`core/conflict.py`](../../core/conflict.py) `_plan_merge_aliases`） | 加别名后保留独立身份 | 无码位字形可能多出内容相同的副本，体积增加 |
| FeatureVariations 无法映射（[`tables/layout_union.py`](../../tables/layout_union.py)） | 同源路径抛 `ValueError`；异源路径保留主条件或跳过打底表合并 | 相关条件下不执行替换，而不是静默写出错误索引 |
| 多级异源合并（[`core/merger.py`](../../core/merger.py) `_merge_base_layout_once`） | 上级已并入的 feature 会在下级重复检测 | 幂等，但 lookup 可能冗余，体积与查找成本增加 |

## 4. 验证覆盖

### 4.1 合并自检

`verify_merge(sources, merged, ...)`（[`core/verify.py`](../../core/verify.py)）检查：

- 码位并集与多余码位；
- 源分片轴空间一致性与合并后轴空间；
- 在默认位置、首轴两端或网格位置上逐字形比较轮廓、hmtx、vmtx；
- GSUB/GPOS feature tag 是否丢失；
- 布局悬空引用、Coverage 顺序、MarkFilteringSet、FeatureVariations、lookup 与 VarStore 引用；
- GDEF 字类、mark 集合、HVAR/VVAR 映射覆盖；
- 容器 `flavor`、`head.flags`、nameID 16/17/25、实例 PostScript 名；
- 竖排变体 `vert`/`vrt2` 覆盖。

`axis_positions="auto"` 只取默认点与首轴两端；`"grid"` 取各轴 min/default/max 的组合（`max_positions` 截断）。`sample` 可以限制每分片比较的字形数。返回值 `{"ok", "failures", "checks"}`；`merge_subsets(verify=True)` 在失败时抛 `AssertionError`。

### 4.2 合成自检

`verify_composition(merged, main_font, base_font, added_glyphs, ...)`（[`core/verify.py`](../../core/verify.py)）在合并轴网格上：

- 将新增字形与打底在该位置的实例比较轮廓与字宽；
- 将主字体字形与主字体在该位置的实例比较轮廓；
- 轮廓容差默认 1 字体单位；字宽容差默认同轮廓容差，主流程调用时使用 3.0。

网格只取各轴 min/default/max（avar 不动点），比较使用 `getGlyphSet(location=...)` 的渲染语义。默认 `sample=30`（每个字形集合抽样数）、`max_positions=6`；主流程调用时 `max_positions=4`、`adv_tolerance=3.0`。它不是所有轴位置的逐点证明；失败时 `_do_merge()` 回退旧路径。

### 4.3 结构不变量

收尾强制检查：

- Unicode/UVS 精确并集与主映射优先（[`core/invariants.py`](../../core/invariants.py) 的 `assert_cmap_union()`）；
- 字形序、`.notdef`、maxp 字形数、复合组件、hmtx/vmtx 覆盖、cmap 子表同步、UVS 引用、avar 轴覆盖（[`core/invariants.py`](../../core/invariants.py) 的 `assert_font_structure()`）；
- 布局悬空引用、Coverage 顺序、mark 集合、FeatureVariations、lookup 引用、VarStore 结构（[`core/verify.py`](../../core/verify.py) 的 `_check_layout_integrity()`、`_check_lookup_references()`、`_check_var_stores()`）。

这些检查在普通、分块、空新增与 CID 出口统一执行。普通路径失败会抛异常；合成路径失败会触发回退。

### 4.4 可选系统引擎测试

`tests/run_regressions.py --engines`（仅仓库）在系统存在 `libharfbuzz.so.0` 与 `libfreetype.so.6` 时用标准库 `ctypes` 运行少量对照：上下文 lookup 错指负对照、主 kern 逐值保留、跨脚本隔离、hint bundle 与剥离后的加载。缺少系统库时明确 SKIP。该测试不安装依赖，也不代表完整 HarfBuzz/FreeType 覆盖。

## 5. 历史验证证据

以下数字来自 2026-10-24 的历史记录（[`CHANGELOG.md`](../../CHANGELOG.md) 0.2.0 与发布核验记录）。本轮只整理文档，**没有重新运行**，因此它们是历史参考，不是本轮新结果。

| 项目 | 数值 | 来源与性质 |
| --- | --- | --- |
| 统一回归 | 157/157 passed，SKIP 0，失败套件 0 | 2026-10-24 历史运行（入口代码路径 `tests/run_regressions.py`，仅仓库）；原四套 46 例 + 七套合成回归 105 例 + 可选引擎 6 例 |
| 原套件 | 13 + 21 + 8 + 4 = 46 | 历史运行 |
| 合成回归 | 21 + 14 + 17 + 24 + 12 + 12 + 5 = 105 | 历史运行；各套件单独计数 |
| Windows cmap 回归 | 21/21 | Python 3.10.11 / fontTools 4.61.0；历史发布核验记录（未随包分发） |
| Windows CLI 保存/重载 | 31,060 字形、30,012 Unicode 码位，缺失/多余/主映射差异均为 0，耗时 120.34 s | 历史发布核验记录（未随包分发）；输入与输出均未随仓库或发布包分发 |
| glyf 对象级注入 | 25k 字形主字体加 135 字形：153 s → 3.7 s | 历史发布记录与旧版 README（v0.1.1 时代）；当前 README 已精简，不是本轮测量 |
| `compose_range="union"` 元组膨胀 | 剪枝前最多约 ×28 | 历史发布记录；实际数量依字体而定 |
| `compose_fit="affine"` 偏差 | 约 6 字体单位 | 历史发布核验记录；以自检结果为准 |
| 布局整数残差 | kerning/anchor 最大约 1 单位，实测 0.70 单位（UPM 1000） | 历史发布核验记录；不是所有字体固定值 |
| 跨 0 hat 修复前偏差 | 0.625 单位 | 历史修复记录（[`CHANGELOG.md`](../../CHANGELOG.md) 0.1.1） |
| avar 假阳性 | 1.58 单位 | 历史修复记录（[`CHANGELOG.md`](../../CHANGELOG.md) 0.1.1；instancer user limits 不套 avar） |
| Python 3.8 | 语法 AST 检查通过，未在 3.8 解释器实跑 | 历史核验结论（[`CHANGELOG.md`](../../CHANGELOG.md)） |
| format 0 溢出 | 已修：GID 超过 255 时升级为 format 6；GID 255 保留 | 当前代码行为，历史 Windows 保存问题 |

SKIP 语义注意：原四套测试的 `main()` 会把正常返回的 SKIP 计入 passed；统一入口单独统计 SKIP 行。上表 157/157 是历史统一入口记录，不代表所有环境都能 0 SKIP。缺字体、缺 WOFF2 所需的 brotli、缺系统引擎库都可能产生 SKIP。

## 6. 故障排查

| 现象 | 可能原因 | 检查与处理 |
| --- | --- | --- |
| 合并后没有新增字形 | 两套字体字符集高度重叠；双 CID 名字空间冲突 | 看 `[提示] 无新增字形` 与 [`core/merger.py`](../../core/merger.py) 的 `_diagnose_empty_merge()`；调换主/打底顺序，或先把一方转 name-keyed |
| 日志出现 `[合成] 回退到默认实例合并` | 轴规划失败、实例化失败或自检失败 | 这是允许的安全回退。检查输入轮廓技术是否一致（[`format/variation_compose.py`](../../format/variation_compose.py)）与 `verify_composition()`；不要通过关闭 `verify_compose` 掩盖问题 |
| 新增字形不随轴变化 | 回退路径或静态打底 | 检查是否发生合成回退；同源分片请改用 `merge_subsets()` |
| 保存时旧格式溢出（历史） | 旧版本只升级 Unicode 子表 | 当前 [`core/glyph_copy.py`](../../core/glyph_copy.py) 的 `_copy_cmap_mappings()` 会升级所有 format 0 子表；确认使用的是本版本代码 |
| 调用 `save_font(..., recalcTimestamp=非 None)` 报 `TypeError` | 当前 fontTools 的 `TTFont.save()` 不接受该关键字 | 保持 `recalcTimestamp=None`（[`utils/save.py`](../../utils/save.py)） |
| `[指令警告] ... 剥离` | hinting 全局环境不兼容或无法证明安全 | 预期降级：新字形失去指令，主字体程序保留 |
| `[表策略警告] kern` | 旧式 kern 版本或格式未知 | 预期降级：该来源 kern 跳过，主表优先（[`core/table_policy.py`](../../core/table_policy.py)） |
| `[表策略警告] VORG` | 缺少可恢复原点的 vmtx 或数据异常 | 预期降级：保留主 VORG，不套用打底默认原点（[`core/table_policy.py`](../../core/table_policy.py)） |
| VORG 在非默认轴位置不正确 | 实例化只保证默认位置 | 需要在目标轴位置重新计算竖排原点 |
| 导入失败 `ModuleNotFoundError` | 父目录不在 `sys.path`，或包目录被改名 | 从仓库父目录导入，或把父目录加入 `PYTHONPATH`；运行 ZIP 从 `FontMerger/` 的父目录导入 |
| CLI 传入文件路径没有反应 | CLI 只读交互输入，不支持位置参数 | 运行 `python FontMerging.py` 后按提示输入，或改用库 API |
| 读取/写入 WOFF2 报 brotli 缺失 | 可选依赖未安装 | 安装 brotli，或改用 sfnt 输入输出 |
| CFF2 分片并集报结构不兼容 | 分片 VarStore 或 GlobalSubrs 被重建/重编号 | 用保持结构的工具重新切分；当前路径拒绝而不是写坏字体 |
| 同源 FV 报条件不一致 | 分片切分工具改写了条件集合或顺序 | 当前路径拒绝有损并集；重新生成顺序一致的分片 |
| `verify_merge` 报失败 | 码位、轮廓、布局或元数据不满足判据 | 查看报告 `failures`（[`core/verify.py`](../../core/verify.py)）；先用默认轴位置定位，再用 `"grid"` 扩大采样 |
| `verify_composition` 报失败 | 合成数据不可逐点等价、整数取整或平台段限制 | 见第 3 节（[`core/verify.py`](../../core/verify.py)）；可调整 `compose_range`/`compose_fit`/`avar_mode` 评估，但不要关闭生产自检 |
| 字体能保存但某些引擎渲染异常 | 验证不等价于所有引擎与所有文本 | 用目标引擎和目标文本单独验证；当前不宣称 GDI/DirectWrite 或全部字节码行为 |

## 7. v0.2.1 验证快照

- 本地回归环境为 Python 3.14.4、fontTools 4.61.1，结果 **157/157 通过，0 跳过**。
- 公开手册共 20 个 Markdown 文件、9 组双语主题。详细页覆盖 60 个根公开 callable 和 25 个普通公开类方法；源码签名附录列出 69 个文件、613 个定义，其中包括内部辅助函数。
- 全部 38 个 Python 示例块通过语法检查；两份根 README 各自的 3 个 Python 块还使用中性合成字体，从解压后的审核包实际执行通过。
- 相比 v0.2.0，47 个运行库 Python 文件仅版本字符串变化。打包工具增加公开 Markdown 和显式审核预览选项。
- 这些检查不证明 Python 3.8 运行时、Windows 安装、GDI/DirectWrite 输出或完整引擎矩阵均受支持。第 5 节的 Windows 测量是 v0.2.0 历史结果。
- 运行库源码链接可在 ZIP 内使用，测试与构建工具仍仅在源码仓库中提供。
