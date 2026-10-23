# 工程架构（ARCHITECTURE）

> 读者：要改代码的工程师 / Agent。本文只写 **v0.1.1 的代码事实**（不是设计愿景），结论可按"文件 + 函数"回查；行号是写作时快照，检索优先用函数名。
> 配套：[文档索引](README.md) · [开发规范](CONVENTIONS.md) · [交接说明](HANDOVER.md) · [多 Agent 协作](AGENTS.md)；对外功能见 [README](../README.md)、版本史见 [CHANGELOG](../CHANGELOG.md)。维护规则：改动分层/主流程/关键不变量/合成步骤时同步更新对应小节（见 [docs/README.md](README.md) §3）。

## 0. 一页速览

- **定位**：纯 fontTools 字体合并库（无 pytest/uharfbuzz/pathops）。两份入口：交互 CLI `FontMerging.py` 与包 API；仓库根目录就是包，当前是"clone 即用"，尚未 pip 化。
- **两条互不复用的合并路径**：① 异源 `FontMerger.merge_two()` —— 按 `静态/可变 × OTF/TTF` 16 路分派，打底可变时先尝试**跨设计空间合成**，失败回退"按打底默认实例化"；② 同源分片 `merge_subsets()` —— 同源 webfont 分片**不实例化、不做轴并集**，逐字形/逐表并集，保留 `gvar`、CFF2 blend 与布局特性。
- **三个最容易写坏字体的地方**：轴归一化空间（§4.1–4.4）、ItemVariationStore 的 `(VarData, 行)` 引用（§4.3）、字形序变化后的布局排序不变量（§4.9、§7.4），改可变数据代码前先读 §4；**质量门** 4 套共 46 个用例（21/13/8/4，§8 与 [AGENTS.md](AGENTS.md) §4），缺字体是合法 SKIP。

## 1. 定位与公共 API

### 1.1 定位

`FontMerger` 的合并语义：主字体全部保留；打底字形在**码位与字形名都不冲突**时并入（自动名 `glyphNNNNN` 例外，见 §3.3）；打底布局特性修剪到存活字形后并集追加、冲突以主为准（§7）；主可变则输出可变，打底可变数据尽量合成/搬运（§6）。输入支持 sfnt 与 WOFF/WOFF2（自动清 flavor），TTC/OTC 不支持；所有保存点走 `save_font()`（§4.8）。

### 1.2 包级导出面（`__init__.py`）

`__init__.py` 是唯一门面（`__version__ = "0.1.1"`）。按类别列主要导出：
- **主流程/并集**：`FontMerger`、`axes_compatible`、`transfer_glyph_variations`、`merge_glyphs_via_ttx`、`SameSourceSubsetMerger`、`load_subsets`、`merge_subsets`；
- **算法/格式**：`resolve_conflicts`、`plan_alias`、`apply_naming`、`rename_glyphs`、`renamed_copy`、`alias_name`、`glyf_to_cff`、`cff_to_glyf`、`convert_font_format`、`create_glyph_subset`、`variable_to_static`、`apply_scale_offset`、`scale_font`、`union_axes`、`axis_union_merge`、`unwrap_webfont`；
- **轴数学/表/布局**：`AxisMapping`、`PiecewiseLinear`、`axis_mappings`、`evaluate_supports`、`refine_support_rebased`、`source_location`、`fvar_triples`、`avar_segments`、`merge_all_tables`、`merge_ot_features`、`prune_base_layout`、`LayoutUnion`、`MarkGlyphSetUnion`、`layout_glyph_names`、`offset_var_devices`、`remap_feature_variations`、`remap_glyph_names`、`resort_layout`、`VarStoreUnion`、`complete_vf_name_table`、`fix_head_flags`；
- **自检/检测/保存/工具**：`verify_merge`、`is_cff`、`is_ttf`、`is_variable`、`type_label`、`all_codepoints`、`glyph_to_codepoints`、`get_copyrights`、`get_family`、`axis_space`、`is_same_source`、`is_auto_glyph_name`、`AUTO_GLYPH_RE`、`EXEMPT_GLYPHS`、`save_font`、`assert_sfnt`、`SFNT_MAGICS`、`load_font`、`merge_fonts`、`DEFAULT_ANSWERS`、`SUPPORTED_EXTS`、`COLLECTION_EXTS`。
- 例外：`verify_composition` 未在包级导出（从 `FontMerger.core.verify` 导入）；`refine_1d`/`refine_support` 亦未导出。

### 1.3 两种入口

1. **CLI** `FontMerging.py:25 run()`：读主字体 + 多级打底（每级独立缩放%/基线偏移）→ `check_compatibility()` 告警确认 → 逐级 `merge_two()` → `apply_naming()` → `save_font()`；默认输出 `<主名>_mod.{otf|ttf}`（扩展名由结果轮廓类型决定），CLI 只是交互 UI。2. **库 API**：`merge_two(main, base)` 合并一级且**不做命名、不落盘**；`merge_fonts(main, [base...], interactive=False, answers=None)` 内部 deepcopy 主字体逐级合并 + 命名 + 清 flavor 后返回；`merge_subsets(paths, out_path=..., verify=...)` 走并集路径（`subsets[0]` 是基底且**就地修改**）。

### 1.4 交互问答与命名边界

问答由 `FontMerger.ask(key, q, opts)` 记忆到 `self.mem`（日志 `[记忆]`）；非交互用 `merger.mem = dict(DEFAULT_ANSWERS)` 预填（`__init__.py:66`，覆盖 10 个 key）。**命名不在 `merge_two()` 内**：Family → "<主字体名> mod"、版权合并由 `apply_naming()` 完成（CLI / `merge_fonts` / 示例脚本）。

## 2. 分层与依赖方向

### 2.1 分层图（箭头 = import 依赖）

```
FontMerging.py ──► __init__.py（门面/加载/便捷函数/再导出）
                     ├──► core/    （编排：16 路分派、注入、冲突、自检、同源并集）
                     │      ├──► format/（轮廓/轴/可变数据/CID/子集/变换）
                     │      ├──► tables/（布局归并、VarStore 并集、表级注册表）
                     │      └──► utils/ （检测、保存防护）
                     └──► format/、tables/、utils/（直接导出）；utils/ 无包内依赖，format/ 依赖 utils/，tables/ 内部互引
```

### 2.2 依赖规则

- **允许** `core/` → `format/`/`tables/`/`utils/`，`format/` → `utils/`，`tables/` 内部；`utils/` 只依赖标准库/fontTools。**应避免** `format/`→`core/`、`tables/`→`core/`、`utils/`→上层、同层循环；函数内延迟 import（如 `core/merger.py` 里 import `variation_compose`）是为打破环/缩短冷启动，不改变逻辑方向。

### 2.3 已知分层例外（代码事实 + 建议）

| 例外 | 证据 | 建议 |
| --- | --- | --- |
| `format/` → `tables/` | `format/cff2_compose.py` 的 `merge_cff2_var_stores()`（:282）、`merge_cff2_hvar()`（:347）函数内 import `..tables.varstore.VarStoreUnion` | 把 `VarStoreUnion` 下移到独立底层模块（`format/` 或新 `common/`），`tables/` 反向引用 |
| `tables/` → `core/` | `tables/cmap.py:3` import `..core.glyph_copy._copy_cmap_mappings` | 该函数是纯 TTFont 工具，移到 `utils/` |
| `format/` → `core/` | `format/cid_merge.py:202 cid_ufo_style_merge()` 内 import `..core.conflict.resolve_conflicts` | 把"码位/名称冲突判定"抽成 `format/`/`utils/` 纯函数，core 侧包装 |
| `tables/` 注册表与主流程脱节 | `tables/base.py:18 merge_all_tables()` 全仓库**无调用点**（只有定义/导出/注册表测试） | 接线进 `_do_merge_once()`，或明确标注为公开 API；见 §10 |

