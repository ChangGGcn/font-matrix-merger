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
