# -*- mode: python ; coding: utf-8 -*-

# Fix for RecursionError: increase recursion limit
import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

# Import required for data files
import os
from pathlib import Path
import mediapipe

# Get current directory
current_dir = os.getcwd()

# Get MediaPipe installation path
mediapipe_path = os.path.dirname(mediapipe.__file__)

a = Analysis(
    ['HV_SYSTEM.py'],
    pathex=[current_dir],
    binaries=[],
    datas=[
        ('user_manual_guides', 'user_manual_guides'),
        ('config', 'config'),
        ('utils', 'utils'),
        ('env.example', '.'),
        # Include MediaPipe modules directory
        (os.path.join(mediapipe_path, 'modules'), 'mediapipe/modules'),
    ],
    hiddenimports=[
        'cv2',
        'mediapipe', 
        'mediapipe.python.solutions.hands',
        'mediapipe.python.solutions.drawing_utils',
        'mediapipe.python.solution_base',
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.backends',
        'matplotlib.backends.backend_tkagg',
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
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
    [],
    exclude_binaries=True,
    name='HV_SYSTEM_Fixed',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HV_SYSTEM_Fixed',
)
