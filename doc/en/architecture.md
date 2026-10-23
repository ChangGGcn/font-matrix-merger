# Architecture: merge paths, pipelines, and data invariants

This guide describes **v0.2.1**. Defaults and supported behavior follow the source code.
Source links use repository paths. The runtime ZIP includes this documentation and the library, but excludes repository-only `tests/` and `build/` trees. Those trees are mentioned as code paths marked repository-only; no relative links are generated for them.

Related pages: [usage](usage.md), [merge API](merge-api.md), [variation model](variation-model.md), [same-source subsets and verification](subsets-and-verification.md), [support boundaries](limitations.md), [module and script reference](script-reference.md).

## 1. Scope and entry points

The library serves two tasks. They use separate implementations and do not share a merge pipeline.

| Entry point | Purpose | Return and ownership |
| --- | --- | --- |
| `FontMerger.merge_two(main, base)` | Merge one base font into one main font | Returns `TTFont`. No naming, no save. The legacy axis-union fallback can modify the main font in place, so pass a copy when the input is reused |
| `merge_fonts(main, bases, interactive=False, answers=None)` | One-call multi-level heterogeneous merge | Deep-copies the main font, merges level by level, applies naming and clears `flavor`. Returns `TTFont`, never saves |
| `merge_subsets(subsets, out_path=None, ...)` | Union of same-source webfont slices | Modifies `subsets[0]` in place as the result. With `out_path=None` it does not save. With `verify=True` a failed check raises `AssertionError` |
| `apply_naming(font, main_family, all_copyrights)` | Derive modified-release names in place | Returns the same `TTFont`. `merge_two` does not call it |

Entry-point parameters and defaults:

| Function | Argument | Type | Default | Meaning, units, and side effects |
| --- | --- | --- | --- | --- |
| `merge_two` | `main`, `base` | `TTFont` | required | Input font objects. The legacy axis-union fallback can modify `main` in place |
| `merge_fonts` | `main_font` | `TTFont` or path | required | The main font is deep-copied before merging |
| | `base_fonts` | `list` | required | Base fonts or paths; list order is priority |
| | `interactive` | `bool` | `False` | Whether to ask interactively; `False` uses `DEFAULT_ANSWERS` |
| | `answers` | `dict` or `None` | `None` | Overrides answers by `ask` key |
| `merge_subsets` | `subsets` | `list` | required | Slice paths or fonts; `subsets[0]` is modified in place |
| | `out_path` | `str` or `None` | `None` | Filesystem output path; `None` does not save |
| | `tag` | `str` | `"s"` | Alias prefix, no unit |
| | `output_flavor` | `str` or `None` | `None` | `None` infers the container from the `out_path` extension when `out_path` is set. With `out_path=None`, `flavor` is not processed, so the result may keep the input container flag (for example, a caller-supplied TTFont loaded from woff2). `"woff"`/`"woff2"` selects a web container explicitly |
| | `complete_name_table` | `bool` | `True` | Adds nameID 16/17/25 and instance PostScript names |
| | `fix_head_flags` | `bool` | `True` | Clears the WOFF2 flag bit in `head.flags` |
| | `verify` | `bool` | `False` | Runs `verify_merge()` after merging; failure raises `AssertionError` |
| | `verbose` | `bool` | `True` | Logging switch |
| `apply_naming` | `output_font` | `TTFont` | required | Modified in place and returned |
| | `main_family` | `str` or localized family text | required | Family-name source |
| | `all_copyrights` | `list` | required | Copyright texts, merged per language |

These arguments carry no length or coordinate units. `out_path` is a filesystem path. `apply_naming()` moves unencodable name records to same-language Unicode records and raises `ValueError` when the language cannot be determined. Return values and exceptions are described here and in the following sections.

The command-line entry `FontMerging.py` is interactive only and accepts no positional arguments. Use the library API for non-interactive work.

Minimal library call with complete imports:

```python
from FontMerger import (FontMerger, apply_naming, get_copyrights,
                        get_family, load_font, save_font)

main = load_font("Main.ttf")
base = load_font("Base.ttf")
merged = FontMerger().merge_two(main, base)
merged = apply_naming(merged, get_family(main), get_copyrights(main, base))
save_font(merged, "Merged.ttf")
```

