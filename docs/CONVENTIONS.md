# 开发规范（CONVENTIONS）

> 读者：参与 font-matrix-merger 的工程师与 Agent。
> 配套：[架构](ARCHITECTURE.md)、[多 Agent 协作](AGENTS.md)、[交接](HANDOVER.md)、[文档索引](README.md)。
> 本文只收**能执行、能检查**的规则：每条规则尽量给出正例/反例或可勾选检查项。规则与代码冲突时以代码为准，并在同一次改动里更新本文。

## 0. 按改动类型读章节

| 你要做的事 | 必读 | 硬门槛 |
| --- | --- | --- |
| 修 bug / 加小功能 | §2 §3 §5 | 四套测试 21/13/8/4 全绿 + 回归用例 |
| 改可变数据 / 合成逻辑 | §4 §5 §9 | 自检门不关 + 实测数字 |
| 改表合并 / 布局 | §2 §4 §9 | 保存 → 重载 → 结构自检通过 |
| 改对外 API / 策略默认值 | §8 | **先问用户** |
| 写注释 / 文档 / CHANGELOG | §1 | 中文、双语、可定位到代码 |
| 发版 | §6.4 §7 | 四套全绿 + 可复现发布包 |

## 1. 语言与文档风格

### 1.1 代码注释与 docstring：中文

- 注释、docstring、日志、提交信息一律中文；标识符、表名、参数名保留英文；专业术语不硬译（TTX、CFF2、gvar、varStore、hat、avar）。
- 模块 docstring 回答三件事：模块解决什么问题、关键不变量是什么、失败时怎么办。正例：`format/axis_mapping.py` 开头解释三层坐标与「跨 0 hat 会被 OT 引擎忽略」；`core/verify.py` 开头列出 5 条自检判据；`core/glyph_rename.py` 开头解释为什么改名必须"一次做全"。
- 函数 docstring：一句话职责 + `Args:` / `Returns:`（现有 20+ 处使用）。类型信息写在 docstring 里（见 §3）。
- 常量用 `#:` 注释说明语义，例如 `core/subset_merge.py` 的 `_PER_GLYPH_TABLES`、`utils/detect.py` 的 `AUTO_GLYPH_RE`。
- 行内注释解释「为什么」，不是「做了什么」。反例：`i += 1  # i 加 1`。
- 引用代码位置写相对路径 + 函数名，如「`tables/ot_merge.py` 的 `prune_base_layout`」；行号可作辅助线索（如 `core/merger.py:580 merge_two()`），但不要只写行号。
- 反例：`# TODO: fix` / `# issue here` 这类无主语英文；把已删代码注释掉留在文件里。

### 1.2 日志：print + 固定 [标签]

- 项目**不使用 logging 框架**，统一 `print`。唯一例外是临时抑制 fontTools 的 VORG 警告（`format/static_extract.py` 的 `variable_to_static`），不要新增 logger。
- 格式：`print("  [标签] 事实或数字")` —— 两空格缩进 + 方括号中文短标签 + 具体数量/名字；子项再缩进 2 空格。
- 正例：
  - `print(f"  [冲突] {len(cf)} 个字形")`（`core/merger.py` 的 `_do_merge_once`）
  - `print(f"  [合成] 回退到默认实例合并: {e}")`（`core/merger.py` 的 `_do_merge`）
  - `log("  [码位] 源 %d, 合并 %d, 缺失 %d, 多余 %d" % ...)`（`core/verify.py` 的 `verify_merge`，`log()` 内部是 `print`）
- 反例：
  - `print("done")` —— 无标签、无数字，用户无法判断发生了什么；
  - `print(e)` —— 裸异常，没写降级行为；
  - `logging.info(...)` —— 与现有输出/CLI 体验不一致。
- 失败路径以 `[警告]` / `[告警]` 开头，并写清「降级到什么行为」；禁止只打印异常而不写后续处理。
- 支持静音的流程用 `self.log(...)` 包一层（`core/subset_merge.py` 的 `SameSourceSubsetMerger.log`，`verbose=False` 完全静默）；新流程类照此实现。
- 逐字形/逐表的高频日志默认不打；临时调试日志提交前删除或改成汇总数字。

