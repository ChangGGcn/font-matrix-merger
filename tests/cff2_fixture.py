#!/usr/bin/env python3
"""测试夹具: 把 CFF2 可变字体切成两个"跨设计空间"的小子集 (阶段 4)。

main 与 base 字形集不相交 (合并时 base 的字形全是新增), 且 base 的 fvar 范围/
默认值被改过 —— 于是两者的归一化空间不同, 必须走跨设计空间合成。
字体不存在时返回 None, 调用方 SKIP。
"""
import os
import subprocess
import sys
import tempfile

_CACHE = {}


def _subset(src, out, unicodes, features="kern,liga,mark,mkmk"):
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return
    proc = subprocess.run(
        [sys.executable, "-m", "fontTools.subset", src,
         "--unicodes=" + unicodes, "--layout-features=" + features,
         "--output-file=" + out],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("pyftsubset 失败: " + proc.stderr[-1500:])


def make_cff2_pair(src_path, out_dir=None):
    """返回 (main_path, base_path)"""
    from fontTools.ttLib import TTFont

    out_dir = out_dir or tempfile.mkdtemp(prefix="fm_cff2_")
    os.makedirs(out_dir, exist_ok=True)
    main_out = os.path.join(out_dir, "main-cff2.otf")
    base_out = os.path.join(out_dir, "base-cff2.otf")
    _subset(src_path, main_out, "U+0041-005A,U+0061-007A")          # 拉丁字母
    _subset(src_path, base_out, "U+0020-0040,U+00C0-00FF")          # 标点 + 重音
    if os.path.getmtime(base_out) < os.path.getmtime(src_path) or not os.path.exists(base_out + ".fixed"):
        font = TTFont(base_out)
        for axis in font["fvar"].axes:
            if axis.axisTag == "wght":
                axis.minValue, axis.defaultValue, axis.maxValue = 150, 300, 900
            elif axis.axisTag == "opsz":
                axis.minValue, axis.defaultValue, axis.maxValue = 8, 14, 48
        font.save(base_out)
        open(base_out + ".fixed", "w").close()
    return main_out, base_out


def cached_cff2_pair(src_path, out_dir=None):
    """生成一次后缓存 (同一测试进程内复用); 字体不存在返回 None"""
    if not src_path or not os.path.exists(src_path):
        return None
    if src_path not in _CACHE:
        _CACHE[src_path] = make_cff2_pair(src_path, out_dir)
    return _CACHE[src_path]
