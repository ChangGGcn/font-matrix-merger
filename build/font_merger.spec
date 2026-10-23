# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — FontMerger 单文件打包。

入口是仓库根的 FontMerging.py, 包是 FontMerger/ (通过 pathex 让静态分析找到);
不收集 afdko —— 库本身不 import 它, 只有旧管线才需要。

用法::

    python3 build/build_exe.py                       # 推荐 (带预检与产物大小)
    python3 -m PyInstaller build/font_merger.spec    # 手动构建
"""
import os

from PyInstaller.utils.hooks import collect_submodules

# SPECPATH 由 PyInstaller 注入 (spec 所在目录); 手动 exec 时退化为本文件目录
try:
    _HERE = os.path.abspath(SPECPATH)      # noqa: F821  (PyInstaller 注入)
except NameError:                          # pragma: no cover
    _HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_ENTRY = os.path.join(_REPO, "FontMerging.py")

#: fontTools 很多子模块是运行时按需 import 的, 必须显式收集;
#: brotli / zopfli 用于 WOFF/WOFF2 编解码
_hidden = collect_submodules("fontTools") + [
    "brotli", "zopfli", "xml.etree.ElementTree",
]

a = Analysis(
    [_ENTRY],
    pathex=[_REPO],
    binaries=[],
    datas=[],
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="FontMerger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
