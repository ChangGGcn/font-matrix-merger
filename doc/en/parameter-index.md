# Complete source signature index

[Technical index](../README.md) | [简体中文](../zh-CN/parameter-index.md)

This appendix lists module-level functions and methods defined directly on classes. It is a static source inventory, not a promise that every helper is a supported public API.

Signatures preserve `self` and `cls` as written in source; callers do not pass them to bound methods. Symbolic defaults are resolved below where their module defines a scalar constant. Function bodies, units and ownership are explained in the topic pages.

## Detailed references

[Merge API](merge-api.md) · [Helper API](helper-api.md) · [Subsets and verification](subsets-and-verification.md) · [Variation model](variation-model.md) · [Script reference](script-reference.md)

## Snapshot coverage

- Version: `0.2.1`. Runtime behavior has not changed as part of this documentation update.
- Files: 69 Python/spec files; definitions: 613. Private local-font configuration is excluded without reading it.
- Runtime-source links work in the ZIP. Repository-only test/build paths are plain code references because those scripts are not shipped in the runtime archive.

## Files

- [FontMerging.py](#module-01)
- [__init__.py](#module-02)
- [build/build_exe.py](#module-03)
- [build/font_merger.spec](#module-04)
- [build/make_release_zip.py](#module-05)
- [core/__init__.py](#module-06)
- [core/conflict.py](#module-07)
- [core/glyph_copy.py](#module-08)
- [core/glyph_rename.py](#module-09)
- [core/hinting_policy.py](#module-10)
- [core/invariants.py](#module-11)
- [core/merger.py](#module-12)
- [core/naming.py](#module-13)
- [core/subset_merge.py](#module-14)
- [core/table_policy.py](#module-15)
- [core/verify.py](#module-16)
- [format/__init__.py](#module-17)
- [format/axis_mapping.py](#module-18)
- [format/cff2_compose.py](#module-19)
- [format/cff2_union.py](#module-20)
- [format/cid_convert.py](#module-21)
- [format/cid_merge.py](#module-22)
- [format/converter.py](#module-23)
- [format/static_extract.py](#module-24)
- [format/subsetter.py](#module-25)
- [format/transform.py](#module-26)
- [format/variation_compose.py](#module-27)
- [format/vf_axes.py](#module-28)
- [format/webfont.py](#module-29)
- [tables/__init__.py](#module-30)
- [tables/_strategies.py](#module-31)
- [tables/base.py](#module-32)
- [tables/cmap.py](#module-33)
- [tables/fvar_avar.py](#module-34)
- [tables/head.py](#module-35)
- [tables/hhea_vhea.py](#module-36)
- [tables/kern.py](#module-37)
- [tables/layout_union.py](#module-38)
- [tables/maxp.py](#module-39)
- [tables/metadata_recalc.py](#module-40)
- [tables/metrics.py](#module-41)
- [tables/name_table.py](#module-42)
- [tables/os2.py](#module-43)
- [tables/ot_merge.py](#module-44)
- [tables/otlayout.py](#module-45)
- [tables/post.py](#module-46)
- [tables/varstore.py](#module-47)
- [tests/__init__.py](#module-48)
- [tests/cff2_fixture.py](#module-49)
- [tests/generate_matrix.py](#module-50)
- [tests/generate_samples.py](#module-51)
- [tests/local_fonts.example.py](#module-52)
- [tests/run_regressions.py](#module-53)
- [tests/subset_fixture.py](#module-54)
- [tests/test_axis_mapping.py](#module-55)
- [tests/test_cff2_compose.py](#module-56)
- [tests/test_cmap_regressions.py](#module-57)
- [tests/test_engine_regressions.py](#module-58)
- [tests/test_invariants.py](#module-59)
- [tests/test_layout_regressions.py](#module-60)
- [tests/test_merger.py](#module-61)
- [tests/test_metadata_regressions.py](#module-62)
- [tests/test_naming_regressions.py](#module-63)
- [tests/test_subset_merge.py](#module-64)
- [tests/test_subset_regressions.py](#module-65)
- [tests/test_transform_regressions.py](#module-66)
- [utils/__init__.py](#module-67)
- [utils/detect.py](#module-68)
- [utils/save.py](#module-69)

<a id="module-01"></a>

## FontMerging.py

[Source](../../FontMerging.py)

| Source definition | Signature |
| --- | --- |
| [run](../../FontMerging.py#L26) | `run()` |

<a id="module-02"></a>

## __init__.py

[Source](../../__init__.py)

| Source definition | Signature |
| --- | --- |
| [load_font](../../__init__.py#L75) | `load_font(source)` |
| [merge_fonts](../../__init__.py#L87) | `merge_fonts(main_font, base_fonts, interactive=False, answers=None)` |

<a id="module-03"></a>

## build/build_exe.py

Repository only: `build/build_exe.py`.

| Source definition | Signature |
| --- | --- |
| `_pyinstaller_version` | `_pyinstaller_version()` |
| `check` | `check(verbose=True)` |
| `build` | `build(clean=False, install=False)` |
| `main` | `main(argv=None)` |

<a id="module-04"></a>

## build/font_merger.spec

Repository only: `build/font_merger.spec`.

| Source definition | Signature |
| --- | --- |
| No callable definitions; module setup or declarations. | |

<a id="module-05"></a>

## build/make_release_zip.py

Repository only: `build/make_release_zip.py`.

| Source definition | Signature |
| --- | --- |
| `_run` | `_run(*args)` |
| `read_version` | `read_version()` |
| `collect_files` | `collect_files(preview=False)` |
| `head_time` | `head_time()` |
| `build` | `build(out_path, root, files, date_time)` |
| `main` | `main(argv=None)` |

<a id="module-06"></a>

## core/__init__.py

[Source](../../core/__init__.py)

| Source definition | Signature |
| --- | --- |
| No callable definitions; module setup or declarations. | |

<a id="module-07"></a>

## core/conflict.py

[Source](../../core/conflict.py)

| Source definition | Signature |
| --- | --- |
| [_uvs_glyphs](../../core/conflict.py#L10) | `_uvs_glyphs(main_font, base_font)` |
| [resolve_conflicts](../../core/conflict.py#L32) | `resolve_conflicts(main_font, base_font)` |
| [_plan_merge_aliases](../../core/conflict.py#L76) | `_plan_merge_aliases(main_font, base_font, tag='b', index=1)` |
| [plan_alias](../../core/conflict.py#L94) | `plan_alias(main_font, base_font, tag='b', index=1)` |

<a id="module-08"></a>

## core/glyph_copy.py

[Source](../../core/glyph_copy.py)

| Source definition | Signature |
| --- | --- |
| [_rmtree](../../core/glyph_copy.py#L8) | `_rmtree(d)` |
| [inject_glyphs_xml](../../core/glyph_copy.py#L20) | `inject_glyphs_xml(main_ttx, base_ttx, output_ttx, glyph_names)` |
| [_extend_variation_maps](../../core/glyph_copy.py#L168) | `_extend_variation_maps(font, glyph_names)` |
| [_prepare_glyph_copy](../../core/glyph_copy.py#L184) | `_prepare_glyph_copy(main_font, base_font, glyphs_to_add)` |
| [_record_copy_sources](../../core/glyph_copy.py#L225) | `_record_copy_sources(result, main_font, base_font, glyph_names)` |
| [merge_glyphs_object](../../core/glyph_copy.py#L234) | `merge_glyphs_object(main_font, base_font, glyphs_to_add)` |
| [merge_glyphs_via_ttx](../../core/glyph_copy.py#L298) | `merge_glyphs_via_ttx(main_font, base_font, glyphs_to_add, use_ttx=None)` |
| [_unicode_cmap](../../core/glyph_copy.py#L371) | `_unicode_cmap(font)` |
| [_cmap_limit](../../core/glyph_copy.py#L383) | `_cmap_limit(fmt)` |
| [_copy_cmap_mappings](../../core/glyph_copy.py#L390) | `_copy_cmap_mappings(dst, src, glyph_names)` |

<a id="module-09"></a>

## core/glyph_rename.py

[Source](../../core/glyph_rename.py)

| Source definition | Signature |
| --- | --- |
| [alias_name](../../core/glyph_rename.py#L13) | `alias_name(name, taken, tag='b', index=1)` |
| [_rename_glyf](../../core/glyph_rename.py#L26) | `_rename_glyf(font, mapping)` |
| [_rename_cff](../../core/glyph_rename.py#L41) | `_rename_cff(font, mapping)` |
| [_rename_metrics](../../core/glyph_rename.py#L59) | `_rename_metrics(font, tag, mapping)` |
| [_rename_cmap](../../core/glyph_rename.py#L68) | `_rename_cmap(font, mapping)` |
| [_rename_variation_maps](../../core/glyph_rename.py#L83) | `_rename_variation_maps(font, mapping)` |
| [rename_glyphs](../../core/glyph_rename.py#L97) | `rename_glyphs(font, mapping)` |
| [renamed_copy](../../core/glyph_rename.py#L144) | `renamed_copy(font, mapping)` |

<a id="module-10"></a>

## core/hinting_policy.py

[Source](../../core/hinting_policy.py)

| Source definition | Signature |
| --- | --- |
| [_strip_programs](../../core/hinting_policy.py#L15) | `_strip_programs(font, names)` |
| [apply_hinting_policy](../../core/hinting_policy.py#L25) | `apply_hinting_policy(result, main, base, added)` |

<a id="module-11"></a>

## core/invariants.py

[Source](../../core/invariants.py)

| Source definition | Signature |
| --- | --- |
| [unicode_cmap](../../core/invariants.py#L8) | `unicode_cmap(font)` |
| [assert_cmap_union](../../core/invariants.py#L21) | `assert_cmap_union(result, main, base, check_main=True, base_mapping=None)` |
| [_uvs_map](../../core/invariants.py#L53) | `_uvs_map(font)` |
| [validate_input_uvs](../../core/invariants.py#L67) | `validate_input_uvs(font, label)` |
| [assert_font_structure](../../core/invariants.py#L84) | `assert_font_structure(font)` |

<a id="module-12"></a>

## core/merger.py

[Source](../../core/merger.py)

| Source definition | Signature |
| --- | --- |
| [_diagnose_empty_merge](../../core/merger.py#L13) | `_diagnose_empty_merge(m, b, conflicts)` |
| [check_compatibility](../../core/merger.py#L44) | `check_compatibility(main_font, base_font)` |
| [axes_compatible](../../core/merger.py#L88) | `axes_compatible(main_font, base_font)` |
| [transfer_glyph_variations](../../core/merger.py#L119) | `transfer_glyph_variations(result, base_var, glyph_names)` |
| [_copy_axis_records](../../core/merger.py#L151) | `_copy_axis_records(src_font, dst_font, merged_fvar, merged_avar)` |
| [_fill_fvar_instances](../../core/merger.py#L196) | `_fill_fvar_instances(font, merged_fvar)` |
| [_copy_name_records](../../core/merger.py#L209) | `_copy_name_records(src_font, dst_font, name_id)` |
| [_compose_cff2_base](../../core/merger.py#L223) | `_compose_cff2_base(m, b, base_font, plan)` |
| [_finish_cff2_hvar](../../core/merger.py#L264) | `_finish_cff2_hvar(result, m, plan)` |
| [_transfer_base_layout_once](../../core/merger.py#L278) | `_transfer_base_layout_once(b, base_font, plan)` |
| [_map_main_var_stores](../../core/merger.py#L299) | `_map_main_var_stores(font, mappings, src_tags, dst_tags, label='合成')` |
| [_reparametrize_main_after_union](../../core/merger.py#L334) | `_reparametrize_main_after_union(main_font, before_axes, before_avar)` |
| [_apply_axis_plan](../../core/merger.py#L359) | `_apply_axis_plan(main_font, base_font, range_policy, avar_mode, fit)` |
| [_finish_variable_merge](../../core/merger.py#L407) | `_finish_variable_merge(merger, result, m, b, variable_source, plan)` |
| [_force_load_axis_tables](../../core/merger.py#L437) | `_force_load_axis_tables(font)` |
| [_collapsing_flats](../../core/merger.py#L448) | `_collapsing_flats(plan)` |
| [_remove_ros](../../core/merger.py#L457) | `_remove_ros(font)` |
| [_add_cid_prefix](../../core/merger.py#L472) | `_add_cid_prefix(font, prefix)` |
| [_normalize_upm](../../core/merger.py#L517) | `_normalize_upm(main_font, base_font)` |
| [FontMerger.__init__](../../core/merger.py#L559) | `FontMerger.__init__(self, compose_variations=True, compose_range='main+extra', compose_fit='exact', avar_mode=0, verify_compose=True, compose_layout=True)` |
| [FontMerger.ask](../../core/merger.py#L570) | `FontMerger.ask(self, key, q, opts=None)` |
| [FontMerger.merge_two](../../core/merger.py#L593) | `FontMerger.merge_two(self, m, b)` |
| [FontMerger._do_merge](../../core/merger.py#L624) | `FontMerger._do_merge(self, m, b, variable_source=None)` |
| [FontMerger._do_merge_once](../../core/merger.py#L639) | `FontMerger._do_merge_once(self, m, b, variable_source=None, compose=False)` |
| [FontMerger._chunked_merge](../../core/merger.py#L791) | `FontMerger._chunked_merge(self, m, b, to_add, chunk_size, variable_source=None, plan=None)` |
| [FontMerger._sOTF_sOTF](../../core/merger.py#L815) | `FontMerger._sOTF_sOTF(self, m, b)` |
| [FontMerger._sTTF_sTTF](../../core/merger.py#L816) | `FontMerger._sTTF_sTTF(self, m, b)` |
| [FontMerger._sOTF_sTTF](../../core/merger.py#L817) | `FontMerger._sOTF_sTTF(self, m, b)` |
| [FontMerger._sTTF_sOTF](../../core/merger.py#L820) | `FontMerger._sTTF_sOTF(self, m, b)` |
| [FontMerger._sOTF_vOTF](../../core/merger.py#L825) | `FontMerger._sOTF_vOTF(self, m, b)` |
| [FontMerger._sOTF_vTTF](../../core/merger.py#L826) | `FontMerger._sOTF_vTTF(self, m, b)` |
| [FontMerger._sTTF_vOTF](../../core/merger.py#L827) | `FontMerger._sTTF_vOTF(self, m, b)` |
| [FontMerger._sTTF_vTTF](../../core/merger.py#L828) | `FontMerger._sTTF_vTTF(self, m, b)` |
| [FontMerger._vOTF_sOTF](../../core/merger.py#L831) | `FontMerger._vOTF_sOTF(self, m, b)` |
| [FontMerger._vOTF_sTTF](../../core/merger.py#L835) | `FontMerger._vOTF_sTTF(self, m, b)` |
| [FontMerger._vTTF_sOTF](../../core/merger.py#L843) | `FontMerger._vTTF_sOTF(self, m, b)` |
| [FontMerger._vTTF_sTTF](../../core/merger.py#L849) | `FontMerger._vTTF_sTTF(self, m, b)` |
| [FontMerger._vOTF_vOTF](../../core/merger.py#L857) | `FontMerger._vOTF_vOTF(self, m, b)` |
| [FontMerger._vOTF_vTTF](../../core/merger.py#L859) | `FontMerger._vOTF_vTTF(self, m, b)` |
| [FontMerger._vTTF_vOTF](../../core/merger.py#L862) | `FontMerger._vTTF_vOTF(self, m, b)` |
| [FontMerger._vTTF_vTTF](../../core/merger.py#L865) | `FontMerger._vTTF_vTTF(self, m, b)` |
| [FontMerger._axis_union](../../core/merger.py#L869) | `FontMerger._axis_union(m, b)` |
| [_finalize_merge](../../core/merger.py#L877) | `_finalize_merge(result, main, base, check_main=True)` |
| [_merge_base_layout_once](../../core/merger.py#L898) | `_merge_base_layout_once(result, base_font, to_add)` |

<a id="module-13"></a>

## core/naming.py

[Source](../../core/naming.py)

| Source definition | Signature |
| --- | --- |
| [_groups](../../core/naming.py#L19) | `_groups(records)` |
| [_lookup](../../core/naming.py#L28) | `_lookup(groups, key, name_id, default=None)` |
| [_modified](../../core/naming.py#L39) | `_modified(family)` |
| [_unique_parts](../../core/naming.py#L44) | `_unique_parts(texts)` |
| [_set_name](../../core/naming.py#L54) | `_set_name(table, text, name_id, key)` |
| [_postscript_name](../../core/naming.py#L75) | `_postscript_name(family, style)` |
| [apply_naming](../../core/naming.py#L85) | `apply_naming(output_font, main_family, all_copyrights)` |

<a id="module-14"></a>

## core/subset_merge.py

[Source](../../core/subset_merge.py)

| Source definition | Signature |
| --- | --- |
| [_copy_cmap_subtable](../../core/subset_merge.py#L76) | `_copy_cmap_subtable(dst_font, src_st, fmt, sub_idx)` |
| [SameSourceSubsetMerger.__init__](../../core/subset_merge.py#L94) | `SameSourceSubsetMerger.__init__(self, tag='s', verbose=True)` |
| [SameSourceSubsetMerger.log](../../core/subset_merge.py#L117) | `SameSourceSubsetMerger.log(self, *args)` |
| [SameSourceSubsetMerger._check_cff2](../../core/subset_merge.py#L125) | `SameSourceSubsetMerger._check_cff2(subsets)` |
| [SameSourceSubsetMerger._copy_cff2_glyphs](../../core/subset_merge.py#L143) | `SameSourceSubsetMerger._copy_cff2_glyphs(merged, base, pairs, fd_map=None)` |
| [SameSourceSubsetMerger.rename_map](../../core/subset_merge.py#L151) | `SameSourceSubsetMerger.rename_map(base, main_names, tag, index, layout_names=frozenset())` |
| [SameSourceSubsetMerger.merge](../../core/subset_merge.py#L181) | `SameSourceSubsetMerger.merge(self, subsets, labels=None)` |
| [SameSourceSubsetMerger._merge_cmap](../../core/subset_merge.py#L354) | `SameSourceSubsetMerger._merge_cmap(self, merged, base, merged_sub_idx, ren, merged_names, merged_cmap)` |
| [SameSourceSubsetMerger._harmonize_cmap](../../core/subset_merge.py#L375) | `SameSourceSubsetMerger._harmonize_cmap(merged, cmap_map)` |
| [SameSourceSubsetMerger._reorder_by_codepoint](../../core/subset_merge.py#L393) | `SameSourceSubsetMerger._reorder_by_codepoint(self, merged, cmap_map)` |
| [SameSourceSubsetMerger._merge_gdef](../../core/subset_merge.py#L413) | `SameSourceSubsetMerger._merge_gdef(self, gdef, ren)` |
| [SameSourceSubsetMerger._finalize_gdef](../../core/subset_merge.py#L433) | `SameSourceSubsetMerger._finalize_gdef(self, merged)` |
| [SameSourceSubsetMerger._merge_variation_maps](../../core/subset_merge.py#L470) | `SameSourceSubsetMerger._merge_variation_maps(self, merged, base, ren, vvar_offset, hvar_offset, added_names)` |
| [SameSourceSubsetMerger._finalize_variation_maps](../../core/subset_merge.py#L497) | `SameSourceSubsetMerger._finalize_variation_maps(self, merged)` |
| [SameSourceSubsetMerger._recalc_metrics](../../core/subset_merge.py#L522) | `SameSourceSubsetMerger._recalc_metrics(font)` |
| [SameSourceSubsetMerger.glyph_map](../../core/subset_merge.py#L606) | `SameSourceSubsetMerger.glyph_map(self)` |
| [_recalc_metrics_cff](../../core/subset_merge.py#L621) | `_recalc_metrics_cff(font)` |
| [load_subsets](../../core/subset_merge.py#L708) | `load_subsets(subsets)` |
| [merge_subsets](../../core/subset_merge.py#L723) | `merge_subsets(subsets, out_path=None, tag='s', output_flavor=None, complete_name_table=True, fix_head_flags=True, verify=False, verbose=True, **verify_kwargs)` |

<a id="module-15"></a>

## core/table_policy.py

[Source](../../core/table_policy.py)

| Source definition | Signature |
| --- | --- |
| [_union_kern](../../core/table_policy.py#L20) | `_union_kern(result, main, bases, added)` |
| [_metric_origin](../../core/table_policy.py#L71) | `_metric_origin(font, name, glyphs)` |
| [_union_vorg](../../core/table_policy.py#L81) | `_union_vorg(result, main, bases, added)` |
| [apply_table_policy](../../core/table_policy.py#L127) | `apply_table_policy(result, main, bases, added)` |

<a id="module-16"></a>

## core/verify.py

[Source](../../core/verify.py)

| Source definition | Signature |
| --- | --- |
| [_pen_value](../../core/verify.py#L26) | `_pen_value(font, glyph_name, glyph_set=None)` |
| [_pen](../../core/verify.py#L32) | `_pen(glyph_name, glyph_set)` |
| [_coords_delta](../../core/verify.py#L39) | `_coords_delta(a, b, tolerance)` |
| [_instance](../../core/verify.py#L58) | `_instance(font, position)` |
| [grid_positions](../../core/verify.py#L78) | `grid_positions(font, per_axis=3, max_positions=64)` |
| [_auto_positions](../../core/verify.py#L94) | `_auto_positions(font)` |
| [_label](../../core/verify.py#L106) | `_label(position, font)` |
| [verify_merge](../../core/verify.py#L112) | `verify_merge(sources, merged, glyph_map=None, axis_positions='auto', tolerance=0.0, sample=None, verbose=True)` |
| [_feature_glyph_count](../../core/verify.py#L376) | `_feature_glyph_count(font, tag, feat)` |
| [verify_composition](../../core/verify.py#L408) | `verify_composition(merged, main_font, base_font, added_glyphs, sample=30, tolerance=1.0, max_positions=6, verbose=False, adv_tolerance=None)` |
| [_check_layout_integrity](../../core/verify.py#L480) | `_check_layout_integrity(font)` |
| [_check_lookup_references](../../core/verify.py#L589) | `_check_lookup_references(font)` |
| [_check_var_stores](../../core/verify.py#L644) | `_check_var_stores(font)` |

<a id="module-17"></a>

## format/__init__.py

[Source](../../format/__init__.py)

| Source definition | Signature |
| --- | --- |
| No callable definitions; module setup or declarations. | |

<a id="module-18"></a>

## format/axis_mapping.py

[Source](../../format/axis_mapping.py)

| Source definition | Signature |
| --- | --- |
| [_clamp_axis](../../format/axis_mapping.py#L36) | `_clamp_axis(v)` |
| [invert_piecewise](../../format/axis_mapping.py#L40) | `invert_piecewise(pl, y, flat='left')` |
| [PiecewiseLinear.__init__](../../format/axis_mapping.py#L72) | `PiecewiseLinear.__init__(self, points)` |
| [PiecewiseLinear.identity](../../format/axis_mapping.py#L78) | `PiecewiseLinear.identity(cls)` |
| [PiecewiseLinear.fvar](../../format/axis_mapping.py#L82) | `PiecewiseLinear.fvar(cls, triple)` |
| [PiecewiseLinear.avar](../../format/axis_mapping.py#L99) | `PiecewiseLinear.avar(cls, segments)` |
| [PiecewiseLinear.map](../../format/axis_mapping.py#L105) | `PiecewiseLinear.map(self, x)` |
| [PiecewiseLinear.inverse](../../format/axis_mapping.py#L128) | `PiecewiseLinear.inverse(self)` |
| [PiecewiseLinear.compose](../../format/axis_mapping.py#L144) | `PiecewiseLinear.compose(self, other)` |
| [PiecewiseLinear.breakpoints](../../format/axis_mapping.py#L159) | `PiecewiseLinear.breakpoints(self, lo=AXIS_MIN, hi=AXIS_MAX)` |
| [PiecewiseLinear.is_identity](../../format/axis_mapping.py#L163) | `PiecewiseLinear.is_identity(self)` |
| [PiecewiseLinear.__repr__](../../format/axis_mapping.py#L167) | `PiecewiseLinear.__repr__(self)` |
| [AxisMapping.__init__](../../format/axis_mapping.py#L174) | `AxisMapping.__init__(self, merged_triple, merged_avar, source_triple, source_avar)` |
| [AxisMapping.to_source](../../format/axis_mapping.py#L196) | `AxisMapping.to_source(self, x)` |
| [AxisMapping.to_merged](../../format/axis_mapping.py#L206) | `AxisMapping.to_merged(self, y)` |
| [AxisMapping.kinks_merged](../../format/axis_mapping.py#L213) | `AxisMapping.kinks_merged(self)` |
| [AxisMapping.collapsing_flats](../../format/axis_mapping.py#L241) | `AxisMapping.collapsing_flats(self)` |
| [AxisMapping.is_identity](../../format/axis_mapping.py#L256) | `AxisMapping.is_identity(self)` |
| [AxisMapping.__repr__](../../format/axis_mapping.py#L261) | `AxisMapping.__repr__(self)` |
| [axis_mappings](../../format/axis_mapping.py#L266) | `axis_mappings(merged_axes, merged_avar, source_axes, source_avar)` |
| [source_location](../../format/axis_mapping.py#L284) | `source_location(mapping, x)` |
| [reachable_range](../../format/axis_mapping.py#L292) | `reachable_range(mapping)` |
| [hat_value](../../format/axis_mapping.py#L308) | `hat_value(x, lower, peak, upper)` |
| [support_value](../../format/axis_mapping.py#L321) | `support_value(loc_norm, support)` |
| [refine_1d](../../format/axis_mapping.py#L326) | `refine_1d(lower, peak, upper, mapping, eps=EPS, shift=0.0)` |
| [refine_support](../../format/axis_mapping.py#L430) | `refine_support(support, mappings, eps=EPS)` |
| [axis_support_at_default](../../format/axis_mapping.py#L454) | `axis_support_at_default(tag, support, mapping)` |
| [refine_support_rebased](../../format/axis_mapping.py#L466) | `refine_support_rebased(support, mappings, eps=EPS)` |
| [evaluate_supports](../../format/axis_mapping.py#L536) | `evaluate_supports(loc_norm, terms)` |
| [fvar_triples](../../format/axis_mapping.py#L544) | `fvar_triples(font)` |
| [avar_segments](../../format/axis_mapping.py#L549) | `avar_segments(font)` |

Symbolic defaults: `AXIS_MAX = 1.0`; `AXIS_MIN = -1.0`; `EPS = 1e-09`.

<a id="module-19"></a>

## format/cff2_compose.py

[Source](../../format/cff2_compose.py)

| Source definition | Signature |
| --- | --- |
| [cff2_var_store](../../format/cff2_compose.py#L33) | `cff2_var_store(font)` |
| [set_cff2_var_store](../../format/cff2_compose.py#L48) | `set_cff2_var_store(font, ot_var_store)` |
| [_private_dicts](../../format/cff2_compose.py#L62) | `_private_dicts(td)` |
| [_programs](../../format/cff2_compose.py#L74) | `_programs(td)` |
| [_blend_columns](../../format/cff2_compose.py#L85) | `_blend_columns(var_store)` |
| [_rewrite_deltas](../../format/cff2_compose.py#L93) | `_rewrite_deltas(deltas, src_regions, plans, constants)` |
| [_rewrite_program](../../format/cff2_compose.py#L105) | `_rewrite_program(program, layout, plans, constants, new_widths)` |
| [_private_arg_types](../../format/cff2_compose.py#L149) | `_private_arg_types()` |
| [_rewrite_private](../../format/cff2_compose.py#L160) | `_rewrite_private(pd, layout, plans, constants)` |
| [reparametrize_cff2](../../format/cff2_compose.py#L206) | `reparametrize_cff2(font, mappings, src_tags, dst_tags=None, eps=0.0001)` |
| [is_cff2_variable](../../format/cff2_compose.py#L277) | `is_cff2_variable(font)` |
| [merge_cff2_var_stores](../../format/cff2_compose.py#L282) | `merge_cff2_var_stores(main_font, base_font, main_mappings, main_tags, dst_tags)` |
| [reparametrize_hvar](../../format/cff2_compose.py#L329) | `reparametrize_hvar(font, mappings, src_tags, dst_tags, folded_default)` |
| [merge_cff2_hvar](../../format/cff2_compose.py#L347) | `merge_cff2_hvar(result, base_store, base_map, added_names)` |
| [offset_cff2_vsindex](../../format/cff2_compose.py#L388) | `offset_cff2_vsindex(font, delta)` |

<a id="module-20"></a>

## format/cff2_union.py

[Source](../../format/cff2_union.py)

| Source definition | Signature |
| --- | --- |
| [_program_key](../../format/cff2_union.py#L33) | `_program_key(charstring)` |
| [subrs_signature](../../format/cff2_union.py#L41) | `subrs_signature(index)` |
| [_value_key](../../format/cff2_union.py#L48) | `_value_key(value, depth=0)` |
| [fdarray_signature](../../format/cff2_union.py#L65) | `fdarray_signature(top)` |
| [varstore_signature](../../format/cff2_union.py#L78) | `varstore_signature(var_store_data)` |
| [_deltas_key](../../format/cff2_union.py#L95) | `_deltas_key(var_data)` |
| [fd_key](../../format/cff2_union.py#L110) | `fd_key(fd)` |
| [FDUnion.__init__](../../format/cff2_union.py#L127) | `FDUnion.__init__(self, merged_top)` |
| [FDUnion.add](../../format/cff2_union.py#L132) | `FDUnion.add(self, base_top)` |
| [cff2_key](../../format/cff2_union.py#L156) | `cff2_key(font)` |
| [check_cff2_compatible](../../format/cff2_union.py#L164) | `check_cff2_compatible(main_font, base_font)` |
| [copy_glyphs](../../format/cff2_union.py#L184) | `copy_glyphs(merged_font, base_font, pairs, fd_map=None)` |
| [sync_glyph_order](../../format/cff2_union.py#L234) | `sync_glyph_order(font)` |
| [set_var_store](../../format/cff2_union.py#L246) | `set_var_store(top, ot_var_store)` |

<a id="module-21"></a>

## format/cid_convert.py

[Source](../../format/cid_convert.py)

| Source definition | Signature |
| --- | --- |
| [_has_ros](../../format/cid_convert.py#L9) | `_has_ros(font)` |
| [_is_cid_font](../../format/cid_convert.py#L17) | `_is_cid_font(font)` |
| [name_to_cid](../../format/cid_convert.py#L21) | `name_to_cid(font)` |
| [cid_to_name](../../format/cid_convert.py#L125) | `cid_to_name(font)` |
| [ensure_cid_format](../../format/cid_convert.py#L233) | `ensure_cid_format(font)` |
| [ensure_name_format](../../format/cid_convert.py#L242) | `ensure_name_format(font)` |

<a id="module-22"></a>

## format/cid_merge.py

[Source](../../format/cid_merge.py)

| Source definition | Signature |
| --- | --- |
| [_has_ros](../../format/cid_merge.py#L13) | `_has_ros(font)` |
| [_get_max_cid](../../format/cid_merge.py#L19) | `_get_max_cid(font)` |
| [shift_cid_range](../../format/cid_merge.py#L33) | `shift_cid_range(font, offset)` |
| [_materialize_charstrings](../../format/cid_merge.py#L109) | `_materialize_charstrings(font)` |
| [merge_cid_fonts](../../format/cid_merge.py#L148) | `merge_cid_fonts(main_font, base_font, added_glyphs)` |
| [cid_ufo_style_merge](../../format/cid_merge.py#L226) | `cid_ufo_style_merge(main_font, base_font)` |

<a id="module-23"></a>

## format/converter.py

[Source](../../format/converter.py)

| Source definition | Signature |
| --- | --- |
| [_require_static_conversion](../../format/converter.py#L20) | `_require_static_conversion(font)` |
| [cff_to_glyf](../../format/converter.py#L28) | `cff_to_glyf(font)` |
| [glyf_to_cff](../../format/converter.py#L105) | `glyf_to_cff(font)` |
| [_apply_windows_fixes](../../format/converter.py#L192) | `_apply_windows_fixes(result, source_font)` |
| [_fallback_glyf_to_cff](../../format/converter.py#L258) | `_fallback_glyf_to_cff(glyph_set, gn, width)` |
| [convert_font_format](../../format/converter.py#L269) | `convert_font_format(font, to_cff)` |

<a id="module-24"></a>

## format/static_extract.py

[Source](../../format/static_extract.py)

| Source definition | Signature |
| --- | --- |
| [variable_to_static](../../format/static_extract.py#L12) | `variable_to_static(font, remove_overlaps=False)` |

<a id="module-25"></a>

## format/subsetter.py

[Source](../../format/subsetter.py)

| Source definition | Signature |
| --- | --- |
| [create_glyph_subset](../../format/subsetter.py#L12) | `create_glyph_subset(font, glyph_names, strip_layout=True)` |

<a id="module-26"></a>

## format/transform.py

[Source](../../format/transform.py)

| Source definition | Signature |
| --- | --- |
| [_transform_matrix](../../format/transform.py#L26) | `_transform_matrix(scale, baseline_offset)` |
| [_remove_hinting](../../format/transform.py#L31) | `_remove_hinting(font)` |
| [scale_font](../../format/transform.py#L58) | `scale_font(font, scale, baseline_offset)` |
| [_vertical_positions](../../format/transform.py#L147) | `_vertical_positions(font)` |
| [_glyph_bounds](../../format/transform.py#L175) | `_glyph_bounds(font)` |
| [_scale_glyf](../../format/transform.py#L195) | `_scale_glyf(font, matrix)` |
| [_translate_cff](../../format/transform.py#L226) | `_translate_cff(font, offset)` |
| [apply_scale_offset](../../format/transform.py#L249) | `apply_scale_offset(font, scale_percent, baseline_offset)` |

<a id="module-27"></a>

## format/variation_compose.py

[Source](../../format/variation_compose.py)

| Source definition | Signature |
| --- | --- |
| [plan_axis_space](../../format/variation_compose.py#L41) | `plan_axis_space(main_font, base_font, range_policy='main+extra', avar_mode=0)` |
| [merged_default_location](../../format/variation_compose.py#L84) | `merged_default_location(merged_fvar, font=None)` |
| [instance_at_merged_default](../../format/variation_compose.py#L93) | `instance_at_merged_default(font, merged_fvar)` |
| [_map_support_terms](../../format/variation_compose.py#L104) | `_map_support_terms(support, mappings, fit='exact')` |
| [reparametrize_gvar](../../format/variation_compose.py#L121) | `reparametrize_gvar(merged_font, source_font, mappings, glyph_names=None, fit='exact')` |
| [_store_region_supports](../../format/variation_compose.py#L184) | `_store_region_supports(var_store, src_tags)` |
| [_make_region](../../format/variation_compose.py#L197) | `_make_region(support, dst_tags)` |
| [_num_shorts](../../format/variation_compose.py#L211) | `_num_shorts(rows, orig=0)` |
| [fold_layout_default](../../format/variation_compose.py#L223) | `fold_layout_default(base_font, mappings)` |
| [transfer_base_layout](../../format/variation_compose.py#L265) | `transfer_base_layout(b_inst, base_font, mappings, merged_fvar)` |
| [region_split_plans](../../format/variation_compose.py#L291) | `region_split_plans(src_regions, mappings, dst_tags, folded_default=False, eps=0.0001, constant_column=True)` |
| [reparametrize_var_store](../../format/variation_compose.py#L347) | `reparametrize_var_store(var_store, mappings, src_tags, dst_tags=None, folded_default=False, eps=0.0001)` |

<a id="module-28"></a>

## format/vf_axes.py

[Source](../../format/vf_axes.py)

| Source definition | Signature |
| --- | --- |
| [get_axes_info](../../format/vf_axes.py#L19) | `get_axes_info(font)` |
| [union_axes](../../format/vf_axes.py#L27) | `union_axes(main_font, base_font)` |
| [_extend_avar_axes](../../format/vf_axes.py#L79) | `_extend_avar_axes(font, n_new_axes)` |
| [_extend_varstore_regions](../../format/vf_axes.py#L100) | `_extend_varstore_regions(font, n_new_axes)` |
| [_extend_region_list](../../format/vf_axes.py#L131) | `_extend_region_list(region_list, n_new_axes)` |
| [_fill_default_axis_values](../../format/vf_axes.py#L144) | `_fill_default_axis_values(font, added)` |
| [_ensure_stat_axis](../../format/vf_axes.py#L164) | `_ensure_stat_axis(font, axis)` |
| [axis_union_merge](../../format/vf_axes.py#L184) | `axis_union_merge(main_font, base_font)` |

<a id="module-29"></a>

## format/webfont.py

[Source](../../format/webfont.py)

| Source definition | Signature |
| --- | --- |
| [unwrap_webfont](../../format/webfont.py#L5) | `unwrap_webfont(path)` |

<a id="module-30"></a>

## tables/__init__.py

[Source](../../tables/__init__.py)

| Source definition | Signature |
| --- | --- |
| No callable definitions; module setup or declarations. | |

<a id="module-31"></a>

## tables/_strategies.py

[Source](../../tables/_strategies.py)

| Source definition | Signature |
| --- | --- |
| [first](../../tables/_strategies.py#L4) | `first(values, default=None)` |
| [max_val](../../tables/_strategies.py#L9) | `max_val(values, default=0)` |
| [min_val](../../tables/_strategies.py#L14) | `min_val(values, default=0)` |
| [bitwise_or](../../tables/_strategies.py#L19) | `bitwise_or(values)` |
| [bitwise_and](../../tables/_strategies.py#L28) | `bitwise_and(values)` |
| [sum_vals](../../tables/_strategies.py#L39) | `sum_vals(values)` |
| [sum_lists](../../tables/_strategies.py#L44) | `sum_lists(lists)` |
| [sum_dicts](../../tables/_strategies.py#L53) | `sum_dicts(dicts)` |
| [current_time](../../tables/_strategies.py#L62) | `current_time(_=None)` |
| [equal](../../tables/_strategies.py#L68) | `equal(values)` |
| [recalculate](../../tables/_strategies.py#L79) | `recalculate(_=None)` |

<a id="module-32"></a>

## tables/base.py

[Source](../../tables/base.py)

| Source definition | Signature |
| --- | --- |
| [register](../../tables/base.py#L10) | `register(tag)` |
| [merge_all_tables](../../tables/base.py#L18) | `merge_all_tables(merged_font, main_font, base_fonts, added_glyphs=None)` |

<a id="module-33"></a>

## tables/cmap.py

[Source](../../tables/cmap.py)

| Source definition | Signature |
| --- | --- |
| [merge_cmap](../../tables/cmap.py#L7) | `merge_cmap(merged, main, bases, added=None)` |

<a id="module-34"></a>

## tables/fvar_avar.py

[Source](../../tables/fvar_avar.py)

| Source definition | Signature |
| --- | --- |
| [merge_fvar](../../tables/fvar_avar.py#L8) | `merge_fvar(merged, main, bases, added=None)` |
| [merge_avar](../../tables/fvar_avar.py#L39) | `merge_avar(merged, main, bases, added=None)` |

<a id="module-35"></a>

## tables/head.py

[Source](../../tables/head.py)

| Source definition | Signature |
| --- | --- |
| [merge_head](../../tables/head.py#L10) | `merge_head(merged, main, bases, added=None)` |
| [fix_head_flags](../../tables/head.py#L40) | `fix_head_flags(font)` |

<a id="module-36"></a>

## tables/hhea_vhea.py

[Source](../../tables/hhea_vhea.py)

| Source definition | Signature |
| --- | --- |
| [_merge_hhea_vhea](../../tables/hhea_vhea.py#L6) | `_merge_hhea_vhea(merged, main, bases, tag)` |
| [merge_hhea](../../tables/hhea_vhea.py#L39) | `merge_hhea(merged, main, bases, added=None)` |
| [merge_vhea](../../tables/hhea_vhea.py#L44) | `merge_vhea(merged, main, bases, added=None)` |

<a id="module-37"></a>

## tables/kern.py

[Source](../../tables/kern.py)

| Source definition | Signature |
| --- | --- |
| [merge_kern](../../tables/kern.py#L6) | `merge_kern(merged, main, bases, added=None)` |

<a id="module-38"></a>

## tables/layout_union.py

[Source](../../tables/layout_union.py)

| Source definition | Signature |
| --- | --- |
| [remap_glyph_names](../../tables/layout_union.py#L22) | `remap_glyph_names(obj, ren, seen=None)` |
| [offset_var_devices](../../tables/layout_union.py#L64) | `offset_var_devices(obj, delta, seen=None)` |
| [layout_glyph_names](../../tables/layout_union.py#L92) | `layout_glyph_names(font)` |
| [sort_coverage_with](../../tables/layout_union.py#L133) | `sort_coverage_with(cov, arrays, order_index)` |
| [_fix_subtable_order](../../tables/layout_union.py#L146) | `_fix_subtable_order(st, order_index)` |
| [resort_layout](../../tables/layout_union.py#L200) | `resort_layout(font)` |
| [lang_systems](../../tables/layout_union.py#L246) | `lang_systems(script)` |
| [lang_systems_with_tag](../../tables/layout_union.py#L256) | `lang_systems_with_tag(script)` |
| [find_or_create_lang](../../tables/layout_union.py#L266) | `find_or_create_lang(script, lang_tag)` |
| [_freeze](../../tables/layout_union.py#L292) | `_freeze(value, depth=0)` |
| [MarkGlyphSetUnion.__init__](../../tables/layout_union.py#L321) | `MarkGlyphSetUnion.__init__(self)` |
| [MarkGlyphSetUnion.add](../../tables/layout_union.py#L325) | `MarkGlyphSetUnion.add(self, mark_glyph_sets, remap_name=None, alive=None, order_index=None)` |
| [MarkGlyphSetUnion.build](../../tables/layout_union.py#L347) | `MarkGlyphSetUnion.build(self, order_index=None)` |
| [MarkGlyphSetUnion.__bool__](../../tables/layout_union.py#L364) | `MarkGlyphSetUnion.__bool__(self)` |
| [remap_feature_variations](../../tables/layout_union.py#L368) | `remap_feature_variations(fv, index_map)` |
| [_lookup_records](../../tables/layout_union.py#L395) | `_lookup_records(obj, seen=None)` |
| [_prune_context_refs](../../tables/layout_union.py#L415) | `_prune_context_refs(st, available)` |
| [_prepare_lookup_graph](../../tables/layout_union.py#L455) | `_prepare_lookup_graph(lookups, lookup_base, roots=None)` |
| [_ordered_unique](../../tables/layout_union.py#L494) | `_ordered_unique(values)` |
| [_merge_required_feature](../../tables/layout_union.py#L499) | `_merge_required_feature(lang, required, records)` |
| [_coalesce_langsys_features](../../tables/layout_union.py#L516) | `_coalesce_langsys_features(table)` |
| [LayoutUnion.__init__](../../tables/layout_union.py#L609) | `LayoutUnion.__init__(self, tag)` |
| [LayoutUnion.add_from](../../tables/layout_union.py#L621) | `LayoutUnion.add_from(self, base_table, ren, var_offset=0, mark_set_remap=())` |
| [LayoutUnion._add_feature_variations](../../tables/layout_union.py#L693) | `LayoutUnion._add_feature_variations(self, base_table, ren, lookup_map, base_index_map, var_offset)` |
| [LayoutUnion._merge_scripts](../../tables/layout_union.py#L730) | `LayoutUnion._merge_scripts(self, base_script_list, base_index_map)` |
| [LayoutUnion.finalize](../../tables/layout_union.py#L761) | `LayoutUnion.finalize(self)` |

<a id="module-39"></a>

## tables/maxp.py

[Source](../../tables/maxp.py)

| Source definition | Signature |
| --- | --- |
| [_program_bytes](../../tables/maxp.py#L12) | `_program_bytes(font, name)` |
| [_hint_axis_space](../../tables/maxp.py#L20) | `_hint_axis_space(font)` |
| [_same_hint_environment](../../tables/maxp.py#L31) | `_same_hint_environment(left, right)` |
| [_merge_hint_resources](../../tables/maxp.py#L52) | `_merge_hint_resources(merged, sources)` |
| [merge_maxp](../../tables/maxp.py#L69) | `merge_maxp(merged, main, bases, added=None)` |

<a id="module-40"></a>

## tables/metadata_recalc.py

[Source](../../tables/metadata_recalc.py)

| Source definition | Signature |
| --- | --- |
| [_attempt](../../tables/metadata_recalc.py#L12) | `_attempt(label, action)` |
| [_recalc_os2](../../tables/metadata_recalc.py#L21) | `_recalc_os2(font)` |
| [_recalc_bounds](../../tables/metadata_recalc.py#L42) | `_recalc_bounds(font)` |
| [recalc_after_merge](../../tables/metadata_recalc.py#L80) | `recalc_after_merge(font)` |

<a id="module-41"></a>

## tables/metrics.py

[Source](../../tables/metrics.py)

| Source definition | Signature |
| --- | --- |
| [merge_hmtx](../../tables/metrics.py#L6) | `merge_hmtx(merged, main, bases, added=None)` |
| [merge_vmtx](../../tables/metrics.py#L21) | `merge_vmtx(merged, main, bases, added=None)` |

<a id="module-42"></a>

## tables/name_table.py

[Source](../../tables/name_table.py)

| Source definition | Signature |
| --- | --- |
| [merge_name](../../tables/name_table.py#L6) | `merge_name(merged, main, bases, added=None)` |
| [complete_vf_name_table](../../tables/name_table.py#L12) | `complete_vf_name_table(font, platformID=3, platEncID=1, langID=1033)` |

<a id="module-43"></a>

## tables/os2.py

[Source](../../tables/os2.py)

| Source definition | Signature |
| --- | --- |
| [_merge_os2_fs_type](../../tables/os2.py#L9) | `_merge_os2_fs_type(values)` |
| [merge_os2](../../tables/os2.py#L24) | `merge_os2(merged, main, bases, added=None)` |

<a id="module-44"></a>

## tables/ot_merge.py

[Source](../../tables/ot_merge.py)

| Source definition | Signature |
| --- | --- |
| [_layout_tags](../../tables/ot_merge.py#L41) | `_layout_tags()` |
| [prune_base_layout](../../tables/ot_merge.py#L45) | `prune_base_layout(base_font, kept_glyphs)` |
| [merged_kept_glyphs](../../tables/ot_merge.py#L96) | `merged_kept_glyphs(base_font, kept_glyphs)` |
| [merge_base_layout](../../tables/ot_merge.py#L104) | `merge_base_layout(main_font, base_pruned, kept_glyphs)` |
| [_apply_gdef_extras](../../tables/ot_merge.py#L184) | `_apply_gdef_extras(font, main_gdef, var_union, mark_union, order_index)` |
| [_use_base_gdef](../../tables/ot_merge.py#L200) | `_use_base_gdef(font, base_gdef)` |
| [_merge_gdef](../../tables/ot_merge.py#L222) | `_merge_gdef(font, main_gdef, base_gdef, kept, var_union=None, mark_union=None)` |
| [_merge_gsub_gpos](../../tables/ot_merge.py#L274) | `_merge_gsub_gpos(font, tag, main_tbl, base_tbl, var_offset=0, mark_set_remap=())` |
| [_merge_script_list](../../tables/ot_merge.py#L380) | `_merge_script_list(main_tbl, base_script_list, feature_of_base, records)` |
| [_remap_lookup_glyph_names](../../tables/ot_merge.py#L419) | `_remap_lookup_glyph_names(font, lookup)` |
| [_remap_obj](../../tables/ot_merge.py#L460) | `_remap_obj(font, obj, remap, seen=None)` |
| [_collect_strings](../../tables/ot_merge.py#L507) | `_collect_strings(obj, names=None, seen=None)` |
| [_lookup_glyphs_in_font](../../tables/ot_merge.py#L543) | `_lookup_glyphs_in_font(font, lookup)` |
| [merge_ot_features](../../tables/ot_merge.py#L563) | `merge_ot_features(main_font, base_font, kept_glyphs)` |

<a id="module-45"></a>

## tables/otlayout.py

[Source](../../tables/otlayout.py)

| Source definition | Signature |
| --- | --- |
| [merge_gsub](../../tables/otlayout.py#L6) | `merge_gsub(merged, main, bases, added=None)` |
| [merge_gpos](../../tables/otlayout.py#L11) | `merge_gpos(merged, main, bases, added=None)` |
| [merge_gdef](../../tables/otlayout.py#L16) | `merge_gdef(merged, main, bases, added=None)` |
| [_merge_otl](../../tables/otlayout.py#L20) | `_merge_otl(merged, main, bases, tag)` |

<a id="module-46"></a>

## tables/post.py

[Source](../../tables/post.py)

| Source definition | Signature |
| --- | --- |
| [merge_post](../../tables/post.py#L7) | `merge_post(merged, main, bases, added=None)` |

<a id="module-47"></a>

## tables/varstore.py

[Source](../../tables/varstore.py)

| Source definition | Signature |
| --- | --- |
| [VarStoreUnion.__init__](../../tables/varstore.py#L24) | `VarStoreUnion.__init__(self)` |
| [VarStoreUnion.add](../../tables/varstore.py#L29) | `VarStoreUnion.add(self, var_store)` |
| [VarStoreUnion.build](../../tables/varstore.py#L58) | `VarStoreUnion.build(self)` |
| [VarStoreUnion.__bool__](../../tables/varstore.py#L81) | `VarStoreUnion.__bool__(self)` |

<a id="module-48"></a>

## tests/__init__.py

Repository only: `tests/__init__.py`.

| Source definition | Signature |
| --- | --- |
| No callable definitions; module setup or declarations. | |

<a id="module-49"></a>

## tests/cff2_fixture.py

Repository only: `tests/cff2_fixture.py`.

| Source definition | Signature |
| --- | --- |
| `_subset` | `_subset(src, out, unicodes, features='kern,liga,mark,mkmk')` |
| `make_cff2_pair` | `make_cff2_pair(src_path, out_dir=None)` |
| `cached_cff2_pair` | `cached_cff2_pair(src_path, out_dir=None)` |

<a id="module-50"></a>

## tests/generate_matrix.py

Repository only: `tests/generate_matrix.py`.

| Source definition | Signature |
| --- | --- |
| `L` | `L(rel)` |
| `LC` | `LC(role)` |
| `mg` | `mg(label, m, b, extra='', mem=None)` |

<a id="module-51"></a>

## tests/generate_samples.py

Repository only: `tests/generate_samples.py`.

| Source definition | Signature |
| --- | --- |
| `font` | `font(rel)` |
| `local` | `local(role)` |
| `s` | `s(font_path, sample_name)` |
| `ensure_output` | `ensure_output()` |
| `sample1_otf_plus_otf` | `sample1_otf_plus_otf()` |
| `sample2_ttf_plus_ttf` | `sample2_ttf_plus_ttf()` |
| `sample3_otf_plus_ttf_conversion` | `sample3_otf_plus_ttf_conversion()` |
| `sample4_variable_instantiate_and_merge` | `sample4_variable_instantiate_and_merge()` |
| `sample5_multilevel_merge` | `sample5_multilevel_merge()` |
| `sample6_high_level_api` | `sample6_high_level_api()` |
| `main` | `main()` |

<a id="module-52"></a>

## tests/local_fonts.example.py

Repository only: `tests/local_fonts.example.py`.

| Source definition | Signature |
| --- | --- |
| No callable definitions; module setup or declarations. | |

<a id="module-53"></a>

## tests/run_regressions.py

Repository only: `tests/run_regressions.py`.

| Source definition | Signature |
| --- | --- |
| `main` | `main()` |

<a id="module-54"></a>

## tests/subset_fixture.py

Repository only: `tests/subset_fixture.py`.

| Source definition | Signature |
| --- | --- |
| `make_subsets` | `make_subsets(src_path, n=3, out_dir=None, flavor='woff2')` |
| `cached_subsets` | `cached_subsets(src_path, n=3, flavor='woff2')` |
| `make_rich_vf` | `make_rich_vf(src_path, out_dir=None, mark_glyphs=40)` |
| `cached_rich_subsets` | `cached_rich_subsets(src_path, n=2, flavor='woff2')` |

<a id="module-55"></a>

## tests/test_axis_mapping.py

Repository only: `tests/test_axis_mapping.py`.

| Source definition | Signature |
| --- | --- |
| `_sample` | `_sample(lo=-1.0, hi=1.0, n=2001)` |
| `_max_err_1d` | `_max_err_1d(lower, peak, upper, mapping, terms)` |
| `test_piecewise_linear_basics` | `test_piecewise_linear_basics()` |
| `test_refine_identity` | `test_refine_identity()` |
| `test_refine_affine_range` | `test_refine_affine_range()` |
| `test_refine_avar` | `test_refine_avar()` |
| `test_refine_range_and_avar` | `test_refine_range_and_avar()` |
| `test_refine_default_mismatch` | `test_refine_default_mismatch()` |
| `test_refine_boundary_truncation` | `test_refine_boundary_truncation()` |
| `test_refine_multi_axis` | `test_refine_multi_axis()` |
| `test_real_avar_roundtrip` | `test_real_avar_roundtrip()` |
| `test_random_stress` | `test_random_stress()` |
| `test_collapsing_flat_detection` | `test_collapsing_flat_detection()` |
| `test_refine_cross_zero` | `test_refine_cross_zero()` |
| `_make_var_store` | `_make_var_store(regions, columns, rows, num_shorts=0)` |
| `_store_supports` | `_store_supports(var_store, tags)` |
| `_store_response` | `_store_response(var_store, tags, outer, inner, loc)` |
| `_source_response` | `_source_response(src_store, mapping, outer, inner, x)` |
| `test_var_store_reparametrize` | `test_var_store_reparametrize()` |
| `main` | `main()` |

<a id="module-56"></a>

## tests/test_cff2_compose.py

Repository only: `tests/test_cff2_compose.py`.

| Source definition | Signature |
| --- | --- |
| `_open` | `_open(path=None)` |
| `_merged_mapping` | `_merged_mapping(font, wide_wght=100.0, hi_opsz=40.0)` |
| `_draw_diff` | `_draw_diff(pen_a, pen_b)` |
| `test_cff2_identity` | `test_cff2_identity()` |
| `test_cff2_vsindex_offset` | `test_cff2_vsindex_offset()` |
| `test_cff2_reparametrize_outlines` | `test_cff2_reparametrize_outlines()` |
| `test_cff2_cross_design_space_merge` | `test_cff2_cross_design_space_merge()` |
| `main` | `main()` |

<a id="module-57"></a>

## tests/test_cmap_regressions.py

Repository only: `tests/test_cmap_regressions.py`.

| Source definition | Signature |
| --- | --- |
| `_font` | `_font(cmap, widths=None, components=None, cff=False)` |
| `_reload` | `_reload(font)` |
| `_uvs` | `_uvs(font, entries)` |
| `_merge` | `_merge(main, base, use_ttx=False)` |
| `test_partial_conflict_and_alias` | `test_partial_conflict_and_alias()` |
| `test_unicode_subtable_sync` | `test_unicode_subtable_sync()` |
| `test_uvs_default_and_nondefault` | `test_uvs_default_and_nondefault()` |
| `test_rename_component_and_uvs` | `test_rename_component_and_uvs()` |
| `test_component_source_identity` | `test_component_source_identity()` |
| `_cid_font` | `_cid_font()` |
| `test_format_ranges_and_same_encoding` | `test_format_ranges_and_same_encoding()` |
| `test_uvs_only_and_new_subtable` | `test_uvs_only_and_new_subtable()` |
| `test_lowlevel_component_closure` | `test_lowlevel_component_closure()` |
| `_variable_font` | `_variable_font(cmap)` |
| `test_variable_alias_maps` | `test_variable_alias_maps()` |
| `test_post3_partial_identity` | `test_post3_partial_identity()` |
| `test_format0_large_glyph_ids` | `test_format0_large_glyph_ids()` |
| `test_ttx_existing_names_linear_scan` | `test_ttx_existing_names_linear_scan()` |
| `test_chunked_component_source_reuse` | `test_chunked_component_source_reuse()` |
| `test_public_alias_contract` | `test_public_alias_contract()` |
| `test_sequential_ttx_and_xml_headers` | `test_sequential_ttx_and_xml_headers()` |
| `test_highlevel_cid_and_variable_alias` | `test_highlevel_cid_and_variable_alias()` |
| `test_highlevel_cid_unique_uvs_renames` | `test_highlevel_cid_unique_uvs_renames()` |
| `test_cid_merge_roundtrip` | `test_cid_merge_roundtrip()` |
| `test_cid_shift_cmap` | `test_cid_shift_cmap()` |
| `test_nonunicode_format0_large_glyph_ids` | `test_nonunicode_format0_large_glyph_ids()` |
| `test_nonunicode_format0_byte_boundary_stays_valid` | `test_nonunicode_format0_byte_boundary_stays_valid()` |
| `main` | `main()` |

<a id="module-58"></a>

## tests/test_engine_regressions.py

Repository only: `tests/test_engine_regressions.py`.

| Source definition | Signature |
| --- | --- |
| `_bind_harfbuzz` | `_bind_harfbuzz()` |
| `_harfbuzz` | `_harfbuzz()` |
| `_hb_version` | `_hb_version(lib)` |
| `_hb_shape` | `_hb_shape(lib, font_bytes, codepoints, script=None, features=None)` |
| `_shape_names` | `_shape_names(lib, font_bytes, codepoints, script=None, features=None)` |
| `_shape_positions` | `_shape_positions(lib, font_bytes, codepoints, script=None, features=None)` |
| `_bind_freetype` | `_bind_freetype()` |
| `_freetype` | `_freetype()` |
| `_ft_load_all` | `_ft_load_all(lib, font_bytes, glyph_count)` |
| `_ft_char_index` | `_ft_char_index(lib, font_bytes, codepoint)` |
| `_build_font` | `_build_font(glyphs, cmap, fea='', hint_globals=False, glyph_programs=None)` |
| `_font_bytes` | `_font_bytes(font)` |
| `_merge` | `_merge(main, base)` |
| `_roundtrip` | `_roundtrip(font)` |
| `_skip` | `_skip(test_name, lib_name, error)` |
| `test_engine_bindings_smoke` | `test_engine_bindings_smoke()` |
| `test_gsub_context_nested_lookup` | `test_gsub_context_nested_lookup()` |
| `test_gpos_kern_values_preserved` | `test_gpos_kern_values_preserved()` |
| `test_cross_script_same_tag_isolation` | `test_cross_script_same_tag_isolation()` |
| `test_freetype_hint_bundle_loads` | `test_freetype_hint_bundle_loads()` |
| `test_freetype_stripped_font_loads` | `test_freetype_stripped_font_loads()` |
| `main` | `main()` |

<a id="module-59"></a>

## tests/test_invariants.py

Repository only: `tests/test_invariants.py`.

| Source definition | Signature |
| --- | --- |
| `_font` | `_font(cmap=None)` |
| `_fails` | `_fails(fn, text)` |
| `test_exact_union_and_main_priority` | `test_exact_union_and_main_priority()` |
| `test_unicode_subtable_and_metric_guards` | `test_unicode_subtable_and_metric_guards()` |
| `test_nested_lookup_guard` | `test_nested_lookup_guard()` |
| `test_glyph_count_guard` | `test_glyph_count_guard()` |
| `test_high_level_partial_conflicts` | `test_high_level_partial_conflicts()` |
| `test_no_added_glyph_uvs_exit` | `test_no_added_glyph_uvs_exit()` |
| `test_chunked_ttx_exit` | `test_chunked_ttx_exit()` |
| `test_injection_failure_is_not_partial_success` | `test_injection_failure_is_not_partial_success()` |
| `test_upm_vorg_override_not_double_scaled` | `test_upm_vorg_override_not_double_scaled()` |
| `test_invalid_default_uvs_is_input_error` | `test_invalid_default_uvs_is_input_error()` |
| `test_private_chunk_rejects_unnormalized_source` | `test_private_chunk_rejects_unnormalized_source()` |
| `test_decomposed_comparison_checks_real_component_geometry` | `test_decomposed_comparison_checks_real_component_geometry()` |
| `main` | `main()` |

<a id="module-60"></a>

## tests/test_layout_regressions.py

Repository only: `tests/test_layout_regressions.py`.

| Source definition | Signature |
| --- | --- |
| `_font` | `_font(fea='', extra=())` |
| `_reload` | `_reload(font)` |
| `_coverage` | `_coverage(glyphs)` |
| `_record` | `_record(tag, target)` |
| `_context` | `_context(tag, fmt, target, chain=False)` |
| `_refs` | `_refs(obj, seen=None)` |
| `_context_font` | `_context_font(tag, fmt, extension=False, chain=False)` |
| `_main` | `_main(tag)` |
| `test_context_lookup_mapping` | `test_context_lookup_mapping()` |
| `test_same_source_context_mapping` | `test_same_source_context_mapping()` |
| `_lang_features` | `_lang_features(table, script_tag, lang_tag=None)` |
| `_substitutions` | `_substitutions(table, features)` |
| `test_langsys_isolation_and_union` | `test_langsys_isolation_and_union()` |
| `test_mark_sets_gid_order` | `test_mark_sets_gid_order()` |
| `_merge_fixture` | `_merge_fixture(source, donor, same_source)` |
| `test_nested_closure_and_dropped_rules` | `test_nested_closure_and_dropped_rules()` |
| `_records` | `_records(obj, seen=None)` |
| `test_partially_dropped_context_rules` | `test_partially_dropped_context_rules()` |
| `_required` | `_required(font, tag)` |
| `test_primary_params_and_required_features` | `test_primary_params_and_required_features()` |
| `_feature_variations` | `_feature_variations(font, feature_tag, alternate, intervals=((0.25, 1.0),))` |
| `_effective_features` | `_effective_features(table, script, variant=False)` |
| `test_feature_variations_local_union` | `test_feature_variations_local_union()` |
| `test_feature_variations_strict_conditions` | `test_feature_variations_strict_conditions()` |
| `_pair_adjustment` | `_pair_adjustment(table, features, first, second)` |
| `test_kern_primary_values_not_unified` | `test_kern_primary_values_not_unified()` |
| `test_coverage_parallel_arrays` | `test_coverage_parallel_arrays()` |
| `test_nonconstant_lookup_map_and_shared_records` | `test_nonconstant_lookup_map_and_shared_records()` |
| `test_required_feature_variations_and_adoption` | `test_required_feature_variations_and_adoption()` |
| `test_parameter_only_feature_and_required_conflict` | `test_parameter_only_feature_and_required_conflict()` |
| `main` | `main()` |

<a id="module-61"></a>

## tests/test_merger.py

Repository only: `tests/test_merger.py`.

| Source definition | Signature |
| --- | --- |
| `_open` | `_open(role)` |
| `_local` | `_local(role)` |
| `test_detect` | `test_detect()` |
| `test_conflict` | `test_conflict()` |
| `test_naming` | `test_naming()` |
| `test_merge_otf_otf` | `test_merge_otf_otf()` |
| `test_merge_ttf_ttf` | `test_merge_ttf_ttf()` |
| `test_table_registry` | `test_table_registry()` |
| `test_high_level_api` | `test_high_level_api()` |
| `_open_vf` | `_open_vf()` |
| `_vf_subsets` | `_vf_subsets(n=2)` |
| `test_save_guard` | `test_save_guard()` |
| `test_conflict_auto_names` | `test_conflict_auto_names()` |
| `test_rename_glyphs` | `test_rename_glyphs()` |
| `test_variable_to_static_fidelity` | `test_variable_to_static_fidelity()` |
| `test_generic_feature_union` | `test_generic_feature_union()` |
| `test_no_dangling_layout_refs` | `test_no_dangling_layout_refs()` |
| `test_variable_to_static_cff2` | `test_variable_to_static_cff2()` |
| `test_generic_merge_preserves_mark_sets_and_fv` | `test_generic_merge_preserves_mark_sets_and_fv()` |
| `test_generic_merge_transfers_variation` | `test_generic_merge_transfers_variation()` |
| `test_cross_design_space_composition` | `test_cross_design_space_composition()` |
| `test_composition_fallback` | `test_composition_fallback()` |
| `test_compose_main_var_store_axes` | `test_compose_main_var_store_axes()` |
| `_count_var_devices` | `_count_var_devices(font, min_outer=0)` |
| `test_compose_base_layout_variation` | `test_compose_base_layout_variation()` |
| `test_real_var_store_reparametrize` | `test_real_var_store_reparametrize()` |
| `main` | `main()` |

<a id="module-62"></a>

## tests/test_metadata_regressions.py

Repository only: `tests/test_metadata_regressions.py`.

| Source definition | Signature |
| --- | --- |
| `_font` | `_font(names, cmap=None, widths=None)` |
| `_joined` | `_joined(main, base, names)` |
| `_reload` | `_reload(font)` |
| `test_os2_alias_is_not_missing_attribute` | `test_os2_alias_is_not_missing_attribute()` |
| `test_os2_ranges_follow_actual_cmap` | `test_os2_ranges_follow_actual_cmap()` |
| `test_metrics_only_contain_surviving_glyphs` | `test_metrics_only_contain_surviving_glyphs()` |
| `test_maxp_kept_programs_receive_source_resources` | `test_maxp_kept_programs_receive_source_resources()` |
| `_set_program` | `_set_program(font, name, bytecode)` |
| `_bundle` | `_bundle(font, function=0)` |
| `_bytes` | `_bytes(font, name)` |
| `test_finalizer_uses_official_average_and_context` | `test_finalizer_uses_official_average_and_context()` |
| `test_finalizer_bmp_clamp_and_clipping_bounds` | `test_finalizer_bmp_clamp_and_clipping_bounds()` |
| `test_panose_stays_main_and_does_not_alias` | `test_panose_stays_main_and_does_not_alias()` |
| `test_os2_version_zero_not_upgraded_without_fields` | `test_os2_version_zero_not_upgraded_without_fields()` |
| `test_finalizer_does_not_replay_variation_or_layout` | `test_finalizer_does_not_replay_variation_or_layout()` |
| `test_hinting_adopts_complete_bundle_and_resources` | `test_hinting_adopts_complete_bundle_and_resources()` |
| `test_hinting_compatible_programs_take_resource_maxima` | `test_hinting_compatible_programs_take_resource_maxima()` |
| `test_hinting_incompatible_bundle_strips_only_new_programs` | `test_hinting_incompatible_bundle_strips_only_new_programs()` |
| `test_hinting_main_prep_alone_blocks_base_adoption` | `test_hinting_main_prep_alone_blocks_base_adoption()` |
| `test_hinting_multilevel_preserves_previous_interpreter` | `test_hinting_multilevel_preserves_previous_interpreter()` |
| `test_hinting_no_imported_programs_does_not_change_resources` | `test_hinting_no_imported_programs_does_not_change_resources()` |
| `test_hinting_axis_mismatch_is_conservatively_stripped` | `test_hinting_axis_mismatch_is_conservatively_stripped()` |
| `_kern` | `_kern(font, pairs, coverage=1)` |
| `test_table_policy_drops_stale_tables_and_unions_safe_kern` | `test_table_policy_drops_stale_tables_and_unions_safe_kern()` |
| `test_kern_unknown_semantics_are_not_imported` | `test_kern_unknown_semantics_are_not_imported()` |
| `_cff_font` | `_cff_font(names, cmap, vertical=True)` |
| `_vorg` | `_vorg(font, default, records)` |
| `_joined_cff` | `_joined_cff(main, base)` |
| `test_vorg_unions_per_glyph_not_source_default` | `test_vorg_unions_per_glyph_not_source_default()` |
| `test_base_only_vorg_restores_main_metric_origins` | `test_base_only_vorg_restores_main_metric_origins()` |
| `test_vorg_without_main_origin_evidence_is_not_adopted` | `test_vorg_without_main_origin_evidence_is_not_adopted()` |
| `test_hinting_unknown_cvar_is_stripped_not_reinterpreted` | `test_hinting_unknown_cvar_is_stripped_not_reinterpreted()` |
| `test_hinting_malformed_environment_falls_back_to_strip` | `test_hinting_malformed_environment_falls_back_to_strip()` |
| `test_vertical_metrics_do_not_add_dropped_glyphs` | `test_vertical_metrics_do_not_add_dropped_glyphs()` |
| `main` | `main()` |

<a id="module-63"></a>

## tests/test_naming_regressions.py

Repository only: `tests/test_naming_regressions.py`.

| Source definition | Signature |
| --- | --- |
| `_font` | `_font(family='Neutral Family', style='Regular')` |
| `_set` | `_set(font, name_id, text, lang=1033, platform=3, encoding=1)` |
| `_get` | `_get(font, name_id, lang=1033, platform=3, encoding=1)` |
| `_snapshot` | `_snapshot(font)` |
| `_roundtrip` | `_roundtrip(font)` |
| `_localized` | `_localized()` |
| `test_family_selection_is_deterministic` | `test_family_selection_is_deterministic()` |
| `test_copyrights_preserve_languages_and_list_api` | `test_copyrights_preserve_languages_and_list_api()` |
| `test_plain_inputs_preserve_localized_copyrights` | `test_plain_inputs_preserve_localized_copyrights()` |
| `test_typographic_and_ribbi_names_remain_distinct` | `test_typographic_and_ribbi_names_remain_distinct()` |
| `test_postscript_names_are_legal_and_collision_resistant` | `test_postscript_names_are_legal_and_collision_resistant()` |
| `test_non_latin_without_mac_roman_is_serializable` | `test_non_latin_without_mac_roman_is_serializable()` |
| `test_language_specific_mac_encoding_and_extra_languages` | `test_language_specific_mac_encoding_and_extra_languages()` |
| `test_naming_is_idempotent_and_preserves_provenance` | `test_naming_is_idempotent_and_preserves_provenance()` |
| `test_variable_references_and_instance_ps_names_are_untouched` | `test_variable_references_and_instance_ps_names_are_untouched()` |
| `test_base_only_copyright_language_and_no_false_translation` | `test_base_only_copyright_language_and_no_false_translation()` |
| `test_non_english_styles_have_distinct_ps_names` | `test_non_english_styles_have_distinct_ps_names()` |
| `test_cff_postscript_identity_matches_name_table` | `test_cff_postscript_identity_matches_name_table()` |
| `main` | `main()` |

<a id="module-64"></a>

## tests/test_subset_merge.py

Repository only: `tests/test_subset_merge.py`.

| Source definition | Signature |
| --- | --- |
| `_vf` | `_vf()` |
| `_static` | `_static()` |
| `_subsets` | `_subsets(n=3)` |
| `_features` | `_features(font, tag)` |
| `test_same_source_detection` | `test_same_source_detection()` |
| `test_merge_subsets_roundtrip` | `test_merge_subsets_roundtrip()` |
| `test_merge_subsets_save_and_reload` | `test_merge_subsets_save_and_reload()` |
| `test_merge_subsets_verify` | `test_merge_subsets_verify()` |
| `test_merge_subsets_cff2` | `test_merge_subsets_cff2()` |
| `test_merge_subsets_rejects_foreign` | `test_merge_subsets_rejects_foreign()` |
| `test_glyph_map_covers_sources` | `test_glyph_map_covers_sources()` |
| `test_subset_merge_preserves_mark_sets_and_fv` | `test_subset_merge_preserves_mark_sets_and_fv()` |
| `main` | `main()` |

<a id="module-65"></a>

## tests/test_subset_regressions.py

Repository only: `tests/test_subset_regressions.py`.

| Source definition | Signature |
| --- | --- |
| `test_composite_closure_and_roundtrip` | `test_composite_closure_and_roundtrip()` |
| `test_layout_output_closure` | `test_layout_output_closure()` |
| `test_encoded_empty_glyph_preserved` | `test_encoded_empty_glyph_preserved()` |
| `test_unsupported_tables_are_explicitly_dropped` | `test_unsupported_tables_are_explicitly_dropped()` |
| `test_missing_requests_keep_legacy_behavior_with_warning` | `test_missing_requests_keep_legacy_behavior_with_warning()` |
| `main` | `main()` |

<a id="module-66"></a>

## tests/test_transform_regressions.py

Repository only: `tests/test_transform_regressions.py`.

| Source definition | Signature |
| --- | --- |
| `_rect` | `_rect(pen, top)` |
| `_font` | `_font(cff=False, vorg=False, variable=False, hinted=False)` |
| `_cff2_font` | `_cff2_font()` |
| `_bounds` | `_bounds(font, name, location=None)` |
| `_reload` | `_reload(font)` |
| `_capture` | `_capture(call, *args)` |
| `test_vertical_positions_and_lengths` | `test_vertical_positions_and_lengths()` |
| `test_negative_offset_win_descent` | `test_negative_offset_win_descent()` |
| `test_vertical_origin_without_vorg` | `test_vertical_origin_without_vorg()` |
| `test_vertical_origin_with_vorg` | `test_vertical_origin_with_vorg()` |
| `test_identity_preserves_hinting` | `test_identity_preserves_hinting()` |
| `test_nonidentity_removes_hinting_consistently` | `test_nonidentity_removes_hinting_consistently()` |
| `test_composite_transform_preserves_topology` | `test_composite_transform_preserves_topology()` |
| `test_gvar_transform_preserves_deltas` | `test_gvar_transform_preserves_deltas()` |
| `test_vdmx_removed_with_warning` | `test_vdmx_removed_with_warning()` |
| `test_scale_upem_already_scales_vertical_metrics` | `test_scale_upem_already_scales_vertical_metrics()` |
| `test_cff_to_glyf_saves_true_type_maxp` | `test_cff_to_glyf_saves_true_type_maxp()` |
| `test_cff_to_glyf_retains_explicit_origin_in_tsb` | `test_cff_to_glyf_retains_explicit_origin_in_tsb()` |
| `test_cff_width_tracks_scaled_advance` | `test_cff_width_tracks_scaled_advance()` |
| `test_cff2_blend_survives_transform` | `test_cff2_blend_survives_transform()` |
| `test_conversion_hinting_policy_is_explicit` | `test_conversion_hinting_policy_is_explicit()` |
| `test_cross_outline_variable_conversion_is_rejected` | `test_cross_outline_variable_conversion_is_rejected()` |
| `test_composite_gvar_and_point_matching_survive` | `test_composite_gvar_and_point_matching_survive()` |
| `main` | `main()` |

<a id="module-67"></a>

## utils/__init__.py

[Source](../../utils/__init__.py)

| Source definition | Signature |
| --- | --- |
| No callable definitions; module setup or declarations. | |

<a id="module-68"></a>

## utils/detect.py

[Source](../../utils/detect.py)

| Source definition | Signature |
| --- | --- |
| [is_auto_glyph_name](../../utils/detect.py#L13) | `is_auto_glyph_name(name)` |
| [is_cff](../../utils/detect.py#L18) | `is_cff(font)` |
| [is_ttf](../../utils/detect.py#L22) | `is_ttf(font)` |
| [is_variable](../../utils/detect.py#L26) | `is_variable(font)` |
| [type_label](../../utils/detect.py#L30) | `type_label(font)` |
| [all_codepoints](../../utils/detect.py#L36) | `all_codepoints(font)` |
| [glyph_to_codepoints](../../utils/detect.py#L44) | `glyph_to_codepoints(font)` |
| [_LocalizedText.__new__](../../utils/detect.py#L56) | `_LocalizedText.__new__(cls, value, records=())` |
| [_name_language](../../utils/detect.py#L62) | `_name_language(key)` |
| [_name_priority](../../utils/detect.py#L72) | `_name_priority(record)` |
| [_localized_records](../../utils/detect.py#L81) | `_localized_records(font, name_ids)` |
| [get_copyrights](../../utils/detect.py#L98) | `get_copyrights(*fonts)` |
| [get_family](../../utils/detect.py#L108) | `get_family(font)` |
| [axis_space](../../utils/detect.py#L114) | `axis_space(font)` |
| [is_same_source](../../utils/detect.py#L122) | `is_same_source(fonts)` |

<a id="module-69"></a>

## utils/save.py

[Source](../../utils/save.py)

| Source definition | Signature |
| --- | --- |
| [read_magic](../../utils/save.py#L15) | `read_magic(path)` |
| [assert_sfnt](../../utils/save.py#L21) | `assert_sfnt(path)` |
| [save_font](../../utils/save.py#L31) | `save_font(font, path, flavor=None, recalcTimestamp=None)` |
| [default_flavor_for](../../utils/save.py#L55) | `default_flavor_for(path)` |

The index is generated from source syntax. `*args` and `**kwargs` do not imply arbitrary keyword support; use the detailed API page for accepted values and forwarded keywords.