### 1.3 对外 README：英文 + 简体中文两版

- `README.md`（英文，默认）与 `README.zh-CN.md`（中文）必须在**同一次改动**里同步；顶部互链格式固定为 `**English** | [简体中文](README.zh-CN.md)` 与 `[English](README.md) | **简体中文**`（示例里的链接指向仓库根目录，不要按 `docs/` 相对路径解析）。
- 两版的章节、表格、参数名、默认值、已知限制条数必须对称；代码块可以相同。
- 版本号三处联动：`__init__.py` 的 `__version__`、两个 README 的 Version 徽章。
- 改了行为必须同步检查：Key highlights、Features 表、合成参数表（`compose_*` / `avar_mode`）、Tests 段、Known Limitations。
- 正例：`CHANGELOG.md` 的 `[Unreleased]` 与两个 README 在同一批提交里更新。
- 反例：只改中文 README；同一参数在两版里写不同默认值。

### 1.4 CHANGELOG：单文件双语，先英后中

- 结构固定（见 `CHANGELOG.md` 顶部约定）：`## [Unreleased]` → `### English`（`#### Added` / `Changed` / `Fixed` / `Tests`）→ `### 简体中文`（`#### 新增` / `变更` / `修复` / `测试`）；版本段标题为 `## [x.y.z] — YYYY-MM-DD`。
- 英文在前、中文在后，条目顺序、数量、事实一一对应；不是"中文段自由发挥"。
- **已发布版本的段落只读**；新变更一律写进 `[Unreleased]`，发版时整体落成新版本段并更新底部 compare 链接。
- 每条写「用户可感知的变化 + 影响 + 数字」。正例：`[Unreleased]` 的 `build/make_release_zip.py` 条目；反例：「重构了一些代码」「修复若干问题」。
- 发布后 `[Unreleased]` 清空，但标题保留。

### 1.5 内部工程文档：中文

- `docs/*.md` 一律中文；对外 README/CHANGELOG 才双语。
- 示例文件用中性占位（`Main-Serif.otf`、`Base-Serif-VF.otf`、`Merged.ttf`），**不出现任何具体字体名**，也不放字体文件。
- 结论必须能定位到代码（文件 + 函数）；数字必须来自实测/测试输出/已发布文档，禁止估算。
- 新增/删除文档要在 [docs/README.md](README.md) 的文档地图登记；「改了什么 → 更新哪份文档」见该文件的维护表。

## 2. 分层与「新代码放哪」

### 2.1 目录职责

| 目录 / 文件 | 只做 | 不放进这里 |
| --- | --- | --- |
| `FontMerging.py` | 交互 CLI：读输入、调库、打印、保存 | 字体合并逻辑 |
| `__init__.py` | 包门面：公共 API 导出、`__version__`、`load_font` / `merge_fonts` / `DEFAULT_ANSWERS` | 实现细节 |
| `core/` | 流程编排：16 路分派、合成/回退、CID 归一、冲突/改名、TTX 注入、命名、自检、同源分片并集 | 单表策略、纯格式转换 |
| `format/` | 轮廓/容器/可变数据变换：CFF↔glyf、CFF2↔CFF、VF→静态、CID、轴并集与轴映射数学、缩放、子集、webfont 解包 | 合并顺序决策、表注册 |
| `tables/` | 单表合并处理器 + 注册表、OT 布局并集、`ItemVariationStore` 并集 | 跨表流程 |
| `utils/` | 叶子工具：类型检测、保存防护 | 任何上层 import |
| `tests/` | 四套测试 + pyftsubset 夹具 + 矩阵/样例生成器 | 测试字体（不入库） |
| `build/` | PyInstaller 管线与仅源码发布包脚本 | 发布产物（`dist/` 已忽略） |

### 2.2 依赖方向

```text
FontMerging.py / __init__.py（入口 / 包门面）
              │
              ▼
            core/ ──► format/ ──► utils/
              └─────► tables/ ──► utils/
```

