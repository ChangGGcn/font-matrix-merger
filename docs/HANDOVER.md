# 交接文档（HANDOVER）

> 读者：刚接手本项目的人或 Agent。目标：**只读这一份**就能跑通四套测试、改一个功能、发一个版本。
> 配套：[ARCHITECTURE](ARCHITECTURE.md)（分层 / 主流程 / 关键不变量）· [CONVENTIONS](CONVENTIONS.md)（代码 / 测试 / Git 规范）· [AGENTS](AGENTS.md)（多 Agent 流程与红线）· 对外说明：[README](../README.md) / [README.zh-CN](../README.zh-CN.md) · 版本历史：[CHANGELOG](../CHANGELOG.md)。
> 事实基准（写作时）：仓库 `Typography/FontMerger`，`main` = `origin/main`（写作时为 `e408504`；本文档提交后以 `git log` 为准），版本 **0.1.1**；`v0.1.1` tag 之后有 [Unreleased] 提交（发布脚本、CHANGELOG、去字体名、`docs/`）。数字来源：README / CHANGELOG / 本机实测（唯一实测耗时：纯数学套件 0.86 s；其余标注为估计或“以实际输出为准”）。

---

## 1. 一句话现状

**v0.1.1 已发布、`main` 与 `origin/main` 同步；项目能把「静态/可变 × OTF/TTF」的主字体与 1~n 个打底字体按 16 种组合合并（跨设计空间合成已做到阶段 0–4），也能把同一可变字体的 webfont 分片按 `merge_subsets()` 保特性并回一个 VF —— 但 JP（CID CFF2）作主字体仍只能降级静态输出，`glyf↔CFF2` 混搭与部分 CFF2 变化数据仍回退“打底默认实例化”，且尚无 pip 安装与 CI。**

- 已发布：tag `v0.1.1`（annotated，2026-09-12，指向 PR #1 合并提交 `6590b09`；`origin` 上已推送）；更早的 `v0.1.0-alpha1` 是轻量 tag（`6f1af8d`）。
- 规模：约 **10.7k 行 Python**（`git ls-files '*.py' | xargs wc -l` = **10,744** 行，不含未入库的 `tests/local_fonts.py`）；纯 fontTools 依赖。
- 能做什么：16 路矩阵（`merge_two()` 自动分派）、多级打底、CFF↔glyf 转换、CID 合并、OT 特性合并、轴并集、跨设计空间合成（gvar / CFF2 blend / 布局变化数据）、`merge_subsets()`（glyf + CFF2 分片并集）、`verify_merge()` / `verify_composition()` 自检、`save_font()` 保存防护。
- 不能做什么：JP CID CFF2 主字体的真·可变保存；`glyf↔CFF2` 跨轮廓技术合成；CFF2 打底的 `VVAR`/Private hint 变化（折默认值）；布局 `VariationIndex` 整数取整残差；打底字体自己的 `FeatureVariations` 并入；`pip install`（仓库根目录即包目录）；CI。
- 相关读数：四套测试 **46 例**（21 / 13 / 8 / 4），详见 §4；关键性能：给 25k 字形主字体加 135 个字形，TTX 整字体往返 **153 s → 3.7 s**（glyf 对象级复制，README / CHANGELOG）。

---

## 2. 环境准备

### 2.1 Python 与依赖

| 项 | 要求 / 现状 | 说明 |
| --- | --- | --- |
| Python | README / 徽章口径 **≥ 3.8**；本机 **3.14.4** | `tests/test_axis_mapping.py` 曾有一处 PEP 701 f-string（同引号嵌套，需 3.12+），已在 [Unreleased] 改成 `print("\\n" + "=" * 50)`；当前源码已按 3.8 语法核对（无 3.9+/3.10+ 专属语法、无函数类型注解） |
| fontTools | **≥ 4.49**（README 徽章 / Quick Start）；本机 **4.61.1** | 校验命令：`python3 -c "import fontTools; print(fontTools.version)"` |
| brotli | 可选 | 只有读写 WOFF/WOFF2 才需要；缺失时 `test_save_guard` 打印 SKIP（`tests/test_merger.py`） |
| pytest / uharfbuzz / pathops | **不需要，也不要引入** | 测试是普通 `def test_*()` + `main()` 运行器；验证不依赖 HarfBuzz（见 §8-8） |
| afdko | 库本身**不 import**；仅 PyInstaller 管线收集 | `build/build_exe.py` 有 `--hidden-import afdko`；本机 `import afdko` 成功 |

> README 的 “Requirements: Python ≥ 3.8, FontTools ≥ 4.49” 是官方口径；版本口径不一致已在 [Unreleased] 修掉（见 §7.3），无需再决策。

### 2.2 测试字体：仓库外 `../test/`

仓库**不分发任何字体**；测试字体位于仓库同级的 `test/` 下，四个子目录：

```
Typography/
├── test/                      # 测试字体与生成产物（不入库）
│   ├── TrueType/              # 静态 TTF
│   ├── OpenType/              # 静态 OTF（CFF）
│   ├── ttf_variable_fonts/    # 可变 TTF（gvar/HVAR/VVAR）
│   ├── otf_variable_fonts/    # 可变 OTF（CFF2）
│   ├── Logic.md               # 早期算法笔记（历史参考）
│   └── samples/               # tests/generate_* 的输出（gitignore）
└── FontMerger/                # 本仓库 = Python 包目录
```

**公开 OFL 字体**（直接按文件名硬编码在测试里，可自由从上游下载；以各自上游 LICENSE 为准）：

