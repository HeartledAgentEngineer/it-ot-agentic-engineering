# -*- mode: python ; coding: utf-8 -*-
# PyInstaller Build-Rezept für OrbitDesk (Standalone Windows EXE)
import os
import sys

# Basisverzeichnis
src_dir = os.path.join(SPECPATH, 'src')
sys.path.insert(0, src_dir)

a = Analysis(
    ['src/master_schalter/orbitdesk_starter.py'],
    pathex=[src_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        'master_schalter',
        'master_schalter.uebersicht',
        'master_schalter.leiste',
        'master_schalter.cli',
        'master_schalter.ziele',
        'master_schalter.kosten_budget',
        'master_schalter.sprach_zentrale',
        'master_schalter.mcp_server',
        'master_schalter.agy_senden',
        'master_schalter.assistent',
        'master_schalter.modi',
        'master_schalter.signale',
        'master_schalter.rollen',
        'master_schalter.zustand',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'tkinter',
        'tkinter.ttk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pandas', 'scipy', 'sympy', 'sklearn', 'tensorflow', 'torch',
        'matplotlib', 'cv2', 'flask', 'django', 'fastapi',
        'pytest', 'unittest',
    ],
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
    name='orbitdesk',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # Windows GUI Application (kein störendes Terminalfenster)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