- 允许：`core → format / tables / utils`；`format → utils`；`tables → utils`；同层内部引用（如 `format/variation_compose.py → format/axis_mapping.py`）。
- 禁止：`utils` import 任何上层；`format` import `core`；`tables` import `core`；库代码 import `FontMerging.py`（入口只由 `__main__` 调用）。
- 现状已知反例（历史遗留，**不要新增**；细节见 [ARCHITECTURE §2.3](ARCHITECTURE.md)）：
  - `tables/cmap.py` 模块级 `from ..core.glyph_copy import _copy_cmap_mappings`（唯一模块级反向依赖）；
  - `format/cff2_compose.py` 函数内延迟 import `tables.varstore.VarStoreUnion`；
  - `format/cid_merge.py` 函数内延迟 import `core.conflict.resolve_conflicts`。
- 确需反向引用时：写在函数体内延迟 import，并在注释里写原因；能重构掉就重构掉。

### 2.3 格式 / 表 / 流程三类改动的落点

- **表（tables/）**：新增单表合并处理器 → `tables/<table_tag>.py`，函数用 `@register("<tag>")` 注册（样板 `tables/head.py` 的 `merge_head`），并在 `tables/__init__.py` 里 import 该模块（注册靠 import 副作用）；共享取值策略放 `tables/_strategies.py`。
  - **已知缺口**：调度器 `merge_all_tables()` 目前没有被合并主流程调用（`core/merger.py` 无引用），注册表只被 `tests/test_merger.py::test_table_registry` 覆盖。要让新表处理真正生效，必须显式接进 `_do_merge_once` 链路；不要以为加了 `@register` 就生效（ARCHITECTURE §2.3 已记录）。
  - 当前主流程实际使用的表级入口：`tables/ot_merge.py` 的 `merge_ot_features`（由 `core/merger.py` 的 `_merge_base_layout_once` 调用）、`tables/layout_union.py` 与 `tables/varstore.py`（同源分片并集）、`tables/name_table.py` 的 `complete_vf_name_table`、`tables/head.py` 的 `fix_head_flags`（由 `core/subset_merge.py` 调用）。
- **格式（format/）**：轮廓/容器/可变数据变换 → `format/`。纯数学（分段线性、hat 分解、轴映射）必须放 `format/axis_mapping.py` 且不依赖字体对象，保证 `tests/test_axis_mapping.py` 无字体可跑；CFF2 变体数据放 `format/cff2_compose.py` / `format/cff2_union.py`。
- **流程（core/）**：分派、回退、CID 归一、冲突/改名、TTX 注入、命名、自检 → `core/`。`FontMerger.merge_two()` 只按 4×4 类型组合分派，业务逻辑放 `_do_merge` / `_do_merge_once` 或 `core/<topic>.py`。
- 公共 API 新增/签名变更 → `__init__.py` 导出 + 两个 README + CHANGELOG；默认参数变更见 §8。
- CLI 新增提问 → `core/merger.py` 的 `ask()` + `__init__.py` 的 `DEFAULT_ANSWERS`；保持「问一次、后续复用」（`self.mem`）。
- 新测试/夹具/脚本 → `tests/test_*.py`、`tests/*_fixture.py`、`build/`；新文档 → `docs/` 并登记索引。

## 3. 代码风格（以现状为准，不硬套 PEP 8）