| `test/` 下相对路径 | 在测试中的角色 | 谁在用 |
| --- | --- | --- |
| `OpenType/LibreCaslonText-Regular.otf` | `otf_latin`：静态 OTF 拉丁 | `test_merger` 多数用例、`generate_samples` 1/3/5/6、`generate_matrix` A/B 组 |
| `TrueType/LXGWWenKaiTC-Regular.ttf` | `ttf_latin`：静态 TTF 拉丁 | `test_merger`（检测/改名/布局回归）、样例 2 |
| `otf_variable_fonts/SourceHanSansCN-VF.otf` / `SourceHanSansJP-VF.otf` | CFF2 VF：CN 用于检测/实例化，JP 用于矩阵 C1/D1（已知限制 ①） | `test_merger`、样例 4；`generate_matrix` C1/D1 |
| `otf_variable_fonts/SourceSerif4Variable-Roman.otf` | CFF2 VF 夹具 | `test_cff2_compose` 全部 4 例、`test_subset_merge` 的 CFF2 例 |
| `ttf_variable_fonts/InterVariable.ttf` / `TrueType/Inter-Regular.ttf` | 跨设计空间打底（`opsz`+`wght`）/ 静态 TTF 布局回归 | `test_merger` 合成与布局回归用例、`test_axis_mapping.test_real_avar_roundtrip` |
| `OpenType/SourceHanSansSC-Regular.otf` | 静态 OTF CJK 打底 | `generate_samples` 样例 5（三级合并） |

**商业授权字体**只经**不入库**的 `tests/local_fonts.py` 按角色引用（模板 `tests/local_fonts.example.py`）。角色表（不写具体文件名）：

| 角色 | 用途 | 影响的用例 |
| --- | --- | --- |
| `cjk_static_otf` / `cjk_static_ttf` | 商业授权静态 CJK OTF / TTF（主/打底） | `test_merger.test_merge_otf_otf`、`test_high_level_api`、`test_merge_ttf_ttf`、样例 1/2/5/6 |
| `cjk_ttf_hanyi` / `symbols_otf` | 混合格式转换样例 / 符号字体（VF 实例化后合并） | 样例 3 / 样例 4 |
| `vf_ttf_helvetica` | 商业授权可变 TTF（拉丁 VF） | `generate_matrix` B2/B4/C3/C4/D2/D3/D4 共 6 格 |
| `vf_ttf_cjk` | 商业授权可变 CJK TTF（`gvar`/HVAR/VVAR/GDEF VarStore/竖排/kern/mark） | `test_merger` 21 例中约 **10 例**、`test_subset_merge` 8 例中 **7 例**（另一例用公开 Source Serif 4） |

复制步骤（在仓库根目录 `Typography/FontMerger` 执行；该文件已被 `.gitignore` 拦截）：

```bash
cp tests/local_fonts.example.py tests/local_fonts.py
# 编辑 tests/local_fonts.py，把每个角色填成相对 tests/../test 的路径；不用的角色保持注释
```

- **不要读取、复制或提交** `tests/local_fonts.py` 的内容（含商业字体名/路径）；文档与注释一律用中性占位（如 `Main-Serif.otf`、`Base-VF.otf`）。任一角色缺失/未配置时，对应用例打印 `SKIP (测试字体未就位)` 后正常返回（**SKIP 会被汇总计为 passed**，见 §4.2）。

### 2.3 包与导入路径（很容易踩）

仓库**根目录名就是包名** `FontMerger`，没有 `pyproject.toml` / `setup.py`（已知限制 ⑥）。导入需要**父目录**在 `sys.path`：

```bash
cd .. && python3 -c "import FontMerger; print(FontMerger.__version__)"   # 0.1.1  ✅
cd FontMerger && python3 -c "import FontMerger"                         # ModuleNotFoundError ❌
```

`FontMerging.py` 与四套测试脚本都会主动把父目录插入 `sys.path`，所以**按 §4 的命令从仓库根目录运行没问题**；真正写调用方代码时，请把 `Typography/` 加进 `PYTHONPATH`（或等 pip 打包完成）。

---

## 3. 快速上手

### 3.1 交互式 CLI

```bash
# 在仓库根目录（Typography/FontMerger）执行
python3 FontMerging.py
```

流程：输入主字体路径（缩放 % + 基线偏移）→ 逐级输入打底字体（`Y` 结束）→ `check_compatibility()` 打印警告 → 逐级 `merge_two()` → `apply_naming()` → 询问输出路径。要点：

- 导出格式 / 输出选项类问题**只问一次**，记在 `FontMerger.mem`（`self.ask()`），后续级别复用。
- 只有 `check_compatibility()` 返回 `ok=False`（双 CID 字符集高度重叠）时才要求输入 `y` 继续；普通警告（混合轮廓、可变打底、UPM 不一致）打印后直接继续。
- 输出默认写到主字体所在目录，文件名 `<主字体名>_mod.{otf|ttf}`（后缀由合并结果的 `is_cff()` 决定，`FontMerging.py` 末尾）。

### 3.2 库 API

```python
# 在 Typography/ 目录下运行，或 export PYTHONPATH=Typography
from FontMerger import (FontMerger, merge_fonts, apply_naming,
                        get_family, get_copyrights)

merger = FontMerger()                       # 默认即 CLI 推荐策略
merger.mem = {"sOTF_sTTF": "OTF",           # 非交互: 预填询问答案
              "vOTF_sOTF": "可变"}

r = merger.merge_two("Main-Serif.otf", "Base-Serif-VF.otf")
r = apply_naming(r, get_family("Main-Serif.otf"),
                 get_copyrights("Main-Serif.otf", "Base-Serif-VF.otf"))
r.save("merged.otf")

# 一行便捷 API（等价于逐级 merge_two + 命名；返回 TTFont 不落盘，flavor 已清）
result = merge_fonts("Main-Serif.otf", ["Base-Serif-VF.otf", "Base-CJK.ttf"],
                     answers={"vOTF_sOTF": "静态"})
```

