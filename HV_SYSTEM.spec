# -*- mode: python ; coding: utf-8 -*-

# Fix for RecursionError: increase recursion limit
import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

# Import required for data files
import os
from pathlib import Path

# Get current directory
current_dir = os.getcwd()

a = Analysis(
    ['HV_SYSTEM.py'],
    pathex=[current_dir],
    binaries=[],
    datas=[
        ('user_manual_guides', 'user_manual_guides'),
        ('config', 'config'),
        ('utils', 'utils'),
        ('env.example', '.'),
    ],
    hiddenimports=[
        'cv2',
        'mediapipe', 
        'tkinter',
        'tkinter.scrolledtext',
        'tkinter.messagebox',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'pyautogui',
        'pynput',
        'pynput.mouse',
        'pyaudio',
        'websockets',
        'dotenv',
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.lib',
        'numpy',
        'threading',
        'asyncio',
        'queue',
        'screeninfo',
        'psutil',
        'winreg',
        'base64',
        'json',
        'time',
        'os',
        'sys',
        'webbrowser',
        'jaraco',
        'jaraco.text',
        'jaraco.functools',
        'jaraco.context',
        'jaraco.classes',
        'pkg_resources',
        'setuptools',
        'importlib_metadata',
        'zipp',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'pandas',
        'pytest',
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
    name='HV_SYSTEM_v2.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX to avoid compression issues
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging if needed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='app_logo.ico',  # Commented out - no icon file available
)