- 缩进 **4 空格**，禁止 tab（当前 0 个 tab 缩进行）。
- 行长软上限 **79**：现有 10,744 行 Python 中 >79 字符约 195 行（~1.8%），>99 字符仅 16 行（集中在测试断言消息与矩阵数据）。新代码尽量 ≤79；可读性优先，但别写 150 字符一行。
- **类型注解现状：函数签名不用注解（0 处）**；类型写在 docstring 的 `Args:` / `Returns:` 里，必要时写成 `(ok: bool, warnings: list[str])` 这种文本（见 `core/merger.py` 的 `check_compatibility`）。不要引入 typing/mypy/pyright；要全仓加注解先按 §8 征得同意。
- **语法基线 Python ≥3.8**（README 声明）。不要用 3.9+/3.10+/3.12+ 才有的写法（`dict |` 合并、`match`、嵌套同引号 f-string、`X | Y` 类型标注）。发现更高版本的旧写法不要扩散，报告 Lead。
- import 顺序：标准库 → 第三方（fontTools）→ 本项目；项目内用相对 import。仅为破循环依赖的 import 放函数体内。
- 命名：模块/函数/变量 `snake_case`；类 `PascalCase`；模块常量 `UPPER_SNAKE`；内部实现加 `_` 前缀（如 `_do_merge`、`_map_main_var_stores`、`_force_load_axis_tables`）。跨模块调用 `_` 函数是内部契约（`core/verify.py` 复用 `_COVERAGE_ATTRS` 时标了 `# noqa: F401`），改动前 grep 全部调用点。
- **输入所有权**：对外入口不就地改调用方字体（`merge_fonts()` 先 `copy.deepcopy(main_font)`）；内部函数就地修改必须在 docstring 注明"就地的修改"（`format/vf_axes.py` 的 `union_axes`、`tables/ot_merge.py` 的 `merge_base_layout`、`tables/layout_union.py` 的 `resort_layout`）。
  - **已知例外**：`FontMerger.merge_two()` 在合成失败回退/旧轴并集路径会就地扩展主字体，调用方需传副本（测试里都是 `copy.deepcopy(main)`）；`merge_subsets()` 会就地改 `subsets[0]`（docstring 已注明）。
- **异常处理**：捕获后必须 `print("  [标签] ...")` 告警并给出降级行为；正例 `tables/base.py` 的 `merge_all_tables`（单表失败打印 `[表合并警告]` + traceback，其余表继续）。禁止新增裸 `except: pass`；现存仅允许两类：临时目录清理（`core/glyph_copy.py` 的 `_rmtree`）与 OS/2 统计量尽力重算（`core/subset_merge.py` 的 `_recalc_metrics_cff`，新代码请改成打印告警）。不得用 try/except 吞掉验证断言（见 §4.6）。

## 4. 字体数据处理铁律

### 4.1 绝不写出非法字体

- 库内所有受控保存点走 `utils/save.py` 的 `save_font()`：保存前清 `flavor`、保存后校验 sfnt 魔数；不要新增直接 `font.save()` 的落盘路径。`merge_fonts()` 返回前会清 `flavor`，README 里的 `r.save()` 示例因此是安全的。
- 宁可失败/回退，也不保存半成品：字形注入失败 → 打印 `[合并失败]` 并返回主字体副本；布局合并失败 → `[OT合并] 跳过...`；CFF2 分片结构不一致 → 抛 `IncompatibleCFF2Error`（`format/cff2_union.py`）。
- 「无法精确表达就清零并告警，不要把增量解释到错误空间」是准则（见 `core/merger.py` 的 `_reparametrize_main_after_union` 注释）。
- 有落盘的测试要做「保存 → `TTFont(out)` 重载 → 结构自检」闭环（如 `test_save_guard`、`test_merge_subsets_save_and_reload`）。

### 4.2 失败必须回退 + 告警，不许静默降级

- 合成失败：`_do_merge()` 捕获后打印 `[合成] 回退到默认实例合并: {e}` 再走旧路径；这是**允许且必须**的降级，日志不能省。
- 打底布局变化未并入 → `[合成] 打底布局变化数据未并入 (保留默认实例): {e}`；OT 合并失败 → `[OT合并] 跳过打底布局合并: {e}`。
- 降级意味着信息损失（如打底字形不再随轴变化），必须同时写进日志和 README 已知限制。

### 4.3 仓库不放字体

- `.gitignore` 按扩展名拦截字体二进制、`*.ttx`、`tests/local_fonts.py`；`dist/`、`*.zip` 也不入库。
- 测试字体在仓库外 `../test/`；夹具用 `pyftsubset` 现场生成到 `tempfile.mkdtemp()`（`tests/subset_fixture.py`、`tests/cff2_fixture.py`）；矩阵输出写 `../test/samples/matrix`（`tests/generate_matrix.py`）。
- 发布包由 `build/make_release_zip.py` 只收 `git ls-files` 跟踪的 `*.py` + README×2 + LICENSE + CHANGELOG，并用 `FORBIDDEN_EXTS` 防御；不要手工往 `dist/` 或 Release 塞字体。

