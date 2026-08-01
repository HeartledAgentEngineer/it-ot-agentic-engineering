# -*- mode: python ; coding: utf-8 -*-


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
        'groq',
        'openai',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # tkinter wird nicht mehr benutzt (Hotkey-Auswahl liegt im Tray-Menü) —
    # ohne diesen Ausschluss packt PyInstaller es trotzdem mit ein.
    excludes=['tkinter', 'tkinter.filedialog', 'tkinter.font'],
    noarchive=False,
    optimize=0,
)

# UAC-Manifest für Admin-Rechte (keyboard-Hook benötigt das)
# Siehe: https://pyinstaller.org/en/stable/man/EXE.html#cmdoption-uac-admin
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