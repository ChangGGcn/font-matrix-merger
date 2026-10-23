# -*- coding: utf-8 -*-
"""布局并集回归：现场构造中性最小字体，校验索引、隔离和来源优先。"""
import copy
from io import BytesIO
import os
import sys
import traceback

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables as ot

_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
sys.path.insert(0, _project_dir)

from FontMerger.tables.layout_union import LayoutUnion, resort_layout
from FontMerger.tables.ot_merge import merge_base_layout


_GLYPHS = ['.notdef', 'a', 'b', 'c', 'a.alt', 'b.alt', 'c.alt']


def _font(fea='', extra=()):
    """构造不依赖磁盘字体的完整最小 TTF。"""
    glyphs = _GLYPHS + list(extra)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap({97: 'a', 98: 'b', 99: 'c'})
    fb.setupGlyf({g: TTGlyphPen(None).glyph() for g in glyphs})
    fb.setupHorizontalMetrics({g: (500, 0) for g in glyphs})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({'familyName': 'NeutralFixture',
                       'styleName': 'Regular', 'psName': 'NeutralFixture'})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200,
                usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    fb.setupMaxp()
    if fea:
        addOpenTypeFeaturesFromString(fb.font, fea)
    return fb.font


def _reload(font):
    """内存保存重载，并让所有布局对象解码后再断言。"""
    stream = BytesIO()
    font.save(stream)
    stream.seek(0)
    result = TTFont(stream)
    for tag in ('GSUB', 'GPOS', 'GDEF'):
        if tag in result:
            result[tag].ensureDecompiled()
    return result


def _coverage(glyphs):
    cov = ot.Coverage()
    cov.glyphs = list(glyphs)
    return cov


def _record(tag, target):
    rec = ot.SubstLookupRecord() if tag == 'GSUB' else ot.PosLookupRecord()
    rec.SequenceIndex = 0
    rec.LookupListIndex = target
    return rec


def _context(tag, fmt, target, chain=False):
    """按规范构造 Context/ChainContext 三种格式；动作来源于 feaLib。"""
    subst = tag == 'GSUB'
    kind = 'Sub' if subst else 'Pos'
    prefix = 'Chain' if chain else ''
    st = getattr(ot, prefix + 'Context' + ('Subst' if subst else 'Pos'))()
    st.Format = fmt
    rec_attr = 'SubstLookupRecord' if subst else 'PosLookupRecord'
    count_attr = 'SubstCount' if subst else 'PosCount'
    if fmt == 3:
        if chain:
            st.BacktrackCoverage = []
            st.BacktrackGlyphCount = 0
            st.InputCoverage = [_coverage(['a']), _coverage(['b'])]
            st.InputGlyphCount = 2
            st.LookAheadCoverage = []
            st.LookAheadGlyphCount = 0
        else:
            st.Coverage = [_coverage(['a']), _coverage(['b'])]
            st.GlyphCount = 2
        owner = st
    else:
        st.Coverage = _coverage(['a'])
        rule_name = prefix + kind + ('Rule' if fmt == 1 else 'ClassRule')
        set_name = prefix + kind + ('RuleSet' if fmt == 1 else 'ClassSet')
        rule = getattr(ot, rule_name)()
        rule.Input = ['b'] if fmt == 1 else [2]
        if chain:
            rule.Backtrack = []
            rule.BacktrackGlyphCount = 0
            rule.InputGlyphCount = 2
            rule.LookAhead = []
            rule.LookAheadGlyphCount = 0
        else:
            rule.GlyphCount = 2
        rule_set = getattr(ot, set_name)()
        setattr(rule_set, rule_name, [rule])
        setattr(rule_set, rule_name + 'Count', 1)
        sets = [rule_set]
        if fmt == 2:
            cd = ot.ClassDef()
            cd.classDefs = {'a': 1, 'b': 2}
            if chain:
                st.InputClassDef = cd
                st.BacktrackClassDef = ot.ClassDef()
                st.BacktrackClassDef.classDefs = {}
                st.LookAheadClassDef = ot.ClassDef()
                st.LookAheadClassDef.classDefs = {}
            else:
                st.ClassDef = cd
            sets = [None, rule_set, None]
        setattr(st, set_name, sets)
        setattr(st, set_name + 'Count', len(sets))
        owner = rule
    setattr(owner, rec_attr, [_record(tag, target)])
    setattr(owner, count_attr, 1)
    return st


