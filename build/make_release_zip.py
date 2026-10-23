#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包"仅源码"发布包 (GitHub Release asset)。

正式包只收 git **已跟踪**的 Python 运行库、CLI、根文档及 doc/ 双语技术文档。
不含测试、构建脚本、devdocs/、README 备份、字体二进制或本地配置：

    __init__.py + FontMerging.py + core/format/tables/utils 下的 *.py
    README.md + README.zh-CN.md + CHANGELOG.md + 原 LICENSE
    doc/ 下的公开 *.md

默认包内目录为 FontMerger，解压后可直接从父目录 import FontMerger。

用法::

    python3 build/make_release_zip.py                  # → dist/font-matrix-merger-v<版本>.zip
    python3 build/make_release_zip.py --out /tmp/x.zip # 指定输出路径
    python3 build/make_release_zip.py --root pkg       # 指定包内顶层目录名
    python3 build/make_release_zip.py --preview        # 审核包另收未跟踪 doc/*.md

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

#: 仅取仓库根文档，保留项目原有授权声明。
KEEP_NAMES = ("README.md", "README.zh-CN.md", "CHANGELOG.md", "LICENSE")
#: 运行库与 CLI 白名单；测试、构建工具及内部文档不进入发布资产。
ROOT_MODULES = ("__init__.py", "FontMerging.py")
PACKAGE_DIRS = ("core/", "format/", "tables/", "utils/")

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


def collect_files(preview=False):
    """按白名单收集文件；preview 仅额外收未跟踪的公开 Markdown。"""
    tracked = _run("git", "ls-files").splitlines()
    candidates = set(tracked)
    if preview:
        candidates.update(_run("git", "ls-files", "--others",
                               "--exclude-standard", "--", "doc").splitlines())
    keep = sorted(f for f in candidates
                  if f in ROOT_MODULES or f in KEEP_NAMES
                  or (f.endswith(".py") and f.startswith(PACKAGE_DIRS)
                      and "__pycache__" not in f.split("/"))
                  or (f.startswith("doc/") and f.endswith(".md")
                      and not any(part.startswith(".")
                                  for part in f.split("/"))))
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
    parser.add_argument("--root", help="包内顶层目录名 (缺省 FontMerger)")
    parser.add_argument("--quiet", action="store_true", help="只输出结果行")
    parser.add_argument("--preview", action="store_true",
                        help="审核预览：另收未跟踪 doc/*.md，不暂存或提交")
    args = parser.parse_args(argv)

    version = read_version()
    root = args.root or "FontMerger"
    suffix = "-review" if args.preview else ""
    out = args.out or os.path.join(
        REPO, "dist", "font-matrix-merger-v%s%s.zip" % (version, suffix))
    files = collect_files(preview=args.preview)
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
