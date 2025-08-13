# PyInstaller hook for MediaPipe
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os
import mediapipe

# Collect all MediaPipe data files
datas = collect_data_files('mediapipe')

# Collect all MediaPipe submodules
hiddenimports = collect_submodules('mediapipe')

# Add specific MediaPipe modules that might be missed
hiddenimports.extend([
    'mediapipe.python.solutions.hands',
    'mediapipe.python.solutions.drawing_utils',
    'mediapipe.python.solution_base',
    'mediapipe.python.solutions.face_detection',
    'mediapipe.python.solutions.face_mesh',
    'mediapipe.python.solutions.pose',
    'mediapipe.python.solutions.selfie_segmentation',
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.backends',
    'matplotlib.backends.backend_tkagg',
])

# Get MediaPipe installation path
mediapipe_path = os.path.dirname(mediapipe.__file__)

# Add the modules directory explicitly
modules_path = os.path.join(mediapipe_path, 'modules')
if os.path.exists(modules_path):
    datas.append((modules_path, 'mediapipe/modules'))
