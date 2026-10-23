# Usage guide

This page gives runnable examples for installation, the command-line tool, library calls and same-source subset merging. Defaults are defined by the source code. Full signatures are in the [source signature index](parameter-index.md); merge policy is described in [merge API](merge-api.md); subset and verification details are in [same-source subsets and verification](subsets-and-verification.md); support boundaries are in [limitations](limitations.md).

## 1. Environment and layout

### 1.1 Runtime dependencies

| Dependency | Requirement | Notes |
| --- | --- | --- |
| Python | ≥ 3.8 | Syntax baseline. |
| fontTools | ≥ 4.49 | The only required third-party package. |
| brotli | Optional | Needed to read or write WOFF2. WOFF and TTF/OTF do not need it. |
| AFDKO | Not required | The runtime does not import AFDKO, and the PyInstaller spec does not collect it. |
| pytest, uharfbuzz, pathops | Not required | Tests are plain scripts; verification does not depend on these packages. |

Install:

```bash
pip install "fonttools>=4.49"
# For WOFF/WOFF2 support
pip install brotli
```

### 1.2 Source checkout

Clone into a directory named `FontMerger`:

```bash
git clone https://github.com/ChangGGcn/font-matrix-merger.git FontMerger
cd FontMerger
python3 FontMerging.py
```

The package name comes from the directory name. `FontMerging.py` inserts its parent directory into `sys.path` and then runs `from FontMerger import ...`. If the directory has another name, for example the default clone name, that import fails. Rename it to `FontMerger`, or create a `FontMerger` entry that points to the checkout. For library imports outside the CLI, also put that parent directory on the import path.

Library imports need the parent directory on the import path:

```bash
cd ..
python3 -c "import FontMerger; print(FontMerger.__version__)"
```

### 1.3 Runtime ZIP

The release ZIP has a top-level directory named `FontMerger/`. After extraction:

```bash
python3 FontMerger/FontMerging.py
```

Library import:

```bash
cd <extraction directory>
python3 -c "import FontMerger; print(FontMerger.__version__)"
```

The runtime ZIP contains the library, the CLI and the public documentation. `tests/` and `build/` exist only in the source repository; see the [module and script reference](script-reference.md).

## 2. Interactive CLI

```bash
python3 FontMerging.py
```

The CLI does not read command-line positional arguments. All input comes from terminal prompts. For scripted use, call `merge_fonts()` or `FontMerger.merge_two()`; see section 3 and the [merge API](merge-api.md).

### 2.1 Input sequence

| Order | Prompt | Default | Unit | Effect |
| --- | --- | --- | --- | --- |
| 1 | Main font path | none | path | Main font; its glyphs and mappings take priority. |
| 2 | Scale (%) | 100 | percent | Applies `(x*s, y*s)` to the main font outlines and metrics. |
| 3 | Baseline offset | 0 | font design units (FU) | Translates along y after scaling, positive upward. |
| 4+ | Base font path for level n | none | path | One prompt per level; enter `Y` to finish. |
| 5 | Scale and baseline offset for each base | 100, 0 | as above | Set independently from the main font. |
| last | Output path | `<main dir>/<main stem>_mod.otf` or `.ttf` | path | Press Enter to accept; the extension selects the container. |

- Leading and trailing single or double quotes are stripped from paths. Paths with spaces can be pasted inside quotes.
- There is one main font and one or more base fonts. Base fonts are merged level by level in the order entered.
- Enter `Y` (case-insensitive) to finish the base list.

### 2.2 Scale and baseline offset

- `100` means no scaling; `110` means a factor of 1.1. A non-finite or non-positive scale raises `ValueError`.
- The baseline offset is interpreted in font design units. Scaling is applied first: `y' = s*y + offset`. A positive offset moves upward.
- The main font and each base font receive their own values. The transform is applied in place to the in-memory `TTFont` and does not modify input files.
- A non-identity transform removes unsafe hinting and pixel caches (cvt, cvar, fpgm, prep, gasp, hdmx, LTSH, VDMX, DSIG) and prints one warning per removed item. UPM is unchanged.
- Fonts containing VARC raise `ValueError` for baseline transforms.

### 2.3 Compatibility warnings and prompts

After loading, the CLI checks adjacent inputs in entry order and prints `[警告]` lines:

| Case | Output | Confirmation required |
| --- | --- | --- |
| Mixed outline formats (CFF and glyf) | The base font will be converted | No |
| Variable base font | The base will be instanced to static first; use `merge_subsets()` for same-source slices | No |
| Variable main font | The default path keeps the main variable font and merges base glyphs at the default instance | No |
| UPM mismatch | The base font will be scaled | No |
| High overlap between two CID character sets | The merge may add no glyphs | Yes, enter `y` or `N` |