def _refs(obj, seen=None):
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return []
    seen.add(id(obj))
    if isinstance(obj, (ot.SubstLookupRecord, ot.PosLookupRecord)):
        return [obj.LookupListIndex]
    if isinstance(obj, dict):
        values = obj.values()
    elif isinstance(obj, (list, tuple)):
        values = obj
    elif hasattr(obj, '__dict__'):
        values = [v for k, v in vars(obj).items() if not k.startswith('_')]
    else:
        return []
    return [i for value in values for i in _refs(value, seen)]


def _context_font(tag, fmt, extension=False, chain=False):
    if tag == 'GSUB':
        body = ('lookup DROP {sub missing by missing.alt;} DROP; '
                'lookup INNER {sub a by a.alt;} INNER; '
                "feature calt {lookup DROP; sub a' lookup INNER b;} calt;")
    else:
        body = ('lookup DROP {pos missing -19;} DROP; '
                'lookup INNER {pos a -23;} INNER; '
                "feature kern {lookup DROP; pos a' lookup INNER b;} kern;")
    font = _font(body, ['missing', 'missing.alt'])
    root = font[tag].table.LookupList.Lookup[-1]
    root.SubTable = [_context(tag, fmt, 1, chain)]
    root.LookupType = (6 if chain else 5) if tag == 'GSUB' else (8 if chain else 7)
    if extension:
        wrapper = ot.ExtensionSubst() if tag == 'GSUB' else ot.ExtensionPos()
        wrapper.Format = 1
        wrapper.ExtensionLookupType = root.LookupType
        wrapper.ExtSubTable = root.SubTable[0]
        root.SubTable = [wrapper]
        root.LookupType = 7 if tag == 'GSUB' else 9
    root.SubTableCount = 1
    return font


def _main(tag):
    fea = ('feature salt {sub c by c.alt;} salt;' if tag == 'GSUB'
           else 'feature dist {pos c 17;} dist;')
    return _font(fea)


def test_context_lookup_mapping():
    cases = 0
    for tag in ('GSUB', 'GPOS'):
        for fmt in (1, 2, 3):
            for chain in (False, True):
                for extension in (False, True):
                    main = _main(tag)
                    base = _context_font(tag, fmt, extension, chain)
                    merge_base_layout(main, base, main.getGlyphOrder())
                    result = _reload(main)
                    lookups = result[tag].table.LookupList.Lookup
                    assert len(lookups) == 3, (tag, fmt, len(lookups))
                    assert _refs(lookups[-1]) == [1], (tag, fmt, _refs(lookups))
                    assert _refs(base[tag].table.LookupList.Lookup[-1]) == [1]
                    cases += 1
    print('  上下文筛选与闭包：%d 组保存重载，内部索引均为 1' % cases)


def test_same_source_context_mapping():
    cases = 0
    for tag in ('GSUB', 'GPOS'):
        for fmt in (1, 2, 3):
            for chain in (False, True):
                for extension in (False, True):
                    main = _main(tag)
                    base = _context_font(tag, fmt, extension, chain)
                    union = LayoutUnion(tag)
                    union.add_from(main[tag].table, {})
                    union.add_from(base[tag].table, {})
                    main[tag].table = union.finalize()
                    # 同源并集保留全部字形，无失效的 DROP。
                    complete = _font(extra=['missing', 'missing.alt'])
                    complete[tag] = main[tag]
                    result = _reload(complete)
                    lookups = result[tag].table.LookupList.Lookup
                    assert len(lookups) == 4
                    assert _refs(lookups[-1]) == [2], (tag, fmt, _refs(lookups))
                    cases += 1
    print('  同源上下文重定位：%d 组保存重载，内部索引均为 2' % cases)


def _lang_features(table, script_tag, lang_tag=None):
    script = next(sr.Script for sr in table.ScriptList.ScriptRecord
                  if sr.ScriptTag == script_tag)
    lang = (script.DefaultLangSys if lang_tag is None else
            next(lr.LangSys for lr in script.LangSysRecord
                 if lr.LangSysTag == lang_tag))
    return [table.FeatureList.FeatureRecord[i] for i in lang.FeatureIndex]


