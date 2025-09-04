import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from config import LOG_LEVEL, LOG_FORMAT

# Configure logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

class FileUtils:
    """File management utilities (trimmed to essentials)"""

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"

class SessionUtils:
    """Session management utilities"""
    
    @staticmethod
    def log_session_activity(activity: str, details: Dict[str, Any] = None):
        """Log session activity"""
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "activity": activity,
            "details": details or {}
        }
        
        logger.info(f"Session activity: {activity}", extra=details)
        return log_entry
    
    @staticmethod
    def get_session_stats() -> Dict[str, Any]:
        """Get session statistics - placeholder for when session state is available"""
        stats = {
            "start_time": datetime.now().isoformat(),
            "images_uploaded": 0,
            "audio_recorded": 0,
            "queries_processed": 0,
            "total_activities": 0
        }
        return stats

class ValidationUtils:
    """Input validation utilities"""
    
    @staticmethod
    def validate_image_file(uploaded_file) -> Dict[str, Any]:
        """Validate uploaded image file"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "file_info": {}
        }
        
        if uploaded_file is None:
            validation_result["is_valid"] = False
            validation_result["errors"].append("No file uploaded")
            return validation_result
        
        # Check file size (max 10MB for images)
        file_size = len(uploaded_file.getvalue())
        validation_result["file_info"]["size"] = file_size
        validation_result["file_info"]["size_formatted"] = FileUtils.format_file_size(file_size)
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            validation_result["is_valid"] = False
            validation_result["errors"].append("File size exceeds 10MB limit")
        
        # Check file type
        file_extension = uploaded_file.name.split('.')[-1].lower()
        validation_result["file_info"]["extension"] = file_extension
        
        from config import ALLOWED_IMAGE_TYPES
        if file_extension not in [ext.lower() for ext in ALLOWED_IMAGE_TYPES]:
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}")
        
        return validation_result
    
    @staticmethod
    def validate_audio_file(uploaded_file) -> Dict[str, Any]:
        """Validate uploaded audio file"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "file_info": {}
        }
        
        if uploaded_file is None:
            validation_result["is_valid"] = False
            validation_result["errors"].append("No audio recorded")
            return validation_result
        
        # Check file size (max 25MB for audio)
        file_size = len(uploaded_file.getvalue())
        validation_result["file_info"]["size"] = file_size
        validation_result["file_info"]["size_formatted"] = FileUtils.format_file_size(file_size)
        
        if file_size > 25 * 1024 * 1024:  # 25MB limit
            validation_result["is_valid"] = False
            validation_result["errors"].append("Audio file size exceeds 25MB limit")
        
        if file_size < 1024:  # Less than 1KB might be empty
            validation_result["warnings"].append("Audio file seems very small - please check recording")
        
        return validation_result