### 2.4 包结构约定

仓库目录名必须是 `FontMerger`（`FontMerging.py` 插父目录后 `from FontMerger import ...`）；`core/format/tables` 的 `__init__.py` 只做少量再导出并触发 handler 注册，完整 API 面以根 `__init__.py` 为准。

## 3. 合并主流程数据流

### 3.1 16 路分派（`core/merger.py:580 merge_two()`）

分类键 `ms=not is_variable(main)`、`mt=is_ttf(main)`、`bs/bt` 同理；方法后缀 `sOTF`=静态 CFF、`sTTF`=静态 glyf、`vOTF`=可变 CFF/CFF2、`vTTF`=可变 glyf。

| 主 \ 打底 | 静态 OTF | 静态 TTF | 可变 OTF | 可变 TTF |
| --- | --- | --- | --- | --- |
| **静态 OTF** | `_sOTF_sOTF` | `_sOTF_sTTF`（问导出，仅记忆） | `_sOTF_vOTF`（打底先实例化） | `_sOTF_vTTF`（打底先实例化） |
| **静态 TTF** | `_sTTF_sOTF`（问导出） | `_sTTF_sTTF` | `_sTTF_vOTF` | `_sTTF_vTTF` |
| **可变 OTF** | `_vOTF_sOTF`（问可变/静态） | `_vOTF_sTTF`（问可变/静态） | `_vOTF_vOTF`（`variable_source=b`） | `_vOTF_vTTF`（问 OTF/TTF） |
| **可变 TTF** | `_vTTF_sOTF`（问可变/静态） | `_vTTF_sTTF`（问可变/静态） | `_vTTF_vOTF`（问 OTF/TTF） | `_vTTF_vTTF` |

所有路径收敛到 `_do_merge()`：静态×静态 / 静态×可变传 `variable_source=None`（打底 VF 先 `variable_to_static`）；可变×静态先问"可变/静态"，选静态则 `variable_to_static(main)`；可变×可变传 `variable_source=b`（打底原始 VF）。**现状提醒**：交叉格式单元格的 "导出 TTF/OTF" 问答只记录答案，主流程不据此改写输出轮廓格式（输出格式由主字体决定，必要时**转换打底**，见 §3.3-4），与 README 矩阵描述存在偏差（§10.4）。

### 3.2 合成路径 vs 传统路径（`core/merger.py:608 _do_merge()`）

```
_do_merge(m,b,variable_source)
  ├─ 打底可变 且 compose_variations=True
  │     try: _do_merge_once(compose=True)          # 跨设计空间合成
  │     except Exception: print("[合成] 回退到默认实例合并: ...")
  │            └─► _do_merge_once(compose=False)   # 传统路径（安全网）
  └─ 否则: _do_merge_once(compose=False)
```

**触发回退的失败点**：`_apply_axis_plan()` 返回 `None` → `RuntimeError("轴空间无法规划")`；`instance_at_merged_default()`/`_transfer_base_layout_once()`/`_compose_cff2_base()` 抛异常；`verify_composition()` 抛 `AssertionError`（`core/merger.py:428`，轮廓容差 1、字宽 3.0）。**传统路径**（`compose=False` 且打底可变）：`_force_load_axis_tables()` → `_axis_union()`（`format/vf_axes.py:27`，就地扩主轴/加打底独有轴）→ `_reparametrize_main_after_union()` 重算主字体各 VarStore region（否则轴数不一致=非法字体）→ `axes_compatible()` 判轴空间与 avar 是否完全一致；不一致则 `variable_source=None` 且打底 `variable_to_static()`。**注意旧路径会就地修改主字体**（未 deepcopy），需要保留输入时调用方自行复制。
**回退后仍生效的能力**：`_finish_variable_merge()` 在 `plan=None, variable_source≠None` 时走 `transfer_glyph_variations()`（轴/avar 完全一致才 1:1 搬 gvar）；`_transfer_base_layout_once()` 失败只降级打底布局，不触发整体回退。

### 3.3 `_do_merge_once()` 的步骤（`core/merger.py:623`）

1. **预处理/合成准备**（仅 `variable_source≠None`）：
   - 合成路径：`m=deepcopy(main)` → `_normalize_upm()` 归一打底 → `_apply_axis_plan()`（`plan_axis_space` → 主 gvar/各 VarStore 重参数化 → `_copy_axis_records()` 写 fvar/avar/STAT/name）→ `instance_at_merged_default()` 得到"合并默认点上的打底"（缺的 master 由 instancer 插值，含幽灵点）→ `transfer_base_layout()`（打底布局变化）→ `_compose_cff2_base()`（打底 CFF2 blend）→ 打印 `collapsing_flats` 告警。
   - 传统路径：`_axis_union()` + `_reparametrize_main_after_union()` + 打底实例化（§3.2）。
2. **UPM 归一**（`_normalize_upm()`）：打底 UPM ≠ 主 UPM 时 `fontTools.ttLib.scaleUpem` 缩放打底（深拷贝）；**CID 归一**：主/打底 CID 组合见 §3.5。
3. **轮廓格式对齐**：`is_cff(m)!=is_cff(b)` → `convert_font_format(b, to_cff=is_cff(m))`；同为 CFF 时对齐 CFF/CFF2 版本（CFF2 主 + CFF 打底 → `convertCFFToCFF2`；反向 `_convertCFF2ToCFF`）。
4. **冲突检测与注入**：`plan_alias()` 给"自动名重名但不同源"的 `glyphNNNNN` 加别名（`renamed_copy()`）→ `resolve_conflicts()` → `to_add = 打底字形 - 冲突 - 主已有`；`to_add` 为空时 `_diagnose_empty_merge()` 给原因并返回主副本。
5. **字形注入**：`to_add ≤ 5000` 用 `merge_glyphs_via_ttx()`（glyf+glyf 走对象快路径，CFF/CFF2/CID 走 TTX 往返）；超过则 `_chunked_merge()`（§3.6）。注入异常 → 打印 `[合并失败]` 并返回主副本（**不是**合成回退）。
6. **可变数据收尾**（`_finish_variable_merge()`）：`_finish_cff2_hvar()` → 计算 `added_now`（含组件闭包补入）→ `plan≠None` 时 `reparametrize_gvar()` + `add_HVAR()` + 可选 `verify_composition()`，否则 `transfer_glyph_variations()`。
7. **打底布局合并**（`_merge_base_layout_once()`）：`merge_ot_features(result, base_font, to_add)`，失败只告警。
8. **返回**；命名与落盘由调用方负责（§1.4）。
> **关于"表合并"**：任务书中的"表合并"对应 `tables/base.py merge_all_tables()` + `TABLE_MERGE_REGISTRY`（head/hhea/vhea/OS/2/post/name/cmap/hmtx/vmtx/GSUB/GPOS/GDEF/fvar/avar/kern/maxp），但**当前 `_do_merge_once()` 不调用它**——主流程的表状态由注入编译、`merge_ot_features()`、`add_HVAR()` 与调用方的 `apply_naming()` 得到。注册表仍可被外部直接调用；`tests/test_merger.py:151 test_table_registry` 只验证 handler 已注册。详见 §10.4。

