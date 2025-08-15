import tkinter as tk
from tkinter import scrolledtext, messagebox
import cv2
import numpy as np
import mediapipe as mp
import threading
import asyncio
import websockets
import base64
import json
import time
import os
import pyautogui
import webbrowser
from pynput.mouse import Controller, Button
from queue import Queue
import screeninfo
import sys
import HandTrackingModule as htm
import pyaudio
import pygetwindow as gw
import psutil
from PIL import Image, ImageTk
import winreg as reg

# For PDF generation:
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# Import our new configuration and utilities
from config.settings import settings, ThemeColors
from utils.logger import logger
from utils.security import security
from utils.application_finder import app_finder

# Use secure configuration instead of hardcoded values
auth_key = settings.ASSEMBLYAI_API_KEY

# Audio configuration from settings
FRAME_PER_BUFFER = settings.FRAME_PER_BUFFER
FORMAT = pyaudio.paInt16
CHANNELS = settings.AUDIO_CHANNELS
RATE = settings.AUDIO_RATE

# Initialize PyAudio
p = pyaudio.PyAudio()
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=FRAME_PER_BUFFER,
)

# WebSocket configuration from settings
URL = settings.ASSEMBLYAI_WEBSOCKET_URL

# Control variables
running_event = threading.Event()
transcription_queue = Queue()
last_transcription_time = time.time()
DEBOUNCE_DELAY = 1.0  # Debounce delay to avoid overlapping commands

# Initialize the mouse controller
mouse = Controller()


# Hand Tracking and Camera Variables
cap = None
detector = htm.handDetector(
    maxHands=settings.MAX_HANDS,
    detectionCon=settings.DETECTION_CONFIDENCE,
    trackCon=settings.TRACKING_CONFIDENCE
)
hand_running = False  # To control the start and stop functionality
hand_thread = None  # Thread for the video feed loop
frame = None  # Frame for the video display

# Smoothing variables from settings
frameR = settings.FRAME_REDUCTION
smoothening = settings.SMOOTHENING_FACTOR
plocX, plocY = 0, 0
clocX, clocY = 0, 0

# Detect screen resolution dynamically
screen = screeninfo.get_monitors()[0]
wScr, hScr = screen.width, screen.height

new_filename = ""
scrolling = False
is_selecting = False

# === Helper Function to Resolve Paths ===
def get_resource_path(relative_path):
    """Get the absolute path for bundled resources for PyInstaller compatibility."""
    try:
        base_path = sys._MEIPASS  # If running as a bundled executable
    except AttributeError:
        base_path = os.path.abspath(".")  # If running as a script
    return os.path.join(base_path, relative_path)

# === Global Paths (Fixed for PyInstaller Compatibility) ===

model_base_path = get_resource_path(os.path.join("mediapipe", "modules"))
hand_landmark_model_path = os.path.join(model_base_path, "hand_landmark")
palm_detection_model_path = os.path.join(model_base_path, "palm_detection")

# Ensure required model paths exist
if not os.path.exists(hand_landmark_model_path):
    raise FileNotFoundError(f"Hand landmark model files not found at {hand_landmark_model_path}")
if not os.path.exists(palm_detection_model_path):
    raise FileNotFoundError(f"Palm detection model files not found at {palm_detection_model_path}")

def continuous_scrolling(direction, step):
    global scrolling
    while scrolling:
        try:
            if direction == "up":
                pyautogui.scroll(step)
            elif direction == "down":
                pyautogui.scroll(-step)
            elif direction == "right":
                pyautogui.hscroll(step)
            elif direction == "left":
                pyautogui.hscroll(-step)
            time.sleep(0.1)  # Adjust delay for smoother scrolling
        except Exception as e:
            print(f"Error during scrolling: {e}")
            scrolling = False  # Stop scrolling if an error occurs



