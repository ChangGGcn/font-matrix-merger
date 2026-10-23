# Module and script reference

This page describes the responsibility, algorithm and first entry point of every Python file and PyInstaller spec in the source repository, grouped by directory. Signatures and defaults are in the [source signature index](parameter-index.md); the merge pipeline is in [merge pipelines and data invariants](architecture.md); public APIs are in the [merge API](merge-api.md) and [helper API](helper-api.md).

## 1. Reading conventions

- Covers the 69 Python or spec files in the source repository: 47 runtime files, 3 build scripts and 19 test or fixture files.
- Files marked **runtime ZIP** ship in the release package. The runtime ZIP contains `FontMerging.py`, `__init__.py`, the Python files under `core/`, `format/`, `tables/` and `utils/`, and the public documentation.
- Files marked **repository only** exist only in the source repository: `tests/` and `build/`. These paths do not exist inside an offline ZIP, so this page uses code paths for them. Their source can be browsed at https://github.com/ChangGGcn/font-matrix-merger.
- The Entry column names the function or class to read first. It does not imply that the entry is a stable public API.
- Test scripts take no extra command-line arguments. The unified runner is `tests/run_regressions.py`, described in section 8.
- The local configuration `tests/local_fonts.py` is not committed. This page neither reads nor lists its contents; the template is `tests/local_fonts.example.py`.

## 2. Entry points and package facade

| File | Entry | Responsibility |
| --- | --- | --- |
| [FontMerging.py](../../FontMerging.py) | `run()` | Interactive CLI. Reads the main font, multiple base levels, scale percentages and baseline offsets, then calls compatibility checks, `merge_two()`, `apply_naming()` and `save_font()`. It reads no command-line positional arguments. |
| [__init__.py](../../__init__.py) | `merge_fonts()`, `load_font()` | Package facade: `__version__`, supported extension sets, `DEFAULT_ANSWERS`, font loading, the convenience merge helper and re-exports of core classes and utilities. |

### 2.1 Input and exit behavior of FontMerging.py

- Input order: main font path, scale percentage, baseline offset; then each base level repeats path, scale percentage and baseline offset; enter `Y` to finish.
- Surrounding quotes are stripped from paths. TTC/OTC inputs and unsupported extensions are rejected and re-prompted.
- After loading, adjacent inputs are checked by `check_compatibility()`. Only `ok=False` from a high-overlap dual-CID pair asks for `y`/`N`; other warnings are printed only.
- The default output path is `<main stem>_mod.otf` or `.ttf` in the main font directory. The extension follows the merged outline type.
- Save failure exits with code 1. Cancellation or a completed run exits with code 0.

## 3. core/: orchestration (runtime ZIP)

| File | Entry | Responsibility and algorithm |
| --- | --- | --- |
| [core/__init__.py](../../core/__init__.py) | module re-exports | Collects conflict, naming, glyph-injection and merger symbols for internal imports. |
| [core/merger.py](../../core/merger.py) | `FontMerger.merge_two()`, `_do_merge()`, `_do_merge_once()`, `_finalize_merge()` | 16-way dispatch; composition attempt and fallback; UPM, CID and outline-format normalization; alias and conflict handling; glyph injection; variable-data finishing; 5000-glyph chunking; shared finalizer (hinting policy, table policy, metadata recalculation, layout sorting, exit invariants). |
| [core/conflict.py](../../core/conflict.py) | `resolve_conflicts()`, `plan_alias()` | Main codepoint priority; keeps base-only codepoints plus component and UVS closure; returns the set that must not be copied; plans automatic-name aliases. |
| [core/glyph_copy.py](../../core/glyph_copy.py) | `merge_glyphs_via_ttx()`, `merge_glyphs_object()`, `inject_glyphs_xml()` | Two injection paths: object-level glyf copying and a TTX XML roundtrip for CFF/CFF2/CID. Handles post-3.0 glyph-name recovery, component renaming, cmap merging and format 0 upgrades. |
| [core/glyph_rename.py](../../core/glyph_rename.py) | `rename_glyphs()`, `renamed_copy()` | Renames glyphs once across glyf, CFF, metrics, cmap, HVAR/VVAR and layout references; provides a deep-copy variant. |
| [core/hinting_policy.py](../../core/hinting_policy.py) | `apply_hinting_policy()` | Handles TrueType instructions of newly added glyphs only; merges maxp resources when the environment is compatible; strips new-glyph instructions with a warning when compatibility cannot be shown. |
| [core/invariants.py](../../core/invariants.py) | `assert_cmap_union()`, `assert_font_structure()` | Exit checks: exact Unicode/UVS union, main mapping priority, complete glyph and layout references. Failures raise instead of returning a partial font. |
| [core/naming.py](../../core/naming.py) | `apply_naming()` | Derives `<family> mod` per language, synchronizes identity name records and PostScript names, and merges copyrights per language. Version, vendor, trademark and license records are preserved. |
| [core/subset_merge.py](../../core/subset_merge.py) | `merge_subsets()`, `SameSourceSubsetMerger.merge()`, `glyph_map()` | Same-source subset union: renaming, per-glyph copying, cmap harmonization, GDEF/VarStore/HVAR/VVAR, layout union, codepoint reorder and layout sorting, metric recalculation. |
| [core/table_policy.py](../../core/table_policy.py) | `apply_table_policy()` | Drops stale signatures and device caches; unions only standard format 0 horizontal kern; handles VORG per surviving glyph; keeps the main font's gasp/meta/trak. |
| [core/verify.py](../../core/verify.py) | `verify_merge()`, `verify_composition()`, `_check_layout_integrity()`, `_check_var_stores()` | Compares outlines and metrics glyph by glyph at sampled axis positions; checks codepoints, features, layout indices, containers and variation tables; provides the composition grid check and structural invariants. |