def _substitutions(table, features):
    return [dict(table.LookupList.Lookup[i].SubTable[0].mapping)
            for fr in features for i in fr.Feature.LookupListIndex]


def test_langsys_isolation_and_union():
    source = _font('languagesystem latn dflt; languagesystem cyrl dflt; '
                   'feature liga {script latn; sub a by a.alt; '
                   'script cyrl; sub b by b.alt;} liga;')
    donor = _font('languagesystem latn dflt; '
                  'feature liga {sub c by c.alt;} liga;')
    for same_source in (False, True):
        result = copy.deepcopy(source)
        if same_source:
            union = LayoutUnion('GSUB')
            union.add_from(source['GSUB'].table, {})
            union.add_from(donor['GSUB'].table, {})
            result['GSUB'].table = union.finalize()
        else:
            merge_base_layout(result, donor, result.getGlyphOrder())
        table = _reload(result)['GSUB'].table
        latn = _lang_features(table, 'latn')
        cyrl = _lang_features(table, 'cyrl')
        assert len(latn) == len(cyrl) == 1
        assert _substitutions(table, latn) == [{'a': 'a.alt'}, {'c': 'c.alt'}]
        assert _substitutions(table, cyrl) == [{'b': 'b.alt'}]
    print('  同 LangSys 并集 2 lookup，跨脚本保持 1 lookup：2 路通过')


def test_mark_sets_gid_order():
    font = _font('markClass b <anchor 0 0> @MARK; '
                 'lookup L {lookupflag UseMarkFilteringSet @MARK; '
                 'pos a 11;} L; feature dist {lookup L;} dist;')
    coverage = font['GDEF'].table.MarkGlyphSetsDef.Coverage[0]
    coverage.glyphs = ['b', 'a']
    resort_layout(font)
    assert coverage.glyphs == ['a', 'b']
    result = _reload(font)
    assert result['GDEF'].table.MarkGlyphSetsDef.Coverage[0].glyphs == ['a', 'b']
    print('  MarkGlyphSets 按 GID 重排：2 个字形保存重载一致')


def _merge_fixture(source, donor, same_source):
    result = copy.deepcopy(source)
    tags = [tag for tag in ('GSUB', 'GPOS') if tag in donor]
    if same_source:
        for tag in tags:
            union = LayoutUnion(tag)
            if tag in source:
                union.add_from(source[tag].table, {})
            union.add_from(donor[tag].table, {})
            result[tag] = newTable(tag)
            result[tag].table = union.finalize()
    else:
        merge_base_layout(result, donor, result.getGlyphOrder())
    return _reload(result)


def test_nested_closure_and_dropped_rules():
    cases = 0
    for tag in ('GSUB', 'GPOS'):
        for fmt in (1, 2, 3):
            for chain in (False, True):
                for extension in (False, True):
                    main = _main(tag)
                    base = _context_font(tag, fmt, extension, chain)
                    table = base[tag].table
                    # 新增外层仅引用上下文，INNER 没有直接 feature 引用。
                    outer = copy.deepcopy(table.LookupList.Lookup[-1])
                    for record in _records(outer):
                        record.LookupListIndex = 2
                    table.LookupList.Lookup.append(outer)
                    table.FeatureList.FeatureRecord[0].Feature.LookupListIndex = [3]
                    result = _merge_fixture(main, base, False)
                    lookups = result[tag].table.LookupList.Lookup
                    assert len(lookups) == 4
                    assert _refs(lookups[-1]) == [2]
                    assert _refs(lookups[-2]) == [1]
                    # INNER 转为引用缺字形，失效需沿三层闭包传播，不留新 ignore。
                    table.LookupList.Lookup[1] = copy.deepcopy(
                        table.LookupList.Lookup[0])
                    result = _merge_fixture(main, base, False)
                    assert len(result[tag].table.LookupList.Lookup) == 1
                    cases += 1
    print('  多层闭包及失效传播：%d 组，保留 4/回退 1 lookup' % cases)


