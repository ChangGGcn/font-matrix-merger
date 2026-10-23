# 模块与脚本参考

本页说明源码仓库中每个 Python 文件与 PyInstaller spec 的职责、算法思路和阅读入口，按目录分组。参数签名与默认值见[完整源码签名索引](parameter-index.md)，合并流程见[合并流程与数据不变量](architecture.md)，对外 API 见[合并 API](merge-api.md) 与[辅助 API](helper-api.md)。

## 1. 阅读约定

- 覆盖源码仓库中的 69 个 Python 或 spec 文件：运行库 47 个、构建脚本 3 个、测试与夹具 19 个。
- 标为**运行 ZIP**的文件随发布包分发。运行 ZIP 含 `FontMerging.py`、`__init__.py`、`core/`、`format/`、`tables/`、`utils/` 下的 Python 文件以及公开文档。
- 标为**仅仓库**的文件只在源码仓库提供：`tests/`、`build/`。离线 ZIP 内不存在这些路径，本页对这些条目只给代码路径；源码可在 https://github.com/ChangGGcn/font-matrix-merger 浏览。
- “入口”列是阅读该文件时先看的函数或类，不表示公共 API 稳定性。
- 测试脚本没有额外命令行参数。统一入口是 `tests/run_regressions.py`，见第 8 节。
- 本地私有配置 `tests/local_fonts.py` 不入库。本页不读取、不列出其中内容；模板见 `tests/local_fonts.example.py`。

## 2. 入口与包门面

| 文件 | 入口 | 职责 |
| --- | --- | --- |
| [FontMerging.py](../../FontMerging.py) | `run()` | 交互式 CLI。读取主字体、多级打底、缩放百分比与基线偏移，调用兼容性检查、`merge_two()`、`apply_naming()`、`save_font()`。不读取命令行位置参数。 |
| [__init__.py](../../__init__.py) | `merge_fonts()`、`load_font()` | 包门面：`__version__`、扩展名集合、`DEFAULT_ANSWERS`、字体加载、便捷合并，以及核心类与工具再导出。 |

### 2.1 FontMerging.py 的输入与退出

- 输入顺序：主字体路径、缩放倍率、基线偏移；随后每级打底字体重复路径、缩放倍率、基线偏移；输入 `Y` 结束。
- 路径首尾引号会被去掉。TTC/OTC 与非支持扩展名会被拒绝并重新询问。
- 加载后对相邻输入运行 `check_compatibility()`。只有返回 `ok=False` 的双 CID 高度重叠会要求 `y`/`N`；其余警告只打印。
- 默认输出路径为主字体目录下的 `<主名>_mod.otf` 或 `.ttf`，扩展名由结果轮廓类型决定。
- 保存失败退出码 1，取消或完成退出码 0。

## 3. core/：流程编排（运行 ZIP）

| 文件 | 入口 | 职责与算法 |
| --- | --- | --- |
| [core/__init__.py](../../core/__init__.py) | 模块再导出 | 汇总冲突、命名、字形注入与合并器常用符号，供内部导入。 |
| [core/merger.py](../../core/merger.py) | `FontMerger.merge_two()`、`_do_merge()`、`_do_merge_once()`、`_finalize_merge()` | 16 路分派；合成路径先试后回退；UPM、CID 与轮廓格式归一；别名与冲突；字形注入；可变数据收尾；5000 字形分块；统一收尾（hinting 策略、表策略、元数据重算、布局排序、出口不变量）。 |
| [core/conflict.py](../../core/conflict.py) | `resolve_conflicts()`、`plan_alias()` | 主字体码位优先；保留打底独有码位与组件、UVS 闭包；返回不应复制的字形集合；规划自动名别名。 |
| [core/glyph_copy.py](../../core/glyph_copy.py) | `merge_glyphs_via_ttx()`、`merge_glyphs_object()`、`inject_glyphs_xml()` | 两条注入路径：glyf 对象级复制，CFF/CFF2/CID 的 TTX XML 往返。处理 post 3.0 字形名恢复、组件改名、cmap 合并与 format 0 升级。 |
| [core/glyph_rename.py](../../core/glyph_rename.py) | `rename_glyphs()`、`renamed_copy()` | 一次同步 glyf、CFF、度量、cmap、HVAR/VVAR 与布局引用；提供深拷贝版本。 |
| [core/hinting_policy.py](../../core/hinting_policy.py) | `apply_hinting_policy()` | 只处理新增字形的 TrueType 指令；兼容时合并 maxp 资源；无法证明兼容时剥离新字形指令并告警。 |
| [core/invariants.py](../../core/invariants.py) | `assert_cmap_union()`、`assert_font_structure()` | 出口自检：精确 Unicode/UVS 并集、主映射优先、字形与布局引用完整。失败抛异常，不返回部分产物。 |
| [core/naming.py](../../core/naming.py) | `apply_naming()` | 按语言派生 `<族名> mod`，同步身份 name 记录与 PostScript 名，按语言合并版权；保留版本、厂商、商标与授权。 |
| [core/subset_merge.py](../../core/subset_merge.py) | `merge_subsets()`、`SameSourceSubsetMerger.merge()`、`glyph_map()` | 同源分片并集：改名、逐字形复制、cmap 统一、GDEF/VarStore/HVAR/VVAR、布局并集、按码位重排与布局排序、度量重算。 |
| [core/table_policy.py](../../core/table_policy.py) | `apply_table_policy()` | 删除失效签名与设备缓存；只并集标准格式 0 的水平 kern；VORG 按存活字形原点处理；保留主字体的 gasp/meta/trak。 |
| [core/verify.py](../../core/verify.py) | `verify_merge()`、`verify_composition()`、`_check_layout_integrity()`、`_check_var_stores()` | 在采样轴位置逐字形比对轮廓与度量；检查码位、特性、布局索引、容器与可变表；提供合成网格自检与结构不变量。 |

