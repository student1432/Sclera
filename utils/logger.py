"""
Structured logging configuration for StudyOS
Provides consistent, structured logging across the application
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
import structlog


def setup_logging(app):
    """Set up structured logging for the Flask application"""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Set up standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    )
    
    # Create logger
    logger = structlog.get_logger("studyos")
    app.logger = logger
    
    return logger


class AppLogger:
    """Application logger with structured output"""
    
    def __init__(self, name: str = "studyos"):
        self.logger = structlog.get_logger(name)
    
    def info(self, message: str, **kwargs):
        """Log info level message"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning level message"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error level message"""
        self.logger.error(message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug level message"""
        self.logger.debug(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical level message"""
        self.logger.critical(message, **kwargs)
    
    def security_event(self, event_type: str, user_id: str = None, 
                      ip_address: str = None, details: Dict = None):
        """
        Log security-related events
        Args:
            event_type: Type of security event (login, logout, failed_login, etc.)
            user_id: User identifier
            ip_address: IP address of the request
            details: Additional event details
        """
        self.logger.info(
            "security_event",
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            timestamp=datetime.utcnow().isoformat(),
            details=details or {}
        )
    
    def audit_log(self, action: str, user_id: str, resource: str, 
                  success: bool = True, details: Dict = None):
        """
        Log audit trail for data changes
        Args:
            action: Action performed (create, update, delete)
            user_id: User who performed the action
            resource: Resource that was modified
            success: Whether the action was successful
            details: Additional details
        """
        self.logger.info(
            "audit_log",
            action=action,
            user_id=user_id,
            resource=resource,
            success=success,
            timestamp=datetime.utcnow().isoformat(),
            details=details or {}
        )


# Global logger instance
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
