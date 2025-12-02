import logging
import sys
from typing import Optional

# Configure logging format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Get configured logger"""
    
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
    
    log_level = level or 'INFO'
    logger.setLevel(getattr(logging, log_level.upper()))
    
    return logger