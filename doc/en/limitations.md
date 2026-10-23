# Support boundaries and troubleshooting

This guide describes **v0.2.1**. Defaults, tolerances and behavior follow the source code. Current validation and historical measurements are recorded separately below.
Source links use repository paths. The runtime ZIP includes this documentation and the library, but not `tests/` or `build/`. Those trees are mentioned as code paths marked repository-only; no relative links are generated for them.

Related pages: [installation and usage](usage.md), [merge API](merge-api.md), [architecture](architecture.md), [variation model](variation-model.md), [same-source subsets and verification](subsets-and-verification.md), [module and script reference](script-reference.md).

## 1. Supported conditions

### 1.1 Inputs and runtime

- Containers: static TTF (glyf), static OTF (CFF), variable TTF (gvar), variable OTF (CFF2), and WOFF/WOFF2. `load_font()` unwraps WOFF/WOFF2 and clears `flavor`.
- TTC/OTC are outside CLI support and must be unpacked first. The CLI accepts `.ttf`, `.otf`, `.woff`, and `.woff2` (`SUPPORTED_EXTS`); collection extensions (`COLLECTION_EXTS`) produce an unpack-first message.
- The declared baseline is Python ≥ 3.8 and fontTools ≥ 4.49. Python 3.8 received a syntax-level AST check only; it was not run on a 3.8 interpreter. The historical v0.2.0 native Windows validation used Python 3.10.11 and fontTools 4.61.0.
- WOFF reading/writing uses standard zlib and does not need `brotli`. Only WOFF2 reading/writing needs optional `brotli`; without it, WOFF2 operations are unavailable.
- There is no `pyproject.toml` or `setup.py`, so `pip install` is not implemented. The repository root is the `FontMerger` package, and its parent directory must be on `sys.path`. The runtime ZIP uses an importable `FontMerger/` root.
- The CLI is interactive only and accepts no positional arguments. Use the library API for scripts.
- The runtime ZIP does not contain `tests/` or `build/`. Such paths are repository-only.

### 1.2 Merge combinations and policy conditions

- Heterogeneous merging covers the 4×4 combinations of static or variable main/base fonts and glyf or CFF/CFF2 outlines. Output outline technology follows the main font. The TTF/OTF export question is recorded but does not change the result.
- Static main with variable base: the base is merged at its default instance; added glyphs do not vary.
- Variable main with static base: when the user selects variable output, the main VF keeps its axis space. Selecting static instances the main font first. Base glyphs are static and add no axes.
- Cross-design-space composition with a variable base requires the same outline technology and matching variation data on both sides: `gvar` for glyf, CFF2 with a VarStore for CFF2. It must pass the sampled `verify_composition()` check. Failure falls back to the legacy path.
- Same-source subset union treats one slice as the base directly. Two or more slices must all be variable, with identical `fvar` axis sets and min/default/max, and identical outline technology. The CFF/CFF2 branch requires slices to be CFF2, so a pure CFF1 slice is rejected. CFF2 also requires the slices to share the same VarStore and GlobalSubrs structure. FDArray differences are handled by FD-level union.
- Same-source FeatureVariations must have exactly matching condition sets and order. A mismatch raises `ValueError`; no lossy combination is attempted.
- CID handling is branch-based. Static dual-CID merging preserves the CID namespace, FDArray/FDSelect, and per-source Private dictionaries instead of flattening to the first FD. `cid_to_name()` remains for name-keyed normalization branches.
- Input ownership: the legacy axis-union fallback of `merge_two()` modifies the main font in place; `merge_subsets()` modifies `subsets[0]`; `scale_font()`/`apply_scale_offset()` scale or offset in place and return the same `TTFont` (`scale=1` with `baseline_offset=0` returns it unchanged; invalid arguments or a VARC font raise `ValueError`); `union_axes()`, `rename_glyphs()`, and `apply_naming()` modify inputs in place. Callers must `deepcopy` when the input is reused. `merge_fonts()` deep-copies the main font first.

## 2. Known unsupported or explicitly rejected cases

These are current design boundaries. They must not be described as supported.