Naming ownership: `merge_two()` produces merged outlines but no modified-release names. `merge_subsets()` does not call `apply_naming()` and does not add a `mod` family suffix or merge copyright text, but its default `complete_name_table=True` adds nameID 16/17/25 and instance PostScript names, and its default `fix_head_flags=True` clears the WOFF2 flag in `head.flags`. Modified-release naming is done after merging by the CLI, `merge_fonts()`, or the caller through `apply_naming()`. `apply_naming()` changes identity fields only (nameID 1, 2, 3, 4, 6, 16, 17 and copyright ID 0). It does not change the version, vendor, trademark, license records, or the axis and instance names of a variable font.

## 2. Two separate paths

### 2.1 Heterogeneous merge

The entry is `FontMerger.merge_two()` in [`core/merger.py`](../../core/merger.py). One call merges one base font. Multi-level input is a caller loop: the result of one level becomes the main font of the next.

The path classifies each side as static or variable and as glyf or CFF/CFF2. That gives 4×4, or 16, combinations. Dispatch is in `merge_two()` and the sixteen methods `_sOTF_sOTF()`, `_vTTF_vTTF()`, and their siblings. When the main font is variable and the base is static, the question offers variable or static output: variable keeps the main VF, while static instances the main font first. When both are variable, the main VF is kept and cross-design-space composition is attempted; only unsupported or failed composition falls back to instancing the base at its default.

### 2.2 Same-source subset union

The entry is `merge_subsets()` in [`core/subset_merge.py`](../../core/subset_merge.py), implemented by `SameSourceSubsetMerger`.

This path does not call `merge_two()`. For variable-by-variable inputs, `merge_two()` first attempts cross-design-space composition when supported: the main VF is kept and base deltas are re-parameterized into the merged space; glyf glyphs use object-level copy and CFF/CFF2 use TTX. Only unsupported or failed composition falls back to instancing the base, where base variation data may be lost. Same-source slices share one axis space and need neither composition nor an axis union; a direct union keeps each slice's `gvar` and layout data. Use `merge_subsets()` for that input.

Same-source detection is `is_same_source()` in [`utils/detect.py`](../../utils/detect.py): at least two fonts, all variable, identical axis sets with identical min/default/max, and identical outline technology. `merge_subsets()` treats a single slice as the base directly; it runs the same-source check only for two or more slices. The CFF/CFF2 branch requires slices to be CFF2, so a pure CFF1 slice is rejected. CFF2 slices additionally require the same VarStore and GlobalSubrs structure (see Section 8).

## 3. The 16-combination matrix

Classification uses `is_variable()` for `fvar`, `is_ttf()` for `glyf`, and CFF/CFF2 otherwise. Rows are the main font; columns are the base font.

| Main \ Base | Static OTF (CFF) | Static TTF (glyf) | Variable OTF (CFF/CFF2) | Variable TTF (glyf) |
| --- | --- | --- | --- | --- |
| Static OTF | CFF glyphs injected through TTX; CFF output | Base converted to CFF; CFF output; TTF/OTF question recorded only | Base instanced at default, CFF2→CFF when needed; static CFF output | Base instanced and converted to CFF; static CFF output |
| Static TTF | Base converted to glyf; TTF output; TTF/OTF question recorded only | glyf objects copied; TTF output | Base instanced and converted to glyf; static TTF output | Base instanced and glyf objects copied; static TTF output |
| Variable OTF | Ask variable/static. Static instances the main font. Variable keeps the main VF and merges static base glyphs at the default outline | Same, with the base converted to CFF/CFF2 first | Try CFF2 variation composition. On failure, fall back to axis union plus base instancing. Keeps a VF output | Cross-outline variation composition is unsupported. Fall back to axis union plus base instancing and conversion. Keeps a VF output; base glyphs stay static |
| Variable TTF | Ask variable/static. Static instances the main font. Variable keeps the main VF and merges static base glyphs at the default outline | Same, with the base kept as glyf | Cross-outline variation composition is unsupported. Fall back to axis union plus base instancing and glyf conversion. Keeps a VF output; base glyphs stay static | Try gvar variation composition. On failure, fall back to axis union plus base instancing; when axis space and avar match, transfer gvar 1:1. Keeps a VF output |

Matrix notes:

- The output outline technology follows the main font. The "export TTF/OTF" question in mixed-format cells is remembered but does not change the result in the current implementation. Only the "variable/static" question changes the code path. Answer keys are defined in `DEFAULT_ANSWERS` in [`__init__.py`](../../__init__.py).
- A static main font with a variable base merges the base at its default instance. Added glyphs do not vary.
- A variable main font with a static base keeps the main axis space only when the user selects variable output. Selecting static instances the main font first. Base glyphs are static and do not add axes.
- A variable main and variable base can be composed only with the same outline technology and matching variation data on both sides: `gvar` for glyf, CFF2 with a VarStore for CFF2. Composition must pass the sampled `verify_composition()` check. On an exception or failed check, the merge falls back to the legacy path. That path unions axes first and then instances the base. When axis space and `avar` match exactly, glyf base deltas can be transferred 1:1 with `transfer_glyph_variations()`. CFF2 bases have no phantom-point 1:1 transfer path, so their variation data is not retained after a fallback.
- `.woff` and `.woff2` inputs are unwrapped by `load_font()` and have `flavor` cleared. The CLI rejects `.ttc` and `.otc`; unpack them first. Supported extensions are listed in `SUPPORTED_EXTS` and `COLLECTION_EXTS`.

## 4. Single-level heterogeneous pipeline

### 4.1 Dispatch and fallback

`merge_two()` only classifies and dispatches. Business logic lives in `_do_merge()` and `_do_merge_once()`.

Composition can fail at these points:

- axis planning returns `None`, and `_apply_axis_plan()` raises `RuntimeError`;
- merged-default instancing, layout variation transfer, or CFF2 composition raises;
- `verify_composition()` fails.

`_do_merge()` catches any of these, prints `[合成] 回退到默认实例合并: <reason>`, and reruns with `compose=False`. The fallback loses information: base glyphs stay at the default instance unless axis space and `avar` match exactly and the 1:1 gvar transfer runs afterwards.

### 4.2 Steps in `_do_merge_once()`

1. Preparation. The composition path deep-copies the main font, normalizes the base UPM, calls `_apply_axis_plan()`, obtains the base at the merged default with `instance_at_merged_default()`, then conditionally runs `transfer_base_layout()` and `_compose_cff2_base()`. The legacy path runs `union_axes()` and `_reparametrize_main_after_union()`, checks `axes_compatible()`, and instances the base when deltas cannot be carried.
2. UPM normalization. If `head.unitsPerEm` differs, `_normalize_upm()` scales the base with the official `scale_upem()`, removes the old hinting environment, and corrects per-glyph VORG overrides from a pre-scale snapshot.
3. CID normalization. Four branches, listed in Table 4.3.
4. Outline alignment. Convert the base when glyf and CFF differ. For a CFF2 main with a CFF base, or the reverse, align the CFF version first.
5. Aliasing and conflicts. `_plan_merge_aliases()` aliases every same-name base glyph except `.notdef`; `renamed_copy()` updates every name-keyed structure. `resolve_conflicts()` returns glyphs to drop. If `to_add` is empty, the code diagnoses the reason, merges cmap mappings, and proceeds to finalization.
6. Glyph injection. glyf+glyf uses `merge_glyphs_object()`; CFF/CFF2/CID uses `merge_glyphs_via_ttx()`; more than 5000 candidates uses `_chunked_merge()`. Injection failure prints a reason and raises `RuntimeError`; it does not return a partial font missing codepoints.
7. Variation finish. `_finish_variable_merge()` first attaches CFF2 base HVAR data. It then either calls `reparametrize_gvar()` (and rebuilds HVAR) when a composition plan exists, or calls `transfer_glyph_variations()`. With a plan and `verify_compose` enabled, it runs the sampled check.
8. Base layout merge. `_merge_base_layout_once()` calls `merge_ot_features()`. A layout failure warns and leaves the already merged glyphs intact.
9. Finalization. `_finalize_merge()` unifies normal, empty-add, chunked, and CID exits. See Section 9.

### 4.3 CID branches