- 策略参数 `FontMerger.__init__(compose_variations / compose_range / compose_fit / avar_mode / verify_compose / compose_layout)` 默认值见 README（**不要擅自改默认**）；`DEFAULT_ANSWERS`（`__init__.py:66`）的键必须与 `ask()` 的 key 一致，缺 key 会在非交互流程里真的去 `input()` 阻塞（§8-11）。

### 3.3 `merge_subsets()` 最小示例

```python
from FontMerger import merge_subsets, verify_merge

paths = sorted(glob("webfont/ja-v2/*.woff2"))     # subsets[0] 作基底
merged = merge_subsets(paths, out_path="Merged-JP.ttf", tag="ja",
                       complete_name_table=True, fix_head_flags=True,
                       verify=True)                # verify 内置 verify_merge
gmap = merged.subset_merger.glyph_map()            # 源字形名 → 合并后 GID（按分片）
```

- `subsets[0]` 会被**就地修改**并作为合并结果继续追加字形（`core/subset_merge.py` 的 `merge_subsets` 文档字符串），需要保留输入请先 `copy.deepcopy`。
- `out_path=None` 时只返回 `TTFont` 不落盘；`output_flavor` 缺省按扩展名（`utils/save.py` 的 `default_flavor_for`）。`verify_merge()` 在 `"auto"` 轴位置（默认点 + 首轴两端）抽样比对轮廓/度量，`axis_positions="grid"` 更穷举。
- CFF2 分片要求共享同一个 **VarStore / GlobalSubrs** 结构（pyftsubset 会保持）；结构不一致时 `format/cff2_union.py:check_cff2_compatible` 抛 `IncompatibleCFF2Error`，不会写出坏字体；CFF 与 CFF2 混合分片不支持（已知限制 ⑧）。

### 3.4 输出命名规则

| 出口 | 命名 |
| --- | --- |
| CLI | `<主字体目录>/<主字体 stem>_mod.{otf|ttf}`；扩展名由合并结果的轮廓类型决定 |
| `merge_fonts()` | 不落盘，返回 `TTFont`（`flavor` 已清空） |
| `merge_subsets()` | 由 `out_path` 决定；`output_flavor` 缺省按扩展名（`.woff2` → `woff2`，其余 sfnt） |
| 发布包 | `dist/font-matrix-merger-v<版本>.zip`，包内根目录 `font-matrix-merger-<版本>/` |
| 矩阵 / 样例 | `../test/samples/matrix/<label><extra>.<ext>`、`../test/samples/SampleN_*.{otf,ttf}` |

---

## 4. 如何测试

### 4.1 四条命令

从**仓库根目录**执行（脚本会自行处理 `sys.path`）：

| 套件 | 命令 | 用例数 | 主要依赖 |
| --- | --- | --- | --- |
| 合并主套件 | `python3 tests/test_merger.py` | **21** | 公开 OFL 字体 + 6 个本地授权角色中的多数 |
| 轴映射数学 | `python3 tests/test_axis_mapping.py` | **13** | 无（唯 `test_real_avar_roundtrip` 可选 `InterVariable.ttf`） |
| 同源分片并集 | `python3 tests/test_subset_merge.py` | **8** | `vf_ttf_cjk`（7 例）+ `SourceSerif4Variable-Roman.otf`（1 例） |
| CFF2 合成 | `python3 tests/test_cff2_compose.py` | **4** | `SourceSerif4Variable-Roman.otf` |

合计 **46 例**，与 CHANGELOG 0.1.1 的 “21 + 13 + 8 + 4 = 46 passing” 一致。每套的 `main()` 汇总打印 `Results: N/N passed` 并以退出码表示成败（`sys.exit(0 if success else 1)`）。

**耗时**：纯数学套件本机实测 **0.86 s（13/13）**（Python 3.14.4 + fontTools 4.61.1）。其余三套依赖本地字体与磁盘（单个 CJK VF 可达 15 MB 级，夹具要现场 `pyftsubset`、部分用例多次实例化/深拷贝），按代码路径为**分钟量级估计**；本文件未实测，不写具体秒数，以实际输出为准。

### 4.2 SKIP 语义（必读）

- 缺字体时用例打印 `  test_xxx: SKIP (测试字体未就位)` 然后**正常 return**；`main()` 的循环只捕获异常，所以 **SKIP 也计入 “passed”**。
- 因此 `Results: 21/21 passed` **不代表全都真跑了**——必须翻日志数 `SKIP` 行；纯数学套件在无字体时也会 `13/13 passed`（其中 1 例可能 SKIP），`test_merger.test_table_registry` 也不需要字体。

### 4.3 测试夹具是现场生成的

- `tests/subset_fixture.py`：用 `python -m fontTools.subset`（pyftsubset）把 VF 按码位切成 n 个同源分片（默认 `woff2`、post-3.0 无字形名、保留全部 layout features），同进程缓存；**不需要随仓库分发 webfont 分片**。其 `make_rich_vf()` 还会补 `GDEF MarkGlyphSetsDef` + `GSUB FeatureVariations` 回归索引重映射。
- `tests/cff2_fixture.py`：把 `SourceSerif4Variable-Roman.otf` 切成 main/base 两个不相交子集并改写 base 的 `fvar` 范围/默认值，制造“归一化空间不同、必须合成”的场景。