Export-format questions (TTF/OTF) only record an answer and do not change the output outline format. The output format follows the main font; base outlines are converted to it. Only the variable/static question changes the code path. Answers are stored in `FontMerger.mem` and reused at later levels.

### 2.4 Output

- The default file name is `<main dir>/<main stem>_mod.otf` or `.ttf`. The extension follows the merged outline type: CFF results use `.otf`, glyf results use `.ttf`.
- The final prompt asks for the output path. Press Enter to accept the default.
- If the output path ends in `.woff` or `.woff2`, the CLI selects a web container through `default_flavor_for()`. WOFF2 output requires brotli.
- On save failure the CLI prints the exception and exits with code 1. A completed run returns 0.

## 3. Non-interactive call: merge_fonts

### 3.1 Complete call

```python
from FontMerger import merge_fonts, save_font

# Static inputs: no interactive questions.
merged = merge_fonts("Main.otf", ["Base-One.otf", "Base-Two.ttf"])
save_font(merged, "Merged.otf")

# Variable main font: force a static output instead of keeping the VF.
merged = merge_fonts(
    "Main-VF.otf", ["Base.otf"],
    answers={"vOTF_sOTF": "静态"},
)
save_font(merged, "Merged-Static.otf")
```

`merge_fonts()` returns a new `TTFont` and does not write a file. Save through `save_font()`, which clears `flavor` and checks the desktop container magic.

### 3.2 Parameters

| Parameter | Type | Default | Meaning | Input ownership |
| --- | --- | --- | --- | --- |
| `main_font` | path or `TTFont` | required | Main font. | A path is loaded first; an object is deep-copied before merging. |
| `base_fonts` | sequence | required | One or more base fonts, merged in order. | A path is loaded first; an object may be converted or instanced internally. |
| `interactive` | `bool` | `False` | `False` pre-fills all questions from `DEFAULT_ANSWERS`; `True` prompts through `input()` for missing answers. | None. |
| `answers` | `dict` or `None` | `None` | Overrides entries in `DEFAULT_ANSWERS`; keys are internal question keys. | The input dict is not modified. |

Common answers:

- `{"vOTF_sOTF": "静态"}`: instance a variable main font before merging.
- `{"vOTF_sOTF": "可变"}`: keep the main font variable. This is the default.
- `{"sOTF_sTTF": "OTF"}`: the export-format question for a static OTF main font with static TTF bases. The answer is recorded only.

Defaults: `DEFAULT_ANSWERS` selects `"可变"` for a variable main font with static bases. The complete key and default table is in the [source signature index](parameter-index.md).

### 3.3 Return value and side effects

- Returns a `TTFont` with naming already applied by `apply_naming()` and with `flavor` cleared, ready for `save_font()`.
- Writes no file and, with `interactive=False`, prints no questions.
- Input files are not modified. A passed `TTFont` object may be converted or instanced internally; use `copy.deepcopy` first if the original object is still needed.
- Naming uses `get_family(main_font)` and `get_copyrights(main_font, *bases)`; see section 6.

## 4. Variable font combinations

`merge_two()` covers 16 cases across static/variable and OTF/TTF. Rows are main fonts; columns are base fonts.

| | Static OTF base | Static TTF base | Variable OTF base | Variable TTF base |
| --- | --- | --- | --- | --- |
| **Static OTF main** | Merge CFF glyphs | Convert base to CFF, then merge | Instance the base at its default, then merge | Instance the base, convert it to CFF, then merge |
| **Static TTF main** | Convert base to glyf, then merge | Merge glyf glyphs | Instance the base, convert it to glyf, then merge | Instance the base at its default, then merge |
| **Variable OTF main** | Ask variable/static; keep the main VF or instance it | Same choice; convert the base to CFF | Try CFF2 composition; check and fall back on failure | Mixed-outline composition unsupported; instance or convert the base and keep the main VF |
| **Variable TTF main** | Ask variable/static; convert the base to glyf | Ask variable/static; keep the main VF or instance it | Mixed-outline composition unsupported; instance or convert the base and keep the main VF | Try gvar/HVAR composition; check and fall back on failure |

Rules:

- Static main plus variable base: the base is instanced to its default axis position with `variable_to_static()`, then merged through the static path.
- Variable main plus static base: choosing "variable" keeps the main VF and merges base glyphs into the main default master. Choosing "static" instances the main font first.
- Variable main plus variable base: the merger first tries cross-design-space composition. Composition requires both sides to store variation in the same outline technology: glyf pairs need gvar on both sides; CFF2 pairs need CFF2 with a VarStore on both sides. If the requirement is not met or the grid self-check fails, the merger prints `[合成] 回退到默认实例合并` and falls back to the axis-union path with the base instanced at its default.
- CFF2 bases contribute HVAR only. VVAR and Private hint variation are not transferred. Layout variation is transferred, but integer rounding leaves deviations of about 1 unit (measured 0.70 units at UPM 1000).
- Boundaries for glyf and CFF2 mixtures, base-side FeatureVariations, JP CID CFF2 main fonts and pip installation are listed in [limitations](limitations.md).
- Policy parameters (`compose_variations`, `compose_range`, `compose_fit`, `avar_mode`, `verify_compose`, `compose_layout`) are documented with defaults in the [source signature index](parameter-index.md); the model is described in [axis mapping and variation composition](variation-model.md).

Example:

```python
from FontMerger import FontMerger, load_font, save_font

merger = FontMerger(compose_variations=True, compose_range="main+extra", avar_mode=0)
merged = merger.merge_two(load_font("Main-VF.ttf"), load_font("Base-VF.ttf"))
save_font(merged, "Merged-VF.ttf")
```

`merge_two()` does not apply naming and does not write a file. To match CLI naming, call `apply_naming()` as shown in section 6.

## 5. Same-source webfont subset union

### 5.1 Complete call

```python
from glob import glob
from FontMerger import merge_subsets, verify_merge, save_font

paths = sorted(glob("webfont/ja-v2/*.woff2"))
merged = merge_subsets(paths, tag="ja")

report = verify_merge(
    paths, merged,
    glyph_map=merged.subset_merger.glyph_map(),
    axis_positions="grid",
)
if not report["ok"]:
    raise SystemExit("verify_merge failed: %s" % report["failures"][:3])

save_font(merged, "Merged-JP.ttf")
# save_font(merged, "Merged-JP.woff2", flavor="woff2")  # Requires brotli
```

One call with built-in verification:

```python
merged = merge_subsets(paths, out_path="Merged.ttf", tag="ja", verify=True)
```

`verify_merge()` compares outlines and metrics glyph by glyph at the default position and the two ends of the first axis. It also checks the codepoint union, features, layout indices and container metadata. Use `axis_positions="grid"` to add positions and `sample` to limit glyphs per subset. It does not replace HarfBuzz, FreeType or Windows rasterizer testing.

### 5.2 Parameters

| Parameter | Type | Default | Meaning | Ownership and side effects |
| --- | --- | --- | --- | --- |
| `subsets` | sequence of paths or `TTFont` | required | Slice list; order is merge order and `subsets[0]` is the base. | The base is modified in place and grows as the result. |
| `out_path` | path or `None` | `None` | Output path; `None` returns only the font. | Writes a file; the extension selects the default container. |
| `tag` | `str` | `"s"` | Alias prefix, for example `ja007.glyph00123`. | None. |
| `output_flavor` | `None`, `"woff"` or `"woff2"` | `None` | Output container. It applies when `out_path` is set; `None` infers the container from the `out_path` extension. | Sets the returned font's `flavor` when `out_path` is set. |
| `complete_name_table` | `bool` | `True` | Adds nameID 16/17/25 and instance PostScript names. | Modifies the returned font. |
| `fix_head_flags` | `bool` | `True` | Clears the WOFF2 residue bit in `head.flags`. | Modifies the returned font. |
| `verify` | `bool` | `False` | Runs `verify_merge()` after the merge and raises `AssertionError` on failure. | No file side effects. |
| `verbose` | `bool` | `True` | Only controls output from `SameSourceSubsetMerger.log()`. `False` does not control log output from lower-level functions or from `verify_merge()`. See the note below. | None. |
| `verify_kwargs` | `dict` | none | Forwarded to `verify_merge()`, for example `axis_positions` or `sample`. | None. |

`merge_subsets(verify=True)` calls `verify_merge()` without forwarding `verbose`, so verification logs still use `verify_merge()`'s own default. To control them, call `verify_merge()` separately with its own `verbose` argument. Do not put `verbose` into `verify_kwargs`: it is already a parameter of `merge_subsets()`, and passing it both explicitly and through the dict raises `TypeError`.

### 5.3 Constraints

