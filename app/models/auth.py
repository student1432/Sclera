"""
Authentication models and decorators.
Handles user authentication, role-based access control, and session management.
"""

from functools import wraps
from flask import session, redirect, url_for, abort
from firebase_config import db
import random
import string

# Firestore collection constants
INSTITUTION_ADMINS_COL = 'institution_admins'
INSTITUTION_TEACHERS_COL = 'institution_teachers'
INSTITUTIONS_COL = 'institutions'
TEACHER_INVITES_COL = 'teacher_invites'
CLASSES_COL = 'classes'
CLASS_INVITES_COL = 'class_invites'


def generate_code(length: int = 6) -> str:
    """
    Generate a random alphanumeric code.
    
    Args:
        length: Length of the code to generate
        
    Returns:
        Random alphanumeric string
    """
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def set_session_identity(uid: str, account_type: str, institution_id: str = None):
    """
    Set user identity in session.
    
    Args:
        uid: User ID
        account_type: Account type ('student', 'teacher', 'admin')
        institution_id: Institution ID (optional)
    """
    session['uid'] = uid
    session['account_type'] = account_type
    if institution_id:
        session['institution_id'] = institution_id
    else:
        session.pop('institution_id', None)


def get_account_type() -> str:
    """
    Get current user's account type from session.
    
    Returns:
        Account type string, defaults to 'student'
    """
    return session.get('account_type', 'student')


def require_institution_role(allowed_roles: list[str]):
    """
    Decorator to require specific institution roles.
    
    Args:
        allowed_roles: List of allowed account types
        
    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'uid' not in session:
                return redirect(url_for('auth.login'))
            
            account_type = get_account_type()
            if account_type not in allowed_roles:
                abort(403)
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


# Predefined role decorators
require_admin_v2 = require_institution_role(['admin'])
require_teacher_v2 = require_institution_role(['teacher'])


def get_admin_profile(uid: str) -> dict:
    """
    Get admin profile for user ID.
    
    Args:
        uid: User ID
        
    Returns:
        Admin profile dict or None if not found
    """
    profile = get_any_profile(uid)
    return profile if profile and profile.get('account_type') == 'admin' else None


def get_teacher_profile(uid: str) -> dict:
    """
    Get teacher profile for user ID.
    
    Args:
        uid: User ID
        
    Returns:
        Teacher profile dict or None if not found
    """
    profile = get_any_profile(uid)
    return profile if profile and profile.get('account_type') == 'teacher' else None


def get_any_profile(uid: str) -> dict:
    """
    Get user profile from any identity collection.
    Checks collections in order of specificity: admin -> teacher -> student.
    
    Args:
        uid: User ID
        
    Returns:
        Profile dict with account_type field or None if not found
    """
    # Check admin collection
    doc = db.collection(INSTITUTION_ADMINS_COL).document(uid).get()
    if doc.exists:
        return {**doc.to_dict(), 'account_type': 'admin'}
    
    # Check teacher collection
    doc = db.collection(INSTITUTION_TEACHERS_COL).document(uid).get()
    if doc.exists:
        return {**doc.to_dict(), 'account_type': 'teacher'}
    
    # Check student collection
    doc = db.collection('users').document(uid).get()
    if doc.exists:
        return {**doc.to_dict(), 'account_type': 'student'}
    
    return None


def institution_login_guard():
    """
    Prevent admin/teacher accounts from entering student app routes.
    
    Returns:
        Redirect response if guard triggers, None otherwise
    """
    if 'uid' not in session:
        return None
    
    account_type = get_account_type()
    
    # Block admin/teacher from student routes
    if account_type == 'admin':
        return redirect(url_for('institution.institution_admin_dashboard'))
    if account_type == 'teacher':
        return redirect(url_for('institution.institution_teacher_dashboard'))
    
    return None


def require_login(f):
    """
    Decorator to require user login.
    
    Args:
        f: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'uid' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    
    wrapper.__name__ = f.__name__
    return wrapper