### 4.4 矩阵与样例生成器（可选）

```bash
python3 tests/generate_matrix.py     # 16 组合矩阵 → ../test/samples/matrix/；任一字体缺失则整体跳过（sys.exit(0)）
python3 tests/generate_samples.py    # 6 个样例 → ../test/samples/
```

两者都会打印缺失角色清单后正常退出，不会报错失败；输出目录在 `../test/samples/`（被 `.gitignore` 的 `test/samples/` 覆盖）。生成器会 `copy.deepcopy` 输入字体，避免 `axis_union` / `variable_to_static` 就地修改污染后续组合。

---

## 5. 发布流程

> 发布 = Lead 动作（AGENTS 红线）；Writer 只准备改动。版本号、CHANGELOG、tag、Release 资产、sha256 四件事必须互相对得上。

### 5.1 版本号三处

| 位置 | 现状 | 改法 |
| --- | --- | --- |
| `__init__.py` | `__version__ = "0.1.1"`（第 22 行） | 改成本次版本（`build/make_release_zip.py` 用正则从这里读版本） |
| `README.md` | 第 6 行 `version-0.1.1-blue.svg` | 同步徽章 |
| `README.zh-CN.md` | 第 6 行同上 | 同步徽章 |

另外 `CHANGELOG.md` 的版本标题与文末 compare 链接也要同步（5.2）。三处漏一处就会出现“包名是 vX、README 是 vY”。

### 5.2 CHANGELOG（单文件双语，先 English 后 简体中文）

- 结构：把 `## [Unreleased]` 的内容提升为 `## [X.Y.Z] — YYYY-MM-DD`，同一版本段内先 `### English` 再 `### 简体中文`，两边结构/细节一致；小节用 Added/Changed/Fixed（中文 新增/变更/修复）。`[Unreleased]` 保留空壳给下次。
- 文末链接更新：`[Unreleased]: .../compare/vX.Y.Z...HEAD`、`[X.Y.Z]: .../compare/v<prev>...vX.Y.Z`。
- 已发布条目**不再改写**；新变更只进 `[Unreleased]`。

### 5.3 打包（仅源码 zip）

```bash
python3 build/make_release_zip.py                 # → dist/font-matrix-merger-v<版本>.zip
python3 build/make_release_zip.py --out /tmp/x.zip --quiet   # 校验用（AGENTS 发布验证门）
```

脚本行为（`build/make_release_zip.py`）：

- 收 **git 已跟踪**的 `*.py` + 根目录 `README.md / README.zh-CN.md / LICENSE / CHANGELOG.md`（`KEEP_NAMES`）；按 `FORBIDDEN_EXTS` **防御性拒绝**字体二进制、`*.ttx`、`*.zip/.exe/.dll`、`*.pyc` 等。
- 版本从 `__init__.py` 读取；zip 内时间戳固定为 **HEAD 提交时间**（`git log -1 --format=%ct`），同一提交重复打包字节一致；包内根目录 `font-matrix-merger-<版本>/`；脚本打印文件数、大小与 **sha256**。
- ⚠️ 当前 `KEEP_NAMES` **不包含 `docs/*.md`**：工程文档（含本文件）不会进发布包；若要随包发布需 Lead 改脚本（共享文件，Writer 不动）。
- ⚠️ `dist/` 里现存的 `font-matrix-merger-v0.1.1.zip`（实测 172,500 字节，sha256 `36898a6b42596f8786bf0ee7076a9cf0726d241fadaff1be4416f21401cb3296`）早于 `make_release_zip.py` 的提交（脚本是 v0.1.1 tag 之后才加的），包内也没有 CHANGELOG.md；**不要用它反推“当前脚本可复现该历史资产”**，它只作为校验流程的样例。

### 5.4 提交与 annotated tag

```bash
git add -A && git commit -m "chore(release): vX.Y.Z — <一句话>"
git tag -a vX.Y.Z -m "vX.Y.Z: <一句话>"          # 必须是 annotated（-a）
git for-each-ref refs/tags/vX.Y.Z --format='%(objecttype)'   # 期望输出 tag
git push origin main
git push origin vX.Y.Z
```

现状参考：`v0.1.1` 是 annotated tag（tagger 2026-09-12，指向 `6590b09`）；`v0.1.0-alpha1` 是轻量 tag（objecttype=commit）。**已发布 tag 不得移动/重打**。

### 5.5 GitHub Release 与 sha256 校验

- 在 GitHub 创建 Release，选 tag `vX.Y.Z`，标题用版本号，说明从 CHANGELOG 该版本段复制（中英双语可同贴）；上传资产 `dist/font-matrix-merger-vX.Y.Z.zip`。
- 校验（任选其一）：WSL `sha256sum dist/font-matrix-merger-vX.Y.Z.zip`；Windows `certutil -hashfile dist\font-matrix-merger-vX.Y.Z.zip SHA256`；下载资产再算一遍，与发布页/本地输出对照，不一致不发布。
- 本机 `gh` **未安装**（`command -v gh` 无输出），Release 走网页界面即可；已推送 tag 可用 `git ls-remote --tags origin` 复核。

### 5.6 WSL 下使用 Windows GCM 凭据（不写任何 token）

本机事实（实测）：

