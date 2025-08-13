"""
Logging configuration for the application
"""
import logging
import os
from datetime import datetime
from config.settings import settings

def setup_logger() -> logging.Logger:
    """Setup and configure logger"""
    
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Create logger
    logger = logging.getLogger('hv_system')
    logger.setLevel(settings.get_log_level())
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # File handler
    log_filename = f"logs/hv_system_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(settings.get_log_level())
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    if not logger.handlers:  # Avoid duplicate handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# Global logger instance
logger = setup_logger()

