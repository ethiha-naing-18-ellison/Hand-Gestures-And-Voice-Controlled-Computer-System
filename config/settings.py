"""
Configuration management for Hand Gesture and Voice Control System
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    """Application settings loaded from environment variables"""
    
    # API Configuration
    ASSEMBLYAI_API_KEY: str = os.getenv('ASSEMBLYAI_API_KEY', '')
    ASSEMBLYAI_WEBSOCKET_URL: str = os.getenv(
        'ASSEMBLYAI_WEBSOCKET_URL', 
        'wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000'
    )
    
    # Audio Configuration
    FRAME_PER_BUFFER: int = int(os.getenv('FRAME_PER_BUFFER', '3200'))
    AUDIO_CHANNELS: int = int(os.getenv('AUDIO_CHANNELS', '1'))
    AUDIO_RATE: int = int(os.getenv('AUDIO_RATE', '16000'))
    
    # Hand Tracking Configuration
    MAX_HANDS: int = int(os.getenv('MAX_HANDS', '1'))
    DETECTION_CONFIDENCE: float = float(os.getenv('DETECTION_CONFIDENCE', '0.5'))
    TRACKING_CONFIDENCE: float = float(os.getenv('TRACKING_CONFIDENCE', '0.5'))
    SMOOTHENING_FACTOR: int = int(os.getenv('SMOOTHENING_FACTOR', '7'))
    FRAME_REDUCTION: int = int(os.getenv('FRAME_REDUCTION', '100'))
    
    # UI Configuration
    DEFAULT_THEME: str = os.getenv('DEFAULT_THEME', 'dark')
    WINDOW_TITLE: str = os.getenv('WINDOW_TITLE', 'Hand Gesture and Voice Control System')
    VERSION: str = os.getenv('VERSION', '2.0.0')
    
    # System Configuration
    DEBUG_MODE: bool = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that all required settings are present"""
        if not cls.ASSEMBLYAI_API_KEY:
            logging.error("ASSEMBLYAI_API_KEY is required but not found in environment variables")
            return False
        return True
    
    @classmethod
    def get_log_level(cls) -> int:
        """Convert log level string to logging constant"""
        levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return levels.get(cls.LOG_LEVEL.upper(), logging.INFO)

# Global settings instance
settings = Settings()

# Validate settings on import
if not settings.validate():
    raise ValueError("Invalid configuration. Please check your environment variables.")

