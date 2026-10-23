# Subsets and verification

[简体中文](../zh-CN/subsets-and-verification.md) | [Variation model](variation-model.md) | [Parameter index](parameter-index.md)

## 1. Scope

Same-source union is for unicode-range subsets of one variable font. It does not plan a new cross-design axis space.
For multiple inputs, [is_same_source](../../utils/detect.py#L122) checks fvar axis spaces and outline types.
This is not a provenance check and does not establish matching avar, hinting or other table contents.
Input order determines the base and the first records retained on conflicts.

The path supports glyf/gvar and structurally compatible CFF2 subsets.
CFF2 requires compatible VarStore / GlobalSubrs; FDArray entries are unioned by content.
Incompatible structures are rejected. Arbitrary CFF2 subsets are not promised to retain every feature.
When multiple subsets supply FeatureVariations, their condition sequences must match in both contents and order.
[LayoutUnion.add_from](../../tables/layout_union.py#L621) raises ValueError for differing sequences rather than joining conditions lossily.

Sources: [SameSourceSubsetMerger](../../core/subset_merge.py#L91), [CFF2 compatibility checks](../../format/cff2_union.py).

## 2. load_subsets

`load_subsets(subsets)` is a package-root export.

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `subsets` | iterable[path / TTFont] | required | Mixed input sequence in merge order | Paths are opened; objects are returned unchanged |

Returns two lists: `(fonts, labels)`.
Paths are read through root `load_font`; WOFF/WOFF2 are unwrapped and flavor is cleared.
Path labels are basenames. Object labels are `subset000`, `subset001` and so on.
Paths with the same basename produce duplicate labels; later glyph-map entries overwrite earlier ones.
Use unique filenames or pass unique labels to the lower-level merge method.
Loading errors propagate to the caller.
Source: [load_subsets](../../core/subset_merge.py#L708).

## 3. SameSourceSubsetMerger

### 3.1 Construction and state

`SameSourceSubsetMerger(tag="s", verbose=True)`.

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `tag` | str | `"s"` | Alias prefix; falsey values become "s" | Stored on the merger |
| `verbose` | bool | `True` | Print this merger's progress | Does not control all lower-level output |

Returns a merger that stores union state; it does not open font files.
Use a new instance for each independent merge. The merge method does not reset accumulated state.
Construction does not verify or save a font.

### 3.2 rename_map

Static method: `rename_map(base, main_names, tag, index, layout_names=frozenset())`.

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `base` | TTFont | required | One source subset | Read-only glyph order |
| `main_names` | set[str] | required | Names already reserved by the result | Copied to a working set |
| `tag` | str | required | Alias prefix | Read-only |
| `index` | int | required | Subset number used in aliases | Read-only |
| `layout_names` | set-like[str] | `frozenset()` | Names referenced by this subset's layout | Read-only; empty by default |

Returns `{old_name: new_name}` only for names needing aliases, without modifying a font.
.notdef is not renamed. Automatic sequence names always receive aliases.
Other collisions receive aliases when referenced by that subset's layout; remaining names reuse existing same-source glyphs.
Source: [rename_map](../../core/subset_merge.py#L151).

### 3.3 merge

`merge(subsets, labels=None)`.

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `subsets` | iterable[TTFont] | required | Nonempty ordered subset sequence; at least two must pass the same-source check | First font is modified in place; later fonts may be lazily loaded/decompiled |
| `labels` | sequence[str] / None | `None` | Unique label per subset; None/falsey generates "0", "1", ... | Copied to a list; caller must match its length to inputs |

Returns the first TTFont, modified in place.
It unions outlines, metrics, supported variation data and layout, reorders GIDs, and synchronizes related tables.
The lower-level method does not complete names, clear save flags, attach subset_merger, invoke verify_merge, or save files.
Empty inputs raise ValueError; multiple non-same-source inputs raise ValueError; unsupported CFF/CFF2 structures can raise NotImplementedError.
Incompatible FV conditions can raise ValueError. The first font may already have changed before an exception; rollback is not promised.
Source: [merge](../../core/subset_merge.py#L181).

### 3.4 glyph_map

`glyph_map()` takes no arguments and returns `{label: {source_name: result_GID}}`.
GIDs are integers calculated from the final_order recorded by merge, not glyph names.
The map includes .notdef; verification skips that glyph.
Do not reuse these GIDs after externally reordering the result.
Source: [glyph_map](../../core/subset_merge.py#L606).

### 3.5 log

`log(*args)` accepts arbitrary positional arguments, with no extra defaults.
It calls `print(*args, flush=True)` when verbose is true and otherwise produces no output. It returns None.
It controls this merger's messages, not all lower-level printing.
Source: [log](../../core/subset_merge.py#L117).

## 4. merge_subsets

`merge_subsets(subsets, out_path=None, tag="s", output_flavor=None, complete_name_table=True, fix_head_flags=True, verify=False, verbose=True, **verify_kwargs)`.

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `subsets` | iterable[path / TTFont] | required | Ordered same-source subsets, not unrelated families | Objects are reused; subsets[0] is modified in place |
| `out_path` | path / None | `None` | Output path; None means no file is written | Writing goes through save_font |
| `tag` | str | `"s"` | Alias prefix | Passed to a new merger instance |
| `output_flavor` | str / None | `None` | With out_path: infer from extension for None; explicit "woff"/"woff2" overrides it | Not assigned to the returned font when out_path is None |
| `complete_name_table` | bool | `True` | Fill nameID 16/17/25 and named-instance PS names | Mutates result name/instance data |
| `fix_head_flags` | bool | `True` | Clear head.flags WOFF2 residue bit 11 | Mutates result head |
| `verify` | bool | `False` | Run verify_merge before saving; failure raises AssertionError | Has the source/label limits described below |
| `verbose` | bool | `True` | Control merger progress messages | Not forwarded as verify_merge.verbose |
| `**verify_kwargs` | keyword arguments | `{}` | Forward additional verification options when verify=True | Safely usable options: axis_positions, tolerance, sample |

Returns the merged TTFont and attaches `result.subset_merger`.
With out_path and flavor=None, the extension selects .woff→woff, .woff2→woff2, or desktop sfnt otherwise.
Explicit flavor overrides extension inference. Without out_path, this function does not apply output_flavor.
Save, compression and verification errors propagate. Empty wrapper input may raise IndexError while its progress arguments are evaluated.

verify_kwargs is used only when verify=True. Unknown keywords are rejected by verify_merge.
Do not pass sources, merged or glyph_map: the wrapper already supplies them.
verbose belongs to the wrapper and is not forwarded; built-in verification still uses its own verbose=True.
Call verify_merge separately for quiet verification or a custom mapping.

**Current built-in verification limits:** the first font is already modified before checking, so it is not an untouched main reference.
The wrapper converts paths to objects. When verify_merge loads those objects again, it creates labels such as subset000.
The merger's glyph_map retains path basenames, which may not match those labels.
Thus verify=True is not an independent complete source comparison. The examples retain original paths or copies for separate verification.
Source: [merge_subsets](../../core/subset_merge.py#L723).

## 5. verify_merge

`verify_merge(sources, merged, glyph_map=None, axis_positions="auto", tolerance=0.0, sample=None, verbose=True)` is a package-root export.

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `sources` | iterable[path / TTFont] | required | Original subsets, preferably untouched copies or original paths | Loaded through load_subsets; objects are not deep-copied there |
| `merged` | TTFont | required | Result to check; a path is not accepted here | Read-only apart from table loading |
| `glyph_map` | dict / None | `None` | `{label: {source_name: result_name_or_GID}}` | Labels must match this call's load_subsets labels |
| `axis_positions` | str / iterable | `"auto"` | "auto", "grid", or a list of None/user-coordinate dicts | Use [None] for no instantiation; bare None raises TypeError |
| `tolerance` | number | `0.0` | Absolute numeric outline-coordinate tolerance in font units | hmtx/vmtx still use exact tuple equality |
| `sample` | int / None | `None` | At most this many source names per subset before .notdef is skipped | Deterministic stride; None/0 means no cap |
| `verbose` | bool | `True` | Print verification progress and failures | Independent of merge_subsets.verbose |

"auto" uses the default plus non-default minimum/maximum of the first axis, not every axis endpoint.
"grid" uses min/default/max across axes, capped at 64 positions by default.
Custom dictionaries use user coordinates. Omitted axes stay at default; axes absent from a source are projected away by the instancing helper.

Returns `{"ok": bool, "failures": list[str], "checks": dict}`. There is currently no top-level stats field.
Checks cover codepoints, axes, positions, sampled outlines/metrics, features, layout references, GDEF, variation maps, container metadata and vertical-reference counts.
An outline mismatch skips that glyph's subsequent metric comparison.
Ordinary check failures enter failures rather than raising AssertionError; loading and instancing errors can still raise.
Source: [verify_merge](../../core/verify.py#L112).

## 6. verify_composition

This function is not a package-root export: `from FontMerger.core.verify import verify_composition`.
`verify_composition(merged, main_font, base_font, added_glyphs, sample=30, tolerance=1.0, max_positions=6, verbose=False, adv_tolerance=None)`.

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `merged` | TTFont | required | Composed result in the intended design space | Reads glyph sets |
| `main_font` | TTFont | required | Main reference with matching glyph names and units | Not modified in place |
| `base_font` | TTFont | required | Fallback reference with matching glyph names and units | Not modified in place |
| `added_glyphs` | sequence[str] | required | Names introduced from fallback; must support len and slicing | Sampled locally; missing source names are skipped |
| `sample` | int / None | `30` | Cap for added names and main names separately | Deterministic stride; None/0 disables the cap |
| `tolerance` | number | `1.0` | Absolute numeric outline-coordinate tolerance, font units | Not an advance-width tolerance when overridden separately |
| `max_positions` | int | `6` | Cap on min/default/max Cartesian grid positions | Truncates enumeration; not all positions are guaranteed |
| `verbose` | bool | `False` | Print success summary | Assertions still raise when false |
| `adv_tolerance` | number / None | `None` | Fallback-added glyph advance-width tolerance, font units | None uses tolerance; main widths are not separately checked here |

Uses `getGlyphSet(location=...)` to read outlines and widths under rendering semantics.
Added glyph outlines and advance widths are compared with fallback; main glyphs are checked for outlines only.
Failure raises AssertionError. Success returns `{"positions": n, "checked": n, "worst": value}`.
checked counts actual comparisons across positions. worst records only maximum numeric outline deviation, not width error.
This does not replace layout-integrity, feature-behavior, vertical-metric or rasterizer checks.

The main workflow defaults verify_compose to True, unlike merge_subsets verify=False.
[FontMerger's call site](../../core/merger.py#L426) uses max_positions=4 and adv_tolerance=3.0; other defaults remain as shown here.
A composition assertion triggers the non-composition retry after propagation. It does not return a "verified composition" result.
Source: [verify_composition](../../core/verify.py#L408).

## 7. grid_positions

Module import: `from FontMerger.core.verify import grid_positions`.
`grid_positions(font, per_axis=3, max_positions=64)`.

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `font` | TTFont | required | Font whose fvar axis order defines the grid | Read-only; static input returns [None] |
| `per_axis` | int | `3` | Retained parameter; currently not read by the implementation | Changing it does not change sampling density |
| `max_positions` | int | `64` | Requested upper count for Cartesian enumeration; use a positive value | Truncates after appending a position; not a validation parameter |

Returns a list of positions. Variable input uses fvar axis order and each axis's deduplicated, sorted min/default/max values in a Cartesian product.
Enumeration stops at the cap. A truncated grid need not include the default or both ends of every axis.
per_axis currently has no effect. Supply custom verify_merge positions when intermediate samples are needed.
Source: [grid_positions](../../core/verify.py#L78).

<a id="verification-limits"></a>
## 8. Verification limits

- **Labels and GIDs:** verify_merge regenerates load_subsets labels before looking up glyph_map. Path and object labels differ; custom labels need alignment. Without a map it compares matching names, not implicit subset numbers.
- **Skipped targets:** missing names or out-of-range GIDs can be skipped rather than failed. Inspect checks["glyphs"]["compared"] for actual coverage. Supply valid nonnegative GIDs.
- **Untouched sources:** in-place modification of the first subset weakens the comparison. Retain paths or pre-merge deep copies for independent evidence.
- **Raw drawing records:** the current raw RecordingPen does not promise recursive component decomposition. The comparator checks operations, numeric values and argument shapes, but not nonnumeric component names. It cannot establish arbitrary composite-glyph geometry equality.
- **Layout:** feature tags, references and ordering are not shaping comparisons. Some GDEF fields are summaries, not proof that every source record was retained.
- **Sampling:** position grids can be truncated and glyphs can be sampled. Neither covers the continuous design space. Floating evaluation, integer metrics and saved quantization also differ.
- **Files:** verify_merge receives an in-memory font and does not read an output file's magic. save_font handles saved-container checks. Records such as name17 can appear in the report without all becoming failure criteria.

These limits follow from the [RecordingPen comparator](../../core/verify.py#L26) and [verify_merge target selection](../../core/verify.py#L179).
The repository's tests/ and build/ directories are not included in the public ZIP. This page does not require them to use the library API.

## 9. Examples

The two filenames represent subsets of the same variable font, not arbitrary fonts.
This example reopens the original paths, aligning labels with the map and avoiding the modified-first-subset reference.
These are usage examples; this documentation review does not run real fonts.

~~~python
from FontMerger import merge_subsets, verify_merge, save_font

paths = ["Main.ttf", "Base.ttf"]
merged = merge_subsets(paths, tag="part", verify=False, verbose=False)
report = verify_merge(
    paths, merged,
    glyph_map=merged.subset_merger.glyph_map(),
    axis_positions="grid", tolerance=0.0, sample=None, verbose=False,
)
if not report["ok"]:
    raise AssertionError(report["failures"])
save_font(merged, "Merged.ttf")
~~~

Lower-level object use needs explicit metadata completion and alignment from custom labels to verification object labels:

~~~python
import copy
from FontMerger import (
    SameSourceSubsetMerger, load_subsets, verify_merge,
    complete_vf_name_table, fix_head_flags,
)

fonts, labels = load_subsets(["Main.ttf", "Base.ttf"])
originals = copy.deepcopy(fonts)
state = SameSourceSubsetMerger(tag="part", verbose=False)
merged = state.merge(fonts, labels=labels)
complete_vf_name_table(merged)
fix_head_flags(merged)

_, verification_labels = load_subsets(originals)
by_source_label = state.glyph_map()
aligned_map = {
    verify_label: by_source_label[source_label]
    for source_label, verify_label in zip(labels, verification_labels)
}
report = verify_merge(
    originals, merged, glyph_map=aligned_map, verbose=False,
)
if not report["ok"]:
    raise AssertionError(report["failures"])
~~~
