"""
Security utilities for StudyOS
Includes password hashing, encryption, and security helpers
"""
import bcrypt
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict


class PasswordManager:
    """Secure password hashing using bcrypt with SHA-256 fallback for legacy accounts"""
    
    @staticmethod
    def _is_legacy_hash(stored_hash: str) -> bool:
        """Check if the stored hash is a legacy SHA-256 hash (64 hex characters)"""
        return len(stored_hash) == 64 and all(c in '0123456789abcdef' for c in stored_hash.lower())
    
    @staticmethod
    def _verify_legacy_hash(password: str, stored_hash: str) -> bool:
        """Verify a password against a legacy SHA-256 hash"""
        import hashlib
        computed_hash = hashlib.sha256(password.encode()).hexdigest()
        return computed_hash == stored_hash
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt with salt
        Args:
            password: Plain text password
        Returns:
            Hashed password string
        """
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """
        Verify a password against its hash
        Supports both bcrypt (new) and SHA-256 (legacy) hashes
        Args:
            password: Plain text password
            stored_hash: Stored hashed password
        Returns:
            True if password matches, False otherwise
        """
        # Check if it's a legacy SHA-256 hash
        if PasswordManager._is_legacy_hash(stored_hash):
            return PasswordManager._verify_legacy_hash(password, stored_hash)
        
        # Otherwise, use bcrypt verification
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    
    @staticmethod
    def is_strong_password(password: str) -> tuple[bool, str]:
        """
        Check if password meets security requirements
        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'\d', password):
            return False, "Password must contain at least one digit"
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
        
        return True, "Password is strong"


class RateLimiter:
    """Simple in-memory rate limiter for login attempts"""
    
    def __init__(self):
        self.attempts: Dict[str, list] = {}
    
    def is_allowed(self, identifier: str, max_attempts: int = 5, 
                   window_minutes: int = 15) -> bool:
        """
        Check if an action is allowed based on rate limiting
        Args:
            identifier: IP address or user identifier
            max_attempts: Maximum attempts allowed
            window_minutes: Time window in minutes
        Returns:
            True if allowed, False if rate limited
        """
        now = datetime.now()
        window = timedelta(minutes=window_minutes)
        
        # Clean old attempts
        if identifier in self.attempts:
            self.attempts[identifier] = [
                attempt for attempt in self.attempts[identifier]
                if now - attempt < window
            ]
        else:
            self.attempts[identifier] = []
        
        # Check if limit exceeded
        if len(self.attempts[identifier]) >= max_attempts:
            return False
        
        return True
    
    def record_attempt(self, identifier: str):
        """Record a new attempt"""
        if identifier not in self.attempts:
            self.attempts[identifier] = []
        self.attempts[identifier].append(datetime.now())
    
    def reset_attempts(self, identifier: str):
        """Reset attempts for an identifier"""
        self.attempts[identifier] = []


class TokenManager:
    """Secure token generation and validation"""
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_csrf_token() -> str:
        """Generate a CSRF token"""
        return secrets.token_hex(16)


# Global rate limiter instance
login_rate_limiter = RateLimiter()


def sanitize_input(text: str) -> str:
    """
    Basic input sanitization to prevent XSS
    Args:
        text: Input text to sanitize
    Returns:
        Sanitized text
    """
    # Remove potentially dangerous HTML tags
    import html
    return html.escape(text)


