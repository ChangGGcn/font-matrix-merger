# Merging API and policy parameters

**English** | [简体中文](../zh-CN/merge-api.md)

This page covers the entry points that load fonts, merge one or more base fonts, and control variable-font composition policy: `load_font`, `merge_fonts`, `FontMerger`, and `DEFAULT_ANSWERS`. It describes v0.2.1; the code in [__init__.py](../../__init__.py) and [core/merger.py](../../core/merger.py) defines the behavior described here. Wording does not promise results beyond what the implementation checks.

Related pages: [usage](usage.md) for installation, CLI and complete examples; [helper-api](helper-api.md) for renaming, naming, format, layout and save helpers; [subsets and verification](subsets-and-verification.md) for `merge_subsets` and `verify_merge`; [axis mapping and variation composition](variation-model.md) for the composition math; [limitations](limitations.md) for supported boundaries.

Runtime source files are linked with relative paths such as [core/merger.py](../../core/merger.py); these links resolve both in the repository and in the runtime ZIP. The runtime ZIP contains the root modules, core/, format/, tables/, utils/, both READMEs, CHANGELOG.md, LICENSE and doc/*.md. It excludes tests/ and build/; those trees are repository-only and are referred to here as code paths, not as relative links.

## 1. Font inputs and ownership

| Entry point | Accepts | Returns |
| --- | --- | --- |
| `load_font(source)` | path (`str` or `pathlib.Path`) or an existing `TTFont` | a `TTFont`; the same object is returned when a `TTFont` is passed |
| `FontMerger.merge_two(m, b)` | two `TTFont` objects; paths are not resolved | merged `TTFont` (a new object) |
| `merge_fonts(main_font, base_fonts, ...)` | paths or `TTFont` for the main font and for each base | merged `TTFont` with `flavor` cleared |

TTC/OTC collections are outside the supported workflow: the CLI rejects `.ttc` and `.otc`, and `load_font` passes other paths to fontTools without special collection handling. WOFF and WOFF2 are accepted through `load_font` (and the CLI), which unwraps them and clears `flavor`.

### 1.1 `load_font(source)`

Signature: `load_font(source)` ([__init__.py](../../__init__.py)).

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `source` | `str`, `pathlib.Path`, or `TTFont` | required | Path to load, or an already loaded font object. |

Returns

- For `.woff` or `.woff2` paths: a new `TTFont` loaded through `FontMerger.format.webfont.unwrap_webfont`, with `font.flavor = None`.
- For other paths: a new `TTFont` built by `fontTools.ttLib.TTFont(path)`. The extension is not validated here; validation and rejection happen in the CLI.
- For any other object: the object is returned unchanged. No copy is made.

Raises: errors from `TTFont` (missing file, unreadable or malformed font). The function does not save or modify a font. It does not decode a collection index.

Example:

```python
from FontMerger import load_font

main = load_font("Main.ttf")
base = load_font("Base.woff2")  # loaded with flavor cleared
```

### 1.2 Ownership rules

| Function | May modify the passed main font | May modify a passed base font |
| --- | --- | --- |
| `load_font` | no | no |
| `merge_fonts` | no; it deep-copies `main_font` before merging | content-level modifications are not intended; internal branches use copies |
| `FontMerger.merge_two` | possibly, in the variable-by-variable fallback path described in section 3.3 | content-level modifications are not intended; lazy table decompilation can occur |

`merge_two` copies or replaces the working base in conversion, instancing and CID-normalization branches. The original base object is used for read-only planning and can be lazily decompiled by fontTools. Treat both inputs as borrowed, and pass copies when the same objects are reused elsewhere.

## 2. `merge_fonts(main_font, base_fonts, interactive=False, answers=None)`

Signature: `merge_fonts(main_font, base_fonts, interactive=False, answers=None)` ([__init__.py](../../__init__.py)).

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `main_font` | path (`str`/`Path`) or `TTFont` | required | Main font, loaded through `load_font`. |
| `base_fonts` | iterable of paths or `TTFont` | required | Base fonts in merge order; each is loaded through `load_font`. |
| `interactive` | `bool` | `False` | If `False`, `DEFAULT_ANSWERS` pre-fills `FontMerger.mem` so no question blocks. If `True`, missing answers are asked on stdin. |
| `answers` | `dict[str, str]` or `None` | `None` | Answer overrides keyed like `DEFAULT_ANSWERS`. Applied after the defaults for non-interactive use, or merged into an otherwise empty memory for interactive use. |

Returns: a merged `TTFont`. The function deep-copies the loaded main font, merges each base level through `merge_two`, applies `apply_naming` using `get_family(main_font)` and `get_copyrights(main_font, *base_fonts)`, clears `flavor`, and returns the font. It does not save a file.

Raises: everything `load_font`, `merge_two` and `apply_naming` can raise, including `ValueError` for invalid input UVS, `RuntimeError` for glyph-injection failure, `AssertionError` for a failed final invariant, and fontTools errors. Composition failures inside `merge_two` are logged and handled by its fallback; they do not become exceptions unless the fallback also fails.

Example:

```python
from FontMerger import merge_fonts, save_font

merged = merge_fonts("Main.ttf", ["Base.ttf"], answers={"vOTF_sOTF": "可变"})
save_font(merged, "Merged.ttf")  # merge_fonts does not write files
```

A second base is merged as a further level:

```python
from FontMerger import merge_fonts

merged = merge_fonts("Main.ttf", ["Base.ttf", "Base2.ttf"])
```

`answers` values must be one of the option strings that the interactive prompt offers for that key. For the variable/static keys the code compares the stored value with `"静态"`; any other string keeps the variable path, so use `"可变"` or `"静态"` exactly.

## 3. `FontMerger` object

### 3.1 `FontMerger(compose_variations=True, compose_range="main+extra", compose_fit="exact", avar_mode=0, verify_compose=True, compose_layout=True)`

Repository source: [core/merger.py](../../core/merger.py). Returns a merger object. Construction performs no font I/O. The object owns a public dictionary `mem`, initialized empty, that stores interactive answers.

| Parameter | Type | Default | Allowed values | Meaning |
| --- | --- | --- | --- | --- |
| `compose_variations` | `bool` | `True` | `True`/`False` | Master switch for composing a variable base into the merged axis space. `False` uses the legacy path. |
| `compose_range` | `str` | `"main+extra"` | `"main+extra"`, `"union"`, `"main"` | Range policy for shared axes. `"main+extra"` keeps the main range and adds base-only axes; `"union"` takes the widest range; `"main"` keeps only main axes. |
| `compose_fit` | `str` | `"exact"` | `"exact"`, `"affine"` | `"exact"` re-bases tuples exactly; `"affine"` fits one hat per tuple and can carry a known deviation. The self-check normally rejects `"affine"` on real fonts. |
| `avar_mode` | `int` | `0` | `0`, `1`, `2` | `0` respects the main `avar`; `1` ignores the base `avar` and uses the main one; `2` drops the output `avar`. |
| `verify_compose` | `bool` | `True` | `True`/`False` | Run a sampled grid comparison before accepting composed outline and advance data. A failed check triggers the documented fallback. |
| `compose_layout` | `bool` | `True` | `True`/`False` | Also re-parameterize the base's GDEF ItemVariationStore and GPOS VariationIndex devices. `False` freezes base layout variation at the merged default. |

The six parameters are used only when both main and base are variable. They do not change static merges, naming, or saving. Fixed-point rounding effects are described in section 6.

### 3.2 `ask(self, key, q, opts=None)`

Signature: `ask(key, q, opts=None)`.

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `key` | `str` | required | Memory key; also the `DEFAULT_ANSWERS` key used by callers. |
| `q` | `str` | required | Question printed to stdout. |
| `opts` | `list[str]` or `None` | `None` | If given, the caller prints the options and the answer is one of them; the user selects by 1-based index. If `None`, free text is returned. |

Returns: the stored answer string. If `key` already exists in `self.mem`, the stored value is returned and the question is not asked. Otherwise the function blocks on `input()`, stores the answer in `self.mem` and returns it. It prints `[询问]` or `[记忆]` lines.

Raises: `EOFError` or `KeyboardInterrupt` from `input()` are not caught. No default value is supplied when the prompt is shown.

### 3.3 `merge_two(m, b)`

Signature: `merge_two(m, b)`. Both parameters are `TTFont` objects; paths are not accepted.

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `m` | `TTFont` | required | Main font. Its glyphs and Unicode mappings have priority. |
| `b` | `TTFont` | required | Base font. Only the glyphs and mappings that survive the conflict plan are copied. |

Returns: a merged `TTFont` for one level. The function does not apply naming, does not save, and does not clear `flavor`.

Behavior:

1. Validates default UVS and explicit UVS glyph references in both inputs. A default UVS entry whose base code point has no ordinary Unicode mapping raises `ValueError` before any merging work.
2. Dispatches on four properties: main static/variable, main CFF/glyf, base static/variable, base CFF/glyf.
3. For a variable base it first tries the composition path configured by the six policy parameters, and falls back to instancing the base at its default when that path raises or the sampled self-check fails.
4. Normalizes UPM, CID format, outline format and glyph-name collisions, injects glyphs, merges pruned base layout features, then runs the finalizer. The finalizer reconciles hinting, small-table policy, official metadata recalculation, layout ordering, and Unicode/UVS plus structure invariants.

Input side effects:

- In the variable-by-variable path, when composition is disabled or raises and the fallback is used, `m` can be extended in place (fvar/avar/varStore updates). Pass a copy when the same object must be preserved. The composition path starts by deep-copying `m`.
- The base is treated as read-only. Conversion, instancing and CID normalization branches work on copies, and fontTools may lazily decompile tables on either input.
- `self.mem` may gain answers when questions are asked.

Raises:

| Exception | When |
| --- | --- |
| `ValueError` | Invalid default UVS or dangling UVS glyph in an input; unsupported conversion of a variable font between outline technologies; other explicit validation failures. |
| `RuntimeError` | Glyph injection failed; the merger refuses to return a partial font. |
| `AssertionError` | The final codepoint, UVS or structure invariants failed. |
| fontTools errors | Malformed tables or compile/save errors that are not converted by the merger. |

Composition failures are logged with `[合成] 回退到默认实例合并: ...` and handled by the fallback; they are not raised unless the fallback path also fails.

## 4. Dispatch and question effects

| Main type | Base type | Path | Questions asked | Actual effect of the answer |
| --- | --- | --- | --- | --- |
| static | static | convert base to the main outline format if needed, then merge | `sOTF_sTTF` or `sTTF_sOTF` when the outline formats differ | Recorded in `mem`; the current code does not branch on it, and the output outline follows the main font. |
| static | variable | instance base at its default axis values, then merge | none | n/a |
| variable | static | keep or instance the main variable font, then merge | `vOTF_sOTF` / `vOTF_sTTF` / `vTTF_sOTF` / `vTTF_sTTF`; `vOTF_sTTF2` or `vTTF_sOTF2` is asked when `"静态"` is chosen | `"静态"` instances the main font; any other value keeps it variable. The second question is recorded; the current code does not branch on it. |
| variable | variable | composition attempt, then legacy fallback | `vOTF_vTTF` or `vTTF_vOTF`; `vOTF_vOTF` and `vTTF_vTTF` ask nothing | Recorded in `mem`; the current code does not branch on it. The merged outline follows the main font. |

All branches share the conflict plan: the main font keeps its glyphs and Unicode mappings; base glyphs are copied only when their code points or closure requirements survive; base glyph names that collide with main names are aliased; base layout features are pruned to surviving glyphs and merged with main priority.

## 5. `DEFAULT_ANSWERS`

`DEFAULT_ANSWERS` in [__init__.py](../../__init__.py) is a module-level dictionary from question key to default answer. Its exact contents:

```python
DEFAULT_ANSWERS = {
    "sOTF_sTTF": "OTF", "sTTF_sOTF": "TTF",
    "vOTF_sTTF2": "TTF", "vTTF_sOTF2": "TTF",
    "vOTF_sOTF": "可变", "vOTF_sTTF": "可变",
    "vTTF_sOTF": "可变", "vTTF_sTTF": "可变",
    "vOTF_vTTF": "OTF", "vTTF_vOTF": "TTF",
}
```

| Key | Default | Question text | Options | Current effect |
| --- | --- | --- | --- | --- |
| `sOTF_sTTF` | `"OTF"` | 导出为 TTF 还是 OTF？ | `"OTF"`, `"TTF"` | Recorded only; output follows the main font. |
| `sTTF_sOTF` | `"TTF"` | 导出为 TTF 还是 OTF？ | `"TTF"`, `"OTF"` | Recorded only; output follows the main font. |
| `vOTF_sOTF` | `"可变"` | 导出为可变/静态？ | `"可变"`, `"静态"` | Used. `"静态"` instances the main font before merging. |
| `vOTF_sTTF` | `"可变"` | 导出为可变/静态？ | `"可变"`, `"静态"` | Used. `"静态"` instances the main font. |
| `vOTF_sTTF2` | `"TTF"` | TTF/OTF？ | `"TTF"`, `"OTF"` | Recorded only; the static path returns the CFF-based instance. |
| `vTTF_sOTF` | `"可变"` | 导出为可变/静态？ | `"可变"`, `"静态"` | Used. `"静态"` instances the main font. |
| `vTTF_sOTF2` | `"TTF"` | TTF/OTF？ | `"TTF"`, `"OTF"` | Recorded only; the static path returns the glyf-based instance. |
| `vTTF_sTTF` | `"可变"` | 导出为可变/静态？ | `"可变"`, `"静态"` | Used. `"静态"` instances the main font. |
| `vOTF_vTTF` | `"OTF"` | OTF/TTF？ | `"OTF"`, `"TTF"` | Recorded only; output follows the main font (CFF). |
| `vTTF_vOTF` | `"TTF"` | TTF/OTF？ | `"TTF"`, `"OTF"` | Recorded only; output follows the main font (glyf). |

Six keys are still asked and stored for CLI compatibility, but the current dispatch code does not read them. Only the four variable/static keys affect control flow. When you preset answers, use the exact option strings shown above; for the four control keys, the comparison is `answer == "静态"`.

Non-interactive preset:

```python
from FontMerger import DEFAULT_ANSWERS, FontMerger

merger = FontMerger()
merger.mem = dict(DEFAULT_ANSWERS)
merger.mem["vOTF_sOTF"] = "静态"
```

`merge_fonts(..., interactive=False, answers={...})` copies `DEFAULT_ANSWERS` first and then applies `answers`. `interactive=True` keeps only the explicitly supplied answers, so every other required key blocks on stdin.

## 6. What the merge guarantees and what it does not

Guaranteed and checked at the merge exit:

- Unicode code points from main and base form a checked set union; the main mapping wins for a shared code point.
- UVS sequences form a checked union; a default UVS entry is resolved by its effective glyph, not by its `None` form alone.
- Main glyphs are not replaced by base glyphs with the same name; colliding base names are aliased and their components and UVS references are remapped.
- Base layout features are pruned to surviving glyphs; conflicts resolve in favor of the main font.
- The final structure is checked for glyph order, metrics coverage, cmap/UVS references, layout indices, and variation store structure.

Not guaranteed:

- Pointwise equality at every axis position. Variable composition is accepted after a sampled grid comparison (`verify_composition` with `max_positions=4` and outline tolerance 1.0 font unit; advance tolerance 3.0 units in this call site), and the merge falls back to instancing the base at its default when the check fails.
- Preservation of all base features. A base lookup is kept only when its referenced glyphs survive; main conflicts win; a base FeatureVariations is not merged into an existing main FeatureVariations cross-source.
- Lossless integer variation. GDEF and GPOS VariationIndex deltas are integers, so re-parameterized columns are rounded; measured kerning variation deviation is about 0.70 font units at UPM 1000. CFF2 HVAR advances are also integer-rounded.
- Identical rendering in every engine or rasterizer. fontTools serialization and sampled outline comparisons do not validate a rasterizer.

## 7. Errors seen by callers

| Situation | Surface |
| --- | --- |
| Invalid default UVS in an input (base code point has no ordinary mapping) | `ValueError` from `merge_two` before merging |
| Dangling explicit UVS glyph in an input | `ValueError` from `merge_two` |
| Glyph injection failure | `RuntimeError` (no partial font is returned) |
| Final codepoint/UVS/structure invariant failure | `AssertionError` |
| Composition path exception | Logged; fallback runs; no exception unless the fallback fails |
| Missing file or malformed font | fontTools exception propagated |

See [limitations](limitations.md) for the supported input matrix and known gaps.