## 4. format/：轮廓、轴与可变数据（运行 ZIP）

| 文件 | 入口 | 职责与算法 |
| --- | --- | --- |
| [format/__init__.py](../../format/__init__.py) | 模块再导出 | 汇总转换、子集、静态提取与 webfont 解包。 |
| [format/axis_mapping.py](../../format/axis_mapping.py) | `PiecewiseLinear`、`AxisMapping`、`refine_1d()`、`refine_support_rebased()` | 三层归一化；fvar/avar 分段线性复合与逆；hat 节点分解、重定基、平台段检测与支撑求值。纯数学，不依赖字体对象。 |
| [format/cff2_compose.py](../../format/cff2_compose.py) | `reparametrize_cff2()`、`merge_cff2_var_stores()`、`merge_cff2_hvar()`、`offset_cff2_vsindex()` | CFF2 blend 程序重写；VarStore 列重参数化；Private DICT blend；并入其他字体时平移 vsindex。 |
| [format/cff2_union.py](../../format/cff2_union.py) | `check_cff2_compatible()`、`FDUnion`、`copy_glyphs()`、`sync_glyph_order()` | 校验分片 CFF2 结构可零重定位并集；FDArray 并集；复制字形；同步 charset 与 FDSelect。 |
| [format/cid_convert.py](../../format/cid_convert.py) | `cid_to_name()`、`name_to_cid()`、`ensure_cid_format()` | CID 与 name-keyed 互转，使用 Adobe-Identity-0；处理 ROS、FDSelect 与 cmap format 14 UVS。 |
| [format/cid_merge.py](../../format/cid_merge.py) | `cid_ufo_style_merge()`、`merge_cid_fonts()`、`shift_cid_range()` | 双 CID 合并：CID 偏移、CharString 物化复制、保存重载归一到 name-keyed。 |
| [format/converter.py](../../format/converter.py) | `convert_font_format()`、`cff_to_glyf()`、`glyf_to_cff()` | CFF 与 glyf 互转（Cu2Qu/Qu2Cu 近似）；拒绝可变字体的跨轮廓转换；附带 Windows/Office 修复与失败回退。 |
| [format/static_extract.py](../../format/static_extract.py) | `variable_to_static()` | 在默认轴位置实例化；CFF2 转 CFF；可选重叠合并，默认关闭。 |
| [format/subsetter.py](../../format/subsetter.py) | `create_glyph_subset()` | 使用官方 Subsetter 维护组件与布局闭包；保留已选空字形；删除不支持的派生缓存与表时告警。 |
| [format/transform.py](../../format/transform.py) | `scale_font()`、`apply_scale_offset()` | 应用 `(x*s, y*s+offset)` 且保持 UPM；处理 glyf/CFF、竖排原点与 TSB；非恒等时移除 hinting 与像素缓存；拒绝 VARC。 |
| [format/variation_compose.py](../../format/variation_compose.py) | `plan_axis_space()`、`reparametrize_gvar()`、`reparametrize_var_store()`、`transfer_base_layout()` | 规划合并轴空间；按合并默认点实例化；gvar 逐字形重参数化；VarStore 行保持重参数化；打底布局变化迁移。 |
| [format/vf_axes.py](../../format/vf_axes.py) | `union_axes()`、`_extend_avar_axes()`、`_extend_varstore_regions()` | 轴并集：扩范围、追加打底独有轴、补 STAT 条目、扩展 avar segments 与各 VarStore region。 |
| [format/webfont.py](../../format/webfont.py) | `unwrap_webfont()` | 读取 WOFF/WOFF2 并清除容器 flavor。 |

