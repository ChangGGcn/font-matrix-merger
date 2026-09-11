#!/usr/bin/env python3
"""基于 test 文件夹中的字体生成合并样例

字体说明:
- OFL 公开字体直接按文件名定位; 文件不存在时对应样例 SKIP。
- 商业授权字体路径通过 tests/local_fonts.py 配置 (该文件不入库)。
"""

import os, sys, copy, time

# 确保包路径正确
_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
_test_dir = os.path.join(_project_dir, "test")
_output_dir = os.path.join(_project_dir, "test", "samples")

sys.path.insert(0, _project_dir)
sys.path.insert(0, _repo_dir)   # 使 tests.local_fonts 在"直接运行脚本"模式下也可导入

from FontMerger import (FontMerger, type_label, get_copyrights,
                         get_family, apply_naming, is_cff, is_ttf,
                         is_variable, merge_fonts)

from fontTools.ttLib import TTFont


def font(rel):
    """公开字体路径; 不存在返回 None"""
    p = os.path.join(_test_dir, rel)
    return p if os.path.exists(p) else None


def local(role):
    """本地授权字体路径 (tests/local_fonts.py 配置); 未配置返回 None"""
    try:
        from tests.local_fonts import LOCAL_FONTS
        rel = LOCAL_FONTS.get(role)
    except ImportError:
        rel = None
    if not rel:
        return None
    p = os.path.join(_test_dir, rel)
    return p if os.path.exists(p) else None


def s(font_path, sample_name):
    """打开字体; 缺失时打印 SKIP 并返回 None"""
    if not font_path:
        print(f"  SKIP: {sample_name} (字体未就位)")
        return None
    return TTFont(font_path)


def ensure_output():
    os.makedirs(_output_dir, exist_ok=True)


def sample1_otf_plus_otf():
    """样例1: 静态OTF(拉丁) + 静态OTF(中文) → 中拉丁混合字体"""
    print("Sample 1: 静态OTF + 静态OTF (拉丁+中文)")
    main = s(font("OpenType/LibreCaslonText-Regular.otf"), "Sample1")
    base = s(local("cjk_static_otf"), "Sample1")
    if not main or not base:
        return None
    print(f"  Main: {type_label(main)}, {len(main.getGlyphOrder())} glyphs")
    print(f"  Base: {type_label(base)}, {len(base.getGlyphOrder())} glyphs")

    merger = FontMerger()
    result = merger.merge_two(main, base)
    print(f"  Result: {type_label(result)}, {len(result.getGlyphOrder())} glyphs")

    cr = get_copyrights(main, base)
    fn = get_family(main)
    result = apply_naming(result, fn, cr)

    out = os.path.join(_output_dir, "Sample1_LatinPlusCJK.otf")
    result.save(out)
    print(f"  Saved: {out}")
    return result


def sample2_ttf_plus_ttf():
    """样例2: 静态TTF + 静态TTF"""
    print("Sample 2: 静态TTF + 静态TTF")
    main = s(font("TrueType/LXGWWenKaiTC-Regular.ttf"), "Sample2")
    base = s(local("cjk_static_ttf"), "Sample2")
    if not main or not base:
        return None
    print(f"  Main: {type_label(main)}, {len(main.getGlyphOrder())} glyphs")
    print(f"  Base: {type_label(base)}, {len(base.getGlyphOrder())} glyphs")

    merger = FontMerger()
    merger.mem = {"sTTF_sOTF": "TTF"}  # in case format detection changes
    result = merger.merge_two(main, base)
    print(f"  Result: {type_label(result)}, {len(result.getGlyphOrder())} glyphs")

    cr = get_copyrights(main, base)
    fn = get_family(main)
    result = apply_naming(result, fn, cr)

    out = os.path.join(_output_dir, "Sample2_TTFPlusTTF.ttf")
    result.save(out)
    print(f"  Saved: {out}")
    return result


def sample3_otf_plus_ttf_conversion():
    """样例3: 静态OTF + 静态TTF (混合格式自动转换)"""
    print("Sample 3: 静态OTF + 静态TTF (格式转换)")
    main = s(font("OpenType/LibreCaslonText-Regular.otf"), "Sample3")
    base = s(local("cjk_ttf_hanyi"), "Sample3")
    if not main or not base:
        return None
    print(f"  Main: {type_label(main)}, {len(main.getGlyphOrder())} glyphs")
    print(f"  Base: {type_label(base)}, {len(base.getGlyphOrder())} glyphs")

    merger = FontMerger()
    merger.mem = {"sOTF_sTTF": "OTF"}
    result = merger.merge_two(main, base)
    print(f"  Result: {type_label(result)}, {len(result.getGlyphOrder())} glyphs")

    cr = get_copyrights(main, base)
    fn = get_family(main)
    result = apply_naming(result, fn, cr)

    out = os.path.join(_output_dir, "Sample3_OTFPlusTTF_Converted.otf")
    result.save(out)
    print(f"  Saved: {out}")
    return result