### 3.4 ASCII 流程图

```
调用方 → FontMerger.merge_two(m, b)               core/merger.py:580
   │  is_variable × is_ttf → 16 路方法矩阵（§3.1）
   ▼
_do_merge(m, b, variable_source)               core/merger.py:608
   ├─ 打底可变 且 compose_variations ── try ─────────────────┐
   │    _do_merge_once(compose=True)                         │ 异常（规划/自检失败）
   │      deepcopy → UPM 归一                                │ ──► 打印 [合成] 回退
   │      → _apply_axis_plan（轴空间 + 主重参数化）            │        │
   │      → instance_at_merged_default                       │        ▼
   │      → transfer_base_layout（布局变化）                  │ _do_merge_once(compose=False)
   │      → _compose_cff2_base（CFF2）                       │ （轴并集 + 打底实例化）
   └─ 否则 ──────────────────────────────────────────────────┘
   ▼ _do_merge_once 主体（两条路径共用）        core/merger.py:623
   1 _normalize_upm（打底 UPM → 主 UPM）
   2 CID 归一（4 分支；双 CID 直接返回，§3.5）
   3 轮廓格式对齐（CFF↔glyf；CFF↔CFF2）
   4 plan_alias + resolve_conflicts → to_add
   5 to_add=0 → 诊断后返回主副本
   6 注入 merge_glyphs_via_ttx（glyf 对象 / CFF TTX）；>5000 → _chunked_merge
   7 _finish_variable_merge：CFF2 HVAR → gvar 重参数化/搬运 → add_HVAR → verify_composition
   8 _merge_base_layout_once：merge_ot_features（修剪 + 并集）
   ▼ 调用方：apply_naming → save_font（清 flavor + 校验 sfnt 魔数）
```

### 3.5 CID 分支（`_do_merge_once` 内提前返回）

| 情形 | 处理 | 返回 |
| --- | --- | --- |
| 主 CID + 打底 CID/name | 双 CID：`cid_ufo_style_merge()`（打底 CID 偏移 `max_cid(main)+100` → 物化 CharStrings 对象复制 → 转 name-keyed → save→reload）；打底 name 先 `ensure_cid_format` 再走双 CID | **直接返回**（回填主 GSUB/GPOS/GDEF），不走可变收尾/布局合并 |
| 主 CFF2（非 CID）+ 打底 CID | 打底 `desubroutinize` + `convertCFFToCFF2`（保留 FDArray，注入时 fdSelectIndex 重映射） | 继续主流程 |
| 主 name-keyed CFF + 打底 CID | `cid_to_name(b)` 统一成 name-keyed | 继续主流程 |

### 3.6 分块合并（`core/merger.py:764`）

阈值 `CHUNK_SIZE = 5000`（`core/merger.py:745`）：每块调一次 `merge_glyphs_via_ttx()`，失败保留已成功部分（或返回主副本）；可变收尾与打底 OT 合并**只在全部块完成后做一次**。TTX 路径每块一次整字体往返，是 CFF 大字体主要慢点（§9）。

### 3.7 同源并集路径 `merge_subsets()`（`core/subset_merge.py:723`）

与 `merge_two()` 完全独立的实现（入口 `SameSourceSubsetMerger.merge()`，`:181`）：
1. 基底=`subsets[0]`；强制加载逐字形表、glyf `ensureDecompiled()`（复合组件惰性持有 GID，改序前必须展开）；同源校验 `is_same_source()`（≥2、全可变、fvar 轴空间一致、轮廓格式一致），CFF2 额外 `check_cff2_compatible()`。
2. 逐分片 `rename_map()`：自动名一律别名；cmap 派生名只在"该分片布局引用"时保留副本，否则去重。
3. **GDEF 先做**（`_merge_gdef`）：GPOS VariationIndex 依赖本分片 VarData 基址 → VarStore 并集返回 `var_offset`，MarkGlyphSets 并集返回索引重映射。
4. 轮廓/度量/变体：glyf 对象复制（组件改名）+ hmtx/vmtx + gvar；CFF2 CharStrings+FDSelect（`FDUnion`）；HVAR/VVAR 先做基址偏移（`_merge_variation_maps`）。
5. cmap 并集 + `_harmonize_cmap()`（每个 Unicode 子表按格式上限覆盖全部码位）。
6. GSUB/GPOS：`LayoutUnion.add_from()`（lookup 追加 + 名 remap + VariationIndex 偏移 + MarkFilteringSet 重映射）→ `finalize()`（同 tag feature 归并、排序、索引重写）。
7. 布局**在字形重排前** finalize（`:313` 注释）→ `_reorder_by_codepoint()` → `resort_layout()`；CFF2 再 `sync_glyph_order()` 同步 charset/FDSelect。
8. `_finalize_variation_maps()` 补全部字形映射、glyf 路径 `add_HVAR()` 由幽灵点重建 HVAR；随后 `_recalc_metrics()`、`complete_vf_name_table()`、`fix_head_flags()`，可选 `verify_merge()`，最后 `save_font()`。

## 4. 关键不变量（代码依赖的 OT/可变字体事实）

### 4.1 三层归一化与 avar 生效位置（`format/axis_mapping.py:4-11`）

`user --fvar 双段线性归一化--> pre --avar 分段线性--> norm`；OT 变体数据（gvar tuple 支撑 / VarStore region / HVAR 索引）的峰值都在 **post-avar 的 norm 空间**。`PiecewiseLinear.fvar(triple)` 建 norm→user（单侧轴 min==default 或 default==max 只建一半域，绝不能带平台段）；`PiecewiseLinear.avar(segments)` 是 pre→norm；`AxisMapping` 组合出 merged_norm↔user↔source_norm，并在**用户空间**钳制轴范围（`:192-193`）——不在归一化空间，否则域外会外推出不存在的 master。

### 4.2 OT `supportScalar` 语义（`format/axis_mapping.py:21-26`、`:430-533`）

- 某轴 `peak == 0` → 该轴被忽略（"该字体此轴恒定"用省略该轴表达）；`lower < 0 < upper`（跨默认点）的 tuple 被引擎**整条忽略** → 细化 hat 必须落在 0 的一侧，`refine_1d()` 强制保留 0 作为节点（`:371-375`；CHANGELOG 记录修复前偏差 0.625）。
- 支撑在合并域边界被截断 → 用 `start==peak` / `peak==end` 的"半 hat"；`refine_support_rebased()` 用包含-排除恒等式处理"源默认点 ≠ 合并默认点"（常数项并入默认 master）。

### 4.3 VariationIndex=（VarData 序号, **行号**）与行保持（`variation_compose.py:9-16`）

GPOS/GSUB 的 Device（`DeltaFormat=0x8000`）即 VariationIndex：`outer=VarData 序号`、`inner` = 该 VarData 的**行号（Item 索引）**（不是 region 序号）。引擎取该行增量向量与各列 region 标量点积 → **一行可承载多个 hat**（列=hat、行值=权重），所以 `reparametrize_var_store()` 可精确重参数化且**保持 ItemCount/行序**，所有 `(outer,inner)` 引用无需重写；并集时只需 outer 加基址。依据：`variation_compose.py:388-412` 的 rows 循环、`core/verify.py:584 _check_var_stores()` 的 `ItemCount` 校验。
> 坑：`tables/varstore.py` docstring 把 inner 说成"VarData 内的 region 序号"，与实现矛盾；以本小节为准（见 §10.4）。

