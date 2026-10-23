# Helper API reference

**English** | [简体中文](../zh-CN/helper-api.md)

This page documents the root package exports other than the merging entry points. It describes v0.2.1; defaults, return values and side effects below are taken from the current source files, not from older README text.

Coverage and division:

- [Merging API](merge-api.md) documents `load_font`, `merge_fonts`, `FontMerger` and `DEFAULT_ANSWERS`.
- [Axis mapping and variation composition](variation-model.md) documents `AxisMapping`, `PiecewiseLinear`, `axis_mappings`, `evaluate_supports`, `refine_support_rebased`, `source_location`, `fvar_triples` and `avar_segments`.
- [Same-source subsets and verification](subsets-and-verification.md) documents `SameSourceSubsetMerger`, `load_subsets`, `merge_subsets` and `verify_merge`.
- This page documents every remaining root export: conflict planning, glyph copying and renaming, naming, format conversion, sub-setting, transforms, axis union, table and layout helpers, name/head completion, detection helpers, save guards and package constants.

Runtime source files are linked with relative paths such as [core/merger.py](../../core/merger.py); these links resolve both in the repository and in the runtime ZIP. The runtime ZIP contains the root modules, core/, format/, tables/, utils/, both READMEs, CHANGELOG.md, LICENSE and doc/*.md. It excludes tests/ and build/; those trees are repository-only and are referred to here as code paths, not as relative links. Private engineering notes are not part of the public documentation.

Entry format: signature, parameters (type, default, unit or meaning), returns, mutates, raises. Inputs are borrowed unless a row says a copy is returned.

## 1. Conflict planning

Repository source: [core/conflict.py](../../core/conflict.py).

### `resolve_conflicts(main_font, base_font)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | required | Main font, read only. |
| `base_font` | `TTFont` | required | Base font, read only. |

Returns: `set[str]` of base glyph names that should not be copied. The retention rules apply only to a base glyph whose name is absent from the main font, or to a glyph that has first been given a distinct name. Under that precondition, the glyph is kept when it has a Unicode code point not present in the main font, when it is required by a non-conflicting UVS sequence, when it has no Unicode cmap entry at all, or when it is a component of another kept base glyph. A manual name that still collides with a main name is reported for removal regardless of its code points; automatic and exempt names are handled separately, and `.notdef` is never reported. The function decides glyph-level conflicts only; it does not alias names and does not edit either font.

Mutates: none. Raises: none declared; absent `cmap` or `glyf` tables are handled by the implementation.

Disambiguate before calling this function. Automatic names (`glyphNNNNN`) can use `plan_alias`; manual same-name glyphs must be renamed explicitly with `rename_glyphs` or `renamed_copy`. A normal merge uses `FontMerger.merge_two`, which applies its internal wider planner. Without disambiguation, a manual same-name glyph is reported for removal even when it has a unique code point.

### `plan_alias(main_font, base_font, tag='b', index=1)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | required | Main font, read only. |
| `base_font` | `TTFont` | required | Base font, read only. |
| `tag` | `str` | `'b'` | Alias prefix inserted in `{tag}{index:03d}.{name}`. |
| `index` | `int` | `1` | Ordinal used in the alias template. |

Returns: `dict[str, str]` mapping old base glyph name to alias for colliding names that look like fontTools sequence names (`glyphNNNNN`). Plain manual names are not included; the merger uses an internal wider planner for its own conflict pass. This keeps the historical public contract of `plan_alias`. Manual collisions need an explicit `rename_glyphs` or `renamed_copy`, or a `FontMerger.merge_two` run; public `plan_alias` alone does not make them safe.

Mutates: none. Raises: none.

## 2. Glyph renaming

Repository source: [core/glyph_rename.py](../../core/glyph_rename.py).

### `alias_name(name, taken, tag='b', index=1)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | `str` | required | Original glyph name. |
| `taken` | container of `str` | required | Names that must not be reused; only membership is tested. |
| `tag` | `str` | `'b'` | Prefix. |
| `index` | `int` | `1` | Ordinal; the format is `{tag}{index:03d}.{name}`, with `_n` appended while the candidate is taken. |

Returns: a new `str`. Mutates: none. Raises: none.

### `rename_glyphs(font, mapping)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `font` | `TTFont` | required | Font modified in place. |
| `mapping` | `dict[str, str]` | required | Old name to new name. Entries whose value equals the key are ignored. |

Returns: the same `font`. Mutates `font` in place: glyph order, `glyf` glyphs and composite components, CFF/CFF2 charstrings, charset and FDSelect mappings, `hmtx`/`vmtx` metrics, all cmap subtables including format 14 entries, VORG records, HVAR/VVAR DeltaSetIndexMaps, and the GSUB/GPOS/GDEF references. A lazy `gvar` is decompiled before glyph order changes.

Raises: `ValueError` if the mapping would produce duplicate glyph names.

### `renamed_copy(font, mapping)`

Parameters: `font` (`TTFont`, read only); `mapping` (`dict[str, str]`). Returns: a deep copy with `rename_glyphs` applied. Mutates: none. Raises: the same `ValueError` as `rename_glyphs`. An empty mapping still returns a deep copy.

## 3. Naming

Repository source: [core/naming.py](../../core/naming.py) and [utils/detect.py](../../utils/detect.py).

### `apply_naming(output_font, main_family, all_copyrights)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `output_font` | `TTFont` | required | Font modified in place. |
| `main_family` | `str` | required | Preferred family name. A value returned by `get_family` carries per-language name records as a `str` subclass; a plain `str` is accepted too. |
| `all_copyrights` | `list[str]` | required | Copyright strings. Values returned by `get_copyrights` are `str` subclasses carrying language records; plain strings are treated as unlocalized additional text. |

Returns: the same `output_font`. Mutates the `name` table in place: the family name gains one `" mod"` suffix (not repeated), per-language identity records (1, 2, 3, 4, 6, 16, 17) are derived from the existing records, copyright records (0) keep every language and merge without adding translations, and a deterministic PostScript name is derived from the family and style with a hash suffix. CFF1 `fontNames`, `FamilyName` and `FullName` are synchronized with the PostScript/family identity. Version, PANOSE, vendor, trademark and other records are not rewritten; CFF2 axis and instance naming is not rebuilt.

Raises: `ValueError` when a rewritten field cannot be encoded and no equivalent Unicode language can be determined; fontTools record errors can propagate.

### `get_family(font)`

Parameters: `font` (`TTFont`, read only). Returns: preferred family name as `str`. The implementation prefers an English record, then nameID 16 over nameID 1 within the same language, with a deterministic platform and language tie-break. When found, the returned object is a `str` subclass carrying all decodable family records (private `_name_records`); it behaves as a plain `str` for comparisons, slicing and formatting. Returns the plain string `'Font'` when no decodable record exists.

Mutates: none. Raises: none; undecodable records are skipped with a warning.

### `get_copyrights(*fonts)`

Parameters: any number of `TTFont` objects, read only. Returns: `list[str]` with one element for each font that has a decodable nameID 0 record, in input order. A font without such a record contributes no element, so the list can be shorter than the argument list. Each element is a `str` subclass carrying all language records for that copyright (private `_name_records`).

Mutates: none. Raises: none; decoding failures are warned and skipped.

## 4. Glyph injection

Repository source: [core/glyph_copy.py](../../core/glyph_copy.py).

### `merge_glyphs_via_ttx(main_font, base_font, glyphs_to_add, use_ttx=None)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | required | Source of all non-copied structure. Not modified in content. |
| `base_font` | `TTFont` | required | Source of copied glyphs, metrics, cmap entries and variation data. Treated as read only; lazy decompilation can occur. |
| `glyphs_to_add` | iterable of `str` | required | Glyph names requested for copying. Component and dependency closure is added internally. |
| `use_ttx` | `bool` or `None` | `None` | `None` selects TTX when either font uses CFF/CFF2, and object copying when both use `glyf`. `True` forces the TTX path; `False` forces object copying when both fonts have `glyf`. |

Returns: a new `TTFont`. The base layout tables are stripped from the working copy; layout features are expected to be merged separately by `merge_ot_features`. Cmap entries for copied glyphs are added, and an in-memory source map is attached to the result for chunked same-source copying. The map is not serialized.

Mutates: the input fonts are not edited in content. The function writes temporary TTX files and removes them before returning. Raises: `ValueError` for a missing base component or an uncompilable injected glyph; subprocess/TTX errors propagate; no partial font is returned.

## 5. Outline conversion and static extraction

Repository source: [format/converter.py](../../format/converter.py) and [format/static_extract.py](../../format/static_extract.py).

### `glyf_to_cff(font)`

Parameters: `font` (`TTFont`, read only). Returns: a new CFF-based `TTFont` with `sfntVersion='OTTO'`. The input is not modified; the conversion works on a deep copy. Already-CFF input returns an unmodified deep copy.

Behavior and side effects on the returned font: TrueType hinting is removed, each glyph is converted to a Type 2 charstring with a cubic approximation, common non-outline tables are deep-copied, and Windows/Office compatibility fixes are applied (CFF `Weight`, RIBBI nameID 2, nameID 16/17, underline defaults, OS/2 v3 fields, checksum reset). Tables in the removal list (DSIG, PCLT, LTSH, hdmx, VDMX, meta, trak) are dropped.

Raises: `ValueError` when the font still has variable-font tables (`fvar`, `gvar`, `HVAR`, `VVAR`, `MVAR` or `cvar`), or when any glyph cannot be converted.

### `cff_to_glyf(font)`

Parameters: `font` (`TTFont`, read only). Returns: a new glyf-based `TTFont`. Already-glyf input returns an unmodified deep copy.

Behavior and side effects on the returned font: hinting is removed, cubic curves are approximated with `Cu2QuPen(max_err=1.0)`, glyph bounds are recalculated, `loca` and a TrueType `maxp` 1.0 are built, `post` 2.0 glyph names are preserved, `hhea.numberOfHMetrics` is fixed, and `cvt `/`fpgm`/`prep`/`gasp`/`VORG`/`DSIG` are removed. Explicit VORG origins are folded into `vmtx` top side bearings before VORG removal.

Raises: `ValueError` for variable font input or a glyph conversion failure; no empty glyphs are fabricated.

### `convert_font_format(font, to_cff)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `font` | `TTFont` | required | Input font, read only. |
| `to_cff` | `bool` | required | `True` for CFF output, `False` for glyf output. |

Returns: a new `TTFont`. If the input already has the requested outline technology, a deep copy is returned unchanged. Otherwise the call delegates to `glyf_to_cff` or `cff_to_glyf`. Mutates: none. Raises: the delegated `ValueError` cases.

### `variable_to_static(font, remove_overlaps=False)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `font` | `TTFont` | required | Input font, read only. |
| `remove_overlaps` | `bool` | `False` | Also run fontTools boolean overlap removal, which rewrites contours. Kept off by default for fidelity comparisons. |

Returns: a new `TTFont`. A non-variable input returns a deep copy. A variable input is instantiated at each axis default value. CFF2 output is converted to CFF, then saved and reloaded once to normalize table views. When instantiation raises, the function logs `[警告] 实例化失败` and returns a deep copy of the original font, which can still be variable. Overlap removal failures are warned and skipped.

Mutates: none. Raises: none from the instantiation failure path; other fontTools errors are not converted.

## 6. Scale and baseline offset

Repository source: [format/transform.py](../../format/transform.py).

### `scale_font(font, scale, baseline_offset)`

| Parameter | Type | Default | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `font` | `TTFont` | required | n/a | Font modified in place and returned. |
| `scale` | `float` | required | multiplier | `1.0` is identity, `1.1` is 110%. Must be finite and greater than zero. |
| `baseline_offset` | `float` | required | font design units | Vertical offset, positive upward. Must be finite. |

Returns: the same `font`. `scale == 1.0` with offset `0` returns immediately. For any other pair the function removes hinting and stale pixel caches (cvt/cvar/fpgm/prep/gasp/hdmx/LTSH/VDMX/DSIG), applies the affine transform, updates vertical origins, `VORG`, `hmtx`/`vmtx`, head bounds and vertical metrics, and leaves `head.unitsPerEm` unchanged.

Raises: `ValueError` for non-finite or non-positive scale, non-finite offset, an unrecognized outline format, or a font with a `VARC` table.

### `apply_scale_offset(font, scale_percent, baseline_offset)`

| Parameter | Type | Default | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `font` | `TTFont` | required | n/a | Font modified in place and returned. |
| `scale_percent` | `float` | required | percent | `100.0` is identity; converted to a multiplier by dividing by 100. |
| `baseline_offset` | `float` | required | font design units | Positive upward. |

Returns: the same `font`, by calling `scale_font(font, scale_percent / 100.0, baseline_offset)`. Mutates and raises as `scale_font`.

## 7. Subsetting and webfont input

Repository source: [format/subsetter.py](../../format/subsetter.py) and [format/webfont.py](../../format/webfont.py).

### `create_glyph_subset(font, glyph_names, strip_layout=True)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `font` | `TTFont` | required | Source font, not modified. |
| `glyph_names` | iterable of `str` | required | Requested glyph names. `.notdef` is always kept. Missing names are warned and ignored, matching the historical interface. |
| `strip_layout` | `bool` | `True` | Remove GSUB, GPOS, GDEF, BASE, VORG and JSTF before subsetting. `False` keeps layout tables so the Subsetter can include layout output glyphs in the closure. |

Returns: a new `TTFont` synchronized by fontTools `Subsetter`. Component, layout output and metric closure are handled by the Subsetter. Tables in the Subsetter default drop list, for example DSIG, JSTF, LTSH and legacy bitmap or Graphite tables, are removed with a `[子集警告]` line; other structural failures propagate.

Mutates: none on the input. Raises: `Subsetter` or fontTools errors that are not the warned missing-name case.

### `unwrap_webfont(path)`

Parameters: `path` (`str` or path-like). Returns: a new `TTFont` with `flavor = None`, loaded from a WOFF/WOFF2 file. Mutates: none. Raises: fontTools load errors.

## 8. Axis union and variable merge utilities

Repository sources: [core/merger.py](../../core/merger.py) and [format/vf_axes.py](../../format/vf_axes.py). The composition math itself is documented in [axis mapping and variation composition](variation-model.md).

### `axes_compatible(main_font, base_font)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | required | Main font, read only. |
| `base_font` | `TTFont` | required | Base font, read only. |

Returns: `bool`. `True` only when both fonts are variable, both use `glyf` outlines, their fvar axis lists match exactly in order, tag and min/default/max values, and their avar segment maps match. This is the precondition for the one-to-one gvar delta transfer used by `transfer_glyph_variations`.

Mutates: none. Raises: none declared.

### `transfer_glyph_variations(result, base_var, glyph_names)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `result` | `TTFont` | required | Merged font, modified in place. |
| `base_var` | `TTFont` | required | Variable base font, read only. |
| `glyph_names` | iterable of `str` | required | Glyphs whose gvar variations are copied. |

Returns: `int`, the number of glyphs for which variations were copied. A glyph is skipped when it has no base variation or when any tuple has a different axis count than the result fvar. The result gvar entries are deep-copied. When at least one glyph is copied, HVAR is rebuilt with fontTools `varLib.hvar.add_HVAR` from phantom points; an HVAR rebuild failure is logged with `[增量]` and does not raise.

Mutates: `result` in place (gvar entries and possibly HVAR). Raises: none declared; the HVAR rebuild error is caught.

### `union_axes(main_font, base_font)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | required | Modified in place; must contain `fvar` for any change. |
| `base_font` | `TTFont` | required | Read only; its axis ranges and base-only axes are merged into the main font. |

Returns: `list[tuple[str, float, float, float]]` of added axes as `(axisTag, min, default, max)`; empty when either font is not variable. Mutates the main font: shared axis ranges are widened while the main default is kept, base-only axes are appended, STAT axis records, fvar instance coordinates, avar identity segments and ItemVariationStore region lists are synchronized. VarStore extension failures are logged; they are not raised.

Raises: none declared beyond fontTools table errors that are not caught.

### `axis_union_merge(main_font, base_font)`

Both parameters are `TTFont`: `main_font` is modified in place and must contain `fvar`; `base_font` is read only. Returns and raises are identical to `union_axes`; this is the public wrapper for the same operation.

## 9. Table-level merge entry points

Repository source: [tables/base.py](../../tables/base.py) and [tables/ot_merge.py](../../tables/ot_merge.py).

### `merge_all_tables(merged_font, main_font, base_fonts, added_glyphs=None)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `merged_font` | `TTFont` | required | Result font, modified by registered handlers. |
| `main_font` | `TTFont` | required | Main font, read only. |
| `base_fonts` | iterable of `TTFont` | required | Base fonts, read only. |
| `added_glyphs` | iterable of `str` or `None` | `None` | Optional set of added glyph names passed to each handler. |

Returns: `None`. The function iterates the sorted union of table tags from the result and the base fonts, skipping `GlyphOrder`, and calls each tag registered with `register(tag)`. Handler exceptions are caught per table and reported with `[表合并警告]` plus a traceback.

Important boundary: this entry is not called by `merge_two`. It replays registered `fvar` and OpenType handlers and is not a merge finalizer. The merger uses `merge_ot_features`, its table-policy step, and its metadata recalculator instead. Current registered tags: `GDEF`, `GPOS`, `GSUB`, `OS/2`, `avar`, `cmap`, `fvar`, `head`, `hhea`, `hmtx`, `kern`, `maxp`, `name`, `post`, `vhea`, `vmtx`.

### `prune_base_layout(base_font, kept_glyphs)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `base_font` | `TTFont` | required | Read only; a deep copy is pruned. |
| `kept_glyphs` | iterable of `str` | required | Base glyphs that survived the merge; `.notdef` is added automatically. |

Returns: a new `TTFont` containing only GSUB/GPOS/GDEF, pruned with the fontTools Subsetter closure, or `None` when the Subsetter fails (a `[OT修剪]` warning is printed). The result carries the pruned glyph order for later reference checks.

Mutates: none. Raises: none from the pruning failure path.

### `merge_ot_features(main_font, base_font, kept_glyphs)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `main_font` | `TTFont` | required | Merged in place; its layout is the priority source. |
| `base_font` | `TTFont` | required | Read only. |
| `kept_glyphs` | iterable of `str` | required | Base glyphs copied into the result. |

Returns: the same `main_font`. The function prunes base layout to `kept_glyphs`, merges surviving lookups and features with main priority, remaps indices and glyph names, and synchronizes GDEF classes, VariationIndex offsets and mark-set indices. When pruning fails it logs `[OT合并] 打底布局修剪失败` and leaves the main layout unchanged.

Raises: `ValueError` for incompatible FeatureVariations conditions or dangling layout references in the base table; fontTools errors can propagate.

## 10. Layout object helpers

Repository source: [tables/layout_union.py](../../tables/layout_union.py) and [tables/varstore.py](../../tables/varstore.py). These helpers operate on fontTools otTables objects and do not validate a whole font on their own.

### `layout_glyph_names(font)`

Parameters: `font` (`TTFont`, read only). Returns: `set[str]` of glyph names referenced by GSUB, GPOS or GDEF. Mutates: none. Raises: none declared.

### `remap_glyph_names(obj, ren, seen=None)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `obj` | otTables object, `dict` or `list` | required | Object tree modified in place. |
| `ren` | `dict[str, str]` | required | Old to new name map; unmatched strings are left unchanged. |
| `seen` | `set` or `None` | `None` | Internal recursion guard; callers leave it unset. |

Returns: `None`. Mutates the object tree. Raises: none declared.

### `offset_var_devices(obj, delta, seen=None)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `obj` | otTables object, `dict` or `list` | required | Object tree modified in place. |
| `delta` | `int` | required | Value added to each VariationIndex outer index. |
| `seen` | `set` or `None` | `None` | Internal recursion guard. |

Returns: `None`. Only devices with `DeltaFormat == 0x8000` are changed; the `NO_VARIATION_INDEX` sentinel is skipped. Raises: none declared.

### `remap_feature_variations(fv, index_map)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `fv` | FeatureVariations object or `None` | required | Modified in place; `None` returns immediately. |
| `index_map` | `dict[int, int]` | required | Old FeatureIndex to new FeatureIndex. |

Returns: `bool`. `True` means at least one substitution record referenced a FeatureIndex absent from the map; the variant is stale and the caller should reject or drop it. `False` means every index was rewritten. Mutates `fv` in place. Raises: none declared.

### `resort_layout(font)`

Parameters: `font` (`TTFont`, modified in place). Returns: the same `font`. Sorts Coverage arrays and their parallel arrays by the current glyph order, including PairValueRecord order and GDEF MarkGlyphSets, AttachList and LigCaretList coverage. Raises: none declared.

### `LayoutUnion(tag)`

| Member | Parameters | Returns | Mutates | Raises |
| --- | --- | --- | --- | --- |
| `__init__(tag)` | `tag`: `str`, required, `'GSUB'` or `'GPOS'` | a collector object | creates empty state | `ValueError` for any other tag |
| `add_from(base_table, ren, var_offset=0, mark_set_remap=())` | `base_table`: otTables GSUB/GPOS; `ren`: `dict[str,str]`; `var_offset`: `int` default `0`; `mark_set_remap`: sequence of `int` default `()` | `None` | collector state only; the input table is deep-copied | `ValueError` for inconsistent FeatureVariations conditions or invalid internal references |
| `finalize()` | none | a new otTables GSUB/GPOS table, or `None` when no feature was added | none | none declared |

`add_from` parameter semantics:

- `base_table`: the source otTables GSUB or GPOS table. It is deep-copied; the caller's table is not modified.
- `ren`: glyph-name map (old name to new name) applied to the copied lookups and to FeatureVariations lookups. Unlisted names stay unchanged.
- `var_offset`: base offset of this source's GDEF VarData in the union. It is added to every VariationIndex outer index in the copied lookups; `NO_VARIATION_INDEX` stays untouched. Use `0` when the source contributes no GDEF VarData.
- `mark_set_remap`: local MarkGlyphSetsDef index of this source to union index. It is applied only to lookups whose LookupFlag has bit 4 set; an empty sequence disables the remap.

`add_from` also remaps feature indices, scripts and language systems. `finalize` coalesces features by language system and returns a table; it does not install the table into a font.

### `MarkGlyphSetUnion()`

| Member | Parameters | Returns | Mutates | Raises |
| --- | --- | --- | --- | --- |
| `add(mark_glyph_sets, remap_name=None, alive=None, order_index=None)` | `mark_glyph_sets`: MarkGlyphSetsDef or `None`; `remap_name`: `dict[str,str]` or `None`; `alive`: `set[str]` or `None`; `order_index`: `dict[str,int]` or `None` | `list[int]` local set index to union set index | collector state | none declared |
| `build(order_index=None)` | `order_index` optional glyph-order map | `otTables.MarkGlyphSetsDef` or `None` for an empty union | none | none declared |

Identical sets are deduplicated. `add` returns `[]` for a `None` input. The object is truthy when it holds at least one set.

`add` parameter semantics:

- `mark_glyph_sets`: one MarkGlyphSetsDef to add. `None` returns `[]` without changing the collector.
- `remap_name`: glyph-name map (old name to new name) applied before filtering and sorting. `None` leaves names unchanged.
- `alive`: glyph survival set. `None` means no filtering; when a set is given, glyphs outside it are removed from each copied coverage after `remap_name` is applied.
- `order_index`: glyph name to GID map used for ordering. `None` sorts glyphs lexicographically; when provided, glyphs are sorted by GID and names missing from the map are placed at the end. The returned list has one union index per input coverage.

`build` parameter semantics: with `order_index=None`, each stored coverage is written in its current order; with a map, each coverage is sorted by GID and names missing from the map are placed at the end. `build` returns `None` for an empty union and does not modify the collector.

### `VarStoreUnion()`

| Member | Parameters | Returns | Mutates | Raises |
| --- | --- | --- | --- | --- |
| `add(var_store)` | `var_store`: otTables VarStore or `None` | `int` base offset of the added VarData, `0` for `None` | collector state; copied VarData entries | none declared |
| `build()` | none | `otTables.VarStore` or `None` | none | none declared |

Regions are deduplicated by their start/peak/end triples, VarData rows are appended, and their `VarRegionIndex` values are remapped. The object is truthy when it holds at least one VarData.

## 11. name and head completion

Repository source: [tables/name_table.py](../../tables/name_table.py) and [tables/head.py](../../tables/head.py).

### `complete_vf_name_table(font, platformID=3, platEncID=1, langID=0x409)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `font` | `TTFont` | required | Modified in place. |
| `platformID` | `int` | `3` | Platform ID for new records, Windows by default. |
| `platEncID` | `int` | `1` | Platform-specific encoding ID, Unicode BMP by default. |
| `langID` | `int` | `0x409` | Language ID, English (US) by default. |

Returns: the same `font`. Does nothing when `fvar` or `name` is absent. Adds nameID 16 (typographic family) and 17 (typographic subfamily) when missing, nameID 25 (variation PostScript name prefix) when missing, and a PostScript name record for each fvar instance whose `postscriptNameID` is `0xFFFF` or `None`. nameID 16 is skipped when nameID 1 is absent. Existing records are not removed. New records are written only for the `platformID`, `platEncID` and `langID` arguments; those records need not exist beforehand, so the call can add a record set for a platform or language the font did not have. Values are read with fontTools `getDebugName`, which may return a record from another platform or language; when nameID 2 or an instance subfamily name is missing the literal fallback `'Regular'` is used, and when no PostScript prefix or family is available the prefix falls back to `'Font'`. These fallbacks are not read from the font. This helper is not equivalent to `apply_naming`'s per-language handling: it completes one requested record set instead of deriving protected identities for each existing language.

Raises: fontTools name-table errors when required records cannot be read or written.

### `fix_head_flags(font)`

Parameters: `font` (`TTFont`, modified in place). Returns: the same `font`. Clears the WOFF2 residual bit 11 and sets bits 0 and 1 (baseline at y=0, left side bearing at x=0). Does nothing without a `head` table. Raises: none declared.

## 12. Detection helpers

Repository source: [utils/detect.py](../../utils/detect.py).

### `is_cff(font)`
Parameters: `font` (`TTFont`, read only). Returns: `bool`, `True` when a `CFF ` or `CFF2` table exists. Mutates: none. Raises: none.

### `is_ttf(font)`
Parameters: `font` (`TTFont`). Returns: `bool`, `True` when a `glyf` table exists. Mutates: none. Raises: none.

### `is_variable(font)`
Parameters: `font` (`TTFont`). Returns: `bool`, `True` when an `fvar` table exists. Mutates: none. Raises: none.

### `type_label(font)`
Parameters: `font` (`TTFont`). Returns: a Chinese status label, for example `'静态TTF'` or `'可变OTF'`; CFF/CFF2 is labeled OTF and `glyf` is labeled TTF. Mutates: none. Raises: none.

### `all_codepoints(font)`
Parameters: `font` (`TTFont`). Returns: `set[int]` of every code point found in any cmap subtable that exposes a `cmap` mapping. Both Unicode and non-Unicode subtables contribute. Mutates: none. Raises: none.

### `glyph_to_codepoints(font)`
Parameters: `font` (`TTFont`). Returns: `dict[str, set[int]]` mapping each glyph name to every code point found in any cmap subtable. Mutates: none. Raises: none.

### `axis_space(font)`
Parameters: `font` (`TTFont`). Returns: `dict[str, tuple[float, float, float]]` mapping axis tag to `(min, default, max)`; `{}` for a non-variable font. Mutates: none. Raises: none.

### `is_same_source(fonts)`
Parameters: `fonts` (iterable of `TTFont`). Returns: `bool`. The conditions are: at least two fonts, every font has `fvar`, all axis triples are identical, and all fonts share the same outline technology (all CFF or all glyf). This is a structural check for webfont slices, not proof of common origin. Mutates: none. Raises: none.

### `is_auto_glyph_name(name)`
Parameters: `name` (`str`). Returns: `bool`, `True` for the fontTools post-3.0 sequence form `glyphNNNNN`. Mutates: none. Raises: none.

### Module constants

- `AUTO_GLYPH_RE`: compiled regular expression `^glyph\d{5}$` used by `is_auto_glyph_name`.
- `EXEMPT_GLYPHS`: `{'.notdef', '.null', 'nonmarkingreturn'}`.

## 13. Save guard

Repository source: [utils/save.py](../../utils/save.py).

### `save_font(font, path, flavor=None, recalcTimestamp=None)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `font` | `TTFont` | required | Font to save; its `flavor` attribute is set to the argument. |
| `path` | `str` or `Path` | required | Output file path. The function passes it to `TTFont.save`; it does not create parent directories. |
| `flavor` | `None`, `'woff'` or `'woff2'` | `None` | Output container. `None` means desktop sfnt. The value is not inferred from the extension; a path ending in `.woff2` with `flavor=None` writes desktop sfnt bytes. |
| `recalcTimestamp` | `None` | `None` | Only `None` is valid. It calls `font.save(path)` with the current fontTools signature. Passing `True` or `False` forwards an unsupported keyword to `TTFont.save`, which raises `TypeError` before any file is written. |

Returns: `(path, magic)`. `path` is the argument as given; `magic` is the first four bytes read back from the written file. When `flavor is None`, a written file whose magic is not in `SFNT_MAGICS` raises `ValueError`. When a web flavor is requested, the container magic is returned without an sfnt assertion.

Raises: `ValueError` for an invalid desktop magic; `TypeError` for a non-`None` `recalcTimestamp`; fontTools save errors propagate.

The `recalcTimestamp` parameter remains in the signature for compatibility, but only `None` is currently usable. To control timestamp recalculation, set the `font.recalcTimestamp` attribute before calling `save_font` with the default `None`. fontTools stores this attribute on each `TTFont` instance and reads it during save. The module-level helper `FontMerger.utils.save.default_flavor_for(path)` maps `.woff2` to `'woff2'`, `.woff` to `'woff'` and every other extension to `None`. It is not re-exported from the package root, but callers can use it to implement extension-based inference explicitly.

### `assert_sfnt(path)`
Parameters: `path` (`str` or `Path`). Returns: the first four bytes of the file. Raises: `ValueError` when the magic is not one of `SFNT_MAGICS`, with a message that suggests passing a web flavor for WOFF/WOFF2.

### `SFNT_MAGICS`
A tuple of accepted sfnt magics: `b'\x00\x01\x00\x00'` (TrueType outlines), `b'OTTO'` (CFF outlines) and `b'true'` (Apple TrueType).

## 14. Package constants

- `SUPPORTED_EXTS`: `{'.ttf', '.otf', '.woff', '.woff2'}`. Used by the CLI to validate input extensions.
- `COLLECTION_EXTS`: `{'.ttc', '.otc'}`. Used by the CLI to reject collections.
- `DEFAULT_ANSWERS`: interactive defaults documented in [merging API](merge-api.md).

## 15. Side-effect summary

| Function or class | Returns a new font | Modifies an input font in place |
| --- | --- | --- |
| `rename_glyphs`, `apply_naming`, `scale_font`, `apply_scale_offset`, `union_axes`, `axis_union_merge`, `merge_ot_features`, `complete_vf_name_table`, `fix_head_flags` | no | yes |
| `merge_glyphs_via_ttx`, `glyf_to_cff`, `cff_to_glyf`, `convert_font_format`, `variable_to_static`, `create_glyph_subset`, `renamed_copy`, `unwrap_webfont` | yes | no |
| `save_font` | no | writes the file and sets `font.flavor` |
| `merge_all_tables` | no | yes (through handlers) |
| `prune_base_layout` | yes | no |
| `resolve_conflicts`, `plan_alias`, `alias_name`, `get_family`, `get_copyrights`, `is_cff`, `is_ttf`, `is_variable`, `type_label`, `all_codepoints`, `glyph_to_codepoints`, `axis_space`, `is_same_source`, `is_auto_glyph_name`, `layout_glyph_names` | no | no |

See [limitations](limitations.md) for behavior that these helpers intentionally do not guarantee.