# Speech to text commands to perform actions
def perform_command(transcription):

    global scrolling

    global selection_mode

    global new_filename

    # Sanitize the input using our security module
    original_transcription = transcription
    transcription = security.sanitize_voice_command(transcription)
    
    if not transcription:
        logger.warning(f"Command blocked or invalid: {original_transcription}")
        return
    
    logger.info(f"Executing command: {transcription}")  # Use logger instead of print

    # === "Type Here" Functionality ===
    # Normalize the transcription to lower case for easier comparison
    transcription = transcription.lower()

    # === Google Search Bar Commands ===
    if any(keyword in transcription for keyword in ["search here", "type here", "type", "search"]):
        try:
            # Find the keyword used in the transcription
            for keyword in ["search here", "type here", "type", "search"]:
                if keyword in transcription:
                    # Extract text after the keyword
                    text_to_type = transcription.split(keyword, 1)[1].strip()
                    break
            else:
                text_to_type = ""

            # Validate the extracted text
            if text_to_type:
                if keyword in ["search here", "search"]:
                    # Focus on the browser's search/address bar for search commands
                    pyautogui.hotkey('ctrl', 'l')  # Shortcut to focus on the address bar
                    time.sleep(0.5)

                    # Debugging: Print the text before typing
                    print(f"Searching: {text_to_type}")

                    # Use pyautogui to type the text and press enter to search
                    pyautogui.typewrite(text_to_type)
                    pyautogui.press('enter')

                elif keyword in ["type here", "type"]:
                    # For "type here" commands, type without focusing on the search bar
                    # Debugging: Print the text before typing
                    print(f"Typing: {text_to_type}")

                    # Use pyautogui to type the text without focusing on search/address bar
                    pyautogui.typewrite(text_to_type)

            else:
                print("No valid text to type.")
        except Exception as e:
            print(f"Error in command: {e}")

    else:
        print("No command recognized for typing or searching.")

    if "show" in transcription or "enter" in transcription or "send" in transcription or "sent" in transcription:
        pyautogui.press('enter')

    # === Mouse Actions ===
    elif "double click" in transcription or "double" in transcription:
        pyautogui.click(clicks=2, interval=0.25)
    elif "click" in transcription:
        pyautogui.click()
    elif "right" in transcription and "click" in transcription:
        pyautogui.click(button="right")

    elif "new tab" in transcription or "new" and "tab" in transcription:
        pyautogui.hotkey("ctrl", "t")  # For Windows/Linux

    elif "close the tab" in transcription or "close" and "tab" in transcription:
        pyautogui.hotkey("ctrl", "w")  # For Windows/Linux

    elif "open again tab" in transcription or "open again" and "tab" in transcription or "open all tab" in transcription or "open again" and "all tab" in transcription or "restore" and "tab" in transcription or "restore" and "all tab" in transcription or "restore" and "all tabs" in transcription:
        pyautogui.hotkey("ctrl", "shift", "t")  # For Windows/Linux

    # === Browser Commands ===
    elif "open" and "chrome" in transcription or "open" and "google" in transcription:
        chrome_path = app_finder.find_application("chrome")
        if chrome_path:
            security.safe_execute_command(f'"{chrome_path}"')
        else:
            logger.error("Chrome not found on system")
    # Ensure each application, website, or tool now has "open" keyword requirement.
    elif "open" and "firefox" in transcription or "open" and "mozilla" in transcription:
        firefox_path = app_finder.find_application("firefox")
        if firefox_path:
            security.safe_execute_command(f'"{firefox_path}"')
        else:
            logger.error("Firefox not found on system")
    elif "open" and "edge" in transcription or "open" and "microsoft" in transcription:
        security.safe_execute_command('start msedge')

    # === Window and Display Controls ===
    elif "minimize" in transcription and "the window" in transcription or "minimize" in transcription and "windows" in transcription:
        pyautogui.hotkey("alt", "space")
        time.sleep(0.2)
        pyautogui.press("n")
    elif "minimize" in transcription and "window" in transcription or "minimize" in transcription and "windows" in transcription:
        pyautogui.hotkey("win", "down")  # Minimize the current window
    elif "minimize all windows" in transcription or "show desktop" in transcription:
        pyautogui.hotkey("win", "m")  # Minimize all open windows
    elif (
        ("restore" in transcription and "window" in transcription)
        or ("restore" in transcription and "windows" in transcription)
    ):
        # Restore any *minimized* windows
        pyautogui.hotkey("win", "shift", "m")
        print("Minimized windows restored.")

    elif ("maximize" in transcription and "window" in transcription):
        # Maximize the *current* active window
        # (WIN + UP is one approach; also ALT + SPACE, X can work)
        pyautogui.hotkey("win", "up")
        print("Window maximized.")

    elif "close" in transcription and "window" in transcription or "close" in transcription and "windows" in transcription:
        pyautogui.hotkey("alt", "f4")

    # === Desktop and Display Controls ===
    elif "open" in transcription and "new" and "desktop" in transcription or "open" in transcription and "new" and "desktops" in transcription or "new" and "desktop" in transcription:
        pyautogui.hotkey("win", "ctrl", "d")
    elif "switch" in transcription and "desktop" in transcription or "switch" and "desktops" in transcription:
        pyautogui.hotkey("win", "ctrl", "right")
    elif "previous" and "desktop" in transcription or "previous" and "desktops" in transcription or "old" and "desktops" in transcription or "old" and "desktops" in transcription:
        pyautogui.hotkey("win", "ctrl", "right")
    elif "close" and "desktop" in transcription or "close" and "desktops" in transcription:
        pyautogui.hotkey("win", "ctrl", "f4")

    # === Activate Selection Mode ===
    elif "select" in transcription:
        selection_mode = True
        pyautogui.keyDown('shift')  # Programmatically press Shift key
        print("Selection mode activated. Use hand gestures to select text.")

    # === Deactivate Selection Mode ===
    elif "selecting" in transcription or "stop selecting" in transcription or "stop selection" in transcription or "close selecting" in transcription or "close selection" in transcription or "stop" and "selection" in transcription or "stop" and "selecting" in transcription or "close" and "selection" in transcription or "close" and "selecting" in transcription:
        pyautogui.keyUp('shift')
        pyautogui.keyUp('shift')
        selection_mode = False
        pyautogui.keyUp('shift')  # Programmatically release Shift key
        pyautogui.keyUp('shift')
        print("Selection mode deactivated.")

        # === Copy Command ===
    elif "copy" in transcription:
        pyautogui.keyUp('shift')
        pyautogui.hotkey('ctrl', 'c')  # Simulate Ctrl + C
        print("Copied selected text.")

    # === Paste Command ===
    elif "paste" in transcription or "pase" in transcription:
        pyautogui.keyUp('shift')
        pyautogui.hotkey('ctrl', 'v')  # Simulate Ctrl + V
        print("Pasted clipboard content.")


    # === Mouse Scrolling Commands ===
    if "scroll" in transcription and "up" in transcription:
        if not scrolling:
            scrolling = True
            threading.Thread(target=continuous_scrolling, args=("up", 100), daemon=True).start()
            print("Scrolling up...")
    elif "scroll" in transcription and "down" in transcription:
        if not scrolling:
            scrolling = True
            threading.Thread(target=continuous_scrolling, args=("down", 100), daemon=True).start()
            print("Scrolling down...")
    elif "scroll" in transcription and "right" in transcription:
        if not scrolling:
            scrolling = True
            threading.Thread(target=continuous_scrolling, args=("right", 100), daemon=True).start()
            print("Scrolling right...")
    elif "scroll" in transcription and "left" in transcription:
        if not scrolling:
            scrolling = True
            threading.Thread(target=continuous_scrolling, args=("left", 100), daemon=True).start()
            print("Scrolling left...")
    elif "stop scrolling" in transcription or "scrolling" in transcription or "stop" and "scrolling" in transcription or "close" and "scrolling" in transcription:
        scrolling = False
        print("Scrolling stopped.")

    # === FILE OPERATION COMMANDS === #
    elif "open" and "explorer" in transcription or "open" and "file explorer" in transcription:
        os.system("explorer")
    elif "open" and "downloads" in transcription or "open" and "download" in transcription:
        os.startfile(os.path.join(os.environ['USERPROFILE'], 'Downloads'))
    elif "open" and "documents" in transcription or "open" and "document" in transcription:
        os.startfile(os.path.join(os.environ['USERPROFILE'], 'Documents'))
    elif "open" and "pictures" in transcription or "open" and "picture" in transcription:
        os.startfile(os.path.join(os.environ['USERPROFILE'], 'Pictures'))

    elif "create a new folder" in transcription or "new folder" in transcription or "create the new folder" in transcription or "create" and "folder" in transcription:
        # Use Ctrl + Shift + N for creating a new folder
        pyautogui.keyDown('ctrl')
        pyautogui.keyDown('shift')
        pyautogui.press('n')
        pyautogui.keyUp('shift')
        pyautogui.keyUp('ctrl')
        pyautogui.keyUp('shift')
        pyautogui.keyUp('ctrl')
        pyautogui.keyUp('shift')
        pyautogui.keyUp('ctrl')
        print("Created a new folder.")

        # === Rename File/Folder (F2) ===
    elif "rename this file" in transcription or "rename this folder" in transcription or "rename file" in transcription or "rename folder" in transcription or "rename" in transcription or "rename" and "file" in transcription or "rename" and "folder" in transcription:
            pyautogui.press('f2')

    elif "open this file" in transcription or "open the folder" in transcription or "open this folder" in transcription or "open folder" in transcription or "open file" in transcription or "open the file" in transcription or "open" and "file" in transcription or "open" and "folder" in transcription:
        pyautogui.click(clicks=2, interval=0.25)

        # === Normal Deletion ===
    elif "delete this file" in transcription or "delete this folder" in transcription or "delete folder" in transcription or "delete file" in transcription or "delete a folder" in transcription or "delete a file" in transcription or "delete this one" in transcription or "delete" and "file" in transcription or "delete" and "folder" in transcription:
        pyautogui.press('delete')


    # === APPLICATIONS == #
    elif "open" and "notepad" in transcription:
        security.safe_execute_command("notepad")
    elif "open" and "calculator" in transcription:
        security.safe_execute_command("calc")
    elif "open" and "camera" in transcription:
        security.safe_execute_command("start microsoft.windows.camera:")
    elif "open" and "calendar" in transcription:
        security.safe_execute_command("start outlookcal:")
    elif "open" and "settings" in transcription:
        security.safe_execute_command("start ms-settings:")
    elif "open" and "task manager" in transcription:
        security.safe_execute_command("taskmgr")
    elif "open" and "control panel" in transcription:
        security.safe_execute_command("control")
    elif "open" and "command prompt" in transcription or "open" and "cmd" in transcription:
        security.safe_execute_command("cmd")
    elif "open" and "powerpoint" in transcription:
        os.system("start powerpnt")
    elif "open" and "excel" in transcription:
        os.system("start excel")
    elif "open" and "word" in transcription or "open" and "microsoft word" in transcription:
        os.system("start winword")
    elif "open" and "teams" in transcription or "open" and "microsoft teams" in transcription:
        os.system("start teams")
    elif "open" and "outlook" in transcription or "open" and "email" in transcription:
        os.system("start outlook")
    elif "open" and "paint" in transcription:
        os.system("mspaint")
    elif "open" and "wordpad" in transcription or "open" and "word pad" in transcription:
        os.system("write")
    elif "open" and "snipping tool" in transcription:
        os.system("snippingtool")
    elif "open" and "spotify" in transcription:
        os.system(r'"C:\Users\<YourUsername>\AppData\Roaming\Spotify\Spotify.exe"')
    elif "open" and "vlc" in transcription or "open" and "vlc media player" in transcription:
        os.system(r'"C:\Program Files\VideoLAN\VLC\vlc.exe"')
    elif "open" and "chrome" in transcription:
        os.system(r'"C:\Program Files\Google\Chrome\Application\chrome.exe"')
    elif "open" and "firefox" in transcription:
        os.system(r'"C:\Program Files\Mozilla Firefox\firefox.exe"')
    elif "open" and "microsoft edge" in transcription or "open" and "edge" in transcription:
        os.system("start msedge")
    elif "open" and "notion" in transcription:
        os.system(r'"C:\Users\<YourUsername>\AppData\Local\Programs\Notion\Notion.exe"')
    elif "open" and "discord" in transcription:
        os.system(r'"C:\Users\<YourUsername>\AppData\Local\Discord\Update.exe --processStart Discord.exe"')
    elif "open" and "zoom" in transcription:
        os.system(r'"C:\Users\<YourUsername>\AppData\Roaming\Zoom\bin\Zoom.exe"')
    elif "open" and "steam" in transcription:
        os.system(r'"C:\Program Files (x86)\Steam\steam.exe"')
    elif "open" and "epic games" in transcription:
        os.system(r'"C:\Program Files (x86)\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe"')
    elif "open" and "adobe reader" in transcription or "open" and "pdf reader" in transcription:
        os.system(r'"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe"')
    elif "open" and "adobe photoshop" in transcription or "open" and "photoshop" in transcription:
        os.system(r'"C:\Program Files\Adobe\Adobe Photoshop 2022\Photoshop.exe"')
    elif "open" and "blender" in transcription:
        os.system(r'"C:\Program Files\Blender Foundation\Blender 3.3\blender.exe"')
    elif "open" and "visual studio" in transcription:
        os.system(r'"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\devenv.exe"')
    elif "open" and "vs code" in transcription or "open" and "visual studio code" in transcription:
        os.system(r'"C:\Users\<YourUsername>\AppData\Local\Programs\Microsoft VS Code\Code.exe"')
    elif "open" and "android studio" in transcription or "open" and "android" in transcription:
        os.system(r'"C:\Program Files\Android\Android Studio\bin\studio64.exe"')
    elif "open" and "intellij idea" in transcription or "open" and "intellij" in transcription:
        os.system(r'"C:\Program Files\JetBrains\IntelliJ IDEA 2023.2\bin\idea64.exe"')
    elif "open" and "pycharm" in transcription:
        os.system(r'"C:\Program Files\JetBrains\PyCharm 2023.2\bin\pycharm64.exe"')


     # === General PowerPoint Commands ===
    elif "open" in transcription and "powerpoint" in transcription:
        os.system("start powerpnt")
        print("PowerPoint opened.")

    elif "close" in transcription and "presentation" in transcription:
        pyautogui.hotkey('esc')
        print("Presentation closed.")

    elif "open" in transcription and "presentation" in transcription or "start" in transcription and "presentation" in transcription:
        # Starts the slideshow from the first slide (F5)
        pyautogui.press('f5')
        print("Presentation started (Slide Show).")

    elif "next slide" in transcription or ("next" in transcription and "slide" in transcription):
        # Moves forward one slide
        pyautogui.press('right')
        print("Moved to the next slide.")

    elif "previous slide" in transcription or ("previous" in transcription and "slide" in transcription):
        # Moves back one slide
        pyautogui.press('left')
        print("Moved to the previous slide.")

    elif "save presentation" in transcription or ("save" in transcription and "presentation" in transcription):
        # Saves the current PowerPoint file (Ctrl+S)
        pyautogui.hotkey('ctrl', 's')
        print("Presentation saved.")

    elif "new slide" in transcription or "new" and "slide" in transcription:
        pyautogui.hotkey('ctrl', 'm')
        print("New slide added.")

    elif "current slide" in transcription or "start from the current slide" in transcription or "starts from the current slide" in transcription:
        pyautogui.hotkey('shift', 'f5')
        print("Slideshow started from current slide.")


    elif (
        "go to slide" in transcription
        or "jump to slide" in transcription
        or ("go" in transcription and "slide" in transcription)
        or ("jump" in transcription and "slide" in transcription)
    ):
        # Extract any digits from the transcription
        # Example: "go to slide 5" => slide_number = [5]
        slide_number = [int(s) for s in transcription.split() if s.isdigit()]

        if slide_number:
            # Type the first slide number found, then press Enter
            pyautogui.typewrite(str(slide_number[0]))
            pyautogui.press("enter")
            print(f"Moved to slide {slide_number[0]}.")
        else:
            # No digit found in the command
            print("No slide number recognized in your command.")


    # === Text Formatting Commands ===

    elif (
        "bold text" in transcription
        or "make it bold" in transcription
        or "make bold" in transcription
        or ("bold" in transcription and "text" in transcription)
    ):
        pyautogui.hotkey('ctrl', 'b')
        print("Bold applied to selected text.")

    elif (
        "italicize text" in transcription
        or ("italicize" in transcription and "text" in transcription)
        or "make it italic" in transcription
    ):
        pyautogui.hotkey('ctrl', 'i')
        print("Italic applied to selected text.")

    elif (
        "underline text" in transcription
        or ("underline" in transcription and "text" in transcription)
        or "make it underline" in transcription
    ):
        pyautogui.hotkey('ctrl', 'u')
        print("Underline applied to selected text.")


    # === Other Slide Commands ===

    elif (
        "duplicate slide" in transcription
        or ("duplicate" in transcription and "slide" in transcription)
    ):
        pyautogui.hotkey('ctrl', 'd')
        print("Current slide duplicated.")

    elif (
        "delete slide" in transcription
        or ("delete" in transcription and "slide" in transcription)
    ):
        # In PowerPoint, Ctrl+Delete can delete the current slide (depending on focus)
        pyautogui.hotkey('ctrl', 'delete')
        print("Current slide deleted.")

    elif (
        "insert picture" in transcription
        or ("insert" in transcription and "picture" in transcription)
    ):
        # Opens Insert Picture dialog: Alt+N, P in PowerPoint
        pyautogui.hotkey('alt', 'n', 'p')
        print("Insert picture dialog opened.")

    elif (
        "insert text box" in transcription
        or ("insert" in transcription and "text box" in transcription)
    ):
        # Opens Insert Text Box tool: Alt+N, X in PowerPoint
        pyautogui.hotkey('alt', 'n', 'x')
        print("Text box inserted.")


    # === System Controls ===
    elif "shut down" in transcription and "laptop" in transcription:
        if security.safe_execute_command("shutdown /s /t 1"):
            logger.info("System shutdown initiated")
    elif "restart" in transcription and "laptop" in transcription:
        if security.safe_execute_command("shutdown /r /t 1"):
            logger.info("System restart initiated")
    elif "lock" in transcription:
        if security.safe_execute_command("rundll32.exe user32.dll,LockWorkStation"):
            logger.info("System locked")
    elif "sleep" in transcription and "laptop" in transcription:
        if security.safe_execute_command("rundll32.exe powrprof.dll,SetSuspendState 0,1,0"):
            logger.info("System sleep initiated")
    elif "log off" in transcription or "sign out" in transcription and "laptop" in transcription:
        if security.safe_execute_command("shutdown -l"):
            logger.info("User logoff initiated")

    # === Volume and Brightness Controls ===
    elif "volume up" in transcription or ("increase" in transcription and "volume" in transcription):
        for _ in range(10):  # Loop 10 times to increase the volume by 10 steps
            pyautogui.press("volumeup")
    elif "volume down" in transcription or ("reduce" in transcription and "volume" in transcription):
        for _ in range(10):  # Loop 10 times to decrease the volume by 10 steps
            pyautogui.press("volumedown")
    elif "mute" in transcription and "volume" in transcription:
        pyautogui.press("volumemute")

    # # # # # === BROWSING AND OPENING WEBSITES AND WEB-APPLICATIONS === # # # # # 

    # === Browser and Website Commands ===
    elif "open" and "youtube" in transcription:
        webbrowser.open("https://www.youtube.com")
        print("Opened YouTube.")
    elif "open" and "gmail" in transcription or "open" and "email" in transcription:
        webbrowser.open("https://mail.google.com")
        print("Opened Gmail.")
    elif "open" and "google drive" in transcription or "open" and "drive" in transcription:
        webbrowser.open("https://drive.google.com")
        print("Opened Google Drive.")
    elif "open" and "google maps" in transcription or "open" and "maps" in transcription:
        webbrowser.open("https://maps.google.com")
        print("Opened Google Maps.")
    elif "open" and "google docs" in transcription or "open" and "docs" in transcription:
        webbrowser.open("https://docs.google.com")
        print("Opened Google Docs.")
    elif "open" and "google sheets" in transcription or "open" and "sheets" in transcription:
        webbrowser.open("https://sheets.google.com")
        print("Opened Google Sheets.")
    elif "open" and "google slides" in transcription or "open" and "slides" in transcription:
        webbrowser.open("https://slides.google.com")
        print("Opened Google Slides.")
    elif "open" and "openai" in transcription or "open" and "chatgpt" in transcription or "open" and "open ai" in transcription:
        webbrowser.open("https://chat.openai.com")
        print("Opened OpenAI ChatGPT.")
    elif "open" and "linkedin" in transcription:
        webbrowser.open("https://www.linkedin.com")
        print("Opened LinkedIn.")
    elif "open" and "facebook" in transcription:
        webbrowser.open("https://www.facebook.com")
        print("Opened Facebook.")
    elif "open" and "twitter" in transcription or "open" and "x" in transcription:
        webbrowser.open("https://twitter.com")
        print("Opened Twitter.")
    elif "open" and "instagram" in transcription:
        webbrowser.open("https://www.instagram.com")
        print("Opened Instagram.")
    elif "open" and "reddit" in transcription:
        webbrowser.open("https://www.reddit.com")
        print("Opened Reddit.")
    elif "open" and "amazon" in transcription:
        webbrowser.open("https://www.amazon.com")
        print("Opened Amazon.")
    elif "open" and "flipkart" in transcription:
        webbrowser.open("https://www.flipkart.com")
        print("Opened Flipkart.")
    elif "open" and "alibaba" in transcription:
        webbrowser.open("https://www.alibaba.com")
        print("Opened Alibaba.")
    elif "open" and "noon" in transcription:
        webbrowser.open("https://www.noon.com")
        print("Opened Noon.")
    elif "open" and "ebay" in transcription or "open" and "e-bay" in transcription:
        webbrowser.open("https://www.ebay.com")
        print("Opened eBay.")
    elif "open" and "airbnb" in transcription:
        webbrowser.open("https://www.airbnb.com")
        print("Opened Airbnb.")
    elif "open" and "expedia" in transcription:
        webbrowser.open("https://www.expedia.com")
        print("Opened Expedia.")
    elif "open" and "imdb" in transcription:
        webbrowser.open("https://www.imdb.com")
        print("Opened IMDb.")
    elif "open" and "rotten tomatoes" in transcription:
        webbrowser.open("https://www.rottentomatoes.com")
        print("Opened Rotten Tomatoes.")
    elif "open" and "crunchyroll" in transcription or "open" and "anime" in transcription:
        webbrowser.open("https://www.crunchyroll.com")
        print("Opened Crunchyroll.")
    elif "open" and "netflix" in transcription or "open" and "movies" in transcription:
        webbrowser.open("https://www.netflix.com")
        print("Opened Netflix.")
    elif "open" and "spotify" in transcription or "open" and "music" in transcription:
        webbrowser.open("https://open.spotify.com")
        print("Opened Spotify.")
    elif "open" and "hulu" in transcription:
        webbrowser.open("https://www.hulu.com")
        print("Opened Hulu.")
    elif "open" and "disney plus" in transcription or "open" and "disney+" in transcription:
        webbrowser.open("https://www.disneyplus.com")
        print("Opened Disney+.")
    elif "open" and "prime video" in transcription or "open" and "amazon prime" in transcription:
        webbrowser.open("https://www.primevideo.com")
        print("Opened Prime Video.")
    elif "open" and "zoom" in transcription:
        webbrowser.open("https://zoom.us")
        print("Opened Zoom.")
    elif "open" and "microsoft teams" in transcription or "open" and "teams" in transcription:
        webbrowser.open("https://teams.microsoft.com")
        print("Opened Microsoft Teams.")
    elif "open" and "slack" in transcription:
        webbrowser.open("https://slack.com")
        print("Opened Slack.")
    elif "open" and "trello" in transcription:
        webbrowser.open("https://trello.com")
        print("Opened Trello.")
    elif "open" and "notion" in transcription:
        webbrowser.open("https://www.notion.so")
        print("Opened Notion.")
    elif "open" and "asana" in transcription:
        webbrowser.open("https://asana.com")
        print("Opened Asana.")
    elif "open" and "khan academy" in transcription:
        webbrowser.open("https://www.khanacademy.org")
        print("Opened Khan Academy.")
    elif "open" and "udemy" in transcription:
        webbrowser.open("https://www.udemy.com")
        print("Opened Udemy.")
    elif "open" and "coursera" in transcription or "open" and "moocs" in transcription:
        webbrowser.open("https://www.coursera.org")
        print("Opened Coursera.")
    elif "open" and "edx" in transcription:
        webbrowser.open("https://www.edx.org")
        print("Opened edX.")
    elif "open" and "medium" in transcription:
        webbrowser.open("https://medium.com")
        print("Opened Medium.")
    elif "open" and "quora" in transcription:
        webbrowser.open("https://www.quora.com")
        print("Opened Quora.")
    elif "open" and "stackoverflow" in transcription or "open" and "stack overflow" in transcription:
        webbrowser.open("https://stackoverflow.com")
        print("Opened Stack Overflow.")
    elif "open" and "github" in transcription or "open" and "git hub" in transcription:
        webbrowser.open("https://github.com")
        print("Opened GitHub.")
    elif "open" and "gitlab" in transcription:
        webbrowser.open("https://gitlab.com")
        print("Opened GitLab.")
    elif "open" and "bitbucket" in transcription:
        webbrowser.open("https://bitbucket.org")
        print("Opened Bitbucket.")
    elif "open" and "leetcode" in transcription:
        webbrowser.open("https://leetcode.com")
        print("Opened LeetCode.")
    elif "open" and "hackerrank" in transcription:
        webbrowser.open("https://www.hackerrank.com")
        print("Opened HackerRank.")
    elif "open" and "geeksforgeeks" in transcription or "open" and "gfg" in transcription:
        webbrowser.open("https://www.geeksforgeeks.org")
        print("Opened GeeksforGeeks.")
    elif "open" and "dev" in transcription or "open" and "dev.to" in transcription:
        webbrowser.open("https://dev.to")
        print("Opened Dev.to.")
    elif "open" and "kaggle" in transcription:
        webbrowser.open("https://www.kaggle.com")
        print("Opened Kaggle.")
    elif "open" and "datacamp" in transcription or "open" and "data camp" in transcription:
        webbrowser.open("https://www.datacamp.com")
        print("Opened DataCamp.")
    elif "open" and "power bi" in transcription:
        webbrowser.open("https://powerbi.microsoft.com")
        print("Opened Power BI.")
    elif "open" and "tableau" in transcription:
        webbrowser.open("https://www.tableau.com")
        print("Opened Tableau.")
    elif "open" and "behance" in transcription:
        webbrowser.open("https://www.behance.net")
        print("Opened Behance.")
    elif "open" and "dribbble" in transcription:
        webbrowser.open("https://dribbble.com")
        print("Opened Dribbble.")
    elif "open" and "zomato" in transcription:
        webbrowser.open("https://www.zomato.com")
        print("Opened Zomato.")
    elif "open" and "swiggy" in transcription:
        webbrowser.open("https://www.swiggy.com")
        print("Opened Swiggy.")
    elif "open" and "dominos" in transcription:
        webbrowser.open("https://www.dominos.com")
        print("Opened Domino's.")
    elif "open" and "the verge" in transcription:
        webbrowser.open("https://www.theverge.com")
        print("Opened The Verge.")
    elif "open" and "wired" in transcription:
        webbrowser.open("https://www.wired.com")
        print("Opened Wired.")
    elif "open" and "techcrunch" in transcription:
        webbrowser.open("https://techcrunch.com")
        print("Opened TechCrunch.")
    elif "open" and "indiegogo" in transcription:
        webbrowser.open("https://www.indiegogo.com")
        print("Opened Indiegogo.")
    elif "open" and "kickstarter" in transcription:
        webbrowser.open("https://www.kickstarter.com")
        print("Opened Kickstarter.")
    elif "open" and "edureka" in transcription:
        webbrowser.open("https://www.edureka.co")
        print("Opened Edureka.")
    elif "open" and "pluralsight" in transcription:
        webbrowser.open("https://www.pluralsight.com")
        print("Opened Pluralsight.")
    elif "open" and "byju's" in transcription or "open" and "byjus" in transcription:
        webbrowser.open("https://byjus.com")
        print("Opened Byju's.")
    elif "open" and "codecademy" in transcription or "open" and "codeacademy" in transcription:
        webbrowser.open("https://www.codecademy.com")
        print("Opened Codecademy.")
    elif "open" and "udacity" in transcription:
        webbrowser.open("https://www.udacity.com")
        print("Opened Udacity.")
    elif "open" and "pinterest" in transcription:
        webbrowser.open("https://www.pinterest.com")
        print("Opened Pinterest.")
    elif "open" and "twitch" in transcription:
        webbrowser.open("https://www.twitch.tv")
        print("Opened Twitch.")
    elif "open" and "wordpress" in transcription:
        webbrowser.open("https://wordpress.com")
        print("Opened WordPress.")
    elif "open" and "weebly" in transcription:
        webbrowser.open("https://www.weebly.com")
        print("Opened Weebly.")
    elif "open" and "wix" in transcription:
        webbrowser.open("https://www.wix.com")
        print("Opened Wix.")


    # === E-commerce and Retail ===
    elif "open" and "shein" in transcription:
        webbrowser.open("https://www.shein.com")
        print("Opened Shein.")

    # === Entertainment and Streaming ===
    elif "open" and "disney plus" in transcription or "open" and "disney+" in transcription:
        webbrowser.open("https://www.disneyplus.com")
        print("Opened Disney+.")
    elif "open" and "imdb" in transcription:
        webbrowser.open("https://www.imdb.com")
        print("Opened IMDb.")

    # === Productivity and Tools ===
    elif "open" and "figma" in transcription:
        webbrowser.open("https://www.figma.com")
        print("Opened Figma.")

    # === News and Media ===
    elif "open" and "cnn" in transcription:
        webbrowser.open("https://www.cnn.com")
        print("Opened CNN.")
    elif "open" and "fox news" in transcription:
        webbrowser.open("https://www.foxnews.com")
        print("Opened Fox News.")
    elif "open" and "medium" in transcription:
        webbrowser.open("https://www.medium.com")
        print("Opened Medium.")

    # === Miscellaneous ===
    elif "open" and "weather" in transcription or "open" and "accuweather" in transcription:
        webbrowser.open("https://www.accuweather.com")
        print("Opened AccuWeather.")
    elif "open" and "coinmarketcap" in transcription:
        webbrowser.open("https://www.coinmarketcap.com")
        print("Opened CoinMarketCap.")
    elif "open" and "speedtest" in transcription:
        webbrowser.open("https://www.speedtest.net")
        print("Opened Speedtest.")
    elif "open" and "character ai" in transcription:
        webbrowser.open("https://character.ai")
        print("Opened Character AI.")
    elif "open" and "deepl" in transcription:
        webbrowser.open("https://www.deepl.com")
        print("Opened DeepL.")
    elif "open" and "nih" in transcription:
        webbrowser.open("https://www.nih.gov")
        print("Opened NIH.")

    # === Project Management Tools ===
    elif "open" and "trello" in transcription:
        webbrowser.open("https://trello.com")
        print("Opened Trello.")
    elif "open" and "asana" in transcription:
        webbrowser.open("https://asana.com")
        print("Opened Asana.")

    # === CRM Tools ===
    elif "open" and "hubspot" in transcription:
        webbrowser.open("https://www.hubspot.com")
        print("Opened HubSpot.")
    elif "open" and "salesforce" in transcription:
        webbrowser.open("https://www.salesforce.com")
        print("Opened Salesforce.")

    # === Communication Apps ===
    elif "open" and "slack" in transcription:
        webbrowser.open("https://slack.com")
        print("Opened Slack.")
    elif "open" and "microsoft teams" in transcription or "open" and "teams" in transcription:
        webbrowser.open("https://teams.microsoft.com")
        print("Opened Microsoft Teams.")

    # === Cloud Storage ===
    elif "open" and "google drive" in transcription or "open" and "drive" in transcription:
        webbrowser.open("https://drive.google.com")
        print("Opened Google Drive.")
    elif "open" and "dropbox" in transcription:
        webbrowser.open("https://www.dropbox.com")
        print("Opened Dropbox.")

    # === Collaborative Editing ===
    elif "open" and "google docs" in transcription or "open" and "docs" in transcription:
        webbrowser.open("https://docs.google.com")
        print("Opened Google Docs.")
    elif "open" and "office online" in transcription or "open" and "microsoft office online" in transcription:
        webbrowser.open("https://www.office.com")
        print("Opened Office Online.")

    # === Accounting Software ===
    elif "open" and "quickbooks" in transcription:
        webbrowser.open("https://quickbooks.intuit.com")
        print("Opened QuickBooks.")
    elif "open" and "xero" in transcription:
        webbrowser.open("https://www.xero.com")
        print("Opened Xero.")

    # === Social Media Management ===
    elif "open" and "hootsuite" in transcription:
        webbrowser.open("https://hootsuite.com")
        print("Opened Hootsuite.")
    elif "open" and "buffer" in transcription:
        webbrowser.open("https://buffer.com")
        print("Opened Buffer.")

    # === E-commerce Platforms ===
    elif "open" and "shopify" in transcription:
        webbrowser.open("https://www.shopify.com")
        print("Opened Shopify.")
    elif "open" and "woocommerce" in transcription:
        webbrowser.open("https://woocommerce.com")
        print("Opened WooCommerce.")

    # === Analytics Tools ===
    elif "open" and "google analytics" in transcription or "open" and "analytics" in transcription:
        webbrowser.open("https://analytics.google.com")
        print("Opened Google Analytics.")
    elif "open" and "mixpanel" in transcription:
        webbrowser.open("https://mixpanel.com")
        print("Opened Mixpanel.")

    # === Email Marketing ===
    elif "open" and "mailchimp" in transcription:
        webbrowser.open("https://mailchimp.com")
        print("Opened Mailchimp.")
    elif "open" and "constant contact" in transcription:
        webbrowser.open("https://www.constantcontact.com")
        print("Opened Constant Contact.")

    # === HR Management Systems ===
    elif "open" and "bamboohr" in transcription:
        webbrowser.open("https://www.bamboohr.com")
        print("Opened BambooHR.")
    elif "open" and "workday" in transcription:
        webbrowser.open("https://www.workday.com")
        print("Opened Workday.")


    # === Learning Management Systems ===
    elif "open" and "moodle" in transcription:
        webbrowser.open("https://moodle.com")
        print("Opened Moodle.")
    elif "open" and "talentlms" in transcription:
        webbrowser.open("https://www.talentlms.com")
        print("Opened TalentLMS.")

    # === Bug Tracking Software ===
    elif "open" and "jira" in transcription:
        webbrowser.open("https://www.atlassian.com/software/jira")
        print("Opened Jira.")
    elif "open" and "bugzilla" in transcription:
        webbrowser.open("https://www.bugzilla.org")
        print("Opened Bugzilla.")

    # === Video Conferencing ===
    elif "open" and "zoom" in transcription:
        webbrowser.open("https://zoom.us")
        print("Opened Zoom.")
    elif "open" and "microsoft teams" in transcription or "open" and "teams" in transcription:
        webbrowser.open("https://teams.microsoft.com")
        print("Opened Microsoft Teams.")

    # === Time Tracking ===
    elif "open" and "harvest" in transcription:
        webbrowser.open("https://www.getharvest.com")
        print("Opened Harvest.")
    elif "open" and "toggl" in transcription:
        webbrowser.open("https://www.toggl.com")
        print("Opened Toggl.")

    # === Appointment Scheduling ===
    elif "open" and "calendly" in transcription:
        webbrowser.open("https://calendly.com")
        print("Opened Calendly.")
    elif "open" and "doodle" in transcription:
        webbrowser.open("https://doodle.com")
        print("Opened Doodle.")

    # === Customer Support Tools ===
    elif "open" and "zendesk" in transcription:
        webbrowser.open("https://www.zendesk.com")
        print("Opened Zendesk.")
    elif "open" and "freshdesk" in transcription:
        webbrowser.open("https://freshdesk.com")
        print("Opened Freshdesk.")

    # === Code Repository ===
    elif "open" and "github" in transcription or "open" and "git hub" in transcription:
        webbrowser.open("https://github.com")
        print("Opened GitHub.")
    elif "open" and "bitbucket" in transcription:
        webbrowser.open("https://bitbucket.org")
        print("Opened Bitbucket.")

    # === Password Management ===
    elif "open" and "lastpass" in transcription:
        webbrowser.open("https://www.lastpass.com")
        print("Opened LastPass.")
    elif "open" and "1password" in transcription or "open" and "one password" in transcription:
        webbrowser.open("https://1password.com")
        print("Opened 1Password.")

    # === Survey and Feedback Apps ===
    elif "open" and "surveymonkey" in transcription:
        webbrowser.open("https://www.surveymonkey.com")
        print("Opened SurveyMonkey.")
    elif "open" and "typeform" in transcription:
        webbrowser.open("https://www.typeform.com")
        print("Opened Typeform.")

    # === Blogging Platforms ===
    elif "open" and "wordpress" in transcription:
        webbrowser.open("https://wordpress.com")
        print("Opened WordPress.")
    elif "open" and "livejournal" in transcription:
        webbrowser.open("https://www.livejournal.com")
        print("Opened LiveJournal.")
    elif "open" and "ghost" in transcription:
        webbrowser.open("https://ghost.org")
        print("Opened Ghost.")

    # === Forums ===
    elif "open" and "vanilla forums" in transcription or "open" and "vanilla" in transcription:
        webbrowser.open("https://vanillaforums.com")
        print("Opened Vanilla Forums.")
    elif "open" and "phpbb" in transcription:
        webbrowser.open("https://www.phpbb.com")
        print("Opened phpBB.")
    elif "open" and "fluxbb" in transcription:
        webbrowser.open("https://fluxbb.org")
        print("Opened FluxBB.")
    elif "open" and "discourse" in transcription:
        webbrowser.open("https://www.discourse.org")
        print("Opened Discourse.")
    elif "open" and "mybb" in transcription:
        webbrowser.open("https://mybb.com")
        print("Opened MyBB.")

    # === Distributed Social Networks ===
    elif "open" and "mastodon" in transcription:
        webbrowser.open("https://mastodon.social")
        print("Opened Mastodon.")
    elif "open" and "friendica" in transcription:
        webbrowser.open("https://friendi.ca")
        print("Opened Friendica.")
    elif "open" and "diaspora" in transcription:
        webbrowser.open("https://diasporafoundation.org")
        print("Opened Diaspora.")
    elif "open" and "gnusocial" in transcription:
        webbrowser.open("https://gnu.io/social")
        print("Opened GNU Social.")

    # === Social Bookmarking ===
    elif "open" and "scuttle" in transcription:
        webbrowser.open("https://scuttle.org")
        print("Opened Scuttle.")
    elif "open" and "meneame" in transcription:
        webbrowser.open("https://www.meneame.net")
        print("Opened Meneame.")

    # === File Sharing and Sync ===
    elif "open" and "nextcloud" in transcription:
        webbrowser.open("https://nextcloud.com")
        print("Opened Nextcloud.")
    elif "open" and "owncloud" in transcription:
        webbrowser.open("https://owncloud.com")
        print("Opened ownCloud.")
    elif "open" and "seafile" in transcription:
        webbrowser.open("https://www.seafile.com")
        print("Opened Seafile.")
    elif "open" and "ifolder" in transcription:
        webbrowser.open("https://www.ifolder.com")
        print("Opened iFolder.")

    # === Webmail ===
    elif "open" and "squirrelmail" in transcription:
        webbrowser.open("https://www.squirrelmail.org")
        print("Opened SquirrelMail.")
    elif "open" and "roundcube" in transcription:
        webbrowser.open("https://roundcube.net")
        print("Opened Roundcube.")
    elif "open" and "imp" in transcription:
        webbrowser.open("https://www.horde.org/imp")
        print("Opened IMP.")

    # === Online Office Suites ===
    elif "open" and "collabora online" in transcription:
        webbrowser.open("https://www.collaboraoffice.com")
        print("Opened Collabora Online.")
    elif "open" and "feng office" in transcription:
        webbrowser.open("https://www.fengoffice.com")
        print("Opened Feng Office.")
    elif "open" and "egroupware" in transcription:
        webbrowser.open("https://www.egroupware.org")
        print("Opened eGroupware.")
    elif "open" and "phpgroupware" in transcription:
        webbrowser.open("https://phpgroupware.org")
        print("Opened PHPGroupware.")
    elif "open" and "etherpad" in transcription:
        webbrowser.open("https://etherpad.org")
        print("Opened Etherpad.")

    # === Wikis ===
    elif "open" and "mediawiki" in transcription:
        webbrowser.open("https://www.mediawiki.org")
        print("Opened MediaWiki.")
    elif "open" and "dokuwiki" in transcription:
        webbrowser.open("https://www.dokuwiki.org")
        print("Opened DokuWiki.")
    elif "open" and "tiddlywiki" in transcription:
        webbrowser.open("https://tiddlywiki.com")
        print("Opened TiddlyWiki.")

    # === Mapping and Virtual Worlds ===
    elif "open" and "openstreetmap" in transcription:
        webbrowser.open("https://www.openstreetmap.org")
        print("Opened OpenStreetMap.")
    elif "open" and "opensimulator" in transcription:
        webbrowser.open("http://opensimulator.org")
        print("Opened OpenSimulator.")
    elif "open" and "opencroquet" in transcription:
        webbrowser.open("http://opencroquet.org")
        print("Opened OpenCroquet.")

    # === Password Management ===
    elif "open" and "bitwarden" in transcription:
        webbrowser.open("https://bitwarden.com")
        print("Opened Bitwarden.")
    elif "open" and "lastpass" in transcription:
        webbrowser.open("https://www.lastpass.com")
        print("Opened LastPass.")
    elif "open" and "1password" in transcription or "open" and "one password" in transcription:
        webbrowser.open("https://1password.com")
        print("Opened 1Password.")

    # === Video Streaming ===
    elif "open" and "peertube" in transcription:
        webbrowser.open("https://joinpeertube.org")
        print("Opened PeerTube.")
    elif "open" and "plumi" in transcription:
        webbrowser.open("https://plumi.org")
        print("Opened Plumi.")
    elif "open" and "openbroadcaster" in transcription:
        webbrowser.open("https://openbroadcaster.com")
        print("Opened OpenBroadcaster.")

    # === Surveys and Feedback ===
    elif "open" and "limesurvey" in transcription:
        webbrowser.open("https://www.limesurvey.org")
        print("Opened LimeSurvey.")
    elif "open" and "surveymonkey" in transcription:
        webbrowser.open("https://www.surveymonkey.com")
        print("Opened SurveyMonkey.")
    elif "open" and "typeform" in transcription:
        webbrowser.open("https://www.typeform.com")
        print("Opened Typeform.")


    # === Bibliographic Tools ===
    elif "open" and "citeseerx" in transcription:
        webbrowser.open("https://citeseerx.ist.psu.edu")
        print("Opened CiteSeerX.")

    # === Translation Tools ===
    elif "open" and "apertium" in transcription:
        webbrowser.open("https://www.apertium.org")
        print("Opened Apertium.")

    # === Music Streaming ===
    elif "open" and "libre fm" in transcription or "open" and "librefm" in transcription:
        webbrowser.open("https://libre.fm")
        print("Opened Libre.fm.")

    # === Time Tracking and Productivity ===
    elif "open" and "livetimer" in transcription:
        webbrowser.open("https://www.livetimer.com")
        print("Opened LiveTimer.")
    elif "open" and "tempo" in transcription:
        webbrowser.open("https://tempo.io")
        print("Opened Tempo.")
    elif "open" and "rescuetime" in transcription:
        webbrowser.open("https://www.rescuetime.com")
        print("Opened RescueTime.")
    elif "open" and "xpenser" in transcription:
        webbrowser.open("https://www.xpenser.com")
        print("Opened Xpenser.")
    elif "open" and "myhours" in transcription:
        webbrowser.open("https://www.myhours.com")
        print("Opened MyHours.")
    elif "open" and "tsheets" in transcription:
        webbrowser.open("https://www.tsheets.com")
        print("Opened TSheets.")

    # === File Sharing and Collaboration ===
    elif "open" and "nomadesk" in transcription:
        webbrowser.open("https://www.nomadesk.com")
        print("Opened NomaDesk.")
    elif "open" and "logmein" in transcription:
        webbrowser.open("https://www.logmein.com")
        print("Opened LogMeIn.")
    elif "open" and "mybloop" in transcription:
        webbrowser.open("https://www.mybloop.com")
        print("Opened MyBloop.")
    elif "open" and "zimbra" in transcription:
        webbrowser.open("https://www.zimbra.com")
        print("Opened Zimbra.")
    elif "open" and "nextcloud" in transcription:
        webbrowser.open("https://nextcloud.com")
        print("Opened Nextcloud.")
    elif "open" and "seafile" in transcription:
        webbrowser.open("https://www.seafile.com")
        print("Opened Seafile.")

    # === Project Management and Planning ===
    elif "open" and "wrike" in transcription:
        webbrowser.open("https://www.wrike.com")
        print("Opened Wrike.")
    elif "open" and "zoho" in transcription:
        webbrowser.open("https://www.zoho.com")
        print("Opened Zoho.")
    elif "open" and "trailfire" in transcription:
        webbrowser.open("https://www.trailfire.com")
        print("Opened Trailfire.")
    elif "open" and "teleport" in transcription:
        webbrowser.open("https://teleporthq.io")
        print("Opened Teleport.")
    elif "open" and "calendar hub" in transcription:
        webbrowser.open("https://www.calendarhub.com")
        print("Opened Calendar Hub.")
    elif "open" and "tripit" in transcription:
        webbrowser.open("https://www.tripit.com")
        print("Opened TripIt.")

    # === Video and Media Sharing ===
    elif "open" and "vimeo" in transcription:
        webbrowser.open("https://vimeo.com")
        print("Opened Vimeo.")
    elif "open" and "metacafe" in transcription:
        webbrowser.open("https://www.metacafe.com")
        print("Opened Metacafe.")
    elif "open" and "pandora" in transcription:
        webbrowser.open("https://www.pandora.com")
        print("Opened Pandora.")
    elif "open" and "dailymotion" in transcription:
        webbrowser.open("https://www.dailymotion.com")
        print("Opened Dailymotion.")
    elif "open" and "clipshack" in transcription:
        webbrowser.open("https://www.clipshack.com")
        print("Opened ClipShack.")
    elif "open" and "imeem" in transcription:
        webbrowser.open("https://www.imeem.com")
        print("Opened Imeem.")

    # === Social and Recommender Systems ===
    elif "open" and "vsocial" in transcription:
        webbrowser.open("https://www.vsocial.com")
        print("Opened vSocial.")
    elif "open" and "strands" in transcription:
        webbrowser.open("https://www.strands.com")
        print("Opened Strands.")
    elif "open" and "tall street" in transcription:
        webbrowser.open("https://www.tallstreet.com")
        print("Opened Tall Street.")
    elif "open" and "wink" in transcription:
        webbrowser.open("https://wink.com")
        print("Opened Wink People Search.")
    elif "open" and "ask" in transcription:
        webbrowser.open("https://www.ask.com")
        print("Opened Askeet.")

    # === AI and Automation Tools ===
    elif "open" and "chatgpt" in transcription or "open" and "openai" in transcription:
        webbrowser.open("https://chat.openai.com")
        print("Opened ChatGPT.")
    elif "open" and "tldr" in transcription:
        webbrowser.open("https://tldrthis.com")
        print("Opened TLDR This.")
    elif "open" and "hey friday" in transcription or "open" and "friday" in transcription:
        webbrowser.open("https://heyfriday.ai")
        print("Opened Hey Friday.")
    elif "open" and "sidekick" in transcription:
        webbrowser.open("https://www.runsidekick.com")
        print("Opened Sidekick.")

    # === Tools for Developers ===
    elif "open" and "foxit pdf mobile" in transcription:
        webbrowser.open("https://www.foxit.com/mobile-pdf")
        print("Opened Foxit PDF Mobile.")
    elif "open" and "extends class" in transcription or "open" and "extend" in transcription:
        webbrowser.open("https://extendsclass.com")
        print("Opened Extends Class.")
    elif "open" and "pull request" in transcription or "open" and "pull" in transcription or "open" and "request" in transcription:
        webbrowser.open("https://pullrequest.com")
        print("Opened Pull Request.")

    # === Entertainment and Travel ===
    elif "open" and "linkup" in transcription or "open" and "link" in transcription:
        webbrowser.open("https://www.linkup.com")
        print("Opened LinkUp.")
    elif "open" and "rawsugar" in transcription:
        webbrowser.open("https://rawsugar.com")
        print("Opened RawSugar.")
    elif "open" and "otavo" in transcription:
        webbrowser.open("https://otavo.com")
        print("Opened Otavo.")
    elif "open" and "camp fire usa" in transcription or "open" and "campfire usa" in transcription:
        webbrowser.open("https://campfire.org")
        print("Opened Camp Fire USA.")

    # === Video and Media Creation/Sharing ===
    elif "open" and "jumpcut" in transcription:
        webbrowser.open("https://www.jumpcut.com")
        print("Opened Jumpcut.")
    elif "open" and "revver" in transcription:
        webbrowser.open("https://www.revver.com")
        print("Opened Revver.")
    elif "open" and "vimeo" in transcription:
        webbrowser.open("https://vimeo.com")
        print("Opened Vimeo.")
    elif "open" and "metacafe" in transcription or "open" and "meta cave" in transcription:
        webbrowser.open("https://www.metacafe.com")
        print("Opened Metacafe.")
    elif "open" and "clipshack" in transcription:
        webbrowser.open("https://www.clipshack.com")
        print("Opened ClipShack.")
    elif "open" and "dailymotion" in transcription:
        webbrowser.open("https://www.dailymotion.com")
        print("Opened Dailymotion.")
    elif "open" and "imeem" in transcription:
        webbrowser.open("https://www.imeem.com")
        print("Opened Imeem.")

    # === Music Discovery and Streaming ===
    elif "open" and "musicovery" in transcription:
        webbrowser.open("https://musicovery.com")
        print("Opened Musicovery.")
    elif "open" and "ilike" in transcription:
        webbrowser.open("https://www.ilike.com")
        print("Opened iLike.")
    elif "open" and "pandora" in transcription:
        webbrowser.open("https://www.pandora.com")
        print("Opened Pandora.")

    # === Event and Task Management ===
    elif "open" and "eventful" in transcription:
        webbrowser.open("https://www.eventful.com")
        print("Opened Eventful.")
    elif "open" and "cogram" in transcription:
        webbrowser.open("https://www.cogram.com")
        print("Opened Cogram.")

    # === Social Bookmarking and Discovery ===
    elif "open" and "blummy" in transcription:
        webbrowser.open("https://www.blummy.com")
        print("Opened Blummy.")
    elif "open" and "trailfire" in transcription:
        webbrowser.open("https://www.trailfire.com")
        print("Opened Trailfire.")
    elif "open" and "blogmarks" in transcription:
        webbrowser.open("https://www.blogmarks.net")
        print("Opened BlogMarks.")
    elif "open" and "linkatopia" in transcription:
        webbrowser.open("https://www.linkatopia.com")
        print("Opened Linkatopia.")
    elif "open" and "tektag" in transcription:
        webbrowser.open("https://www.tektag.com")
        print("Opened TekTag.")
    elif "open" and "ma.gnolia" in transcription:
        webbrowser.open("https://www.ma.gnolia.com")
        print("Opened Ma.gnolia.")
    elif "open" and "diigo" in transcription:
        webbrowser.open("https://www.diigo.com")
        print("Opened Diigo.")

    # === AI Tools ===
    elif "open" and "tabnine" in transcription:
        webbrowser.open("https://www.tabnine.com")
        print("Opened Tabnine.")
    elif "open" and "browse ai" in transcription:
        webbrowser.open("https://www.browse.ai")
        print("Opened Browse AI.")
    elif "open" and "promptlayer" in transcription:
        webbrowser.open("https://promptlayer.com")
        print("Opened PromptLayer.")
    elif "open" and "nuclia" in transcription:
        webbrowser.open("https://www.nuclia.com")
        print("Opened Nuclia.")
    elif "open" and "axiom ai" in transcription:
        webbrowser.open("https://www.axiom.ai")
        print("Opened Axiom AI.")
    elif "open" and "riku ai" in transcription:
        webbrowser.open("https://riku.ai")
        print("Opened Riku AI.")
    elif "open" and "robovision" in transcription:
        webbrowser.open("https://www.robovision.ai")
        print("Opened Robovision.")
    elif "open" and "seek ai" in transcription:
        webbrowser.open("https://www.seek.ai")
        print("Opened Seek AI.")

    # === Development and Code Collaboration ===
    elif "open" and "replit" in transcription:
        webbrowser.open("https://replit.com")
        print("Opened Replit.")
    elif "open" and "dotnetkicks" in transcription:
        webbrowser.open("https://www.dotnetkicks.com")
        print("Opened DotNetKicks.")
    elif "open" and "message dance" in transcription:
        webbrowser.open("https://www.messagedance.com")
        print("Opened MessageDance.")


    # === Networking and Messaging ===
    elif "open" and "ebuddy" in transcription:
        webbrowser.open("https://www.ebuddy.com")
        print("Opened eBuddy.")
    elif "open" and "fring" in transcription:
        webbrowser.open("https://www.fring.com")
        print("Opened Fring.")
    elif "open" and "trillian" in transcription:
        webbrowser.open("https://www.trillian.im")
        print("Opened Trillian.")

    # === Data Management and Tracking ===
    elif "open" and "zoto" in transcription:
        webbrowser.open("https://www.zoto.com")
        print("Opened Zoto.")
    elif "open" and "eventful" in transcription:
        webbrowser.open("https://www.eventful.com")
        print("Opened Eventful.")
    elif "open" and "networthiq" in transcription:
        webbrowser.open("https://www.networthiq.com")
        print("Opened NetworthIQ.")

    # === Bonus Apps ===
    elif "open" and "cligs" in transcription:
        webbrowser.open("https://www.cligs.com")
        print("Opened Cligs.")
    elif "open" and "joopz" in transcription:
        webbrowser.open("https://www.joopz.com")
        print("Opened Joopz.")
    elif "open" and "jajah" in transcription:
        webbrowser.open("https://www.jajah.com")
        print("Opened JAJAH.")

    # === New Social Media and Communication ===
    elif "open" and "live" in transcription:
        webbrowser.open("https://www.live.com")
        print("Opened Live.")
    elif "open" and "t.me" in transcription or "open" and "telegram link" in transcription:
        webbrowser.open("https://t.me")
        print("Opened Telegram Link.")
    elif "open" and "pixiv" in transcription:
        webbrowser.open("https://www.pixiv.net")
        print("Opened Pixiv.")
    elif "open" and "vk" in transcription or "open" and "vkontakte" in transcription:
        webbrowser.open("https://www.vk.com")
        print("Opened VKontakte.")
    elif "open" and "x" in transcription or "open" and "x dot com" in transcription:
        webbrowser.open("https://www.x.com")
        print("Opened X.")

    # === New E-commerce and Retail ===
    elif "open" and "amazon japan" in transcription or "open" and "amazon.co.jp" in transcription:
        webbrowser.open("https://www.amazon.co.jp")
        print("Opened Amazon Japan.")
    elif "open" and "amazon india" in transcription or "open" and "amazon.in" in transcription:
        webbrowser.open("https://www.amazon.in")
        print("Opened Amazon India.")
    elif "open" and "rakuten" in transcription:
        webbrowser.open("https://www.rakuten.co.jp")
        print("Opened Rakuten.")
    elif "open" and "temu" in transcription:
        webbrowser.open("https://www.temu.com")
        print("Opened Temu.")
    elif "open" and "etsy" in transcription:
        webbrowser.open("https://www.etsy.com")
        print("Opened Etsy.")

    # === Entertainment and Streaming ===
    elif "open" and "hanime" in transcription or "open" and "hanime.tv" in transcription:
        webbrowser.open("https://www.hanime.tv")
        print("Opened Hanime.")
    elif "open" and "animeflv" in transcription:
        webbrowser.open("https://www.animeflv.net")
        print("Opened AnimeFLV.")
    elif "open" and "animesuge" in transcription:
        webbrowser.open("https://www.animesuge.to")
        print("Opened AnimeSuge.")
    elif "open" and "roblox" in transcription:
        webbrowser.open("https://www.roblox.com")
        print("Opened Roblox.")
    elif "open" and "steampowered" in transcription or "open" and "steam" in transcription:
        webbrowser.open("https://www.steampowered.com")
        print("Opened Steam.")

    # === Productivity and Tools ===
    elif "open" and "archive of our own" in transcription or "open" and "ao3" in transcription:
        webbrowser.open("https://www.archiveofourown.org")
        print("Opened Archive of Our Own (AO3).")
    elif "open" and "sharepoint" in transcription:
        webbrowser.open("https://www.sharepoint.com")
        print("Opened SharePoint.")
    elif "open" and "adjust" in transcription:
        webbrowser.open("https://www.adjust.com")
        print("Opened Adjust.")

    # === News and Media ===
    elif "open" and "marca" in transcription:
        webbrowser.open("https://www.marca.com")
        print("Opened Marca.")
    elif "open" and "as.com" in transcription:
        webbrowser.open("https://www.as.com")
        print("Opened AS.")
    elif "open" and "nytimes" in transcription or "open" and "new york times" in transcription:
        webbrowser.open("https://www.nytimes.com")
        print("Opened The New York Times.")
    elif "open" and "the guardian" in transcription:
        webbrowser.open("https://www.theguardian.com")
        print("Opened The Guardian.")

    # === File Sharing and Shortening ===
    elif "open" and "mediafire" in transcription:
        webbrowser.open("https://www.mediafire.com")
        print("Opened MediaFire.")
    elif "open" and "goo.gl" in transcription:
        webbrowser.open("https://www.goo.gl")
        print("Opened Goo.gl.")
    elif "open" and "page link" in transcription:
        webbrowser.open("https://www.page.link")
        print("Opened Page.link.")
    elif "open" and "app link" in transcription:
        webbrowser.open("https://www.app.link")
        print("Opened App.link.")

    # === Entertainment and Fandom ===
    elif "open" and "fandom" in transcription:
        webbrowser.open("https://www.fandom.com")
        print("Opened Fandom.")
    elif "open" and "fanfiction" in transcription:
        webbrowser.open("https://www.fanfiction.net")
        print("Opened FanFiction.")

    # === Manga and Anime ===
    elif "open" and "syosetu" in transcription:
        webbrowser.open("https://www.syosetu.com")
        print("Opened Syosetu.")
    elif "open" and "mangadex" in transcription:
        webbrowser.open("https://www.mangadex.org")
        print("Opened MangaDex.")
    elif "open" and "mangago" in transcription:
        webbrowser.open("https://www.mangago.me")
        print("Opened MangaGo.")
    elif "open" and "mangakakalot" in transcription:
        webbrowser.open("https://www.mangakakalot.com")
        print("Opened MangaKakalot.")

    # === Miscellaneous ===
    elif "open" and "apple" in transcription:
        webbrowser.open("https://www.apple.com")
        print("Opened Apple.")
    elif "open" and "noodlemagazine" in transcription:
        webbrowser.open("https://www.noodlemagazine.com")
        print("Opened NoodleMagazine.")
    elif "open" and "dzen" in transcription:
        webbrowser.open("https://www.dzen.ru")
        print("Opened Dzen.")
    elif "open" and "fmoviesz" in transcription:
        webbrowser.open("https://www.fmoviesz.to")
        print("Opened FMovies.")
    elif "open" and "ign" in transcription:
        webbrowser.open("https://www.ign.com")
        print("Opened IGN.")
    elif "open" and "bit.ly" in transcription:
        webbrowser.open("https://www.bit.ly")
        print("Opened Bit.ly.")


     # === Function Keys Commands ===
    elif "press" and "f1" in transcription:
        pyautogui.press('f1')
    elif "press" and "f2" in transcription:
        pyautogui.press('f2')
    elif "press" and "f3" in transcription:
        pyautogui.press('f3')
    elif "press" and "f4" in transcription:
        pyautogui.press('f4')
    elif "press" and "f5" in transcription:
        pyautogui.press('f5')
    elif "press" and "f6" in transcription:
        pyautogui.press('f6')
    elif "press" and "f7" in transcription:
        pyautogui.press('f7')
    elif "press" and "f8" in transcription:
        pyautogui.press('f8')
    elif "press" and "f9" in transcription:
        pyautogui.press('f9')
    elif "press" and "f10" in transcription:
        pyautogui.press('f10')
    elif "press" and "f11" in transcription:
        pyautogui.press('f11')
    elif "press" and "f12" in transcription:
        pyautogui.press('f12')

    # === Ending the Program ===
    elif "end the program" in transcription or "stop" in transcription and "program" in transcription:
        print("Program ending")
        os._exit(0)

    # Example: Debugging in Sidebar
    #st.sidebar.write(f"Executed command: {transcription}")


