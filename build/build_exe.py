#!/usr/bin/env python3
"""PyInstaller 构建脚本 — 将 FontMerger 打包为独立 exe"""

import os, sys, subprocess

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_dir = os.path.dirname(os.path.dirname(_script_dir))
_merge_fonts_py = os.path.join(_project_dir, "merge_fonts.py")
_spec_file = os.path.join(_script_dir, "merge_fonts.spec")

# 确保 PyInstaller 已安装
try:
    import PyInstaller
except ImportError:
    print("Installing PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "FontMerger",
        "--add-data", f"{os.path.join(_project_dir, 'FontMerger')};FontMerger",
        "--hidden-import", "fontTools",
        "--hidden-import", "fontTools.ttLib",
        "--hidden-import", "fontTools.cffLib",
        "--hidden-import", "fontTools.merge",
        "--hidden-import", "fontTools.pens.t2CharStringPen",
        "--hidden-import", "fontTools.pens.ttGlyphPen",
        "--hidden-import", "fontTools.pens.qu2cuPen",
        "--hidden-import", "fontTools.pens.cu2quPen",
        "--hidden-import", "fontTools.fontBuilder",
        "--hidden-import", "fontTools.varLib.instancer",
        "--hidden-import", "afdko",
        "--hidden-import", "xml.etree.ElementTree",
        "--hidden-import", "brotli",
        "--hidden-import", "zopfli",
        "--collect-submodules", "fontTools",
        "--collect-submodules", "afdko",
        "--clean",
        _merge_fonts_py,
    ]

    print("Building FontMerger.exe...")
    subprocess.check_call(cmd, cwd=_script_dir)
    print(f"\nBuild complete! Output in: {os.path.join(_script_dir, 'dist')}")


if __name__ == "__main__":
    build()