def validate_email(email: str) -> bool:
    """
    Validate email format
    Args:
        email: Email address to validate
    Returns:
        True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ============================================================================
# CHAT SECURITY CLASSES
# ============================================================================

import bleach
import time
from collections import defaultdict
from typing import Dict, List, Any


class MessageSecurityValidator:
    """Validates and sanitizes chat messages"""
    
    def __init__(self):
        self.max_message_length = 4000
        self.max_mentions_per_message = 10
        self.max_hashtags_per_message = 5
        
        # Allowed HTML tags for rich text
        self.allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'code', 'pre']
        self.allowed_attributes = {'*': ['class']}
        
        # Patterns to detect and redact sensitive information
        self.prohibited_patterns = [
            (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[REDACTED-CARD]'),  # Credit cards
            (r'\b\d{3}-?\d{2}-?\d{4}\b', '[REDACTED-SSN]'),  # SSN patterns
        ]
        
    def validate_message_content(self, content: str, sender_uid: str) -> Dict[str, Any]:
        """
        Comprehensive message content validation
        
        Args:
            content: Message content to validate
            sender_uid: UID of message sender
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'sanitized_content': content
        }
        
        # Length validation
        if len(content) > self.max_message_length:
            validation_result['is_valid'] = False
            validation_result['errors'].append(
                f'Message exceeds maximum length of {self.max_message_length} characters'
            )
            return validation_result
        
        # Empty content check
        if not content.strip():
            validation_result['is_valid'] = False
            validation_result['errors'].append('Message cannot be empty')
            return validation_result
        
        # Pattern detection and redaction
        for pattern, replacement in self.prohibited_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                validation_result['warnings'].append(
                    'Message contains potentially sensitive information that has been redacted'
                )
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
        
        # Mention validation
        mentions = re.findall(r'@([\w\._-]+)', content)
        if len(mentions) > self.max_mentions_per_message:
            validation_result['warnings'].append(
                f'Too many mentions ({len(mentions)}). Maximum allowed: {self.max_mentions_per_message}'
            )
        
        # Hashtag validation
        hashtags = re.findall(r'#([\w]+)', content)
        if len(hashtags) > self.max_hashtags_per_message:
            validation_result['warnings'].append(
                f'Too many hashtags ({len(hashtags)}). Maximum allowed: {self.max_hashtags_per_message}'
            )
        
        # HTML sanitization
        sanitized_content = bleach.clean(
            content,
            tags=self.allowed_tags,
            attributes=self.allowed_attributes,
            strip=True
        )
        
        validation_result['sanitized_content'] = sanitized_content
        return validation_result
    
    def extract_mentions(self, content: str) -> List[str]:
        """Extract @mentions from message"""
        return re.findall(r'@([\w\._-]+)', content)
    
    def extract_hashtags(self, content: str) -> List[str]:
        """Extract #hashtags from message"""
        return re.findall(r'#([\w]+)', content)