- WSL 里的 Linux git **没有配置 credential.helper**（`git config --global credential.helper` 为空）；`origin` 是干净的 `https://github.com/ChangGGcn/font-matrix-merger.git`（无内嵌凭据）。
- Windows Git 存在：`/mnt/c/Program Files/Git/cmd/git.exe`；GCM 可执行文件：`/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe`（安装位置可能不同，先用 `ls` 确认）。
- `git ls-remote` 读公开仓库不需要认证；**push / Release 才需要**。

两种可用方式：

1. **直接用 Windows git 执行写操作**（最省事）：`"/mnt/c/Program Files/Git/cmd/git.exe" push origin main` —— 认证由 Windows 侧 GCM 接管，必要时弹 Windows 浏览器/设备码。
2. **让 WSL 的 Linux git 调用 GCM**（注意：路径含空格，**不能**把 plain 路径直接写进 `credential.helper` —— git 会按 shell 命令拆开，报 `/mnt/c/Program: not found`）。两种可行做法：① 一次性（推荐，不改全局配置）：写一个无空格的包装脚本（内容为 `#!/bin/sh` + `exec "/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe" "$@"`），再 `git -c credential.helper=/tmp/gcmwrap/git-credential-gcm push origin main`，用完删除；② 持久：`git config --global credential.helper '!"/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe"'`（`!` 前缀 + 整段引号）。首次会走 GCM 登录，登录一次后凭据存在 Windows 凭据管理器里。

注意事项：

- **不要把 token/PAT 写进 remote URL、命令行、脚本、文档或提交**；本仓库 remote 必须保持无凭据形式。检查：`git remote -v`。
- 不要把凭据输出贴进日志/汇报（`git credential fill` 的输出含敏感字段）。
- 如果 GCM 不弹窗：确认 WSL interop 开启、路径存在、用的是 Windows 的 `git.exe` 或有效的 helper 配置；必要时在 Windows 终端里先跑一次 `git push` 完成登录。
- 任何 push/tag/Release 动作都只由 Lead 执行。

---

## 6. 已完成工作（按提交时间线）

| 日期 / 提交 | 内容 | 关键数字（来源） |
| --- | --- | --- |
| 2026-08-30 `15cacca` / `9a37178` / `b82b403` / `6f1af8d` | 初始提交 + **v0.1.0-alpha1**（16 路矩阵、`merge_two`/`merge_fonts`、格式转换、CID、OT 合并、轴并集、交互 CLI、双语 README、PyInstaller、测试与矩阵生成器）→ README 改 GitHub 标准、测试字体改 OFL、授权字体移入 `local_fonts` | 初始发布（CHANGELOG） |
| 2026-09-11 `0478cb5` / `b878d32` / `ef04aa4` | `.gitattributes`（文本 LF）；**`merge_subsets()` 同源分片并集**（对象级，不走 TTX）+ 通用路径/save 修复；README 补 `verify_merge`/保存防护/glyf 快速注入 | glyf 注射 153 s → 3.7 s（25k 字形 +135） |
| 2026-09-11 `16b54cd` | **CFF2 分片并集** + `MarkGlyphSetsDef`/`FeatureVariations` 并集保留 | — |
| 2026-09-11 `5aa866f` | 轴空间一致的打底保留 `gvar` 增量（`axes_compatible()` + `add_HVAR` 重建） | 已知限制 ④ 落地 |
| 2026-09-11 `6c5ab10` / `58007d7` | **阶段 0 + 1**：轴空间映射 / hat 精确重参数化基础设施（不改现有输出）→ `gvar` 跨设计空间合成 | — |
| 2026-09-11 `cc1bc76` / `cf77918` | **阶段 3a + 3b**：主字体 `ItemVariationStore` 重参数化 + **跨 0 hat 修复**；打底布局变化数据（GDEF VarStore + GPOS 设备）并入 | 修复前偏差 0.625 单位；kerning 残差实测 0.70 单位（UPM 1000） |
| 2026-09-11 `6426db9` / `b5a0edc` / `ab722df` | **阶段 4a/4b/4c**：CFF2 blend/vsindex 重参数化引擎 → 接入主流程 → 自检改用 glyphSet 渲染语义 + avar 轴扩展修复 + 跨字族 CFF2 验证 | 自检假阳性 1.58 单位被修正 |
| 2026-09-12 `4e178fd` → `6590b09` | **v0.1.1 发布**：跨设计空间合成（阶段 0–4）+ 字体二进制 `.gitignore`；PR #1 合并 | 46 例测试全通过 |
| 2026-09-12 `5a732f6` / `5c9bedd` / `d67a915` / `e2aeb91` | 合并矩阵文案 5×5 → **4×4**；新增 **CHANGELOG.md**（中英双语单文件）与 **仅源码发布打包** `build/make_release_zip.py` | 见 §5.3 |
| 2026-09-12 `c73268a` → `e408504` | README 去具体字体名（中性占位）、授权字体全部走 `local_fonts`（模板新增 `vf_ttf_cjk` 角色）、代码示例名占位 | — |

> 提交里出现的阶段编号是 **0 / 1 / 3a / 3b / 4a / 4b / 4c**，没有单独的“阶段 2”提交；阶段 4 的缺口见 §7.2。当前 tag 之后还有 `docs/`（本目录）等 [Unreleased] 变更，以 `git log` 为准。

---

## 7. 未完成与已知问题

### 7.1 README「Known Limitations」九条（对外口径，逐条转述）