1. **Packaging and CI**: no pip install, no `pyproject.toml`, and no CI. Imports depend on the package directory name and the parent `sys.path`. See [`__init__.py`](../../__init__.py) and [`FontMerging.py`](../../FontMerging.py).
2. **CLI positional arguments**: `FontMerging.py` runs the interactive flow only. There is no argument parser. See [`FontMerging.py`](../../FontMerging.py).
3. **Collection fonts**: TTC/OTC must be unpacked first. The extension sets are in [`__init__.py`](../../__init__.py).
4. **Cross-outline variable composition**: glyf main with CFF2 base, or CFF2 main with glyf base, is not composed pointwise. It falls back to axis union plus base default instancing, and base glyphs may lose axis variation. See `_do_merge()` in [`core/merger.py`](../../core/merger.py) and [`format/variation_compose.py`](../../format/variation_compose.py).
5. **CFF2 base VVAR and Private hint variation**: only base HVAR is merged by glyph name. VVAR data and Private hint blends remain static; hint blends are folded to their defaults. See `merge_cff2_hvar()` and `offset_cff2_vsindex()` in [`format/cff2_compose.py`](../../format/cff2_compose.py).
6. **Base FeatureVariations in the heterogeneous path**: a valid base table, including its FV, can be adopted only when the main table is absent or empty (no lookups and no features). Otherwise base FV records are not spliced across sources and main conditions are preserved. A base FV referencing a missing lookup or feature causes that table merge to be rejected and main layout preserved. See `merge_base_layout()` in [`tables/ot_merge.py`](../../tables/ot_merge.py).
7. **Same-source FV mismatch**: different condition sets or order are rejected outright. Mixed CFF/CFF2 slices are unsupported. CFF2 inputs whose VarStore was rebuilt or renumbered per slice raise `IncompatibleCFF2Error`. See `LayoutUnion.add_from()` in [`tables/layout_union.py`](../../tables/layout_union.py) and `check_cff2_compatible()` in [`format/cff2_union.py`](../../format/cff2_union.py).
8. **CID-keyed CFF2 as the main font**: the matrix generator still uses a static-instanced fallback for C1/D1, and saving can leave incomplete format 4 cmap references for base Latin glyphs. This is separate from static dual-CID merging: the static CID/CFF path keeps CID and FD structure in `cid_ufo_style_merge()` in [`format/cid_merge.py`](../../format/cid_merge.py) and has save/reload regressions. The matrix generator is repository-only: `tests/generate_matrix.py` (code path, no relative link).
9. **Unknown kern formats**: the legacy `kern` merge handles only standard version 0, subtable format 0, and coverage 1 horizontal pairs. Other versions or formats are skipped with a warning, with main priority. Heterogeneous GPOS does not perform cross-source codepoint unification, avoiding double positioning of the same pair. See `_union_kern()` in [`core/table_policy.py`](../../core/table_policy.py) and `_merge_gsub_gpos()` in [`tables/ot_merge.py`](../../tables/ot_merge.py).
10. **VORG at non-default axis positions**: default-position instancing has defined values; other positions require additional handling. When an origin cannot be recovered, for example because `vmtx` is missing, the main VORG is kept instead of applying base defaults. See `_union_vorg()` in [`core/table_policy.py`](../../core/table_policy.py) and `variable_to_static()` in [`format/static_extract.py`](../../format/static_extract.py).
11. **Rendering and shaping equivalence**: verification compares outlines and metrics through fontTools `getGlyphSet()` and RecordingPen. It is not HarfBuzz shaping or FreeType/Windows rasterization. Optional system-engine tests cover a few synthetic cases, not a full engine matrix. See `verify_merge()` and `verify_composition()` in [`core/verify.py`](../../core/verify.py).
12. **Verification scope**: `verify_merge()` and `verify_composition()` use sampled fonts and sampled axis positions. They are not pointwise proofs for every axis position, text run, or feature. Sampling parameters are in `grid_positions()` and `_auto_positions()` in [`core/verify.py`](../../core/verify.py).
13. **Python 3.8 runtime**: syntax checks only; no 3.8 interpreter run. The declared baseline is not a cross-version runtime guarantee. See the historical check record in [`CHANGELOG.md`](../../CHANGELOG.md).
14. **Interface boundary for `save_font(..., recalcTimestamp=non-None)`**: [`utils/save.py`](../../utils/save.py) currently forwards `recalcTimestamp` to `TTFont.save()`, but the current fontTools `TTFont.save()` signature accepts only `file` and `reorderTables`. A non-`None` value therefore raises `TypeError`. Keep `recalcTimestamp=None`; this round does not change runtime code.

Fixed historical issue, not in the unsupported list: format 0 overflow. `_copy_cmap_mappings()` in [`core/glyph_copy.py`](../../core/glyph_copy.py) upgrades a format 0 subtable to format 6 when an actual mapped GID exceeds 255, preserving its mapping. The old `OverflowError` is a fixed historical issue, not a current limitation.