| Case | Processing | Return |
| --- | --- | --- |
| CID main + CID base | `cid_ufo_style_merge()`: `shift_cid_range()` offsets the base CIDs and preserves the main CID namespace. CharString objects are copied, base FDArray entries are appended with their own Private dictionaries, cmap/UVS are synchronized, and the result is saved and reloaded | Goes to `_finalize_merge()` |
| CID main + name-keyed base | Convert the base to CFF if needed, call `ensure_cid_format()`, then use the dual-CID path | Goes to `_finalize_merge()` |
| CFF2 main (non-CID) + CID base | Desubroutinize the CFF base, call `convertCFFToCFF2()`, keep FDArray, then inject normally | Continues the main pipeline |
| name-keyed CFF main + CID base | `cid_to_name()` normalizes the base to name-keyed | Continues the main pipeline |

The static dual-CID path no longer flattens to the first FD, and it does not require CID to name-keyed conversion first. `cid_to_name()` remains for the name-keyed normalization branches above. The CID-keyed CFF2 main-font variable-output save issue is separate from static CID/CFF merging; see [support boundaries](limitations.md).

### 4.4 Object copy and TTX round trip

| Condition | Path | Key behavior |
| --- | --- | --- |
| Both sides are glyf | `merge_glyphs_object()` | Per-glyph deep copy; component dependency closure; same-name components aliased first; `hmtx`/`vmtx`/`gvar` synchronized; `HVAR`/`VVAR` maps extended with `NO_VARIATION_INDEX`; cmap union |
| CFF/CFF2/CID | `merge_glyphs_via_ttx()` | Strip base OT tables; `saveXML` both fonts; `inject_glyphs_xml()` injects CharStrings, FDArray, glyf, metrics, VarIdxMap and maxp; compile with the `fontTools ttx` subprocess; restore glyph names from the pre-injection GlyphOrder |
| More than 5000 candidates | `_chunked_merge()` | Inject in 5000-glyph chunks; require name normalization before chunking; raise on the first failed chunk instead of returning a partial result; run variation finish, layout merge, and finalization once after all chunks |

The critical TTX constraint: post-3.0 binaries do not store glyph names. `inject_glyphs_xml()` returns the intended GlyphOrder, and the reloaded font must restore names by position. Otherwise cmap and layout references point to renumbered glyphs. The comments in `core/glyph_copy.py` document this behavior.

## 5. Glyph identity, conflicts, and mappings

### 5.1 Main priority and partial codepoint conflicts

- All main glyphs and codepoint mappings are kept. A base mapping never overrides a main mapping. `assert_cmap_union()` checks the Unicode codepoint union, main-map priority, and the UVS union.
- A base glyph is kept when it has a codepoint not present in the main font, has no codepoint, or is required by a component closure or UVS. It is dropped when all its codepoints conflict with the main font and no other dependency needs it. See `resolve_conflicts()`.
- Equal names do not prove equal outlines. Every same-name base glyph except `.notdef` is aliased by `_plan_merge_aliases()` before conflict resolution. The public `plan_alias()` keeps its older contract and returns only automatic-name aliases.
- Composite glyphs are copied with their component closure. A missing base component raises an error. A same-name component is aliased rather than borrowing the main outline (`_prepare_glyph_copy()`).
- UVS-referenced glyphs are kept even when all ordinary codepoints conflict. `validate_input_uvs()` at the heterogeneous merge entry rejects dangling UVS glyphs and invalid default UVS entries.

### 5.2 Rename synchronization

`rename_glyphs()` updates every name-keyed structure in one pass: GlyphOrder, glyf including components, CFF/CFF2 CharStrings and charset, hmtx/vmtx, cmap including format 14 UVS, HVAR/VVAR DeltaSetIndexMaps, VORG, and all glyph references in GSUB/GPOS/GDEF. `gvar` is materialized before renaming so lazy decoding does not use old names.

### 5.3 cmap and format 0

`_copy_cmap_mappings()` merges mappings in place:

- Main mappings win. Unicode subtables are synchronized by format range (format 4 uses the U+FFFE limit; format 12/13 cover the full range).
- Non-Unicode subtables keep their own encoding domain and are not filled with the Unicode union.
- Every format 0 subtable whose actual mapped GID exceeds 255 is upgraded to a format 6 subtable with the same platform, encoding, and language, preserving its mapping. GID 255 remains valid. This prevents the old 8-bit overflow at save time.
- UVS entries are unioned by selector. A default UVS entry becomes explicit when the main mapping differs and the source glyph can be retained.