def _records(obj, seen=None):
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return []
    seen.add(id(obj))
    if isinstance(obj, (ot.SubstLookupRecord, ot.PosLookupRecord)):
        return [obj]
    if isinstance(obj, dict):
        values = obj.values()
    elif isinstance(obj, (list, tuple)):
        values = obj
    elif hasattr(obj, '__dict__'):
        values = [v for k, v in vars(obj).items() if not k.startswith('_')]
    else:
        return []
    return [rec for value in values for rec in _records(value, seen)]


def test_partially_dropped_context_rules():
    for tag in ('GSUB', 'GPOS'):
        for fmt in (1, 2, 3):
            for chain in (False, True):
                base = _context_font(tag, fmt, False, chain)
                table = base[tag].table
                root = table.LookupList.Lookup[-1]
                valid_st = root.SubTable[0]
                invalid = copy.deepcopy(valid_st)
                for rec in _records(invalid):
                    rec.LookupListIndex = 0
                # 两条规则共享同一 Coverage 槽位，原有 ignore 规则必须保留。
                if fmt == 3:
                    ignore = copy.deepcopy(valid_st)
                    rec_attr = 'SubstLookupRecord' if tag == 'GSUB' else 'PosLookupRecord'
                    setattr(ignore, rec_attr, [])
                    setattr(ignore, 'SubstCount' if tag == 'GSUB' else 'PosCount', 0)
                    root.SubTable = [invalid, ignore, valid_st]
                else:
                    prefix = 'Chain' if chain else ''
                    kind = 'Sub' if tag == 'GSUB' else 'Pos'
                    set_attr = prefix + kind + ('RuleSet' if fmt == 1 else 'ClassSet')
                    rule_attr = prefix + kind + ('Rule' if fmt == 1 else 'ClassRule')
                    slot = 0 if fmt == 1 else 1
                    rs = getattr(valid_st, set_attr)[slot]
                    valid_rule = getattr(rs, rule_attr)[0]
                    bad_rule = copy.deepcopy(valid_rule)
                    for rec in _records(bad_rule):
                        rec.LookupListIndex = 0
                    ignore = copy.deepcopy(valid_rule)
                    setattr(ignore, 'SubstLookupRecord' if tag == 'GSUB'
                            else 'PosLookupRecord', [])
                    setattr(ignore, 'SubstCount' if tag == 'GSUB' else 'PosCount', 0)
                    setattr(rs, rule_attr, [bad_rule, ignore, valid_rule])
                    setattr(rs, rule_attr + 'Count', 3)
                main = _merge_fixture(_main(tag), base, False)
                lookups = main[tag].table.LookupList.Lookup
                assert len(lookups) == 3
                assert _refs(lookups[-1]) == [1]
                st = lookups[-1].SubTable[-1]
                if fmt == 3:
                    assert len(lookups[-1].SubTable) == 2
                else:
                    assert len(getattr(getattr(st, set_attr)[slot], rule_attr)) == 2
    print('  失效规则删除/原有 ignore 保留：12 组，余下 1 动作与 1 ignore')


def _required(font, tag):
    table = font['GSUB'].table
    index = next(i for i, fr in enumerate(table.FeatureList.FeatureRecord)
                 if fr.FeatureTag == tag)
    for sr in table.ScriptList.ScriptRecord:
        lang = sr.Script.DefaultLangSys
        lang.ReqFeatureIndex = index
        lang.FeatureIndex = [i for i in lang.FeatureIndex if i != index]
        lang.FeatureCount = len(lang.FeatureIndex)