## 3. Degradations and information loss

These paths still produce fonts, but with degradation or information loss. The log lines identify each case.

| Scenario | Behavior and log | Impact |
| --- | --- | --- |
| Composition failure ([`core/merger.py`](../../core/merger.py) `_do_merge`) | Prints `[合成] 回退到默认实例合并: <reason>` and uses the legacy path | Base glyphs stay at the default instance. A 1:1 gvar transfer runs only for glyf bases when axis space and avar match exactly; CFF2 bases have no such path |
| Base layout variation not transferred ([`format/variation_compose.py`](../../format/variation_compose.py) `transfer_base_layout`) | Prints `[合成] 打底布局变化数据未并入 (保留默认实例)` or `[OT合并] 跳过...` | Base kerning and anchor variation stays frozen at the default point |
| `compose_layout=False` | GDEF ItemVariationStore and GPOS VariationIndex are not transferred | Layout variation does not follow the axes |
| CFF2 base VVAR / Private hint ([`format/cff2_compose.py`](../../format/cff2_compose.py)) | Only HVAR is merged; hint blends are folded to defaults | Vertical variation and Private hint variation are lost |
| Incompatible hinting environment ([`core/hinting_policy.py`](../../core/hinting_policy.py)) | Prints `[指令警告] ... 剥离 N 个新增字形的指令` | New glyphs lose small-size hinting; main programs remain |
| Non-identity scale/offset or UPM normalization ([`format/transform.py`](../../format/transform.py) `_remove_hinting`) | `_remove_hinting()` removes glyph instructions, global programs, and pixel caches (cvt/cvar/fpgm/prep/gasp/hdmx/LTSH/VDMX/DSIG) | Small-size hinting and pixel-cache behavior disappear; outlines and metrics are transformed in design units |
| Win metrics expansion ([`tables/metadata_recalc.py`](../../tables/metadata_recalc.py) `_recalc_bounds`) | Prints `[元数据] Win 度量扩大为 ...` | Line height may grow when the metrics expand to cover all default outlines |
| Unknown or non-standard kern ([`core/table_policy.py`](../../core/table_policy.py) `_union_kern`) | Prints `[表策略警告] ...` and skips that source | That source's kern data is not merged |
| VORG origin cannot be recovered ([`core/table_policy.py`](../../core/table_policy.py) `_union_vorg`) | Prints `[表策略警告] VORG 原点并集失败，保留主表...` | Base default origins are not applied, avoiding misalignment |
| Automatic-name or same-name conflicts ([`core/conflict.py`](../../core/conflict.py) `_plan_merge_aliases`) | Aliasing preserves source identity | A no-codepoint glyph may gain a content-identical copy, increasing size |
| Unmappable FeatureVariations ([`tables/layout_union.py`](../../tables/layout_union.py)) | The same-source path raises `ValueError`; the heterogeneous path keeps main conditions or skips the base table merge | Affected substitutions do not run instead of writing invalid indices silently |
| Multiple heterogeneous levels ([`core/merger.py`](../../core/merger.py) `_merge_base_layout_once`) | Features attached at an earlier level are detected again at the next level | Idempotent, but lookups can be redundant, increasing size and lookup cost |

## 4. Verification coverage

### 4.1 Merge verification

`verify_merge(sources, merged, ...)` in [`core/verify.py`](../../core/verify.py) checks:

- the codepoint union and extra codepoints;
- source slice axis consistency and the merged axis space;
- per-glyph outlines, hmtx, and vmtx at the default position, first-axis endpoints, or a grid;
- GSUB/GPOS feature tag loss;
- dangling layout references, Coverage ordering, MarkFilteringSet, FeatureVariations, lookup, and VarStore references;
- GDEF glyph classes, mark sets, and HVAR/VVAR map coverage;
- container `flavor`, `head.flags`, nameID 16/17/25, and instance PostScript names;
- vertical `vert`/`vrt2` coverage.

`axis_positions="auto"` uses the default point and the first axis endpoints. `"grid"` uses each axis min/default/max combinations, truncated by `max_positions`. `sample` limits glyphs per slice. The return value is `{"ok", "failures", "checks"}`. `merge_subsets(verify=True)` raises `AssertionError` on failure.

### 4.2 Composition verification

