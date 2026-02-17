# Bubble Chat System - Quick Start Guide

## 🚀 Implementation Status

### ✅ Completed
- [x] Added Flask-SocketIO and dependencies to requirements.txt
- [x] Created security utilities (MessageSecurityValidator, BubbleRateLimiter, FileUploadSecurity)
- [x] Implementation plan document created

### ⏳ Next Steps

## Step 1: Install Dependencies

```powershell
cd c:\Users\HP\Downloads\TEST1
pip install -r requirements.txt
```

## Step 2: Add Chat API Endpoints to app.py

Add these imports at the top of app.py (after existing imports):

```python
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from utils.security import message_validator, bubble_rate_limiter, file_upload_security
import uuid
```

Initialize SocketIO after Flask app initialization (around line 37):

```python
# Initialize Flask-SocketIO for real-time chat
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='threading',
                   logger=True,
                   engineio_logger=False)
```

## Step 3: Add Chat Routes

Add these routes after the existing bubble routes (after line 2459):

```python
# ============================================================================
# BUBBLE CHAT SYSTEM
# ============================================================================

@app.route('/bubble/<bubble_id>/chat')
@require_login
def bubble_chat(bubble_id):
    """Bubble chat interface"""
    uid = session['uid']
    user_data = get_user_data(uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    
    # Get bubble data
    bubble_doc = db.collection('bubbles').document(bubble_id).get()
    if not bubble_doc.exists:
        flash('Bubble not found', 'error')
        return redirect(url_for('community_dashboard'))
    
    bubble_data = bubble_doc.to_dict()
    
    # Check if user is a member
    is_member = uid in bubble_data.get('member_uids', [])
    is_creator = bubble_data.get('creator_uid') == uid
    
    if not is_member and not is_creator:
        flash('You are not a member of this bubble', 'error')
        return redirect(url_for('community_dashboard'))
    
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'bubble': {
            'id': bubble_id,
            'name': bubble_data.get('name'),
            'description': bubble_data.get('description'),
            'member_count': len(bubble_data.get('member_uids', [])),
            'is_creator': is_creator
        }
    }
    
    return render_template('bubble_chat.html', **context)


@app.route('/api/bubbles/<bubble_id>/chat/messages', methods=['GET'])
@require_login
def get_chat_messages(bubble_id):
    """Get chat messages for a bubble"""
    uid = session['uid']
    
    try:
        # Verify bubble membership
        bubble_doc = db.collection('bubbles').document(bubble_id).get()
        if not bubble_doc.exists:
            return jsonify({'error': 'Bubble not found'}), 404
        
        bubble_data = bubble_doc.to_dict()
        if uid not in bubble_data.get('member_uids', []):
            return jsonify({'error': 'Not authorized'}), 403
        
        # Get pagination parameters
        limit = min(int(request.args.get('limit', 50)), 100)
        
        # Query messages
        messages_ref = db.collection('bubbles').document(bubble_id).collection('messages')
        messages_query = messages_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit)
        
        messages = []
        for doc in messages_query.stream():
            msg_data = doc.to_dict()
            msg_data['message_id'] = doc.id
            messages.append(msg_data)
        
        # Reverse to show oldest first
        messages.reverse()
        
        return jsonify({
            'success': True,
            'messages': messages,
            'count': len(messages)
        })
        
    except Exception as e:
        logger.error(f"Get messages error: {str(e)}")
        return jsonify({'error': 'Failed to fetch messages'}), 500


@app.route('/api/bubbles/<bubble_id>/chat/messages', methods=['POST'])
@require_login
def send_chat_message(bubble_id):
    """Send a chat message"""
    uid = session['uid']
    
    try:
        # Verify bubble membership
        bubble_doc = db.collection('bubbles').document(bubble_id).get()
        if not bubble_doc.exists:
            return jsonify({'error': 'Bubble not found'}), 404
        
        bubble_data = bubble_doc.to_dict()
        if uid not in bubble_data.get('member_uids', []):
            return jsonify({'error': 'Not authorized'}), 403
        
        # Get message content
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({'error': 'Message content required'}), 400
        
        # Rate limiting check
        is_allowed, rate_msg = bubble_rate_limiter.check_user_rate_limit(uid, 'send_message', bubble_id)
        if not is_allowed:
            return jsonify({'error': rate_msg}), 429
        
        # Validate and sanitize message
        validation = message_validator.validate_message_content(content, uid)
        if not validation['is_valid']:
            return jsonify({'error': validation['errors'][0]}), 400
        
        # Get user data for sender info
        user_data = get_user_data(uid)
        
        # Create message document
        message_id = str(uuid.uuid4())
        message_data = {
            'message_id': message_id,
            'content': validation['sanitized_content'],
            'sender_uid': uid,
            'sender_name': user_data.get('name', 'Unknown'),
            'timestamp': firestore.SERVER_TIMESTAMP,
            'message_type': 'text',
            'deleted': False,
            'reactions': {}
        }
        
        # Save message
        db.collection('bubbles').document(bubble_id).collection('messages').document(message_id).set(message_data)
        
        # Broadcast via SocketIO
        socketio.emit('new_message', {
            'bubble_id': bubble_id,
            'message': message_data
        }, room=f'bubble_{bubble_id}')
        
        return jsonify({
            'success': True,
            'message_id': message_id,
            'message': 'Message sent successfully'
        })
        
    except Exception as e:
        logger.error(f"Send message error: {str(e)}")
        return jsonify({'error': 'Failed to send message'}), 500


@app.route('/api/bubbles/<bubble_id>/chat/messages/<message_id>', methods=['DELETE'])
@require_login
def delete_chat_message(bubble_id, message_id):
    """Delete a chat message"""
    uid = session['uid']
    
    try:
        # Verify bubble membership
        bubble_doc = db.collection('bubbles').document(bubble_id).get()
        if not bubble_doc.exists:
            return jsonify({'error': 'Bubble not found'}), 404
        
        bubble_data = bubble_doc.to_dict()
        is_creator = bubble_data.get('creator_uid') == uid
        
        # Get message
        message_doc = db.collection('bubbles').document(bubble_id).collection('messages').document(message_id).get()
        if not message_doc.exists:
            return jsonify({'error': 'Message not found'}), 404
        
        message_data = message_doc.to_dict()
        
        # Check permissions (sender or bubble creator)
        if message_data.get('sender_uid') != uid and not is_creator:
            return jsonify({'error': 'Not authorized'}), 403
        
        # Soft delete
        db.collection('bubbles').document(bubble_id).collection('messages').document(message_id).update({
            'deleted': True,
            'deleted_by': uid,
            'deleted_at': firestore.SERVER_TIMESTAMP
        })
        
        # Broadcast deletion
        socketio.emit('message_deleted', {
            'bubble_id': bubble_id,
            'message_id': message_id
        }, room=f'bubble_{bubble_id}')
        
        return jsonify({
            'success': True,
            'message': 'Message deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Delete message error: {str(e)}")
        return jsonify({'error': 'Failed to delete message'}), 500


# ============================================================================
# SOCKETIO EVENT HANDLERS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    uid = session.get('uid')
    if uid:
        logger.info(f"User {uid} connected to WebSocket")
        emit('connection_status', {'status': 'connected'})
    else:
        logger.warning("Unauthenticated WebSocket connection attempt")
        return False


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    uid = session.get('uid')
    if uid:
        logger.info(f"User {uid} disconnected from WebSocket")


@socketio.on('join_bubble')
def handle_join_bubble(data):
    """User joins a bubble chat room"""
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
            if uid in bubble_data.get('member_uids', []):
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
    """User leaves a bubble chat room"""
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
    """User starts typing"""
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
    """User stops typing"""
    uid = session.get('uid')
    if not uid:
        return
    
    bubble_id = data.get('bubble_id')
    if not bubble_id:
        return
    
    emit('user_typing', {
        'uid': uid,
        'action': 'stop',
        'bubble_id': bubble_id
    }, room=f'bubble_{bubble_id}', include_self=False)
```

