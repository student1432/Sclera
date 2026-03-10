"""
Simple logging configuration for StudyOS
Provides basic logging functionality without external dependencies
"""
import logging
import sys
from datetime import datetime
from typing import Any, Dict


class AppLogger:
    """Simple logger wrapper for StudyOS"""
    
    def __init__(self, name: str = "StudyOS"):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        if kwargs:
            message += f" - {kwargs}"
        self.logger.info(message)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        if kwargs:
            message += f" - {kwargs}"
        self.logger.error(message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        if kwargs:
            message += f" - {kwargs}"
        self.logger.warning(message)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        if kwargs:
            message += f" - {kwargs}"
        self.logger.debug(message)
    
    def security_event(self, event_type: str, **kwargs):
        """Log security-related events"""
        message = f"SECURITY_EVENT: {event_type}"
        if kwargs:
            message += f" - {kwargs}"
        self.logger.warning(message)  # Use warning level for security events


def setup_logging(app):
    """Set up logging for the Flask application"""
    # Simple logging setup without structlog
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


# Create global logger instance
logger = AppLogger()


def log_request_info(app):
    """Middleware to log request information"""
    @app.after_request
    def after_request(response):
        logger.info(
            "request_completed",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            ip=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None
        )
        return response