def test_primary_params_and_required_features():
    source = _font('languagesystem latn dflt; languagesystem cyrl dflt; '
                   'feature rlig {sub a by a.alt;} rlig; '
                   'feature ss01 {sub b by b.alt;} ss01;')
    donor = _font('languagesystem latn dflt; '
                  'feature rlig {sub b by b.alt;} rlig; '
                  'feature ss01 {sub c by c.alt;} ss01;')
    for font, name_id in ((source, 256), (donor, 257)):
        _required(font, 'rlig')
        fr = next(fr for fr in font['GSUB'].table.FeatureList.FeatureRecord
                  if fr.FeatureTag == 'ss01')
        params = ot.FeatureParamsStylisticSet()
        params.Version = 0
        params.UINameID = name_id
        fr.Feature.FeatureParams = params
        font['name'].setName('Neutral option', name_id, 3, 1, 0x409)
    for same_source in (False, True):
        table = _merge_fixture(source, donor, same_source)['GSUB'].table
        for sr in table.ScriptList.ScriptRecord:
            lang = sr.Script.DefaultLangSys
            required = table.FeatureList.FeatureRecord[lang.ReqFeatureIndex]
            assert required.FeatureTag == 'rlig'
            expected = 2 if sr.ScriptTag == 'latn' else 1
            assert len(required.Feature.LookupListIndex) == expected
            optional = _lang_features(table, sr.ScriptTag)
            assert [fr.FeatureTag for fr in optional] == ['ss01']
            assert optional[0].Feature.FeatureParams.UINameID == 256
            assert len(optional[0].Feature.LookupListIndex) == expected
        # 主来源原对象未被合并器修改。
        assert len(source['GSUB'].table.FeatureList.FeatureRecord) == 2
    # 主无必需特性时应接纳打底 required，不能仅合并可选列表。
    no_required = _font('languagesystem latn dflt; feature salt {sub c by c.alt;} salt;')
    for same_source in (False, True):
        table = _merge_fixture(no_required, donor, same_source)['GSUB'].table
        lang = table.ScriptList.ScriptRecord[0].Script.DefaultLangSys
        assert table.FeatureList.FeatureRecord[lang.ReqFeatureIndex].FeatureTag == 'rlig'
    print('  主参数 256 保持；required 同 tag 并集与缺省接纳：4 路通过')


def _feature_variations(font, feature_tag, alternate, intervals=((0.25, 1.0),)):
    """给 feaLib 生成的 lookup 设置最小条件替换，支持显式空替换。"""
    from fontTools.ttLib.tables._f_v_a_r import Axis
    fvar = newTable('fvar')
    axis = Axis()
    axis.axisTag = 'wght'
    axis.minValue, axis.defaultValue, axis.maxValue = 100, 400, 900
    axis.flags = 0
    axis.axisNameID = 258
    fvar.axes = [axis]
    fvar.instances = []
    font['fvar'] = fvar
    font['name'].setName('Neutral axis', 258, 3, 1, 0x409)
    table = font['GSUB'].table
    index = next(i for i, fr in enumerate(table.FeatureList.FeatureRecord)
                 if fr.FeatureTag == feature_tag)
    fv = ot.FeatureVariations()
    fv.Version = 0x00010000
    fv.FeatureVariationRecord = []
    for bounds in intervals:
        rec = ot.FeatureVariationRecord()
        rec.ConditionSet = ot.ConditionSet()
        condition = ot.ConditionTable()
        condition.Format = 1
        condition.AxisIndex = 0
        condition.FilterRangeMinValue, condition.FilterRangeMaxValue = bounds
        rec.ConditionSet.ConditionTable = [condition]
        rec.ConditionSet.ConditionCount = 1
        rec.FeatureTableSubstitution = ot.FeatureTableSubstitution()
        rec.FeatureTableSubstitution.Version = 0x00010000
        sub = ot.FeatureTableSubstitutionRecord()
        sub.FeatureIndex = index
        sub.Feature = copy.deepcopy(table.FeatureList.FeatureRecord[index].Feature)
        sub.Feature.LookupListIndex = list(alternate)
        sub.Feature.LookupCount = len(alternate)
        rec.FeatureTableSubstitution.SubstitutionRecord = [sub]
        rec.FeatureTableSubstitution.SubstitutionCount = 1
        fv.FeatureVariationRecord.append(rec)
    fv.FeatureVariationRecordCount = len(fv.FeatureVariationRecord)
    table.FeatureVariations = fv
    table.Version = 0x00010001


def _effective_features(table, script, variant=False):
    selected = _lang_features(table, script)
    if not variant:
        return selected
    substitutions = {sub.FeatureIndex: sub.Feature for sub in
                     table.FeatureVariations.FeatureVariationRecord[0]
                     .FeatureTableSubstitution.SubstitutionRecord}
    records = table.FeatureList.FeatureRecord
    output = []
    for fr in selected:
        index = records.index(fr)
        alternate = copy.deepcopy(fr)
        alternate.Feature = substitutions.get(index, fr.Feature)
        output.append(alternate)
    return output


