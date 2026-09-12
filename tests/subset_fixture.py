#!/usr/bin/env python3
"""测试夹具: 把本地可变字体按 unicode-range 切成"同源分片"。

模拟真实 webfont 分片的结构: pyftsubset + post 3.0 (无字形名) + woff2,
保留 gvar/HVAR/VVAR 与全部布局特性。合并测试与冲突测试共用。

字体不存在时返回 None, 调用方 SKIP。
"""
import functools
import os
import subprocess
import sys
import tempfile

_CACHE = {}


def make_subsets(src_path, n=3, out_dir=None, flavor="woff2"):
    """按 cps[i::n] 把 src_path 切成 n 个分片, 返回路径列表 (按序号)"""
    from fontTools.ttLib import TTFont

    out_dir = out_dir or tempfile.mkdtemp(prefix="fm_subsets_")
    os.makedirs(out_dir, exist_ok=True)
    cps = sorted(TTFont(src_path).getBestCmap())
    ext = ".woff2" if flavor == "woff2" else ".ttf"
    paths = []
    for i in range(n):
        chunk = cps[i::n]
        out = os.path.join(out_dir, "sub-%03d%s" % (i, ext))
        paths.append(out)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            continue
        args = [sys.executable, "-m", "fontTools.subset", src_path,
                "--unicodes=" + ",".join("U+%04X" % c for c in chunk),
                "--layout-features=*", "--no-hinting", "--desubroutinize",
                "--output-file=" + out]
        if flavor:
            args.append("--flavor=" + flavor)
        proc = subprocess.run(args, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError("pyftsubset 失败: " + proc.stderr[-1500:])
    return paths


def cached_subsets(src_path, n=3, flavor="woff2"):
    """生成一次后缓存 (同一测试进程内复用); 字体不存在返回 None"""
    if not src_path or not os.path.exists(src_path):
        return None
    key = (src_path, n, flavor)
    if key not in _CACHE:
        _CACHE[key] = make_subsets(src_path, n=n, flavor=flavor)
    return list(_CACHE[key])


def make_rich_vf(src_path, out_dir=None, mark_glyphs=40):
    """给可变字体补上"容易被合并搞坏"的两样东西后另存, 返回路径。

      * GDEF MarkGlyphSetsDef 追加一个新 Coverage, 并把某个 GPOS lookup 的
        LookupFlag bit4 (UseMarkFilteringSet) 指向它 —— 合并后索引必须重映射;
      * GSUB FeatureVariations (rvrn) —— FeatureList 重排后索引必须重写。

    两者都是 fontTools 官方 API 生成的合法结构:
      otTables.MarkGlyphSetsDef / varLib.featureVars.addFeatureVariations。
    """
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables import otTables as ot
    from fontTools.varLib.featureVars import addFeatureVariations

    font = TTFont(src_path)
    order = font.getGlyphOrder()
    cmap = font.getBestCmap()

    # ---- MarkGlyphSetsDef + LookupFlag bit4 ----
    gdef = font["GDEF"].table
    if getattr(gdef, "MarkGlyphSetsDef", None) is None:
        mgs = ot.MarkGlyphSetsDef()
        mgs.MarkSetTableFormat = 1
        mgs.Coverage = []
        mgs.MarkSetCount = 0
        gdef.MarkGlyphSetsDef = mgs
    mgs = gdef.MarkGlyphSetsDef
    names = [cmap[cp] for cp in sorted(cmap)[:mark_glyphs] if cmap[cp] in order]
    cov = ot.Coverage()
    cov.glyphs = sorted(set(names), key=order.index)
    mgs.Coverage.append(cov)                     # 追加 (不是替换!)
    mgs.MarkSetCount = len(mgs.Coverage)
    gdef.Version = max(gdef.Version or 0x00010000, 0x00010002)

    if "GPOS" in font and font["GPOS"].table.LookupList:
        lk = font["GPOS"].table.LookupList.Lookup[0]
        lk.LookupFlag = (getattr(lk, "LookupFlag", 0) or 0) | 0x0010
        lk.MarkFilteringSet = mgs.MarkSetCount - 1

    # ---- FeatureVariations (rvrn): 任意两个存在字形 ----
    glyphs = [cmap[cp] for cp in sorted(cmap) if cmap[cp] in order]
    src_gn = glyphs[0]
    dst_gn = next(g for g in glyphs[1:] if g != src_gn)
    addFeatureVariations(font, [([{"wght": (0.5, 1.0)}], {src_gn: dst_gn})],
                         featureTag="rvrn")

    out_dir = out_dir or tempfile.mkdtemp(prefix="fm_rich_")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "rich-vf.ttf")
    font.save(out)
    return out


def cached_rich_subsets(src_path, n=2, flavor="woff2"):
    """(rich VF 路径, 其分片列表); 字体不存在返回 (None, None)"""
    if not src_path or not os.path.exists(src_path):
        return None, None
    key = ("rich", src_path, n, flavor)
    if key not in _CACHE:
        rich = make_rich_vf(src_path)
        _CACHE[key] = (rich, make_subsets(rich, n=n, flavor=flavor))
    rich, paths = _CACHE[key]
    return rich, list(paths)
