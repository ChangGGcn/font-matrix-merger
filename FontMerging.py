#!/usr/bin/env python3
"""FontMerger — 字体合并工具主入口

用法:
    python FontMerging.py                     # 交互模式
    python FontMerging.py main.otf base.otf   # 命令行模式
"""

import os, sys
from pathlib import Path

# 确保父目录在 sys.path 中 (处理直接运行此脚本的情况)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_script_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from FontMerger import (FontMerger, SUPPORTED_EXTS, COLLECTION_EXTS,
                         load_font, type_label, get_copyrights,
                         get_family, apply_naming, is_cff, apply_scale_offset)
from FontMerger.utils.save import save_font, default_flavor_for
import copy


def run():
    print("=" * 56)
    print("  FontMerger 字体合并工具")
    print("  支持: 静态/可变 x OTF/TTF x 多级打底 x WOFF/WOFF2")
    print("=" * 56)

    merger = FontMerger()
    inputs = []

    # ---- 主字体 ----
    print("\n请输入主字体（拖入文件或输入路径）:")
    while True:
        try:
            p = input("  主字体路径: ").strip().strip('"').strip("'")
        except (EOFError, KeyboardInterrupt):
            print("\n取消。"); sys.exit(0)
        if not p:
            print("  路径不能为空。"); continue
        ext = Path(p).suffix.lower()
        if ext in COLLECTION_EXTS:
            print("  请先将字体集解包 (TTC/OTC)。"); continue
        if ext not in SUPPORTED_EXTS:
            print(f"  不支持该格式！({ext})"); continue
        try:
            sc = input("  缩放倍率(%) [100]: ").strip()
            sc = float(sc) if sc else 100.0
            of = input("  基线偏移 [0]: ").strip()
            of = float(of) if of else 0.0
        except (EOFError, KeyboardInterrupt):
            print("\n取消。"); sys.exit(0)
        except ValueError:
            print("  请输入有效数字。"); continue
        inputs.append((p, sc, of))
        break

    # ---- 打底字体 ----
    lv = 1
    while True:
        print(f"\n第 {lv} 级打底字体（Y 结束）:")
        try:
            p = input("  路径: ").strip().strip('"').strip("'")
        except (EOFError, KeyboardInterrupt):
            print("\n取消。"); sys.exit(0)
        if p.upper() == "Y":
            if lv == 1:
                print("  请至少输入一个打底字体。"); continue
            break
        if not p:
            print("  路径不能为空。"); continue
        ext = Path(p).suffix.lower()
        if ext in COLLECTION_EXTS:
            print("  请先将字体集解包 (TTC/OTC)。"); continue
        if ext not in SUPPORTED_EXTS:
            print(f"  不支持该格式！({ext})"); continue
        try:
            sc = input("  缩放倍率(%) [100]: ").strip()
            sc = float(sc) if sc else 100.0
            of = input("  基线偏移 [0]: ").strip()
            of = float(of) if of else 0.0
        except (EOFError, KeyboardInterrupt):
            print("\n取消。"); sys.exit(0)
        except ValueError:
            print("  请输入有效数字。"); continue
        inputs.append((p, sc, of))
        lv += 1

    # ---- 加载 ----
    print("\n加载字体...")
    loaded = []
    for path, sc, of in inputs:
        ext = Path(path).suffix.lower()
        print(f"  {path}")
        f = load_font(path)
        # 缩放倍率 + 基线偏移 (Logic.md 通用步骤: 关于 (0,0) 点)
        if sc != 100.0 or of != 0.0:
            print(f"    缩放 {sc}% / 基线偏移 {of:+.1f}")
            apply_scale_offset(f, sc, of)
        loaded.append((f, sc, of))
        print(f"    {type_label(f)}, {len(f.getGlyphOrder())} 字形")

    # ---- 兼容性检查 ----
    print("\n兼容性检查...")
    from FontMerger.core.merger import check_compatibility
    for i, (bf, bs, bo) in enumerate(loaded[1:], 1):
        ok, warnings = check_compatibility(loaded[i-1][0], bf)
        if warnings:
            for w in warnings:
                print(f"  [警告] {w}")
        if not ok:
            print(f"\n  第 {i} 级打底字体与主字体不兼容。")
            ans = input("  是否继续? (y/N): ").strip().lower()
            if ans != 'y':
                print("  已取消。"); sys.exit(0)

    # ---- 逐级合并 ----
    print("\n开始合并...")
    mo = loaded[0][0]
    cr = get_copyrights(*[f for f, _, _ in loaded])
    fn = get_family(mo)
    cur = copy.deepcopy(mo)

    for i, (bf, bs, bo) in enumerate(loaded[1:], 1):
        print(f"\n--- 第 {i} 级 ---")
        cur = merger.merge_two(cur, bf)

    # ---- 名称 ----
    print("\n处理名称...")
    cur = apply_naming(cur, fn, cr)

    # ---- 保存 ----
    mp = inputs[0][0]
    md = os.path.dirname(os.path.abspath(mp))
    mn = os.path.splitext(os.path.basename(mp))[0]
    de = ".otf" if is_cff(cur) else ".ttf"
    do = os.path.join(md, f"{mn}_mod{de}")

    try:
        out = input(f"\n输出路径 [{do}]: ").strip().strip('"').strip("'")
    except (EOFError, KeyboardInterrupt):
        print("\n取消。"); sys.exit(0)
    if not out:
        out = do

    try:
        # 统一走保存防护: 清 flavor + 校验 sfnt 魔数 (避免写出"名为 .ttf 的 woff2")
        _, magic = save_font(cur, out, flavor=default_flavor_for(out))
        print(f"\n完成! {out}  [{magic!r}]")
        print(f"  {type_label(cur)}, {len(cur.getGlyphOrder())} 字形")
    except Exception as e:
        print(f"\n保存失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run()