1. **JP（CID CFF2）作主字体**（矩阵 C1/D1）：合并本身成功（约 18,600–18,868 字形），但保存阶段打底拉丁字形在 cmap format 4 的引用偶发不完整；矩阵生成器降级走静态实例化路径。真·可变输出需解决 CFF2 CID 命名空间问题。
2. **跨设计空间的字形增量**：同轴空间/同 `avar` 走 1:1 搬运（`axes_compatible()`）；不同则走合成（`format/axis_mapping.py`），`verify_composition` 网格自检（容差 1 单位）不通过就**透明回退**到“打底按默认实例化”。缺口见 §7.2。
3. **OpenType 特性**：追加的 base feature 所引用字形必须都在主字体（否则跳过该 lookup）；同 tag feature 并成一条；base Script/LangSys 并入；FeatureList 重排后重写 `FeatureVariations` 索引（无法映射的记录丢弃）；GDEF 类/VarStore/MarkGlyphSets 取并集并重映射 `LookupFlag` bit4。**异源路径不并入打底字体自己的 `FeatureVariations`**。
4–5. **VORG**：默认轴位置正确，非默认位置需重算；**多级 OT 特性**：上级已并入的 feature 在后续级别会被重复检测（幂等，但 lookup 可能冗余）。
6. **打包**：仓库根目录即包本身，`pip install` 未接线；目前 clone 即用，PyPI 化目录结构在规划中。
7. **授权测试字体**仅本地使用、不分发；文档只出现公开 OFL 字体名。
8. **`merge_subsets()` CFF2 边界**：分片需共享同一 VarStore/GlobalSubrs 结构；FDArray 差异由 FD 级并集处理；逐分片重建/重编号 VarStore 的工具会产生需重写 blend 的场景（当前明确报错）；CFF/CFF2 混片不支持。
9. **自动名字形一律加别名**：post-3.0 序号名（`glyphNNNNN`）跨分片同名不同源，故保留为内容相同的副本，用体积换“绝不混淆”。

### 7.2 阶段 4 的已知缺口（跨设计空间合成）

- **(a) 轮廓技术混搭**：`glyf` 组合要求两边都有 `gvar`；CFF2 组合要求两边都是带 `VarStore` 的 CFF2。**`glyf↔CFF2` 混搭**、或变化数据在别的表里 → 回退实例化。
- **(b) CFF2 打底的 `VVAR` / Private hint 变化**：HVAR 按字形名并入；VVAR 与 hint blend 目前保持静态（hint 的 blend 折成默认值）。
- **(c) 整数取整残差**：`VariationIndex` 增量是整数，重参数化后逐列取整 → kerning/anchor 变化最大约 1 单位（实测 0.70，UPM 1000）；CFF2 字宽同理（测试容差 4 单位、轮廓 0.01 单位）。
- **(d) 主字体自身 varStore** 只在轴空间真的变化时（`compose_range="union"/"main"` 或 `avar_mode != 0`）才重参数化；默认点贡献由“恒定 region”（全轴峰值 0）承载。
- 另外：`compose_range="union"` 的外插误差更大，剪枝前 tuple 数最多可达 **×28**；`compose_fit="affine"` 体积小但实测偏差约 **6 单位**，通常被自检拒绝并回退；主 `avar` 把某段用户区间压成一点时（`collapsing_flats()`）无法逐点还原，需 `avar_mode=2` 取舍。

### 7.3 工程债与「代码 vs 文档」不一致（本轮已修 1/2/5，其余待办）

1. ✅ **Python 版本口径（已修）**：`tests/test_axis_mapping.py` 原有一处 `print(f"\n{"="*50}")`（PEP 701，3.12+ 才能解析），已改成 `print("\n" + "=" * 50)`；复查全仓库无 3.9+/3.10+ 专属语法、无函数类型注解，README 的 ≥3.8 口径成立。
2. ✅ **CLI 的“命令行模式”（已修）**：`FontMerging.py` 顶部 docstring 原写 `python FontMerging.py main.otf base.otf`，但 `run()` 不读 `sys.argv`；docstring 已改为“交互模式（当前唯一入口）+ 非交互请用库 API”。
3. **PyInstaller 管线依赖仓库外文件**：`build/build_exe.py` 与 `build/merge_fonts.spec` 指向父目录的旧入口 `../merge_fonts.py`（本机存在，20 KB 级）并把父目录的 `FontMerger/` 作为包数据；同时 `--collect-submodules afdko`。当前仓库入口是 `FontMerging.py`，库本身不 import afdko。换目录布局/想让 exe 跟新入口一致时，需要 Lead 先核对这条管线。
4. **发布包不收 `docs/`**：`build/make_release_zip.py` 的 `KEEP_NAMES` 只有根目录四个文档；本轮工程文档若希望随包发布，需要改脚本（共享文件）。
5. ✅ **README 的“兼容性警告按 y 确认”（已修）**：代码实际只在 `check_compatibility()` 返回 `ok=False`（双 CID 高度重叠）时才询问 `y`，普通警告（混合格式/可变打底/UPM）只打印后继续；两个 README 的 CLI 段落与要点已改成这一口径。
6–7. **库 API 导入前提与打包/CI**：仓库根目录直接 `import FontMerger` 会 `ModuleNotFoundError`（实测，需父目录在 `sys.path`）；仓库没有 `.github/` 与 `pyproject.toml`，回归靠本地四套脚本 + Lead 手跑。
8. **导出格式问答未生效（已知债）**：`_sOTF_sTTF` / `_vOTF_vTTF` 等先 `ask("…TTF/OTF…")` 再丢弃返回值；实际输出轮廓格式由主字体决定（打底轮廓转换到主格式），只有“可变/静态”这一问改变代码路径。README 合并矩阵下方与 ARCHITECTURE §10.4 已注明。
9. **表级注册表未接入主流程（已知债）**：`tables/base.py` 的 `merge_all_tables()` 全仓库无调用点（只有定义/导出/注册表测试）；主流程的表状态来自字形注入编译 + `merge_ot_features()` + `add_HVAR()`。新增表处理器（`@register`）**不会自动生效**，需先接线（见 CONVENTIONS §2.3、ARCHITECTURE §2.3/§10.4）。
10. **双 CID 的 cmap 可能残留旧名（未验证，勿轻信）**：`format/cid_merge.py:74-77 shift_cid_range()` 的 cmap 循环体是 `pass`（注释称“names already updated”），但 fontTools 的 cmap 存的是字形名字符串，不会随 `setGlyphOrder()`/charset 改名自动更新。双 CID 路径无自动化用例；真要动它，先补含 cmap format 14 的双 CID 回归。本条仅为代码审读结论，未实测。