## 4. format/: outlines, axes and variation data (runtime ZIP)

| File | Entry | Responsibility and algorithm |
| --- | --- | --- |
| [format/__init__.py](../../format/__init__.py) | module re-exports | Collects conversion, subsetting, static extraction and webfont unwrapping. |
| [format/axis_mapping.py](../../format/axis_mapping.py) | `PiecewiseLinear`, `AxisMapping`, `refine_1d()`, `refine_support_rebased()` | Three-layer normalization; piecewise-linear fvar/avar composition and inverse; hat nodal decomposition, re-basing, flat detection and support evaluation. Pure math, independent of font objects. |
| [format/cff2_compose.py](../../format/cff2_compose.py) | `reparametrize_cff2()`, `merge_cff2_var_stores()`, `merge_cff2_hvar()`, `offset_cff2_vsindex()` | Rewrites CFF2 blend programs; reparameterizes VarStore columns; rewrites Private DICT blends; offsets vsindex when merging into another font. |
| [format/cff2_union.py](../../format/cff2_union.py) | `check_cff2_compatible()`, `FDUnion`, `copy_glyphs()`, `sync_glyph_order()` | Verifies that slice CFF2 structures support zero-relocation union; unions FDArray; copies glyphs; synchronizes charset and FDSelect. |
| [format/cid_convert.py](../../format/cid_convert.py) | `cid_to_name()`, `name_to_cid()`, `ensure_cid_format()` | CID and name-keyed conversion using Adobe-Identity-0; handles ROS, FDSelect and cmap format 14 UVS. |
| [format/cid_merge.py](../../format/cid_merge.py) | `cid_ufo_style_merge()`, `merge_cid_fonts()`, `shift_cid_range()` | Dual-CID merge: CID offsets, materialized CharString copies, and a save/reload pass that returns a name-keyed font. |
| [format/converter.py](../../format/converter.py) | `convert_font_format()`, `cff_to_glyf()`, `glyf_to_cff()` | CFF and glyf conversion (Cu2Qu/Qu2Cu approximation); rejects cross-outline conversion of variable fonts; includes Windows/Office fixes and fallback handling. |
| [format/static_extract.py](../../format/static_extract.py) | `variable_to_static()` | Instances at the default axis position; converts CFF2 to CFF; optional overlap removal is off by default. |
| [format/subsetter.py](../../format/subsetter.py) | `create_glyph_subset()` | Uses the official Subsetter for component and layout closure; keeps selected empty glyphs; removes unsupported derived caches and tables with warnings. |
| [format/transform.py](../../format/transform.py) | `scale_font()`, `apply_scale_offset()` | Applies `(x*s, y*s+offset)` while keeping UPM; handles glyf/CFF, vertical origins and TSB; removes hinting and pixel caches for non-identity transforms; rejects VARC. |
| [format/variation_compose.py](../../format/variation_compose.py) | `plan_axis_space()`, `reparametrize_gvar()`, `reparametrize_var_store()`, `transfer_base_layout()` | Plans the merged axis space; instances at the merged default; reparameterizes gvar per glyph; keeps VarStore rows during reparameterization; transfers base layout variation. |
| [format/vf_axes.py](../../format/vf_axes.py) | `union_axes()`, `_extend_avar_axes()`, `_extend_varstore_regions()` | Axis union: extends ranges, adds base-only axes, adds STAT entries, extends avar segments and every VarStore region. |
| [format/webfont.py](../../format/webfont.py) | `unwrap_webfont()` | Loads WOFF/WOFF2 and clears the container flavor. |