### 4.4 gvar 多 tuple 可求和（`core/glyph_copy.py:184`、`variation_compose.py:121`）

gvar 一个字形可有多个 tuple，渲染时按 supportScalar 加权**求和**。故源 tuple 的一个 hat 可精确拆成合并空间多个 hat（`reparametrize_gvar()` 对每条 tuple 调 `_map_support_terms()` 生成多条新 tuple，增量按权重缩放、`None` 幽灵点保留）；HVAR 不参与该求和，需 `add_HVAR()` 从幽灵点重算。

### 4.5 CFF2 blend 布局与 vsindex（`format/cff2_compose.py:2-23`）

- blend 块：`[v_1…v_n, Δ_1…Δ_n（每个 region 一个）, n, "blend"]`；`n`=被混合值个数，`Δ` 个数由当前 `vsindex` 指向的 VarData 的 region 数决定（缺省取 Private DICT 的 vsindex，再缺省 0）。
- VarStore 重参数化保持 **VarData 序号** → 程序里的 `vsindex` 不需改写；并入别的字体时必须 `offset_cff2_vsindex()` 平移，并给"隐式引用"的程序补显式 `vsindex`（否则会取合并后主字体 Private 的 vsindex）。
- Private DICT 的 blend 值按 argType 分 `delta`（BlueValues/StemSnapH/V，每值一项）与 `number`（BlueScale/StdHW 等，平铺）；并集时 Private 的 vsindex/blend 折成默认值并删键（fontTools instancer 的既定假设，见 `offset_cff2_vsindex()` docstring）。
- 复制 CharString 必须把 `cs.private` 指向**合并字体**的 FD Private；`set_cff2_var_store()` 要把 topDict/CharStrings/所有 Private 的 `vstore` 指向同一 VarStoreData（instancer 有对象同一性断言）。

### 4.6 HVAR VarIdxMap 与 `NO_VARIATION_INDEX`

HVAR/VVAR 的 `AdvWidthMap` 等是**按字形名索引的 DeltaSetIndexMap**（值 `(outer<<16)|inner`）；fontTools 的 `VarIdxMap.preWrite` 按字形序逐个取值，**缺项直接 KeyError**，所以新增/合并后必须给全部字形显式映射，无增量用 `NO_VARIATION_INDEX=0xFFFF/0xFFFF`（`core/verify.py:300-317`）。实现：`core/glyph_copy.py:168 _extend_variation_maps()`、`inject_glyphs_xml()` 的 XML 补 Map、`cff2_compose.py:347 merge_cff2_hvar()`、`subset_merge.py:497 _finalize_variation_maps()`。

### 4.7 instancer 语义（`core/verify.py:58-76`）

实测：`instantiateVariableFont(user_limits)` **不套 avar**，`TTFont.getGlyphSet(location=...)`（渲染语义）会套 avar，二者可差 1 单位级。因此采样点只取各轴 min/default/max（avar 的三个不动点）；`verify_composition()` 用 `getGlyphSet(location=pos)` 比对（字宽天然带 HVAR）；合成默认点实例用 `instantiateVariableFont(..., optimize=False)`（含幽灵点）。

### 4.8 TTX 往返、post 3.0 字形名与保存防护

`core/glyph_copy.py:260 merge_glyphs_via_ttx()`：剥离打底 OT 表（防命名方案冲突）→ 主/打底 `saveXML` → `inject_glyphs_xml()` 在 XML 层注入（glyf/CFF CharStrings+FDArray/hmtx/vmtx/VarIdxMap/maxp）→ 子进程 `python -m fontTools ttx` 编译 → 重载。关键：**post 3.0 二进制不存字形名**，fontTools 载入时按 cmap 反推；刚注入的字形还没有 cmap 条目，名字会被重编号 → 注入函数返回 XML 的 `GlyphOrder`，载入后按位置 `setGlyphOrder(intended_order)` 恢复（`:306-313`）。CFF 注入时 FDArray 追加要同步修正 `fdSelectIndex` 偏移（`:57-78`）。
保存防护 `utils/save.py:31 save_font()`：保存前 `font.flavor=flavor`（None=桌面 sfnt），保存后读前 4 字节校验 `SFNT_MAGICS=(b"\x00\x01\x00\x00", b"OTTO", b"true")`——woff2 载入的 TTFont 会记住 flavor，`save("x.ttf")` 实际写出 wOF2。另有 `tables/head.py:40 fix_head_flags()` 清 `head.flags` WOFF2 残留 bit 11。

### 4.9 其它必须维护的同步约束（速查）

| 不变量 | 依据 |
| --- | --- |
| Coverage 按 GID 升序，且 PairValueRecord/MarkArray/RuleSet 等并行数组同序（含 Context/ChainContext F1、MarkBase/MarkLig/MarkMark、GDEF AttachList/LigCaretList） | `tables/layout_union.py:195 resort_layout()`（P4 清单） |
| 布局表引用字形必须存在；Extension 子表递归收集 | `tables/ot_merge.py:565 _lookup_glyphs_in_font()`、`core/verify.py:476 _check_layout_integrity()` |
| 主有 vmtx 时每字形必须有纵向度量（编译期 KeyError，缺失补 (0,0)）；`maxp.numGlyphs` == 最终字形数 | `core/glyph_copy.py` TTX/对象两路径、各注入/并集收尾 |
| 每个 VarStore 的 `RegionAxisCount` == fvar 轴数、VarRegionIndex/VariationIndex 不越界；avar `segments` 覆盖**每条** fvar 轴（无映射补恒等段，否则 compile KeyError） | `core/verify.py:584`、`core/merger.py:179-191`、`format/vf_axes.py:79` |
| CFF2 charset/FDSelect 与最终字形序一致（CFF2 无 charset 表，编译按 top.charset 取 CharStrings） | `format/cff2_union.py:234 sync_glyph_order()` |
| FeatureList 重排后重写 Script/LangSys/FeatureVariations 的 FeatureIndex；LookupFlag bit4 的 MarkFilteringSet 是 GDEF MarkGlyphSetsDef 下标、并集后必须重映射 | `tables/ot_merge.py:415`、`tables/layout_union.py:301/359`、`core/verify.py` |
| 轴数变化前先把 gvar/HVAR/VVAR/MVAR/cvar/avar/STAT 读进内存（否则 reader 里是旧轴数二进制） | `core/merger.py:437 _force_load_axis_tables()` |
| cmap 子表受格式上限约束（0/4/6/12），合并后按上限 harmonize | `core/subset_merge.py:69 _CMAP_LIMITS`、`:374 _harmonize_cmap()` |

## 5. 模块地图

行数为写作时 `wc -l`；"关键入口"= 修改该文件时先看的函数/类。