## 5. tables/：单表与布局合并（运行 ZIP）

| 文件 | 入口 | 职责与算法 |
| --- | --- | --- |
| [tables/__init__.py](../../tables/__init__.py) | 导入副作用 | 导入各表模块以触发 `@register`，并再导出调度器与注册表。 |
| [tables/_strategies.py](../../tables/_strategies.py) | `first()`、`max_val()`、`bitwise_or()` | 表合并取值策略：主优先、最值、按位运算、求和、列表与字典合并、时间戳与重算占位。 |
| [tables/base.py](../../tables/base.py) | `register()`、`merge_all_tables()` | 表级注册表与兼容调度器。主合并流程不调用；逐表失败告警并继续，不能当作完整验证。 |
| [tables/cmap.py](../../tables/cmap.py) | `merge_cmap()` | 注册表 handler；字形级 cmap 已在 `core/glyph_copy.py` 处理。 |
| [tables/fvar_avar.py](../../tables/fvar_avar.py) | `merge_fvar()`、`merge_avar()` | 注册表 handler：保留主字体 fvar/avar 语义。 |
| [tables/head.py](../../tables/head.py) | `merge_head()`、`fix_head_flags()` | head 合并；清除 `head.flags` 的 WOFF2 残留位。 |
| [tables/hhea_vhea.py](../../tables/hhea_vhea.py) | `merge_hhea()`、`merge_vhea()` | hhea/vhea 度量与行距策略。 |
| [tables/kern.py](../../tables/kern.py) | `merge_kern()` | 注册表 kern 合并，主字体值优先。 |
| [tables/layout_union.py](../../tables/layout_union.py) | `LayoutUnion`、`MarkGlyphSetUnion`、`resort_layout()`、`offset_var_devices()` | 深度字形名重映射；VariationIndex 偏移；同一 LangSys 内同 tag feature 归并；嵌套 lookup 图修剪与索引重写；FeatureVariations 索引重写；Coverage 与并行数组排序。 |
| [tables/maxp.py](../../tables/maxp.py) | `merge_maxp()`、`_merge_hint_resources()` | 更新字形数；只在指令环境兼容且指令实际保留时扩大 hint 资源。 |
| [tables/metadata_recalc.py](../../tables/metadata_recalc.py) | `recalc_after_merge()` | 按最终字体重算 OS/2 范围、平均字宽、最大上下文与 head 边界；PANOSE 全零不猜测；失败告警并保留原值。 |
| [tables/metrics.py](../../tables/metrics.py) | `merge_hmtx()`、`merge_vmtx()` | 注册表 handler：水平与纵向度量合并。 |
| [tables/name_table.py](../../tables/name_table.py) | `complete_vf_name_table()`、`merge_name()` | 补 nameID 16/17/25 与实例 PostScript 名；注册表 name 清理。 |
| [tables/os2.py](../../tables/os2.py) | `merge_os2()` | 设计身份以主字体为准；合并嵌入权限；保留主表版本，不凭打底版本制造缺字段。 |
| [tables/ot_merge.py](../../tables/ot_merge.py) | `merge_ot_features()`、`prune_base_layout()`、`merge_base_layout()` | 用 Subsetter 闭包修剪打底布局；GSUB/GPOS/GDEF 图并集；同一 LangSys 内同 tag 归并；嵌套索引重映射；GDEF VarStore/MarkGlyphSets 并集与 MarkFilteringSet 重映射。 |
| [tables/otlayout.py](../../tables/otlayout.py) | `merge_gsub()`、`merge_gpos()`、`merge_gdef()` | 旧注册表 handler：主字体已有布局表时整体保留。 |
| [tables/post.py](../../tables/post.py) | `merge_post()` | 注册表 post 表合并。 |
| [tables/varstore.py](../../tables/varstore.py) | `VarStoreUnion` | ItemVariationStore 并集：region 去重、VarData 拼接，返回 outer 基址偏移。 |

## 6. utils/：叶子工具（运行 ZIP）