## 5. tables/: table and layout merging (runtime ZIP)

| File | Entry | Responsibility and algorithm |
| --- | --- | --- |
| [tables/__init__.py](../../tables/__init__.py) | import side effects | Imports the per-table modules so `@register` runs; re-exports the scheduler and registry. |
| [tables/_strategies.py](../../tables/_strategies.py) | `first()`, `max_val()`, `bitwise_or()` | Table merge value strategies: main priority, maximum, minimum, bitwise operations, sums, list and dict merging, timestamps and recalculation placeholders. |
| [tables/base.py](../../tables/base.py) | `register()`, `merge_all_tables()` | Table registry and compatibility scheduler. The main merge pipeline does not call it; per-table failures warn and continue, so it is not a complete verification step. |
| [tables/cmap.py](../../tables/cmap.py) | `merge_cmap()` | Registry handler; glyph-level cmap work happens in `core/glyph_copy.py`. |
| [tables/fvar_avar.py](../../tables/fvar_avar.py) | `merge_fvar()`, `merge_avar()` | Registry handlers that preserve the main font's fvar/avar semantics. |
| [tables/head.py](../../tables/head.py) | `merge_head()`, `fix_head_flags()` | head merging; clears the WOFF2 residue bit in `head.flags`. |
| [tables/hhea_vhea.py](../../tables/hhea_vhea.py) | `merge_hhea()`, `merge_vhea()` | hhea/vhea metric and line-spacing strategies. |
| [tables/kern.py](../../tables/kern.py) | `merge_kern()` | Registry kern merging with main-font priority. |
| [tables/layout_union.py](../../tables/layout_union.py) | `LayoutUnion`, `MarkGlyphSetUnion`, `resort_layout()`, `offset_var_devices()` | Deep glyph-name remapping; VariationIndex offsets; same-tag feature coalescing within one LangSys; nested lookup graph pruning and index rewriting; FeatureVariations index rewriting; Coverage and parallel-array sorting. |
| [tables/maxp.py](../../tables/maxp.py) | `merge_maxp()`, `_merge_hint_resources()` | Updates glyph count; expands hint resources only when the instruction environment is compatible and instructions are actually retained. |
| [tables/metadata_recalc.py](../../tables/metadata_recalc.py) | `recalc_after_merge()` | Recalculates OS/2 ranges, average width, maximum context and head bounds from the final font; does not guess a zero PANOSE; warns and keeps existing values on failure. |
| [tables/metrics.py](../../tables/metrics.py) | `merge_hmtx()`, `merge_vmtx()` | Registry handlers for horizontal and vertical metrics. |
| [tables/name_table.py](../../tables/name_table.py) | `complete_vf_name_table()`, `merge_name()` | Adds nameID 16/17/25 and instance PostScript names; registry name cleanup. |
| [tables/os2.py](../../tables/os2.py) | `merge_os2()` | Design identity follows the main font; embedding permissions are merged; the main table version is kept so no missing fields are invented. |
| [tables/ot_merge.py](../../tables/ot_merge.py) | `merge_ot_features()`, `prune_base_layout()`, `merge_base_layout()` | Prunes base layout with Subsetter closure; merges GSUB/GPOS/GDEF graphs; coalesces same-tag features within one LangSys; remaps nested indices; unions GDEF VarStore/MarkGlyphSets and remaps MarkFilteringSet. |
| [tables/otlayout.py](../../tables/otlayout.py) | `merge_gsub()`, `merge_gpos()`, `merge_gdef()` | Legacy registry handlers: keep the main layout table wholesale when it exists. |
| [tables/post.py](../../tables/post.py) | `merge_post()` | Registry post-table merging. |
| [tables/varstore.py](../../tables/varstore.py) | `VarStoreUnion` | ItemVariationStore union: deduplicates regions, concatenates VarData and returns the outer base offset. |

## 6. utils/: leaf utilities (runtime ZIP)