### 4.4 不出现商业授权字体名

- 授权字体只经不入库的 `tests/local_fonts.py` 的**角色名**引用；模板 `tests/local_fonts.example.py`（角色如 `cjk_static_otf`、`cjk_static_ttf`、`vf_ttf_cjk`）。
- 文档、注释、提交信息、Release notes 用中性占位（`Main-Serif.otf`、`Base-VF.ttf`）；不要读取或复制 `tests/local_fonts.py` 内容到任何提交物。
- 公开 OFL 字体名只允许出现在测试定位路径中，文档不点名；回归检查参考提交 `e408504`（`git ls-files` 全文件 0 命中商业字体名）。

### 4.5 已发布内容不改写

- 已发布 tag（`v0.1.0-alpha1`、`v0.1.1`）、Release 资产、`CHANGELOG.md` 已发布段落**只读**。
- 不 force-push `main`、不 `reset --hard` 覆盖他人提交、不删分支/tag；需要修正就发新版本。
- 版本号、tag、资产名三者对应：`v<版本>` ↔ `font-matrix-merger-v<版本>.zip`。

### 4.6 自检门不能为了让测试变绿而关

- `FontMerger` 的 `verify_compose` 默认 `True`；`merge_subsets(..., verify=True)` 失败抛 `AssertionError`。不得改默认值、不得在测试里全局关、不得放宽断言。
- 唯一例外：单测为隔离被测功能显式 `FontMerger(verify_compose=False)`（`test_cross_design_space_composition`），必须注释原因，产品默认不变。
- 结构自检（`core/verify.py` 的 `_check_layout_integrity`、`_check_var_stores`）只加检查，不删检查。

## 5. 测试规范

### 5.1 运行器：`def test_*` + `main()`，不用 pytest

四套测试与期望数（提交前必须全绿，合计 21+13+8+4=46）：

| 命令 | 套件 | 期望 |
| --- | --- | --- |
| `python3 tests/test_merger.py` | 主合并 / 合成 / 布局 / 保存 | 21 |
| `python3 tests/test_axis_mapping.py` | 轴映射纯数学（无字体依赖） | 13 |
| `python3 tests/test_subset_merge.py` | 同源分片并集 | 8 |
| `python3 tests/test_cff2_compose.py` | CFF2 合成 | 4 |

- 用例是普通函数：无参数、无 fixture 注入、直接 `assert`。`main()` 里**显式列出**要跑的测试（不靠反射收集），逐个 `try/except` 打印 `FAILED - {e}` + traceback，结尾 `Results: passed/len passed`，`return passed == len(tests)`，`sys.exit(0 if main() else 1)`。
- 成功输出一行摘要 + 关键数字（如 `%d 字形 × 4 位置, 轮廓 %.2e / 字宽 %.2e, PASSED`）。
- **SKIP 也计入 passed**：缺字体时打印 `  test_xxx: SKIP (原因)` 后 `return`，`main()` 仍 `passed += 1`。所以「21/21」不代表 21 个都真跑了；汇报必须单列 SKIP 与原因（见 [AGENTS §5](AGENTS.md)）。
- 依赖：标准库 + fontTools + 本项目；不引入 pytest/uharfbuzz/pathops。

### 5.2 夹具：pyftsubset 现场生成 + 进程内缓存

- 不随仓库提交任何字体/分片；夹具函数接受源字体路径，缺失返回 `None`，调用方 SKIP。
- 生成方式：`python -m fontTools.subset`（`tests/subset_fixture.py` 的 `make_subsets`）或 fontTools 官方 API（`make_rich_vf` 构造 MarkGlyphSetsDef / FeatureVariations）；输出到 `tempfile.mkdtemp(prefix=...)`。
- 开销大的夹具用模块级 `_CACHE` + `cached_*()` 复用（`tests/subset_fixture.py`、`tests/cff2_fixture.py`），同一测试进程只生成一次。
- 夹具要模拟真实结构（post 3.0 自动名、woff2、分片码位互斥），否则测不到真问题。

### 5.3 随机测试固定种子

