# -*- mode: python ; coding: utf-8 -*-

import os
import re

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

# Versi diambil dari animetracker/__init__.py (satu sumber) dan ditanam ke metadata .exe
# (klik kanan -> Properties -> Details).
with open(os.path.join(SPECPATH, 'animetracker', '__init__.py'), encoding='utf-8') as f:
    APP_VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)
_v = tuple(int(x) for x in (APP_VERSION.split('.') + ['0', '0', '0'])[:4])

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_v, prodvers=_v),
    kids=[
        StringFileInfo([StringTable('040904B0', [
            StringStruct('ProductName', 'Anime & Show Tracker'),
            StringStruct('FileDescription', 'Anime & Show Tracker'),
            StringStruct('FileVersion', APP_VERSION),
            StringStruct('ProductVersion', APP_VERSION),
            StringStruct('OriginalFilename', 'AnimeTracker.exe'),
        ])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])]),
    ],
)

datas = []
binaries = []
hiddenimports = ['win32api', 'win32con', 'requests', 'win11toast', 'PIL._tkinter_finder']

# customtkinter butuh file tema JSON & font-nya ikut dibundel.
for pkg in ['customtkinter', 'winrt', 'winrt.windows.data.xml.dom', 'winrt.windows.foundation',
            'winrt.windows.ui.notifications']:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ['tracker.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AnimeTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_info,
)
