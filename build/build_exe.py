#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyInstaller 打包脚本 — 把本仓库的 CLI 打成单文件可执行程序。

用法::

    python3 build/build_exe.py                 # 按 build/font_merger.spec 构建
    python3 build/build_exe.py --check         # 只做预检, 不构建
    python3 build/build_exe.py --install       # 缺 PyInstaller 时先 pip install
    python3 build/build_exe.py --clean         # 构建前清 PyInstaller 缓存

入口: 仓库根目录 FontMerging.py (交互式 CLI); 包: FontMerger/。
产物: build/dist/FontMerger(.exe); 中间文件: build/build/ (两者均被 .gitignore 忽略)。

注意: PyInstaller 不能跨平台交叉编译 —— 要 Windows 的 .exe 必须在 Windows 上运行
本脚本 (或 Windows CI); 在 WSL/Linux 上构建得到的是 Linux 可执行文件, 仅用于验证
依赖收集是否完整。
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ENTRY = os.path.join(REPO, "FontMerging.py")
SPEC = os.path.join(HERE, "font_merger.spec")
#: 产物与中间文件都放在 build/ 下 (被 .gitignore 的 build/*/ 覆盖)
DIST = os.path.join(HERE, "dist")
WORK = os.path.join(HERE, "build")


def _pyinstaller_version():
    """返回 PyInstaller 版本号; 未安装返回 None"""
    try:
        import PyInstaller
        return PyInstaller.__version__
    except ImportError:
        return None


def check(verbose=True):
    """预检: 入口 / spec / 包目录 / PyInstaller 是否就位; 全部通过返回 True"""
    ok = True
    items = (
        ("入口 FontMerging.py", ENTRY),
        ("spec font_merger.spec", SPEC),
        ("包 FontMerger/__init__.py", os.path.join(REPO, "__init__.py")),
    )
    for label, path in items:
        exists = os.path.exists(path)
        ok = ok and exists
        if verbose:
            print("  [预检] %-26s %-4s %s" % (label, "OK" if exists else "缺失", path))
    version = _pyinstaller_version()
    ok = ok and version is not None
    if verbose:
        hint = ("v" + version) if version else "未安装 (pip install pyinstaller, 或加 --install)"
        print("  [预检] %-26s %s" % ("PyInstaller", hint))
        print("  [预检] %-26s %s" % ("平台", sys.platform))
        if not sys.platform.startswith("win"):
            print("  [预检] 提示: 当前不是 Windows, 产物不是 .exe (PyInstaller 不能交叉编译)")
    return ok


def build(clean=False, install=False):
    """调用 PyInstaller 构建; 返回子进程退出码"""
    if _pyinstaller_version() is None:
        if not install:
            print("  [错误] 未安装 PyInstaller: pip install pyinstaller (或重跑加 --install)")
            return 1
        print("  [安装] pip install pyinstaller ...")
        code = subprocess.call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        if code != 0:
            print("  [错误] PyInstaller 安装失败")
            return code
    if not check():
        print("  [错误] 预检未通过, 取消构建")
        return 1
    cmd = [sys.executable, "-m", "PyInstaller", SPEC,
           "--distpath", DIST, "--workpath", WORK, "--noconfirm"]
    if clean:
        cmd.append("--clean")
    print("  [构建] " + " ".join(cmd))
    code = subprocess.call(cmd, cwd=REPO)
    if code == 0:
        exe = os.path.join(DIST, "FontMerger.exe" if sys.platform.startswith("win") else "FontMerger")
        if os.path.exists(exe):
            print("  [完成] 产物: %s (%.1f MB)" % (exe, os.path.getsize(exe) / 1024.0 / 1024.0))
        else:
            print("  [完成] 构建成功, 但未找到预期产物: %s" % exe)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description="PyInstaller 打包 FontMerger 单文件可执行程序")
    parser.add_argument("--check", action="store_true", help="只做预检, 不构建")
    parser.add_argument("--install", action="store_true", help="缺 PyInstaller 时先 pip install")
    parser.add_argument("--clean", action="store_true", help="构建前清 PyInstaller 缓存")
    args = parser.parse_args(argv)
    if args.check:
        return 0 if check() else 1
    return build(clean=args.clean, install=args.install)


if __name__ == "__main__":
    sys.exit(main())