### 5.4 UPM transform

UPM differences are normalized on the base side only; the main UPM does not change. `_normalize_upm()` uses the official `scale_upem()` and fixes per-glyph VORG overrides that some fontTools versions omit. Hinting and pixel caches are removed before scaling so instructions cannot keep old design units. CLI scale and baseline offset are a separate path implemented by `scale_font()`.

## 6. Variable-data composition

### 6.1 Normalization and OpenType semantics

- Three coordinate layers: `user --fvar normalization--> pre --avar--> norm`. OpenType variation data (gvar tuple supports, VarStore regions, HVAR/VVAR maps) peaks in the post-avar norm space. See `PiecewiseLinear` and `AxisMapping` in [`format/axis_mapping.py`](../../format/axis_mapping.py).
- `supportScalar` behavior: a zero peak axis is ignored; a support with `lower < 0 < upper` is ignored as a whole; hats never cross zero; domain-boundary truncation uses half hats. `refine_1d()` keeps 0 as a node. `refine_support_rebased()` handles a non-zero constant when the source and merged defaults differ.
- One gvar glyph can carry several tuples, and rendering sums their weighted deltas. A source tuple can therefore be split into several merged-space tuples. `reparametrize_gvar()` performs the split and keeps phantom points.
- A `VariationIndex` `(outer, inner)` is a VarData index and a **row** index, not a region index. `reparametrize_var_store()` keeps ItemCount and row order, redistributes columns, and leaves references valid. Union shifts only the outer base (`VarStoreUnion`).
- A CFF2 blend block is "default values, delta blocks, count, blend". The number of delta blocks follows the region count of the VarData selected by `vsindex`. `reparametrize_cff2()` rewrites CharStrings, GlobalSubrs, and Private Subrs while preserving VarData order. `merge_cff2_var_stores()` joins the stores; `offset_cff2_vsindex()` offsets base references.
- HVAR/VVAR `AdvWidthMap` and related maps are DeltaSetIndexMaps keyed by glyph name. `VarIdxMap.preWrite` requires every glyph, and glyphs without variation must receive an explicit `NO_VARIATION_INDEX`. CFF2 composition rebuilds the map by glyph name in `merge_cff2_hvar()`.
- `instantiateVariableFont()` user-coordinate limits do not apply `avar`; `getGlyphSet(location=...)` does. Verification therefore samples only each axis min/default/max (fixed points of `avar`) and compares through `getGlyphSet()` semantics (`_instance()` and `verify_composition()` in `core/verify.py`).

### 6.2 Policy parameters

Parameters are defined in `FontMerger.__init__()` in [`core/merger.py`](../../core/merger.py).

| Parameter | Type | Default | Meaning and effect |
| --- | --- | --- | --- |
| `compose_variations` | `bool` | `True` | Whether to attempt cross-design-space composition. Disabling it uses the legacy instancing and axis-union path |
| `compose_range` | `str` | `"main+extra"` | Merged axis-range policy. `"main+extra"`: shared axes use the main range, base-only axes use the base range. `"union"`: shared axes take the widest range. `"main"`: keep main axes only |
| `compose_fit` | `str` | `"exact"` | `"exact"` splits hats exactly. `"affine"` maps only support endpoints and peaks; it is smaller but has known bias, so the sampled check decides acceptance |
| `avar_mode` | `int` | `0` | `0`: keep the main avar and map base data through user space. `1`: ignore the base avar. `2`: omit avar and remove the table |
| `verify_compose` | `bool` | `True` | Run `verify_composition()` after composition. Failure raises and triggers fallback |
| `compose_layout` | `bool` | `True` | Transfer base layout variation (GDEF ItemVariationStore and GPOS VariationIndex). Disabling it freezes base layout at the default point |

The parameters affect policy only; they do not mutate input font objects. Their side effects are limited to the current call. Return and exception behavior: `merge_two()` returns a `TTFont`; composition failure falls back, while structural-check or injection failure on the ordinary path raises.

### 6.3 Composition data flow