- Inputs should come from one variable font: when several slices are passed, all must be variable, with identical axis spaces and identical outline technology. The check is `is_same_source()`. Foreign inputs raise `ValueError`; use `merge_two()` instead.
- CFF2 slices must share the same VarStore and GlobalSubrs structures. A slice whose structures were rebuilt is rejected with a clear error instead of writing a broken font. FDArray differences are handled by an FD-level union. Mixed CFF and CFF2 slices are not supported.
- `merge_subsets()` performs no instancing and no axis union. It carries over each slice's `gvar` or CFF2 blend data, HVAR/VVAR, layout lookups and GDEF variation data. The retained data and boundaries are described in [same-source subsets and verification](subsets-and-verification.md).
- The result is variable. `glyph_map()` returns `{slice label: {source glyph name: merged GID}}` with keys in input order.

## 6. Naming, copyrights and input ownership

The CLI and `merge_fonts()` apply naming automatically. `merge_two()` does not. In a manual flow:

```python
from FontMerger import (FontMerger, apply_naming, get_family,
                        get_copyrights, load_font, save_font)

main = load_font("Main.ttf")
base = load_font("Base.ttf")
merged = FontMerger().merge_two(main, base)
merged = apply_naming(merged, get_family(main), get_copyrights(main, base))
save_font(merged, "Merged.ttf")
```

What `apply_naming()` does:

- Localized family names become `<original family> mod`. NameID 1/3/4/6/16/17 are updated, and nameID 2 is filled only when it is missing. Calling it again does not add a second ` mod` suffix.
- Copyrights are merged per language with a blank line between parts. Languages present only in a base font are kept; no English translation is invented.
- The PostScript name is derived from a cleaned Unicode name plus a hash suffix, so cleaning or truncation does not create duplicates.
- Version, vendor, trademark, license and fvar/STAT names are left unchanged.
- It modifies the passed font in place and returns it.

Input ownership:

- `merge_fonts()` deep-copies the main font first, returns a new font and writes no input file.
- `merge_two()` deep-copies the main font on the composition path. The fallback and legacy axis-union paths may extend the main font in place. Copy the input first if the original object is needed.
- `merge_subsets()` modifies `subsets[0]` in place.
- `apply_naming()` and `save_font()` both modify the passed font object.

## 7. Output containers

```python
from FontMerger import save_font

save_font(font, "Merged.ttf")                    # Desktop sfnt
save_font(font, "Merged.woff2", flavor="woff2")  # Web container, requires brotli
```

| Call | Output | Notes |
| --- | --- | --- |
| `save_font(font, path)` | sfnt (TTF/OTF) | Reads the first four bytes after saving and asserts sfnt magic. |
| `save_font(font, path, flavor="woff")` | WOFF | Sets `font.flavor` before saving. |
| `save_font(font, path, flavor="woff2")` | WOFF2 | Requires brotli; fontTools raises an import error without it. |
| `default_flavor_for(path)` | Inferred from the extension | `.woff2` returns `woff2`, `.woff` returns `woff`, anything else returns `None`. |
| `merge_subsets(..., output_flavor=...)` | As above | `None` infers from `out_path`. |

Do not call `font.save()` directly on a font loaded from WOFF or WOFF2. `TTFont.flavor` keeps the original container, so the call can write a file named `.ttf` with `wOF2` magic. Route all saves through `save_font()`.

## 8. Paths, formats and common errors

| Symptom | Cause | Action |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'FontMerger'` | The repository directory is not named `FontMerger`, or its parent is not on `sys.path`. | Rename the directory or set `PYTHONPATH` as in section 1.2. |
| CLI says "请先将字体集解包 (TTC/OTC)" | The input is a font collection. | Unpack it into individual TTF/OTF files first. |
| CLI says "不支持该格式" | The extension is not `.ttf`, `.otf`, `.woff` or `.woff2`. | Convert the file before entering it. |
| WOFF2 save reports a missing module | brotli is not installed. | Install brotli, or output TTF/OTF. |
| The output does not install on Windows | A direct `font.save()` kept the WOFF2 flavor. | Use `save_font()`. |
| Base glyphs do not vary after merging | The merge used the default-instance or fallback path. | Check `[合成]` lines in the log; see [limitations](limitations.md). |

More boundaries and troubleshooting are in [limitations](limitations.md). Script and test entry points are in the [module and script reference](script-reference.md).

## 9. Next reading

Documentation index: [../README.md](../README.md). Related pages: [merge API](merge-api.md), [helper API](helper-api.md), [same-source subsets and verification](subsets-and-verification.md), [axis mapping and variation composition](variation-model.md), [merge pipelines and data invariants](architecture.md), [limitations](limitations.md), [source signature index](parameter-index.md). Project README: [../../README.md](../../README.md), [../../README.zh-CN.md](../../README.zh-CN.md).
