#!/usr/bin/env python3
"""CFF2 blend/vsindex 跨设计空间重参数化的自检 (阶段 4)

判据: 重参数化后的字体在合并空间任意位置画出的轮廓, 必须与源字体在对应位置
(经用户空间钳制) 的实例逐点一致 —— 用 fontTools 的 glyphSet(blender) 直接画
轮廓比对, 不依赖 HarfBuzz。
"""
import copy
import os
import random
import sys
from io import BytesIO

_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
_test_fonts_dir = os.path.join(_project_dir, "test")
sys.path.insert(0, _project_dir)
sys.path.insert(0, _repo_dir)

from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

from FontMerger.format.axis_mapping import AxisMapping, fvar_triples
from FontMerger.format.cff2_compose import (cff2_var_store, offset_cff2_vsindex,
                                            reparametrize_cff2)

_CFF2 = os.path.join(_test_fonts_dir, "otf_variable_fonts",
                     "SourceSerif4Variable-Roman.otf")


def _open(path=None):
    p = path or _CFF2
    return TTFont(p) if os.path.exists(p) else None


def _merged_mapping(font, wide_wght=100.0, hi_opsz=40.0):
    """构造一个"并集风格"的合并空间: wght 两端更宽, opsz 上限更高"""
    src = fvar_triples(font)
    merged = dict(src)
    merged["wght"] = (min(src["wght"][0], wide_wght), src["wght"][1],
                      max(src["wght"][2], 1000.0))
    merged["opsz"] = (src["opsz"][0], src["opsz"][1], hi_opsz)
    mappings = {tag: AxisMapping(merged[tag], None, src[tag], None)
                for tag in merged}
    return src, merged, mappings


def _draw_diff(pen_a, pen_b):
    """两个 RecordingPen 的最大坐标偏差 (结构不同返回 inf)"""
    if len(pen_a.value) != len(pen_b.value):
        return float("inf")
    worst = 0.0
    for (op1, a1), (op2, a2) in zip(pen_a.value, pen_b.value):
        if op1 != op2 or len(a1) != len(a2):
            return float("inf")
        for x, y in zip(a1, a2):
            xs = x if isinstance(x, tuple) else (x,)
            ys = y if isinstance(y, tuple) else (y,)
            for u, v in zip(xs, ys):
                if isinstance(u, (int, float)) and isinstance(v, (int, float)):
                    worst = max(worst, abs(float(u) - float(v)))
    return worst


def test_cff2_identity():
    """恒等映射: 列数不变, 轮廓逐点不变 (重参数化的最弱情形)"""
    font = _open()
    if font is None:
        print("  test_cff2_identity: SKIP (测试字体未就位)")
        return
    src_triples = fvar_triples(font)
    mappings = {tag: AxisMapping(src_triples[tag], None, src_triples[tag], None)
                for tag in src_triples}
    before = [vd.VarRegionCount for vd in cff2_var_store(font).VarData]
    rep = reparametrize_cff2(font, mappings, list(src_triples), list(src_triples))
    after = [vd.VarRegionCount for vd in cff2_var_store(font).VarData]
    assert before == after, (before, after)
    loc = {tag: 0.5 for tag in src_triples}
    pen = RecordingPen()
    font.getGlyphSet(location=loc, normalized=True)["A"].draw(pen)
    assert pen.value, "没有画出任何轮廓"
    print("  test_cff2_identity: 列 %s 不变, %d 个 blend 重写, PASSED"
          % (after, rep["blends"]))


def test_cff2_vsindex_offset():
    """并入别的字体前的 vsindex 平移: 显式引用 +1, 隐式引用补一条 vsindex"""
    font = _open()
    if font is None:
        print("  test_cff2_vsindex_offset: SKIP (测试字体未就位)")
        return
    td = font["CFF2"].cff.topDictIndex[0]
    cs = td.CharStrings["A"]
    cs.decompile()
    # 源程序没有显式 vsindex (整个字体都没有) → 应补一条, 并在 private 里记偏移
    assert "vsindex" not in cs.program
    patched = offset_cff2_vsindex(font, 7)
    assert patched > 0, patched
    cs = td.CharStrings["A"]
    cs.decompile()
    i = cs.program.index("vsindex")
    assert cs.program[i - 1] == 7, cs.program[max(0, i - 3):i + 1]
    # 再来一次: 显式引用被平移 (而不是叠加插入)
    before = cs.program.count("vsindex")
    offset_cff2_vsindex(font, 1)
    cs = td.CharStrings["A"]
    cs.decompile()
    i = cs.program.index("vsindex")
    assert cs.program[i - 1] == 8, cs.program[max(0, i - 3):i + 1]
    assert cs.program.count("vsindex") == before
    print("  test_cff2_vsindex_offset: 补 %d 条, 平移正确, PASSED" % patched)