def test_feature_variations_local_union():
    source = _font('languagesystem latn dflt; languagesystem cyrl dflt; '
                   'feature liga {sub a by a.alt;} liga; '
                   'feature salt {sub b by b.alt;} salt;')
    donor = _font('languagesystem latn dflt; feature liga {sub c by c.alt;} liga;')
    for empty in (False, True):
        _feature_variations(source, 'liga', [] if empty else [1])
        for same_source in (False, True):
            table = _merge_fixture(source, donor, same_source)['GSUB'].table
            for script in ('latn', 'cyrl'):
                defaults = [fr for fr in _effective_features(table, script)
                            if fr.FeatureTag == 'liga']
                variants = [fr for fr in _effective_features(table, script, True)
                            if fr.FeatureTag == 'liga']
                donor_maps = [{'c': 'c.alt'}] if script == 'latn' else []
                assert _substitutions(table, defaults) == [{'a': 'a.alt'}] + donor_maps
                expected = ([] if empty else [{'b': 'b.alt'}]) + donor_maps
                assert _substitutions(table, variants) == expected
    print('  FV 默认/替换/空替换与脚本隔离：4 路，逐 lookup 与来源一致')


def test_feature_variations_strict_conditions():
    source = _font('feature liga {sub a by a.alt;} liga; '
                   'feature salt {sub b by b.alt;} salt;')
    donor = _font('feature liga {sub c by c.alt;} liga;')
    _feature_variations(source, 'liga', [1], ((0.25, 1.0), (-1.0, 1.0)))
    _feature_variations(donor, 'liga', [], ((0.25, 1.0), (-1.0, 1.0)))
    union = LayoutUnion('GSUB')
    union.add_from(source['GSUB'].table, {})
    union.add_from(donor['GSUB'].table, {})
    result = copy.deepcopy(source)
    result['GSUB'].table = union.finalize()
    table = _reload(result)['GSUB'].table
    assert len(table.FeatureVariations.FeatureVariationRecord) == 2
    selected = [fr for fr in _effective_features(table, 'DFLT', True)
                if fr.FeatureTag == 'liga']
    assert _substitutions(table, selected) == [{'b': 'b.alt'}]
    # 不同条件优先序不能按条件签名随意拼接；失败必须原子保留已加入状态。
    bad = copy.deepcopy(donor)
    bad['GSUB'].table.FeatureVariations.FeatureVariationRecord.reverse()
    before = (len(union.lookups), len(union.feature_records), len(union.fv_order))
    try:
        union.add_from(bad['GSUB'].table, {})
    except ValueError as exc:
        assert '条件' in str(exc)
    else:
        raise AssertionError('FV 条件优先序不一致却被接受')
    assert before == (len(union.lookups), len(union.feature_records), len(union.fv_order))
    print('  FV 两条件首匹配顺序保持；反序输入原子拒绝，状态 0 变化')


def _pair_adjustment(table, features, first, second):
    value = 0
    for feature in features:
        for index in feature.Feature.LookupListIndex:
            lookup = table.LookupList.Lookup[index]
            for st in lookup.SubTable:
                if isinstance(st, ot.ExtensionPos):
                    st = st.ExtSubTable
                if not isinstance(st, ot.PairPos) or first not in st.Coverage.glyphs:
                    continue
                assert st.Format == 1
                pairs = st.PairSet[st.Coverage.glyphs.index(first)].PairValueRecord
                value += sum(getattr(pair.Value1, 'XAdvance', 0)
                             for pair in pairs if pair.SecondGlyph == second)
    return value