| 层 | 文件（行数） | 职责 | 关键入口 |
| --- | --- | --- | --- |
| 顶层 | `__init__.py`(121)、`FontMerging.py`(161) | 包门面：版本/常量/`DEFAULT_ANSWERS`/加载/便捷函数/全量再导出；交互式 CLI（输入/校验/缩放偏移/兼容确认/逐级合并/命名/保存） | `load_font()`、`merge_fonts()`、`run()` |
| utils | `utils/detect.py`(103)、`utils/save.py`(62) | 类型检测/码位/版权/family/轴空间/同源判定/自动名识别；保存防护（清 flavor、sfnt 魔数、按扩展名推断 flavor） | `is_same_source()`、`axis_space()`、`save_font()`、`default_flavor_for()` |
| core | `core/merger.py`(852) | 16 路分派；合成/传统路径；CID/格式归一；注入编排；可变收尾；分块 | `merge_two()`、`_do_merge()`、`_do_merge_once()`、`_apply_axis_plan()`、`_finish_variable_merge()` |
| core | `core/glyph_copy.py`(359) | 字形注入两条路径：TTX XML 往返（CFF/CFF2/CID）与 glyf 对象复制；cmap 并集；VarIdxMap 补齐 | `merge_glyphs_via_ttx()`、`merge_glyphs_object()`、`inject_glyphs_xml()` |
| core | `core/subset_merge.py`(776) | 同源分片并集：改名、逐字形复制、cmap/GDEF/布局/VarStore/HVAR/VVAR、重排、度量重算 | `SameSourceSubsetMerger.merge()`、`merge_subsets()`、`glyph_map()` |
| core | `core/verify.py`(647) | 两套自检（`verify_merge` / `verify_composition`）+ 布局/VarStore 结构检查 | `verify_merge()`、`verify_composition()`、`_check_layout_integrity()`、`_check_var_stores()` |
| core | `core/conflict.py`(45)、`core/glyph_rename.py`(141)、`core/naming.py`(32) | 冲突判定与自动名别名；同步重命名字形；Family→"<main> mod"/版权合并/MacRoman 清理 | `resolve_conflicts()`、`plan_alias()`、`rename_glyphs()`、`apply_naming()` |
| format | `format/axis_mapping.py`(553) | 轴映射数学：三层归一化、分段线性复合/逆、hat 分解/重定基、平台段检测 | `AxisMapping`、`PiecewiseLinear`、`refine_1d()`、`refine_support_rebased()` |
| format | `format/variation_compose.py`(426) | 轴空间规划、按合并默认点实例化、gvar/VarStore 重参数化（行保持）、布局变化迁移 | `plan_axis_space()`、`instance_at_merged_default()`、`reparametrize_gvar()`、`reparametrize_var_store()`、`transfer_base_layout()` |
| format | `format/cff2_compose.py`(438) | CFF2 blend/vsindex 重参数化、Private blend、VarStore/HVAR 并集、vsindex 平移 | `reparametrize_cff2()`、`merge_cff2_var_stores()`、`merge_cff2_hvar()`、`offset_cff2_vsindex()` |
| format | `format/cff2_union.py`(250) | 同源 CFF2 结构签名校验、FDArray 并集、字形复制、charset/FDSelect 同步 | `check_cff2_compatible()`、`FDUnion`、`copy_glyphs()`、`sync_glyph_order()` |
| format | `format/vf_axes.py`(186) | 轴并集：扩 min/max、追加打底独有轴、STAT/avar/各 VarStore region 轴扩展 | `union_axes()`、`_extend_avar_axes()`、`_extend_varstore_regions()` |
| format | `format/converter.py`(252)、`format/static_extract.py`(98) | glyf↔CFF（Cu2Qu/Qu2Cu, max_err=1.0）+ Windows/Office 修复；VF→默认轴静态实例、CFF2→CFF、可选 removeOverlaps | `convert_font_format()`、`glyf_to_cff()`、`cff_to_glyf()`、`variable_to_static()` |
| format | `format/cid_convert.py`(246)、`format/cid_merge.py`(231) | CID↔name-keyed 归一（Adobe-Identity-0）；双 CID 偏移合并（物化 CharString、save→reload） | `ensure_cid_format()`、`cid_to_name()`、`cid_ufo_style_merge()` |
| format | `format/transform.py`(206)、`format/subsetter.py`(42)、`format/webfont.py`(8) | 缩放+基线偏移（Pen 重建轮廓+同步度量）；字形子集（可剔布局表）；WOFF/WOFF2 解包 | `scale_font()`、`apply_scale_offset()`、`create_glyph_subset()`、`unwrap_webfont()` |
| tables | `tables/base.py`(41) | 表级合并调度器 + `@register(tag)` 注册表（**主流程未调用**，§3.3 注） | `merge_all_tables()`、`register()`、`TABLE_MERGE_REGISTRY` |
| tables | `tables/ot_merge.py`(600) | 打底 GSUB/GPOS/GDEF 的 Subsetter 闭包修剪 + 逐表并集（主流程实际使用） | `merge_ot_features()`、`prune_base_layout()`、`merge_base_layout()` |
| tables | `tables/layout_union.py`(638) | 深度 remap、VariationIndex 偏移、按 tag feature 并集、Script/LangSys、FV 重写、Coverage 重排 | `LayoutUnion`、`MarkGlyphSetUnion`、`resort_layout()`、`offset_var_devices()` |
| tables | `tables/varstore.py`(81)、`tables/name_table.py`(60)、`tables/head.py`(48) | ItemVariationStore 并集（region 去重/VarData 拼接/outer 基址）；补 nameID 16/17/25+实例 PS 名；清 WOFF2 残留 bit | `VarStoreUnion.add()/build()`、`complete_vf_name_table()`、`fix_head_flags()` |
| tables | `tables/{_strategies,hhea_vhea,os2,post,maxp,cmap,kern,otlayout,fvar_avar,metrics}.py` | 表合并策略函数与注册表 handler（仅当外部调用 `merge_all_tables()` 时生效） | 各 `@register` 函数 |
| tests/build | `tests/test_merger.py`(781)、`tests/test_axis_mapping.py`(514)、`tests/test_subset_merge.py`(346)、`tests/test_cff2_compose.py`(250) | 四套用例 21/13/8/4（覆盖见 §8.1） | `main()` |
| tests/build | `tests/subset_fixture.py`(117)、`tests/cff2_fixture.py`(56)、`tests/generate_matrix.py`(154)、`tests/generate_samples.py`(245) | pyftsubset 分片/rich VF/CFF2 夹具；16 组合矩阵；6 个样例 | `cached_subsets()`、`cached_cff2_pair()` |
| tests/build | `build/make_release_zip.py`(118)、`build/build_exe.py`(51) | 仅源码发布包（git 跟踪文件+HEAD 时间戳+sha256）；PyInstaller（**布局过时**，§10.4） | `main()`、`build()` |

## 6. 可变字体合成子系统（阶段 0–4）

### 6.1 阶段与模块

代码里只有**阶段 0**（`tests/test_axis_mapping.py` 头注释）与**阶段 4**（`format/cff2_compose.py` 头注释）有显式标注；1–3 的边界由 CHANGELOG 条目与模块职责归纳（仓库无单独阶段文档）：

| 阶段 | 内容 | 代码位置 |
| --- | --- | --- |
| 0 | 轴映射数学：三层归一化、hat 精确分解/重定基、平台段、VarStore 行保持 | `format/axis_mapping.py`；`tests/test_axis_mapping.py` |
| 1–2 | 合并轴空间规划 + 按合并默认点实例化（缺 master 由幽灵点插值）；gvar 重参数化、主字体 gvar/各 VarStore 重算、HVAR 重建 | `plan_axis_space()`、`instance_at_merged_default()`、`reparametrize_gvar()`、`core/merger.py:359 _apply_axis_plan()`、`:299 _map_main_var_stores()` |
| 3 | 打底布局变化迁移（GDEF ItemVariationStore + GPOS VariationIndex，行保持） | `variation_compose.py:223 fold_layout_default()`、`:265 transfer_base_layout()` |
| 4 | CFF2：blend/vsindex 重写、Private blend、VarStore/HVAR 并集、vsindex 平移 | `format/cff2_compose.py`；`core/merger.py:223 _compose_cff2_base()`、`:264 _finish_cff2_hvar()` |