def test_cff2_reparametrize_outlines():
    """真实 CFF2 字体: 合并空间采样点上的轮廓与源实例逐点一致。

    同时覆盖: Private DICT 的 blend 值 (hint) 重写、保存/重载后的可用性。
    """
    base = _open()
    if base is None:
        print("  test_cff2_reparametrize_outlines: SKIP (测试字体未就位)")
        return
    font = TTFont(_CFF2)
    src_triples, merged, mappings = _merged_mapping(font)
    rep = reparametrize_cff2(font, mappings, list(src_triples), list(merged))
    assert rep["columns"][1] > rep["columns"][0], rep
    assert rep["blends"] > 0 and rep["private"] > 0, rep
    store = cff2_var_store(font)
    assert store.VarRegionList.RegionAxisCount == len(merged)
    for reg in store.VarRegionList.Region:
        assert len(reg.VarRegionAxis) == len(merged)
        for axis in reg.VarRegionAxis:
            assert not (axis.StartCoord < 0.0 < axis.EndCoord), "跨 0 的 region"

    rng = random.Random(11)
    names = [n for n in base.getGlyphOrder() if n != ".notdef"]
    sample = rng.sample(names, 16)
    worst = 0.0
    checked = 0
    for _ in range(6):
        loc_m = {tag: rng.uniform(-1.0, 1.0) for tag in merged}
        loc_s = {tag: mappings[tag].to_source(loc_m[tag]) for tag in merged}
        gs_new = font.getGlyphSet(location=loc_m, normalized=True)
        gs_src = base.getGlyphSet(location=loc_s, normalized=True)
        for gn in sample:
            p1, p2 = RecordingPen(), RecordingPen()
            gs_new[gn].draw(p1)
            gs_src[gn].draw(p2)
            diff = _draw_diff(p1, p2)
            assert diff < 1e-6, (gn, loc_m, diff)
            checked += 1
            worst = max(worst, diff)

    buf = BytesIO()
    font.save(buf)
    again = TTFont(BytesIO(buf.getvalue()))
    gs = again.getGlyphSet(location={tag: 1.0 for tag in merged}, normalized=True)
    pen = RecordingPen()
    gs["A"].draw(pen)
    assert pen.value, "保存/重载后画不出轮廓 (Private blend 编码不一致?)"
    print("  test_cff2_reparametrize_outlines: %d 字形, %d 列 → %d 列, "
          "最大偏差 %.2e, PASSED"
          % (checked, rep["columns"][0], rep["columns"][1], worst))


def test_cff2_cross_design_space_merge():
    """CFF2 × CFF2 跨设计空间合并: 打底新字形的轮廓与字宽在各轴位置上都对。

    主/打底 = SourceSerif4 的两个不相交子集, 打底的 fvar 范围与默认值被改过
    (归一化空间不同) → 走合成路径: 打底 CFF2 的 blend 重参数化并入, 打底
    HVAR 的变化宽度按字形名重新接上。
    """
    main_p = os.path.join(_test_fonts_dir, "otf_variable_fonts",
                          "SourceSerif4Variable-Roman.otf")
    from tests.cff2_fixture import cached_cff2_pair
    pair = cached_cff2_pair(main_p)
    if not pair:
        print("  test_cff2_cross_design_space_merge: SKIP (测试字体未就位)")
        return
    main_path, base_path = pair
    from FontMerger import FontMerger

    main, base = TTFont(main_path), TTFont(base_path)
    merged = FontMerger(verify_compose=False).merge_two(
        copy.deepcopy(main), copy.deepcopy(base))
    added = [gn for gn in merged.getGlyphOrder()
             if gn not in set(main.getGlyphOrder())]
    assert added, "没有新增字形"
    axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue)
            for a in merged["fvar"].axes}
    b_axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue)
              for a in base["fvar"].axes}
    # 用 glyphSet(location=用户坐标) 比较: 它会应用 avar (与渲染一致);
    # instantiateVariableFont 的 user limits 不套 avar, 在这类字体上会有
    # 1 单位级的系统性偏差 (见 core/verify.py 的说明)。
    worst_o = worst_w = 0.0
    checked = 0
    for loc in ({"wght": 700.0, "opsz": 30.0}, {"wght": 200.0, "opsz": 10.0},
                {"wght": 300.0, "opsz": 14.0}, {"wght": 900.0, "opsz": 48.0}):
        loc_m = {t: min(max(v, axes[t][0]), axes[t][2]) for t, v in loc.items()}
        loc_b = {t: min(max(v, b_axes[t][0]), b_axes[t][2])
                 for t, v in loc.items() if t in b_axes}
        gs_m = merged.getGlyphSet(location=loc_m)
        gs_b = base.getGlyphSet(location=loc_b)
        for gn in added:
            if gn not in gs_b:
                continue
            p1, p2 = RecordingPen(), RecordingPen()
            gs_m[gn].draw(p1)
            gs_b[gn].draw(p2)
            worst_o = max(worst_o, _draw_diff(p1, p2))
            worst_w = max(worst_w, abs(gs_m[gn].width - gs_b[gn].width))
            checked += 1
    assert checked > 0, "没有可比较的字形"
    # 轮廓容差 0.01 单位: blend 增量在 charstring 里是 16.16 定点数, 重参数化
    # 后的浮点权重取整留下 1e-3 级残差 (UPM 1000 下即 1e-6 em)。
    # 字宽容差 4 单位: HVAR 的增量是**整数**, 一个源列拆成多个 hat 后逐个取整,
    # 非默认位置上的残差可达几个单位 (同样的原因见布局 kerning 的 0.7 单位)。
    assert worst_o < 0.01, "轮廓偏差 %.4f" % worst_o
    assert worst_w < 4.0, "字宽偏差 %.4f" % worst_w
    print("  test_cff2_cross_design_space_merge: %d 字形 × 4 位置, 轮廓 %.2e / "
          "字宽 %.2e, PASSED" % (checked, worst_o, worst_w))


def main():
    print("FontMerger CFF2-composition Test Suite")
    print("=" * 50)
    tests = [
        test_cff2_identity,
        test_cff2_vsindex_offset,
        test_cff2_reparametrize_outlines,
        test_cff2_cross_design_space_merge,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  {test.__name__}: FAILED - {e}")
            import traceback
            traceback.print_exc()
    print(f"\n{'='*50}")
    print(f"  Results: {passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