def test_kern_primary_values_not_unified():
    source = _font('feature kern {pos a b -100; pos b c -40;} kern;',
                   ['x', 'y'])
    donor = _font('lookup OVER {pos uni0061 uni0062 -100;} OVER; '
                  'lookup NEW {pos x y -70;} NEW; '
                  'feature kern {lookup OVER; lookup NEW;} kern;',
                  ['uni0061', 'uni0062', 'x', 'y'])
    before = _pair_adjustment(source['GPOS'].table,
                              _lang_features(source['GPOS'].table, 'DFLT'), 'a', 'b')
    result = _merge_fixture(source, donor, False)
    table = result['GPOS'].table
    features = _lang_features(table, 'DFLT')
    assert len(features) == 1
    assert _pair_adjustment(table, features, 'a', 'b') == before == -100
    assert _pair_adjustment(table, features, 'b', 'c') == -40
    assert _pair_adjustment(table, features, 'x', 'y') == -70
    assert len(table.LookupList.Lookup) == 2
    print('  kern 主字对逐值 -100/-40 保持，新增字对 -70，不发生双重定位')


def test_coverage_parallel_arrays():
    font = _font('feature dist {pos a 11; pos b 23;} dist; '
                 'feature curs {pos cursive a <anchor 10 20> <anchor 30 40>; '
                 'pos cursive b <anchor 50 60> <anchor 70 80>;} curs;')
    original = font['GPOS'].table.LookupList.Lookup
    single = next(st for lk in original for st in lk.SubTable
                  if isinstance(st, ot.SinglePos))
    assert single.Format == 2
    font.setGlyphOrder(['.notdef', 'b', 'a', 'c', 'a.alt', 'b.alt', 'c.alt'])
    resort_layout(font)
    result = _reload(font)
    for lookup in result['GPOS'].table.LookupList.Lookup:
        for st in lookup.SubTable:
            assert st.Coverage.glyphs == ['b', 'a']
            if isinstance(st, ot.SinglePos):
                assert [v.XAdvance for v in st.Value] == [23, 11]
            elif isinstance(st, ot.CursivePos):
                assert [v.EntryAnchor.XCoordinate for v in st.EntryExitRecord] == [50, 10]
    print('  SinglePos fmt2/CursivePos 并行数组：2 类 × 2 字形值无损')


def test_nonconstant_lookup_map_and_shared_records():
    for tag in ('GSUB', 'GPOS'):
        for same_source in (False, True):
            base = _context_font(tag, 3, True)
            table = base[tag].table
            first, inner, root = table.LookupList.Lookup
            additional = _font('feature salt {sub b by b.alt;} salt;' if tag == 'GSUB'
                               else 'feature dist {pos b 29;} dist;')
            other = copy.deepcopy(additional[tag].table.LookupList.Lookup[0])
            table.LookupList.Lookup = [inner, first, other, root]
            st = root.SubTable[0].ExtSubTable
            records = _records(st)
            records[0].LookupListIndex = 0
            second = _record(tag, 2)
            second.SequenceIndex = 1
            rec_attr = 'SubstLookupRecord' if tag == 'GSUB' else 'PosLookupRecord'
            setattr(st, rec_attr, records + [second])
            setattr(st, 'SubstCount' if tag == 'GSUB' else 'PosCount', 2)
            # Extension 共用同一子表，重映射不能执行两次。
            root.SubTable.append(root.SubTable[0])
            root.SubTableCount = 2
            table.FeatureList.FeatureRecord[0].Feature.LookupListIndex = [1, 3]
            main = _main(tag)
            if same_source:
                # 人工失效引用用于验证同源图修剪；不得回指主的 lookup。
                table.LookupList.Lookup[1] = copy.deepcopy(root)
                for rec in _records(table.LookupList.Lookup[1]):
                    rec.LookupListIndex = 999
                union = LayoutUnion(tag)
                union.add_from(main[tag].table, {})
                union.add_from(table, {})
                main[tag].table = union.finalize()
            else:
                merge_base_layout(main, base, main.getGlyphOrder())
            # 保存前共享对象必须只被映射一次；重载后解码器不保证对象身份。
            assert _refs(main[tag].table.LookupList.Lookup[-1]) == [1, 2]
            result = _reload(main)
            lookups = result[tag].table.LookupList.Lookup
            assert len(lookups) == 4
            assert all(_refs(st) == [1, 2] for st in lookups[-1].SubTable)
            assert _refs(root) == [0, 2]
    print('  非恒定映射 0→1/2→2、共享 Extension 单次映射：4 路通过')