def sample4_variable_instantiate_and_merge():
    """样例4: 可变OTF实例化 + 合并"""
    print("Sample 4: 可变OTF → 静态实例 + 合并")
    vf_path = font("otf_variable_fonts/SourceHanSansCN-VF.otf")
    if not vf_path:
        print("  SKIP: Sample4 (SourceHanSansCN-VF.otf not found)")
        return None

    vf = TTFont(vf_path)
    print(f"  VF: {type_label(vf)}, {len(vf.getGlyphOrder())} glyphs")

    from FontMerger import variable_to_static
    static_inst = variable_to_static(vf)
    print(f"  Static instance: {type_label(static_inst)}, "
          f"{len(static_inst.getGlyphOrder())} glyphs")

    # 与另一个字体合并
    sym_path = local("symbols_otf")
    if sym_path:
        sym = TTFont(sym_path)
        print(f"  Symbol font: {type_label(sym)}, {len(sym.getGlyphOrder())} glyphs")

        merger = FontMerger()
        result = merger.merge_two(static_inst, sym)
        print(f"  Result: {type_label(result)}, {len(result.getGlyphOrder())} glyphs")

        cr = get_copyrights(vf, sym)
        fn = get_family(vf)
        result = apply_naming(result, fn, cr)

        out = os.path.join(_output_dir, "Sample4_VariableStaticPlusSymbols.otf")
        result.save(out)
        print(f"  Saved: {out}")
        return result
    print("  SKIP: Sample4 (symbols font 未配置)")
    return static_inst


def sample5_multilevel_merge():
    """样例5: 三级合并 (主 + 打底1 + 打底2)"""
    print("Sample 5: 多级合并")
    main = s(font("OpenType/LibreCaslonText-Regular.otf"), "Sample5")
    base1 = s(local("cjk_static_otf"), "Sample5")
    base2 = s(font("OpenType/SourceHanSansSC-Regular.otf"), "Sample5")
    if not main or not base1 or not base2:
        return None
    print(f"  Main: {type_label(main)}, {len(main.getGlyphOrder())} glyphs")
    print(f"  Base1: {type_label(base1)}, {len(base1.getGlyphOrder())} glyphs")
    print(f"  Base2: {type_label(base2)}, {len(base2.getGlyphOrder())} glyphs")

    merger = FontMerger()
    result = merger.merge_two(main, base1)
    print(f"  After L1: {len(result.getGlyphOrder())} glyphs")
    result = merger.merge_two(result, base2)
    print(f"  After L2: {len(result.getGlyphOrder())} glyphs")

    cr = get_copyrights(main, base1, base2)
    fn = get_family(main)
    result = apply_naming(result, fn, cr)

    out = os.path.join(_output_dir, "Sample5_MultiLevel_3Fonts.otf")
    result.save(out)
    print(f"  Saved: {out}")
    return result


def sample6_high_level_api():
    """样例6: 便捷 API (merge_fonts 一行调用)"""
    print("Sample 6: merge_fonts 便捷 API")
    main_path = font("OpenType/LibreCaslonText-Regular.otf")
    base1_path = local("cjk_static_otf")
    if not main_path or not base1_path:
        print("  SKIP: Sample6 (字体未就位)")
        return None

    result = merge_fonts(main_path, [base1_path], interactive=False)
    print(f"  Result: {type_label(result)}, {len(result.getGlyphOrder())} glyphs")

    out = os.path.join(_output_dir, "Sample6_ConvenienceAPI.otf")
    result.save(out)
    print(f"  Saved: {out}")
    return result


def main():
    ensure_output()
    start = time.time()
    results = []

    for sample_func in [sample1_otf_plus_otf, sample2_ttf_plus_ttf,
                         sample3_otf_plus_ttf_conversion,
                         sample4_variable_instantiate_and_merge,
                         sample5_multilevel_merge, sample6_high_level_api]:
        try:
            r = sample_func()
            results.append(r)
            print()
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            print()

    elapsed = time.time() - start
    successful = sum(1 for r in results if r is not None)
    print(f"\n{'='*60}")
    print(f"  Generated {successful}/{len(results)} samples in {elapsed:.1f}s")
    print(f"  Output: {_output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
