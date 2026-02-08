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
