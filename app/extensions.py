"""
Flask extensions initialization module.
Centralizes all extension initialization for the application factory pattern.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_mail import Mail
from flask_socketio import SocketIO
from firebase_config import auth, db
import os

# Global extension instances
limiter = None
talisman = None
mail = None
socketio = None


def init_extensions(app):
    """
    Initialize all Flask extensions with the given application.
    
    Args:
        app: Flask application instance
    """
    global limiter, talisman, mail, socketio
    
    env = os.environ.get('FLASK_ENV', 'production')
    
    # Initialize rate limiter
    disable_rate_limits = (
        env == 'development' or
        os.environ.get('DISABLE_RATE_LIMITS', 'False').lower() == 'true'
    )
    
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[app.config['RATE_LIMIT_DEFAULT']],
        enabled=(not disable_rate_limits),
        storage_uri="memory://"
    )
    
    # Initialize security headers with Talisman
    talisman = Talisman(
        app,
        force_https=app.config['SESSION_COOKIE_SECURE'],
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        strict_transport_security_include_subdomains=True,
        content_security_policy={
            'default-src': "'self'",
            'script-src': ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://fonts.googleapis.com", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com", "https://cdn.jsdelivr.net", "https://cdn.socket.io"],
            'style-src': ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://fonts.googleapis.com", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com"],
            'font-src': ["https://fonts.googleapis.com", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com"],
            'img-src': ["'self'", "data:", "https:"],
            'connect-src': ["'self'", "https://cdn.jsdelivr.net", "https://cdn.socket.io", "wss:", "ws:"],
            'frame-ancestors': "'none'",
            'base-uri': "'self'",
            'form-action': "'self'"
        },
        referrer_policy='strict-origin-when-cross-origin'
    )
    
    # Initialize Flask-Mail
    mail = Mail(app)
    
    # Initialize Flask-SocketIO for real-time chat
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*",
        async_mode='threading',
        logger=True,
        engineio_logger=False,
        manage_session=False
    )


def get_limiter():
    """Get the rate limiter instance."""
    return limiter


def get_mail():
    """Get the mail instance."""
    return mail


def get_socketio():
    """Get the SocketIO instance."""
    return socketio
