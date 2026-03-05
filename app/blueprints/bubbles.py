"""
Study Bubbles blueprint.
Handles group collaboration, bubble management, chat, and file sharing.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.models.auth import require_login
from app.models.firestore_helpers import get_document
from app.services.bubble_service import (
    create_bubble, join_bubble, leave_bubble, send_message, get_bubble_messages,
    upload_file_to_bubble, get_bubble_files, get_bubble_members, get_user_bubbles,
    generate_bubble_leaderboard, update_bubble_settings, delete_bubble
)
from utils import logger
from werkzeug.utils import secure_filename
import os

bubbles_bp = Blueprint('bubbles', __name__)


@bubbles_bp.route('/')
@require_login
def bubbles_home():
    """Main bubbles page showing user's bubbles and discovery."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get user's bubbles
    user_bubbles = get_user_bubbles(uid)
    
    return render_template('bubbles_home.html',
                         user_bubbles=user_bubbles,
                         user_data=user_data)


@bubbles_bp.route('/create', methods=['GET', 'POST'])
@require_login
def create_bubble_page():
    """Create a new study bubble."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        bubble_type = request.form.get('bubble_type', 'study')
        subject = request.form.get('subject')
        
        if not all([name, description]):
            flash('Name and description are required', 'error')
            return redirect(url_for('bubbles.create_bubble_page'))
        
        success, message, bubble_id = create_bubble(uid, name, description, bubble_type, subject)
        
        if success:
            flash(message, 'success')
            return redirect(url_for('bubbles.bubble_detail', bubble_id=bubble_id))
        else:
            flash(message, 'error')
            return redirect(url_for('bubbles.create_bubble_page'))
    
    return render_template('create_bubble.html', user_data=user_data)


@bubbles_bp.route('/<bubble_id>')
@require_login
def bubble_detail(bubble_id):
    """Detailed view of a bubble with chat and files."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get bubble data
    from app.models.firestore_helpers import get_document
    bubble_data = get_document('bubbles', bubble_id)
    
    if not bubble_data:
        flash('Bubble not found', 'error')
        return redirect(url_for('bubbles.bubbles_home'))
    
    # Check if user is a member
    if uid not in bubble_data.get('member_ids', []):
        flash('You are not a member of this bubble', 'error')
        return redirect(url_for('bubbles.bubbles_home'))
    
    # Get bubble messages, files, and members
    messages = get_bubble_messages(bubble_id, limit=50)
    files = get_bubble_files(bubble_id, limit=20)
    members = get_bubble_members(bubble_id)
    
    # Get leaderboard
    leaderboard = generate_bubble_leaderboard(bubble_id, period='week')
    
    return render_template('bubble_detail.html',
                         bubble_data=bubble_data,
                         messages=messages,
                         files=files,
                         members=members,
                         leaderboard=leaderboard,
                         user_data=user_data)


@bubbles_bp.route('/<bubble_id>/join', methods=['POST'])
@require_login
def join_bubble_endpoint(bubble_id):
    """Join a bubble."""
    uid = session['uid']
    
    success, message = join_bubble(uid, bubble_id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('bubbles.bubble_detail', bubble_id=bubble_id))


@bubbles_bp.route('/<bubble_id>/leave', methods=['POST'])
@require_login
def leave_bubble_endpoint(bubble_id):
    """Leave a bubble."""
    uid = session['uid']
    
    success, message = leave_bubble(uid, bubble_id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('bubbles.bubbles_home'))


@bubbles_bp.route('/<bubble_id>/chat/send', methods=['POST'])
@require_login
def send_chat_message(bubble_id):
    """Send a chat message in a bubble."""
    uid = session['uid']
    
    message = request.form.get('message', '').strip()
    message_type = request.form.get('message_type', 'text')
    
    if not message:
        return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400
    
    success, message_text, message_id = send_message(uid, bubble_id, message, message_type)
    
    if success:
        return jsonify({
            'success': True,
            'message': message_text,
            'message_id': message_id
        })
    else:
        return jsonify({'success': False, 'message': message_text}), 400


@bubbles_bp.route('/<bubble_id>/chat/messages')
@require_login
def get_chat_messages(bubble_id):
    """Get chat messages for a bubble."""
    uid = session['uid']
    
    # Check if user is a member
    bubble_data = get_document('bubbles', bubble_id)
    if not bubble_data or uid not in bubble_data.get('member_ids', []):
        return jsonify({'error': 'Not a member of this bubble'}), 403
    
    limit = request.args.get('limit', type=int, default=50)
    before = request.args.get('before')
    
    messages = get_bubble_messages(bubble_id, limit=limit, before=before)
    
    return jsonify({'messages': messages})