### 6.2 数学核心（`format/axis_mapping.py`）

- `PiecewiseLinear`：`fvar()` 建 norm→user（单侧轴只建一半域）；`avar()` 建 pre→norm；`compose()` 断点 = 二者断点 ∪ self 断点在 other 下的原像；`inverse()` 平台段取右端；域外按平移规则外推。`AxisMapping` 预组合 `merged_norm↔user↔source_norm`，`to_source()/to_merged()` 都做用户空间钳制；`kinks_merged()` 汇总折点（fvar 端点/默认点、两边 avar 折点、钳制点、平台段两端）；`collapsing_flats()` 报"合并 avar 把用户区间压成一点"；`is_identity()` 判恒等。
- `refine_1d(lower, peak, upper, mapping, shift=...)`：节点 = 域边界/钳制点/支撑像端点与峰/映射断点/0；节点基函数即 OT hat；删共线冗余节点但**保留 0**；端点越界用半 hat；`shift` 为重定基量。`refine_support_rebased(support, mappings)`：剔除 OT 忽略轴 → `reachable_range()` 判"永远达不到 → 恒 0" → 包含-排除恒等式逐轴细化 + 笛卡尔积，返回 `(constant, terms)`；`refine_support()` 是不重定基的简化版。

### 6.3 规划、实例化、重参数化（`format/variation_compose.py`）

- `plan_axis_space(main, base, range_policy, avar_mode)`：合并 fvar = 主轴（`union` 时共有轴取并集）+ 打底独有轴（`main` 时丢弃）；合并 avar = 主 avar 优先、缺则打底（`avar_mode=1` 忽略打底，`=2` 不用 avar）；返回 `(merged_fvar, merged_avar, base_maps)`。
- `reparametrize_gvar(merged_font, source_font, mappings, glyph_names, fit)`：对每字形每条 tuple，`exact` → `refine_support_rebased()` 拆多条新 tuple（增量乘权重，`None` 幽灵点保留）；`affine` 只映射端点/峰（紧凑但有偏差，通常被自检拒绝）。
- `region_split_plans(...)` 把源 region 转成合并空间列计划：`constant_column=True` 用"全轴 peak=0 恒定 region"承载默认点常数 C（GPOS 只能这样表达），`False` 时把 C 返回给调用方折进静态值（CFF2 blend 默认值）。`reparametrize_var_store(...)` **行保持**——ItemCount/行序不变，每行按列计划重分配到新列；`_num_shorts()` 维护 `wordDeltaCount`。
- `fold_layout_default()`：官方 `instantiateItemVariationStore` 求合并默认点增量，`MutatorMerger(deleteVariations=False)` 把增量折进 GPOS/GDEF 静态值但保留设备；随后 `transfer_base_layout()` 把 GDEF VarStore 换成 `folded_default=True` 的重参数化版本，二者相加即逐点等价。

### 6.4 CFF2 的同一套数学（`format/cff2_compose.py`）

`reparametrize_cff2()`：CFF2 VarStore region → `region_split_plans(folded_default=False)`（常数 C 由 blend 默认值承载）；所有出现 blend 的程序（CharStrings + GlobalSubrs + 各 Private.Subrs，`_programs()`）逐 token 重写；Private DICT blend 按 argType 重写；最后 `set_cff2_var_store()`。`merge_cff2_var_stores()`：主 VarStore 先按合并空间重算（或仅尾部追加恒定轴），再与打底 VarData 拼接（主在前），打底 vsindex 加基址。`merge_cff2_hvar()`：打底 HVAR（folded_default=True）并进结果，按**字形名**重建 AdvWidthMap，只有真正来自打底且非 `NO_VARIATION_INDEX` 的字形才偏移 outer。

### 6.5 合成自检与回退

`verify_composition()`（`core/verify.py:404`）：在合并轴网格（默认 `max_positions=6`，调用方 4）上用 `getGlyphSet(location=pos)` 逐点比对新字形 vs 打底、主字形 vs 主字体；轮廓容差 1 单位、字宽默认同容差（调用方传 3.0），失败抛 `AssertionError` → `_do_merge` 回退传统路径。采样默认 30 字形（主流程调用即默认）。**回退是异常驱动的**，日志固定 `[合成] 回退到默认实例合并: <原因>`。

### 6.6 策略参数（`FontMerger.__init__`，`core/merger.py:546`）

| 参数 | 默认 | 作用 |
| --- | --- | --- |
| `compose_variations` | `True` | 合成总开关；关 = 直接传统路径 |
| `compose_range` | `"main+extra"` | `"union"` 共有轴取并集；`"main"` 只保留主轴（打底独有轴被钳掉） |
| `compose_fit` | `"exact"` | `"affine"` 只做仿射拟合（体积小、有偏差） |
| `avar_mode` | `0` | 0=尊重主 avar；1=忽略打底 avar；2=完全不用 avar（删表） |
| `verify_compose` | `True` | 合成后跑网格自检，失败回退 |
| `compose_layout` | `True` | 打底布局变化一并搬运；关 = 打底布局冻结在合并默认点 |

### 6.7 已知缺口（README "Known Limitations" #2 + 代码事实）

要求主/打底可变数据在**同一种轮廓技术**（glyf 两边都要 gvar；CFF2 两边都要带 VarStore 的 CFF2），glyf↔CFF2 混搭仍回退实例化；CFF2 路径只并入打底 HVAR，**VVAR 与 Private hint 变化保持静态**（hint blend 折默认值）；合并 avar 取主字体的，主轴把用户区间压成一点时该区间无法逐点等价（`collapsing_flats()` 检测+告警，可试 `avar_mode=2`）；布局 VariationIndex 增量取整后 kerning/anchor 变化可能差约 1 单位（实测 0.70 @ UPM 1000，可用 `compose_layout=False` 保持旧行为）；异源路径**不并入打底自己的 FeatureVariations**。

## 7. 布局合并子系统

### 7.1 异源路径（主流程实际使用，`tables/ot_merge.py`）

```
merge_ot_features(main, base, kept_glyphs)        tables/ot_merge.py:585
  ├─ prune_base_layout(base, kept)                :41
  │    deepcopy 打底 → Subsetter(populate=kept∪.notdef, layout_features=["*"],
  │    notdef_outline=True, name_IDs=[]) → ss.subset() 闭包+布局修剪
  │    → 只提取 GSUB/GPOS/GDEF 到新 TTFont（轮廓作废）
  └─ merge_base_layout(main, base_pruned, kept)   :100
       ├─ GDEF：字类主优先；MarkGlyphSetsDef/VarStore 并集（索引/outer 重映射）
       ├─ 主无 GDEF/GSUB/GPOS → 整体采用打底（GDEF 按主字形集过滤）
       └─ GSUB/GPOS：_merge_gsub_gpos()          :261
            lookup deepcopy → 名重映射 → 全引用必须在主字体（Extension 递归）
            否则跳过 → VariationIndex/bit4 重映射 → 同 (tag, FeatureParams) 并入
            主记录或新增 → Script/LangSys 并入 → FeatureList 排序 → FV 索引重写
            → resort_layout()
```

### 7.2 同源并集路径（`tables/layout_union.py`）