| Step | Key functions | Result |
| --- | --- | --- |
| Plan axis space | `plan_axis_space()` | Merged fvar/avar and mappings from merged space to base space |
| Extend main and recompute main data | `_apply_axis_plan()`, `reparametrize_gvar()`, `reparametrize_var_store()`, `_copy_axis_records()` | Main fvar/avar/STAT/name updated; main gvar and GDEF/HVAR/VVAR/MVAR/BASE VarStores follow the new space |
| Instance base at merged default | `instance_at_merged_default()` | Static base outlines, metrics, and layout static values at the merged default |
| Transfer layout variation | `transfer_base_layout()`, `fold_layout_default()` | Base GDEF VarStore and GPOS VariationIndex re-parameterized with rows preserved |
| Re-parameterize gvar | `reparametrize_gvar()` | New glyphs split into merged-space tuples; HVAR rebuilt |
| Re-parameterize CFF2 | `reparametrize_cff2()`, `merge_cff2_var_stores()`, `merge_cff2_hvar()` | blend/vsindex, VarStore, and base HVAR merged |
| Verify | `verify_composition()` | Compares new glyphs against the base and main glyphs against the main font on a grid; failure raises `AssertionError` |

Verification covers a sampled grid and sampled glyphs. It is not a pointwise proof for every axis position. Default tolerances: 1 font unit for outlines, the same for advance widths unless overridden; the main pipeline uses 3.0 for advance widths. CFF2 tests use 0.01 for outlines and 4 for widths because of blend fixed-point encoding and HVAR integer rounding. Integer residuals and flat-avar limits are listed in [support boundaries](limitations.md).

### 6.4 Fallback and legacy path

After composition failure the legacy path runs:

- `union_axes()` adds base-only axes and wider ranges to the main font in place. `_reparametrize_main_after_union()` recomputes main VarStores.
- `axes_compatible()` checks exact axis space and avar equality. When they match, glyf base gvar deltas can still be transferred 1:1 and HVAR rebuilt; CFF2 bases have no such path. Otherwise delta transfer is skipped.
- The base is instanced at its default with `variable_to_static()`, then merged.

This path modifies the main font in place. Output may remain a VF, but base glyph variation can be lost. When the merged avar collapses a user interval to one normalized point, `collapsing_flats()` reports the interval and the log prints a warning. `avar_mode=2` can drop avar to recover base variation at the cost of changing main interpolation.

## 7. Layout merging

### 7.1 Heterogeneous path

The entry is `merge_ot_features()`, called by `_merge_base_layout_once()`.

1. `prune_base_layout()` uses the official `Subsetter` with the surviving glyph set as input, performs closure and layout pruning, and extracts only GSUB/GPOS/GDEF.
2. GDEF merge: GlyphClassDef and MarkAttachClassDef are main-first with base fill-in. MarkGlyphSetsDef is unioned and LookupFlag bit4 indices are remapped. GDEF VarStore regions and VarData are unioned, and base GPOS VariationIndex outers receive the base offset.
3. GSUB/GPOS merge: copy the base lookup graph in source order, verify that all referenced glyphs exist, build a complete old-to-new lookup index map, and close nested context dependencies. A context rule referencing a dropped lookup is removed as a whole instead of becoming an empty ignore rule. Same-tag features are unioned only within the same Script/LangSys; main parameters and required features take priority. Base ScriptList/LangSys entries are merged; the FeatureList is re-sorted and every feature index is rewritten.
4. FeatureVariations: when the main table is absent or empty (no lookups and no features), a valid base table including its FV can be adopted. Otherwise base FV records are not spliced across sources and main conditions are preserved. A base FV referencing a missing lookup or feature causes that table merge to be rejected and main layout preserved.
5. Finalize with `resort_layout()` to repair Coverage and parallel-array ordering.

### 7.2 Same-source union path

The same-source path uses `LayoutUnion`, with per-slice `add_from()` and a final `finalize()`.

- Every slice lookup is appended, glyph names are remapped through that slice's rename map, and VariationIndex values receive the GDEF VarData base offset.
- Same-tag features are combined within the same LangSys; required features are preserved.
- FeatureVariations requires exactly matching condition sets and their order across slices. A mismatch raises `ValueError` instead of performing a lossy union. Records at the same position are combined, and empty substitutions are kept.
- The FeatureList is sorted by tag; default, required, and FV feature indices are rewritten; `resort_layout()` runs at the end.

### 7.3 Ordering and reference invariants