| File | Entry | Responsibility |
| --- | --- | --- |
| [utils/__init__.py](../../utils/__init__.py) | `*` re-export | Forwards public symbols from `detect.py`. |
| [utils/detect.py](../../utils/detect.py) | `is_cff()`, `get_family()`, `get_copyrights()`, `is_same_source()` | Type and axis-space detection, localized name selection, same-source subset detection and automatic-name recognition. |
| [utils/save.py](../../utils/save.py) | `save_font()`, `assert_sfnt()`, `default_flavor_for()` | Clears flavor, saves and checks sfnt magic; infers containers from extensions. |

## 7. build/ and packaging (repository only)

| File | Entry | Responsibility |
| --- | --- | --- |
| `build/build_exe.py` | `check()`, `build()`, `main()` | PyInstaller driver. |
| `build/font_merger.spec` | PyInstaller Analysis/EXE | Single-file packaging configuration. |
| `build/make_release_zip.py` | `collect_files()`, `build()`, `main()` | Source-only runtime ZIP. |

### 7.1 build/build_exe.py

- `--check`: runs preflight checks for the entry, spec, package directory, PyInstaller and platform. Builds nothing.
- `--install`: runs `pip install pyinstaller` when PyInstaller is missing.
- `--clean`: clears the PyInstaller cache before building.
- Products go to `build/dist/FontMerger` or `build/dist/FontMerger.exe`. Intermediate files go to `build/build/`. Neither directory is committed.
- PyInstaller cannot cross-compile. A Windows executable must be built on Windows; Linux/WSL products only exercise dependency collection.

### 7.2 build/font_merger.spec

- Uses the repository-root `FontMerging.py` as entry and sets `pathex` to the repository root so the `FontMerger` package resolves.
- Collects `fontTools` submodules plus `brotli`, `zopfli` and `xml.etree.ElementTree`.
- Does not collect AFDKO. The library does not import it.
- The spec cannot run on its own. Use `build/build_exe.py` or `python3 -m PyInstaller build/font_merger.spec`.

### 7.3 build/make_release_zip.py

- `--out PATH`: output zip. Default `dist/font-matrix-merger-v<version>.zip`.
- `--root NAME`: top-level directory inside the zip. Default `FontMerger`.
- `--quiet`: print result lines only.
- `--preview`: review preview. Additionally collects untracked, non-ignored `doc/*.md` from `git ls-files --others --exclude-standard -- doc`. It does not stage or commit them. The default output name becomes `dist/font-matrix-merger-v<version>-review.zip`.
- Regular collection: tracked runtime files and CLI (`__init__.py`, `FontMerging.py`, `*.py` under `core/format/tables/utils`), root documents (both READMEs, CHANGELOG, LICENSE) and tracked `doc/*.md`.
- Not collected: `tests/`, `build/`, private local documentation, font binaries, `*.ttx` and packaging products.
- Zip timestamps are fixed to the HEAD commit time, so repeated builds from the same commit are byte-identical. The script prints file count, size and sha256.
- Review-stage documentation is untracked and therefore absent from a regular build. Use `--preview` when a complete review asset is needed.

## 8. tests/ (repository only)

### 8.1 Runner and conventions

- Tests are plain `def test_*()` functions plus a `main()` runner. pytest is not used.
- Each test script takes no extra command-line arguments. Run one directly with `python3 tests/test_<name>.py`.
- The four baseline suites expect 21, 13, 8 and 4 cases.
- When a font is missing, the case prints `SKIP` and returns normally. `main()` still counts it as passed. Read the SKIP lines as well as the summary number.
- Unified runner `tests/run_regressions.py`:
  - No flags: the four baseline suites plus seven synthetic regression suites.
  - `--synthetic-only`: only synthetic suites that need no external fonts.
  - `--engines`: appends system HarfBuzz/FreeType tests. Cases with missing system libraries are skipped; nothing is installed.
  - The runner writes one full log per suite to a temporary directory and reports passed counts, exit codes and SKIP counts.

### 8.2 Test suites