`LayoutUnion(tag).add_from(base_table, ren, var_offset, mark_set_remap)`：整表 deepcopy lookup → `remap_glyph_names()` 深度改名 → `offset_var_devices()` → MarkFilteringSet 重映射 → lookup 索引整体后移；同 tag feature 按签名归并；`finalize()` 合并 feature、按 tag 排序、重写 Script/LangSys 索引、重建 FeatureVariations（条件集相同则合并替换表并取 lookup 并集）。

### 7.3 冲突规则

主字体已有同 tag feature → 打底 lookup 并集进主记录（不整条跳过，FeatureParams 不同另立记录）；打底 lookup 引用任一不存在于主字体的字形 → 整条跳过（宁缺勿坏）；GDEF 字类主值优先、打底只补主缺失字形（否则新增字形丢失 mark/base 分类）；打底 FV 在异源路径不并入，主 FV 重排后重写索引、无法映射才整体丢弃。

### 7.4 `resort_layout()`

字形序变化后的统一收尾（`layout_union.py:195`）：覆盖 §4.9 首行的 P4 项，`sort_coverage_with()` 重排 Coverage+并行数组、`_fix_subtable_order()` 按子表分派。任何改动字形 GID 的路径**都必须**在保存前调用它（TTX 往返由编译器重排）。

## 8. 测试架构

### 8.1 四套用例（46 个）

| 套件 | 数量 | 覆盖什么 | 依赖字体 |
| --- | --- | --- | --- |
| `tests/test_merger.py` | 21 | 类型检测、冲突/自动名别名、命名、注册表完整性、OTF/TTF 代表性合并、高层 API、保存防护、字形改名、VF→静态保真、同 tag feature 并集、无悬空布局引用、CFF2→CFF、MarkGlyphSets/FV 保留、轴一致时 gvar 搬运、跨设计空间合成/回退/主 VarStore/打底布局变化、真实 VarStore 重参数化 | 是（缺字体 SKIP） |
| `tests/test_axis_mapping.py` | 13 | 纯数学（阶段 0）：PiecewiseLinear/fvar/avar、恒等/范围/avar/多轴细化、重定基、边界截断、跨 0、平台段、随机压力、VarStore 行保持的 6 种形态 | 部分（真实 avar 用例） |
| `tests/test_subset_merge.py` | 8 | 同源判定、并集 roundtrip（码位/可变性/特性/gvar/GDEF/vmtx/name/head）、落盘重载、`verify_merge`、CFF2 分片、异源拒绝、glyph_map、MarkGlyphSets/FV 索引 | 是 |
| `tests/test_cff2_compose.py` | 4 | CFF2 恒等重参数化、vsindex 偏移/补插、轮廓+Private blend 重写（保存/重载）、CFF2×CFF2 跨设计空间合并 | 是 |

### 8.2 夹具生成方式

- `tests/subset_fixture.py`：`make_subsets()` 调 `python -m fontTools.subset` 按 `cps[i::n]` 切 N 份（`--layout-features=* --no-hinting --desubroutinize --flavor=woff2`），进程内 `_CACHE` 缓存；`make_rich_vf()` 用 fontTools 官方 API 给 VF 追加 `MarkGlyphSetsDef` + `LookupFlag` bit4 指向 + `FeatureVariations`(rvrn)——专门覆盖合并最容易搞坏的两类结构。
- `tests/cff2_fixture.py`：把 CFF2 VF 切成字形不相交的 main/base 两片，并改打底 fvar 的 wght/opsz 范围与默认值 → 归一化空间不同，强制走合成；用 `.fixed` 标记文件避免重复改轴。夹具均为生成物：webfont 分片不随仓库分发，仓库不放任何字体文件。

### 8.3 SKIP 语义与运行器

缺字体时用例打印 `SKIP (测试字体未就位)` 并**正常返回**；`main()` 把正常返回计为 passed（"21/21 passed" 可能包含 SKIP；[AGENTS.md](AGENTS.md) §4 要求汇报时列出 SKIP 与原因）。授权字体经不入库的 `tests/local_fonts.py` 角色解析（模板 `tests/local_fonts.example.py`），OFL 字体直接写相对 `tests/../test/` 的路径；**文档不写授权字体名、不读其内容**。

### 8.4 16 组合矩阵与样例生成器

- `tests/generate_matrix.py`：产出 `A1–A4 / B1–B4 / C1–C4 / D1–D4` 共 16 个文件到 `test/samples/matrix`，打印字形数/体积/轴信息；缺任一字体整体跳过（exit 0）。**C1/D1 主动降级为静态路径**（JP CID CFF2 作主字体保存期 cmap format 4 引用不完整，README Known Limitations #1）。
- `tests/generate_samples.py`：6 个使用样例（OTF+OTF、TTF+TTF、混合格式转换、VF 实例化+合并、三级合并、`merge_fonts`）。`build/make_release_zip.py`：`git ls-files` 收源码 + 4 个根文档 → `dist/font-matrix-merger-v<版本>.zip`；版本取 `__init__.py`，zip 时间戳固定 HEAD 提交时间（可复现），防御性拒绝字体/中间产物扩展名。

### 8.5 验证门

纯文档改动：无测试但须事实核查（本文件即此类）。代码改动：四套全绿（21/13/8/4），涉及合成时确认 `verify_composition` 断言仍生效（不得关 `verify_compose` 换绿灯），详见 [AGENTS.md](AGENTS.md) §4。

## 9. 性能与资源

> 只引用仓库内实测数字；无实测处标注结构性成本。

1. **glyf 注入快路径**：`merge_glyphs_object()` 逐字形对象复制，避免整字体 TTX 往返。README 实测："给 25k 字形主字体加 135 个字形：153 s → 3.7 s"（`README.md` 第 66 行；`core/glyph_copy.py:184` docstring 亦记"整字体 TTX 往返实测约 150 秒"）。
2. **TTX 路径成本**：CFF/CFF2/CID 走 `saveXML→注入→ttx 编译`，代价与**整个字体规模**成正比；`subprocess` 超时 300 s/次（`core/glyph_copy.py:300-304`）；分块阈值 5000 字形（`core/merger.py:745`）控制单次注入峰值内存/对象数，跨块共享的打底布局合并只做一次；分块时每块一次整字体往返（§3.6），是 CFF 大字体主要慢点。
3. **元组/列膨胀**：`compose_fit="exact"` 把一个源 hat 拆成多个合并空间 hat，跨轴细化是各轴项数的笛卡尔积，`compose_range="union"` 时"剪枝前元组数最多可达 ×28"（README 参数表），`refine_1d()` 剪共线节点/零权重项控制膨胀；VarStore 每个源 region 可能变多列、行数不变，`NumShorts` 决定 int16/int8 编码，改列后必须重算（`_num_shorts()`）。
4. **deepcopy 与内存**：对象复制路径（主 + 剥离 OT 的打底副本 + 结果）、合成路径（`m` 副本 + 打底实例 + `variable_source` 副本）、CID 路径（再 save→reload）都产生多份字体对象；峰值内存 ≈ 主字体 2~3 份 + 打底，分块每块还会 deepcopy 当前结果。
5. **自检/夹具成本**：`verify_merge()` 默认在"默认位置 + 首轴两端"逐字形实例化比对（`sample` 可抽样，测试用 120~250）；`verify_composition()` 默认 6 网格点 × 30 字形（主流程 4 点）；`_check_layout_integrity()`/`_check_var_stores()` 是对象树遍历，随布局表规模线性增长；测试夹具进程内缓存 pyftsubset 产物，避免重复切分。

## 10. 扩展点与架构债

### 10.1 加一张表怎么加