`verify_composition(merged, main_font, base_font, added_glyphs, ...)` in [`core/verify.py`](../../core/verify.py) compares on a merged-axis grid:

- added glyphs against the base instance at the same location, for outlines and advance widths;
- main glyphs against the main font instance at the same location, for outlines.

The outline tolerance defaults to 1 font unit. The advance-width tolerance defaults to the outline tolerance; the main pipeline passes 3.0.

The grid uses only each axis min/default/max (fixed points of `avar`), and comparison uses `getGlyphSet(location=...)` rendering semantics. Defaults are `sample=30` glyphs per set and `max_positions=6`; the main pipeline passes `max_positions=4` and `adv_tolerance=3.0`. It is not a pointwise proof for every axis position. On failure, `_do_merge()` falls back to the legacy path.

### 4.3 Structural invariants

Finalization enforces:

- exact Unicode/UVS union and main-map priority (`assert_cmap_union()` in [`core/invariants.py`](../../core/invariants.py));
- glyph order, `.notdef`, maxp glyph count, components, hmtx/vmtx coverage, cmap subtable synchronization, UVS references, and avar axis coverage (`assert_font_structure()` in [`core/invariants.py`](../../core/invariants.py));
- dangling layout references, Coverage order, mark sets, FeatureVariations, lookup references, and VarStore structure (`_check_layout_integrity()`, `_check_lookup_references()`, `_check_var_stores()` in [`core/verify.py`](../../core/verify.py)).

These checks run on ordinary, chunked, empty-add, and CID exits. The ordinary path raises on failure; the composition path raises and triggers fallback.

### 4.4 Optional system-engine tests

`tests/run_regressions.py --engines` (repository-only) runs a few comparisons with standard-library `ctypes` when `libharfbuzz.so.0` and `libfreetype.so.6` exist: a nested-lookup mispointing negative control, main kern value preservation, cross-script isolation, and loading of an adopted or stripped hint bundle. Missing libraries produce an explicit SKIP. The tests install no dependencies and do not represent full HarfBuzz or FreeType coverage.

## 5. Historical verification evidence

The numbers below come from historical records dated 2026-10-24 ([`CHANGELOG.md`](../../CHANGELOG.md) 0.2.0 and release review notes). This documentation round did **not** rerun them. They are historical references, not new results.

| Item | Value | Source and status |
| --- | --- | --- |
| Unified regression | 157/157 passed, 0 skipped, 0 failed suites | Historical run on 2026-10-24; entry code path `tests/run_regressions.py`, repository-only; 46 original cases + 105 synthetic cases + 6 optional engine cases |
| Original suites | 13 + 21 + 8 + 4 = 46 | Historical run |
| Synthetic regressions | 21 + 14 + 17 + 24 + 12 + 12 + 5 = 105 | Historical run; per-suite counts |
| Windows cmap regression | 21/21 | Python 3.10.11 / fontTools 4.61.0; historical release review record, not distributed |
| Windows CLI save/reload | 31,060 glyphs, 30,012 Unicode codepoints; 0 missing, 0 extra, 0 main-map differences; 120.34 s | Historical release review record, not distributed; inputs and outputs were not distributed with the repository or release |
| glyf object-level injection | 25k-glyph main plus 135 glyphs: 153 s → 3.7 s | Historical release record and older README (v0.1.1 era); the current README is simplified, and this was not measured this round |
| `compose_range="union"` tuple growth | At most about ×28 before pruning | Historical release record; depends on the fonts |
| `compose_fit="affine"` deviation | About 6 font units | Historical release review record; the sampled check decides acceptance |
| Layout integer residual | Kerning/anchor difference around 1 unit at most; measured 0.70 units at UPM 1000 | Historical release review record; not a fixed value for every font |
| Cross-zero hat bias before the fix | 0.625 units | Historical fix record ([`CHANGELOG.md`](../../CHANGELOG.md) 0.1.1) |
| avar false positive | 1.58 units | Historical fix record ([`CHANGELOG.md`](../../CHANGELOG.md) 0.1.1; instancer user limits do not apply avar) |
| Python 3.8 | AST syntax check passed; no 3.8 interpreter run | Historical review conclusion ([`CHANGELOG.md`](../../CHANGELOG.md)) |
| Format 0 overflow | Fixed: upgrade to format 6 when a GID exceeds 255; GID 255 remains valid | Current code behavior; historical Windows save issue |

