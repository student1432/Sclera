"""
Study Bubbles service layer.
Handles group collaboration, bubble management, real-time chat, and file sharing.
"""

from app.models.firestore_helpers import get_document, update_document, set_document, add_to_subcollection, query_collection, delete_document
from app.models.auth import get_any_profile
from firebase_config import db
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import uuid


def create_bubble(creator_id: str, name: str, description: str, bubble_type: str = 'study', subject: str = None) -> Tuple[bool, str, Optional[str]]:
    """
    Create a new study bubble.
    
    Args:
        creator_id: User ID of the bubble creator
        name: Bubble name
        description: Bubble description
        bubble_type: Type of bubble (study, project, general)
        subject: Related subject (optional)
        
    Returns:
        Tuple of (success: bool, message: str, bubble_id: Optional[str])
    """
    try:
        creator_profile = get_any_profile(creator_id)
        if not creator_profile:
            return False, 'Creator profile not found', None
        
        bubble_id = f"bubble_{uuid.uuid4().hex[:8]}"
        
        bubble_data = {
            'id': bubble_id,
            'name': name,
            'description': description,
            'bubble_type': bubble_type,
            'subject': subject,
            'creator_id': creator_id,
            'creator_name': creator_profile.get('name', ''),
            'member_ids': [creator_id],
            'member_count': 1,
            'status': 'active',
            'created_at': get_current_timestamp(),
            'last_activity': get_current_timestamp(),
            'settings': {
                'allow_invites': True,
                'require_approval': False,
                'max_members': 20
            },
            'stats': {
                'total_messages': 0,
                'total_files': 0,
                'total_study_time': 0
            }
        }
        
        # Create bubble document
        set_document('bubbles', bubble_id, bubble_data)
        
        # Add creator to bubble members subcollection
        member_data = {
            'user_id': creator_id,
            'name': creator_profile.get('name', ''),
            'role': 'admin',
            'joined_at': get_current_timestamp(),
            'status': 'active'
        }
        add_to_subcollection('bubbles', bubble_id, 'members', member_data)
        
        # Update user's bubbles list
        user_data = get_document('users', creator_id)
        if user_data:
            bubbles = user_data.get('bubbles', [])
            bubbles.append({
                'bubble_id': bubble_id,
                'name': name,
                'joined_at': get_current_timestamp(),
                'role': 'admin'
            })
            update_document('users', creator_id, {'bubbles': bubbles})
        
        return True, 'Bubble created successfully', bubble_id
        
    except Exception as e:
        return False, f'Error creating bubble: {str(e)}', None


def join_bubble(user_id: str, bubble_id: str, invite_code: str = None) -> Tuple[bool, str]:
    """
    Join a study bubble.
    
    Args:
        user_id: User ID
        bubble_id: Bubble ID
        invite_code: Optional invite code for private bubbles
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        user_profile = get_any_profile(user_id)
        if not user_profile:
            return False, 'User profile not found'
        
        bubble_data = get_document('bubbles', bubble_id)
        if not bubble_data:
            return False, 'Bubble not found'
        
        # Check if user is already a member
        if user_id in bubble_data.get('member_ids', []):
            return False, 'Already a member of this bubble'
        
        # Check bubble capacity
        settings = bubble_data.get('settings', {})
        max_members = settings.get('max_members', 20)
        if len(bubble_data.get('member_ids', [])) >= max_members:
            return False, 'Bubble is full'
        
        # Add user to bubble
        member_ids = bubble_data.get('member_ids', [])
        member_ids.append(user_id)
        
        update_document('bubbles', bubble_id, {
            'member_ids': member_ids,
            'member_count': len(member_ids),
            'last_activity': get_current_timestamp()
        })
        
        # Add user to members subcollection
        member_data = {
            'user_id': user_id,
            'name': user_profile.get('name', ''),
            'role': 'member',
            'joined_at': get_current_timestamp(),
            'status': 'active'
        }
        add_to_subcollection('bubbles', bubble_id, 'members', member_data)
        
        # Update user's bubbles list
        user_data = get_document('users', user_id)
        if user_data:
            bubbles = user_data.get('bubbles', [])
            bubbles.append({
                'bubble_id': bubble_id,
                'name': bubble_data.get('name', ''),
                'joined_at': get_current_timestamp(),
                'role': 'member'
            })
            update_document('users', user_id, {'bubbles': bubbles})
        
        return True, 'Joined bubble successfully'
        
    except Exception as e:
        return False, f'Error joining bubble: {str(e)}'


def leave_bubble(user_id: str, bubble_id: str) -> Tuple[bool, str]:
    """
    Leave a study bubble.
    
    Args:
        user_id: User ID
        bubble_id: Bubble ID
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        bubble_data = get_document('bubbles', bubble_id)
        if not bubble_data:
            return False, 'Bubble not found'
        
        # Check if user is a member
        if user_id not in bubble_data.get('member_ids', []):
            return False, 'Not a member of this bubble'
        
        # Remove user from bubble
        member_ids = bubble_data.get('member_ids', [])
        member_ids.remove(user_id)
        
        update_document('bubbles', bubble_id, {
            'member_ids': member_ids,
            'member_count': len(member_ids),
            'last_activity': get_current_timestamp()
        })
        
        # Remove from members subcollection
        members = query_collection(f'bubbles/{bubble_id}/members', filters=[('user_id', '==', user_id)])
        for member in members:
            delete_document(f'bubbles/{bubble_id}/members', member.get('id'))
        
        # Update user's bubbles list
        user_data = get_document('users', user_id)
        if user_data:
            bubbles = user_data.get('bubbles', [])
            bubbles = [b for b in bubbles if b.get('bubble_id') != bubble_id]
            update_document('users', user_id, {'bubbles': bubbles})
        
        return True, 'Left bubble successfully'
        
    except Exception as e:
        return False, f'Error leaving bubble: {str(e)}'


