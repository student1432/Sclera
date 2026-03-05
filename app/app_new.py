"""
Refactored Flask application entry point.
Uses the application factory pattern with modular blueprints and service layer.
"""

from app import create_app, run_app
from app.socketio_handlers.events import register_socketio_events
from app.extensions import get_socketio
import os

# Create application instance
app = create_app()

# Register SocketIO events
socketio = get_socketio()
register_socketio_events(socketio)

# Dedicated CSS endpoint with explicit MIME type
@app.route('/styles.css')
def serve_css():
    from flask import send_from_directory
    return send_from_directory('static', 'styles.css')

if __name__ == '__main__':
    run_app(app)