## Step 4: Update app.py run command

At the very end of app.py, replace:

```python
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

With:

```python
if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
```

## Step 5: Update Firestore Security Rules

Add to `firestore.rules`:

```
match /bubbles/{bubbleId}/messages/{messageId} {
  allow read: if request.auth != null && 
              request.auth.uid in get(/databases/$(database)/documents/bubbles/$(bubbleId)).data.member_uids;
  allow create: if request.auth != null && 
                request.auth.uid in get(/databases/$(database)/documents/bubbles/$(bubbleId)).data.member_uids;
  allow update, delete: if request.auth != null && 
                        (request.auth.uid == resource.data.sender_uid || 
                         request.auth.uid == get(/databases/$(database)/documents/bubbles/$(bubbleId)).data.creator_uid);
}
```

## Step 6: Create Basic Chat Template

Create `templates/bubble_chat.html` - see next artifact for full template.

## Step 7: Test the Implementation

1. Start the server:
```powershell
python app.py
```

2. Navigate to a bubble and add `/chat` to the URL:
```
http://localhost:5000/bubble/{bubble_id}/chat
```

3. Test sending messages
4. Open in multiple browser windows to test real-time updates

## 🎯 What You Get

This minimal implementation provides:

✅ Real-time chat messaging
✅ Message history loading
✅ Message deletion (sender or creator only)
✅ Rate limiting
✅ Content sanitization
✅ Typing indicators
✅ Online presence
✅ WebSocket connection management

## 📋 Next Features to Add

After this works, you can add:
- Todo lists
- File sharing
- Voice messages
- Message reactions
- Read receipts
- Message search
- Bubble management enhancements

## 🐛 Troubleshooting

**WebSocket not connecting:**
- Check that Flask-SocketIO is installed
- Verify socketio.run() is used instead of app.run()
- Check browser console for errors

**Messages not appearing:**
- Check Firestore security rules
- Verify user is a bubble member
- Check browser console and server logs

**Rate limiting issues:**
- Adjust limits in `utils/security.py` BubbleRateLimiter class

## 📚 Resources

- Flask-SocketIO docs: https://flask-socketio.readthedocs.io/
- Socket.IO client docs: https://socket.io/docs/v4/client-api/
- Firestore docs: https://firebase.google.com/docs/firestore