| 文件 | 入口 | 职责 |
| --- | --- | --- |
| [utils/__init__.py](../../utils/__init__.py) | `*` 再导出 | 转发 `detect.py` 的公共符号。 |
| [utils/detect.py](../../utils/detect.py) | `is_cff()`、`get_family()`、`get_copyrights()`、`is_same_source()` | 类型与轴空间检测、本地化名称选择、同源分片判定、自动名识别。 |
| [utils/save.py](../../utils/save.py) | `save_font()`、`assert_sfnt()`、`default_flavor_for()` | 清除 flavor、保存、校验 sfnt 魔数；按扩展名推断容器。 |

## 7. build/ 与打包（仅仓库）

| 文件 | 入口 | 职责 |
| --- | --- | --- |
| `build/build_exe.py` | `check()`、`build()`、`main()` | PyInstaller 驱动。 |
| `build/font_merger.spec` | PyInstaller Analysis/EXE | 单文件打包配置。 |
| `build/make_release_zip.py` | `collect_files()`、`build()`、`main()` | 仅源码运行 ZIP。 |

### 7.1 build/build_exe.py

- `--check`：只做预检，检查入口、spec、包目录、PyInstaller 与平台，不构建。
- `--install`：缺少 PyInstaller 时先执行 `pip install pyinstaller`。
- `--clean`：构建前清 PyInstaller 缓存。
- 产物写到 `build/dist/FontMerger` 或 `build/dist/FontMerger.exe`，中间文件在 `build/build/`，两者都不入库。
- PyInstaller 不能交叉编译。Windows 可执行文件必须在 Windows 上构建；Linux/WSL 产物只用于检查依赖收集。

### 7.2 build/font_merger.spec

- 入口是仓库根 `FontMerging.py`，`pathex` 指向仓库根以解析 `FontMerger` 包。
- 收集 `fontTools` 子模块，以及 `brotli`、`zopfli` 与 `xml.etree.ElementTree`。
- 不收集 AFDKO。库本身不 import 它。
- spec 不能单独运行；用 `build/build_exe.py` 或 `python3 -m PyInstaller build/font_merger.spec`。

### 7.3 build/make_release_zip.py

- `--out PATH`：指定输出 zip。默认 `dist/font-matrix-merger-v<版本>.zip`。
- `--root NAME`：指定包内顶层目录名。默认 `FontMerger`。
- `--quiet`：只输出结果行。
- `--preview`：审核预览。额外收集 `git ls-files --others --exclude-standard -- doc` 中未跟踪且未被忽略的 `doc/*.md`，不暂存、不提交。默认输出名变为 `dist/font-matrix-merger-v<版本>-review.zip`。
- 常规收集：已跟踪的运行库与 CLI（`__init__.py`、`FontMerging.py`、`core/format/tables/utils` 下的 `*.py`）、根文档（两版 README、CHANGELOG、LICENSE）以及已跟踪的 `doc/*.md`。
- 不收集：`tests/`、`build/`、本地私有文档、字体二进制、`*.ttx`、打包产物。
- zip 内时间戳固定为 HEAD 提交时间，同一提交重复构建字节一致。脚本打印文件数、大小与 sha256。
- 审核阶段的文档尚未提交时，普通构建不会包含它们；需要可审阅的完整资产时使用 `--preview`。

## 8. tests/（仅仓库）

### 8.1 运行器与约定

- 测试是普通 `def test_*()` 函数加 `main()` 运行器，不使用 pytest。
- 每个测试脚本不接收额外命令行参数。直接运行：`python3 tests/test_<name>.py`。
- 四套基线测试的期望数量是 21、13、8、4。
- 缺字体时用例打印 `SKIP` 后正常返回，`main()` 仍把它计为 passed。必须同时查看 SKIP 行，不能只看汇总数字。
- 统一入口 `tests/run_regressions.py`：
  - 不带参数：基线四套加七套合成回归。
  - `--synthetic-only`：只跑不依赖外部字体的合成回归。
  - `--engines`：追加系统 HarfBuzz/FreeType 测试；缺失系统库的用例 SKIP，不安装依赖。
  - 运行器把每套完整日志写入临时目录，并汇总 passed、退出码与 SKIP 数。

### 8.2 测试套件