# Function to add the application to Windows startup
def add_to_startup():
    """
    Add the current executable to the Windows startup registry key.
    """
    try:
        # Get the path of the current executable
        exe_path = os.path.realpath(sys.argv[0])

        # Define the registry key and the application name
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "HandVoiceControlApp"  # Choose a unique name for your application

        # Open the registry key
        reg_key = reg.OpenKey(reg.HKEY_CURRENT_USER, key, 0, reg.KEY_SET_VALUE)

        # Add the application to the registry
        reg.SetValueEx(reg_key, app_name, 0, reg.REG_SZ, exe_path)
        reg.CloseKey(reg_key)

        print(f"{app_name} added to startup.")
    except Exception as e:
        print(f"Failed to add to startup: {e}")

# Call the function to add to startup
add_to_startup()


# Function to send and receive data from the WebSocket
async def send_receive():
    global transcription_queue
    async with websockets.connect(
        URL,
        extra_headers=(("Authorization", auth_key),),
        ping_interval=5,
        ping_timeout=20
    ) as _ws:
        print("Connected to WebSocket")

        session_begins = await _ws.recv()
        print("Session begins:", session_begins)

        async def send():
            while running_event.is_set():
                try:
                    data = stream.read(FRAME_PER_BUFFER)
                    data = base64.b64encode(data).decode("utf-8")
                    json_data = json.dumps({"audio_data": str(data)})

                    await _ws.send(json_data)
                except websockets.exceptions.ConnectionClosedError:
                    print("Connection closed during send")
                    break
                except Exception as e:
                    print("Error in send:", e)
                    break
                await asyncio.sleep(0.01)

        async def receive():
            accumulated_text = ""  # Accumulate the text during speech
            last_received_time = time.time()  # Track the last time text was received
            pause_threshold = 1.0  # Time in seconds to consider a pause in speech

            while running_event.is_set():
                try:
                    result_str = await _ws.recv()
                    current_text = json.loads(result_str).get('text', '').strip()

                    # Process only when new text arrives
                    if current_text:
                        print(f"New transcription chunk: {current_text}")
                        accumulated_text = current_text
                        last_received_time = time.time()

                    # Check if there’s a pause and process the accumulated text
                    if time.time() - last_received_time > pause_threshold and accumulated_text:
                        print(f"Final transcription after pause: {accumulated_text}")
                        transcription_queue.put(accumulated_text)  # Add transcription to the queue
                        accumulated_text = ""  # Reset after processing
                except websockets.exceptions.ConnectionClosedError:
                    print("Connection closed during receive")
                    break
                except Exception as e:
                    print("Error in receive:", e)
                    break

        await asyncio.gather(send(), receive())


