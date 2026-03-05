"""
Authentication blueprint.
Handles user authentication, registration, login, logout, and session management.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.extensions import get_limiter
from app.services.auth_service import (
    register_user, authenticate_user, register_admin, authenticate_admin,
    register_teacher, authenticate_teacher, validate_registration_data, validate_login_data
)
from app.models.auth import require_login, set_session_identity
from app.models.profile import initialize_profile_fields
from utils import logger
import os

# Get configuration
env = os.environ.get('FLASK_ENV', 'production')
from config import config

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    """Main index route - redirect based on authentication status."""
    if 'uid' in session:
        return redirect(url_for('dashboard.profile_dashboard'))
    return redirect(url_for('auth.landing'))


@auth_bp.route('/landing')
def landing():
    """Landing page for non-authenticated users."""
    return render_template('landing.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
@get_limiter().limit(config[env].RATE_LIMIT_SIGNUP)
def signup():
    """User registration endpoint."""
    if request.method == 'POST':
        # Validate input
        data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'purpose': request.form.get('purpose')
        }
        
        is_valid, message, validated_data = validate_registration_data(data)
        if not is_valid:
            flash(message, 'error')
            return redirect(url_for('auth.signup'))
        
        name = validated_data['name']
        email = validated_data['email']
        password = validated_data['password']
        purpose = validated_data['purpose']
        age = request.form.get('age')
        
        # Register user
        success, message, user_id = register_user(name, email, password, purpose, age, request.remote_addr)
        
        if success:
            session['uid'] = user_id
            flash('Account created successfully!', 'success')
            
            # Redirect to appropriate setup
            if purpose == 'school':
                return redirect(url_for('auth.setup_highschool'))
            elif purpose == 'exam_prep':
                return redirect(url_for('auth.setup_exam'))
            else:
                flash('Invalid purpose selected', 'error')
                return redirect(url_for('auth.signup'))
        else:
            flash(message, 'error')
            return redirect(url_for('auth.signup'))
    
    return render_template('signup.html')


@auth_bp.route('/setup/highschool', methods=['GET', 'POST'])
@require_login
def setup_highschool():
    """High school setup for student accounts."""
    if request.method == 'POST':
        uid = session['uid']
        
        # Basic school info
        school_data = {
            'board': request.form.get('board'),
            'grade': request.form.get('grade')
        }
        
        # Add subject combination for grades 11 and 12
        grade = request.form.get('grade')
        if grade in ['11', '12']:
            subject_combination = request.form.get('subject_combination')
            if subject_combination:
                school_data['subject_combination'] = subject_combination
        
        # Update user with school data
        from app.models.firestore_helpers import update_document
        update_document('users', uid, {'school': school_data})
        
        flash('Setup complete!', 'success')
        return redirect(url_for('dashboard.profile_dashboard'))
    
    return render_template('setup_highschool.html')


@auth_bp.route('/setup/exam', methods=['GET', 'POST'])
@require_login
def setup_exam():
    """Exam setup for exam preparation accounts."""
    if request.method == 'POST':
        uid = session['uid']
        exam_type = request.form.get('exam_type')
        
        from app.models.firestore_helpers import update_document
        update_document('users', uid, {'exam': {'type': exam_type}})
        
        flash('Setup complete!', 'success')
        return redirect(url_for('dashboard.profile_dashboard'))
    
    return render_template('setup_exam.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
@get_limiter().limit(config[env].RATE_LIMIT_LOGIN)
def login():
    """User login endpoint."""
    if request.method == 'POST':
        # Get client IP for rate limiting
        client_ip = request.remote_addr
        
        # Validate input
        data = {
            'email': request.form.get('email', '').strip(),
            'password': request.form.get('password', '')
        }
        
        is_valid, message, validated_data = validate_login_data(data)
        if not is_valid:
            flash(message, 'error')
            return redirect(url_for('auth.login'))
        
        email = validated_data['email']
        password = validated_data['password']
        
        # Authenticate user
        success, message, user_data = authenticate_user(email, password, client_ip)
        
        if success:
            session['uid'] = user_data['uid']
            set_session_identity(user_data['uid'], 'student')
            
            # Initialize profile fields
            initialize_profile_fields(user_data['uid'])
            
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard.profile_dashboard'))
        else:
            flash(message, 'error')
            return redirect(url_for('auth.login'))
    
    return render_template('login.html')


@auth_bp.route('/login/student', methods=['GET', 'POST'])
def login_student():
    """Explicit student login (mirrors /login for clarity)."""
    return login()


@auth_bp.route('/logout')
def logout():
    """User logout endpoint."""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('auth.landing'))


@auth_bp.route('/signup/admin', methods=['GET', 'POST'])
def signup_admin():
    """Admin registration endpoint."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        institution_name = request.form.get('institution_name', '').strip()
        
        # Basic validation
        if not all([name, email, password, institution_name]):
            flash('All fields are required.', 'error')
            return redirect(url_for('auth.signup_admin'))
        
        # Register admin
        success, message, admin_id = register_admin(name, email, password, institution_name, request.remote_addr)
        
        if success:
            flash('Admin account created successfully!', 'success')
            return redirect(url_for('auth.login_admin'))
        else:
            flash(message, 'error')
            return redirect(url_for('auth.signup_admin'))
    
    return render_template('signup_admin.html')


@auth_bp.route('/login/admin', methods=['GET', 'POST'])
def login_admin():
    """Admin login endpoint."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        # Authenticate admin
        success, message, admin_data = authenticate_admin(email, password, request.remote_addr)
        
        if success:
            session['uid'] = admin_data['uid']
            set_session_identity(admin_data['uid'], 'admin', admin_data.get('institution_id'))
            
            flash('Login successful!', 'success')
            return redirect(url_for('institution.institution_admin_dashboard'))
        else:
            flash(message, 'error')
            return redirect(url_for('auth.login_admin'))
    
    return render_template('login_admin.html')


@auth_bp.route('/signup/teacher', methods=['GET', 'POST'])
def signup_teacher():
    """Teacher registration endpoint."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        # Basic validation
        if not all([name, email, password]):
            flash('All fields are required.', 'error')
            return redirect(url_for('auth.signup_teacher'))
        
        # Register teacher
        success, message, teacher_id = register_teacher(name, email, password, request.remote_addr)
        
        if success:
            flash('Teacher account created successfully!', 'success')
            return redirect(url_for('auth.login_teacher'))
        else:
            flash(message, 'error')
            return redirect(url_for('auth.signup_teacher'))
    
    return render_template('signup_teacher.html')


@auth_bp.route('/login/teacher', methods=['GET', 'POST'])
def login_teacher():
    """Teacher login endpoint."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        # Authenticate teacher
        success, message, teacher_data = authenticate_teacher(email, password, request.remote_addr)
        
        if success:
            session['uid'] = teacher_data['uid']
            set_session_identity(teacher_data['uid'], 'teacher', teacher_data.get('institution_id'))
            
            flash('Login successful!', 'success')
            return redirect(url_for('institution.institution_teacher_dashboard'))
        else:
            flash(message, 'error')
            return redirect(url_for('auth.login_teacher'))
    
    return render_template('login_teacher.html')


@auth_bp.route('/institution/gateway')
def institution_gateway():
    """Gateway page for institution users to select their role (Teacher/Admin)."""
    return render_template('institution_gateway.html')