SKIP semantics: the original four suites' `main()` functions count a normally returned SKIP as passed. The unified runner counts SKIP lines separately. The historical 157/157 record reports 0 skipped, but other environments can produce SKIP from missing fonts, missing brotli for WOFF2, or missing system engine libraries.

## 6. Troubleshooting

| Symptom | Likely cause | Check and action |
| --- | --- | --- |
| No new glyphs after merging | Heavily overlapping character sets or dual-CID namespace conflict | Read the `[提示] 无新增字形` line and `_diagnose_empty_merge()` in [`core/merger.py`](../../core/merger.py); swap main/base order or convert one side to name-keyed first |
| `[合成] 回退到默认实例合并` | Axis planning, instancing, or self-check failure | This is the allowed safe fallback. Check outline technology in [`format/variation_compose.py`](../../format/variation_compose.py) and the `verify_composition()` check. Do not disable `verify_compose` to hide the problem |
| Added glyphs do not vary | Fallback path or static base | Check whether composition fell back. For same-source slices, use `merge_subsets()` |
| Old-format overflow at save (historical) | Older code upgraded Unicode subtables only | Current `_copy_cmap_mappings()` in [`core/glyph_copy.py`](../../core/glyph_copy.py) upgrades every format 0 subtable. Confirm the current code version |
| `save_font(..., recalcTimestamp=non-None)` raises `TypeError` | The current fontTools `TTFont.save()` does not accept that keyword | Keep `recalcTimestamp=None` ([`utils/save.py`](../../utils/save.py)) |
| `[指令警告] ... 剥离` | Incompatible or unprovable hinting environment | Expected degradation: new glyphs lose instructions; main programs remain |
| `[表策略警告] kern` | Unknown legacy kern version or format | Expected degradation: that source's kern is skipped; main values win ([`core/table_policy.py`](../../core/table_policy.py)) |
| `[表策略警告] VORG` | No recoverable origin from vmtx, or abnormal data | Expected degradation: main VORG is kept ([`core/table_policy.py`](../../core/table_policy.py)) |
| VORG wrong at non-default axis positions | Instancing guarantees the default position | Recompute vertical origins at the target axis position |
| `ModuleNotFoundError` on import | Parent directory not on `sys.path`, or package directory renamed | Import from the parent directory or add it to `PYTHONPATH`. For the runtime ZIP, import from the parent of `FontMerger/` |
| CLI ignores a file path | The CLI reads interactive input only and has no positional arguments | Run `python FontMerging.py` and follow the prompts, or use the library API |
| WOFF2 read/write reports missing brotli | Optional dependency not installed | Install brotli or use sfnt inputs and outputs |
| CFF2 subset union reports incompatible structure | Slice VarStore or GlobalSubrs was rebuilt or renumbered | Re-slice with a structure-preserving tool. The current path rejects rather than writing a broken font |
| Same-source FV reports a condition mismatch | The slicing tool changed condition sets or order | The current path rejects a lossy union. Regenerate slices with matching order |
| `verify_merge` reports failures | Codepoints, outlines, layout, or metadata do not meet the criteria | Inspect the report `failures` list in [`core/verify.py`](../../core/verify.py). Start at the default position, then widen sampling with `"grid"` |
| `verify_composition` reports failure | Non-equivalent data, integer rounding, or flat-avar limits | See Section 3 ([`core/verify.py`](../../core/verify.py)). Adjust `compose_range`, `compose_fit`, or `avar_mode` to evaluate, but keep the production check enabled |
| A font saves but renders incorrectly in some engine | Verification is not equivalent to all engines and all text | Validate separately with the target engine and text. The current documentation does not claim GDI/DirectWrite or full bytecode behavior |

## 7. v0.2.1 validation snapshot

- The local regression run used Python 3.14.4 and fontTools 4.61.1: **157/157 passed, 0 skipped**.
- The public manual has 20 Markdown files and 9 paired topics. Detailed pages cover 60 root callables and 25 ordinary public class methods. The source-signature appendix lists 69 files and 613 definitions, including internal helpers.
- All 38 Python example blocks passed a syntax check. The 3 Python blocks in each root README were also executed from the extracted review ZIP using neutral synthetic fonts.
- The 47 runtime Python files are unchanged from v0.2.0 except for the version string. Packaging changes add public Markdown and an explicit review-preview option.
- These checks do not establish Python 3.8 runtime support, Windows installation behavior, GDI/DirectWrite output or a full engine matrix. Windows measurements in Section 5 are historical v0.2.0 results.
- Runtime source links work in the ZIP. Tests and build tools remain repository-only.
