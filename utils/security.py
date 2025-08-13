"""
Security utilities for input validation and sanitization
"""
import re
import subprocess
import shlex
from typing import List, Optional
from utils.logger import logger

class SecurityValidator:
    """Security validation and sanitization utilities"""
    
    # Whitelist of allowed system commands
    ALLOWED_COMMANDS = {
        'shutdown': ['shutdown', '/s', '/r', '/l', '/t'],
        'system': ['notepad', 'calc', 'mspaint', 'explorer'],
        'hotkeys': ['ctrl', 'shift', 'alt', 'win', 'tab', 'enter', 'esc'],
        'keys': ['left', 'right', 'up', 'down', 'space', 'backspace', 'delete'],
        'function_keys': [f'f{i}' for i in range(1, 13)]
    }
    
    # Dangerous patterns to block
    DANGEROUS_PATTERNS = [
        r'[;&|`$]',  # Command injection characters
        r'\.\.[/\\]',  # Directory traversal
        r'rm\s+-rf',  # Dangerous deletion commands
        r'del\s+/[sf]',  # Windows dangerous deletion
        r'format\s+c:',  # Format system drive
        r'net\s+user',  # User manipulation
        r'reg\s+delete',  # Registry deletion
    ]
    
    @classmethod
    def sanitize_voice_command(cls, command: str) -> str:
        """Sanitize voice command input"""
        if not command or not isinstance(command, str):
            return ""
        
        # Convert to lowercase and strip whitespace
        command = command.lower().strip()
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                logger.warning(f"Blocked potentially dangerous command: {command}")
                return ""
        
        # Remove special characters except allowed ones
        command = re.sub(r'[^\w\s\-\+\.]', '', command)
        
        return command
    
    @classmethod
    def validate_system_command(cls, command: str) -> bool:
        """Validate if system command is allowed"""
        if not command:
            return False
        
        command_parts = command.lower().split()
        if not command_parts:
            return False
        
        base_command = command_parts[0]
        
        # Check if base command is in whitelist
        for category, allowed in cls.ALLOWED_COMMANDS.items():
            if base_command in allowed:
                return True
        
        logger.warning(f"Blocked unauthorized system command: {command}")
        return False
    
    @classmethod
    def safe_execute_command(cls, command: str) -> bool:
        """Safely execute system command with validation"""
        if not cls.validate_system_command(command):
            return False
        
        try:
            # Use shlex to safely parse command
            cmd_parts = shlex.split(command)
            
            # Execute with limited permissions
            result = subprocess.run(
                cmd_parts,
                timeout=30,  # 30 second timeout
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"Command failed: {command}, Error: {result.stderr}")
                return False
            
            logger.info(f"Successfully executed command: {command}")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return False
        except Exception as e:
            logger.error(f"Error executing command {command}: {str(e)}")
            return False
    
    @classmethod
    def validate_file_path(cls, file_path: str) -> bool:
        """Validate file path for security"""
        if not file_path:
            return False
        
        # Check for directory traversal
        if '..' in file_path or '~' in file_path:
            logger.warning(f"Blocked path traversal attempt: {file_path}")
            return False
        
        # Check for system directories
        dangerous_paths = [
            'system32', 'windows', 'program files', 'boot'
        ]
        
        path_lower = file_path.lower()
        for dangerous in dangerous_paths:
            if dangerous in path_lower:
                logger.warning(f"Blocked access to system directory: {file_path}")
                return False
        
        return True

# Global security validator instance
security = SecurityValidator()