当前有两条**互不相通**的"表合并"路径，先决定接哪条：① 只影响元数据/度量的表（如新的 name/OS/2 派生字段）→ `tables/<tag>.py` 写 `@register("<tag>")` handler → `tables/__init__.py` import 触发注册 → `tests/test_merger.py:151` 的 expected 集合补 tag；**注意** handler 只有外部显式调 `merge_all_tables()` 才跑，`merge_two()` 主流程不调，要进主流程得在 `_do_merge_once()` 尾部接线并补回归。② 字形级/可变数据表 → 通常不能只靠 handler：字形注入由 `core/glyph_copy.py`/`core/subset_merge.py` 负责，可变数据由 §6 模块负责；加表意味着同时改注入与合成路径，并在 `core/verify.py` 加结构校验。

### 10.2 加一种布局结构（lookup 子表/新属性）

1. 含 Coverage/并行数组 → 在 `layout_union.py:128 _COVERAGE_ATTRS` 补属性名，并在 `_fix_subtable_order()` 加子表类型分支（否则 GID 重排后 HarfBuzz 静默出错）；2. 字形名引用 → `remap_glyph_names()` 是通用深度遍历（dict/list/对象），通常无需改，但要确认新结构不是"按 GID 索引的并行数组"；3. 带 VariationIndex → `offset_var_devices()` 已覆盖任意对象树里的 `ot.Device`，并集时传入正确 `var_offset`；4. 自检 → `_check_layout_integrity()` 按白名单收集引用（`glyphs/Substitute/SecondGlyph/Component/Input/Backtrack/LookAhead/classDefs/mapping/ligatures`），新属性要补白名单；5. 测试 → 仿 `subset_fixture.make_rich_vf()` 造"易被合并搞坏"的夹具并补同型断言。

### 10.3 加一种轮廓技术/可变数据

- 轮廓转换：`format/converter.py`（glyf↔CFF 已有；**VF-aware 的 glyf↔CFF2 转换不存在**，这是 glyf↔CFF2 合成无法支持的直接原因）。
- 同源分片：`format/cff2_union.py` 是样板（结构签名 → 拒绝不可零重定位的输入 → FD 并集 → 逐字形复制 → sync 字形序）；新格式照此加 `check_*_compatible/copy_glyphs/sync_*`。
- 异源合成：在 `format/variation_compose.py` 加"数据→合并空间"的重参数化函数，在 `core/merger.py:_finish_variable_merge()` 接线，并在 `core/verify.py` 补自检；保持"失败抛异常 → `_do_merge` 回退"的契约。

### 10.4 架构债清单（有证据）

| 项 | 证据 | 影响/建议 |
| --- | --- | --- |
| 表级注册表未接入主流程 | `tables/base.py:18 merge_all_tables()` 全仓库无调用；`_do_merge_once()` 直接返回 | 两套表合并语义并存（`tables/otlayout.py`"主有则整体保留" vs `tables/ot_merge.py`"lookup 并集"）；建议接线或标注为独立 API |
| 重复实现（轴并集/cmap 拷贝） | `format/vf_axes.py union_axes()`（主流程）vs `tables/fvar_avar.py merge_fvar()`（注册表，语义更简单）；`core/glyph_copy.py _copy_cmap_mappings()` vs `core/subset_merge.py _merge_cmap()` | 改轴语义要记得两处；建议统一到 `vf_axes` 并抽公共 cmap 工具 |
| 导出格式问答未生效 | `_sOTF_sTTF/_vOTF_vTTF` 等调 `ask()` 后丢弃返回值；实际输出由主字体轮廓决定 | 与 README 矩阵描述不一致；实现转换或在文档/提示中说明"仅记录" |
| 文档/注释与代码不一致 | ① `README.md` 的 "Pure FontTools pipeline" 条目（第 30 行）与 `README.zh-CN.md` 第 27 行曾称字形注入只走 TTX 往返（同文件第 66 行已写 glyf 对象快路径 153→3.7 s）；② `tables/varstore.py` docstring 曾把 VariationIndex 的 inner 说成 region 序号（实为行号） | ✅ ①② 已由 Lead 在本轮修掉（两个 README 的 pipeline 条目 + docstring），并在合并矩阵下方补了“导出格式询问仅记录”的说明；无需再跟 |
| 双 CID 的 cmap 可能残留旧字形名（**未验证**） | `format/cid_merge.py:74-77 shift_cid_range()` 的 cmap 循环体是 `pass`，注释称“names already updated”，但 fontTools 的 cmap 存的是字形名字符串，不会随 `setGlyphOrder`/charset 自动更新；若后续合并未重建 cmap，映射会指向旧名 | 需补双 CID 回归用例（含 cmap format 14 UVS）后再修：`table.cmap = {cp: mapping.get(gn, gn) ...}` + `uvsDict` 同步；在此之前不要声称双 CID cmap 已验证 |
| 死代码/过时构建脚本 | `core/merger.py:457 _remove_ros()`、`:472 _add_cid_prefix()` 无调用，`create_glyph_subset` 被 import 未用，`format/cid_convert.py:242 ensure_name_format()` 无调用；`build/build_exe.py` 入口指向根目录不存在的 `merge_fonts.py` 且假设"工程根≠包根" | 清理/重建前确认下游依赖；与 README 限制 6（pip 化未接线）同源，重建打包脚本前不要承诺 exe |
| 传统路径就地修改主字体 | `compose=False` 分支 `_axis_union()` 直接改 `m`（未 deepcopy）；合成路径才 deepcopy | 上层需保留输入时自行复制（测试/生成器均如此）；建议文档化或入口统一复制 |
| 单文件较大、职责集中 | `core/merger.py` 852 行、`core/subset_merge.py` 776 行、`tables/layout_union.py` 638 行 | 新功能优先放 `format/`/`tables/` 独立模块，再在 core 接线 |

### 10.5 建议的下一步（与 README/CHANGELOG 口径一致）

1. **可变数据覆盖**：glyf↔CFF2 混搭合成（当前回退实例化，需 VF-aware 轮廓转换 + 两侧同时重参数化，§6.7）；VVAR 支持（异源路径只重建 HVAR，CFF2 的 VVAR/私有 hint 变化仍静态，README #2）。
2. **JP（CID CFF2）作主字体**：保存期 cmap format 4 引用问题未解（README #1，矩阵 C1/D1 走静态路径）。
3. **pip/PyPI 化与 CI**：仓库根即包、无 CI 配置，`build/build_exe.py` 需随布局重写（README #6）；§10.4 的文档不一致项已在 [Unreleased] 修掉，后续把 §2.3 分层例外列为评审检查项。

### 10.6 改代码前自检清单

- 改了字形 GID/字形序 → 保存前 `resort_layout()`（CFF2 额外 `sync_glyph_order()`）；改了轴/区域 → `_check_var_stores()` 不报错、每个 VarStore 的 `RegionAxisCount` == 新 fvar 轴数、avar `segments` 覆盖全部轴。
- 改了 HVAR/VVAR 映射 → 全部字形都有映射项（无变化用 `NO_VARIATION_INDEX`）；改了布局 → `_check_layout_integrity()` 无悬空/未排序/越界、`verify_merge()` 的 feature 覆盖不减少。
- 改了合成数学 → `tests/test_axis_mapping.py` 13 个数学用例 + `verify_composition` 自检仍生效（不允许用 `verify_compose=False` 掩盖失败）；四个测试套件 21/13/8/4，缺字体 SKIP 要如实汇报。