| File | Purpose | Run |
| --- | --- | --- |
| `tests/test_axis_mapping.py` | Pure axis math: piecewise-linear maps, hat decomposition, re-basing, crossing zero, flats, VarStore row preservation. No external font is required; one optional case uses a real avar font and skips when it is absent. | `python3 tests/test_axis_mapping.py`, 13 cases |
| `tests/test_merger.py` | Merge orchestration, conflict and naming, save guard, cross-design-space composition and fallback, layout and variation preservation. | `python3 tests/test_merger.py`, 21 cases |
| `tests/test_subset_merge.py` | Same-source subset union, codepoint and feature retention, CFF2 subsets, save/reload, glyph_map. | `python3 tests/test_subset_merge.py`, 8 cases |
| `tests/test_cff2_compose.py` | CFF2 blend/vsindex reparameterization, Private blends and cross-font merging. | `python3 tests/test_cff2_compose.py`, 4 cases |
| `tests/test_cmap_regressions.py` | Synthetic-font regressions for codepoint priority, subtable synchronization, UVS, components and CID. | `python3 tests/test_cmap_regressions.py` |
| `tests/test_layout_regressions.py` | Layout union: context lookups, LangSys isolation, FeatureVariations, kern and Coverage ordering. | `python3 tests/test_layout_regressions.py` |
| `tests/test_transform_regressions.py` | Scale and baseline offset, vertical origins, hinting policy and outline-conversion saves. | `python3 tests/test_transform_regressions.py` |
| `tests/test_metadata_regressions.py` | OS/2, head, maxp, hinting, VORG, kern and table-policy regressions. | `python3 tests/test_metadata_regressions.py` |
| `tests/test_naming_regressions.py` | Localized naming, RIBBI and PostScript names, copyright merging and idempotence. | `python3 tests/test_naming_regressions.py` |
| `tests/test_invariants.py` | Exit invariants: codepoint union, main mapping, nested indices, failure paths and UPM/VORG. | `python3 tests/test_invariants.py` |
| `tests/test_subset_regressions.py` | Subset closure, empty-glyph retention and explicit removal of unsupported tables. | `python3 tests/test_subset_regressions.py` |
| `tests/test_engine_regressions.py` | Layout execution and loading through system HarfBuzz/FreeType; skips missing libraries. | `python3 tests/test_engine_regressions.py`, or the runner with `--engines` |

### 8.3 Fixtures, generators and configuration

| File | Purpose | Usage |
| --- | --- | --- |
| `tests/__init__.py` | Package marker so `tests.*` imports work. | Imported by tests. |
| `tests/subset_fixture.py` | Builds same-source slices and a rich VF with pyftsubset, cached per process. | Imported by tests and generators. |
| `tests/cff2_fixture.py` | Builds a CFF2 main/base pair with disjoint glyphs and different axis spaces, cached per process. | Imported by tests. |
| `tests/generate_matrix.py` | Generates the 16-combination matrix and mixed fonts under `test/samples/matrix/` outside the repository. | `python3 tests/generate_matrix.py`; prints missing roles and skips the whole run when a font is absent. |
| `tests/generate_samples.py` | Generates six usage samples under `test/samples/` outside the repository. | `python3 tests/generate_samples.py`; individual samples may SKIP. |
| `tests/local_fonts.example.py` | Template for the local licensed-font role mapping. | Copy to `tests/local_fonts.py` and fill roles. The real file is not committed. |
| `tests/run_regressions.py` | Unified regression runner. | `python3 tests/run_regressions.py`, optionally with `--synthetic-only` or `--engines`. |

## 9. Runtime ZIP and repository-only files

| Category | Contents | Notes |
| --- | --- | --- |
| Runtime ZIP | `FontMerging.py`, `__init__.py`, `*.py` under `core/`, `format/`, `tables/` and `utils/`, both READMEs, CHANGELOG, LICENSE and public `doc/` Markdown. | The top-level directory after extraction is `FontMerger/`. Relative links from documentation to runtime source resolve inside the ZIP. |
| Repository only | `tests/`, `build/`, private local documentation, `dist/`, fonts and local configuration. | These paths are absent from an offline ZIP. Entries above use code paths, not relative links. |
| Review preview | Untracked `doc/*.md`. | Collected explicitly by `build/make_release_zip.py --preview` without staging or committing. |

Use the actual build output before publication: `python3 build/make_release_zip.py` or `python3 build/make_release_zip.py --preview` prints the file list, size and sha256.

## 10. Next reading

[merge API](merge-api.md), [helper API](helper-api.md), [same-source subsets and verification](subsets-and-verification.md), [axis mapping and variation composition](variation-model.md), [merge pipelines and data invariants](architecture.md), [limitations](limitations.md), [source signature index](parameter-index.md). Documentation index: [../README.md](../README.md).