After layout pruning or GID changes:

- Coverage glyphs stay in ascending GID order. PairPos Format 1 PairValueRecords stay sorted by second glyph GID. Coverage and parallel arrays in MarkBase/MarkLig/MarkMark stay in the same order.
- Context/ChainContext Format 1 Coverage and RuleSets stay paired. ReverseChainSingleSubst Coverage and Substitute stay paired.
- LookupFlag bit4 MarkFilteringSet indices point to existing GDEF mark sets.
- After FeatureList sorting, ScriptList/LangSys FeatureIndex values, FeatureVariations FeatureIndex values, and substitution lookup indices remain valid.

`resort_layout()` in `tables/layout_union.py` is the shared finalizer. `_check_layout_integrity()` and `_check_lookup_references()` provide structural checks.

## 8. Same-source subset union

`merge_subsets()` merges in input order, and `subsets[0]` is the base that receives the result in place. Core steps:

1. Force-load per-glyph tables. Call `glyf.ensureDecompiled()` so components do not keep old GIDs.
2. Check same-source input with `is_same_source()`. For CFF2, `check_cff2_compatible()` also checks GlobalSubrs and VarStore structure.
3. Build a rename map per slice with `rename_map()`: automatic `glyphNNNNN` names and same-name glyphs referenced by that slice's layout are aliased; other duplicate names are treated as same-source glyphs and deduplicated.
4. Merge GDEF first: the VarStore union returns a base offset and the MarkGlyphSets union returns an index map. GPOS VariationIndex depends on that base.
5. Copy outlines and metrics per glyph. glyf copies glyf/hmtx/vmtx/gvar. CFF2 copies CharStrings and FDSelect; FDArray is deduplicated by content (`FDUnion`).
6. Union cmap. `_harmonize_cmap()` makes each Unicode subtable cover all codepoints within its format limit.
7. Append and remap GSUB/GPOS with `LayoutUnion`.
8. Finalize layout before glyph reordering. Reorder GIDs by codepoint, run `resort_layout()`, and for CFF2 run `sync_glyph_order()` to synchronize charset and FDSelect.
9. HVAR/VVAR: the glyf path rebuilds HVAR from phantom points of the merged gvar. CFF2 and VVAR use VarStore union and DeltaSetIndexMap rebasing, with missing entries filled by `NO_VARIATION_INDEX`.
10. Recompute head/hhea/vhea/maxp/OS/2 metrics. Complete nameID 16/17/25 and instance PostScript names. Clear the WOFF2 flag bit in `head.flags`.
11. Optionally run `verify_merge()`; save with `save_font()`. The result carries `subset_merger`, and `glyph_map()` maps each slice's source glyph names to merged GIDs.

CFF2 union requires slices to share VarStore and GlobalSubrs. FDArray differences are handled by FD-level union. Mixed CFF and CFF2 slices are unsupported. Inputs whose structure was rebuilt raise `IncompatibleCFF2Error` instead of producing a broken font.

## 9. Finalization and invariants

`_finalize_merge()` runs on ordinary, empty-add, chunked, and CID exits:

| Stage | Function | Effect |
| --- | --- | --- |
| Hinting | `apply_hinting_policy()` | Compatible global programs expand maxp resources. If the old font has no interpreter environment at all, the base program can be adopted as a bundle with a warning. Otherwise new glyph instructions are stripped |
| Table policy | `apply_table_policy()` | Drops invalid DSIG/hdmx/LTSH/VDMX, unions safe legacy kern data, and unions CFF VORG origins; keeps the main table when an origin cannot be recovered; meta/trak/gasp keep main policy and warn when base-only |
| Metadata | `recalc_after_merge()` | Removes stale metrics; recomputes head bounds, maxp, hhea/vhea, and OS/2 ranges and average width; Win metrics only grow |
| Layout ordering | `resort_layout()` | Repairs Coverage and parallel-array ordering |
| Structural checks | `assert_cmap_union()`, `assert_font_structure()` | Exact Unicode/UVS union, main-map priority, and complete glyph/metric/layout/VarStore references |

Library save points go through `save_font()`: it sets `flavor`, saves, and validates the sfnt magic. This prevents a WOFF2-loaded font from being written as a file named `.ttf` with `wOF2` magic. `merge_two()` does not save; callers should use `save_font()` or handle `flavor` themselves.