def test_required_feature_variations_and_adoption():
    source = _font('feature rlig {sub a by a.alt;} rlig; '
                   'feature salt {sub b by b.alt;} salt;')
    donor = _font('feature rlig {sub c by c.alt;} rlig;')
    _required(source, 'rlig')
    _required(donor, 'rlig')
    _feature_variations(source, 'rlig', [1])
    for same_source in (False, True):
        table = _merge_fixture(source, donor, same_source)['GSUB'].table
        req = table.ScriptList.ScriptRecord[0].Script.DefaultLangSys.ReqFeatureIndex
        feature = table.FeatureList.FeatureRecord[req]
        assert feature.FeatureTag == 'rlig'
        assert _substitutions(table, [feature]) == [{'a': 'a.alt'}, {'c': 'c.alt'}]
        replacements = table.FeatureVariations.FeatureVariationRecord[0]
        alt = next(sub.Feature for sub in
                   replacements.FeatureTableSubstitution.SubstitutionRecord
                   if sub.FeatureIndex == req)
        assert alt.LookupListIndex == [1, 2]
    # 主无 GSUB 时，FV、lookup 映射、脚本可达性仍须全部走完整采用路径。
    result = _merge_fixture(_font(), source, False)
    table = result['GSUB'].table
    req = table.ScriptList.ScriptRecord[0].Script.DefaultLangSys.ReqFeatureIndex
    assert table.FeatureList.FeatureRecord[req].FeatureTag == 'rlig'
    assert len(table.LookupList.Lookup) == 2
    assert table.FeatureVariations.FeatureVariationRecord[0].FeatureTableSubstitution        .SubstitutionRecord[0].Feature.LookupListIndex == [1]
    print('  必需特性 FV 逐 lookup 保留及主无 GSUB 的完整采用：3 路通过')


def test_parameter_only_feature_and_required_conflict():
    source = _font('languagesystem latn dflt; feature rlig {sub a by a.alt;} rlig;')
    donor = _font('languagesystem latn dflt; feature calt {sub b by b.alt;} calt;')
    _required(source, 'rlig')
    _required(donor, 'calt')
    for same_source in (False, True):
        table = _merge_fixture(source, donor, same_source)['GSUB'].table
        lang = table.ScriptList.ScriptRecord[0].Script.DefaultLangSys
        req = table.FeatureList.FeatureRecord[lang.ReqFeatureIndex]
        assert req.FeatureTag == 'rlig'
        assert _substitutions(table, [req]) == [{'a': 'a.alt'}]
        assert lang.FeatureIndex == []
    # GPOS size 的 FeatureParams 本身有效，即使整张表没有任何 lookup。
    parameter_font = _font('feature size {parameters 120 0 0 0;} size;')
    assert parameter_font['GPOS'].table.LookupList.Lookup == []
    for same_source in (False, True):
        table = _merge_fixture(_font(), parameter_font, same_source)['GPOS'].table
        size = _lang_features(table, 'DFLT')[0]
        assert size.FeatureTag == 'size'
        # FEA 的 120 decipoints 对应 fontTools 对象里的 12 pt。
        assert size.Feature.FeatureParams.DesignSize == 12.0
        assert size.Feature.LookupListIndex == []
    print('  不同 required tag 主优先；参数型空 size 特性完整采用：4 路通过')


def main():
    tests = [test_context_lookup_mapping, test_same_source_context_mapping,
             test_langsys_isolation_and_union, test_mark_sets_gid_order,
             test_nested_closure_and_dropped_rules,
             test_partially_dropped_context_rules,
             test_primary_params_and_required_features,
             test_feature_variations_local_union,
             test_feature_variations_strict_conditions,
             test_kern_primary_values_not_unified,
             test_coverage_parallel_arrays,
             test_nonconstant_lookup_map_and_shared_records,
             test_required_feature_variations_and_adoption,
             test_parameter_only_feature_and_required_conflict]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print('  %s: PASSED' % test.__name__)
        except Exception as exc:
            print('  %s: FAILED - %s' % (test.__name__, exc))
            traceback.print_exc()
    print('Results: %d/%d passed' % (passed, len(tests)))
    return passed == len(tests)


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
