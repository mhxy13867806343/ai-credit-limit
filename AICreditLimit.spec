# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/hooksvue/Desktop/ai-credit-limit/main.py'],
    pathex=['/Users/hooksvue/Desktop/ai-credit-limit'],
    binaries=[],
    datas=[('/Users/hooksvue/Desktop/ai-credit-limit/ai_credit_limit', 'ai_credit_limit')],
    hiddenimports=['ai_credit_limit', 'ai_credit_limit.app', 'ai_credit_limit.config', 'ai_credit_limit.detectors', 'ai_credit_limit.models', 'ai_credit_limit.parsers', 'ai_credit_limit.theme', 'ai_credit_limit.ui_tray', 'ai_credit_limit.ui_utils', 'ai_credit_limit.ui_auto_refresh', 'ai_credit_limit.ui_usage_card', 'ai_credit_limit.ui_dialogs', 'ai_credit_limit.codex_account', 'ai_credit_limit.codex_sessions', 'ai_credit_limit.antigravity_account', 'ai_credit_limit.claude_sessions'],
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
