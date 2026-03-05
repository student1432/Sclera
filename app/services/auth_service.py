"""
Authentication service layer.
Handles all authentication-related business logic.
"""

from firebase_config import auth as firebase_auth, db
from firebase_admin import auth as admin_auth
from utils import PasswordManager, logger, validate_schema, user_registration_schema, user_login_schema
from app.models.firestore_helpers import set_document, get_document
from app.models.profile import initialize_profile_fields
from datetime import datetime
from typing import Tuple, Dict, Optional


def register_user(name: str, email: str, password: str, purpose: str, age: str = None, ip_address: str = None) -> Tuple[bool, str, Optional[str]]:
    """
    Register a new user account.
    
    Args:
        name: User's full name
        email: User's email address
        password: User's password
        purpose: Account purpose (school, exam_prep, after_tenth)
        age: User's age (optional)
        ip_address: User's IP address for logging
        
    Returns:
        Tuple of (success: bool, message: str, user_id: Optional[str])
    """
    try:
        # Check if email already exists
        try:
            admin_auth.get_user_by_email(email)
            return False, 'Email already exists. Please login.', None
        except admin_auth.UserNotFoundError:
            pass
        
        # Create Firebase Auth user
        user = admin_auth.create_user(email=email, password=password)
        uid = user.uid
        
        # Hash password for local storage
        password_hash = PasswordManager.hash_password(password)
        
        # Create user data
        user_data = {
            'uid': uid,
            'name': name,
            'age': age,
            'email': email,
            'password_hash': password_hash,
            'purpose': purpose,
            'about': '',
            'skills': [],
            'hobbies': [],
            'certificates': [],
            'achievements': [],
            'interests': {'careers': [], 'courses': [], 'internships': []},
            'highschool': None,
            'exam': None,
            'after_tenth': None,
            'chapters_completed': {},
            'time_studied': 0,
            'goals': [],
            'tasks': [],
            'todos': [],
            'milestones': [],
            'exam_results': [],
            'timezone': 'Asia/Kolkata',  # Default timezone (IST)
            'connections': {
                'accepted': [],
                'pending_sent': [],
                'pending_received': []
            },
            'bubbles': [],
            'academic_sharing_consents': {},
            'profile_visibility': {
                'name': True,
                'grade': True,
                'school': True,
                'academic_progress': False,
                'subjects': True
            },
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Save user to Firestore
        set_document('users', uid, user_data)
        
        # Initialize profile fields
        initialize_profile_fields(uid)
        
        # Log registration
        logger.security_event("user_registered", user_id=uid, ip_address=ip_address)
        
        return True, 'Account created successfully', uid
        
    except Exception as e:
        logger.error("signup_error", error=str(e), email=email)
        return False, 'Error creating account: An error occurred during registration', None


def authenticate_user(email: str, password: str, ip_address: str = None) -> Tuple[bool, str, Optional[Dict]]:
    """
    Authenticate user with email and password.
    
    Args:
        email: User's email address
        password: User's password
        ip_address: User's IP address for logging
        
    Returns:
        Tuple of (success: bool, message: str, user_data: Optional[Dict])
    """
    try:
        # Authenticate with Firebase
        user = firebase_auth.sign_in_with_email_and_password(email, password)
        uid = user['localId']
        
        # Get user data from Firestore
        user_data = get_document('users', uid)
        if not user_data:
            return False, 'User data not found', None
        
        # Log successful login
        logger.security_event("user_login", user_id=uid, ip_address=ip_address)
        
        return True, 'Login successful', user_data
        
    except Exception as e:
        logger.error("login_error", error=str(e), email=email)
        return False, 'Invalid email or password', None


def register_admin(name: str, email: str, password: str, institution_name: str, ip_address: str = None) -> Tuple[bool, str, Optional[str]]:
    """
    Register a new admin account.
    
    Args:
        name: Admin's full name
        email: Admin's email address
        password: Admin's password
        institution_name: Name of the institution
        ip_address: User's IP address for logging
        
    Returns:
        Tuple of (success: bool, message: str, admin_id: Optional[str])
    """
    try:
        # Check if email already exists
        try:
            admin_auth.get_user_by_email(email)
            return False, 'Email already exists.', None
        except admin_auth.UserNotFoundError:
            pass
        
        # Create Firebase Auth user
        user = admin_auth.create_user(email=email, password=password)
        uid = user.uid
        
        # Hash password for local storage
        password_hash = PasswordManager.hash_password(password)
        
        # Create institution first
        institution_data = {
            'name': institution_name,
            'created_at': datetime.utcnow().isoformat(),
            'created_by': uid,
            'admin_ids': [uid],
            'teacher_ids': [],
            'student_ids': []
        }
        
        institution_ref = db.collection('institutions').add(institution_data)
        institution_id = institution_ref[1].id
        
        # Create admin data
        admin_data = {
            'uid': uid,
            'name': name,
            'email': email,
            'password_hash': password_hash,
            'institution_id': institution_id,
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Save admin to Firestore
        set_document('institution_admins', uid, admin_data)
        
        # Update institution with admin ID
        db.collection('institutions').document(institution_id).update({
            'admin_ids': [uid]
        })
        
        # Log registration
        logger.security_event("admin_registered", user_id=uid, ip_address=ip_address)
        
        return True, 'Admin account created successfully', uid
        
    except Exception as e:
        logger.error("admin_signup_error", error=str(e), email=email)
        return False, 'Error creating admin account.', None


def authenticate_admin(email: str, password: str, ip_address: str = None) -> Tuple[bool, str, Optional[Dict]]:
    """
    Authenticate admin with email and password.
    
    Args:
        email: Admin's email address
        password: Admin's password
        ip_address: User's IP address for logging
        
    Returns:
        Tuple of (success: bool, message: str, admin_data: Optional[Dict])
    """
    try:
        # Authenticate with Firebase
        user = firebase_auth.sign_in_with_email_and_password(email, password)
        uid = user['localId']
        
        # Get admin data from Firestore
        admin_data = get_document('institution_admins', uid)
        if not admin_data:
            return False, 'Admin account not found', None
        
        # Log successful login
        logger.security_event("admin_login", user_id=uid, ip_address=ip_address)
        
        return True, 'Login successful', admin_data
        
    except Exception as e:
        logger.error("admin_login_error", error=str(e), email=email)
        return False, 'Invalid email or password', None


def register_teacher(name: str, email: str, password: str, ip_address: str = None) -> Tuple[bool, str, Optional[str]]:
    """
    Register a new teacher account.
    
    Args:
        name: Teacher's full name
        email: Teacher's email address
        password: Teacher's password
        ip_address: User's IP address for logging
        
    Returns:
        Tuple of (success: bool, message: str, teacher_id: Optional[str])
    """
    try:
        # Check if email already exists
        try:
            admin_auth.get_user_by_email(email)
            return False, 'Email already exists.', None
        except admin_auth.UserNotFoundError:
            pass
        
        # Create Firebase Auth user
        user = admin_auth.create_user(email=email, password=password)
        uid = user.uid
        
        # Hash password for local storage
        password_hash = PasswordManager.hash_password(password)
        
        # Create teacher data
        teacher_data = {
            'uid': uid,
            'name': name,
            'email': email,
            'password_hash': password_hash,
            'institution_id': None,  # Will be set when joining institution
            'created_at': datetime.utcnow().isoformat(),
            'status': 'pending'  # pending, active, disabled
        }
        
        # Save teacher to Firestore
        set_document('institution_teachers', uid, teacher_data)
        
        # Log registration
        logger.security_event("teacher_registered", user_id=uid, ip_address=ip_address)
        
        return True, 'Teacher account created successfully', uid
        
    except Exception as e:
        logger.error("teacher_signup_error", error=str(e), email=email)
        return False, 'Error creating teacher account.', None


def authenticate_teacher(email: str, password: str, ip_address: str = None) -> Tuple[bool, str, Optional[Dict]]:
    """
    Authenticate teacher with email and password.
    
    Args:
        email: Teacher's email address
        password: Teacher's password
        ip_address: User's IP address for logging
        
    Returns:
        Tuple of (success: bool, message: str, teacher_data: Optional[Dict])
    """
    try:
        # Authenticate with Firebase
        user = firebase_auth.sign_in_with_email_and_password(email, password)
        uid = user['localId']
        
        # Get teacher data from Firestore
        teacher_data = get_document('institution_teachers', uid)
        if not teacher_data:
            return False, 'Teacher account not found', None
        
        # Check if teacher is active
        if teacher_data.get('status') == 'disabled':
            return False, 'Teacher account is disabled', None
        
        # Log successful login
        logger.security_event("teacher_login", user_id=uid, ip_address=ip_address)
        
        return True, 'Login successful', teacher_data
        
    except Exception as e:
        logger.error("teacher_login_error", error=str(e), email=email)
        return False, 'Invalid email or password', None


def validate_registration_data(data: Dict) -> Tuple[bool, str, Optional[Dict]]:
    """
    Validate user registration data.
    
    Args:
        data: Registration form data
        
    Returns:
        Tuple of (is_valid: bool, message: str, validated_data: Optional[Dict])
    """
    # Validate using schema
    is_valid, result = validate_schema(user_registration_schema, data)
    if not is_valid:
        return False, f'Validation error: {result}', None
    
    # Check password strength
    password = result.get('password', '')
    is_strong, msg = PasswordManager.is_strong_password(password)
    if not is_strong:
        return False, f'Password not strong enough: {msg}', None
    
    return True, 'Validation successful', result


def validate_login_data(data: Dict) -> Tuple[bool, str, Optional[Dict]]:
    """
    Validate user login data.
    
    Args:
        data: Login form data
        
    Returns:
        Tuple of (is_valid: bool, message: str, validated_data: Optional[Dict])
    """
    # Validate using schema
    is_valid, result = validate_schema(user_login_schema, data)
    if not is_valid:
        return False, f'Validation error: {result}', None
    
    return True, 'Validation successful', result
