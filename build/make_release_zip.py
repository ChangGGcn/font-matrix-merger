#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包"仅源码"发布包 (GitHub Release asset)。

只收 git **已跟踪**的 Python 源码与文档, 不含任何字体二进制、PyInstaller 产物
或本地配置 (tests/local_fonts.py 之类被 .gitignore 排除的文件天然不会进来):

    *.py + README.md + README.zh-CN.md + LICENSE + CHANGELOG.md

用法::

    python3 build/make_release_zip.py                  # → dist/font-matrix-merger-v<版本>.zip
    python3 build/make_release_zip.py --out /tmp/x.zip # 指定输出路径
    python3 build/make_release_zip.py --root pkg       # 指定包内顶层目录名

版本号取自 `__init__.py` 的 `__version__`; zip 内条目时间戳固定为 HEAD 提交时间,
因此同一提交重复打包结果一致 (可复现, 便于校验 sha256)。
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
import zipfile

#: 除了 *.py 之外要收进发布包的文件 (按 basename 匹配, 只取仓库根目录的文档)
KEEP_NAMES = ("README.md", "README.zh-CN.md", "LICENSE", "CHANGELOG.md")

#: 发布包里绝不允许出现的扩展名 (防御性检查: 字体二进制与打包产物)
FORBIDDEN_EXTS = (".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2", ".eot",
                  ".dfont", ".pfb", ".pfa", ".pfr", ".bdf", ".pcf", ".ttx",
                  ".zip", ".7z", ".exe", ".dll", ".so", ".dylib", ".pyc")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def _run(*args):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True,
                          check=True).stdout


def read_version():
    """从 __init__.py 读 __version__"""
    text = open(os.path.join(REPO, "__init__.py"), encoding="utf-8").read()
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        raise SystemExit("__init__.py 里找不到 __version__")
    return match.group(1)


def collect_files():
    """按 git 跟踪清单挑出要打包的文件 (排序, 保证可复现)"""
    tracked = _run("git", "ls-files").split()
    keep = sorted(f for f in tracked
                  if f.endswith(".py") or os.path.basename(f) in KEEP_NAMES)
    bad = [f for f in keep if f.lower().endswith(FORBIDDEN_EXTS)]
    if bad:
        raise SystemExit("发布包里混入了不该有的文件: %s" % bad)
    missing = [n for n in KEEP_NAMES if n not in tracked]
    if missing:
        print("  [提示] 仓库里没有这些文件 (跳过): %s" % ", ".join(missing))
    return keep


def head_time():
    """HEAD 提交时间 (zip 内条目时间戳, 保证可复现)"""
    return time.gmtime(int(_run("git", "log", "-1", "--format=%ct", "HEAD").strip()))[:6]


def build(out_path, root, files, date_time):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in files:
            info = zipfile.ZipInfo(root + "/" + name, date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(os.path.join(REPO, name), "rb") as fh:
                zf.writestr(info, fh.read())
    return out_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="打包仅源码发布包")
    parser.add_argument("--out", help="输出路径 (缺省 dist/font-matrix-merger-v<版本>.zip)")
    parser.add_argument("--root", help="包内顶层目录名 (缺省 font-matrix-merger-<版本>)")
    parser.add_argument("--quiet", action="store_true", help="只输出结果行")
    args = parser.parse_args(argv)

    version = read_version()
    root = args.root or "font-matrix-merger-" + version
    out = args.out or os.path.join(REPO, "dist",
                                   "font-matrix-merger-v%s.zip" % version)
    files = collect_files()
    out = build(out, root, files, head_time())

    with open(out, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    size = os.path.getsize(out)
    if not args.quiet:
        print("版本:     %s" % version)
        print("包内根目录: %s/" % root)
        print("文件:     %d 个 (%d 个 .py + %d 个文档)"
              % (len(files), sum(1 for f in files if f.endswith(".py")),
                 sum(1 for f in files if not f.endswith(".py"))))
        for f in files:
            if not f.endswith(".py"):
                print("          %s" % f)
    print("输出:     %s" % out)
    print("大小:     %d 字节" % size)
    print("sha256:   %s" % digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