---

## 8. 地雷与调试口诀

1. **“instancer 不套 avar”**：`instantiateVariableFont()` 的 user limits **不应用 avar**，`getGlyphSet(location=...)` 会应用。比对渲染语义时用 `glyphSet`；网格采样只用各轴 min/default/max（avar 不动点）。否则会得到 1 单位级假阳性（实测 1.58）。`core/verify.py:58`、`:404`。
2. **“VariationIndex 的两级是 (VarData 序号, 行号)”**：`(outer, inner)` 不是 region 序号；一行可以承载多个 hat（列 = hat，行值 = 权重），所以重参数化必须**行保持**，并入时只偏移 outer 基址。`format/variation_compose.py:347`、`tables/varstore.py`、`tables/layout_union.py:offset_var_devices`。
3. **“跨 0 的 hat 会被整条忽略”**：OT 引擎对 `lower < 0 < upper` 的支撑整条丢弃。`refine_1d()` 必须把归一化默认点 0 留作节点；修复前实测偏差 0.625。`format/axis_mapping.py:326`、测试 `test_refine_cross_zero`。
4. **“改轴数前先把轴表读进内存”**：`_force_load_axis_tables()`（`core/merger.py:437`）在轴并集前访问 `gvar/HVAR/VVAR/MVAR/cvar/avar/STAT`，把按旧轴数编码的二进制读进内存，否则 reader 返回旧 `gvar.axisCount`，instancer 断言失败（实测 `(2, 1, ['wght','opsz'])`）。
5. **“post-3.0 字体二进制不存字形名”**：TTX 往返后必须按 TTX 的 `GlyphOrder` 顺序 `setGlyphOrder(intended_order)` 恢复，否则新字形被按序号重命名、cmap/布局引用全对不上。`core/glyph_copy.py:308`；`glyphNNNNN` 跨字体同名要别名（`core/conflict.py`、`plan_alias()`）。
6. **“avar 要改 segments，不是只改 AxisSegmentMap”**：`table__a_v_a_r.compile()` 按 fvar 轴序从 `self.segments[axis]` 重建表；只 append `table.AxisSegmentMap` 会在保存时 `KeyError`。`format/vf_axes.py:79`（`_extend_avar_axes`，CHANGELOG 有修复记录）。
7. **“RegionAxisCount 必须等于 fvar 轴数”**：轴并集/重参数化后，各表 `VarStore.VarRegionList.RegionAxisCount` 与每个 region 的轴坐标数必须跟新 `fvar` 一致，否则产出非法字体。`core/verify.py:584`（`_check_var_stores`）会检查 `RegionAxisCount` / `VarRegionIndex` / `VariationIndex` 越界；回归用例 `test_compose_main_var_store_axes`。
8. **“没有 uharfbuzz 怎么验证”**：用 `fontTools.pens.recordingPen.RecordingPen` + `font.getGlyphSet(location=用户坐标[, normalized=True])` 逐点比对；宽度从 glyphSet 读（自带 HVAR）。CFF2 也用同一招（`test_cff2_compose` 注释明确“不依赖 HarfBuzz”）。`core/verify.py:26`（`_pen`/`_coords_delta`）、`test_cff2_compose._draw_diff`。
9. **“输入对象可能被就地改”**：`union_axes()`、`variable_to_static()`、`merge_subsets()`（`subsets[0]`）都会改传入对象；生成器/多级流程要 `copy.deepcopy`（`tests/generate_matrix.py` 即如此）。
10. **“TTX 整字体往返很贵，glyf 走对象复制”**：给 25k 字形字体加 135 个字形，TTX 约 153 s，对象级约 3.7 s；巨字体还会按 `CHUNK_SIZE=5000` 分块（`core/merger.py:745`）。CFF/CFF2/CID 仍必须走 TTX（`core/glyph_copy.py:260`）。
11. **“保存与测试常识”**：所有保存点必须走 `save_font()`（清 `flavor` + 断言 sfnt 魔数，否则 woff2 载入的字体可能被写成“名为 .ttf、实为 wOF2”的文件，`utils/save.py:31`）；SKIP 计为 passed（§4.2），且 `FontMerger.mem` 的键必须覆盖 `DEFAULT_ANSWERS`（`__init__.py:66`），否则非交互调用卡在 `input()`。

---

## 9. 关键文件索引（遇到 X 看哪里）

