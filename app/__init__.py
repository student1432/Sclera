"""
Flask application factory module.
Creates and configures the Flask application with all blueprints and extensions.
"""

from flask import Flask
from config import config
from app.extensions import init_extensions, get_socketio
import os


def create_app(config_name=None):
    """
    Application factory function.
    
    Args:
        config_name: Configuration name (development, production, testing)
        
    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    env = config_name or os.environ.get('FLASK_ENV', 'production')
    config[env].init_app(app)
    
    # Initialize extensions
    init_extensions(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register SocketIO events
    register_socketio_events(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register request handlers
    register_request_handlers(app)
    
    return app


def register_blueprints(app):
    """Register all application blueprints."""
    from app.blueprints.auth import auth_bp
    from app.blueprints.syllabus import syllabus_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.bubbles import bubbles_bp
    from app.blueprints.institution import institution_bp
    
    # Register blueprints with URL prefixes
    app.register_blueprint(auth_bp)
    app.register_blueprint(syllabus_bp, url_prefix='/syllabus')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(bubbles_bp, url_prefix='/bubbles')
    app.register_blueprint(institution_bp, url_prefix='/institution')


def register_socketio_events(app):
    """Register SocketIO event handlers."""
    from app.socketio_handlers.events import register_socketio_events
    from app.extensions import get_socketio
    
    socketio = get_socketio()
    register_socketio_events(socketio)


def register_error_handlers(app):
    """Register application error handlers."""
    from utils import logger
    import traceback
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors"""
        if app.request_context and app.request_context.request.is_json:
            return {'error': 'Not found', 'message': 'Resource not found'}, 404
        return 'error.html', 404
    
    @app.errorhandler(429)
    def rate_limit_handler(error):
        """Handle rate limit exceeded"""
        logger.security_event(
            "rate_limit_exceeded", 
            user_id=getattr(app.request_context, 'session', {}).get('uid'), 
            ip_address=app.request_context.request.remote_addr if app.request_context else None
        )
        if app.request_context and app.request_context.request.is_json:
            return {'error': 'Too many requests', 'message': 'Rate limit exceeded. Please try again later.'}, 429
        return 'error.html', 429
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle internal server errors"""
        logger.error(
            "internal_server_error", 
            error=str(error), 
            path=app.request_context.request.path if app.request_context else None,
            traceback=traceback.format_exc()
        )
        if app.request_context and app.request_context.request.is_json:
            return {'error': 'Internal server error', 'message': 'Something went wrong'}, 500
        return 'error.html', 500


def register_request_handlers(app):
    """Register before and after request handlers."""
    from utils import logger
    from app.models.auth import institution_login_guard
    
    @app.before_request
    def log_request():
        """Log all incoming requests"""
        from flask import request, session
        
        # Skip login guard for API routes
        if request.path.startswith('/api/'):
            return None
        
        guard_resp = institution_login_guard()
        if guard_resp is not None:
            return guard_resp
            
        logger.debug("request_started",
                     method=request.method,
                     path=request.path,
                     ip=request.remote_addr,
                     user_agent=str(request.user_agent))
    
    @app.after_request
    def log_response(response):
        """Log all responses"""
        from flask import request
        
        logger.info("request_completed",
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    ip=request.remote_addr)
        return response


def run_app(app):
    """Run the Flask application with SocketIO."""
    socketio = get_socketio()
    env = os.environ.get('FLASK_ENV', 'production')
    debug = env == 'development'
    port = int(os.environ.get('PORT', 5000))
    
    logger = __import__('utils').logger
    logger.info("application_startup", environment=env, debug=debug, port=port)
    
    socketio.run(app, debug=debug, host='0.0.0.0', port=port)