Input ownership summary:

| Function | Modifies input |
| --- | --- |
| `merge_two()` | Returns a new font on the normal path; the legacy axis-union fallback modifies the main font |
| `merge_fonts()` | Deep-copies the main font; does not modify a `TTFont` passed by the caller |
| `merge_subsets()` | Modifies `subsets[0]` |
| `scale_font()` / `apply_scale_offset()` | In place; returns the same `TTFont`. `scale=1` and `baseline_offset=0` return unchanged; invalid arguments or a VARC font raise `ValueError` |
| `union_axes()` | In place on main |
| `rename_glyphs()` / `apply_naming()` | In place |

## 10. Modules, dependencies, and extension points

Layer direction:

```text
__init__.py / FontMerging.py
        |
        v
      core/  --->  format/  --->  utils/
        |  \-->  tables/
        \---->  utils/
```

Module summary:

| Layer | Main files | Responsibility |
| --- | --- | --- |
| Entry | `__init__.py`, `FontMerging.py` | Exports, loading, convenience API, interactive CLI |
| core | `merger.py`, `glyph_copy.py`, `glyph_rename.py`, `conflict.py`, `naming.py`, `subset_merge.py`, `verify.py`, `hinting_policy.py`, `table_policy.py`, `invariants.py` | Dispatch, composition and fallback, injection, renaming, naming, verification, finalization policy |
| format | `axis_mapping.py`, `variation_compose.py`, `cff2_compose.py`, `cff2_union.py`, `vf_axes.py`, `converter.py`, `static_extract.py`, `cid_convert.py`, `cid_merge.py`, `transform.py`, `subsetter.py`, `webfont.py` | Axis math, variation re-parameterization, outline and format conversion, CID, scaling, subsetting |
| tables | `ot_merge.py`, `layout_union.py`, `varstore.py`, `metadata_recalc.py`, `maxp.py`, `base.py`, and single-table handlers | Layout union, VarStore union, metadata recalculation, table registry |
| utils | `detect.py`, `save.py` | Type and same-source detection, save guard |

Known dependency exceptions (current state, not a reason to add more):

| Exception | Location | Note |
| --- | --- | --- |
| `tables/` to `core/` | `tables/cmap.py` module-level import of `..core.glyph_copy._copy_cmap_mappings` | Legacy reverse import from the table registry path |
| `format/` to `tables/` | `format/cff2_compose.py` function-local import of `..tables.varstore.VarStoreUnion` | CFF2 composition reuses the ItemVariationStore union |
| `format/` to `core/` | `format/cid_merge.py` function-local imports of `..core.glyph_copy._copy_cmap_mappings` and `..core.conflict.resolve_conflicts` | CID merge reuses conflict planning and cmap synchronization |
| `format/` to `tables/` | `format/cid_merge.py` function-local import of `..tables.layout_union.remap_glyph_names` | Rename synchronization of layout references |

Independent table registry: `merge_all_tables()` and `TABLE_MERGE_REGISTRY` in `tables/base.py` remain callable as a standalone API, but the main pipeline does not call them. Finalization uses the explicit policy functions in Section 9. A new `@register` handler does not enter the main pipeline automatically. Wiring it requires an explicit call from the `_do_merge_once()` exit or `_finalize_merge()`, plus regression coverage. Calling the old registry on a merged font reprocesses already composed fvar and OT tables and must not be used as a finalizer.

Extension points:

- Add a finalization policy: add an explicit step in `core/table_policy.py` or `tables/metadata_recalc.py` and call it from `_finalize_merge()`. Do not depend on the unwired registry.
- Add a layout structure: add the relevant Coverage attributes and subtable branch in `tables/layout_union.py` (`_fix_subtable_order()`), and add reference checks to `_check_layout_integrity()`.
- Add an outline technology or variation data type: follow the structure signature and re-parameterization pattern in `format/cff2_union.py` and `format/cff2_compose.py`. Keep the contract that composition failure raises and triggers fallback.
- Add a public parameter: update `FontMerger.__init__()`, the `__init__.py` exports, [merge API](merge-api.md), and the parameter table here.

Locate code by function name first; line numbers may change between versions. The complete signature index is in the [parameter index](parameter-index.md).
