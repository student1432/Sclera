"""
AI Assistant routes.
Handles AI chat functionality, consent management, and conversation threads.
"""

from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from app.models.auth import require_login
from app.models.firestore_helpers import get_document
from ai_assistant import get_ai_assistant
from utils import logger
from firebase_config import db
from firebase_admin import firestore
from datetime import datetime

ai_bp = Blueprint('ai_assistant', __name__)


@ai_bp.route('/ai-assistant')
@require_login
def ai_assistant_page():
    """AI Assistant main page with consent check."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User profile not found', 'error')
        return redirect(url_for('core.landing'))
    
    # Check AI consent
    ai_consent = user_data.get('ai_consent', False)
    
    if not ai_consent:
        return render_template('ai_assistant_consent.html', user_data=user_data)
    
    context = {
        'user_data': user_data,
        'has_class': bool(user_data.get('class_ids'))
    }
    return render_template('ai_assistant.html', **context)


@ai_bp.route('/ai-assistant/consent', methods=['POST'])
@require_login
def ai_assistant_consent():
    """Handle AI consent decision."""
    uid = session['uid']
    consent_given = request.form.get('consent') == 'yes'
    
    try:
        user_ref = db.collection('users').document(uid)
        user_ref.update({
            'ai_consent': consent_given,
            'ai_consent_date': datetime.utcnow() if consent_given else None,
            'updated_at': datetime.utcnow()
        })
        
        if consent_given:
            flash('AI Assistant access granted! You can now use AI features.', 'success')
        else:
            flash('AI Assistant access denied. You can enable it later from your profile.', 'info')
    
    except Exception as e:
        logger.error(f"AI consent update error: {str(e)}")
        flash('An error occurred while updating your consent preference', 'error')
    
    return redirect(url_for('dashboard.profile'))


@ai_bp.route('/api/ai/chat/planning', methods=['POST'])
@require_login
def ai_chat_planning():
    """API endpoint for planning chatbot."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data or not user_data.get('ai_consent', False):
        return jsonify({'error': 'AI Assistant access not granted'}), 403
    
    try:
        data = request.get_json()
        message = data.get('message', '')
        thread_id = data.get('thread_id')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get AI assistant
        ai = get_ai_assistant()
        
        # Create or get thread
        if not thread_id:
            thread_id = ai.create_thread(uid, 'planning')
        
        # Send message and get response
        response = ai.chat(thread_id, message, user_data)
        
        return jsonify({
            'response': response['response'],
            'thread_id': thread_id,
            'message_id': response['message_id']
        })
    
    except Exception as e:
        logger.error(f"AI planning chat error: {str(e)}")
        return jsonify({'error': 'AI service temporarily unavailable'}), 500


@ai_bp.route('/api/ai/chat/doubt', methods=['POST'])
@require_login
def ai_chat_doubt():
    """API endpoint for doubt resolution chatbot."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data or not user_data.get('ai_consent', False):
        return jsonify({'error': 'AI Assistant access not granted'}), 403
    
    try:
        data = request.get_json()
        message = data.get('message', '')
        thread_id = data.get('thread_id')
        subject = data.get('subject', '')
        chapter = data.get('chapter', '')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get AI assistant
        ai = get_ai_assistant()
        
        # Create or get thread
        if not thread_id:
            thread_id = ai.create_thread(uid, 'doubt')
        
        # Send message and get response
        response = ai.chat(thread_id, message, user_data, {
            'subject': subject,
            'chapter': chapter
        })
        
        return jsonify({
            'response': response['response'],
            'thread_id': thread_id,
            'message_id': response['message_id']
        })
    
    except Exception as e:
        logger.error(f"AI doubt chat error: {str(e)}")
        return jsonify({'error': 'AI service temporarily unavailable'}), 500


@ai_bp.route('/api/ai/chat/history/<chatbot_type>', methods=['GET'])
@require_login
def get_chat_history(chatbot_type):
    """Get conversation history for a specific chatbot type (active thread)."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data or not user_data.get('ai_consent', False):
        return jsonify({'error': 'AI Assistant access not granted'}), 403
    
    try:
        ai = get_ai_assistant()
        history = ai.get_thread_history(uid, chatbot_type)
        
        return jsonify({
            'history': history,
            'chatbot_type': chatbot_type
        })
    
    except Exception as e:
        logger.error(f"Error loading chat history: {str(e)}")
        return jsonify({'error': 'Failed to load conversation history'}), 500


