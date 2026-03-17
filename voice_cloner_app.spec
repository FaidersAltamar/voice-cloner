# PyInstaller spec para generar .exe
# Ejecutar: pyinstaller voice_cloner_app.spec
# Requiere: pip install pyinstaller

# Nota: El .exe incluirá Python y dependencias. RVC (rvc-no-gui) debe estar
# en la misma carpeta que el .exe o se usará la ruta relativa al ejecutable.

a = Analysis(
    ['voice_cloner_app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['pydub', 'tkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['flask', 'werkzeug'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VoiceCloner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