def send_message(user_id: str, bubble_id: str, message: str, message_type: str = 'text') -> Tuple[bool, str, Optional[str]]:
    """
    Send a message to a bubble chat.
    
    Args:
        user_id: User ID
        bubble_id: Bubble ID
        message: Message content
        message_type: Type of message (text, file, system)
        
    Returns:
        Tuple of (success: bool, message: str, message_id: Optional[str])
    """
    try:
        user_profile = get_any_profile(user_id)
        if not user_profile:
            return False, 'User profile not found', None
        
        bubble_data = get_document('bubbles', bubble_id)
        if not bubble_data:
            return False, 'Bubble not found', None
        
        # Check if user is a member
        if user_id not in bubble_data.get('member_ids', []):
            return False, 'Not a member of this bubble', None
        
        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        
        message_data = {
            'id': message_id,
            'user_id': user_id,
            'user_name': user_profile.get('name', ''),
            'message': message,
            'message_type': message_type,
            'timestamp': get_current_timestamp(),
            'edited': False,
            'edited_at': None,
            'reply_to': None,
            'reactions': {}
        }
        
        # Add message to messages subcollection
        add_to_subcollection('bubbles', bubble_id, 'messages', message_data)
        
        # Update bubble stats and activity
        update_document('bubbles', bubble_id, {
            'last_activity': get_current_timestamp(),
            'stats.total_messages': db.field_increment(1)
        })
        
        return True, 'Message sent successfully', message_id
        
    except Exception as e:
        return False, f'Error sending message: {str(e)}', None


def get_bubble_messages(bubble_id: str, limit: int = 50, before: str = None) -> List[Dict]:
    """
    Get messages from a bubble chat.
    
    Args:
        bubble_id: Bubble ID
        limit: Maximum number of messages to return
        before: Get messages before this timestamp (optional)
        
    Returns:
        List of message dictionaries
    """
    filters = []
    if before:
        filters.append(('timestamp', '<', before))
    
    messages = query_collection(
        collection=f'bubbles/{bubble_id}/messages',
        filters=filters,
        order_by='timestamp',
        direction='DESC',
        limit=limit
    )
    
    return messages