@ai_bp.route('/api/ai/threads/<chatbot_type>', methods=['GET'])
@require_login
def get_threads(chatbot_type):
    """Get all conversation threads for a chatbot type."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data or not user_data.get('ai_consent', False):
        return jsonify({'error': 'AI Assistant access not granted'}), 403
    
    try:
        ai = get_ai_assistant()
        threads = ai.get_user_threads(uid, chatbot_type)
        
        return jsonify({
            'threads': threads,
            'chatbot_type': chatbot_type
        })
    
    except Exception as e:
        logger.error(f"Error loading threads: {str(e)}")
        return jsonify({'error': 'Failed to load threads'}), 500


@ai_bp.route('/api/ai/threads/<chatbot_type>/create', methods=['POST'])
@require_login
def create_thread(chatbot_type):
    """Create a new conversation thread."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data or not user_data.get('ai_consent', False):
        return jsonify({'error': 'AI Assistant access not granted'}), 403
    
    try:
        ai = get_ai_assistant()
        thread_id = ai.create_thread(uid, chatbot_type)
        
        return jsonify({
            'thread_id': thread_id,
            'chatbot_type': chatbot_type
        })
    
    except Exception as e:
        logger.error(f"Error creating thread: {str(e)}")
        return jsonify({'error': 'Failed to create thread'}), 500


@ai_bp.route('/api/ai/threads/<chatbot_type>/<thread_id>/switch', methods=['POST'])
@require_login
def switch_thread(chatbot_type, thread_id):
    """Switch active thread for a chatbot type."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data or not user_data.get('ai_consent', False):
        return jsonify({'error': 'AI Assistant access not granted'}), 403
    
    try:
        ai = get_ai_assistant()
        ai.set_active_thread(uid, chatbot_type, thread_id)
        
        return jsonify({
            'thread_id': thread_id,
            'chatbot_type': chatbot_type
        })
    
    except Exception as e:
        logger.error(f"Error switching thread: {str(e)}")
        return jsonify({'error': 'Failed to switch thread'}), 500


@ai_bp.route('/api/ai/threads/<chatbot_type>/<thread_id>/delete', methods=['DELETE'])
@require_login
def delete_thread(chatbot_type, thread_id):
    """Delete a conversation thread."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data or not user_data.get('ai_consent', False):
        return jsonify({'error': 'AI Assistant access not granted'}), 403
    
    try:
        ai = get_ai_assistant()
        ai.delete_thread(uid, chatbot_type, thread_id)
        
        return jsonify({
            'thread_id': thread_id,
            'chatbot_type': chatbot_type,
            'deleted': True
        })
    
    except Exception as e:
        logger.error(f"Error deleting thread: {str(e)}")
        return jsonify({'error': 'Failed to delete thread'}), 500


@ai_bp.route('/api/ai/threads/<chatbot_type>/<thread_id>/export/<format_type>', methods=['GET'])
@require_login
def export_thread(chatbot_type, thread_id, format_type):
    """Export a conversation thread."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data or not user_data.get('ai_consent', False):
        return jsonify({'error': 'AI Assistant access not granted'}), 403
    
    if format_type not in ['json', 'txt', 'csv']:
        return jsonify({'error': 'Invalid export format'}), 400
    
    try:
        ai = get_ai_assistant()
        export_data = ai.export_thread(uid, chatbot_type, thread_id, format_type)
        
        return jsonify({
            'export_data': export_data,
            'format': format_type,
            'thread_id': thread_id,
            'chatbot_type': chatbot_type
        })
    
    except Exception as e:
        logger.error(f"Error exporting thread: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500
