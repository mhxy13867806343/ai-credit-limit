# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/hooksvue/Desktop/ai-credit-limit/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    name='AICreditLimit',
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
    icon=['/Users/hooksvue/Desktop/ai-credit-limit/assets/icon.icns'],
)
app = BUNDLE(
    exe,
    name='AICreditLimit.app',
    icon='/Users/hooksvue/Desktop/ai-credit-limit/assets/icon.icns',
    bundle_identifier='com.aicreditlimit.app',
)