- 用 `random.Random(<seed>)` 本地实例，不用全局 `random`；现有种子：`20240911`（轴映射）、`20240912`（varStore 重参数化）、`11`（CFF2）。
- 采样规模与容差写进测试与输出：如 `assert worst <= 1.0`（VarStore，1 单位）、轮廓 `0.01` / 字宽 `4.0`（CFF2 定点 + 整数取整），并在注释里解释容差来源。

### 5.4 回归测试必须带可量化断言

- 每个 bugfix 必须带回归用例，断言具体数值或结构，不允许只断言「不抛异常」：
  - 数值：`assert worst <= 1.0`、`assert abs(got - want) < 1e-6`，并打印实测值；
  - 结构：`assert not report["dangling"]`、`assert RegionAxisCount == len(fvar.axes)`，保存 → 重载后再查一遍。
- 断言只能收紧，不能放松；容差变更要在提交信息里说明实测依据。
- 修复前先让测试在旧代码上失败（或说明为何复现不了），再验证新代码通过。

### 5.5 新增测试套件/用例的接入

- 新套件 `tests/test_<topic>.py`：照抄现有头部（`_script_dir` / `_repo_dir` / `_project_dir` 三个路径 + `sys.path.insert`，使直接运行脚本时也能 import `tests.local_fonts`）；从 `FontMerger` 顶层导出导入 API；字体 helper 用 `_open`（OFL 相对路径）/ `_local`（授权角色）。
- 新用例加进对应 `main()` 的 `tests` 列表，并在用例里打印带数字的 `PASSED` 摘要。
- 期望数字变化要同步：`CHANGELOG.md` 的 Tests 段、`docs/README.md` 速览、本文件 §5.1。
- 只跑自己新增的套件不算过门；四套全绿才算。

## 6. Git 规范

### 6.1 分支与推送

- `main` 是唯一长期分支，与 `origin/main` 同步；文档/单文件小修/测试补充可直接提交 `main`。
- 跨多文件、多阶段功能或高风险重构走功能分支 + PR（历史例：提交 `6590b09` 的 `Merge pull request #1: v0.1.1 (跨设计空间可变数据合成, 阶段 0-4)`）；合并用 merge commit，不 rebase 已推送历史。
- 仓库**没有 CI**（无 `.github/`）：门禁靠本地四套测试 + §7 评审清单，不能靠「推上去看看」。

### 6.2 提交信息

- 格式：`<type>(<scope>): <中文摘要>`。type 从历史归纳为 `feat` / `fix` / `docs` / `tests` / `chore`（`build`、`release` 作 scope）；scope 可用 `阶段N`、`changelog`、`build`、`release`、`docs+tests`。
- 摘要一句话说清「改了什么」；正文空一行后分点写：动机/根因 → 改动（带文件路径）→ 实测数据（数字 + 单位）→ 回归数字。
- 真实示例（摘自仓库历史，字体名已中性化）：

```text
fix(阶段4c): 合成自检改用 glyphSet 渲染语义 + avar 轴扩展修复 + 跨字族 CFF2 验证

跨字族实测暴露三个问题, 一并修掉:
- core/verify.py: instantiateVariableFont 的 user limits 不套 avar ...
- format/vf_axes.py: _extend_avar_axes 只改 table.AxisSegmentMap ...
- 实测: 171 字形, 1366 个 blend 重参数化 (列 8 → 37) ...
- 回归: test_merger 21/21, test_cff2_compose 4/4, test_axis_mapping 13/13,
  test_subset_merge 8/8
```

```text
chore(release): v0.1.1 — 跨设计空间可变数据合成 (阶段 0-4) + 字体二进制 gitignore

版本: 0.1.0-alpha1 → 0.1.1 (__init__.py 与两个 README 徽章)
...
测试: test_merger 21 + test_axis_mapping 13 + test_subset_merge 8 +
test_cff2_compose 4 = 46 全通过
```

- 一个提交一个逻辑变更；同一根因的一组修复可以合在一个 `fix` 里（上面的 `fix(阶段4c)` 即三个同源 bug），但不得混入无关格式化/重排。
- 历史里有中英混用的提交（如 `chore: add .gitattributes (LF normalization)`）；新提交优先中文摘要 + 中文正文。