| 想改 / 排查 | 文件 : 关键函数 |
| --- | --- |
| 16 路分派、单级合并主流程、合成回退 | `core/merger.py`：`FontMerger.merge_two`(:580)、`_do_merge`(:608)、`_do_merge_once`(:623) |
| glyf 对象复制 / CFF·CFF2·CID 的 TTX 注入 | `core/glyph_copy.py`：`merge_glyphs_object`(:184)、`merge_glyphs_via_ttx`(:260)、`inject_glyphs_xml`(:20) |
| 冲突判定 / 字形改名（glyf/cmap/hmtx/布局同步） | `core/conflict.py`：`resolve_conflicts`、`plan_alias`；`core/glyph_rename.py`：`rename_glyphs`、`renamed_copy` |
| 命名与版权 | `core/naming.py`、`utils/detect.py`：`get_family`、`get_copyrights` |
| 保存防护 / 容器判断 | `utils/save.py`：`save_font`(:31)、`assert_sfnt`、`default_flavor_for` |
| 可变→静态、CFF↔glyf、CID 转换 | `format/static_extract.py`、`format/converter.py`、`format/cid_convert.py`、`format/cid_merge.py` |
| 轴并集与轴映射数学 | `format/vf_axes.py`：`union_axes`、`_extend_avar_axes`(:79)、`_extend_varstore_regions`；`format/axis_mapping.py`：`AxisMapping`、`refine_1d`(:326)、`refine_support_rebased`(:466) |
| gvar / varStore 重参数化、布局变化数据 | `format/variation_compose.py`：`plan_axis_space`、`reparametrize_gvar`(:121)、`reparametrize_var_store`(:347)、`transfer_base_layout`(:265) |
| CFF2 blend/vsindex 重参数化、HVAR、分片兼容性 | `format/cff2_compose.py`：`reparametrize_cff2`(:206)、`merge_cff2_var_stores`、`offset_cff2_vsindex`；`format/cff2_union.py`：`check_cff2_compatible`、`FDUnion`、`IncompatibleCFF2Error` |
| 同源分片并集 | `core/subset_merge.py`：`SameSourceSubsetMerger`(:91)、`merge_subsets`(:723)、`glyph_map`(:606) |
| 合并自检 / 布局完整性 / VarStore 合法性 | `core/verify.py`：`verify_merge`(:112)、`verify_composition`(:404)、`_check_layout_integrity`(:476)、`_check_var_stores`(:584) |
| OT 特性 / 布局并集 / FeatureVariations / MarkGlyphSets | `tables/ot_merge.py`：`merge_ot_features`(:585)、`prune_base_layout`(:41)；`tables/layout_union.py`：`LayoutUnion`(:386)、`MarkGlyphSetUnion`(:301)、`remap_feature_variations`(:359)、`resort_layout`(:195) |
| VarStore 并集 / fvar·avar 合并 / 逐表注册 | `tables/varstore.py`、`tables/fvar_avar.py`、`tables/base.py` |
| 测试夹具 | `tests/subset_fixture.py`、`tests/cff2_fixture.py` |
| 发布打包 / exe | `build/make_release_zip.py`、`build/build_exe.py`、`build/merge_fonts.spec` |
| CLI 与便捷 API | `FontMerging.py`、`__init__.py`（`merge_fonts`、`load_font`、`DEFAULT_ANSWERS`） |

---

## 10. 建议的下一步优先级

1. ✅ **P0｜统一 Python 版本口径（已完成）**：`tests/test_axis_mapping.py` 的 PEP 701 写法已改成 3.8 兼容；全仓库复查无 3.9+/3.10+ 专属语法。
2. **P1｜补阶段 4 边界**：先把 `glyf↔CFF2` 混搭与 CFF2 打底 `VVAR`/hint 场景做成“明确告警 + 稳定回退”（现在已有回退，但缺显式日志/文档入口），再评估真正的跨技术合成。理由：决定“跨设计空间”能力的完整性，且新增支持必须过 `verify_composition`。
3. **P1｜JP CID CFF2 主字体保存**：攻 cmap format 4 不完整 / CID 命名空间问题，解锁矩阵 C1/D1 的真·可变输出。理由：这是 README 列的第一条限制，也是 16 路矩阵最后的“降级格”。
4. **P1｜pip 打包 + CI**：加 `pyproject.toml`（消除“仓库根即包”导致的导入坑）与最小 CI（至少跑 `tests/test_axis_mapping.py`，字体套件在无字体环境 SKIP）。理由：当前所有验证靠本地手跑，且 §2.3 的导入问题会持续困扰使用者。
5. **P2｜降低布局整数残差**：针对 `VariationIndex` 的取整误差做残差再分配/容差策略，把实测 0.70 单位压小，并把容差写进 `verify_composition` 的文档化参数。理由：直接影响 kerning/anchor 在合并 VF 中的视觉一致性。
6. **P2｜CLI / PyInstaller 与文档对齐**：CLI docstring 已修（不再承诺不存在的命令行模式）；剩余是把 `build/` 管线指向仓库内入口、去掉对外部 `../merge_fonts.py` 的依赖（§7.3 ③）。理由：这是“文档承诺 ≠ 实际行为”的典型，容易在交接/发布时踩坑。

---

## 11. 维护本文件

- 每次发布后更新 §1（现状）、§6（时间线）、§7（已知问题），并同步 [CHANGELOG](../CHANGELOG.md)；发布流程变化时更新 §5。
- 本文件为**中文**工程文档；不写商业授权字体名、不放字体/凭据，示例用中性占位（`Main-Serif.otf`、`Base-VF.otf`）；数字必须来自 README / CHANGELOG / 可复现实测，不确定的写“未实测/以实际为准”。