class BubbleRateLimiter:
    """Rate limiting for bubble chat actions"""
    
    def __init__(self):
        self.user_limits = {
            'messages_per_minute': 10,
            'messages_per_hour': 100,
            'files_per_hour': 20,
            'reactions_per_minute': 30
        }
        self.bubble_limits = {
            'messages_per_minute': 50,
            'new_members_per_hour': 10
        }
        self.user_activity = defaultdict(lambda: defaultdict(list))
        self.bubble_activity = defaultdict(lambda: defaultdict(list))
        
    def check_user_rate_limit(self, uid: str, action: str, bubble_id: str = None) -> tuple:
        """
        Check if user exceeds rate limits
        
        Args:
            uid: User ID
            action: Action type ('send_message', 'upload_file', 'add_reaction')
            bubble_id: Optional bubble ID for bubble-specific limits
            
        Returns:
            Tuple of (is_allowed: bool, message: str)
        """
        current_time = time.time()
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        
        user_activity = self.user_activity[uid]
        
        if action == 'send_message':
            # Check per-minute limit
            recent_messages = [t for t in user_activity['messages'] if t > minute_ago]
            if len(recent_messages) >= self.user_limits['messages_per_minute']:
                return False, 'Rate limit exceeded: Too many messages per minute'
            
            # Check per-hour limit
            recent_hour_messages = [t for t in user_activity['messages'] if t > hour_ago]
            if len(recent_hour_messages) >= self.user_limits['messages_per_hour']:
                return False, 'Rate limit exceeded: Too many messages per hour'
            
            # Check bubble-specific limits
            if bubble_id:
                bubble_activity = self.bubble_activity[bubble_id]
                bubble_recent = [t for t in bubble_activity['messages'] if t > minute_ago]
                if len(bubble_recent) >= self.bubble_limits['messages_per_minute']:
                    return False, 'Bubble rate limit exceeded'
            
            # Log activity
            user_activity['messages'].append(current_time)
            if bubble_id:
                self.bubble_activity[bubble_id]['messages'].append(current_time)
        
        elif action == 'upload_file':
            recent_files = [t for t in user_activity['files'] if t > hour_ago]
            if len(recent_files) >= self.user_limits['files_per_hour']:
                return False, 'Rate limit exceeded: Too many file uploads per hour'
            user_activity['files'].append(current_time)
        
        elif action == 'add_reaction':
            recent_reactions = [t for t in user_activity['reactions'] if t > minute_ago]
            if len(recent_reactions) >= self.user_limits['reactions_per_minute']:
                return False, 'Rate limit exceeded: Too many reactions per minute'
            user_activity['reactions'].append(current_time)
        
        return True, 'Allowed'
    
    def cleanup_old_activities(self):
        """Clean up old activity records to prevent memory bloat"""
        current_time = time.time()
        hour_ago = current_time - 3600
        
        for uid in list(self.user_activity.keys()):
            for action in list(self.user_activity[uid].keys()):
                self.user_activity[uid][action] = [
                    t for t in self.user_activity[uid][action] if t > hour_ago
                ]
            # Remove empty user entries
            if not self.user_activity[uid]:
                del self.user_activity[uid]
        
        for bubble_id in list(self.bubble_activity.keys()):
            for action in list(self.bubble_activity[bubble_id].keys()):
                self.bubble_activity[bubble_id][action] = [
                    t for t in self.bubble_activity[bubble_id][action] if t > hour_ago
                ]
            # Remove empty bubble entries
            if not self.bubble_activity[bubble_id]:
                del self.bubble_activity[bubble_id]


class FileUploadSecurity:
    """Security validation for file uploads"""
    
    ALLOWED_MIME_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'application/pdf', 'text/plain',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    def validate_file_upload(self, file, bubble_id: str, uploader_uid: str) -> Dict[str, Any]:
        """
        Comprehensive file upload validation
        
        Args:
            file: File object from request
            bubble_id: Bubble ID where file is being uploaded
            uploader_uid: UID of uploader
            
        Returns:
            Dictionary with validation results
        """
        from werkzeug.utils import secure_filename
        import hashlib
        
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'file_info': {}
        }
        
        # Check if file exists
        if not file:
            validation_result['is_valid'] = False
            validation_result['errors'].append('No file provided')
            return validation_result
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset position
        
        if file_size > self.MAX_FILE_SIZE:
            validation_result['is_valid'] = False
            validation_result['errors'].append(
                f'File size exceeds maximum allowed size of {self.MAX_FILE_SIZE // (1024*1024)}MB'
            )
            return validation_result
        
        # Read file content for analysis
        file_content = file.read()
        file.seek(0)
        
        # Get MIME type (basic check using file extension)
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Basic MIME type validation based on extension
        mime_map = {
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
            'gif': 'image/gif', 'webp': 'image/webp', 'pdf': 'application/pdf',
            'txt': 'text/plain', 'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        mime_type = mime_map.get(file_ext, 'application/octet-stream')
        
        if mime_type not in self.ALLOWED_MIME_TYPES:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f'File type {mime_type} is not allowed')
            return validation_result
        
        # Generate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        validation_result['file_info'] = {
            'mime_type': mime_type,
            'file_size': file_size,
            'file_hash': file_hash,
            'original_filename': filename
        }
        
        return validation_result


# Global chat security instances
message_validator = MessageSecurityValidator()
bubble_rate_limiter = BubbleRateLimiter()
file_upload_security = FileUploadSecurity()
