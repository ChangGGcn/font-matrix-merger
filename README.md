# font-matrix-merger

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![FontTools](https://img.shields.io/badge/fontTools-%E2%89%A54.49-important.svg)]()
[![Version](https://img.shields.io/badge/version-0.1.0--alpha1-orange.svg)]()

**English** | [简体中文](README.zh-CN.md)

**font-matrix-merger** is a powerful Python library for merging multiple fonts into one, covering every combination of **static / variable × OTF / TTF** for both the main font and the base fonts — with format conversion, CID-keyed CFF handling, OpenType feature merging, variable-font axis unions, scaling and baseline offsets, and multi-level (n-step) chained merges.

## About

The library is built on top of [**FontTools**](https://github.com/fonttools/fonttools) (MIT) — used for all glyph/table-level manipulation, CFF/CFF2 conversion, varLib instancing and subsetting — and follows the conventions of [**AFDKO**](https://github.com/adobe-type-tools/afdko) (Adobe Font Development Kit for OpenType, Apache-2.0), which is bundled in the project's PyInstaller build pipeline and referenced for its CID-keyed UFO / CIDMap remapping approach.

Key highlights:

- **16-way merge matrix**: `merge_two()` auto-dispatches to the right strategy for any main/base combination.
- **Same-source subset union**: `merge_subsets()` rebuilds **one variable font** from the per-`unicode-range` webfont subsets of a single VF — **glyf and CFF2** outlines, `gvar`/CFF2 blends (`vsindex` + FDSelect/FDArray), `hmtx`/`vmtx`, `cmap`, GSUB/GPOS lookups (per-tag **feature union**), the GDEF `ItemVariationStore`/`MarkGlyphSetsDef` and `HVAR`/`VVAR` are all carried over, so weight interpolation and `vert`/`vrt2`/`kern`/`mark` survive.
- **Merge self-check**: `verify_merge()` instances sources and result at several axis positions and compares outline/metrics glyph by glyph, then asserts codepoints, features, layout integrity and container metadata.
- **Save guard**: every save point goes through `save_font()`, which clears `flavor` and asserts the sfnt magic — a woff2-loaded font can no longer be written as an `x.ttf` file with `wOF2` magic.
- **Multi-level chaining**: a main font plus 1..n base fonts, merged level by level; format/export questions are asked only once (answer memorization).
- **CID-aware**: dual-CID fonts are merged via CID offset + materialized CharString copy; CID↔name-keyed normalization is handled automatically.
- **Variable fonts**: a variable main font stays variable in the output, with axis **union** across main and base fonts (fvar/avar/STAT synchronized, varStore regions extended).
- **Cross-design-space composition**: when the base font is variable, its per-glyph deltas are **re-parameterized into the merged normalized space** (`format/axis_mapping.py`), so the merged glyphs stay pointwise equal to the base instance at every location — including base-only axes, different axis ranges and different `avar` maps. When the base's default differs from the merged default the missing master is interpolated (phantom points included) and the tuples are re-based; a grid self-check (`verify_composition`) must pass or the merge falls back to the legacy "instance the base at its default" behaviour.
- **OpenType merging**: base GSUB/GPOS/GDEF tables are pruned with `fontTools.subset` closure to the surviving glyphs, then appended with lookup-index remapping and deep glyph-name remapping; conflicts resolve in favor of the main font.
- **Pure FontTools pipeline**: glyph injection goes through the official TTX XML roundtrip (`saveXML` → inject → `ttx` compile) instead of `fontTools.merge`, which raises `NotImplementedError` on CID-keyed CFF.

### Project layout

```
FontMerger/
├── FontMerging.py           # Interactive CLI entry point
├── __init__.py              # Public API exports
├── core/                    # 16-way dispatch, TTX glyph injection, conflict & naming
├── format/                  # static extraction, CFF↔glyf, CID, axis union, transform, subset, webfont
├── tables/                  # per-table merge registry + GSUB/GPOS/GDEF merge
├── tests/                   # 16-matrix generator + unit tests
└── build/                   # PyInstaller packaging (bundles FontTools + AFDKO)
```

## Features

| Capability | Description |
|---|---|
| **16-way merge matrix** | All `static/variable × OTF/TTF × main/base` combinations, auto-dispatched |
| **Multi-level chaining** | Main + 1..n base fonts; each level can have its own scale & baseline offset |
| **Format conversion** | CFF↔glyf (cubic↔quadratic), CFF2→CFF (`_convertCFF2ToCFF`), CFF→CFF2 |
| **CID merging** | Dual-CID: CID offset + direct CharString copy; CID↔name-keyed conversion (incl. cmap format 14 UVS) |
| **Variable fonts** | Main VF preserved in output (CFF2/HVAR/STAT/fvar kept & extended); base VF glyphs keep their `gvar` deltas (HVAR rebuilt from phantom points) when both fonts share the same axis space and `avar` |
| **Cross-design-space composition** | Base `gvar` deltas **and** layout variation data (`GDEF` `ItemVariationStore` + `GPOS` `VariationIndex` devices) re-parameterized into the merged normalized space (hat decomposition in `format/axis_mapping.py`), base-only axes added, different ranges/`avar` handled by user-space clamping + exact hat splitting; rows of the var store are preserved so every `(outer, inner)` reference stays valid; the main font's own var stores are re-parameterized too; verify gate with fallback; policy parameters `compose_variations`/`compose_range`/`compose_fit`/`avar_mode`/`compose_layout` |
| **Axis union** | Union of main/base axis spaces; varStore (incl. GDEF/HVAR/MVAR) constant-axis region extension |
| **OpenType feature merging** | Base GSUB/GPOS/GDEF pruned via Subsetter closure, then appended; same-tag features are **unioned** into one record, base scripts/lang-systems are merged so the appended features stay reachable, `FeatureVariations` feature indices are rewritten after the re-sort, GDEF classes/VarStore/MarkGlyphSets take the union (+ `LookupFlag` bit4 `MarkFilteringSet` remap) |
| **Scale + baseline offset** | Pen-pipeline outline rebuild (T2CharStringPen/TTGlyphPen + TransformPen) with synced metrics |
| **Overlap removal** | `removeOverlaps` boolean union after variable→static instancing |
| **Subsetting** | `create_glyph_subset` — keep only glyphs for a given character set |
| **WOFF/WOFF2 unwrap** | Web fonts accepted as input directly |
| **Same-source subset union** | `merge_subsets()`: object-level union of `unicode-range` subsets of one VF (no TTX roundtrip); **glyf + CFF2** (CharStrings/FDSelect/FDArray union, CFF2 `blend`/`vsindex` kept as-is), feature/script/GDEF-VarStore/MarkGlyphSets union, FeatureVariations index rewrite, HVAR rebuild (glyf) or HVAR VarStore union (CFF2), VVAR rebase, cmap harmonization, name completion |
| **Merge verification** | `verify_merge()`: per-glyph outline/metric diff at N axis positions, plus cmap / feature / layout-integrity / container assertions |
| **Save guard** | `save_font()`: clear `flavor`, assert sfnt magic; `head.flags` WOFF2 bit removal, nameID 16/17/25 + instance PS names |
| **Fast glyf injection** | `glyf` + `glyf` merges copy glyphs object by object instead of round-tripping the whole font through TTX (adding 135 glyphs to a 25k-glyph font: 153 s → 3.7 s); CFF/CFF2/CID keep the TTX pipeline |
| **Naming** | Output family `<main font> mod`, copyrights merged with `^n^n` separators |

### Merge matrix (5×5)

Main and base fonts are each classified as `static/variable × OTF/TTF` — 16 semantic combinations. **Rows = main font type, columns = base font type.**

| | Static OTF base | Static TTF base | Variable OTF base | Variable TTF base |
| :--- | :--- | :--- | :--- | :--- |
| **Static OTF main** | *General*: multi-level merging, per-font independent scale/baseline offset | Asks the user whether to export TTF or OTF | Drops base glyphs whose **codepoint or name** already exists in main; the rest + only the OpenType features referencing surviving glyphs are merged into main (base auto-instanced to the default instance) | Converts the main OTF outlines to quadratic curves; then same as “Variable OTF main × Static OTF base” |
| **Static TTF main** | Asks the user whether to export TTF or OTF | *General* | Converts the main TTF outlines to cubic curves; then same as “Variable OTF main × Static OTF base” | Same as “Variable OTF main × Static OTF base” |
| **Variable OTF main** | Asks whether to export variable or static: ① Static → interpolate a font at the main’s axis values, then handle as static; ② Variable → drop base glyphs conflicting with main, merge main glyphs into the variable OTF’s default master, insert main’s OpenType features into each master | Same as left (static path) | *Master handling*: drop base glyphs conflicting in each master; merge base masters into main — same axis values → add glyphs/features to the main master, different axis values → create a new master. *Axis handling*: axis min/max = union; base-only axes are added (missing masters filled with default values) | Asks the user whether to export TTF or OTF; then same as “Variable OTF main × Variable OTF base” |
| **Variable TTF main** | Asks whether to export variable or static (same as “Variable OTF main”; on the variable path main glyphs are converted to quadratic first) | Same as left (static path) | Asks TTF or OTF; then same as “Variable OTF main × Variable OTF base” | Same as “Variable OTF main × Variable OTF base” |

### General rules (all combinations)

1. **Multi-level chaining**: the result of main + first (n−1) base levels becomes the “main” of level n; already-asked questions are not asked again (memorized).
2. **Naming**: Family becomes `<main font name> mod`; copyrights are written into all copyright fields (`^n^n`-separated); everything else follows the main font.
3. **OpenType features**: the main font’s features are fully preserved; non-conflicting base language/feature tables can be kept wholesale (items referring to deleted glyphs are removed); on conflict, the main font wins.
4. **Glyph retention**: all main-font glyphs are kept; base glyphs are merged only when **both codepoint and name** do not conflict with the main font.
5. **Input formats**: WOFF/WOFF2 are unwrapped automatically; TTC/OTC must be unpacked first; other formats are rejected.

> **Implementation status**: the “② Variable path” of a variable main font is supported (main VF preserved + axis union + base glyphs merged at the default instance). Per-axis *master-level interpolation composition* (base glyphs varying with the base’s axes) is **not yet implemented**.

## Quick Start

Requirements: **Python ≥ 3.8**, **FontTools ≥ 4.49**.

```bash
git clone https://github.com/ChangGGcn/font-matrix-merger.git
cd font-matrix-merger
pip install "fonttools>=4.49"

# Interactive CLI
python FontMerging.py
```

The CLI is interactive: enter the main font path (plus scale % and baseline offset), then any number of base fonts (press `Y` to finish), and compatibility warnings can be confirmed with `y`. The output is written to `<main font>_mod.{otf|ttf}`.

### Three-font input/output example (main + 2 base levels)

```
========================================================
  FontMerger 字体合并工具
  支持: 静态/可变 x OTF/TTF x 多级打底 x WOFF/WOFF2
========================================================

请输入主字体（拖入文件或输入路径）:
  主字体路径:  test/OpenType/LibreCaslonText-Regular.otf
  缩放倍率(%) [100]: 100
  基线偏移 [0]: 0
第 1 级打底字体（Y 结束）:
  路径:  test/otf_variable_fonts/SourceSerif4Variable-Roman.otf
  缩放倍率(%) [100]: 100
  基线偏移 [0]: 0
第 2 级打底字体（Y 结束）:
  路径:  test/TrueType/LXGWWenKaiTC-Regular.ttf
  缩放倍率(%) [100]: 100
  基线偏移 [0]: 0
第 3 级打底字体（Y 结束）:
  路径:  Y

加载字体...
  test/OpenType/LibreCaslonText-Regular.otf
    静态OTF, 537 字形
  test/otf_variable_fonts/SourceSerif4Variable-Roman.otf
    可变OTF, 1464 字形
  test/TrueType/LXGWWenKaiTC-Regular.ttf
    静态TTF, 25764 字形

兼容性检查...
  [警告] 打底字体为可变字体, 将先实例化为静态再合并
  [警告] 混合轮廓格式: 主字体为CFF, 打底为glyf. 将自动转换打底字体
  [警告] 主字体为可变字体, 将先实例化为静态再合并

开始合并...

--- 第 1 级 ---
  主: 静态OTF | 打底: 可变OTF
  [CFF2→CFF] 转换完成 (1464 glyphs)
  [重叠合并] 完成 (1464 glyphs)
  [CID归一] 打底字体 CID→name (输出统一为 name-keyed)
  [CID→name] 转换完成 (1464 glyphs)
  [冲突] 409 个字形
  [新增] 1054 个字形
  合并后字形: 1591
  [OT合并] GDEF: 来自打底 (主无, 过滤后 200 个字类)
  [OT合并] GSUB: 追加 10 个打底 feature (主冲突跳过)
  [OT合并] GPOS: 追加 2 个打底 feature (主冲突跳过)

--- 第 2 级 ---
  主: 静态OTF | 打底: 静态TTF
  [询问] 导出为 TTF 还是 OTF？
    1. OTF
    2. TTF
> 1
  [转换] 轮廓格式不同，自动转换打底字体...
  [冲突] 915 个字形
  [新增] 24848 个字形
  [分块] 5 块, 每块 ≤5000 字形
  [OT合并] GSUB: 追加 2 个打底 feature (主冲突跳过)
  [OT合并] GPOS: 追加 3 个打底 feature (主冲突跳过)

处理名称...

输出路径 [test/OpenType/LibreCaslonText-Regular_mod.otf]: 
完成! test/OpenType/LibreCaslonText-Regular_mod.otf
  静态OTF, 26439 字形
```

Notes:

- Export-format / output questions are asked only **once**; later levels reuse the memorized answer.
- Each base level can have its own scale % and baseline offset.
- Compatibility warnings are informational; confirm with `y` to continue.

### Library API

```python
from FontMerger import FontMerger, apply_naming, get_family, get_copyrights
from FontMerger.format.static_extract import variable_to_static
from fontTools.ttLib import TTFont

merger = FontMerger()
# Pre-answer the interactive questions (non-interactive use)
merger.mem = {"sOTF_sTTF": "OTF", "vOTF_sOTF": "可变"}

# Level-by-level merge
r = merger.merge_two(main_font, base_font)
r = apply_naming(r, get_family(main_font), get_copyrights(main_font, base_font))
r.save("merged.otf")

# Or the one-line convenience helper
from FontMerger import merge_fonts
result = merge_fonts("main.otf", ["base1.otf", "base2.ttf"])

# Pre-answer the interactive questions explicitly (non-interactive use)
result = merge_fonts("main.otf", ["base.otf"], answers={"vOTF_sOTF": "静态"})
```

#### Cross-design-space composition parameters

When main and base are both variable with **different** axis sets/ranges or a
different `avar`, the base deltas must be re-parameterized into the merged
normalized space. These parameters are policy knobs for that step; the defaults
are the ones recommended for "most faithful to the designer's intent":

| Parameter | Default | Meaning |
| --- | --- | --- |
| `compose_variations` | `True` | Master switch. When the composed result fails the grid self-check the merger **falls back** to the legacy behaviour (base instanced at its default) and logs a warning, so enabling this can never produce a worse font than before. |
| `compose_range` | `"main+extra"` | Which range an axis takes in the merged font: `"main+extra"` = shared axes keep the **main** font's range, axes only the base has are added with the base's range; `"union"` = widest of both (larger interpolation-extrapolation error and up to ×28 more tuples before knot pruning); `"main"` = only the main font's axes, base axes are clamped away. |
| `compose_fit` | `"exact"` | `"exact"` = the base's tuples are split exactly onto the merged knot grid (pointwise equality, more tuples); `"affine"` = fit a single hat per tuple in the merged space (compact, but off by ~6 units on real fonts, so the self-check usually rejects it). |
| `avar_mode` | `0` | `0` = keep the main font's `avar` (most faithful to the main designer; needs the phantom-point master when the defaults differ); `1` = drop the base's `avar` and use the main's for both; `2` = drop `avar` from the output entirely (recovers the base's variation where the main's `avar` collapses a user interval to a point). |
| `verify_compose` | `True` | Run `verify_composition()` on a small grid of the merged axes before accepting the composed outline/hmtx data; on failure, warn + fall back. |
| `compose_layout` | `True` | Also re-parameterize the base's **layout** variation (`GDEF` `ItemVariationStore` + `GPOS` `VariationIndex` devices) so the base's kerning/mark/anchor variation keeps animating in the merged font; the rows of the store are preserved, so no reference rewriting is needed. Turn off to keep the old behaviour (base layout frozen at the merged default). |

```python
# Cross-design-space merge: base contributes base-only axes and its own avar
merger = FontMerger(compose_variations=True, compose_range="main+extra", avar_mode=0)
r = merger.merge_two("ZedText-VF.ttf", "InterVariable.ttf")
```

### Merging same-source webfont subsets (`merge_subsets`)

When a variable font is shipped as N webfont subsets (one `@font-face` +
`unicode-range` per slice), merging them back with the generic variable×variable
path would instance every base slice to a static font (losing `gvar`/`HVAR`/`VVAR`
and the `vert`/`vrt2`/`kern`/`mark` lookups of every slice but the first).
`merge_subsets()` takes the union path instead: no instancing, no axis union,
every slice keeps its own glyphs, deltas and lookups.

```python
from FontMerger import merge_subsets, verify_merge

paths = sorted(glob("webfont/ja-v2/*.woff2"))      # subsets[0] is the base

merged = merge_subsets(paths, out_path="OpenAISansJP-Merged.ttf", tag="ja",
                       complete_name_table=True, fix_head_flags=True)

# self-check: instance sources + result at the default/min/max axis positions
report = verify_merge(paths, merged,
                      glyph_map=merged.subset_merger.glyph_map())
assert report["ok"], report["failures"]

# source glyph name -> merged GID (post-reorder), per subset
gmap = merged.subset_merger.glyph_map()
```

Or in one call, with the self-check built in:

```python
merged = merge_subsets(paths, out_path="Merged.ttf", tag="ja", verify=True)
```

### Tests

`tests/generate_matrix.py` generates the full 16-combination matrix; `tests/test_merger.py` (unit tests) and `tests/test_subset_merge.py` (same-source subset union) contain the test cases. The subset cases build their own fixtures with `pyftsubset` (`tests/subset_fixture.py`), so no webfont slices need to be committed. The test suite needs a local font collection (paths are resolved under `tests/../test/`) — the fonts themselves are **not redistributed** with the repository. [OFL Google Fonts](https://fonts.google.com/) typefaces used in the samples (Libre Caslon Text, LXGW WenKai TC, Source Serif/Source Han, Zed Text) can be downloaded freely; *commercially licensed* test fonts are mapped in the local, non-committed file `tests/local_fonts.py` (template: `tests/local_fonts.example.py`) and any missing font simply skips the corresponding case.

## Known Limitations

1. **JP (CID CFF2) as the main font** (matrix cells C1/D1): the merge itself succeeds (~18,600–18,868 glyphs), but the save stage can leave incomplete cmap format-4 references for base Latin glyphs; the matrix generator falls back to a static-instanced path. A true variable output requires solving deeper CFF2 CID namespace issues.
2. **Base-glyph variation across design spaces**: when main and base are both variable and share the same axis space and `avar`, the base glyphs' `gvar` deltas are transferred 1:1 and `HVAR` is rebuilt from the phantom points (`axes_compatible()`). When the design spaces differ (different axis sets/ranges or a different `avar`), the base deltas are **composed** — re-parameterized into the merged normalized space by `format/axis_mapping.py` — and the result is accepted only if the `verify_composition` grid check passes (tolerance 1 unit), otherwise the merge transparently falls back to instancing the base at its default. Remaining gaps in this path: (a) it needs **both** fonts to be `glyf`+`gvar` — a CFF2 base still falls back to instancing, and CFF2 blend composition is not implemented yet; (b) the merged `avar` is the main font's, so an axis range that the main font compresses to a single normalized point (`collapsing_flats()`) cannot keep the base's variation across that interval — the merger detects this, warns, and keeps the main behaviour (pass `avar_mode=2` to drop `avar` entirely and recover the base's variation, at the cost of changing the main font's interpolation); (c) layout variation of the base is transferred as well (`GDEF` `ItemVariationStore` + `GPOS` `VariationIndex`, via `transfer_base_layout()`), but since `VariationIndex` deltas are integers the re-parameterized columns are rounded, so kerning/anchor variation can deviate by up to ~1 unit (measured 0.70 units on Inter's kerning at UPM 1000) — set `compose_layout=False` to keep the old behaviour (base layout frozen at the merged default); (d) the main font's own var stores are only re-parameterized when the axis space actually changes (`compose_range="union"`/`"main"` or `avar_mode != 0`), where the default-location term has to be carried by a constant (peak-0) region.
3. **OpenType features**: appended base features are merged only if all referenced glyphs exist in the main font (otherwise the lookup is skipped). Same-tag features are unioned into one record, base scripts/lang-systems are merged so the appended features stay reachable, `FeatureVariations` feature indices are rewritten after the re-sort (the table itself is preserved; records whose index cannot be mapped are dropped), and GDEF `GlyphClassDef`/`MarkAttachClassDef`/`MarkGlyphSetsDef` plus the `ItemVariationStore` take the union with `LookupFlag` bit4 `MarkFilteringSet` indices remapped. Base-font `FeatureVariations` are not merged in the heterogeneous path (only the main font's are preserved).
4. **VORG**: values are correct when instancing at the default axis position; non-default positions need recomputation.
5. **Multi-level OT features**: a feature already merged at an earlier level is re-detected at later levels (idempotent, but lookups may become redundant).
6. **Packaging**: the repository root is the package itself, so `pip install` from a clone is not wired up yet — clone-and-run for now; a PyPI-ready layout is planned.
7. **Locally licensed fonts** are used only for local testing and are intentionally excluded from this repository (paths live in the non-committed `tests/local_fonts.py`); all fonts named in the documentation samples are OFL-licensed.
8. **`merge_subsets()` CFF2 scope**: glyf subsets and CFF2 subsets are both supported, but CFF2 requires the slices to share the same CFF2 **VarStore and GlobalSubrs** structure (pyftsubset keeps them intact); differences in FDArray are handled by an FD-level union. If a tool rebuilt/re-numbered the CFF2 VarStore per slice, the `blend`/`vsindex` data would need to be rewritten — that path raises a clear error instead of writing a broken font. Mixed CFF/CFF2 slices are not supported.
9. **Auto-named glyph aliasing**: subset glyphs with post-3.0 sequence names (`glyphNNNNN`) are always aliased, so a slice that keeps the same no-codepoint glyph as another slice contributes an extra (content-identical) copy; this trades a little size for never conflating two different glyphs.

## License

Released under the [MIT License](LICENSE). Sample fonts used for testing remain © their respective authors.