def upload_file_to_bubble(user_id: str, bubble_id: str, filename: str, file_size: int, file_type: str, file_url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Upload a file to a bubble.
    
    Args:
        user_id: User ID
        bubble_id: Bubble ID
        filename: Original filename
        file_size: File size in bytes
        file_type: MIME type
        file_url: Storage URL
        
    Returns:
        Tuple of (success: bool, message: str, file_id: Optional[str])
    """
    try:
        user_profile = get_any_profile(user_id)
        if not user_profile:
            return False, 'User profile not found', None
        
        bubble_data = get_document('bubbles', bubble_id)
        if not bubble_data:
            return False, 'Bubble not found', None
        
        # Check if user is a member
        if user_id not in bubble_data.get('member_ids', []):
            return False, 'Not a member of this bubble', None
        
        file_id = f"file_{uuid.uuid4().hex[:8]}"
        
        file_data = {
            'id': file_id,
            'user_id': user_id,
            'user_name': user_profile.get('name', ''),
            'filename': filename,
            'file_size': file_size,
            'file_type': file_type,
            'file_url': file_url,
            'uploaded_at': get_current_timestamp(),
            'downloads': 0
        }
        
        # Add file to files subcollection
        add_to_subcollection('bubbles', bubble_id, 'files', file_data)
        
        # Update bubble stats
        update_document('bubbles', bubble_id, {
            'last_activity': get_current_timestamp(),
            'stats.total_files': db.field_increment(1)
        })
        
        return True, 'File uploaded successfully', file_id
        
    except Exception as e:
        return False, f'Error uploading file: {str(e)}', None


def get_bubble_files(bubble_id: str, limit: int = 20) -> List[Dict]:
    """
    Get files uploaded to a bubble.
    
    Args:
        bubble_id: Bubble ID
        limit: Maximum number of files to return
        
    Returns:
        List of file dictionaries
    """
    files = query_collection(
        collection=f'bubbles/{bubble_id}/files',
        order_by='uploaded_at',
        direction='DESC',
        limit=limit
    )
    
    return files


def get_bubble_members(bubble_id: str) -> List[Dict]:
    """
    Get members of a bubble.
    
    Args:
        bubble_id: Bubble ID
        
    Returns:
        List of member dictionaries
    """
    members = query_collection(f'bubbles/{bubble_id}/members', order_by='joined_at')
    return members


def get_user_bubbles(user_id: str) -> List[Dict]:
    """
    Get all bubbles for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        List of bubble dictionaries
    """
    user_data = get_document('users', user_id)
    if not user_data:
        return []
    
    bubble_ids = [b.get('bubble_id') for b in user_data.get('bubbles', [])]
    bubbles = []
    
    for bubble_id in bubble_ids:
        bubble_data = get_document('bubbles', bubble_id)
        if bubble_data:
            bubbles.append(bubble_data)
    
    return bubbles


def generate_bubble_leaderboard(bubble_id: str, period: str = 'week') -> List[Dict]:
    """
    Generate a leaderboard for a bubble based on study time.
    
    Args:
        bubble_id: Bubble ID
        period: Time period ('day', 'week', 'month')
        
    Returns:
        List of leaderboard entries
    """
    try:
        bubble_data = get_document('bubbles', bubble_id)
        if not bubble_data:
            return []
        
        member_ids = bubble_data.get('member_ids', [])
        leaderboard = []
        
        # Calculate time period
        now = datetime.utcnow()
        if period == 'day':
            start_time = (now - timedelta(days=1)).isoformat()
        elif period == 'week':
            start_time = (now - timedelta(days=7)).isoformat()
        elif period == 'month':
            start_time = (now - timedelta(days=30)).isoformat()
        else:
            start_time = (now - timedelta(days=7)).isoformat()
        
        # Get study time for each member
        for member_id in member_ids:
            user_data = get_document('users', member_id)
            if not user_data:
                continue
            
            # Get study sessions in the period
            study_sessions = query_collection(
                collection=f'users/{member_id}/study_sessions',
                filters=[('start_time', '>=', start_time)],
                order_by='start_time',
                direction='DESC'
            )
            
            total_time = sum(s.get('duration_minutes', 0) for s in study_sessions)
            
            leaderboard.append({
                'user_id': member_id,
                'name': user_data.get('name', ''),
                'study_time_minutes': total_time,
                'sessions_count': len(study_sessions)
            })
        
        # Sort by study time (highest first)
        leaderboard.sort(key=lambda x: x['study_time_minutes'], reverse=True)
        
        # Add ranks
        for i, entry in enumerate(leaderboard):
            entry['rank'] = i + 1
        
        return leaderboard
        
    except Exception as e:
        return []


def update_bubble_settings(user_id: str, bubble_id: str, settings: Dict) -> Tuple[bool, str]:
    """
    Update bubble settings.
    
    Args:
        user_id: User ID (must be admin)
        bubble_id: Bubble ID
        settings: Settings dictionary
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        bubble_data = get_document('bubbles', bubble_id)
        if not bubble_data:
            return False, 'Bubble not found'
        
        # Check if user is admin or creator
        if user_id != bubble_data.get('creator_id'):
            return False, 'Only bubble creator can update settings'
        
        # Update settings
        current_settings = bubble_data.get('settings', {})
        current_settings.update(settings)
        
        update_document('bubbles', bubble_id, {'settings': current_settings})
        
        return True, 'Settings updated successfully'
        
    except Exception as e:
        return False, f'Error updating settings: {str(e)}'


def delete_bubble(user_id: str, bubble_id: str) -> Tuple[bool, str]:
    """
    Delete a bubble (only creator can delete).
    
    Args:
        user_id: User ID
        bubble_id: Bubble ID
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        bubble_data = get_document('bubbles', bubble_id)
        if not bubble_data:
            return False, 'Bubble not found'
        
        # Check if user is creator
        if user_id != bubble_data.get('creator_id'):
            return False, 'Only bubble creator can delete bubble'
        
        # Remove bubble from all members' bubble lists
        member_ids = bubble_data.get('member_ids', [])
        for member_id in member_ids:
            user_data = get_document('users', member_id)
            if user_data:
                bubbles = user_data.get('bubbles', [])
                bubbles = [b for b in bubbles if b.get('bubble_id') != bubble_id]
                update_document('users', member_id, {'bubbles': bubbles})
        
        # Delete bubble document
        delete_document('bubbles', bubble_id)
        
        return True, 'Bubble deleted successfully'
        
    except Exception as e:
        return False, f'Error deleting bubble: {str(e)}'


# Helper functions
def get_current_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat()
