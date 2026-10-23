# Variation model

[简体中文](../zh-CN/variation-model.md) | [Parameter index](parameter-index.md)

This page describes cross-design-space composition and its mathematical API.
Same-source subset union follows a separate path; see [Subsets and verification](subsets-and-verification.md).
The equations describe the model, not a guarantee that a saved font matches every source at every position.

## 1. Coordinate spaces

| Space | Meaning | Units |
| --- | --- | --- |
| `user` | Axis values defined by fvar minimum, default and maximum | Axis-specific user units |
| `pre` | Two-piece linear normalization around the default | Normalized coordinates, normally within `[-1, 1]` |
| `norm` | Coordinates after the avar segment map | Normalized coordinates used by variation supports |

The forward path is `user → pre → norm`.
An `AxisMapping` connects merged and source post-avar spaces through user coordinates.
User coordinates outside the source range are clamped to its endpoints.
A one-sided axis has only half of the normalized domain.

Source: [AxisMapping and PiecewiseLinear](../../format/axis_mapping.py#L66).

## 2. Axis planning and policies

The default `compose_range="main+extra"` keeps the main range and default for shared axes.
It adds fallback-only axes, rather than taking a full range union.
`"union"` expands shared minima/maxima but keeps the main default.
`"main"` keeps only the main axes and ranges.

| Parameter | Type | Default | Meaning / units | Effects |
| --- | --- | --- | --- | --- |
| `compose_variations` | bool | `True` | Attempt cross-design-space composition on supported merge paths | False selects the existing non-composition path |
| `compose_range` | str | `"main+extra"` | `"main+extra"`, `"union"` or `"main"`; ranges use user units | Changes the output design space |
| `compose_fit` | str | `"exact"` | Split supports at mapping breakpoints, or use endpoint/peak-only `"affine"` mapping | Affine mode can miss intermediate behavior and fail verification |
| `avar_mode` | int | `0` | 0 uses source maps and prefers the main output map; 1 ignores the fallback map; 2 ignores all avar maps | Mode 1 keeps the main map; mode 2 removes output avar |
| `verify_compose` | bool | `True` | Check sampled glyphs at sampled positions | A composition-check failure triggers the existing fallback path |
| `compose_layout` | bool | `True` | Transfer supported fallback GDEF/GPOS variation data | False leaves fallback layout at the instantiated merged default |

These are [FontMerger constructor](../../core/merger.py#L559) options.
[plan_axis_space](../../format/variation_compose.py#L41) returns `(merged_fvar, merged_avar, base_mappings)` without editing inputs.
Do not confuse these policies with the older axis-union helper.

## 3. Supports, rebasing and phantom points

A support is `{axis_tag: (lower, peak, upper)}` in post-avar normalized coordinates.
OpenType ignores a support axis whose peak is zero or whose interval crosses zero.
Such an axis does not encode the intended varying tent.
Refinement omits ignored axes and retains zero as a subdivision node.
Generated varying tents must have nonzero peaks and must not cross zero.
Boundary-truncated tents may have `lower == peak` or `peak == upper`.

Different source and merged defaults require rebasing:

`f(T(x)) = C + Σ weight × supportScalar(x, support)`

`C` is the source contribution at the merged default.
The default master or a constant-region column must carry it exactly once.
The remaining terms vanish at that default.
[refine_support_rebased](../../format/axis_mapping.py#L466) combines per-axis refinement by inclusion-exclusion.

[instance_at_merged_default](../../format/variation_compose.py#L93) calls fontTools with `inplace=False` and `optimize=False`.
This includes the phantom-point contribution to metrics.
[reparametrize_gvar](../../format/variation_compose.py#L121) rewrites supports and rounds scaled deltas.
HVAR can be rebuilt from the resulting gvar phantom points.

Exact support decomposition is a mathematical target under supported monotone maps.
It does not remove integer rounding or saved-coordinate quantization.
A merged avar plateau can collapse a user interval to one normalized value.
If the source changes over that interval, one output value cannot reproduce its behavior.
The code reports `collapsing_flats()`; it does not recover the lost distinction.

## 4. ItemVariationStore references

| Field | Meaning |
| --- | --- |
| `outer` | Index of a VarData block |
| `inner` | Item row inside that block, not a region index |
| Column | Delta associated with one region support |

The engine sums row deltas multiplied by their region scalars.
[reparametrize_var_store](../../format/variation_compose.py#L347) changes regions and columns while retaining VarData order, ItemCount and row order.
References remain valid during that rewrite.
Store union later appends VarData blocks and shifts appended outer indices; inner rows stay unchanged.

Fallback layout static values are first folded to the merged default.
Its rewritten store then omits that contribution to avoid counting it twice.
Other rewrites can retain the constant in a region whose axes all have peak zero.
Integer column deltas are rounded, so splitting columns can introduce residual error.
No universal one-font-unit error bound is asserted here.

Sources: [fold_layout_default and transfer_base_layout](../../format/variation_compose.py#L223), [VarStoreUnion](../../tables/varstore.py).

## 5. CFF2 and metric boundaries

CFF2 `blend` combines default operands with region deltas.
Its final count operand is the number of blended values.
The current `vsindex` selects the VarData block and region-delta count.
An implicit selection comes from the Private DICT, or zero.

[reparametrize_cff2](../../format/cff2_compose.py#L206) rewrites blend defaults and columns while keeping VarData indices.
It also processes subroutines and supported Private DICT blend values.
After store union, [offset_cff2_vsindex](../../format/cff2_compose.py#L388) shifts the fallback selection and adds explicit selections when needed.
For a nonzero offset, it folds Private hint blends to default values and removes the Private `vsindex` key.
Those hint variations are not preserved.

The cross-design-space CFF2 path transfers supported HVAR advance-width variation after glyph injection.
[merge_cff2_hvar](../../format/cff2_compose.py#L347) requires an existing result HVAR and a fallback store.
It rebuilds advance mappings for all glyphs; absent variation uses `NO_VARIATION_INDEX`.
This path does not provide equivalent fallback VVAR transfer.
Vertical fallback data may remain at the instantiated default.
Same-source subset union has a separate HVAR/VVAR union path.

Composition is not a general conversion between glyf/gvar and CFF2 variation topology.
On failure, [FontMerger._do_merge](../../core/merger.py#L624) reports the reason and retries its non-composition path.
A layout-transfer failure can instead retain default-instance layout without abandoning the whole merge.
See [verification limits](subsets-and-verification.md#verification-limits) before interpreting a passing report.

## 6. AxisMapping API

Import: `from FontMerger import AxisMapping`.
Constructor: `AxisMapping(merged_triple, merged_avar, source_triple, source_avar)`.

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `merged_triple` | sequence[3] | required | Merged minimum/default/maximum, user units | Copied to tuple |
| `merged_avar` | mapping / None | required | Merged pre→norm segments; falsey means identity | Copied to dict |
| `source_triple` | sequence[3] | required | Source minimum/default/maximum, user units | Copied to tuple |
| `source_avar` | mapping / None | required | Source pre→norm segments; falsey means identity | Copied to dict |

Use valid monotone axis maps; the constructor is not a font validator. The following methods are read-only and do not edit fonts.

| Method | Parameter | Type / default | Meaning / return |
| --- | --- | --- | --- |
| `to_source(x)` | `x` | number, required | Merged norm → source norm; clamps in source user space; plateau inverse uses the right endpoint |
| `to_merged(y)` | `y` | number, required | Source norm → merged norm; clamps in merged user space |
| `kinks_merged()` | none | no arguments | New sorted list of candidate merged-normalized breakpoints |
| `collapsing_flats()` | none | no arguments | New list of `(norm, user_lo, user_hi)` merged plateaus |
| `is_identity()` | none | no arguments | bool using exact triple/dictionary equality, not approximate functional equality |
| `__repr__()` | none | no arguments | Diagnostic str showing the merged and source triples |

Explicit identity segments and an absent map can compare differently in `is_identity()`.
Source: [AxisMapping](../../format/axis_mapping.py#L171).

## 7. PiecewiseLinear API

Import: `from FontMerger import PiecewiseLinear`.
Constructor: `PiecewiseLinear(points)`.
`identity`, `fvar` and `avar` are classmethods. Other listed methods operate on an instance.

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `points` | iterable[(number, number)] | required | Nodes of a monotone nondecreasing map; units depend on the map | Sorted into new xs/ys lists; caller validates points |

| Method | Parameter | Type / default | Meaning / return |
| --- | --- | --- | --- |
| `identity()` | none | classmethod; no arguments | New identity map with nodes -1, 0, 1 |
| `fvar(triple)` | `triple` | sequence[3], required | New normalized→user map; one-sided axes use half the domain |
| `avar(segments)` | `segments` | mapping / None, required | New pre→norm map; falsey input gives identity |
| `map(x)` | `x` | number, required | Evaluate in input units; outside nodes use translation extrapolation, not clamping |
| `inverse()` | none | no arguments | New inverse map; plateau values select the right endpoint |
| `compose(other)` | `other` | PiecewiseLinear, required | New map for `self(other(x))`; inputs unchanged |
| `breakpoints(lo=-1.0, hi=1.0)` | `lo` | number, -1.0 | Lower input bound; returns interior nodes only |
| `breakpoints(lo=-1.0, hi=1.0)` | `hi` | number, 1.0 | Upper input bound; endpoints excluded using EPS = `1e-9` |
| `is_identity()` | none | no arguments | bool requiring exactly the canonical three x nodes and y values matching within EPS |
| `__repr__()` | none | no arguments | Diagnostic str listing point pairs |

The inverse is not unique on a plateau. Extra collinear nodes can make `is_identity()` False.
Source: [PiecewiseLinear](../../format/axis_mapping.py#L66).

## 8. Exported mathematical functions

All functions below are package-root exports. Inputs are read-only and results are newly created. Reading a font can trigger lazy table loading.

### 8.1 axis_mappings

`axis_mappings(merged_axes, merged_avar, source_axes, source_avar)`

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `merged_axes` | dict | required | `{tag: (min, default, max)}` in user units | Read-only |
| `merged_avar` | dict / None | required | Merged `{tag: {pre: norm}}` segments | Read-only; None treated as empty |
| `source_axes` | dict | required | Source triples in user units | Read-only |
| `source_avar` | dict / None | required | Source per-axis segments | Read-only; None treated as empty |

Returns a new `{tag: AxisMapping}` only for shared axes. It does not add missing axes.
Source: [axis_mappings](../../format/axis_mapping.py#L266).

### 8.2 source_location

`source_location(mapping, x)`

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `mapping` | AxisMapping | required | One merged→source axis mapping | Read-only |
| `x` | number | required | Merged post-avar normalized coordinate | Read-only |

Returns `mapping.to_source(x)`, including user-space clamping.
Source: [source_location](../../format/axis_mapping.py#L284).

### 8.3 refine_support_rebased

`refine_support_rebased(support, mappings, eps=1e-9)`

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `support` | dict | required | Source post-avar `{tag: (lower, peak, upper)}` | Read-only |
| `mappings` | dict[AxisMapping] | required | One mapping for every active support axis | Read-only |
| `eps` | number | `1e-9` | Dimensionless threshold for omitting small scalar terms | Not a font-coordinate tolerance |

Returns `(C, terms)`; a term is `(support_dict, weight)`.
The default eps is the module constant `EPS`.

Missing active-axis mappings raise `KeyError`.
Unreachable supports return `(0.0, [])`.
If all axes are ignored under OT semantics, it returns `(1.0, [])`.
Source: [refine_support_rebased](../../format/axis_mapping.py#L466).

### 8.4 evaluate_supports

`evaluate_supports(loc_norm, terms)`

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `loc_norm` | dict | required | Merged post-avar `{tag: coordinate}` | Read-only |
| `terms` | iterable | required | `(support_dict, weight)` pairs | Consumed for the sum |

Returns the dimensionless weighted support sum. It does not add a rebasing constant; add `C` separately.
Source: [evaluate_supports](../../format/axis_mapping.py#L536).

### 8.5 fvar_triples

`fvar_triples(font)`

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `font` | TTFont | required | Font with fvar axes in user units | Reads tables; returns a new dictionary |

Returns `{tag: (min, default, max)}`. A missing fvar table can raise `KeyError`.
Source: [fvar_triples](../../format/axis_mapping.py#L544).

### 8.6 avar_segments

`avar_segments(font)`

| Parameter | Type | Default | Meaning / units | Ownership / effects |
| --- | --- | --- | --- | --- |
| `font` | TTFont | required | Font whose pre→norm maps are needed | Reads tables; copies nested dictionaries |

Returns `{tag: {pre: norm}}`, or `{}` when no avar table exists.
Source: [avar_segments](../../format/axis_mapping.py#L549).

## 9. Advanced module functions

These module helpers are not all package-root exports. Full parameters are in the [parameter index](parameter-index.md).
Font-mutating helpers require coordinated fvar/avar, outlines, metrics and stores. One helper call is not a complete merge.

| Module | Signature | Role |
| --- | --- | --- |
| [axis_mapping](../../format/axis_mapping.py) | `invert_piecewise(pl, y, flat="left")` | Segment-wise inverse with explicit plateau choice |
| [axis_mapping](../../format/axis_mapping.py) | `reachable_range(mapping)` | Reachable source normalized interval |
| [axis_mapping](../../format/axis_mapping.py) | `hat_value(x, lower, peak, upper)` | One-dimensional scalar helper |
| [axis_mapping](../../format/axis_mapping.py) | `support_value(loc_norm, support)` | OT support scalar |
| [axis_mapping](../../format/axis_mapping.py) | `refine_1d(lower, peak, upper, mapping, eps=EPS, shift=0.0)` | One-axis refinement |
| [axis_mapping](../../format/axis_mapping.py) | `refine_support(support, mappings, eps=EPS)` | Refinement without rebasing |
| [axis_mapping](../../format/axis_mapping.py) | `axis_support_at_default(tag, support, mapping)` | Merged-default contribution |
| [variation_compose](../../format/variation_compose.py) | `plan_axis_space(main_font, base_font, range_policy="main+extra", avar_mode=0)` | Read inputs and plan output axes |
| [variation_compose](../../format/variation_compose.py) | `merged_default_location(merged_fvar, font=None)` | Default user coordinates, optionally projected |
| [variation_compose](../../format/variation_compose.py) | `instance_at_merged_default(font, merged_fvar)` | Return an instance; source not edited in place |
| [variation_compose](../../format/variation_compose.py) | `reparametrize_gvar(merged_font, source_font, mappings, glyph_names=None, fit="exact")` | Mutate destination gvar |
| [variation_compose](../../format/variation_compose.py) | `fold_layout_default(base_font, mappings)` | Return copied layout with default values folded |
| [variation_compose](../../format/variation_compose.py) | `transfer_base_layout(b_inst, base_font, mappings, merged_fvar)` | Mutate instantiated fallback layout |
| [variation_compose](../../format/variation_compose.py) | `region_split_plans(src_regions, mappings, dst_tags, folded_default=False, eps=1e-4, constant_column=True)` | Build region-column plans |
| [variation_compose](../../format/variation_compose.py) | `reparametrize_var_store(var_store, mappings, src_tags, dst_tags=None, folded_default=False, eps=1e-4)` | Return rewritten store and report |
| [cff2_compose](../../format/cff2_compose.py) | `cff2_var_store(font)` | Read CFF2 store or None |
| [cff2_compose](../../format/cff2_compose.py) | `set_cff2_var_store(font, ot_var_store)` | Mutate CFF2 references to share one store |
| [cff2_compose](../../format/cff2_compose.py) | `reparametrize_cff2(font, mappings, src_tags, dst_tags=None, eps=1e-4)` | Mutate CFF2 blends and store |
| [cff2_compose](../../format/cff2_compose.py) | `is_cff2_variable(font)` | Check CFF2, fvar and store presence |
| [cff2_compose](../../format/cff2_compose.py) | `merge_cff2_var_stores(main_font, base_font, main_mappings, main_tags, dst_tags)` | Mutate both fonts' CFF2 store references |
| [cff2_compose](../../format/cff2_compose.py) | `reparametrize_hvar(font, mappings, src_tags, dst_tags, folded_default)` | Mutate HVAR regions |
| [cff2_compose](../../format/cff2_compose.py) | `merge_cff2_hvar(result, base_store, base_map, added_names)` | Mutate result HVAR and advance mapping |
| [cff2_compose](../../format/cff2_compose.py) | `offset_cff2_vsindex(font, delta)` | Mutate vsindex; flatten supported Private hint variations |

## 10. Examples

This example uses no font files. It checks selected points of a mathematical mapping, not a saved font.

~~~python
from fontTools.varLib.models import supportScalar
from FontMerger import (
    AxisMapping, PiecewiseLinear, evaluate_supports,
    refine_support_rebased, source_location,
)

mapping = AxisMapping((100, 400, 900), None, (200, 400, 800), None)
support = {"wght": (0.0, 0.5, 1.0)}
constant, terms = refine_support_rebased(support, {"wght": mapping})
for x in (-1.0, -0.5, 0.0, 0.25, 0.5, 0.75, 1.0):
    expected = supportScalar(
        {"wght": source_location(mapping, x)}, support, ot=True
    )
    actual = constant + evaluate_supports({"wght": x}, terms)
    assert abs(actual - expected) < 1e-7

identity = PiecewiseLinear.identity()
assert identity.map(0.0) == 0.0
~~~

Reading maps from caller-supplied fonts:

~~~python
from FontMerger import load_font, fvar_triples, avar_segments, axis_mappings

main_font = load_font("Main.ttf")
base_font = load_font("Base.ttf")
mappings = axis_mappings(
    fvar_triples(main_font), avar_segments(main_font),
    fvar_triples(base_font), avar_segments(base_font),
)
~~~

Both inputs in the second example must contain fvar. The result contains only shared axes; it does not plan new axes or edit either font.
