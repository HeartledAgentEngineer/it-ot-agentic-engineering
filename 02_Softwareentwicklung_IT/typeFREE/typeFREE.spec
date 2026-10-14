# -*- mode: python ; coding: utf-8 -*-
# Schlankes Build-Rezept für typeFREE
# Nur die wirklich benötigten Module – kein pandas/scipy/lxml-Ballast.

# Version + Commit bei JEDEM Build frisch schreiben (CI/CD-Plan 14.10.2026): sonst rutscht
# eine liegengebliebene windows/_version_build.py aus einem alten Build in die neue EXE.
# Releases setzen TYPEFREE_VERSION (z. B. typefree-v1.2.0), sonst gilt "dev".
import os
import sys
sys.path.insert(0, os.path.join(SPECPATH, 'ci'))
import version_schreiben
version_schreiben.schreiben(os.environ.get('TYPEFREE_VERSION', 'dev'),
                            os.environ.get('TYPEFREE_COMMIT') or version_schreiben.git_commit())

a = Analysis(
    ['windows\\typefree.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'keyboard',
        'sounddevice',
        'soundfile',
        'numpy',
        'pyperclip',
        'pyautogui',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'openai',
        'version',
        '_version_build',   # vom Build erzeugt (ci/version_schreiben.py)
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # GUI-Toolkits – nicht benötigt
        'tkinter', 'PyQt5', 'PySide', 'PySide2', 'wx',
        # Datenanalyse – nicht benötigt
        'pandas', 'scipy', 'sympy', 'statsmodels',
        # Machine Learning – nicht benötigt
        'sklearn', 'tensorflow', 'torch', 'keras', 'xgboost',
        # Bilderverarbeitung (außer PIL) – nicht benötigt
        'opencv', 'matplotlib', 'plotly', 'bokeh', 'seaborn',
        # Web/Cloud SDKs – nicht benötigt
        'flask', 'django', 'fastapi', 'boto3', 'azure', 'google',
        # Datenformate – nicht benötigt
        'lxml', 'pyarrow', 'bs4', 'yaml', 'toml',
        # Tests – nicht in EXE
        'pytest', 'unittest', 'nose',
        # Sonstige
        'jupyter', 'notebook', 'ipython',
        # OpenCV-spezifisch (oft von anderen Libs hereingeholt)
        'cv2',
    ],
    noarchive=False,
    optimize=0,
)

# UAC-Manifest für Admin-Rechte (keyboard-Hook benötigt das)
a.datas += [('typeFREE.exe.manifest', '.\\typeFREE.exe.manifest', 'DATA')]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='typeFREE',
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
    uac_admin=True,
)