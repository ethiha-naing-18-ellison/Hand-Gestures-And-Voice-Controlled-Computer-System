"""
Dynamic application discovery utilities for cross-platform compatibility
"""
import os
import winreg
from pathlib import Path
from typing import Optional, Dict, List
from utils.logger import logger

class ApplicationFinder:
    """Find applications dynamically instead of using hardcoded paths"""
    
    def __init__(self):
        self._app_cache: Dict[str, str] = {}
        self._common_paths = [
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            r"C:\Users\{username}\AppData\Local\Programs",
            r"C:\Users\{username}\AppData\Roaming",
        ]
    
    def find_application(self, app_name: str) -> Optional[str]:
        """Find application executable path"""
        
        # Check cache first
        if app_name in self._app_cache:
            return self._app_cache[app_name]
        
        # Try different methods to find the application
        methods = [
            self._find_in_registry,
            self._find_in_common_paths,
            self._find_in_path_env,
            self._find_windows_apps
        ]
        
        for method in methods:
            try:
                path = method(app_name)
                if path and os.path.exists(path):
                    self._app_cache[app_name] = path
                    logger.info(f"Found {app_name} at: {path}")
                    return path
            except Exception as e:
                logger.debug(f"Method {method.__name__} failed for {app_name}: {e}")
        
        logger.warning(f"Could not find application: {app_name}")
        return None
    
    def _find_in_registry(self, app_name: str) -> Optional[str]:
        """Find application in Windows registry"""
        registry_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        ]
        
        for reg_path in registry_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                    if app_name.lower() in display_name.lower():
                                        install_location, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                        return self._find_exe_in_directory(install_location)
                                except FileNotFoundError:
                                    continue
                        except OSError:
                            continue
            except Exception as e:
                logger.debug(f"Registry search failed: {e}")
        
        return None
    
    def _find_in_common_paths(self, app_name: str) -> Optional[str]:
        """Search in common installation directories"""
        username = os.getenv('USERNAME', '')
        
        for path_template in self._common_paths:
            search_path = path_template.format(username=username)
            if os.path.exists(search_path):
                for root, dirs, files in os.walk(search_path):
                    for file in files:
                        if (app_name.lower() in file.lower() and 
                            file.lower().endswith('.exe')):
                            return os.path.join(root, file)
        
        return None
    
    def _find_in_path_env(self, app_name: str) -> Optional[str]:
        """Find application in PATH environment variable"""
        path_env = os.getenv('PATH', '')
        for path_dir in path_env.split(os.pathsep):
            if os.path.exists(path_dir):
                exe_path = os.path.join(path_dir, f"{app_name}.exe")
                if os.path.exists(exe_path):
                    return exe_path
        
        return None
    
    def _find_windows_apps(self, app_name: str) -> Optional[str]:
        """Find Windows Store apps and built-in applications"""
        windows_apps = {
            'calculator': 'calc.exe',
            'notepad': 'notepad.exe',
            'paint': 'mspaint.exe',
            'wordpad': 'write.exe',
            'explorer': 'explorer.exe',
            'cmd': 'cmd.exe',
            'powershell': 'powershell.exe',
            'taskmgr': 'taskmgr.exe',
            'control': 'control.exe'
        }
        
        if app_name.lower() in windows_apps:
            return windows_apps[app_name.lower()]
        
        return None
    
    def _find_exe_in_directory(self, directory: str) -> Optional[str]:
        """Find executable file in given directory"""
        if not directory or not os.path.exists(directory):
            return None
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith('.exe'):
                    return os.path.join(root, file)
        
        return None
    
    def get_supported_applications(self) -> Dict[str, str]:
        """Get list of applications that can be discovered"""
        apps_to_find = [
            'chrome', 'firefox', 'edge', 'notepad', 'calculator',
            'powerpoint', 'excel', 'word', 'outlook', 'teams',
            'spotify', 'vlc', 'discord', 'zoom', 'steam'
        ]
        
        supported = {}
        for app in apps_to_find:
            path = self.find_application(app)
            if path:
                supported[app] = path
        
        return supported

# Global application finder instance
app_finder = ApplicationFinder()

