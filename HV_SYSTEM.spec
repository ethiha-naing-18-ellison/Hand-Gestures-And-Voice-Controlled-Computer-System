# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

a = Analysis(
    ['HV_SYSTEM.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Project\\Hand-Gesture-Voice-Controlled-Computer-System\\hv_background.png', '.'), ('C:\\Project\\Hand-Gesture-Voice-Controlled-Computer-System\\hv_userinterface.png', '.'), ('C:\\Project\\Hand-Gesture-Voice-Controlled-Computer-System\\user_manual_guides', 'user_manual_guides'), ('C:\\Project\\Hand-Gesture-Voice-Controlled-Computer-System\\myenv\\Lib\\site-packages\\mediapipe\\modules\\hand_landmark', 'mediapipe/modules/hand_landmark'), ('C:\\Project\\Hand-Gesture-Voice-Controlled-Computer-System\\myenv\\Lib\\site-packages\\mediapipe\\modules\\palm_detection', 'mediapipe/modules\\palm_detection')],
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
    name='HV_SYSTEM',
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
    icon=['C:\\Project\\Hand-Gesture-Voice-Controlled-Computer-System\\app_logo.ico'],
)