# === User Interface Class (First Page) ===
class UserInterface:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{settings.WINDOW_TITLE} - Setup")
        self.root.state('zoomed')
        
        # Use theme colors from settings
        self.colors = {
            'primary': ThemeColors.PRIMARY,
            'secondary': ThemeColors.SECONDARY,
            'accent': ThemeColors.ACCENT,
            'background': ThemeColors.BG_DARK,
            'surface': ThemeColors.BG_DARKER,
            'card': ThemeColors.BG_SECONDARY,
            'text_primary': ThemeColors.TEXT_PRIMARY,
            'text_secondary': ThemeColors.TEXT_SECONDARY,
            'success': ThemeColors.SUCCESS,
            'warning': ThemeColors.WARNING,
            'error': ThemeColors.ERROR
        }
        
        self.root.configure(bg=ThemeColors.BG_DARK)

        # Set application icon
        logo_image_path = get_resource_path("app_logo.ico")
        try:
            self.root.iconbitmap(logo_image_path)
        except Exception as e:
            print(f"Failed to load logo: {e}")

        self.create_modern_layout()
        self.create_welcome_content()

    def create_modern_layout(self):
        """Create modern gradient background and layout"""
        # Create main container
        self.main_frame = tk.Frame(self.root, bg=self.colors['background'])
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create gradient effect with canvas
        self.bg_canvas = tk.Canvas(
            self.main_frame, 
            highlightthickness=0,
            bg=self.colors['background']
        )
        self.bg_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind resize event to update gradient
        self.root.bind('<Configure>', self.on_window_resize)
        self.root.after(100, self.create_gradient_background)

    def create_gradient_background(self):
        """Create a modern gradient background"""
        self.bg_canvas.delete("gradient")
        
        width = self.bg_canvas.winfo_width()
        height = self.bg_canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            self.root.after(100, self.create_gradient_background)
            return
        
        # Create gradient strips
        for i in range(height):
            # Create color transition from primary to secondary
            ratio = i / height
            
            # Interpolate between colors
            r1, g1, b1 = self.hex_to_rgb(self.colors['background'])
            r2, g2, b2 = self.hex_to_rgb(self.colors['surface'])
            
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            
            color = f"#{r:02x}{g:02x}{b:02x}"
            
            self.bg_canvas.create_line(
                0, i, width, i, 
                fill=color, 
                width=1,
                tags="gradient"
            )

    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def on_window_resize(self, event):
        """Handle window resize to update gradient"""
        if event.widget == self.root:
            self.root.after(50, self.create_gradient_background)

    def create_welcome_content(self):
        """Create the welcome page content with modern design"""
        # Create welcome card
        card_frame = tk.Frame(
            self.bg_canvas, 
            bg=self.colors['card'],
            relief=tk.FLAT,
            bd=0
        )
        
        # Main title
        title_label = tk.Label(
            card_frame,
            text="🖐️ HV SYSTEM",
            font=("Segoe UI", 48, "bold"),
            fg=self.colors['primary'],
            bg=self.colors['card']
        )
        title_label.pack(pady=(40, 10))
        
        # Subtitle
        subtitle_label = tk.Label(
            card_frame,
            text="Hand Gestures & Voice Controlled Computer System",
            font=("Segoe UI", 18),
            fg=self.colors['text_secondary'],
            bg=self.colors['card']
        )
        subtitle_label.pack(pady=(0, 30))
        
        # Feature highlights
        features_frame = tk.Frame(card_frame, bg=self.colors['card'])
        features_frame.pack(pady=20)
        
        features = [
            ("🖱️", "Gesture Control", "Control mouse with hand movements"),
            ("🎤", "Voice Commands", "1500+ voice commands available"),
            ("🛡️", "Secure & Reliable", "Enterprise-grade security")
        ]
        
        for i, (icon, title, desc) in enumerate(features):
            feature_frame = tk.Frame(features_frame, bg=self.colors['card'])
            feature_frame.grid(row=0, column=i, padx=40, pady=10)
            
            tk.Label(
                feature_frame,
                text=icon,
                font=("Segoe UI", 24),
                bg=self.colors['card'],
                fg=self.colors['accent']
            ).pack()
            
            tk.Label(
                feature_frame,
                text=title,
                font=("Segoe UI", 14, "bold"),
                bg=self.colors['card'],
                fg=self.colors['text_primary']
            ).pack()
            
            tk.Label(
                feature_frame,
                text=desc,
                font=("Segoe UI", 10),
                bg=self.colors['card'],
                fg=self.colors['text_secondary'],
                wraplength=150
            ).pack()
        
        # Action buttons
        button_frame = tk.Frame(card_frame, bg=self.colors['card'])
        button_frame.pack(pady=(40, 40))
        
        # Create modern buttons
        self.start_button = self.create_modern_button(
            button_frame,
            text="🚀 Start Application",
            command=self.start_main_application,
            primary=True
        )
        self.start_button.pack(side=tk.LEFT, padx=15)
        
        self.manual_button = self.create_modern_button(
            button_frame,
            text="📖 User Manual",
            command=self.show_user_manual,
            primary=False
        )
        self.manual_button.pack(side=tk.LEFT, padx=15)
        
        # Position the card in center
        self.bg_canvas.create_window(
            self.bg_canvas.winfo_reqwidth() // 2,
            self.bg_canvas.winfo_reqheight() // 2,
            window=card_frame,
            anchor=tk.CENTER
        )
        
        # Update card position when canvas size changes
        self.bg_canvas.bind('<Configure>', self.center_card)

    def create_modern_button(self, parent, text, command, primary=True):
        """Create a modern styled button"""
        if primary:
            bg_color = self.colors['primary']
            fg_color = self.colors['text_primary']
            active_bg = self.colors['secondary']
        else:
            bg_color = self.colors['surface']
            fg_color = self.colors['text_primary']
            active_bg = self.colors['card']
        
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 12, "bold"),
            bg=bg_color,
            fg=fg_color,
            activebackground=active_bg,
            activeforeground=fg_color,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            padx=30,
            pady=12
        )
        
        # Add hover effects
        button.bind("<Enter>", lambda e: self.on_button_hover(button, True, primary))
        button.bind("<Leave>", lambda e: self.on_button_hover(button, False, primary))
        
        return button

    def on_button_hover(self, button, entering, primary):
        """Handle button hover effects"""
        if entering:
            if primary:
                button.config(bg=self.colors['secondary'])
            else:
                button.config(bg=self.colors['card'])
        else:
            if primary:
                button.config(bg=self.colors['primary'])
            else:
                button.config(bg=self.colors['surface'])

    def center_card(self, event):
        """Center the card when canvas is resized"""
        canvas_width = event.width
        canvas_height = event.height
        
        # Update card position
        self.bg_canvas.coords("all", canvas_width // 2, canvas_height // 2)

    def start_main_application(self):
        """
        Instead of going directly to HandVoiceControlApp,
        go to ModeSelectionPage.
        """
        self.root.destroy()  # Close the current window

        new_root = tk.Tk()
        ModeSelectionPage(new_root)
        new_root.mainloop()

    def show_user_manual(self):
        manual_window = tk.Toplevel(self.root)
        manual_window.title("User Manual Guidelines")
        manual_window.state('zoomed')
        manual_window.configure(bg=ThemeColors.BG_DARK)

        # Attempt to set an icon for the manual window
        logo_image_path = get_resource_path("app_logo.ico")
        try:
            manual_window.iconbitmap(logo_image_path)
        except Exception as e:
            print(f"Failed to load manual window icon: {e}")

        # Create background canvas with theme colors
        bg_canvas = tk.Canvas(
            manual_window, 
            highlightthickness=0,
            bg=ThemeColors.BG_DARK
        )
        bg_canvas.pack(fill=tk.BOTH, expand=True)

        # Create gradient background for manual window
        self.create_manual_gradient_background(bg_canvas)

        # === Create a scrolled text area for the manual ===
        manual_text = scrolledtext.ScrolledText(
            bg_canvas,
            wrap=tk.WORD,
            font=("Helvetica", 12),
            width=70,
            height=40,
            bg=ThemeColors.BG_PRIMARY,
            fg=ThemeColors.TEXT_PRIMARY,
            relief=tk.FLAT,
            insertbackground=ThemeColors.TEXT_PRIMARY
        )
        manual_text.place(relx=0.5, rely=0.45, anchor=tk.CENTER)

        # Define styling "tags" for the scrolled text using theme colors
        manual_text.tag_config(
            "title",
            font=("Helvetica", 18, "bold"),
            foreground=ThemeColors.SECONDARY,
            justify="center",
            spacing3=15  # extra spacing after paragraph
        )
        manual_text.tag_config(
            "heading",
            font=("Helvetica", 14, "bold"),
            foreground=ThemeColors.ACCENT,
            spacing3=10
        )
        manual_text.tag_config(
            "body",
            font=("Helvetica", 12),
            foreground=ThemeColors.TEXT_PRIMARY,
            spacing3=5
        )
        manual_text.tag_config(
            "image_desc",
            font=("Helvetica", 11, "italic"),
            foreground=ThemeColors.TEXT_SECONDARY,
            spacing3=5
        )

        # Keep references to images
        self.manual_images = []

        def insert_image(image_relative_path, caption=None):
            """
            Inserts an image (via get_resource_path) and optional italic caption underneath.
            """
            full_path = get_resource_path(image_relative_path)
            if os.path.exists(full_path):
                try:
                    img = Image.open(full_path)
                    # Optionally resize the image if too large:
                    # img = img.resize((250, 180), Image.Resampling.LANCZOS)
                    img_tk = ImageTk.PhotoImage(img)
                    self.manual_images.append(img_tk)  # prevent GC

                    # Insert the image
                    manual_text.image_create(tk.END, image=img_tk)
                    manual_text.insert(tk.END, "\n", "body")

                    # If there's a caption, insert it in italic style
                    if caption:
                        manual_text.insert(tk.END, caption + "\n\n", "image_desc")
                    else:
                        manual_text.insert(tk.END, "\n", "body")

                except Exception as e:
                    manual_text.insert(tk.END, f"[Error loading {full_path}: {e}]\n", "body")
            else:
                manual_text.insert(tk.END, f"[Image not found: {full_path}]\n", "body")

        # ===== MANUAL CONTENT =====

    def create_manual_gradient_background(self, canvas):
        """Create a gradient background for the manual window"""
        canvas.delete("gradient")
        
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            # Schedule retry if canvas not ready
            canvas.after(100, lambda: self.create_manual_gradient_background(canvas))
            return
        
        # Create gradient strips
        for i in range(height):
            # Create color transition from dark to primary
            ratio = i / height
            
            # Interpolate between colors
            r1, g1, b1 = self.hex_to_rgb(ThemeColors.BG_DARK)
            r2, g2, b2 = self.hex_to_rgb(ThemeColors.PRIMARY)
            
            r = int(r1 + (r2 - r1) * ratio * 0.4)  # Subtle gradient
            g = int(g1 + (g2 - g1) * ratio * 0.4)
            b = int(b1 + (b2 - b1) * ratio * 0.4)
            
            color = f"#{r:02x}{g:02x}{b:02x}"
            
            canvas.create_line(
                0, i, width, i, 
                fill=color, 
                width=1,
                tags="gradient"
            )
        manual_text.insert(tk.END, "USER MANUAL GUIDELINES\n", "title")

        manual_text.insert(tk.END, "1. OVERVIEW\n", "heading")
        manual_text.insert(tk.END,
            "This system allows users to control their computer using hand gestures and voice commands.\n"
            "Gestures are recognized via the webcam, while voice commands are captured by the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "2. GETTING STARTED\n", "heading")
        manual_text.insert(tk.END,
            "Click 'Start' on the main page to initialize the system. "
            "Make sure your camera and microphone are connected and functioning properly.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "3. GESTURE CONTROLS\n", "heading")
        manual_text.insert(tk.END,
            "Below are the primary gestures supported. Each entry has a descriptive image:\n\n",
            "body"
        )

        # 3.1 Mouse Movement
        manual_text.insert(tk.END, "Mouse Movement (Index Finger Only)\n", "heading")
        manual_text.insert(tk.END,
            "Raise ONLY your Index finger to move the mouse pointer. Keep other fingers folded.\n",
            "body"
        )
        insert_image("user_manual_guides/mouse_movement.png", caption="Figure: Mouse Movement Gesture")

        # 3.2 Left Click
        manual_text.insert(tk.END, "Left Click (Index + Middle Fingers)\n", "heading")
        manual_text.insert(tk.END,
            "Raise your Index and Middle fingers together. This performs a left-click action.\n",
            "body"
        )
        insert_image("user_manual_guides/left_click.png", caption="Figure: Left Click Gesture")

        # 3.3 Right Click
        manual_text.insert(tk.END, "Right Click (Index + Middle + Ring)\n", "heading")
        manual_text.insert(tk.END,
            "Raise Index, Middle, and Ring fingers together to perform a right-click.\n",
            "body"
        )
        insert_image("user_manual_guides/right_click.png", caption="Figure: Right Click Gesture")

        # 3.4 Scroll Up
        manual_text.insert(tk.END, "Scroll Up\n", "heading")
        manual_text.insert(tk.END,
            "Raise all five fingers. This action scrolls up.\n",
            "body"
        )
        insert_image("user_manual_guides/scroll_up.png")

        # 3.5 Scroll Down
        manual_text.insert(tk.END, "Scroll Down\n", "heading")
        manual_text.insert(tk.END,
            "Raise Index, Middle, Ring, and Pinky only (Thumb folded). This scrolls down.\n",
            "body"
        )
        insert_image("user_manual_guides/scroll_down.png")

        # 3.6 Move Forward
        manual_text.insert(tk.END, "Move Forward (Only Pinky Up)\n", "heading")
        manual_text.insert(tk.END,
            "Raise ONLY your pinky finger to move forward in slides.\n",
            "body"
        )
        insert_image("user_manual_guides/move_forward.png")

        # 3.7 Move Backward
        manual_text.insert(tk.END, "Move Backward (Only Thumb Up)\n", "heading")
        manual_text.insert(tk.END,
            "Raise ONLY your thumb to move backward in slides.\n",
            "body"
        )
        insert_image("user_manual_guides/move_backward.png")

        # 3.8 Zoom In
        manual_text.insert(tk.END, "Zoom In (Thumb + Index + Pinky)\n", "heading")
        manual_text.insert(tk.END,
            "Keep Middle & Ring folded, raise the other three to Zoom In.\n",
            "body"
        )
        insert_image("user_manual_guides/zoom_in.png")

        # 3.9 Zoom Out
        manual_text.insert(tk.END, "Zoom Out (Thumb + Index + Middle + Pinky)\n", "heading")
        manual_text.insert(tk.END,
            "Keep only the Ring finger folded, raise the rest to Zoom Out.\n",
            "body"
        )
        insert_image("user_manual_guides/zoom_out.png")

        # Additional manual text
        manual_text.insert(tk.END, "4. VOICE COMMANDS\n", "heading")
        manual_text.insert(tk.END,
            "Basic commands include opening/closing applications, web search, etc.\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )


        manual_text.insert(tk.END, "Opening and Closing Apllication\n", "heading")
        manual_text.insert(tk.END,
            "Basic commands include opening/closing applications, web search, etc.\n"
            "For Example: Say (Open Powerpoint) clearly toward the microphone\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "Search Results\n", "heading")
        manual_text.insert(tk.END,
            "Say (Show me the results) after typing on the google search bar\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "New tab\n", "heading")
        manual_text.insert(tk.END,
            "Say (Open new tab)\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "Minimize Window\n", "heading")
        manual_text.insert(tk.END,
            "Say (Minimize the window)\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "Maximize Window\n", "heading")
        manual_text.insert(tk.END,
            "Say (Maximize the window)\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "Close Window\n", "heading")
        manual_text.insert(tk.END,
            "Say (Close the window)\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "Scroll Up\n", "heading")
        manual_text.insert(tk.END,
            "Say (Scroll Up)\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "Scroll Down\n", "heading")
        manual_text.insert(tk.END,
            "Say (Scroll Down)\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "Create New Folder\n", "heading")
        manual_text.insert(tk.END,
            "Say (Create a New Folder)\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "Rename Folder\n", "heading")
        manual_text.insert(tk.END,
            "Say (Rename the Folder)\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "Delete Folder\n", "heading")
        manual_text.insert(tk.END,
            "Say (Delete this folder)\n"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )


        manual_text.insert(tk.END, "Typing Function\n", "heading")
        manual_text.insert(tk.END,
            "Typing Funcion will perform by saying (Type Here) or (Type) Command\n"
            "For Example: Say (Type Here what is artificial intelligence) on google searchbar"
            "Speak clearly toward the microphone.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "5. TROUBLESHOOTING\n", "heading")
        manual_text.insert(tk.END,
            "If the camera feed doesn’t appear, ensure no other program is using the camera.\n"
            "Check microphone permissions if voice commands do not work.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "6. SUPPORT\n", "heading")
        manual_text.insert(tk.END,
            "For further assistance, please contact the developer.\n\n",
            "body"
        )

        manual_text.insert(tk.END, "=============================================\n", "title")


        manual_text.config(state=tk.DISABLED)  # Make the text read-only

        # -------- PDF Download Feature (Text Only) -------


        def download_manual_as_pdf():
            """
            Generate a PDF version of the user manual with IMAGES, 
            using a data structure that holds heading, body text, 
            and (optional) image paths. Saves 'HV_Manual.pdf' in 
            the user's Downloads folder.
            """

            # 1) Define or retrieve your manual's sections:
            #    (In practice, this list might live at class-level or be passed in.)
            manual_sections = [
                {
                    "heading": "Mouse Movement (Index Finger Only)",
                    "body": (
                        "Raise ONLY your Index finger to move the mouse pointer. "
                        "Keep other fingers folded."
                    ),
                    "image_path": "user_manual_guides/mouse_movement.png",
                    "caption": "Figure: Mouse Movement Gesture",
                },
                {
                    "heading": "Left Click (Index + Middle Fingers)",
                    "body": (
                        "Raise your Index and Middle fingers together. "
                        "This performs a left-click action."
                    ),
                    "image_path": "user_manual_guides/left_click.png",
                    "caption": "Figure: Left Click Gesture",
                },
                {
                    "heading": "Right Click (Index + Middle + Ring Fingers)",
                    "body": (
                        "Raise Index, Middle, and Ring fingers together "
                        "to perform a right-click action."
                    ),
                    "image_path": "user_manual_guides/right_click.png",
                    "caption": "Figure: Right Click Gesture",
                },
                {
                    "heading": "Scroll Up (All Five Fingers)",
                    "body": (
                        "Raise all five fingers. This action scrolls up."
                    ),
                    "image_path": "user_manual_guides/scroll_up.png",
                    "caption": "Figure: Scroll Up Gesture",
                },
                {
                    "heading": "Scroll Down (Thumb Folded)",
                    "body": (
                        "Raise Index, Middle, Ring, and Pinky only (Thumb folded). "
                        "This scrolls down."
                    ),
                    "image_path": "user_manual_guides/scroll_down.png",
                    "caption": "Figure: Scroll Down Gesture",
                },
                {
                    "heading": "Move Forward (Only Pinky Up)",
                    "body": (
                        "Raise ONLY your pinky finger to move forward in slides."
                    ),
                    "image_path": "user_manual_guides/move_forward.png",
                    "caption": "Figure: Move Forward Gesture",
                },
                {
                    "heading": "Move Backward (Only Thumb Up)",
                    "body": (
                        "Raise ONLY your thumb to move backward in slides."
                    ),
                    "image_path": "user_manual_guides/move_backward.png",
                    "caption": "Figure: Move Backward Gesture",
                },
                {
                    "heading": "Zoom In (Thumb + Index + Pinky)",
                    "body": (
                        "Keep Middle & Ring folded, raise the other three to Zoom In."
                    ),
                    "image_path": "user_manual_guides/zoom_in.png",
                    "caption": "Figure: Zoom In Gesture",
                },
                {
                    "heading": "Zoom Out (Thumb + Index + Middle + Pinky)",
                    "body": (
                        "Keep only the Ring finger folded, raise the rest to Zoom Out."
                    ),
                    "image_path": "user_manual_guides/zoom_out.png",
                    "caption": "Figure: Zoom Out Gesture",
                },
                {
                    "heading": "Voice Commands Overview",
                    "body": (
                        "Basic commands include opening/closing applications, web search, and more. "
                        "Speak clearly toward the microphone."
                    ),
                },
                {
                    "heading": "Opening and Closing Application",
                    "body": (
                        "For Example: Say (Open PowerPoint) clearly toward the microphone."
                    ),
                },
                {
                    "heading": "Search Results",
                    "body": (
                        "Say (Show me the results) after typing on the Google search bar."
                    ),
                },
                {
                    "heading": "New Tab",
                    "body": (
                        "Say (Open new tab)."
                    ),
                },
                {
                    "heading": "Minimize Window",
                    "body": (
                        "Say (Minimize the window)."
                    ),
                },
                {
                    "heading": "Maximize Window",
                    "body": (
                        "Say (Maximize the window)."
                    ),
                },
                {
                    "heading": "Close Window",
                    "body": (
                        "Say (Close the window)."
                    ),
                },
                {
                    "heading": "Scroll Up",
                    "body": (
                        "Say (Scroll Up)."
                    ),
                },
                {
                    "heading": "Scroll Down",
                    "body": (
                        "Say (Scroll Down)."
                    ),
                },
                {
                    "heading": "Create New Folder",
                    "body": (
                        "Say (Create a New Folder)."
                    ),
                },
                {
                    "heading": "Rename Folder",
                    "body": (
                        "Say (Rename the Folder)."
                    ),
                },
                {
                    "heading": "Delete Folder",
                    "body": (
                        "Say (Delete this folder)."
                    ),
                },
                {
                    "heading": "Typing Function",
                    "body": (
                        "Typing Function will perform by saying (Type Here) or (Type) Command. "
                        "For Example: Say (Type Here what is artificial intelligence) on Google search bar."
                    ),
                },
                {
                    "heading": "Troubleshooting",
                    "body": (
                        "If the camera feed doesn’t appear, ensure no other program is using the camera. "
                        "Check microphone permissions if voice commands do not work."
                    ),
                },
                {
                    "heading": "Support",
                    "body": (
                        "For further assistance, please contact the developer."
                    ),
                }, 
            ]

            # 2) Determine the user’s Downloads folder
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.exists(downloads_path):
                os.makedirs(downloads_path, exist_ok=True)

            pdf_filename = os.path.join(downloads_path, "HV_Manual.pdf")

            # 3) Create a SimpleDocTemplate for the PDF
            doc = SimpleDocTemplate(
                pdf_filename,
                pagesize=A4,
                rightMargin=40,
                leftMargin=40,
                topMargin=60,
                bottomMargin=60
            )

            # 4) Build a "story" list with Paragraph, Spacer, Image, etc.
            story = []
            styles = getSampleStyleSheet()
            style_heading = styles["Heading2"]
            style_body = styles["BodyText"]
            style_title = styles["Title"]

            # PDF Title
            story.append(Paragraph("HAND GESTURES AND VOICE CONTROLLED COMPUTER SYSTEM", style_title))
            story.append(Paragraph("User Manual Guidelines", style_title))
            story.append(Spacer(1, 0.2 * inch))

            # Add each manual section
            for section in manual_sections:
                # Heading
                story.append(Paragraph(section["heading"], style_heading))

                # Body Text
                story.append(Paragraph(section["body"], style_body))
                story.append(Spacer(1, 0.1 * inch))

                # Image (only if path is valid and not None)
                image_path = section.get("image_path")
                if image_path:  # i.e., not None or empty string
                    full_image_path = get_resource_path(image_path)
                    if os.path.exists(full_image_path):
                        try:
                            # Insert the image
                            rl_img = RLImage(full_image_path, width=4 * inch, height=3 * inch)
                            story.append(rl_img)

                            # Optional caption
                            if section.get("caption"):
                                caption_html = f"<font size=10><i>{section['caption']}</i></font>"
                                story.append(Paragraph(caption_html, style_body))
                            story.append(Spacer(1, 0.2 * inch))

                        except Exception as e:
                            # If there's an error loading the image, print or add a note
                            error_text = f"[Error loading image: {full_image_path}] {str(e)}"
                            story.append(Paragraph(error_text, style_body))
                    else:
                        # If file doesn't exist, note that
                        not_found_text = f"[Image not found: {full_image_path}]"
                        story.append(Paragraph(not_found_text, style_body))
                else:
                    # If there's no image path (None/empty), optionally note that
                    if section.get("caption"):
                        note_text = f"[No image for this section: {section['caption']}]"
                    else:
                        note_text = "[No image provided for this section.]"
                    story.append(Paragraph(note_text, style_body))

                story.append(Spacer(1, 0.2 * inch))

            # Final divider
            story.append(Paragraph("=========================================", style_title))

            # 5) Build the PDF
            doc.build(story)

            # Show a success message
            messagebox.showinfo(
                "Download Complete",
                f"PDF with images saved in your Downloads folder:\n{pdf_filename}"
            )


        # ---- Buttons: Close & Download ----
        close_button = tk.Button(
            bg_canvas,
            text="Close",
            command=manual_window.destroy,
            bg=ThemeColors.BUTTON_BG,
            fg=ThemeColors.BUTTON_FG,
            font=("Helvetica", 12, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=ThemeColors.BUTTON_HOVER,
            activeforeground=ThemeColors.TEXT_PRIMARY
        )
        close_button.place(relx=0.45, rely=0.9, anchor=tk.CENTER)

        download_button = tk.Button(
            bg_canvas,
            text="Download",
            command=download_manual_as_pdf,
            bg=ThemeColors.BUTTON_BG,
            fg=ThemeColors.BUTTON_FG,
            font=("Helvetica", 12, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=ThemeColors.BUTTON_HOVER,
            activeforeground=ThemeColors.TEXT_PRIMARY
        )
        download_button.place(relx=0.55, rely=0.9, anchor=tk.CENTER)

class ModeSelectionPage:
    def __init__(self, root):
        self.root = root
        self.root.title("Select Mode - Hand Gesture or Hand & Voice")
        self.root.state("zoomed")
        
        # Use theme colors from settings
        self.colors = {
            'primary': ThemeColors.PRIMARY,
            'secondary': ThemeColors.SECONDARY,
            'accent': ThemeColors.ACCENT,
            'background': ThemeColors.BG_DARK,
            'surface': ThemeColors.BG_DARKER,
            'card': ThemeColors.BG_SECONDARY,
            'text_primary': ThemeColors.TEXT_PRIMARY,
            'text_secondary': ThemeColors.TEXT_SECONDARY,
            'success': ThemeColors.SUCCESS,
            'warning': ThemeColors.WARNING,
            'error': ThemeColors.ERROR
        }
        
        self.root.configure(bg=ThemeColors.BG_DARK)

        # Try setting an icon if desired:
        logo_image_path = get_resource_path("app_logo.ico")
        try:
            self.root.iconbitmap(logo_image_path)
        except Exception as e:
            print(f"Failed to load logo: {e}")

        self.create_modern_mode_layout()

    def create_modern_mode_layout(self):
        """Create modern mode selection layout"""
        # Create main container
        self.main_frame = tk.Frame(self.root, bg=self.colors['background'])
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create gradient background
        self.bg_canvas = tk.Canvas(
            self.main_frame, 
            highlightthickness=0,
            bg=self.colors['background']
        )
        self.bg_canvas.pack(fill=tk.BOTH, expand=True)

        # Setup gradient
        self.root.bind('<Configure>', self.on_window_resize)
        self.root.after(100, self.create_gradient_background)
        
        # Create content
        self.root.after(200, self.create_mode_content)

    def create_gradient_background(self):
        """Create a modern gradient background"""
        self.bg_canvas.delete("gradient")
        
        width = self.bg_canvas.winfo_width()
        height = self.bg_canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            self.root.after(100, self.create_gradient_background)
            return
        
        # Create gradient strips
        for i in range(height):
            ratio = i / height
            
            # Interpolate between colors
            r1, g1, b1 = self.hex_to_rgb(self.colors['background'])
            r2, g2, b2 = self.hex_to_rgb(self.colors['surface'])
            
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            
            color = f"#{r:02x}{g:02x}{b:02x}"
            
            self.bg_canvas.create_line(
                0, i, width, i, 
                fill=color, 
                width=1,
                tags="gradient"
            )

    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def on_window_resize(self, event):
        """Handle window resize to update gradient"""
        if event.widget == self.root:
            self.root.after(50, self.create_gradient_background)

    def create_mode_content(self):
        """Create mode selection content with improved layout"""
        # Create main container with better spacing
        container_frame = tk.Frame(
            self.bg_canvas,
            bg=self.colors['background']
        )
        
        # Title with better positioning
        title_label = tk.Label(
            container_frame,
            text="Select Mode",
            font=("Segoe UI", 32, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['background']
        )
        title_label.pack(pady=(60, 40))
        
        # Mode selection grid frame
        modes_frame = tk.Frame(container_frame, bg=self.colors['background'])
        modes_frame.pack(pady=20)
        
        # Configure grid weights for responsive layout
        modes_frame.grid_columnconfigure(0, weight=1)
        modes_frame.grid_columnconfigure(1, weight=1)
        
        # Hand Gesture Mode Card
        gesture_card = self.create_improved_mode_card(
            modes_frame,
            icon="🖐️",
            title="Gesture Only",
            description="Control with hand movements\nPerfect for silent operation",
            features=["Silent operation", "Hand tracking", "Gesture recognition"],
            command=self.launch_gesture_only,
            column=0
        )
        
        # Hand & Voice Mode Card
        voice_card = self.create_improved_mode_card(
            modes_frame,
            icon="🎤",
            title="Hand & Voice",
            description="Full control with both hands and voice\nMaximum functionality",
            features=["Voice commands", "Hand gestures", "1500+ commands"],
            command=self.launch_hand_and_voice,
            column=1
        )
        
        # Navigation buttons with better spacing
        nav_frame = tk.Frame(container_frame, bg=self.colors['background'])
        nav_frame.pack(pady=(40, 20))
        
        # Go Back button
        back_button = self.create_improved_button(
            nav_frame,
            text="← Go Back",
            command=self.go_back,
            primary=False
        )
        back_button.pack()
        
        # Position the container in center
        self.bg_canvas.create_window(
            self.bg_canvas.winfo_reqwidth() // 2,
            self.bg_canvas.winfo_reqheight() // 2,
            window=container_frame,
            anchor=tk.CENTER
        )
        
        # Update container position when canvas size changes
        self.bg_canvas.bind('<Configure>', self.center_container)

    def create_mode_card(self, parent, icon, title, description, features, command, column):
        """Create a mode selection card"""
        card = tk.Frame(
            parent,
            bg=self.colors['surface'],
            relief=tk.FLAT,
            bd=0
        )
        card.grid(row=0, column=column, padx=30, pady=20, sticky="nsew")
        
        # Icon
        icon_label = tk.Label(
            card,
            text=icon,
            font=("Segoe UI", 48),
            bg=self.colors['surface'],
            fg=self.colors['accent']
        )
        icon_label.pack(pady=(30, 20))
        
        # Title
        title_label = tk.Label(
            card,
            text=title,
            font=("Segoe UI", 18, "bold"),
            bg=self.colors['surface'],
            fg=self.colors['text_primary']
        )
        title_label.pack(pady=(0, 15))
        
        # Description
        desc_label = tk.Label(
            card,
            text=description,
            font=("Segoe UI", 12),
            bg=self.colors['surface'],
            fg=self.colors['text_secondary'],
            justify=tk.CENTER
        )
        desc_label.pack(pady=(0, 20))
        
        # Features
        for feature in features:
            feature_label = tk.Label(
                card,
                text=f"✓ {feature}",
                font=("Segoe UI", 11),
                bg=self.colors['surface'],
                fg=self.colors['success'],
                anchor="w"
            )
            feature_label.pack(pady=2, padx=30, fill=tk.X)
        
        # Select button
        select_button = self.create_modern_button(
            card,
            text="Select Mode",
            command=command,
            primary=True
        )
        select_button.pack(pady=(30, 30))
        
        # Add hover effects to the card
        card.bind("<Enter>", lambda e: self.on_card_hover(card, True))
        card.bind("<Leave>", lambda e: self.on_card_hover(card, False))
        
        return card

    def on_card_hover(self, card, entering):
        """Handle card hover effects"""
        if entering:
            card.config(bg=self.colors['card'])
            for child in card.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=self.colors['card'])
        else:
            card.config(bg=self.colors['surface'])
            for child in card.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=self.colors['surface'])

    def create_modern_button(self, parent, text, command, primary=True):
        """Create a modern styled button"""
        if primary:
            bg_color = self.colors['primary']
            fg_color = self.colors['text_primary']
            active_bg = self.colors['secondary']
        else:
            bg_color = self.colors['surface']
            fg_color = self.colors['text_primary']
            active_bg = self.colors['card']
        
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 12, "bold"),
            bg=bg_color,
            fg=fg_color,
            activebackground=active_bg,
            activeforeground=fg_color,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            padx=30,
            pady=12
        )
        
        # Add hover effects
        button.bind("<Enter>", lambda e: self.on_button_hover(button, True, primary))
        button.bind("<Leave>", lambda e: self.on_button_hover(button, False, primary))
        
        return button

    def on_button_hover(self, button, entering, primary):
        """Handle button hover effects"""
        if entering:
            if primary:
                button.config(bg=self.colors['secondary'])
            else:
                button.config(bg=self.colors['card'])
        else:
            if primary:
                button.config(bg=self.colors['primary'])
            else:
                button.config(bg=self.colors['surface'])

    def center_container(self, event=None):
        """Center the container when window is resized"""
        canvas_width = self.bg_canvas.winfo_width()
        canvas_height = self.bg_canvas.winfo_height()
        
        # Update container position
        self.bg_canvas.coords("all", canvas_width // 2, canvas_height // 2)

    def create_improved_mode_card(self, parent, icon, title, description, features, command, column):
        """Create an improved mode selection card with better styling"""
        card = tk.Frame(
            parent,
            bg=self.colors['surface'],
            relief=tk.FLAT,
            bd=0
        )
        card.grid(row=0, column=column, padx=20, pady=10, sticky="nsew")
        
        # Icon
        icon_label = tk.Label(
            card,
            text=icon,
            font=("Segoe UI", 40),
            bg=self.colors['surface'],
            fg=self.colors['accent']
        )
        icon_label.pack(pady=(25, 15))
        
        # Title
        title_label = tk.Label(
            card,
            text=title,
            font=("Segoe UI", 16, "bold"),
            bg=self.colors['surface'],
            fg=self.colors['text_primary']
        )
        title_label.pack(pady=(0, 10))
        
        # Description
        desc_label = tk.Label(
            card,
            text=description,
            font=("Segoe UI", 11),
            bg=self.colors['surface'],
            fg=self.colors['text_secondary'],
            justify=tk.CENTER,
            wraplength=200
        )
        desc_label.pack(pady=(0, 15))
        
        # Features
        for feature in features:
            feature_label = tk.Label(
                card,
                text=f"✓ {feature}",
                font=("Segoe UI", 10),
                bg=self.colors['surface'],
                fg=self.colors['success'],
                anchor="w"
            )
            feature_label.pack(pady=1, padx=20, fill=tk.X)
        
        # Select button
        select_button = self.create_improved_button(
            card,
            text="Select Mode",
            command=command,
            primary=True
        )
        select_button.pack(pady=(20, 25))
        
        # Add hover effects to the card
        card.bind("<Enter>", lambda e: self.on_card_hover(card, True))
        card.bind("<Leave>", lambda e: self.on_card_hover(card, False))
        
        return card

    def create_improved_button(self, parent, text, command, primary=True):
        """Create an improved modern styled button"""
        if primary:
            bg_color = self.colors['primary']
            fg_color = "#082026"  # Dark text for better contrast
            active_bg = self.colors['secondary']
        else:
            bg_color = "transparent"
            fg_color = self.colors['text_primary']
            active_bg = "rgba(255,255,255,.06)"
        
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 11, "bold"),
            bg=bg_color,
            fg=fg_color,
            activebackground=active_bg,
            activeforeground=fg_color,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            padx=25,
            pady=10
        )
        
        # Add hover effects
        button.bind("<Enter>", lambda e: self.on_button_hover(button, True, primary))
        button.bind("<Leave>", lambda e: self.on_button_hover(button, False, primary))
        
        return button

    def launch_gesture_only(self):
        """
        Destroy this page and launch the HandGestureApp.
        """
        self.root.destroy()
        app_root = tk.Tk()
        HandGestureApp(app_root)  # <--- We'll define this class below
        app_root.mainloop()

    def launch_hand_and_voice(self):
        """
        Destroy this page and launch the existing HandVoiceControlApp.
        """
        self.root.destroy()
        app_root = tk.Tk()
        HandVoiceControlApp(app_root)
        app_root.mainloop()

    def go_back(self):
        """
        Destroy this page and go back to the UserInterface page.
        """
        self.root.destroy()
        new_root = tk.Tk()
        UserInterface(new_root)
        new_root.mainloop()

class HandGestureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hand Gesture-Only System [HV-SYSTEM]")
        self.root.state('zoomed')
        self.root.configure(bg=ThemeColors.BG_DARK)

        # Try to set icon
        logo_image_path = get_resource_path("app_logo.ico")
        try:
            self.root.iconbitmap(logo_image_path)
        except Exception as e:
            print(f"Failed to load application logo: {e}")

        # === Background Canvas with Theme Colors ===
        self.bg_canvas = tk.Canvas(
            self.root, 
            highlightthickness=0,
            bg=ThemeColors.BG_DARK
        )
        self.bg_canvas.pack(fill=tk.BOTH, expand=True)

        # Create gradient background
        self.create_gradient_background()

        # === Create improved button container ===
        button_frame = tk.Frame(self.bg_canvas, bg=ThemeColors.BG_DARK)
        button_frame.pack(pady=20)
        
        # Create improved buttons with better styling
        self.start_button = tk.Button(
            button_frame, 
            text="Start", 
            command=self.start_system, 
            font=("Segoe UI", 12, "bold"),
            bg=ThemeColors.PRIMARY,
            fg="#082026",
            activebackground=ThemeColors.SECONDARY,
            activeforeground="#082026",
            relief=tk.FLAT,
            cursor="hand2",
            padx=30,
            pady=12
        )
        self.start_button.pack(side=tk.LEFT, padx=10)
        
        self.go_back_button = tk.Button(
            button_frame, 
            text="Go Back", 
            command=self.go_back,
            font=("Segoe UI", 12, "bold"),
            bg="transparent",
            fg=ThemeColors.TEXT_PRIMARY,
            activebackground="rgba(255,255,255,.06)",
            activeforeground=ThemeColors.TEXT_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            padx=30,
            pady=12
        )
        self.go_back_button.pack(side=tk.LEFT, padx=10)
        
        self.stop_button = tk.Button(
            button_frame, 
            text="Stop", 
            command=self.stop_system,
            font=("Segoe UI", 12, "bold"),
            bg="transparent",
            fg=ThemeColors.TEXT_PRIMARY,
            activebackground="rgba(255,255,255,.06)",
            activeforeground=ThemeColors.TEXT_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            padx=30,
            pady=12
        )
        self.stop_button.pack(side=tk.LEFT, padx=10)

        # === Video Feed Canvas with improved styling ===
        canvas_frame = tk.Frame(
            self.bg_canvas, 
            bg=ThemeColors.BG_DARK,
            relief=tk.FLAT,
            bd=0
        )
        
        self.canvas = tk.Canvas(
            canvas_frame, 
            bg=ThemeColors.CANVAS_BG, 
            highlightbackground=ThemeColors.CANVAS_BORDER,
            highlightthickness=2,
            relief=tk.FLAT
        )
        
        # === Footer with improved styling ===
        self.footer = tk.Frame(
            self.bg_canvas, 
            bg=ThemeColors.BG_DARK,
            relief=tk.FLAT,
            bd=0
        )
        
        self.footer_label_left = tk.Label(
            self.footer, 
            text="Albukhary International University",
            bg=ThemeColors.BG_DARK, 
            fg=ThemeColors.TEXT_SECONDARY, 
            font=("Segoe UI", 10, "italic")
        )
        self.footer_label_center = tk.Label(
            self.footer,
            text="Developed by [Thiha Naing], 2024",
            bg=ThemeColors.BG_DARK, 
            fg=ThemeColors.TEXT_SECONDARY, 
            font=("Segoe UI", 10, "italic")
        )
        self.footer_label_right = tk.Label(
            self.footer, 
            text=f"Version: {settings.VERSION}",
            bg=ThemeColors.BG_DARK, 
            fg=ThemeColors.TEXT_SECONDARY, 
            font=("Segoe UI", 10, "italic")
        )

        self.adjust_layout()
        self.root.bind("<Configure>", self.adjust_layout)

        # We do NOT run the voice recognition thread or maintain transcription here
        # because this is the gesture-only app.

    def create_gradient_background(self):
        """Create a modern gradient background"""
        self.bg_canvas.delete("gradient")
        
        width = self.bg_canvas.winfo_width()
        height = self.bg_canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            self.root.after(100, self.create_gradient_background)
            return
        
        # Create gradient strips
        for i in range(height):
            # Create color transition from dark to primary
            ratio = i / height
            
            # Interpolate between colors
            r1, g1, b1 = self.hex_to_rgb(ThemeColors.BG_DARK)
            r2, g2, b2 = self.hex_to_rgb(ThemeColors.PRIMARY)
            
            r = int(r1 + (r2 - r1) * ratio * 0.3)  # Subtle gradient
            g = int(g1 + (g2 - g1) * ratio * 0.3)
            b = int(b1 + (b2 - b1) * ratio * 0.3)
            
            color = f"#{r:02x}{g:02x}{b:02x}"
            
            self.bg_canvas.create_line(
                0, i, width, i, 
                fill=color, 
                width=1,
                tags="gradient"
            )

    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def adjust_layout(self, event=None):
        screen_width = self.root.winfo_width()
        screen_height = self.root.winfo_height()

        # Update gradient background
        self.create_gradient_background()

        # Place buttons
        self.start_button.place(relx=0.35, rely=0.05, anchor=tk.CENTER)
        self.stop_button.place(relx=0.65, rely=0.05, anchor=tk.CENTER)
        self.go_back_button.place(relx=0.50, rely=0.05, anchor=tk.CENTER)


        # Adjust size and position for the camera frame
        cam_width = screen_width * 0.33  # 33% of screen width
        cam_height = screen_height * 0.45  # 45% of screen height
        self.canvas.place(relx=0.5, rely=0.55, anchor=tk.CENTER, width=cam_width, height=cam_height)

        # Footer
        self.footer.place(relx=0, rely=1, anchor=tk.SW, width=screen_width, height=60)
        self.footer_label_left.pack(side=tk.LEFT, padx=20)
        self.footer_label_center.pack(side=tk.LEFT, expand=True)
        self.footer_label_right.pack(side=tk.RIGHT, padx=20)

    def start_system(self):
        global hand_running
        if not running_event.is_set() and not hand_running:
            running_event.set()
            hand_running = True
            # Only run the hand tracking thread
            threading.Thread(target=self.run_hand_tracking, daemon=True).start()

    def stop_system(self):
        global hand_running
        running_event.clear()
        hand_running = False
        if cap is not None:
            cap.release()

    def go_back(self):
        # Stop the system
        self.stop_system()
        self.root.destroy()

        # Return to ModeSelectionPage or UserInterface as you wish
        # If you prefer going directly to ModeSelectionPage again:
        new_root = tk.Tk()
        ModeSelectionPage(new_root)
        new_root.mainloop()

    def run_hand_tracking(self):
        global cap, plocX, plocY, clocX, clocY, frame
        is_selecting = False

        cap = cv2.VideoCapture(0)
        cap.set(3, 640)
        cap.set(4, 480)
        detector = htm.handDetector(maxHands=1)

        while hand_running:
            success, img = cap.read()
            if not success:
                print("Failed to read from camera.")
                break

            try:
                # (Same code from your existing run_hand_tracking)
                img = detector.findHands(img)
                lmList, _ = detector.findPosition(img)

                if lmList:
                    # Example finger tips: Index=8, Middle=12, Ring=16, Pinky=20, Thumb=4
                    x1, y1 = lmList[8][1:], lmList[8][2:]  # If needed, but we only use x1,y1
                    # Actually: x1, y1 = lmList[8][1], lmList[8][2]

                    # Which fingers are up? -> [Thumb, Index, Middle, Ring, Pinky]
                    fingers = detector.fingersUp()
                    thumb_up = (fingers[0] == 1)
                    index_up = (fingers[1] == 1)
                    middle_up = (fingers[2] == 1)
                    ring_up = (fingers[3] == 1)
                    pinky_up = (fingers[4] == 1)

                    # ----- Move Mouse (Only Index) -----
                    if index_up and not middle_up and not pinky_up:
                        x_index = lmList[8][1]
                        y_index = lmList[8][2]

                        x_map = np.interp(x_index, (frameR, 640 - frameR), (0, wScr))
                        y_map = np.interp(y_index, (frameR, 480 - frameR), (0, hScr))
                        clocX = plocX + (x_map - plocX) / smoothening
                        clocY = plocY + (y_map - plocY) / smoothening
                        mouse.position = (wScr - clocX, clocY)  # invert X if desired
                        plocX, plocY = clocX, clocY

                    # ----- Left Click (Index + Middle) -----
                    elif index_up and middle_up and not thumb_up and not ring_up and not pinky_up:
                        mouse.click(Button.left, 1)
                        time.sleep(0.2)

                    # ----- Right Click (Index + Middle + Ring) -----
                    elif index_up and middle_up and ring_up and not thumb_up and not pinky_up:
                        mouse.click(Button.right, 1)
                        time.sleep(0.2)

                    # ----- Scroll Down (Index + Middle + Ring + Pinky, thumb down) -----
                    elif index_up and middle_up and ring_up and pinky_up and not thumb_up:
                        mouse.scroll(0, -2)
                        time.sleep(0.2)

                    # ----- Scroll Up (All 5 fingers) -----
                    elif thumb_up and index_up and middle_up and ring_up and pinky_up:
                        mouse.scroll(0, 2)
                        time.sleep(0.2)

                    # ----- Forward: ONLY Pinky => Right arrow -----
                    elif pinky_up and not thumb_up and not index_up and not middle_up and not ring_up:
                        pyautogui.press('right')
                        time.sleep(1.0)

                    # ----- Backward: ONLY Thumb => Left arrow -----
                    elif thumb_up and not index_up and not middle_up and not ring_up and not pinky_up:
                        pyautogui.press('left')
                        time.sleep(1.0)

                    # ----- Zoom Out (Thumb + Index + Middle + Pinky, ring down) -----
                    elif thumb_up and index_up and middle_up and pinky_up and not ring_up:
                        pyautogui.hotkey('ctrl', '-')
                        time.sleep(0.2)

                    # ----- Zoom In (Thumb + Index + Pinky, middle + ring down) -----
                    elif thumb_up and index_up and pinky_up and not middle_up and not ring_up:
                        pyautogui.hotkey('ctrl', '+')
                        time.sleep(0.2)

                # Convert frame to tk image and display
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img_resized = cv2.resize(img_rgb, (640, 480))
                img_tk = tk.PhotoImage(data=cv2.imencode('.ppm', img_resized)[1].tobytes())
                self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
                self.canvas.image = img_tk

            except Exception as e:
                print(f"Error during hand tracking: {e}")

        if cap is not None:
            cap.release()


class HandVoiceControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hand Gesture and Voice-Controlled Computer System [HV-SYSTEM]")
        self.root.state('zoomed')  # Start maximized
        
        # Use theme colors from settings
        self.colors = {
            'primary': ThemeColors.PRIMARY,
            'secondary': ThemeColors.SECONDARY,
            'accent': ThemeColors.ACCENT,
            'background': ThemeColors.BG_DARK,
            'surface': ThemeColors.BG_DARKER,
            'card': ThemeColors.BG_SECONDARY,
            'text_primary': ThemeColors.TEXT_PRIMARY,
            'text_secondary': ThemeColors.TEXT_SECONDARY,
            'success': ThemeColors.SUCCESS,
            'warning': ThemeColors.WARNING,
            'error': ThemeColors.ERROR
        }
        
        self.root.configure(bg=ThemeColors.BG_DARK)

        # === Set Application Icon ===
        logo_image_path = get_resource_path("app_logo.ico")
        try:
            self.root.iconbitmap(logo_image_path)
        except Exception as e:
            print(f"Failed to load application logo: {e}")

        self.create_modern_main_layout()

    def create_modern_main_layout(self):
        """Create the modern main application layout"""
        # Create main container
        self.main_frame = tk.Frame(self.root, bg=self.colors['background'])
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create gradient background
        self.bg_canvas = tk.Canvas(
            self.main_frame,
            highlightthickness=0,
            bg=self.colors['background']
        )
        self.bg_canvas.pack(fill=tk.BOTH, expand=True)

        # Setup gradient
        self.root.bind('<Configure>', self.on_window_resize)
        self.root.after(100, self.create_gradient_background)
        
        # Create the interface elements
        self.root.after(200, self.create_interface_elements)
        
        # Auto-start the system
        self.root.after(500, self.start_system)

    def create_gradient_background(self):
        """Create a modern gradient background"""
        self.bg_canvas.delete("gradient")
        
        width = self.bg_canvas.winfo_width()
        height = self.bg_canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            self.root.after(100, self.create_gradient_background)
            return
        
        # Create gradient strips
        for i in range(height):
            ratio = i / height
            
            # Interpolate between colors
            r1, g1, b1 = self.hex_to_rgb(self.colors['background'])
            r2, g2, b2 = self.hex_to_rgb(self.colors['surface'])
            
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            
            color = f"#{r:02x}{g:02x}{b:02x}"
            
            self.bg_canvas.create_line(
                0, i, width, i,
                fill=color,
                width=1,
                tags="gradient"
            )

    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def on_window_resize(self, event):
        """Handle window resize to update gradient"""
        if event.widget == self.root:
            self.root.after(50, self.create_gradient_background)
            self.root.after(100, self.adjust_layout)

    def create_interface_elements(self):
        """Create all interface elements with modern styling"""
        # Status indicator
        self.create_status_indicator()
        
        # Control panel
        self.create_control_panel()
        
        # Video feed area
        self.create_video_feed_area()
        
        # Transcription area
        self.create_transcription_area()
        
        # Footer
        self.create_modern_footer()
        
        # Initial layout
        self.adjust_layout()

    def create_status_indicator(self):
        """Create modern status indicator"""
        self.status_frame = tk.Frame(
            self.bg_canvas,
            bg=self.colors['card'],
            relief=tk.FLAT,
            bd=0
        )
        
        # Status title
        status_label = tk.Label(
            self.status_frame,
            text="🔧 System Status",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['card'],
            fg=self.colors['text_primary']
        )
        status_label.pack(pady=(10, 5))
        
        # Status indicator
        self.status_indicator = tk.Label(
            self.status_frame,
            text="● READY",
            font=("Segoe UI", 12, "bold"),
            bg=self.colors['card'],
            fg=self.colors['warning']
        )
        self.status_indicator.pack(pady=(0, 10))

    def create_control_panel(self):
        """Create modern control panel"""
        self.control_frame = tk.Frame(
            self.bg_canvas,
            bg=self.colors['card'],
            relief=tk.FLAT,
            bd=0
        )
        
        # Title
        control_title = tk.Label(
            self.control_frame,
            text="🎮 Control Panel",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['card'],
            fg=self.colors['text_primary']
        )
        control_title.pack(pady=(15, 10))
        
        # Button container
        button_container = tk.Frame(self.control_frame, bg=self.colors['card'])
        button_container.pack(pady=10)
        
        # Control buttons
        self.start_button = self.create_modern_button(
            button_container,
            text="🚀 Start System",
            command=self.start_system,
            primary=True,
            icon_color=self.colors['success']
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = self.create_modern_button(
            button_container,
            text="⏹️ Stop System",
            command=self.stop_system,
            primary=False,
            icon_color=self.colors['error']
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.go_back_button = self.create_modern_button(
            button_container,
            text="← Go Back",
            command=self.go_back,
            primary=False
        )
        self.go_back_button.pack(side=tk.LEFT, padx=5)

    def create_video_feed_area(self):
        """Create modern video feed area"""
        self.video_frame = tk.Frame(
            self.bg_canvas,
            bg=self.colors['card'],
            relief=tk.FLAT,
            bd=0
        )
        
        # Video title
        video_title = tk.Label(
            self.video_frame,
            text="📹 Camera Feed",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['card'],
            fg=self.colors['text_primary']
        )
        video_title.pack(pady=(15, 10))
        
        # Video canvas with modern styling
        self.canvas = tk.Canvas(
            self.video_frame,
            bg=self.colors['surface'],
            highlightbackground=self.colors['primary'],
            highlightthickness=2,
            relief=tk.FLAT
        )
        self.canvas.pack(pady=(0, 15), padx=15)

    def create_transcription_area(self):
        """Create modern transcription area"""
        self.transcription_frame = tk.Frame(
            self.bg_canvas,
            bg=self.colors['card'],
            relief=tk.FLAT,
            bd=0
        )
        
        # Transcription title
        transcription_title = tk.Label(
            self.transcription_frame,
            text="🎤 Voice Transcription",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['card'],
            fg=self.colors['text_primary']
        )
        transcription_title.pack(pady=(15, 10))
        
        # Transcription text area with modern styling
        self.transcription_text = scrolledtext.ScrolledText(
            self.transcription_frame,
            wrap=tk.WORD,
            font=("Consolas", 11),
            bg=self.colors['surface'],
            fg=self.colors['text_primary'],
            relief=tk.FLAT,
            insertbackground=self.colors['text_primary'],
            selectbackground=self.colors['primary'],
            selectforeground=self.colors['text_primary'],
            bd=0
        )
        self.transcription_text.pack(pady=(0, 15), padx=15, fill=tk.BOTH, expand=True)

    def create_modern_footer(self):
        """Create modern footer"""
        self.footer = tk.Frame(
            self.bg_canvas,
            bg=self.colors['card'],
            relief=tk.FLAT,
            bd=0
        )
        
        # Footer content
        footer_content = tk.Frame(self.footer, bg=self.colors['card'])
        footer_content.pack(expand=True, fill=tk.X, pady=10)

        self.footer_label_left = tk.Label(
            footer_content,
            text="🎓 Albukhary International University",
            bg=self.colors['card'],
            fg=self.colors['text_secondary'],
            font=("Segoe UI", 10)
        )
        self.footer_label_left.pack(side=tk.LEFT, padx=20)

        self.footer_label_center = tk.Label(
            footer_content,
            text="💻 Developed by [Thiha Naing], 2024",
            bg=self.colors['card'],
            fg=self.colors['text_secondary'],
            font=("Segoe UI", 10)
        )
        self.footer_label_center.pack(side=tk.LEFT, expand=True)

        self.footer_label_right = tk.Label(
            footer_content,
            text=f"🔖 Version: {settings.VERSION}",
            bg=self.colors['card'],
            fg=self.colors['text_secondary'],
            font=("Segoe UI", 10)
        )
        self.footer_label_right.pack(side=tk.RIGHT, padx=20)

    def create_modern_button(self, parent, text, command, primary=True, icon_color=None):
        """Create a modern styled button"""
        if primary:
            bg_color = self.colors['primary']
            fg_color = self.colors['text_primary']
            active_bg = self.colors['secondary']
        else:
            bg_color = self.colors['surface']
            fg_color = self.colors['text_primary']
            active_bg = self.colors['card']
        
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 10, "bold"),
            bg=bg_color,
            fg=fg_color,
            activebackground=active_bg,
            activeforeground=fg_color,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            padx=20,
            pady=8
        )
        
        # Add hover effects
        button.bind("<Enter>", lambda e: self.on_button_hover(button, True, primary))
        button.bind("<Leave>", lambda e: self.on_button_hover(button, False, primary))
        
        return button

    def on_button_hover(self, button, entering, primary):
        """Handle button hover effects"""
        if entering:
            if primary:
                button.config(bg=self.colors['secondary'])
            else:
                button.config(bg=self.colors['card'])
        else:
            if primary:
                button.config(bg=self.colors['primary'])
            else:
                button.config(bg=self.colors['surface'])

    def update_status(self, status, color_key='warning'):
        """Update the status indicator"""
        if hasattr(self, 'status_indicator'):
            self.status_indicator.config(
                text=f"● {status}",
                fg=self.colors[color_key]
            )

    def adjust_layout(self, event=None):
        """Adjust the layout for resizing and initial screen setup."""
        screen_width = self.root.winfo_width()
        screen_height = self.root.winfo_height()

        # Skip if elements are not yet created
        if not hasattr(self, 'status_frame'):
            return

        # Layout configuration
        padding = 20
        card_height = 150
        
        # Status indicator - top left
        if hasattr(self, 'status_frame'):
            self.status_frame.place(
                x=padding, 
                y=padding, 
                width=250, 
                height=100
            )
        
        # Control panel - top center
        if hasattr(self, 'control_frame'):
            self.control_frame.place(
                relx=0.5, 
                y=padding, 
                anchor=tk.N,
                width=400, 
                height=120
            )
        
        # Video feed - left side
        if hasattr(self, 'video_frame'):
            video_width = int(screen_width * 0.4)
            video_height = int(screen_height * 0.6)
            self.video_frame.place(
                x=padding,
                y=140,
                width=video_width,
                height=video_height
            )
            
            # Adjust canvas size within video frame
            if hasattr(self, 'canvas'):
                canvas_width = video_width - 30
                canvas_height = video_height - 80
                self.canvas.config(width=canvas_width, height=canvas_height)
        
        # Transcription area - right side
        if hasattr(self, 'transcription_frame'):
            trans_width = int(screen_width * 0.55)
            trans_height = int(screen_height * 0.6)
            trans_x = screen_width - trans_width - padding
            self.transcription_frame.place(
                x=trans_x,
                y=140,
                width=trans_width,
                height=trans_height
            )
            
            # Adjust text area size
            if hasattr(self, 'transcription_text'):
                text_width = trans_width - 30
                text_height = trans_height - 80
                self.transcription_text.config(width=text_width//8, height=text_height//15)
        
        # Footer - bottom
        if hasattr(self, 'footer'):
            footer_y = screen_height - 70
            self.footer.place(
                x=0, 
                y=footer_y, 
                width=screen_width, 
                height=70
            )


    def start_system(self):
        global hand_running
        if not running_event.is_set() and not hand_running:
            running_event.set()
            hand_running = True
            
            # Update status
            self.update_status("STARTING...", 'warning')

            threading.Thread(target=self.run_hand_tracking, daemon=True).start()
            threading.Thread(target=lambda: asyncio.run(send_receive()), daemon=True).start()
            self.update_transcription()
            
            # Update status to active
            self.root.after(1000, lambda: self.update_status("ACTIVE", 'success'))

    def stop_system(self):
        global hand_running
        running_event.clear()
        hand_running = False
        
        # Update status
        self.update_status("STOPPED", 'error')

        if cap is not None:
            cap.release()


    # === NEW METHOD: Go Back to the UserInterface page ===
    def go_back(self):
        # Stop the system if it is running
        self.stop_system()

        # Destroy this window
        self.root.destroy()

        # Reopen the UserInterface (assuming it's defined in the same file)
        new_root = tk.Tk()
        ModeSelectionPage(new_root)
        new_root.mainloop()


    def run_hand_tracking(self):
        """
        Continuously capture frames from webcam and apply gesture logic:
        - Move mouse (index finger)
        - Left/Right click
        - Scroll
        - Forward/Backward slides (pinky/thumb alone -> arrow keys)
        - Zoom in/out
        - Selection
        Displays the camera feed on self.canvas.
        """
        global cap, plocX, plocY, clocX, clocY, frame
        is_selecting = False

        cap = cv2.VideoCapture(0)
        cap.set(3, 640)
        cap.set(4, 480)
        detector = htm.handDetector(maxHands=1)

        while hand_running:
            success, img = cap.read()
            if not success:
                print("Failed to read from camera. Exiting loop.")
                break

            try:
                # Detect the hand and find landmarks
                img = detector.findHands(img)
                lmList, _ = detector.findPosition(img)

                if lmList:
                    # Example finger tips: Index=8, Middle=12, Ring=16, Pinky=20, Thumb=4
                    x1, y1 = lmList[8][1:], lmList[8][2:]  # If needed, but we only use x1,y1
                    # Actually: x1, y1 = lmList[8][1], lmList[8][2]

                    # Which fingers are up? -> [Thumb, Index, Middle, Ring, Pinky]
                    fingers = detector.fingersUp()
                    thumb_up = (fingers[0] == 1)
                    index_up = (fingers[1] == 1)
                    middle_up = (fingers[2] == 1)
                    ring_up = (fingers[3] == 1)
                    pinky_up = (fingers[4] == 1)

                    # ----- Move Mouse (Only Index) -----
                    if index_up and not middle_up and not pinky_up:
                        x_index = lmList[8][1]
                        y_index = lmList[8][2]

                        x_map = np.interp(x_index, (frameR, 640 - frameR), (0, wScr))
                        y_map = np.interp(y_index, (frameR, 480 - frameR), (0, hScr))
                        clocX = plocX + (x_map - plocX) / smoothening
                        clocY = plocY + (y_map - plocY) / smoothening
                        mouse.position = (wScr - clocX, clocY)  # invert X if desired
                        plocX, plocY = clocX, clocY

                    # ----- Left Click (Index + Middle) -----
                    elif index_up and middle_up and not thumb_up and not ring_up and not pinky_up:
                        mouse.click(Button.left, 1)
                        time.sleep(0.2)

                    # ----- Right Click (Index + Middle + Ring) -----
                    elif index_up and middle_up and ring_up and not thumb_up and not pinky_up:
                        mouse.click(Button.right, 1)
                        time.sleep(0.2)

                    # ----- Scroll Down (Index + Middle + Ring + Pinky, thumb down) -----
                    elif index_up and middle_up and ring_up and pinky_up and not thumb_up:
                        mouse.scroll(0, -2)
                        time.sleep(0.2)

                    # ----- Scroll Up (All 5 fingers) -----
                    elif thumb_up and index_up and middle_up and ring_up and pinky_up:
                        mouse.scroll(0, 2)
                        time.sleep(0.2)

                    # ----- Forward: ONLY Pinky => Right arrow -----
                    elif pinky_up and not thumb_up and not index_up and not middle_up and not ring_up:
                        pyautogui.press('right')
                        time.sleep(1.0)

                    # ----- Backward: ONLY Thumb => Left arrow -----
                    elif thumb_up and not index_up and not middle_up and not ring_up and not pinky_up:
                        pyautogui.press('left')
                        time.sleep(1.0)

                    # ----- Zoom Out (Thumb + Index + Middle + Pinky, ring down) -----
                    elif thumb_up and index_up and middle_up and pinky_up and not ring_up:
                        pyautogui.hotkey('ctrl', '-')
                        time.sleep(0.2)

                    # ----- Zoom In (Thumb + Index + Pinky, middle + ring down) -----
                    elif thumb_up and index_up and pinky_up and not middle_up and not ring_up:
                        pyautogui.hotkey('ctrl', '+')
                        time.sleep(0.2)

                    # ----- Selection logic: if index+middle+ring+pinky up => hold left button -----
                    if index_up and middle_up and ring_up and pinky_up:
                        if not is_selecting:
                            mouse.press(Button.left)
                            is_selecting = True
                            print("Selection started")
                    else:
                        if is_selecting:
                            mouse.release(Button.left)
                            is_selecting = False
                            print("Selection ended")


                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img_resized = cv2.resize(img_rgb, (640, 480))
                img_tk = tk.PhotoImage(data=cv2.imencode('.ppm', img_resized)[1].tobytes())
                self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
                self.canvas.image = img_tk

            except Exception as e:
                print(f"Error during hand tracking: {e}")

        if cap is not None:
            cap.release()

    def update_transcription(self):
        if not transcription_queue.empty():
            transcription = transcription_queue.get()
            self.transcription_text.insert(tk.END, transcription + "\n")
            self.transcription_text.see(tk.END)
            try:
                perform_command(transcription)
            except Exception as e:
                print(f"Error in perform_command: {e}")

        if running_event.is_set():
            self.root.after(50, self.update_transcription)


# === Launch the Combined Application ===
if __name__ == "__main__":
    root = tk.Tk()
    app = UserInterface(root)
    root.mainloop()
