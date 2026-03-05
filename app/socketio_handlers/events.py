"""
SocketIO event handlers.
Handles real-time WebSocket events for chat, notifications, and live collaboration.
"""

from flask_socketio import emit, join_room, leave_room
from flask import session
from app.models.firestore_helpers import get_document
from app.models.profile import get_user_data
from app.services.bubble_service import send_message
from utils import logger
from firebase_config import db


def register_socketio_events(socketio):
    """Register all SocketIO event handlers."""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle WebSocket connection."""
        uid = session.get('uid')
        if uid:
            logger.info(f"User {uid} connected to WebSocket")
            emit('connection_status', {'status': 'connected'})
        else:
            logger.warning("Unauthenticated WebSocket connection attempt")
            return False
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle WebSocket disconnection."""
        uid = session.get('uid')
        if uid:
            logger.info(f"User {uid} disconnected from WebSocket")
    
    @socketio.on('join_bubble')
    def handle_join_bubble(data):
        """User joins a bubble chat room."""
        uid = session.get('uid')
        if not uid:
            return
        
        bubble_id = data.get('bubble_id')
        if not bubble_id:
            return
        
        # Verify membership
        try:
            bubble_doc = db.collection('bubbles').document(bubble_id).get()
            if bubble_doc.exists:
                bubble_data = bubble_doc.to_dict()
                if uid in bubble_data.get('member_ids', []):
                    join_room(f'bubble_{bubble_id}')
                    logger.info(f"User {uid} joined bubble room {bubble_id}")
                    
                    # Notify others
                    user_data = get_user_data(uid)
                    emit('user_joined', {
                        'uid': uid,
                        'name': user_data.get('name', 'Unknown'),
                        'bubble_id': bubble_id
                    }, room=f'bubble_{bubble_id}', include_self=False)
        except Exception as e:
            logger.error(f"Join bubble error: {str(e)}")
    
    @socketio.on('leave_bubble')
    def handle_leave_bubble(data):
        """User leaves a bubble chat room."""
        uid = session.get('uid')
        if not uid:
            return
        
        bubble_id = data.get('bubble_id')
        if not bubble_id:
            return
        
        leave_room(f'bubble_{bubble_id}')
        logger.info(f"User {uid} left bubble room {bubble_id}")
        
        # Notify others
        user_data = get_user_data(uid)
        emit('user_left', {
            'uid': uid,
            'name': user_data.get('name', 'Unknown'),
            'bubble_id': bubble_id
        }, room=f'bubble_{bubble_id}', include_self=False)
    
    @socketio.on('typing_start')
    def handle_typing_start(data):
        """User starts typing."""
        uid = session.get('uid')
        if not uid:
            return
        
        bubble_id = data.get('bubble_id')
        if not bubble_id:
            return
        
        user_data = get_user_data(uid)
        emit('user_typing', {
            'uid': uid,
            'name': user_data.get('name', 'Unknown'),
            'bubble_id': bubble_id,
            'action': 'start'
        }, room=f'bubble_{bubble_id}', include_self=False)
    
    @socketio.on('typing_stop')
    def handle_typing_stop(data):
        """User stops typing."""
        uid = session.get('uid')
        if not uid:
            return
        
        bubble_id = data.get('bubble_id')
        if not bubble_id:
            return
        
        user_data = get_user_data(uid)
        emit('user_typing', {
            'uid': uid,
            'name': user_data.get('name', 'Unknown'),
            'bubble_id': bubble_id,
            'action': 'stop'
        }, room=f'bubble_{bubble_id}', include_self=False)
    
    @socketio.on('send_message')
    def handle_send_message(data):
        """Handle real-time message sending."""
        uid = session.get('uid')
        if not uid:
            return
        
        bubble_id = data.get('bubble_id')
        message = data.get('message')
        message_type = data.get('message_type', 'text')
        
        if not all([bubble_id, message]):
            return
        
        # Verify membership and send message
        try:
            bubble_doc = db.collection('bubbles').document(bubble_id).get()
            if bubble_doc.exists:
                bubble_data = bubble_doc.to_dict()
                if uid in bubble_data.get('member_ids', []):
                    # Send message through service
                    success, message_text, message_id = send_message(uid, bubble_id, message, message_type)
                    
                    if success:
                        # Get message details for broadcasting
                        from app.services.bubble_service import get_bubble_messages
                        messages = get_bubble_messages(bubble_id, limit=1)
                        if messages:
                            message_data = messages[0]
                            
                            # Broadcast to all bubble members
                            emit('new_message', {
                                'message': message_data,
                                'bubble_id': bubble_id
                            }, room=f'bubble_{bubble_id}')
                            
                            logger.info(f"Message sent in bubble {bubble_id} by user {uid}")
                    else:
                        emit('message_error', {
                            'error': message_text,
                            'bubble_id': bubble_id
                        })
        except Exception as e:
            logger.error(f"Send message error: {str(e)}")
            emit('message_error', {
                'error': 'Failed to send message',
                'bubble_id': bubble_id
            })
    
    @socketio.on('study_session_update')
    def handle_study_session_update(data):
        """Handle real-time study session updates."""
        uid = session.get('uid')
        if not uid:
            return
        
        action = data.get('action')  # 'start', 'stop', 'update'
        session_data = data.get('session_data', {})
        
        # Broadcast to user's study partners (if in bubbles)
        user_data = get_user_data(uid)
        bubble_ids = [b.get('bubble_id') for b in user_data.get('bubbles', [])]
        
        for bubble_id in bubble_ids:
            emit('study_activity', {
                'uid': uid,
                'name': user_data.get('name', 'Unknown'),
                'action': action,
                'session_data': session_data,
                'bubble_id': bubble_id
            }, room=f'bubble_{bubble_id}', include_self=False)
    
    @socketio.on('goal_update')
    def handle_goal_update(data):
        """Handle real-time goal updates."""
        uid = session.get('uid')
        if not uid:
            return
        
        goal_id = data.get('goal_id')
        progress = data.get('progress')
        completed = data.get('completed', False)
        
        # Broadcast to user's study partners
        user_data = get_user_data(uid)
        bubble_ids = [b.get('bubble_id') for b in user_data.get('bubbles', [])]
        
        for bubble_id in bubble_ids:
            emit('goal_activity', {
                'uid': uid,
                'name': user_data.get('name', 'Unknown'),
                'goal_id': goal_id,
                'progress': progress,
                'completed': completed,
                'bubble_id': bubble_id
            }, room=f'bubble_{bubble_id}', include_self=False)
    
    @socketio.on('task_update')
    def handle_task_update(data):
        """Handle real-time task updates."""
        uid = session.get('uid')
        if not uid:
            return
        
        task_id = data.get('task_id')
        completed = data.get('completed', False)
        
        # Broadcast to user's study partners
        user_data = get_user_data(uid)
        bubble_ids = [b.get('bubble_id') for b in user_data.get('bubbles', [])]
        
        for bubble_id in bubble_ids:
            emit('task_activity', {
                'uid': uid,
                'name': user_data.get('name', 'Unknown'),
                'task_id': task_id,
                'completed': completed,
                'bubble_id': bubble_id
            }, room=f'bubble_{bubble_id}', include_self=False)
    
    @socketio.on('bubble_file_upload')
    def handle_bubble_file_upload(data):
        """Handle real-time file upload notifications."""
        uid = session.get('uid')
        if not uid:
            return
        
        bubble_id = data.get('bubble_id')
        file_info = data.get('file_info', {})
        
        # Broadcast to bubble members
        emit('file_uploaded', {
            'uid': uid,
            'name': get_user_data(uid).get('name', 'Unknown'),
            'bubble_id': bubble_id,
            'file_info': file_info
        }, room=f'bubble_{bubble_id}', include_self=False)
    
    @socketio.on('bubble_leaderboard_update')
    def handle_bubble_leaderboard_update(data):
        """Handle real-time leaderboard updates."""
        bubble_id = data.get('bubble_id')
        period = data.get('period', 'week')
        
        # Generate new leaderboard
        from app.services.bubble_service import generate_bubble_leaderboard
        leaderboard = generate_bubble_leaderboard(bubble_id, period)
        
        # Broadcast to bubble members
        emit('leaderboard_updated', {
            'bubble_id': bubble_id,
            'period': period,
            'leaderboard': leaderboard
        }, room=f'bubble_{bubble_id}')
    
    @socketio.on('institution_notification')
    def handle_institution_notification(data):
        """Handle institution-wide notifications (admin/teacher only)."""
        uid = session.get('uid')
        if not uid:
            return
        
        # Check if user is admin or teacher
        user_profile = get_document('users', uid)
        if not user_profile:
            return
        
        account_type = session.get('account_type')
        if account_type not in ['admin', 'teacher']:
            return
        
        institution_id = data.get('institution_id')
        notification = data.get('notification', {})
        
        # Broadcast to all institution members
        if account_type == 'admin':
            # Admin can send to all members
            institution_data = get_document('institutions', institution_id)
            if institution_data:
                student_ids = institution_data.get('student_ids', [])
                teacher_ids = institution_data.get('teacher_ids', [])
                
                for member_id in student_ids + teacher_ids:
                    emit('institution_notification', {
                        'institution_id': institution_id,
                        'notification': notification,
                        'sender': user_profile.get('name', 'Admin')
                    }, room=f'user_{member_id}')
        
        elif account_type == 'teacher':
            # Teacher can send to their classes
            classes = query_collection('classes', filters=[('teacher_id', '==', uid)])
            for class_data in classes:
                student_ids = class_data.get('student_ids', [])
                for student_id in student_ids:
                    emit('institution_notification', {
                        'institution_id': institution_id,
                        'notification': notification,
                        'sender': user_profile.get('name', 'Teacher'),
                        'class_id': class_data.get('id')
                    }, room=f'user_{student_id}')
    
    return socketio