@bubbles_bp.route('/<bubble_id>/files/upload', methods=['POST'])
@require_login
def upload_file(bubble_id):
    """Upload a file to a bubble."""
    uid = session['uid']
    
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('bubbles.bubble_detail', bubble_id=bubble_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('bubbles.bubble_detail', bubble_id=bubble_id))
    
    if file:
        filename = secure_filename(file.filename)
        
        # For now, we'll simulate file upload
        # In production, you'd upload to Firebase Storage or similar
        file_size = len(file.read())
        file.seek(0)  # Reset file pointer
        file_type = file.content_type
        
        # Simulate file URL
        file_url = f"/files/{bubble_id}/{filename}"
        
        success, message, file_id = upload_file_to_bubble(
            uid, bubble_id, filename, file_size, file_type, file_url
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
    
    return redirect(url_for('bubbles.bubble_detail', bubble_id=bubble_id))


@bubbles_bp.route('/<bubble_id>/files')
@require_login
def bubble_files(bubble_id):
    """View files in a bubble."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user is a member
    bubble_data = get_document('bubbles', bubble_id)
    if not bubble_data or uid not in bubble_data.get('member_ids', []):
        flash('You are not a member of this bubble', 'error')
        return redirect(url_for('bubbles.bubbles_home'))
    
    # Get files
    files = get_bubble_files(bubble_id, limit=100)
    
    return render_template('bubble_files.html',
                         bubble_data=bubble_data,
                         files=files,
                         user_data=user_data)


@bubbles_bp.route('/<bubble_id>/members')
@require_login
def bubble_members(bubble_id):
    """View members of a bubble."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user is a member
    bubble_data = get_document('bubbles', bubble_id)
    if not bubble_data or uid not in bubble_data.get('member_ids', []):
        flash('You are not a member of this bubble', 'error')
        return redirect(url_for('bubbles.bubbles_home'))
    
    # Get members
    members = get_bubble_members(bubble_id)
    
    return render_template('bubble_members.html',
                         bubble_data=bubble_data,
                         members=members,
                         user_data=user_data)


@bubbles_bp.route('/<bubble_id>/leaderboard')
@require_login
def bubble_leaderboard(bubble_id):
    """View study leaderboard for a bubble."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user is a member
    bubble_data = get_document('bubbles', bubble_id)
    if not bubble_data or uid not in bubble_data.get('member_ids', []):
        flash('You are not a member of this bubble', 'error')
        return redirect(url_for('bubbles.bubbles_home'))
    
    # Get leaderboard for different periods
    period = request.args.get('period', 'week')
    leaderboard = generate_bubble_leaderboard(bubble_id, period)
    
    return render_template('bubble_leaderboard.html',
                         bubble_data=bubble_data,
                         leaderboard=leaderboard,
                         period=period,
                         user_data=user_data)


@bubbles_bp.route('/<bubble_id>/settings', methods=['GET', 'POST'])
@require_login
def bubble_settings(bubble_id):
    """Manage bubble settings."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user is creator
    bubble_data = get_document('bubbles', bubble_id)
    if not bubble_data or uid != bubble_data.get('creator_id'):
        flash('Only bubble creator can manage settings', 'error')
        return redirect(url_for('bubbles.bubble_detail', bubble_id=bubble_id))
    
    if request.method == 'POST':
        settings = {
            'allow_invites': request.form.get('allow_invites') == 'on',
            'require_approval': request.form.get('require_approval') == 'on',
            'max_members': int(request.form.get('max_members', 20))
        }
        
        success, message = update_bubble_settings(uid, bubble_id, settings)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('bubbles.bubble_settings', bubble_id=bubble_id))
    
    return render_template('bubble_settings.html',
                         bubble_data=bubble_data,
                         user_data=user_data)


@bubbles_bp.route('/<bubble_id>/delete', methods=['POST'])
@require_login
def delete_bubble_endpoint(bubble_id):
    """Delete a bubble (creator only)."""
    uid = session['uid']
    
    success, message = delete_bubble(uid, bubble_id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('bubbles.bubbles_home'))


@bubbles_bp.route('/api/user_bubbles')
@require_login
def api_user_bubbles():
    """API endpoint to get user's bubbles."""
    uid = session['uid']
    
    bubbles = get_user_bubbles(uid)
    return jsonify({'bubbles': bubbles})


@bubbles_bp.route('/api/<bubble_id>/messages')
@require_login
def api_bubble_messages(bubble_id):
    """API endpoint to get bubble messages."""
    uid = session['uid']
    
    # Check if user is a member
    bubble_data = get_document('bubbles', bubble_id)
    if not bubble_data or uid not in bubble_data.get('member_ids', []):
        return jsonify({'error': 'Not a member of this bubble'}), 403
    
    limit = request.args.get('limit', type=int, default=50)
    before = request.args.get('before')
    
    messages = get_bubble_messages(bubble_id, limit=limit, before=before)
    
    return jsonify({'messages': messages})


@bubbles_bp.route('/api/<bubble_id>/leaderboard')
@require_login
def api_bubble_leaderboard(bubble_id):
    """API endpoint to get bubble leaderboard."""
    uid = session['uid']
    
    # Check if user is a member
    bubble_data = get_document('bubbles', bubble_id)
    if not bubble_data or uid not in bubble_data.get('member_ids', []):
        return jsonify({'error': 'Not a member of this bubble'}), 403
    
    period = request.args.get('period', 'week')
    leaderboard = generate_bubble_leaderboard(bubble_id, period)
    
    return jsonify({'leaderboard': leaderboard, 'period': period})