| 文件 | 目的 | 运行 |
| --- | --- | --- |
| `tests/test_axis_mapping.py` | 轴映射纯数学：分段线性、hat 分解、重定基、跨 0、平台段、VarStore 行保持。无必需外部字体；1 个用例可选真实 avar 字体，缺失时 SKIP。 | `python3 tests/test_axis_mapping.py`，13 例 |
| `tests/test_merger.py` | 主合并、冲突与命名、保存防护、跨设计空间合成与回退、布局与可变表保留。 | `python3 tests/test_merger.py`，21 例 |
| `tests/test_subset_merge.py` | 同源分片并集、码位与特性保留、CFF2 分片、落盘重载、glyph_map。 | `python3 tests/test_subset_merge.py`，8 例 |
| `tests/test_cff2_compose.py` | CFF2 blend/vsindex 重参数化、Private blend、跨字体合并。 | `python3 tests/test_cff2_compose.py`，4 例 |
| `tests/test_cmap_regressions.py` | 现场构造字体的码位优先级、子表同步、UVS、组件与 CID 回归。 | `python3 tests/test_cmap_regressions.py` |
| `tests/test_layout_regressions.py` | 布局并集：上下文 lookup、LangSys 隔离、FeatureVariations、kern 与 Coverage 排序。 | `python3 tests/test_layout_regressions.py` |
| `tests/test_transform_regressions.py` | 缩放与基线偏移、竖排原点、hinting 策略、轮廓格式转换保存。 | `python3 tests/test_transform_regressions.py` |
| `tests/test_metadata_regressions.py` | OS/2、head、maxp、hinting、VORG、kern 与表策略回归。 | `python3 tests/test_metadata_regressions.py` |
| `tests/test_naming_regressions.py` | 多语言命名、RIBBI 与 PostScript 名、版权合并、幂等性。 | `python3 tests/test_naming_regressions.py` |
| `tests/test_invariants.py` | 出口不变量：码位并集、主映射、嵌套索引、失败路径、UPM/VORG。 | `python3 tests/test_invariants.py` |
| `tests/test_subset_regressions.py` | 子集闭包、空字形保留、不支持表的显式删除。 | `python3 tests/test_subset_regressions.py` |
| `tests/test_engine_regressions.py` | 用系统 HarfBuzz/FreeType 验证布局执行与加载；缺库 SKIP。 | `python3 tests/test_engine_regressions.py`，或运行器加 `--engines` |

### 8.3 夹具、生成器与配置

| 文件 | 目的 | 使用方式 |
| --- | --- | --- |
| `tests/__init__.py` | 使 `tests.*` 可导入的包标记。 | 由测试导入。 |
| `tests/subset_fixture.py` | 用 pyftsubset 现场生成同源分片与 rich VF，进程内缓存。 | 由测试与生成器导入。 |
| `tests/cff2_fixture.py` | 生成字形不相交、轴空间不同的 CFF2 main/base 夹具，进程内缓存。 | 由测试导入。 |
| `tests/generate_matrix.py` | 生成 16 组合矩阵与混合字体，输出到仓库外 `test/samples/matrix/`。 | `python3 tests/generate_matrix.py`；缺字体时打印缺失项并整体跳过。 |
| `tests/generate_samples.py` | 生成 6 个使用样例到仓库外 `test/samples/`。 | `python3 tests/generate_samples.py`；单个样例可 SKIP。 |
| `tests/local_fonts.example.py` | 本地授权字体角色映射模板。 | 复制为 `tests/local_fonts.py` 后按角色填写；该文件不入库。 |
| `tests/run_regressions.py` | 统一回归入口。 | `python3 tests/run_regressions.py`，或加 `--synthetic-only` / `--engines`。 |

## 9. 运行 ZIP 与仅仓库文件

| 类别 | 内容 | 说明 |
| --- | --- | --- |
| 运行 ZIP 包含 | `FontMerging.py`、`__init__.py`、`core/`、`format/`、`tables/`、`utils/` 下的 `*.py`，两版 README、CHANGELOG、LICENSE，公开 `doc/` Markdown。 | 解压后顶层目录为 `FontMerger/`。文档内指向运行库的相对链接在 ZIP 内有效。 |
| 仅源码仓库 | `tests/`、`build/`、本地私有文档、`dist/`、字体与本地配置。 | 离线 ZIP 内没有这些路径；本页对应条目只给代码路径，不给相对链接。 |
| 审核预览 | 未跟踪的 `doc/*.md`。 | 由 `build/make_release_zip.py --preview` 显式收集，不暂存、不提交。 |

发布前以实际构建输出为准：`python3 build/make_release_zip.py` 或 `python3 build/make_release_zip.py --preview` 会打印文件清单、大小与 sha256。

## 10. 继续阅读

[合并 API](merge-api.md)、[辅助 API](helper-api.md)、[同源分片与验证](subsets-and-verification.md)、[轴映射与可变数据合成](variation-model.md)、[合并流程与数据不变量](architecture.md)、[支持边界](limitations.md)、[完整源码签名索引](parameter-index.md)。文档索引：[../README.zh-CN.md](../README.zh-CN.md)。
