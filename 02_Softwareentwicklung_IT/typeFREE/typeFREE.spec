# -*- mode: python ; coding: utf-8 -*-
# Schlankes Build-Rezept für typeFREE
# Nur die wirklich benötigten Module – kein pandas/scipy/lxml-Ballast.

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
        'groq',
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