### 6.3 行尾、空白与提交范围

- 全部文本以 **LF** 入库/检出（`.gitattributes`: `* text=auto eol=lf`）；字体/zip/png 等声明为 binary。不提交 CRLF、BOM、行尾空白。
- 禁止提交：字体二进制与 `*.ttx`、`tests/local_fonts.py`、`dist/` 与 `*.zip`、`__pycache__`、`.venv`、PyInstaller 输出、任何本机绝对路径/密钥。
- 提交前看 `git status --short` 与 `git diff`；只 `git add` 明确路径，禁止 `git add -A`。
- 不提交生成物/临时文件；调试产物写到 `tempfile` 或已忽略目录。

### 6.4 tag 与 release（仅 Lead，且需用户确认）

1. 版本号三处：`__init__.py` 的 `__version__` + 两个 README 的 Version 徽章。
2. `CHANGELOG.md`：`[Unreleased]` 落成 `## [新版本] — YYYY-MM-DD`，更新底部 compare 链接，中英同步。
3. 四套测试全绿（21/13/8/4）。
4. `python3 build/make_release_zip.py` 生成 `dist/font-matrix-merger-v<版本>.zip`（可复现：zip 内时间戳固定为 HEAD 提交时间）；记录 sha256。
5. annotated tag `v<版本>` + GitHub Release，资产用该 zip；发布后校验 sha256；已发布 tag 不移动，出问题发新版本。

## 7. 评审清单（逐条勾）

- [ ] **作用域**：diff 只含任务声明的文件；无无关格式化/重排；一个逻辑变更。
- [ ] **正确性门**：改动层次有对应测试；四套 `21/13/8/4` 全绿，报告列出 SKIP 项与原因。
- [ ] **自检调用**：合成路径 `verify_composition` 未关闭/放宽；`verify_merge` 失败仍会抛错；没有删用例或改松断言。
- [ ] **降级路径**：新增失败分支有 `[标签]` 告警并落到安全行为；无新增裸 `except: pass`。
- [ ] **字体红线**：diff 里无字体二进制/`*.ttx`/`tests/local_fonts.py`；无新增具体字体名或本机绝对路径。
- [ ] **保存安全**：新增落盘点走 `save_font()`；保存后能重载并过结构自检。
- [ ] **文档**：两个 README + `CHANGELOG.md` 的 `[Unreleased]`（双语对称）已同步；内部 docs 对应小节已更新。
- [ ] **数字**：提交信息/文档里的实测值与测试输出一致，带单位。
- [ ] **依赖**：未新增第三方依赖；未抬高 Python 版本基线。
- [ ] **API/默认值**：对外 API 或策略默认值若变化，已获用户确认并写进 CHANGELOG。
- [ ] **可回滚**：改动可单独 revert，不依赖后续提交。

## 8. 变更分级：哪些必须先问用户

**必须先问（停下等确认）**：

1. 策略默认值：`compose_variations` / `compose_range` / `compose_fit` / `avar_mode` / `verify_compose` / `compose_layout`、`remove_overlaps` 等默认值或交互问法。
2. 授权/字体：新增测试字体或 `local_fonts` 角色、把任何字体/派生数据纳入分发、修改 LICENSE/版权。
3. 发布动作：版本号、tag、GitHub Release、发布包内容/资产、任何 git 发布操作。
4. 破坏性 git：force-push、`reset --hard`、rebase 已推送历史、删分支/tag/Release、改写已发布 CHANGELOG。
5. 对外 API 破坏性变更：`__init__.py` 导出面、`merge_two` / `merge_subsets` / `merge_fonts` 签名、CLI 交互行为。
6. 依赖与基线：新增依赖（违反「只依赖 fontTools」）、Python 版本基线、PyPI/打包布局。
7. 验证降级：关闭/放宽任何自检，或删除/跳过测试。

**可自主完成但需在汇报说明**：bugfix（附回归测试）、内部重构（不改 API/默认值）、文档与测试补充、日志措辞。

