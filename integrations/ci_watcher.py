import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Dict, Any

from utils.logger import get_logger

logger = get_logger(__name__)

class CIWatcher(FileSystemEventHandler):
    """Watch for file changes and trigger healing"""
    
    def __init__(self, pipeline, watch_path: str = "."):
        self.pipeline = pipeline
        self.watch_path = watch_path
        self.observer = None
    
    def start(self):
        """Start watching"""
        
        self.observer = Observer()
        self.observer.schedule(self, self.watch_path, recursive=True)
        self.observer.start()
        
        logger.info(f"Started watching {self.watch_path}")
    
    def stop(self):
        """Stop watching"""
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
    
    def on_modified(self, event):
        """Handle file modification"""
        
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        # Only process Python files
        if not file_path.endswith('.py'):
            return
        
        # Skip certain directories
        skip_dirs = ['venv', 'env', '__pycache__', '.git']
        if any(skip_dir in file_path for skip_dir in skip_dirs):
            return
        
        logger.info(f"File modified: {file_path}")
        
        # Could trigger analysis/healing here
        # For now, just log