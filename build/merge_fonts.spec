# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FontMerger"""

import os, sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# 收集 fontTools 和 afdko 的所有子模块
fonttools_hidden = collect_submodules('fontTools')
afdko_hidden = collect_submodules('afdko')

a = Analysis(
    ['../../merge_fonts.py'],
    pathex=[],
    binaries=[],
    datas=[('../../FontMerger', 'FontMerger')],
    hiddenimports=fonttools_hidden + afdko_hidden + [
        'xml.etree.ElementTree', 'brotli', 'zopfli', 'struct',
        'copy', 'tempfile', 'atexit', 'pathlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FontMerger',
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