**团队内由 Lead 决策**：改共享文件（README/CHANGELOG/`__init__.py`/`core/merger.py` 等）、跨写作用域、与其它任务的依赖顺序、git 提交与发布动作。

## 9. 常见错误清单（症状 → 原因 → 正确做法）

| 症状 | 原因 | 正确做法（定位） |
| --- | --- | --- |
| 合成自检假失败（实测 1.58 单位偏差） | `instantiateVariableFont` 的 user limits 不套 `avar`，`getGlyphSet` 才套 | 用 `getGlyphSet(location=...)` 比对；采样点取 min/default/max（avar 不动点）（`core/verify.py` 的 `_instance`、`verify_composition`） |
| 某段轴区间增量整段消失（实测 0.625 偏差） | `lower < 0 < upper` 的 hat 被 OT 引擎整条忽略 | 细化时保留 0 节点；用 `supportScalar` 引擎语义验证，不用理想 hat 求和（`format/axis_mapping.py` 的 `refine_1d`；`test_refine_cross_zero`） |
| 保存 `AssertionError` / 非法字体 | `RegionAxisCount` 与 fvar 轴数不一致，或 `VariationIndex` 越界 | 轴空间变化后重算所有 VarStore region；`_check_var_stores` 自检（`core/merger.py` 的 `_map_main_var_stores`、`core/verify.py`） |
| 增量被解释到错误位置 | 误以为 `VariationIndex` 的 inner 是 region，实际是 **VarData 行号** | 行保持、重参数化列，不重写引用（`format/variation_compose.py` 模块 docstring；提交 `cc1bc76`） |
| instancer 断言 `(2, 1, ['wght','opsz'])` | 改 fvar 后仍从 reader 读旧轴数二进制 | 改轴前 `_force_load_axis_tables()` 强制加载 gvar/HVAR/...（`core/merger.py`） |
| 新增轴后保存 `KeyError: '<轴 tag>'` | `avar.compile` 按 fvar 轴序读 `segments`，只改 `table.AxisSegmentMap` 无效 | 同时写 `avar.segments`（`format/vf_axes.py` 的 `_extend_avar_axes`） |
| 不同字体同名自动字形被当成同一个 | post 3.0 的 `glyphNNNNN` 不具标识性；TTX 往返也可能改名 | 用 `is_auto_glyph_name` 判断并加别名；改名清单一次做全（`utils/detect.py`、`core/glyph_rename.py`） |
| 编译期 KeyError / 组件指向错字形 | 复合字形惰性持有 GID；改字形序前没展开 | 先 `glyf.ensureDecompiled()` 再改序（`core/glyph_rename.py`、`core/glyph_copy.py`） |
| 编译期 `vmtx` KeyError | 主字体有 `vmtx` 时每个字形都必须有纵向度量 | 新增字形补 `(0,0)`；HVAR/VVAR 映射补 `NO_VARIATION_INDEX`（`core/glyph_copy.py`、`core/subset_merge.py`） |
| HarfBuzz 静默错位（fontTools 仍能保存） | Coverage 与并行数组不同序、PairValueRecord 未按 GID 升序、MarkFilteringSet/FeatureVariations 索引未重映射 | 布局并集/重排后 `resort_layout()` + 重映射索引（`tables/layout_union.py`；`core/verify.py` 的 `_check_layout_integrity`） |
| woff2 被存成 `x.ttf`，Windows 装不上 | `TTFont.flavor` 保留了 woff2 | 一律走 `save_font()`（`utils/save.py`；README 的 Save guard） |
| 双 CID 合并后新增 0 个字形 | 两套 CID 字符集高度重叠 | 调换主/打底顺序或先把打底转 name-keyed（`core/merger.py` 的 `_diagnose_empty_merge`、`check_compatibility`） |

## 附：提交前 30 秒自检

```bash
cd Typography/FontMerger
python3 tests/test_axis_mapping.py     # 13
python3 tests/test_merger.py           # 21
python3 tests/test_subset_merge.py     # 8
python3 tests/test_cff2_compose.py     # 4
git status --short                     # 确认没有字体/本地配置混入
git diff --stat                        # 确认 diff 范围
```
