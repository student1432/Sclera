# ============================================================================
# SCLERA - Academic Institution Platform (Standalone Slice)
# Extracted from the StudyOS monolith app.py
# Contains: Auth, Dashboard, Academic, Calendar, Study Mode, AI, Docs,
#           Institution Management (Admin/Teacher), Statistics, Settings
# Excludes: Community/Bubbles/Chat (ScleraCollab), Careers/Courses (ScleraCareer)
# ============================================================================
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort, send_from_directory
from firebase_config import auth, db
from firebase_admin import auth as admin_auth, storage
from datetime import datetime, date, timedelta
from templates.academic_data import get_syllabus, get_available_subjects, ACADEMIC_SYLLABI
from careers_data import get_career_by_id

from utils import (
    PasswordManager, login_rate_limiter, logger, validate_schema,
    user_registration_schema, user_login_schema, CacheManager
)
from utils.timezone import get_current_time_for_user
from config import config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_mail import Mail, Message
import os
from werkzeug.utils import secure_filename
import time
import uuid
from functools import wraps
from firebase_admin import firestore
Increment = firestore.Increment
from collections import defaultdict
import random
import string
from marshmallow import ValidationError
import traceback
# AI Assistant import
from ai_assistant import get_ai_assistant
# Gemini Analytics import
from gemini_analytics import gemini_analytics
# CLI Commands import
from gemini_cli import register_cli_commands
# Chat security utilities
# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()
# Initialize Flask app with configuration
env = os.environ.get('FLASK_ENV', 'production')
app = Flask(__name__, template_folder='sclera_templates')
config[env].init_app(app)
# Dedicated CSS endpoint with explicit MIME type
@app.route('/styles.css')
def serve_css():
    from flask import send_from_directory
    return send_from_directory('static', 'styles.css')
# Initialize rate limiter
disable_rate_limits = (
    env == 'development' or
    os.environ.get('DISABLE_RATE_LIMITS', 'False').lower() == 'true'
)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[config[env].RATE_LIMIT_DEFAULT],
    enabled=(not disable_rate_limits),
    storage_uri="memory://"
)
# Initialize security headers with Talisman
Talisman(app,
    force_https=config[env].SESSION_COOKIE_SECURE,
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,
    strict_transport_security_include_subdomains=True,
    content_security_policy={
        'default-src': "'self'",
        'script-src': ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://fonts.googleapis.com", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com", "https://cdn.jsdelivr.net", "https://cdn.socket.io"],
        'style-src': ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://fonts.googleapis.com", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com"],
        'font-src': ["https://fonts.googleapis.com", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com"],
        'img-src': ["'self'", "data:", "https:"],
        'connect-src': ["'self'", "https://cdn.jsdelivr.net", "https://cdn.socket.io", "wss:", "ws:"],
        'frame-ancestors': "'none'",
        'base-uri': "'self'",
        'form-action': "'self'"
    },
    referrer_policy='strict-origin-when-cross-origin'
)
user_ref = None
# Initialize Flask-Mail
mail = Mail(app)
from report_generator import generate_class_report_pdf, generate_student_report_pdf
import io, json
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
# ============================================================================
# INSTITUTION V2 CONSTANTS / HELPERS
# ============================================================================
INSTITUTION_ADMINS_COL = 'institution_admins'
INSTITUTION_TEACHERS_COL = 'institution_teachers'
INSTITUTIONS_COL = 'institutions'
TEACHER_INVITES_COL = 'teacher_invites'
CLASSES_COL = 'classes'
CLASS_INVITES_COL = 'class_invites'
def _generate_code(length: int = 6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
def _set_session_identity(uid: str, account_type: str, institution_id: str | None = None):
    session['uid'] = uid
    session['account_type'] = account_type  # 'student' | 'teacher' | 'admin'
    if institution_id:
        session['institution_id'] = institution_id
    else:
        session.pop('institution_id', None)
def _get_account_type() -> str:
    return session.get('account_type', 'student')
def require_institution_role(allowed_roles: list[str]):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'uid' not in session:
                return redirect(url_for('login'))
            account_type = _get_account_type()
            if account_type not in allowed_roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator
require_admin_v2 = require_institution_role(['admin'])
require_teacher_v2 = require_institution_role(['teacher'])
def _get_admin_profile(uid: str) -> dict | None:
    profile = _get_any_profile(uid)
    return profile if profile and profile.get('account_type') == 'admin' else None
def _get_teacher_profile(uid: str) -> dict | None:
    profile = _get_any_profile(uid)
    return profile if profile and profile.get('account_type') == 'teacher' else None
def _get_any_profile(uid: str) -> dict | None:
    """Check all identity collections and return profile + account_type."""
    # Check collections in order of specificity
    doc = db.collection(INSTITUTION_ADMINS_COL).document(uid).get()
    if doc.exists: return {**doc.to_dict(), 'account_type': 'admin'}
    doc = db.collection(INSTITUTION_TEACHERS_COL).document(uid).get()
    if doc.exists: return {**doc.to_dict(), 'account_type': 'teacher'}
    doc = db.collection('users').document(uid).get()
    if doc.exists: return {**doc.to_dict(), 'account_type': 'student'}
    return None
def _get_institution_analytics(institution_id, class_ids=None):
    """
    Enhanced analytics with Gemini AI predictions for at-risk detection.
    Falls back to rule-based logic if AI predictions unavailable.
    If class_ids is provided, filter students by those classes.
    """
    heatmap_data = defaultdict(int)
    at_risk_students = []
    if not institution_id:
        return {'heatmap': {}, 'at_risk': []}
    
    # 1. Fetch relevant classes
    classes_ref = db.collection(CLASSES_COL).where('institution_id', '==', institution_id)
    classes_docs = list(classes_ref.stream())
    if class_ids:
        classes_docs = [d for d in classes_docs if d.id in class_ids]
    classes_map = {d.id: d.to_dict() for d in classes_docs}
    all_student_ids = set()
    for _, c_data in classes_map.items():
        all_student_ids.update(c_data.get('student_uids', []))
    
    # 2. Aggregations (Heatmap)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    for sid in all_student_ids:
        sessions = db.collection('users').document(sid).collection('study_sessions').where('start_time', '>=', thirty_days_ago.isoformat()).stream()
        for s in sessions:
            s_data = s.to_dict()
            h = s_data.get('local_hour')
            w = s_data.get('local_weekday')
            if h is not None and w is not None:
                heatmap_data[f"{w}-{h}"] += 1
    
    # 3. Enhanced Risk Analytics with Gemini predictions
    for sid in all_student_ids:
        s_doc = db.collection('users').document(sid).get()
        if not s_doc.exists: continue
        s_data = s_doc.to_dict()
        
        # Try to get Gemini predictions first
        risk_prediction = s_data.get('risk_prediction', {})
        readiness_prediction = s_data.get('readiness_prediction', {})
        
        # Check if we need to generate new AI predictions
        use_ai_predictions = False
        needs_prediction_update = False
        
        if risk_prediction:
            try:
                last_updated = risk_prediction.get('last_updated', '')
                prompt_version = risk_prediction.get('prompt_version', 'v1')
                if last_updated:
                    last_date = datetime.fromisoformat(last_updated)
                    # Use predictions if they're recent (within 7 days) and from v2 prompt
                    if (datetime.utcnow() - last_date).days <= 7 and prompt_version == 'v2':
                        use_ai_predictions = True
                    # Mark for update if predictions are old or from v1 prompt
                    elif (datetime.utcnow() - last_date).days > 7 or prompt_version != 'v2':
                        needs_prediction_update = True
            except:
                needs_prediction_update = True
        else:
            # No predictions exist, need to generate
            needs_prediction_update = True
        
        # Auto-generate AI predictions if needed and available
        if needs_prediction_update and gemini_analytics.ai_available:
            try:
                new_risk_data, new_readiness_data = gemini_analytics.predict_student_risk_and_readiness(sid)
                if new_risk_data or new_readiness_data:
                    gemini_analytics.store_student_predictions(sid, new_risk_data, new_readiness_data)
                    # Use the newly generated predictions
                    if new_risk_data and new_risk_data.get('risk') == 'at_risk':
                        risk_prediction = new_risk_data
                        readiness_prediction = new_readiness_data or {}
                        use_ai_predictions = True
                        logger.info(f"Auto-generated AI predictions for student {sid}")
            except Exception as e:
                logger.error(f"Failed to auto-generate predictions for {sid}: {e}")
                # Fall back to rule-based if AI generation fails
        
        student_class = "Unknown"
        for cid, cdata in classes_map.items():
            if sid in cdata.get('student_uids', []):
                student_class = cdata.get('name', cid)
                break
        
        if use_ai_predictions and risk_prediction.get('risk') == 'at_risk':
            # Use AI-predicted at-risk students
            at_risk_students.append({
                'uid': sid,
                'name': s_data.get('name', 'Student'),
                'class': student_class,
                'status': 'at_risk_ai',
                'risk_level': risk_prediction.get('risk', 'at_risk'),
                'explanation': risk_prediction.get('explanation', 'AI-detected risk'),
                'confidence': risk_prediction.get('confidence', 0),
                'key_factors': risk_prediction.get('key_factors', []),
                'readiness_score': readiness_prediction.get('readiness_score', 0),
                'readiness_summary': readiness_prediction.get('summary', ''),
                'ai_detected': True
            })
        else:
            # Fallback to rule-based logic for students without AI predictions
            last_str = s_data.get('last_login_date')
            status = 'healthy'
            momentum = 0
            
            # Check login activity
            if not last_str: 
                status = 'stagnating'
            else:
                days = (datetime.utcnow() - datetime.fromisoformat(last_str)).days
                if days > 7: status = 'stagnating'
            
            # Check chapter completion (NEW)
            progress = calculate_academic_progress(s_data)
            completion_rate = progress.get('overall', 0)
            if completion_rate < 25 and status == 'healthy':
                status = 'declining'  # Low completion rate
            
            # Velocity Momentum
            results = s_data.get('exam_results', [])
            if len(results) >= 2:
                try:
                    sorted_res = sorted(results, key=lambda x: x.get('date', ''), reverse=True)
                    series = [float(r.get('percentage', r.get('score', 0))) for r in sorted_res[:3]][::-1]
                    momentum = series[-1] - series[0]
                    if momentum < -5: 
                        status = 'critical' if status == 'stagnating' else 'declining'
                except: 
                    pass
            
            if status != 'healthy':
                at_risk_students.append({
                    'uid': sid,
                    'name': s_data.get('name', 'Student'),
                    'class': student_class,
                    'status': status,
                    'momentum': round(momentum, 2),
                    'completion_rate': completion_rate,
                    'ai_detected': False,
                    'explanation': f'Rule-based detection: {status} (completion: {completion_rate}%, momentum: {round(momentum, 2)})'
                })
    
    return {
        'heatmap': dict(heatmap_data),
        'at_risk': at_risk_students
    }
def _institution_login_guard():
    """Prevent admin/teacher accounts from entering student app routes."""
    if 'uid' not in session:
        return None
    path = request.path or ''
    if path in ['/logout', '/styles.css', '/login'] or path.startswith('/static/'):
        return None
    account_type = _get_account_type()
    # Block students from V2 institution portals
    if account_type == 'student' and (path.startswith('/institution/admin') or path.startswith('/institution/teacher')):
        abort(403)
    # Allow institution routes for admin/teacher
    if path.startswith('/institution'):
        return None
    # Block admin/teacher from student app
    if account_type == 'admin':
        return redirect(url_for('institution_admin_dashboard'))
    if account_type == 'teacher':
        return redirect(url_for('institution_teacher_dashboard'))
    return None
# ============================================================================
# UTILITY FUNCTIONS - 
# ============================================================================
# ============================================================================
# STATISTICS
# ============================================================================
TEST_TYPES = [
    "Unit Test 1", "Unit Test 2", "Unit Test 3", "Unit Test 4",
    "Unit Test 5", "Unit Test 6",
    "Quarterly", "Half Yearly",
    "Pre Midterms", "Midterms", "Post Midterms",
    "1st Midterm", "2nd Midterm",
    "Pre Finals", "Finals",
    "Pre Annual", "Annual"
]
def require_login(f):
    def wrapper(*args, **kwargs):
        if 'uid' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper
def get_user_data(uid):
    user_doc = db.collection('users').document(uid).get()
    if user_doc.exists:
        return user_doc.to_dict()
    return {}

# ============================================================================
# SCLERACOLLAB INTEGRATION FUNCTIONS
# ============================================================================
def get_collab_user_by_email(email: str) -> dict | None:
    """Check if user exists in ScleraCollab collection"""
    try:
        # Access Collab Firestore (same project, different collection)
        collab_users = db.collection('collab_users')
        query = collab_users.where('email', '==', email).limit(1).get()
        for doc in query:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error("collab_user_lookup_error", error=str(e), email=email)
        return None

def get_collab_user_by_uid(uid: str) -> dict | None:
    """Get Collab user by UID"""
    try:
        collab_doc = db.collection('collab_users').document(uid).get()
        if collab_doc.exists:
            return collab_doc.to_dict()
        return None
    except Exception as e:
        logger.error("collab_user_by_uid_error", error=str(e), uid=uid)
        return None

def get_sclera_user_by_uid(uid: str) -> dict | None:
    """Get Sclera user by UID"""
    try:
        sclera_doc = db.collection('users').document(uid).get()
        if sclera_doc.exists:
            return sclera_doc.to_dict()
        return None
    except Exception as e:
        logger.error("sclera_user_by_uid_error", error=str(e), uid=uid)
        return None

def initialize_sclera_from_collab(collab_user: dict, additional_info: dict) -> dict:
    """Create Sclera profile from Collab data"""
    base_profile = {
        'uid': collab_user.get('uid'),
        'name': collab_user.get('name', ''),
        'email': collab_user.get('email', ''),
        'profile_picture': collab_user.get('profile_picture', ''),
        'bio': collab_user.get('bio', ''),
        'imported_from_collab': True,
        'collab_import_date': datetime.utcnow().isoformat(),
        'about': collab_user.get('bio', ''),
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
        'timezone': 'Asia/Kolkata',
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
    
    # Add academic info from additional form
    base_profile.update(additional_info)
    
    # Import education from Collab
    if collab_user.get('education') and len(collab_user['education']) > 0:
        edu = collab_user['education'][0]  # Take first education entry
        base_profile.update({
            'school': {
                'board': edu.get('board', ''),
                'grade': edu.get('grade', ''),
                'institution': edu.get('institution', '')
            }
        })
    else:
        # Create empty school structure if no education data
        base_profile['school'] = {
            'board': '',
            'grade': '',
            'institution': ''
        }
    
    # Import skills from Collab
    if collab_user.get('skills'):
        skills = collab_user['skills']
        if isinstance(skills, list):
            base_profile['skills'] = [s.get('name', s) if isinstance(s, dict) else str(s) for s in skills]
    
    # Import projects from Collab  
    if collab_user.get('projects'):
        base_profile['projects'] = collab_user['projects']
    
    return base_profile
def calculate_academic_progress(user_data, uid=None):
    """
    Calculate academic progress with 3-tier exclusion system:
    Level 1: Institution exclusions (admin)
    Level 2: Class exclusions (teacher)
    Level 3: Personal exclusions (student)
    """
    purpose = user_data.get('purpose')
    chapters_completed = user_data.get('chapters_completed', {})
    personal_exclusions = user_data.get('academic_exclusions', {})
    # Fetch institution and class exclusions
    institution_exclusions = {}
    class_exclusions = {}
    inst_id = user_data.get('institution_id')
    class_ids = user_data.get('class_ids', [])
    # Level 1: Institution Exclusions
    if inst_id:
        try:
            inst_excl_doc = db.collection('institutions').document(inst_id).collection('syllabus_exclusions').document('current').get()
            if inst_excl_doc.exists:
                institution_exclusions = inst_excl_doc.to_dict().get('chapters', {})
        except:
            pass
    # Level 2: Class Exclusions (union of all classes student is in)
    if class_ids:
        for class_id in class_ids:
            try:
                class_excl_doc = db.collection('classes').document(class_id).collection('excluded_chapters').document('current').get()
                if class_excl_doc.exists:
                    class_exclusions.update(class_excl_doc.to_dict().get('chapters', {}))
            except:
                pass
    # Merge all exclusions (union)
    all_exclusions = {}
    all_exclusions.update(institution_exclusions)
    all_exclusions.update(class_exclusions)
    all_exclusions.update(personal_exclusions)
    syllabus = {}
    syllabus_purpose = {
        'school': 'school',
        'exam_prep': 'exam',
        'after_tenth': 'after_tenth'
    }.get(purpose, purpose)
    if purpose == 'school' and user_data.get('school'):
        school = user_data['school']
        subject_combination = school.get('subject_combination')
        syllabus = get_syllabus(syllabus_purpose, school.get('board'), school.get('grade'), subject_combination=subject_combination)
    elif purpose == 'exam_prep' and user_data.get('exam'):
        syllabus = get_syllabus(syllabus_purpose, user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        syllabus = get_syllabus(syllabus_purpose, 'CBSE', at.get('grade'), at.get('subjects', []))
    if not syllabus:
        return {
            'overall': 0,
            'by_subject': {},
            'total_chapters': 0,
            'total_completed': 0,
            'momentum': 0,
            'consistency': 0,
            'readiness': 0
        }
    by_subject = {}
    chapters_by_subject = {}
    total_chapters = 0
    total_completed = 0
    for subject_name, subject_data in syllabus.items():
        chapters = subject_data.get('chapters', {})
        subject_completed_data = chapters_completed.get(subject_name, {})
        subject_valid_count = 0
        subject_completed_count = 0
        for chapter_name in chapters.keys():
            exclusion_key = f"{subject_name}::{chapter_name}"
            # If chapter is excluded at ANY level, skip it
            if all_exclusions.get(exclusion_key):
                continue
            subject_valid_count += 1
            if subject_completed_data.get(chapter_name, False):
                subject_completed_count += 1
        if subject_valid_count > 0:
            by_subject[subject_name] = round((subject_completed_count / subject_valid_count) * 100, 1)
        else:
            by_subject[subject_name] = 0
        # Store chapter counts per subject
        chapters_by_subject[subject_name] = {
            'total': subject_valid_count,
            'completed': subject_completed_count
        }
        total_chapters += subject_valid_count
        total_completed += subject_completed_count
    # --- AI Analytics Engine ---
    momentum = 0
    consistency = 0
    readiness = 0
    # 1. Momentum: Last 4 exams gradient
    results = user_data.get('exam_results', [])
    if len(results) >= 2:
        sorted_res = sorted(results, key=lambda x: x.get('date', ''), reverse=True)
        try:
            series = [float(r.get('percentage', r.get('score', 0))) for r in sorted_res[:4]][::-1]
            momentum = round(series[-1] - series[0], 1)
        except: pass
    # 2. Consistency: Time pattern stability
    # In a full app, we analyze study_sessions. Here we use session data if available.
    # Logic: More sessions per week = higher consistency.
    sessions_count = len(user_data.get('recent_sessions', [])) # Mocking session density
    consistency = min(100, sessions_count * 15) # Example calculation
    # 3. Readiness: Weighted Academic Health
    avg_score = 0
    if results:
        avg_score = sum([float(r.get('percentage', r.get('score', 0))) for r in results]) / len(results)
    overall = round((total_completed / total_chapters) * 100, 1) if total_chapters > 0 else 0
    readiness = round((overall * 0.4) + (avg_score * 0.6), 1)
    return {
        'overall': overall,
        'by_subject': by_subject,
        'chapters_by_subject': chapters_by_subject,
        'total_chapters': total_chapters,
        'total_completed': total_completed,
        'momentum': momentum,
        'consistency': consistency,
        'readiness': readiness
    }
def calculate_average_percentage(results):
    valid_percentages = []
    for r in results:
        try:
            score = float(r.get('score', 0))
            max_score = float(r.get('max_score', 0))
            if max_score > 0:
                pct = (score / max_score) * 100
                valid_percentages.append(pct)
        except (TypeError, ValueError):
            continue
    if not valid_percentages:
        return 0
    return round(sum(valid_percentages) / len(valid_percentages), 1)
def initialize_profile_fields(uid):
    user_doc = db.collection('users').document(uid).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    updates = {}
    defaults = {
        'about': '', 'skills': [], 'hobbies': [], 'certificates': [],
        'achievements': [], 'chapters_completed': {}, 'time_studied': 0,
        'goals': [], 'tasks': [], 'todos': [], 'milestones': [], 'exam_results': [],
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
        }
    }
    # interests is a structured object now
    if 'interests' not in user_data:
        updates['interests'] = {'careers': [], 'courses': [], 'internships': []}
    elif isinstance(user_data.get('interests'), list):
        # migrate old list format to new structured format
        updates['interests'] = {'careers': [], 'courses': [], 'internships': []}
    for key, default in defaults.items():
        if key not in user_data:
            updates[key] = default
    if updates:
        db.collection('users').document(uid).update(updates)
    # Remove the problematic lines that try to access session and get_user_data
    # uid = session['uid']  # This causes error during login
    # user_data = get_user_data(uid)  # This is unnecessary
    # name_top_statistics = user_data.get('name')  # This variable is not used
# ============================================================================
# AUTH ROUTES
# ============================================================================
@app.route('/')
def index():
    if 'uid' in session:
        return redirect(url_for('profile_dashboard'))
    return redirect(url_for('landing'))
@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/institution/gateway')
def institution_gateway():
    """Gateway page for institution users to select their role (Teacher/Admin)"""
    return render_template('institution_gateway.html')
@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit(config[env].RATE_LIMIT_SIGNUP)
def signup():
    if request.method == 'POST':
        # Validate input using schema
        data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'purpose': request.form.get('purpose')
        }
        is_valid, result = validate_schema(user_registration_schema, data)
        if not is_valid:
            flash(f'Validation error: {result}', 'error')
            return redirect(url_for('signup'))
        name = result['name']
        age = request.form.get('age')
        email = result['email']
        password = result['password']
        purpose = result['purpose']
        # Check password strength
        is_strong, msg = PasswordManager.is_strong_password(password)
        if not is_strong:
            flash(f'Password not strong enough: {msg}', 'error')
            return redirect(url_for('signup'))
        
        # NEW: Check Collab first
        collab_user = get_collab_user_by_email(email)
        if collab_user:
            flash('You already have a ScleraCollab account. Please login instead.', 'error')
            return redirect(url_for('login'))
        
        try:
            try:
                admin_auth.get_user_by_email(email)
                flash('Email already exists. Please login.', 'error')
                return redirect(url_for('login'))
            except admin_auth.UserNotFoundError:
                pass
            user = admin_auth.create_user(email=email, password=password)
            uid = user.uid
            password_hash = PasswordManager.hash_password(password)
            user_data = {
                'uid': uid, 'name': name, 'age': age, 'email': email,
                'password_hash': password_hash, 'purpose': purpose,
                'about': '', 'skills': [], 'hobbies': [], 'certificates': [],
                'achievements': [],
                'interests': {'careers': [], 'courses': [], 'internships': []},
                'highschool': None, 'exam': None, 'after_tenth': None,
                'chapters_completed': {}, 'time_studied': 0,
                'goals': [], 'tasks': [], 'todos': [], 'milestones': [],
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
            db.collection('users').document(uid).set(user_data)
            session['uid'] = uid
            logger.security_event("user_registered", user_id=uid, ip_address=request.remote_addr)
            if purpose == 'school':
                return redirect(url_for('setup_highschool'))
            elif purpose == 'exam_prep':
                return redirect(url_for('setup_exam'))
            else:
                flash('Invalid purpose selected', 'error')
                return redirect(url_for('signup'))
        except Exception as e:
            logger.error("signup_error", error=str(e), email=email)
            flash(f'Error creating account: An error occurred during registration', 'error')
            return redirect(url_for('signup'))
    return render_template('signup.html')
@app.route('/setup/highschool', methods=['GET', 'POST'])
@require_login
def setup_highschool():
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
                
                # Add custom subjects if selected
                if subject_combination == 'Custom':
                    custom_subjects = request.form.getlist('subjects')
                    if custom_subjects:
                        school_data['custom_subjects'] = custom_subjects
        
        db.collection('users').document(uid).update({'school': school_data})
        flash('Setup complete!', 'success')
        return redirect(url_for('profile_dashboard'))
    
    # GET request - check if we have pre-filled data from Collab
    pending_board = session.pop('pending_board', None)
    pending_grade = session.pop('pending_grade', None)
    pending_school = session.pop('pending_school', None)
    
    return render_template('setup_highschool.html', 
                         prefill_board=pending_board,
                         prefill_grade=pending_grade,
                         prefill_school=pending_school)
@app.route('/setup/exam', methods=['GET', 'POST'])
@require_login
def setup_exam():
    if request.method == 'POST':
        uid = session['uid']
        db.collection('users').document(uid).update({'exam': {'type': request.form.get('exam_type')}})
        flash('Setup complete!', 'success')
        return redirect(url_for('profile_dashboard'))
    return render_template('setup_exam.html')
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit(config[env].RATE_LIMIT_LOGIN)
def login():
    if request.method == 'POST':
        # Get client IP for rate limiting
        client_ip = request.remote_addr
        # Check rate limiting
        if not login_rate_limiter.is_allowed(client_ip):
            flash('Too many login attempts. Please try again later.', 'error')
            logger.security_event("login_rate_limited", ip_address=client_ip)
            return redirect(url_for('login'))
        # Validate input
        data = {
            'email': request.form.get('email'),
            'password': request.form.get('password')
        }
        is_valid, result = validate_schema(user_login_schema, data)
        if not is_valid:
            flash('Invalid email or password format', 'error')
            return redirect(url_for('login'))
        email = result['email']
        password = result['password']
        
        try:
            # NEW: Check Collab first
            collab_user = get_collab_user_by_email(email)
            
            if collab_user:
                # Try Collab authentication
                user = admin_auth.get_user_by_email(email)
                uid = user.uid
                
                # Verify UID matches Collab user
                if uid != collab_user.get('uid'):
                    login_rate_limiter.record_attempt(client_ip)
                    flash('Invalid credentials for your ScleraCollab account.', 'error')
                    return render_template('login.html')
                
                # Check if Sclera profile exists
                sclera_user = get_sclera_user_by_uid(uid)
                
                if not sclera_user:
                    # Show academic info collection form
                    return render_template('complete_academic_profile.html', 
                                     collab_user=collab_user)
                else:
                    # Existing Sclera user - normal login
                    login_rate_limiter.reset_attempts(client_ip)
                    _set_session_identity(uid, 'student')
                    session.permanent = True
                    session['from_collab'] = True
                    logger.security_event("successful_login", user_id=uid, ip_address=client_ip)
                    
                    # Update login streak
                    user_ref = db.collection('users').document(uid)
                    snapshot = user_ref.get()
                    user_data = snapshot.to_dict() if snapshot.exists else {}
                    today = date.today().isoformat()
                    last_login = user_data.get('last_login_date')
                    streak = user_data.get('login_streak', 0)
                    if last_login:
                        last_date = datetime.fromisoformat(last_login).date()
                        if last_date == date.today():
                            pass
                        elif last_date == date.today() - timedelta(days=1):
                            streak +=1
                        else:
                            streak=1
                    else:
                        streak = 1
                    user_ref.update({
                        'last_login_date': today,
                        'login_streak': streak
                    })
                    initialize_profile_fields(uid)
                    flash('Welcome back from ScleraCollab!', 'success')
                    return redirect(url_for('profile_dashboard'))
            
            # Normal Sclera login flow
            user = admin_auth.get_user_by_email(email)
            uid = user.uid
            user_doc = db.collection('users').document(uid).get()
            if not user_doc.exists:
                login_rate_limiter.record_attempt(client_ip)
                flash('Invalid email or password', 'error')
                return redirect(url_for('login'))
            user_data = user_doc.to_dict()
            stored_hash = user_data.get('password_hash')
            if not stored_hash:
                flash('Please contact support to reset your password', 'error')
                return redirect(url_for('login'))
            if not PasswordManager.verify_password(password, stored_hash):
                login_rate_limiter.record_attempt(client_ip)
                logger.security_event("failed_login", user_id=uid, ip_address=client_ip)
                flash('Invalid email or password', 'error')
                return redirect(url_for('login'))
            # Check if this is a legacy SHA-256 hash and upgrade to bcrypt
            if PasswordManager._is_legacy_hash(stored_hash):
                new_hash = PasswordManager.hash_password(password)
                db.collection('users').document(uid).update({'password_hash': new_hash})
                logger.security_event("password_hash_upgraded", user_id=uid, ip_address=client_ip)
            # Successful login - reset rate limiter
            login_rate_limiter.reset_attempts(client_ip)
            _set_session_identity(uid, 'student')
            session.permanent = True
            logger.security_event("successful_login", user_id=uid, ip_address=client_ip)
            user_ref = db.collection('users').document(uid)
            snapshot = user_ref.get()
            user_data = snapshot.to_dict() if snapshot.exists else {}
            today = date.today().isoformat()
            last_login = user_data.get('last_login_date')
            streak = user_data.get('login_streak', 0)
            if last_login:
                last_date = datetime.fromisoformat(last_login).date()
                if last_date == date.today():
                    pass
                elif last_date == date.today() - timedelta(days=1):
                    streak +=1
                else:
                    streak=1
            else:
                streak = 1
            user_ref.update({
                'last_login_date': today,
                'login_streak': streak
            })
            initialize_profile_fields(uid)
            flash('Login successful!', 'success')
            return redirect(url_for('profile_dashboard'))
            
        except admin_auth.UserNotFoundError:
            login_rate_limiter.record_attempt(client_ip)
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
        except Exception as e:
            logger.error("login_error", error=str(e), email=email, ip=client_ip, traceback=str(e.__traceback__))
            flash(f'Login error: {str(e)}', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')
@app.route('/login/student', methods=['GET', 'POST'])
def login_student():
    """Explicit student login (mirrors /login for clarity)"""
    return login()
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('landing'))

@app.route('/complete-academic-profile', methods=['POST'])
def complete_academic_profile():
    uid = request.form.get('uid')
    purpose = request.form.get('purpose')
    board = request.form.get('board') 
    grade = request.form.get('grade')
    school = request.form.get('school', '')
    
    if not uid or not purpose or not board or not grade:
        flash('Please fill in all required fields', 'error')
        return redirect(url_for('login'))
    
    try:
        # Get Collab user data
        collab_user = get_collab_user_by_uid(uid)
        if not collab_user:
            flash('Invalid session', 'error')
            return redirect(url_for('login'))
        
        # Create Sclera profile with Collab data (without academic info for now)
        base_profile = initialize_sclera_from_collab(collab_user, {
            'purpose': purpose,
            'school': school  # Only include school name, not the full structure
        })
        
        # Save base profile first
        db.collection('users').document(uid).set(base_profile)
        
        # Set session
        session['uid'] = uid
        session['from_collab'] = True
        session['just_imported'] = True
        session.permanent = True
        
        logger.security_event("collab_user_imported", user_id=uid, ip_address=request.remote_addr)
        
        # Now redirect to appropriate setup flow based on purpose
        if purpose == 'school':
            # Store the board and grade in session for the setup flow
            session['pending_board'] = board
            session['pending_grade'] = grade
            session['pending_school'] = school
            flash('Welcome from ScleraCollab! Please complete your school setup.', 'success')
            return redirect(url_for('setup_highschool'))
        elif purpose == 'exam_prep':
            # For exam prep, we need to collect the exam type
            flash('Welcome from ScleraCollab! Please select your exam type.', 'success')
            return redirect(url_for('setup_exam'))
        else:
            # For other purposes, create a basic structure and go to dashboard
            additional_info = {
                'purpose': purpose,
                'board': board,
                'grade': grade,
                'school': school
            }
            
            # Update with additional info
            sclera_profile = initialize_sclera_from_collab(collab_user, additional_info)
            db.collection('users').document(uid).set(sclera_profile)
            
            flash('Your Sclera profile has been created with your Collab data!', 'success')
            return redirect(url_for('profile_dashboard'))
        
    except Exception as e:
        logger.error("complete_academic_profile_error", error=str(e), uid=uid)
        flash('An error occurred while creating your profile. Please try again.', 'error')
        return redirect(url_for('login'))
@app.route('/student/join/class', methods=['GET', 'POST'])
@require_login
def student_join_class():
    """Student joins a class via multi-use invite code (overlay only)"""
    if request.method == 'POST':
        invite_code = request.form.get('invite_code', '').strip().upper()
        if not invite_code:
            flash('Invite code is required', 'error')
            return render_template('student_join_class.html')
        try:
            # Find class invite
            invite_ref = db.collection('class_invites').document(invite_code).get()
            if not invite_ref.exists:
                flash('Invalid invite code', 'error')
                return render_template('student_join_class.html')
            invite = invite_ref.to_dict()
            if not invite.get('active', False):
                flash('Invite code is no longer active', 'error')
                return render_template('student_join_class.html')
            class_id = invite.get('class_id')
            teacher_id = invite.get('teacher_id')
            institution_id = invite.get('institution_id')
            if not (class_id and teacher_id and institution_id):
                flash('Malformed invite', 'error')
                return render_template('student_join_class.html')
            # Overlay student with institution/class info (no academic data changes)
            uid = session.get('uid')
            user_ref = db.collection('users').document(uid)
            user_ref.update({
                'institution_id': institution_id,
                'class_ids': firestore.ArrayUnion([class_id]),
                'teacher_id': teacher_id
            })
            # Add student to class roster
            class_ref = db.collection('classes').document(class_id)
            class_ref.update({
                'student_uids': firestore.ArrayUnion([uid])
            })
            flash('Successfully joined the class!', 'success')
            return redirect(url_for('profile_dashboard'))
        except Exception as e:
            logger.error("student_join_class_error", error=str(e), invite_code=invite_code)
            flash('An error occurred while joining the class', 'error')
    return render_template('student_join_class.html')
@app.route('/institution/teacher/classes/create', methods=['GET', 'POST'])
@require_teacher_v2
def institution_teacher_create_class():
    """Teacher creates a class and generates multi-use invite code"""
    uid = session.get('uid')
    teacher_profile = _get_any_profile(uid) or {}
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        board = request.form.get('board', '').strip()
        grade = request.form.get('grade', '').strip()
        purpose = request.form.get('purpose', '').strip()
        exam_type = request.form.get('exam_type', '').strip()
        subject_combination = request.form.get('subject_combination', '').strip()
        
        if not name:
            flash('Class name is required', 'error')
            return render_template('institution_teacher_create_class.html', profile=teacher_profile)
        
        if not purpose:
            flash('Purpose selection is required', 'error')
            return render_template('institution_teacher_create_class.html', profile=teacher_profile)
        
        if purpose == 'exam':
            if not exam_type:
                flash('Exam type selection is required for exam preparation', 'error')
                return render_template('institution_teacher_create_class.html', profile=teacher_profile)
            # For exam purpose, board and grade are not required
            board = board or 'Not Applicable'  # Set default value for database
            grade = grade or 'Not Applicable'  # Set default value for database
        elif purpose == 'school':
            if not board:
                flash('Board selection is required for school studies', 'error')
                return render_template('institution_teacher_create_class.html', profile=teacher_profile)
            
            if not grade:
                flash('Grade selection is required for school studies', 'error')
                return render_template('institution_teacher_create_class.html', profile=teacher_profile)
            
            if board == 'CBSE' and grade in ['11', '12'] and not subject_combination:
                flash('Subject combination selection is required for CBSE Class 11-12', 'error')
                return render_template('institution_teacher_create_class.html', profile=teacher_profile)
        
        # For exam purpose, use exam_type as the purpose value
        final_purpose = exam_type if purpose == 'exam' else purpose
        try:
            institution_id = teacher_profile.get('institution_id')
            class_id = str(uuid.uuid4())
            # Create class
            db.collection('classes').document(class_id).set({
                'id': class_id,
                'name': name,
                'board': board,
                'grade': grade,
                'purpose': final_purpose,
                'original_purpose': purpose,  # Store the original purpose for reference
                'exam_type': exam_type if purpose == 'exam' else None,
                'subject_combination': subject_combination if purpose == 'school' and board == 'CBSE' and grade in ['11', '12'] else None,
                'teacher_id': uid,
                'institution_id': institution_id,
                'student_uids': [],
                'created_at': firestore.SERVER_TIMESTAMP
            })
            # Generate multi-use invite code
            invite_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
            db.collection('class_invites').document(invite_code).set({
                'code': invite_code,
                'class_id': class_id,
                'teacher_id': uid,
                'institution_id': institution_id,
                'active': True,
                'created_at': firestore.SERVER_TIMESTAMP
            })
            flash(f'Class created! Invite code: {invite_code}', 'success')
            return redirect(url_for('institution_teacher_dashboard'))
        except Exception as e:
            logger.error("teacher_create_class_error", error=str(e))
            flash('Failed to create class', 'error')
    return render_template('institution_teacher_create_class.html', profile=teacher_profile)
@app.route('/institution/teacher/classes')
@require_teacher_v2
def institution_teacher_classes():
    """List teacher's classes with invite codes and actions"""
    try:
        uid = session.get('uid')
        profile = _get_teacher_profile(uid) or {}
        institution_id = profile.get('institution_id')
        classes = []
        class_docs = db.collection('classes').where('teacher_id', '==', uid).stream()
        for doc in class_docs:
            cls = doc.to_dict()
            cls['uid'] = doc.id
            # Find invite code for this class
            invite = db.collection('class_invites').where('class_id', '==', doc.id).where('active', '==', True).limit(1).get()
            if invite:
                invite = next(iter(invite))
                cls['invite_code'] = invite.get('code')
            classes.append(cls)
        return render_template('institution_teacher_classes.html', profile=profile, classes=classes, institution_id=institution_id)
    except Exception as e:
        logger.error("teacher_list_classes_error", error=str(e))
        flash('Failed to load classes', 'error')
        return redirect(url_for('institution_teacher_dashboard'))

@app.route('/institution/teacher/class/<class_id>/delete', methods=['POST'])
@require_teacher_v2
def delete_class(class_id):
    """Delete a class and all associated data"""
    try:
        uid = session.get('uid')
        profile = _get_teacher_profile(uid) or {}
        institution_id = profile.get('institution_id')
        
        # Verify class belongs to teacher and institution
        class_doc = db.collection('classes').document(class_id).get()
        if not class_doc.exists or class_doc.to_dict().get('teacher_id') != uid or class_doc.to_dict().get('institution_id') != institution_id:
            abort(403)
        
        class_data = class_doc.to_dict()
        class_name = class_data.get('name', 'Class')
        
        # Delete all associated data
        batch = db.batch()
        
        # Delete class document
        batch.delete(db.collection('classes').document(class_id))
        
        # Delete invite codes
        invites = db.collection('class_invites').where('class_id', '==', class_id).stream()
        for invite_doc in invites:
            batch.delete(invite_doc.reference)
        
        # Delete excluded chapters
        batch.delete(db.collection('classes').document(class_id).collection('excluded_chapters').document('current'))
        
        # Remove class ID from all students
        students = class_data.get('student_uids', [])
        for student_uid in students:
            student_doc = db.collection('users').document(student_uid).get()
            if student_doc.exists:
                student_data = student_doc.to_dict()
                current_class_ids = student_data.get('class_ids', [])
                if class_id in current_class_ids:
                    current_class_ids.remove(class_id)
                    batch.update(db.collection('users').document(student_uid), {'class_ids': current_class_ids})
        
        # Commit all deletions
        batch.commit()
        
        flash(f'Class "{class_name}" has been deleted successfully.', 'success')
        return redirect(url_for('institution_teacher_classes'))
        
    except Exception as e:
        logger.error("delete_class_error", error=str(e))
        flash('Failed to delete class', 'error')
        return redirect(url_for('institution_teacher_classes'))
# ============================================================================
# INSTITUTION V2 AUTH (ADMIN / TEACHER)
# ============================================================================
@app.route('/signup/admin', methods=['GET', 'POST'])
def signup_admin():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        institution_name = request.form.get('institution_name', '').strip()
        password = request.form.get('password', '')
        if not name or not email or not institution_name or not password:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('signup_admin'))
        is_strong, msg = PasswordManager.is_strong_password(password)
        if not is_strong:
            flash(f'Password not strong enough: {msg}', 'error')
            return redirect(url_for('signup_admin'))
        try:
            try:
                admin_auth.get_user_by_email(email)
                flash('Email already exists. Please login.', 'error')
                return redirect(url_for('login_admin'))
            except admin_auth.UserNotFoundError:
                pass
            user = admin_auth.create_user(email=email, password=password)
            uid = user.uid
            institution_id = uuid.uuid4().hex
            now = datetime.utcnow().isoformat()
            db.collection(INSTITUTIONS_COL).document(institution_id).set({
                'name': institution_name,
                'created_at': now,
                'created_by': uid,
                'status': 'active',
                'plan': 'Free'
            })
            db.collection(INSTITUTION_ADMINS_COL).document(uid).set({
                'uid': uid,
                'name': name,
                'email': email,
                'phone': phone,
                'institution_id': institution_id,
                'role': 'admin',
                'status': 'active',
                'created_at': now,
                'last_login_at': None,
                'password_hash': PasswordManager.hash_password(password),
            })
            _set_session_identity(uid, 'admin', institution_id=institution_id)
            flash('Admin account created successfully!', 'success')
            return redirect(url_for('institution_admin_dashboard'))
        except Exception as e:
            logger.error("admin_signup_error", error=str(e), email=email)
            flash('Error creating admin account.', 'error')
            return redirect(url_for('signup_admin'))
    return render_template('signup_admin.html')
@app.route('/login/admin', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('login_admin'))
        try:
            user = admin_auth.get_user_by_email(email)
            uid = user.uid
            profile = _get_admin_profile(uid)
            if not profile:
                flash('Invalid admin credentials.', 'error')
                return redirect(url_for('login_admin'))
            if profile.get('status') != 'active':
                flash('Your admin account is disabled.', 'error')
                return redirect(url_for('login_admin'))
            stored_hash = profile.get('password_hash')
            if not stored_hash or not PasswordManager.verify_password(password, stored_hash):
                flash('Invalid admin credentials.', 'error')
                return redirect(url_for('login_admin'))
            institution_id = profile.get('institution_id')
            db.collection(INSTITUTION_ADMINS_COL).document(uid).update({
                'last_login_at': datetime.utcnow().isoformat()
            })
            _set_session_identity(uid, 'admin', institution_id=institution_id)
            flash('Login successful!', 'success')
            return redirect(url_for('institution_admin_dashboard'))
        except admin_auth.UserNotFoundError:
            flash('Invalid admin credentials.', 'error')
            return redirect(url_for('login_admin'))
        except Exception as e:
            logger.error("admin_login_error", error=str(e), email=email)
            flash('Login error.', 'error')
            return redirect(url_for('login_admin'))
    return render_template('login_admin.html')
@app.route('/signup/teacher', methods=['GET', 'POST'])
def signup_teacher():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        if not name or not email or not password:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('signup_teacher'))
        is_strong, msg = PasswordManager.is_strong_password(password)
        if not is_strong:
            flash(f'Password not strong enough: {msg}', 'error')
            return redirect(url_for('signup_teacher'))
        try:
            try:
                admin_auth.get_user_by_email(email)
                flash('Email already exists. Please login.', 'error')
                return redirect(url_for('login_teacher'))
            except admin_auth.UserNotFoundError:
                pass
            user = admin_auth.create_user(email=email, password=password)
            uid = user.uid
            now = datetime.utcnow().isoformat()
            db.collection(INSTITUTION_TEACHERS_COL).document(uid).set({
                'uid': uid,
                'name': name,
                'email': email,
                'phone': phone,
                'institution_id': None,
                'role': 'teacher',
                'status': 'pending',
                'created_at': now,
                'last_login_at': None,
                'password_hash': PasswordManager.hash_password(password),
                'class_ids': [],
            })
            _set_session_identity(uid, 'teacher')
            flash('Teacher account created. Join an institution to activate.', 'success')
            return redirect(url_for('institution_teacher_join'))
        except Exception as e:
            logger.error("teacher_signup_error", error=str(e), email=email)
            flash('Error creating teacher account.', 'error')
            return redirect(url_for('signup_teacher'))
    return render_template('signup_teacher.html')
@app.route('/login/teacher', methods=['GET', 'POST'])
def login_teacher():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('login_teacher'))
        try:
            user = admin_auth.get_user_by_email(email)
            uid = user.uid
            profile = _get_teacher_profile(uid)
            if not profile:
                flash('Invalid teacher credentials.', 'error')
                return redirect(url_for('login_teacher'))
            if profile.get('status') == 'disabled':
                flash('Your teacher account is disabled.', 'error')
                return redirect(url_for('login_teacher'))
            stored_hash = profile.get('password_hash')
            if not stored_hash or not PasswordManager.verify_password(password, stored_hash):
                flash('Invalid teacher credentials.', 'error')
                return redirect(url_for('login_teacher'))
            institution_id = profile.get('institution_id')
            db.collection(INSTITUTION_TEACHERS_COL).document(uid).update({
                'last_login_at': datetime.utcnow().isoformat()
            })
            _set_session_identity(uid, 'teacher', institution_id=institution_id)
            if not institution_id or profile.get('status') != 'active':
                flash('Join an institution to activate your account.', 'info')
                return redirect(url_for('institution_teacher_join'))
            flash('Login successful!', 'success')
            return redirect(url_for('institution_teacher_dashboard'))
        except admin_auth.UserNotFoundError:
            flash('Invalid teacher credentials.', 'error')
            return redirect(url_for('login_teacher'))
        except Exception as e:
            logger.error("teacher_login_error", error=str(e), email=email)
            flash('Login error.', 'error')
            return redirect(url_for('login_teacher'))
    return render_template('login_teacher.html')
@app.route('/institution/teacher/join', methods=['GET', 'POST'])
@require_teacher_v2
def institution_teacher_join():
    uid = session['uid']
    profile = _get_teacher_profile(uid) or {}
    if request.method == 'POST':
        code = request.form.get('invite_code', '').strip().upper()
        if not code:
            flash('Invite code is required.', 'error')
            return redirect(url_for('institution_teacher_join'))
        invite_q = db.collection(TEACHER_INVITES_COL).where('code', '==', code).where('used', '==', False).limit(1)
        invites = list(invite_q.stream())
        if not invites:
            flash('Invalid or expired invite code.', 'error')
            return redirect(url_for('institution_teacher_join'))
        invite_doc = invites[0]
        invite_data = invite_doc.to_dict()
        institution_id = invite_data.get('institution_id')
        batch = db.batch()
        batch.update(invite_doc.reference, {
            'used': True,
            'used_by': uid,
            'used_at': datetime.utcnow().isoformat()
        })
        batch.update(db.collection(INSTITUTION_TEACHERS_COL).document(uid), {
            'institution_id': institution_id,
            'status': 'active'
        })
        batch.commit()
        _set_session_identity(uid, 'teacher', institution_id=institution_id)
        flash('Successfully joined institution!', 'success')
        return redirect(url_for('institution_teacher_dashboard'))
    return render_template('institution_teacher_join.html', profile=profile)
@app.route('/institution/admin/dashboard')
@require_admin_v2
def institution_admin_dashboard():
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id') or session.get('institution_id')
    inst_doc = db.collection(INSTITUTIONS_COL).document(institution_id).get() if institution_id else None
    institution = inst_doc.to_dict() if inst_doc and inst_doc.exists else {}
    teachers_ref = db.collection(INSTITUTION_TEACHERS_COL).where('institution_id', '==', institution_id)
    teachers = []
    for t in teachers_ref.stream():
        d = t.to_dict()
        d['uid'] = t.id
        teachers.append(d)
    students_ref = db.collection('users').where('institution_id', '==', institution_id)
    students = []
    for s in students_ref.stream():
        d = s.to_dict()
        d['uid'] = s.id
        students.append(d)
    # Analytics (Heatmap + Predictive Risk)
    analytics = _get_institution_analytics(institution_id)
    context = {
        'profile': admin_profile,
        'institution': institution,
        'institution_id': institution_id,
        'teachers': teachers,
        'students': students,
        'heatmap_data': analytics['heatmap'],
        'at_risk_students': analytics['at_risk']
    }
    return render_template('institution_admin_dashboard.html', **context)
@app.route('/institution/admin/teacher_invite', methods=['POST'])
@require_admin_v2
def institution_admin_create_teacher_invite():
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')
    code = _generate_code(8)
    db.collection(TEACHER_INVITES_COL).add({
        'code': code,
        'institution_id': institution_id,
        'created_by': uid,
        'created_at': datetime.utcnow().isoformat(),
        'used': False,
        'used_by': None,
        'used_at': None,
        'one_time': True
    })
    flash(f'Teacher invite code generated: {code}', 'success')
    return redirect(url_for('institution_admin_dashboard'))
@app.route('/institution/admin/teachers/<teacher_uid>/disable', methods=['POST'])
@require_admin_v2
def institution_admin_disable_teacher(teacher_uid):
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')
    t_doc = db.collection(INSTITUTION_TEACHERS_COL).document(teacher_uid).get()
    if not t_doc.exists:
        abort(404)
    t = t_doc.to_dict()
    if t.get('institution_id') != institution_id:
        abort(403)
    db.collection(INSTITUTION_TEACHERS_COL).document(teacher_uid).update({'status': 'disabled'})
    try:
        admin_auth.update_user(teacher_uid, disabled=True)
    except Exception:
        pass
    flash('Teacher disabled.', 'success')
    return redirect(url_for('institution_admin_dashboard'))
@app.route('/institution/admin/teachers/<teacher_uid>/delete', methods=['POST'])
@require_admin_v2
def institution_admin_delete_teacher(teacher_uid):
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')
    t_doc = db.collection(INSTITUTION_TEACHERS_COL).document(teacher_uid).get()
    if not t_doc.exists:
        abort(404)
    t = t_doc.to_dict()
    if t.get('institution_id') != institution_id:
        abort(403)
    # Soft-delete by default (keep auth but disable); profile removed.
    try:
        admin_auth.update_user(teacher_uid, disabled=True)
    except Exception:
        pass
    db.collection(INSTITUTION_TEACHERS_COL).document(teacher_uid).delete()
    flash('Teacher deleted.', 'success')
    return redirect(url_for('institution_admin_dashboard'))
@app.route('/institution/admin/students/<student_uid>/remove', methods=['POST'])
@require_admin_v2
def institution_admin_remove_student(student_uid):
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')
    s_doc = db.collection('users').document(student_uid).get()
    if not s_doc.exists:
        abort(404)
    s = s_doc.to_dict()
    if s.get('institution_id') != institution_id:
        abort(403)
    # Remove overlay links; do NOT touch academic progress
    class_ids = s.get('class_ids', []) or []
    batch = db.batch()
    batch.update(db.collection('users').document(student_uid), {
        'institution_id': None,
        'class_ids': [],
        'role': 'student'
    })
    for cid in class_ids:
        batch.update(db.collection(CLASSES_COL).document(cid), {
            'students': firestore.ArrayRemove([student_uid])
        })
    batch.commit()
    flash('Student removed from institution (personal dashboard preserved).', 'success')
    return redirect(url_for('institution_admin_dashboard'))
@app.route('/institution/admin/students/<student_uid>/delete', methods=['POST'])
@require_admin_v2
def institution_admin_delete_student(student_uid):
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')
    s_doc = db.collection('users').document(student_uid).get()
    if not s_doc.exists:
        abort(404)
    s = s_doc.to_dict()
    if s.get('institution_id') != institution_id:
        abort(403)
    # Hard delete = disable auth + remove user doc (this WILL delete academic data)
    try:
        admin_auth.update_user(student_uid, disabled=True)
    except Exception:
        pass
    db.collection('users').document(student_uid).delete()
    flash('Student deleted (account disabled).', 'success')
    return redirect(url_for('institution_admin_dashboard'))
@app.route('/institution/teacher/dashboard')
@require_teacher_v2
def institution_teacher_dashboard():
    uid = session['uid']
    profile = _get_teacher_profile(uid) or {}
    institution_id = profile.get('institution_id')
    if not institution_id or profile.get('status') != 'active':
        return redirect(url_for('institution_teacher_join'))
    classes_ref = db.collection(CLASSES_COL).where('institution_id', '==', institution_id).where('teacher_id', '==', uid)
    classes = []
    # Fetch invite codes for the dashboard view as well
    for c in classes_ref.stream():
        cls_data = c.to_dict()
        cls_data['id'] = c.id
        # Find invite code for this class
        invite = db.collection('class_invites').where('class_id', '==', c.id).where('active', '==', True).limit(1).get()
        if invite:
            invite_doc = next(iter(invite))
            cls_data['invite_code'] = invite_doc.get('code')
        classes.append(cls_data)
    # Analytics (Heatmap + Predictive Risk) for the teacher's classes
    class_ids = [c['id'] for c in classes]
    analytics = _get_institution_analytics(institution_id, class_ids=class_ids)
    return render_template('institution_teacher_dashboard.html', 
                           profile=profile, 
                           classes=classes, 
                           institution_id=institution_id,
                           heatmap_data=analytics['heatmap'],
                           at_risk_students=analytics['at_risk'])
@app.route('/institution/teacher/class/<class_id>/upload', methods=['GET', 'POST'])
@require_teacher_v2
def institution_teacher_upload_file(class_id):
    uid = session['uid']
    profile = _get_teacher_profile(uid) or {}
    # Check if teacher owns the class
    class_doc = db.collection('classes').document(class_id).get()
    if not class_doc.exists or class_doc.to_dict().get('teacher_id') != uid:
        flash('Unauthorized', 'error')
        return redirect(url_for('institution_teacher_dashboard'))
    if request.method == 'POST':
        try:
            file = request.files.get('file')
            if not file or file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
            filename = secure_filename(file.filename)
            file_id = str(uuid.uuid4())
            # Save to local storage
            upload_folder = os.path.join(app.root_path, 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            file_path = os.path.join(upload_folder, f'{file_id}_{filename}')
            file.save(file_path)
            # Get actual file size
            file_size = os.path.getsize(file_path)
            file_url = url_for('serve_upload', filename=f'{file_id}_{filename}')
            # Save to Firestore
            db.collection('class_files').document(file_id).set({
                'id': file_id,
                'class_id': class_id,
                'file_name': filename,
                'file_url': file_url,
                'uploaded_by': uid,
                'upload_date': datetime.utcnow().isoformat(),
                'file_type': 'notes',
                'file_size': file_size
            })
            flash('File uploaded successfully', 'success')
            return redirect(url_for('institution_teacher_dashboard'))
        except Exception as e:
            logger.error(f"File upload error: {str(e)}")
            flash('An error occurred while uploading the file', 'error')
            return redirect(request.url)
    # GET: render upload form
    class_data = class_doc.to_dict()
    return render_template('institution_teacher_upload.html', class_id=class_id, class_name=class_data.get('name'), profile=profile)
@app.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded files from local storage"""
    try:
        return send_from_directory(
            os.path.join(app.root_path, 'uploads'),
            filename
        )
    except FileNotFoundError:
        abort(404)
@app.route('/profile_banners/<filename>')
def serve_profile_banner(filename):
    """Serve profile banners from local storage"""
    try:
        return send_from_directory(
            os.path.join(app.root_path, 'static', 'profile_banners'),
            filename
        )
    except FileNotFoundError:
        # Return default banner or 404
        return '', 404
# ============================================================================
# MAIN DASHBOARD
# ============================================================================
@app.route('/dashboard')
@app.route('/profile')
@require_login
def profile_dashboard():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    purpose = user_data.get('purpose')
    academic_summary = ''
    if purpose == 'school' and user_data.get('school'):
        school = user_data['school']
        academic_summary = f"{school.get('board', '')} – Grade {school.get('grade', '')}"
    elif purpose == 'exam' and user_data.get('exam'):
        academic_summary = f"{user_data['exam'].get('type', '')} Preparation"
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        academic_summary = f"{at.get('stream', '')} – Grade {at.get('grade', '')}"
    progress_data = calculate_academic_progress(user_data)
    # Get user's saved career interests for the interests island
    interests = user_data.get('interests', {})
    if isinstance(interests, list):
        interests = {'careers': [], 'courses': [], 'internships': []}
    saved_career_ids = interests.get('careers', [])
    saved_careers = [get_career_by_id(cid) for cid in saved_career_ids if get_career_by_id(cid)]
    # NEW: Fetch upcoming calendar events for widget
    upcoming_events = []
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        week_later = today + timedelta(days=7)
        # Fix: Fetch events specifically for this user
        events_ref = db.collection('calendar_events').where('uid', '==', uid).stream()
        for doc in events_ref:
            event_data = doc.to_dict()
            event_data['id'] = doc.id
            # Normalize date for sorting and display
            s_date = event_data.get('start_date') or event_data.get('start')
            if s_date:
                try:
                    if isinstance(s_date, str):
                        dt = datetime.fromisoformat(s_date.replace('Z', '+00:00'))
                    else:
                        dt = s_date
                    if today <= dt.replace(tzinfo=None) <= week_later:
                        event_data['display_date'] = dt.strftime('%Y-%m-%d')
                        upcoming_events.append(event_data)
                except: pass
        upcoming_events.sort(key=lambda x: str(x.get('start_date') or x.get('start') or ''))
        upcoming_events = upcoming_events[:5]
    except Exception as e:
        logger.error(f"Fetch upcoming events error: {str(e)}")
    # NEW: Get performance metrics
    performance_data = {'average': 0, 'last': 0, 'highest': 0, 'readiness': 0}
    try:
        results = user_data.get('exam_results', [])
        if results:
            # Fix: use percentage if available, else calculate from score
            scores = []
            for r in results:
                if 'percentage' in r:
                    scores.append(float(r['percentage']))
                elif r.get('max_score'):
                    scores.append(float(r['score'] / r['max_score'] * 100))
            if scores:
                performance_data['average'] = round(sum(scores) / len(scores), 1)
                performance_data['last'] = round(scores[-1], 1)
                performance_data['highest'] = round(max(scores), 1)
        
        # Calculate readiness using existing function
        progress_data = calculate_academic_progress(user_data)
        performance_data['readiness'] = round(progress_data.get('readiness', 0), 1)
    except Exception as e:
        logger.error(f"Calculate performance error: {str(e)}")
    # NEW: Get study time data (last 7 days)
    study_time_data = []
    try:
        daily_totals = defaultdict(int)
        sessions_ref = db.collection('users').document(uid).collection('study_sessions').stream()
        for doc in sessions_ref:
            session_data = doc.to_dict()
            session_start = session_data.get('start_time', '')
            if session_start:
                date_part = session_start.split('T')[0]
                daily_totals[date_part] += session_data.get('duration_seconds', 0) // 60
        today = datetime.now()
        for i in range(6, -1, -1):
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            study_time_data.append({
                'date': date,
                'minutes': daily_totals.get(date, 0)
            })
    except Exception as e:
        logger.error(f"Fetch study time error: {str(e)}")
    # NEW: Get totals
    totals_data = {'total_goals': 0, 'completed_goals': 0, 'total_tasks': 0, 'completed_tasks': 0, 'total_study_time': 0}
    try:
        goals = user_data.get('goals', [])
        totals_data['total_goals'] = len(goals) if isinstance(goals, list) else 0
        totals_data['completed_goals'] = sum(1 for g in goals if isinstance(g, dict) and g.get('completed', False)) if isinstance(goals, list) else 0
        tasks = user_data.get('tasks', [])
        totals_data['total_tasks'] = len(tasks) if isinstance(tasks, list) else 0
        totals_data['completed_tasks'] = sum(1 for t in tasks if isinstance(t, dict) and t.get('completed', False)) if isinstance(tasks, list) else 0
        
        # Calculate total study time in hours
        total_minutes = user_data.get('time_studied', 0)
        totals_data['total_study_time'] = round(total_minutes / 60, 1) if total_minutes > 0 else 0
    except Exception as e:
        logger.error(f"Calculate totals error: {str(e)}")
    # NEW: Get incomplete tasks
    recent_tasks = []
    try:
        tasks = user_data.get('tasks', [])
        if isinstance(tasks, list):
            recent_tasks = [t for t in tasks if isinstance(t, dict) and not t.get('completed', False)][:5]
    except: pass
    context = {
        'user': user_data,
        'email': user_data.get('email', 'N/A'),
        'name': user_data.get('name', 'Student'),
        'purpose': purpose,
        'purpose_display': (purpose or '').replace('_', ' ').title(),
        'academic_summary': academic_summary,
        'progress_data': progress_data,
        'overall_progress': progress_data.get('overall', 0),
        'subject_progress': progress_data.get('by_subject', {}),
        'chapters_by_subject': progress_data.get('chapters_by_subject', {}),
        'total_chapters': progress_data.get('total_chapters', 0),
        'completed_chapters': progress_data.get('total_completed', 0),
        'saved_careers': saved_careers,
        'streak': user_data.get('login_streak', 0),
        'profile_picture': user_data.get('profile_picture'),
        'settings': user_data.get('settings', {}),
        'in_institution': bool(user_data.get('institution_id')),
        'has_class': bool(user_data.get('class_ids')),
        # NEW: Dashboard data for new islands
        'upcoming_events': upcoming_events,
        'performance_data': performance_data,
        'study_time_data': study_time_data,
        'totals_data': totals_data,
        'recent_tasks': recent_tasks
    }
    return render_template('main_dashboard.html', **context)
@app.route('/student/class/files', methods=['GET'])
@require_login
def student_files():
    uid = session['uid']
    user_data = get_user_data(uid)
    class_ids = user_data.get('class_ids', [])
    if not class_ids:
        flash('You need to join a class to access class files.', 'info')
        return redirect(url_for('profile_dashboard'))
    files = []
    for class_id in class_ids:
        class_files = db.collection('class_files').where('class_id', '==', class_id).stream()
        for f in class_files:
            f_data = f.to_dict()
            # Add class name
            class_doc = db.collection('classes').document(class_id).get()
            class_name = class_doc.to_dict().get('name', 'Unknown') if class_doc.exists else 'Unknown'
            f_data['class_name'] = class_name
            files.append(f_data)
    # Group by class
    from collections import defaultdict
    grouped_files = defaultdict(list)
    for f in files:
        grouped_files[f['class_name']].append(f)
    return render_template('student_class_files.html', grouped_files=grouped_files, settings=user_data.get('settings', {}))
@app.route('/student/class/management')
@require_login
def class_management():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('profile_dashboard'))
    institution_id = user_data.get('institution_id')
    class_ids = user_data.get('class_ids', [])
    if not institution_id or not class_ids:
        flash('You need to be in an institution and class to access class management.', 'info')
        return redirect(url_for('profile_dashboard'))
    institution_doc = db.collection('institutions').document(institution_id).get()
    institution_name = institution_doc.to_dict().get('name', 'Unknown') if institution_doc.exists else 'Unknown'
    classes_info = []
    for class_id in class_ids:
        class_doc = db.collection('classes').document(class_id).get()
        if not class_doc.exists:
            continue
        class_data = class_doc.to_dict()
        teacher_uid = class_data.get('teacher_id')
        teacher_profile = _get_teacher_profile(teacher_uid) if teacher_uid else None
        # Fetch files for this class
        files = []
        class_files = db.collection('class_files').where('class_id', '==', class_id).stream()
        for f in class_files:
            f_data = f.to_dict()
            files.append(f_data)
        classes_info.append({
            'id': class_id,
            'name': class_data.get('name', 'Unknown'),
            'teacher_name': teacher_profile.get('name', 'Unknown') if teacher_profile else 'Unknown',
            'institution_name': institution_name,
            'files': files
        })
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'settings': user_data.get('settings', {}),
        'classes_info': classes_info,
        'in_institution': True,
        'has_class': True
    }
    return render_template('class_management.html', **context)
@app.route('/student/class/leave/<class_id>', methods=['POST'])
@require_login
def leave_class(class_id):
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('profile_dashboard'))
    class_ids = user_data.get('class_ids', [])
    if class_id not in class_ids:
        flash('You are not enrolled in this class.', 'error')
        return redirect(url_for('class_management'))
    # Remove the class_id from user's class_ids
    db.collection('users').document(uid).update({
        'class_ids': firestore.ArrayRemove([class_id])
    })
    flash('You have successfully left the class.', 'success')
    return redirect(url_for('class_management'))
@app.route('/download/class_file/<file_id>', methods=['GET'])
@require_login
def download_class_file(file_id):
    file_doc = db.collection('class_files').document(file_id).get()
    if not file_doc.exists:
        abort(404)
    file_data = file_doc.to_dict()
    class_id = file_data['class_id']
    uid = session['uid']
    user_data = get_user_data(uid)
    if class_id not in user_data.get('class_ids', []):
        abort(403)
    # Redirect to file_url
    return redirect(file_data['file_url'])
# ============================================================================
# CALENDAR SYSTEM
# ============================================================================
@app.route('/calendar')
@require_login
def calendar_dashboard():
    """Main calendar dashboard view"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    context = {
        'user': user_data,
        'name': user_data.get('name', 'Student'),
        'settings': user_data.get('settings', {}),
        'in_institution': bool(user_data.get('institution_id')) if user_data else False,
        'has_class': bool(user_data.get('class_ids')) if user_data else False
    }
    return render_template('calendar_dashboard.html', **context)

@app.route('/api/syllabus', methods=['GET'])
def get_syllabus_api():
    """Get syllabus data based on purpose, board/exam, and grade"""
    try:
        purpose = request.args.get('purpose')
        board = request.args.get('board')
        exam = request.args.get('exam')
        grade = request.args.get('grade')
        subject_combination = request.args.get('subject_combination')
        
        if not purpose:
            return jsonify({'error': 'Purpose parameter is required'}), 400
        
        if purpose == 'school' and (not board or not grade):
            return jsonify({'error': 'Board and grade parameters required for school purpose'}), 400
        
        if purpose == 'exam' and not exam:
            return jsonify({'error': 'Exam parameter required for exam purpose'}), 400
        
        # Get syllabus data
        if purpose == 'school':
            syllabus = get_syllabus('school', board, grade, subject_combination=subject_combination)
        elif purpose == 'exam':
            syllabus = get_syllabus('exam', exam)
        else:
            return jsonify({'error': 'Invalid purpose'}), 400
        
        return jsonify(syllabus)
        
    except Exception as e:
        logger.error(f"Get syllabus API error: {str(e)}")
        return jsonify({'error': 'Failed to fetch syllabus data'}), 500

@app.route('/api/test', methods=['GET'])
def test_api():
    """Test endpoint to verify API is working"""
    return jsonify({'message': 'API is working', 'timestamp': datetime.now().isoformat()})

@app.route('/api/calendar/events', methods=['GET'])
@require_login
def get_calendar_events():
    """Get all calendar events for the logged-in user"""
    uid = session['uid']
    try:
        # Get date range from query params (optional)
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        events_ref = db.collection('calendar_events').where('uid', '==', uid)
        events = []
        for doc in events_ref.stream():
            event_data = doc.to_dict()
            event_data['id'] = doc.id
            # Convert Firestore timestamps to ISO strings for FullCalendar
            if 'start_date' in event_data and event_data['start_date']:
                event_data['start'] = event_data['start_date'].isoformat() if hasattr(event_data['start_date'], 'isoformat') else event_data['start_date']
            if 'end_date' in event_data and event_data['end_date']:
                event_data['end'] = event_data['end_date'].isoformat() if hasattr(event_data['end_date'], 'isoformat') else event_data['end_date']
            events.append(event_data)
        return jsonify({'events': events})
    except Exception as e:
        logger.error(f"Get calendar events error: {str(e)}")
        return jsonify({'error': 'Failed to fetch events'}), 500
@app.route('/api/calendar/events', methods=['POST'])
@require_login
def create_calendar_event():
    """Create a new calendar event"""
    _institution_login_guard()
    uid = session['uid']
    try:
        data = request.get_json()
        # Validate required fields
        if not data.get('title'):
            return jsonify({'error': 'Title is required'}), 400
        # Event type color mapping
        color_map = {
            'assignment': '#3b82f6',  # blue
            'exam': '#ef4444',        # red
            'meeting': '#22c55e',     # green
            'class': '#f59e0b',       # amber
            'task': '#8b5cf6',        # purple
            'other': '#6b7280'        # gray
        }
        event_type = data.get('event_type', 'other')
        event_id = str(uuid.uuid4())
        event_data = {
            'id': event_id,
            'uid': uid,
            'title': data.get('title'),
            'description': data.get('description', ''),
            'event_type': event_type,
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
            'all_day': data.get('all_day', False),
            'color': color_map.get(event_type, '#6b7280'),
            'linked_task_id': data.get('linked_task_id'),
            'linked_chapter_id': data.get('linked_chapter_id'),
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        db.collection('calendar_events').document(event_id).set(event_data)
        return jsonify({'success': True, 'event': event_data, 'id': event_id})
    except Exception as e:
        logger.error(f"Create calendar event error: {str(e)}")
        return jsonify({'error': 'Failed to create event'}), 500
@app.route('/api/calendar/events/<event_id>', methods=['PUT'])
@require_login
def update_calendar_event(event_id):
    """Update an existing calendar event"""
    _institution_login_guard()
    uid = session['uid']
    try:
        # Verify event belongs to user
        event_doc = db.collection('calendar_events').document(event_id).get()
        if not event_doc.exists:
            return jsonify({'error': 'Event not found'}), 404
        event_data = event_doc.to_dict()
        if event_data.get('uid') != uid:
            return jsonify({'error': 'Unauthorized'}), 403
        data = request.get_json()
        # Update fields
        update_data = {
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        if 'title' in data:
            update_data['title'] = data['title']
        if 'description' in data:
            update_data['description'] = data['description']
        if 'event_type' in data:
            update_data['event_type'] = data['event_type']
        if 'start_date' in data:
            update_data['start_date'] = data['start_date']
        if 'end_date' in data:
            update_data['end_date'] = data['end_date']
        if 'all_day' in data:
            update_data['all_day'] = data['all_day']
        db.collection('calendar_events').document(event_id).update(update_data)
        return jsonify({'success': True, 'message': 'Event updated'})
    except Exception as e:
        logger.error(f"Update calendar event error: {str(e)}")
        return jsonify({'error': 'Failed to update event'}), 500
@app.route('/api/calendar/events/<event_id>', methods=['DELETE'])
@require_login
def delete_calendar_event(event_id):
    """Delete a calendar event"""
    _institution_login_guard()
    uid = session['uid']
    try:
        # Verify event belongs to user
        event_doc = db.collection('calendar_events').document(event_id).get()
        if not event_doc.exists:
            return jsonify({'error': 'Event not found'}), 404
        event_data = event_doc.to_dict()
        if event_data.get('uid') != uid:
            return jsonify({'error': 'Unauthorized'}), 403
        db.collection('calendar_events').document(event_id).delete()
        return jsonify({'success': True, 'message': 'Event deleted'})
    except Exception as e:
        logger.error(f"Delete calendar event error: {str(e)}")
        return jsonify({'error': 'Failed to delete event'}), 500
@app.route('/api/calendar/events/<event_id>/move', methods=['POST'])
@require_login
def move_calendar_event(event_id):
    """Move event to new date/time (drag-and-drop support)"""
    _institution_login_guard()
    uid = session['uid']
    try:
        # Verify event belongs to user
        event_doc = db.collection('calendar_events').document(event_id).get()
        if not event_doc.exists:
            return jsonify({'error': 'Event not found'}), 404
        event_data = event_doc.to_dict()
        if event_data.get('uid') != uid:
            return jsonify({'error': 'Unauthorized'}), 403
        data = request.get_json()
        update_data = {
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        db.collection('calendar_events').document(event_id).update(update_data)
        return jsonify({'success': True, 'message': 'Event moved'})
    except Exception as e:
        logger.error(f"Move calendar event error: {str(e)}")
        return jsonify({'error': 'Failed to move event'}), 500
# ============================================================================
# STUDY SESSIONS
# ============================================================================
@app.route('/api/study_sessions', methods=['GET'])
@require_login
def get_study_sessions():
    """Get study sessions for graphs"""
    _institution_login_guard()
    uid = session['uid']
    try:
        # Get last 30 days by default
        days = int(request.args.get('days', 30))
        sessions_ref = db.collection('study_sessions').where('uid', '==', uid).order_by('session_date', direction=firestore.Query.DESCENDING).limit(days)
        sessions = []
        for doc in sessions_ref.stream():
            session_data = doc.to_dict()
            session_data['id'] = doc.id
            sessions.append(session_data)
        return jsonify({'sessions': sessions})
    except Exception as e:
        logger.error(f"Get study sessions error: {str(e)}")
        return jsonify({'error': 'Failed to fetch study sessions'}), 500
@app.route('/api/study_sessions', methods=['POST'])
@require_login
def log_study_session():
    """Log a new study session"""
    _institution_login_guard()
    uid = session['uid']
    try:
        data = request.get_json()
        session_id = str(uuid.uuid4())
        session_data = {
            'id': session_id,
            'uid': uid,
            'subject': data.get('subject', 'General'),
            'duration_minutes': int(data.get('duration_minutes', 0)),
            'session_date': data.get('session_date', datetime.utcnow().isoformat()),
            'created_at': firestore.SERVER_TIMESTAMP
        }
        db.collection('study_sessions').document(session_id).set(session_data)
        return jsonify({'success': True, 'session': session_data})
    except Exception as e:
        logger.error(f"Log study session error: {str(e)}")
        return jsonify({'error': 'Failed to log study session'}), 500
# ============================================================================
# DASHBOARD DATA APIs
# ============================================================================
@app.route('/api/dashboard/performance')
@require_login
def get_dashboard_performance():
    """Get exam performance metrics for dashboard"""
    _institution_login_guard()
    uid = session['uid']
    try:
        user_data = get_user_data(uid)
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        # Get exam results
        results = user_data.get('results', {})
        if not results:
            return jsonify({
                'average': 0,
                'last': 0,
                'highest': 0,
                'total_exams': 0
            })
        # Calculate metrics
        scores = []
        for exam_type, subjects in results.items():
            if isinstance(subjects, dict):
                for subject, data in subjects.items():
                    if isinstance(data, dict) and 'percentage' in data:
                        scores.append(float(data['percentage']))
        if not scores:
            return jsonify({
                'average': 0,
                'last': 0,
                'highest': 0,
                'total_exams': 0
            })
        average = sum(scores) / len(scores)
        last = scores[-1] if scores else 0
        highest = max(scores)
        return jsonify({
            'average': round(average, 1),
            'last': round(last, 1),
            'highest': round(highest, 1),
            'total_exams': len(scores)
        })
    except Exception as e:
        logger.error(f"Get dashboard performance error: {str(e)}")
        return jsonify({'error': 'Failed to fetch performance data'}), 500
@app.route('/api/dashboard/study_time')
@require_login
def get_dashboard_study_time():
    """Get study time data for graphs"""
    _institution_login_guard()
    uid = session['uid']
    try:
        # Get last 7 days of study sessions
        sessions_ref = db.collection('study_sessions').where('uid', '==', uid).order_by('session_date', direction=firestore.Query.DESCENDING).limit(30)
        # Aggregate by date
        from collections import defaultdict
        daily_totals = defaultdict(int)
        for doc in sessions_ref.stream():
            session_data = doc.to_dict()
            session_date = session_data.get('session_date', '')
            # Extract date part (YYYY-MM-DD)
            if isinstance(session_date, str):
                date_part = session_date.split('T')[0]
            else:
                date_part = datetime.now().strftime('%Y-%m-%d')
            daily_totals[date_part] += session_data.get('duration_minutes', 0)
        # Get last 7 days
        today = datetime.now()
        last_7_days = []
        for i in range(6, -1, -1):
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            last_7_days.append({
                'date': date,
                'minutes': daily_totals.get(date, 0)
            })
        total_week = sum(day['minutes'] for day in last_7_days)
        return jsonify({
            'daily': last_7_days,
            'total_week_hours': round(total_week / 60, 1)
        })
    except Exception as e:
        logger.error(f"Get dashboard study time error: {str(e)}")
        return jsonify({'error': 'Failed to fetch study time data'}), 500
@app.route('/api/dashboard/totals')
@require_login
def get_dashboard_totals():
    """Get totals for goals and tasks"""
    _institution_login_guard()
    uid = session['uid']
    try:
        user_data = get_user_data(uid)
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        # Count goals
        goals = user_data.get('goals', [])
        total_goals = len(goals) if isinstance(goals, list) else 0
        completed_goals = sum(1 for g in goals if isinstance(g, dict) and g.get('completed', False)) if isinstance(goals, list) else 0
        # Count tasks
        tasks = user_data.get('tasks', [])
        total_tasks = len(tasks) if isinstance(tasks, list) else 0
        completed_tasks = sum(1 for t in tasks if isinstance(t, dict) and t.get('completed', False)) if isinstance(tasks, list) else 0
        return jsonify({
            'total_goals': total_goals,
            'completed_goals': completed_goals,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks
        })
    except Exception as e:
        logger.error(f"Get dashboard totals error: {str(e)}")
        return jsonify({'error': 'Failed to fetch totals'}), 500
@app.route('/api/dashboard/upcoming_events')
@require_login
def get_upcoming_events():
    """Get upcoming calendar events for widget (next 7 days)"""
    _institution_login_guard()
    uid = session['uid']
    try:
        # Get events from today onwards
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        week_later = today + timedelta(days=7)
        events_ref = db.collection('calendar_events').where('uid', '==', uid)
        upcoming = []
        for doc in events_ref.stream():
            event_data = doc.to_dict()
            event_data['id'] = doc.id
            # Parse start_date
            start_date_str = event_data.get('start_date', '')
            if start_date_str:
                try:
                    if isinstance(start_date_str, str):
                        event_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                    else:
                        event_date = start_date_str
                    # Check if within next 7 days
                    if today <= event_date <= week_later:
                        upcoming.append(event_data)
                except:
                    pass
        # Sort by date
        upcoming.sort(key=lambda x: x.get('start_date', ''))
        return jsonify({'events': upcoming[:10]})  # Limit to 10
    except Exception as e:
        logger.error(f"Get upcoming events error: {str(e)}")
        return jsonify({'error': 'Failed to fetch upcoming events'}), 500
# ============================================================================
# AI ASSISTANT
# ============================================================================
@app.route('/ai-assistant')
@require_login
def ai_assistant():
    """AI Assistant main page with consent check"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    # TEMPORARILY BYPASS CONSENT CHECK FOR DEBUGGING
    # Check if user has consented to AI features
    # ai_consent = user_data.get('ai_consent', False)
    # if not ai_consent:
    #     # Show consent screen
    #     return render_template('ai_consent.html', user=user_data)
    # Show AI assistant interface (force consent for debugging)
    ai_consent = True  # Force consent for debugging
    context = {
        'user': user_data,
        'name': user_data.get('name', 'Student'),
        'ai_consent': ai_consent,
        'settings': user_data.get('settings', {}),
        'in_institution': bool(user_data.get('institution_id')),
        'has_class': bool(user_data.get('class_ids'))
    }
    return render_template('ai_assistant.html', **context)
@app.route('/ai-assistant/consent', methods=['POST'])
@require_login
def ai_assistant_consent():
    """Handle AI consent decision"""
    uid = session['uid']
    consent = request.form.get('consent') == 'yes'
    if consent:
        # Update user with consent
        db.collection('users').document(uid).update({'ai_consent': True})
        flash('AI Assistant enabled! You can now use AI-powered academic planning and doubt resolution.', 'success')
    else:
        flash('AI Assistant access denied. You can enable it later from your profile.', 'info')
    return redirect(url_for('profile_dashboard'))
@app.route('/api/ai/chat/planning', methods=['POST'])
@require_login
def ai_chat_planning():
    """API endpoint for planning chatbot"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    # Check consent
    # TEMPORARILY BYPASS CONSENT CHECK FOR DEBUGGING
    # if not user_data.get('ai_consent', False):
    #     return jsonify({'error': 'AI consent required'}), 403
    message = request.json.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Message required'}), 400
    try:
        ai = get_ai_assistant()
        academic_context = ai.get_academic_context(user_data)
        # Save user message
        ai.save_message(uid, 'planning', 'user', message)
        response = ai.generate_planning_response(message, academic_context)
        # Save AI response
        ai.save_message(uid, 'planning', 'assistant', response)
        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"AI planning chat error: {str(e)}")
        return jsonify({'error': 'AI service temporarily unavailable'}), 500
@app.route('/api/ai/chat/doubt', methods=['POST'])
@require_login
def ai_chat_doubt():
    """API endpoint for doubt resolution chatbot"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    # Check consent
    # TEMPORARILY BYPASS CONSENT CHECK FOR DEBUGGING
    # if not user_data.get('ai_consent', False):
    #     return jsonify({'error': 'AI consent required'}), 403
    message = request.json.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Message required'}), 400
    try:
        ai = get_ai_assistant()
        academic_context = ai.get_academic_context(user_data)
        # Save user message
        ai.save_message(uid, 'doubt', 'user', message)
        response = ai.generate_doubt_response(message, academic_context)
        # Save AI response
        ai.save_message(uid, 'doubt', 'assistant', response)
        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"AI doubt chat error: {str(e)}")
        return jsonify({'error': 'AI service temporarily unavailable'}), 500
@app.route('/api/ai/chat/history/<chatbot_type>', methods=['GET'])
@require_login
def get_chat_history(chatbot_type):
    """Get conversation history for a specific chatbot type (active thread)"""
    uid = session['uid']
    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400
    try:
        ai = get_ai_assistant()
        history = ai.get_conversation_history(uid, chatbot_type)
        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"Error loading chat history: {str(e)}")
        return jsonify({'error': 'Failed to load conversation history'}), 500
@app.route('/api/ai/threads/<chatbot_type>', methods=['GET'])
@require_login
def get_threads(chatbot_type):
    """Get all conversation threads for a chatbot type"""
    uid = session['uid']
    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400
    try:
        ai = get_ai_assistant()
        threads = ai.get_user_threads(uid, chatbot_type)
        active_thread_id = ai.get_active_thread_id(uid, chatbot_type)
        return jsonify({
            'threads': threads,
            'active_thread_id': active_thread_id
        })
    except Exception as e:
        logger.error(f"Error loading threads: {str(e)}")
        return jsonify({'error': 'Failed to load threads'}), 500
@app.route('/api/ai/threads/<chatbot_type>/create', methods=['POST'])
@require_login
def create_thread(chatbot_type):
    """Create a new conversation thread"""
    uid = session['uid']
    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400
    title = request.json.get('title', f'New {chatbot_type.title()} Conversation')
    try:
        ai = get_ai_assistant()
        thread_id = ai.create_new_thread(uid, chatbot_type, title)
        if thread_id:
            return jsonify({
                'success': True,
                'thread_id': thread_id,
                'title': title
            })
        else:
            return jsonify({'error': 'Failed to create thread'}), 500
    except Exception as e:
        logger.error(f"Error creating thread: {str(e)}")
        return jsonify({'error': 'Failed to create thread'}), 500
@app.route('/api/ai/threads/<chatbot_type>/<thread_id>/switch', methods=['POST'])
@require_login
def switch_thread(chatbot_type, thread_id):
    """Switch active thread for a chatbot type"""
    uid = session['uid']
    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400
    try:
        ai = get_ai_assistant()
        success = ai.switch_thread(uid, chatbot_type, thread_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Thread not found or invalid'}), 404
    except Exception as e:
        logger.error(f"Error switching thread: {str(e)}")
        return jsonify({'error': 'Failed to switch thread'}), 500
@app.route('/api/ai/threads/<chatbot_type>/<thread_id>/delete', methods=['DELETE'])
@require_login
def delete_thread(chatbot_type, thread_id):
    """Delete a conversation thread"""
    uid = session['uid']
    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400
    try:
        ai = get_ai_assistant()
        success = ai.delete_thread(uid, chatbot_type, thread_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Cannot delete active thread or thread not found'}), 400
    except Exception as e:
        logger.error(f"Error deleting thread: {str(e)}")
        return jsonify({'error': 'Failed to delete thread'}), 500
@app.route('/api/ai/threads/<chatbot_type>/<thread_id>/export/<format_type>', methods=['GET'])
@require_login
def export_thread(chatbot_type, thread_id, format_type):
    """Export a conversation thread"""
    uid = session['uid']
    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400
    if format_type not in ['text', 'markdown', 'json']:
        return jsonify({'error': 'Invalid export format. Use: text, markdown, or json'}), 400
    try:
        ai = get_ai_assistant()
        export_data = ai.export_thread(uid, chatbot_type, thread_id, format_type)
        if export_data:
            if format_type == 'json':
                return jsonify(export_data)
            else:
                # Return as downloadable text file
                from flask import Response
                filename = f"conversation_{thread_id}.{format_type}"
                return Response(
                    export_data,
                    mimetype='text/plain',
                    headers={
                        'Content-Disposition': f'attachment; filename={filename}',
                        'Content-Type': 'text/plain; charset=utf-8'
                    }
                )
        else:
            return jsonify({'error': 'Thread not found or export failed'}), 404
    except Exception as e:
        logger.error(f"Error exporting thread: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500
@app.route('/api/ai/threads/<chatbot_type>/<thread_id>/history', methods=['GET'])
@require_login
def get_thread_history(chatbot_type, thread_id):
    """Get messages for a specific conversation thread"""
    uid = session['uid']
    if chatbot_type not in ['planning', 'doubt']:
        return jsonify({'error': 'Invalid chatbot type'}), 400
    try:
        ai = get_ai_assistant()
        history = ai.get_conversation_history(uid, chatbot_type, thread_id)
        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"Error loading thread history: {str(e)}")
        return jsonify({'error': 'Failed to load thread history'}), 500

# ============================================================================
# GEMINI ANALYTICS API ENDPOINTS
# ============================================================================
@app.route('/api/analytics/cluster/class/<class_id>', methods=['POST'])
@require_teacher_v2
def cluster_class_study_patterns(class_id):
    """Generate study pattern clusters for a class"""
    uid = session['uid']
    teacher_profile = _get_teacher_profile(uid) or {}
    institution_id = teacher_profile.get('institution_id')
    
    try:
        # Verify teacher has access to this class
        class_doc = db.collection('classes').document(class_id).get()
        if not class_doc.exists:
            return jsonify({'error': 'Class not found'}), 404
        
        class_data = class_doc.to_dict()
        if class_data.get('institution_id') != institution_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Check if recently clustered
        last_clustered = class_data.get('last_clustered')
        if last_clustered:
            last_date = datetime.fromisoformat(last_clustered)
            if (datetime.utcnow() - last_date).days < 7:
                # Return cached clusters
                clusters = class_data.get('study_clusters', [])
                return jsonify({
                    'clusters': clusters,
                    'cached': True,
                    'last_clustered': last_clustered
                })
        
        # Generate new clusters
        clusters = gemini_analytics.analyze_class_study_patterns(class_id)
        
        if clusters:
            gemini_analytics.store_class_clusters(class_id, clusters)
            return jsonify({
                'clusters': clusters,
                'cached': False,
                'last_clustered': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({'error': 'Failed to generate clusters'}), 500
            
    except Exception as e:
        logger.error(f"Error clustering class {class_id}: {str(e)}")
        return jsonify({'error': 'Clustering failed'}), 500

@app.route('/api/analytics/cluster/institution/<institution_id>', methods=['POST'])
@require_admin_v2
def cluster_institution_study_patterns(institution_id):
    """Generate study pattern clusters for entire institution"""
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    
    if admin_profile.get('institution_id') != institution_id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get all classes in institution
        classes_query = db.collection('classes').where('institution_id', '==', institution_id)
        institution_clusters = []
        
        for class_doc in classes_query.stream():
            class_id = class_doc.id
            class_data = class_doc.to_dict()
            
            # Check if recently clustered
            last_clustered = class_data.get('last_clustered')
            if last_clustered:
                last_date = datetime.fromisoformat(last_clustered)
                if (datetime.utcnow() - last_date).days < 7:
                    # Use cached clusters
                    clusters = class_data.get('study_clusters', [])
                    institution_clusters.extend(clusters)
                    continue
            
            # Generate new clusters
            clusters = gemini_analytics.analyze_class_study_patterns(class_id)
            if clusters:
                gemini_analytics.store_class_clusters(class_id, clusters)
                institution_clusters.extend(clusters)
        
        return jsonify({
            'clusters': institution_clusters,
            'total_classes': len(list(classes_query.stream())),
            'generated_at': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error clustering institution {institution_id}: {str(e)}")
        return jsonify({'error': 'Institution clustering failed'}), 500

@app.route('/api/analytics/student/<student_uid>/predictions', methods=['GET'])
@require_institution_role(['teacher', 'admin'])
def get_student_predictions(student_uid):
    """Get AI predictions for a specific student"""
    uid = session['uid']
    account_type = _get_account_type()
    
    try:
        # Verify access rights
        if account_type == 'teacher':
            teacher_profile = _get_teacher_profile(uid) or {}
            institution_id = teacher_profile.get('institution_id')
            class_ids = teacher_profile.get('class_ids', [])
            
            # Check if student is in teacher's class
            student_doc = db.collection('users').document(student_uid).get()
            if not student_doc.exists:
                return jsonify({'error': 'Student not found'}), 404
            
            student_data = student_doc.to_dict()
            if student_data.get('institution_id') != institution_id:
                return jsonify({'error': 'Access denied'}), 403
            
            # Check class membership
            student_class_ids = student_data.get('class_ids', [])
            if not any(class_id in class_ids for class_id in student_class_ids):
                return jsonify({'error': 'Student not in your classes'}), 403
                
        elif account_type == 'admin':
            admin_profile = _get_admin_profile(uid) or {}
            institution_id = admin_profile.get('institution_id')
            
            student_doc = db.collection('users').document(student_uid).get()
            if not student_doc.exists:
                return jsonify({'error': 'Student not found'}), 404
            
            student_data = student_doc.to_dict()
            if student_data.get('institution_id') != institution_id:
                return jsonify({'error': 'Access denied'}), 403
        
        # Get predictions
        student_doc = db.collection('users').document(student_uid).get()
        student_data = student_doc.to_dict()
        
        risk_prediction = student_data.get('risk_prediction', {})
        readiness_prediction = student_data.get('readiness_prediction', {})
        
        return jsonify({
            'risk_prediction': risk_prediction,
            'readiness_prediction': readiness_prediction,
            'student_name': student_data.get('name', 'Student'),
            'last_updated': max(
                risk_prediction.get('last_updated', ''),
                readiness_prediction.get('last_updated', '')
            )
        })
        
    except Exception as e:
        logger.error(f"Error getting predictions for {student_uid}: {str(e)}")
        return jsonify({'error': 'Failed to get predictions'}), 500

@app.route('/profile/resume')
@require_login
def profile_resume():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    purpose = user_data.get('purpose')
    academic_summary = ''
    if purpose == 'school' and user_data.get('school'):
        school = user_data['school']
        academic_summary = f"{school.get('board', '')} – Grade {school.get('grade', '')}"
    elif purpose == 'exam' and user_data.get('exam'):
        academic_summary = f"{user_data['exam'].get('type', '')} Preparation"
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        academic_summary = f"{at.get('stream', '')} – Grade {at.get('grade', '')}"
    context = {
        'user': user_data,
        'name': user_data.get('name', 'Student'),
        'about': user_data.get('about', ''),
        'purpose_display': purpose.replace('_', ' ').title() if purpose else '',
        'academic_summary': academic_summary,
        'skills': user_data.get('skills', []),
        'hobbies': user_data.get('hobbies', []),
        'certificates': user_data.get('certificates', []),
        'achievements': user_data.get('achievements', []),
        'goals': [g for g in user_data.get('goals', []) if not g.get('completed', False)][:5],
        'profile_picture': user_data.get('profile_picture'),
        'profile_banner': user_data.get('profile_banner')
    }
    return render_template('profile_resume.html', **context)
def allowed_file(filename):
    """Check if file has allowed extension"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
@app.route('/profile/edit', methods=['GET', 'POST'])
@require_login
def profile_edit():
    uid = session['uid']
    if request.method == 'POST':
        # Handle profile picture removal
        action = request.form.get('action')
        if action == 'remove_pfp':
            # Remove profile picture from database
            db.collection('users').document(uid).update({'profile_picture': None})
            flash('Profile picture removed successfully!', 'success')
            return redirect(url_for('profile_edit'))
        # Handle banner removal
        if action == 'remove_banner':
            # Remove profile banner from database
            db.collection('users').document(uid).update({'profile_banner': None})
            flash('Profile banner removed successfully!', 'success')
            return redirect(url_for('profile_edit'))
        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                # Validate file
                if not allowed_file(file.filename):
                    flash('Invalid file type. Please upload JPG, PNG, or WebP images.', 'error')
                    return redirect(url_for('profile_edit'))
                if file.content_length > 5 * 1024 * 1024:  # 5MB limit
                    flash('File size too large. Please upload images smaller than 5MB.', 'error')
                    return redirect(url_for('profile_edit'))
                try:
                    # Create profile pictures directory if it doesn't exist
                    upload_dir = os.path.join(app.root_path, 'static', 'profile_pictures')
                    os.makedirs(upload_dir, exist_ok=True)
                    # Generate unique filename
                    filename = secure_filename(f"{uid}_{int(time.time())}_{file.filename}")
                    file_path = os.path.join(upload_dir, filename)
                    # Save file to local storage
                    file.save(file_path)
                    # Store relative path in database (will be served via Flask route)
                    profile_picture_path = f"profile_pictures/{filename}"
                    # Update user data with profile picture path
                    db.collection('users').document(uid).update({'profile_picture': profile_picture_path})
                    logger.info(f"Profile picture saved successfully: {profile_picture_path}")
                except Exception as e:
                    logger.error(f"Profile picture upload error: {str(e)}")
                    logger.error(f"Error type: {type(e).__name__}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    flash(f'Failed to upload profile picture: {str(e)}', 'error')
                    return redirect(url_for('profile_edit'))
        # Handle banner upload
        if 'profile_banner' in request.files:
            file = request.files['profile_banner']
            if file and file.filename:
                # Validate file
                if not allowed_file(file.filename):
                    flash('Invalid file type. Please upload JPG, PNG, or WebP images.', 'error')
                    return redirect(url_for('profile_edit'))
                if file.content_length > 10 * 1024 * 1024:  # 10MB limit for banners
                    flash('Banner file size too large. Please upload images smaller than 10MB.', 'error')
                    return redirect(url_for('profile_edit'))
                try:
                    # Process and convert image to banner format
                    try:
                        from PIL import Image
                        import io
                    except ImportError:
                        # PIL/Pillow not available, skip processing
                        flash('Banner processing not available. Please install Pillow for image processing.', 'warning')
                        # Still save the original file
                        upload_dir = os.path.join(app.root_path, 'static', 'profile_banners')
                        os.makedirs(upload_dir, exist_ok=True)
                        filename = secure_filename(f"{uid}_{int(time.time())}_banner{file.filename[file.filename.rfind('.'):]}")
                        file_path = os.path.join(upload_dir, filename)
                        file.save(file_path)
                        profile_banner_path = f"profile_banners/{filename}"
                        db.collection('users').document(uid).update({'profile_banner': profile_banner_path})
                        logger.info(f"Profile banner saved without processing: {profile_banner_path}")
                        flash('Profile banner uploaded successfully!', 'success')
                        return redirect(url_for('profile_edit'))
                    # Read image
                    image = Image.open(file)
                    # Convert to RGB if necessary (for JPEG compatibility)
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")
                    # Resize to banner dimensions (1200x400 - good aspect ratio for banners)
                    banner_width = 1200
                    banner_height = 400
                    # Calculate aspect ratios
                    target_ratio = banner_width / banner_height
                    image_ratio = image.width / image.height
                    if image_ratio > target_ratio:
                        # Image is wider, crop width
                        new_width = int(image.height * target_ratio)
                        left = (image.width - new_width) // 2
                        image = image.crop((left, 0, left + new_width, image.height))
                    elif image_ratio < target_ratio:
                        # Image is taller, crop height
                        new_height = int(image.width / target_ratio)
                        top = (image.height - new_height) // 2
                        image = image.crop((0, top, image.width, top + new_height))
                    # Resize to exact dimensions
                    image = image.resize((banner_width, banner_height), Image.Resampling.LANCZOS)
                    # Save as WebP for better compression
                    output = io.BytesIO()
                    image.save(output, format='WebP', quality=85)
                    output.seek(0)
                    # Create profile banners directory if it doesn't exist
                    upload_dir = os.path.join(app.root_path, 'static', 'profile_banners')
                    os.makedirs(upload_dir, exist_ok=True)
                    # Generate unique filename
                    filename = secure_filename(f"{uid}_{int(time.time())}_banner.webp")
                    file_path = os.path.join(upload_dir, filename)
                    # Save processed image
                    with open(file_path, 'wb') as f:
                        f.write(output.getvalue())
                    # Store relative path in database
                    profile_banner_path = f"profile_banners/{filename}"
                    # Update user data with profile banner path
                    db.collection('users').document(uid).update({'profile_banner': profile_banner_path})
                    logger.info(f"Profile banner processed and saved successfully: {profile_banner_path}")
                except Exception as e:
                    logger.error(f"Profile banner processing error: {str(e)}")
                    logger.error(f"Error type: {type(e).__name__}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    flash(f'Failed to process banner image: {str(e)}', 'error')
                    return redirect(url_for('profile_edit'))
        updates = {
            'name': request.form.get('name'),
            'about': request.form.get('about'),
            'skills': [s.strip() for s in request.form.get('skills', '').split(',') if s.strip()],
            'hobbies': [h.strip() for h in request.form.get('hobbies', '').split(',') if h.strip()],
            'certificates': [c.strip() for c in request.form.get('certificates', '').split(',') if c.strip()],
            'achievements': [a.strip() for a in request.form.get('achievements', '').split(',') if a.strip()]
        }
        db.collection('users').document(uid).update(updates)
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile_resume'))
    user_data = get_user_data(uid)
    context = {
        'user': user_data,
        'name': user_data.get('name', ''),
        'about': user_data.get('about', ''),
        'skills': ', '.join(user_data.get('skills', [])),
        'hobbies': ', '.join(user_data.get('hobbies', [])),
        'certificates': ', '.join(user_data.get('certificates', [])),
        'achievements': ', '.join(user_data.get('achievements', [])),
        'profile_picture': user_data.get('profile_picture')
    }
    return render_template('profile_edit.html', **context)
# ============================================================================
# PROFILE PICTURE SERVING
# ============================================================================
@app.route('/profile_pictures/<filename>')
def serve_profile_picture(filename):
    """Serve profile pictures from local storage"""
    try:
        return send_from_directory(
            os.path.join(app.root_path, 'static', 'profile_pictures'),
            filename
        )
    except FileNotFoundError:
        # Return default profile picture or 404
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'default-profile.png'
        ), 404
# ============================================================================
# ACADEMIC DASHBOARD
# ============================================================================
@app.route('/academic')
@require_login
def academic_dashboard():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    purpose = user_data.get('purpose')
    syllabus_purpose = {
        'school': 'school',
        'exam_prep': 'exam',
        'after_tenth': 'after_tenth'
    }.get(purpose, purpose)
    syllabus = {}
    if purpose == 'school' and user_data.get('school'):
        school = user_data['school']
        subject_combination = school.get('subject_combination')
        syllabus = get_syllabus(syllabus_purpose, school.get('board'), school.get('grade'), subject_combination=subject_combination)
    elif purpose == 'exam_prep' and user_data.get('exam'):
        syllabus = get_syllabus(syllabus_purpose, user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        syllabus = get_syllabus(syllabus_purpose, 'CBSE', at.get('grade'), at.get('subjects', []))
    progress_data = calculate_academic_progress(user_data)
    chapters_completed = user_data.get('chapters_completed', {})
    # Merge institution and class exclusions for UI consistency
    all_exclusions = {}
    inst_id = user_data.get('institution_id')
    class_ids = user_data.get('class_ids', [])
    if inst_id:
        try:
            inst_excl = db.collection('institutions').document(inst_id).collection('syllabus_exclusions').document('current').get()
            if inst_excl.exists: all_exclusions.update(inst_excl.to_dict().get('chapters', {}))
        except: pass
    if class_ids:
        for cid in class_ids:
            try:
                class_excl = db.collection('classes').document(cid).collection('excluded_chapters').document('current').get()
                if class_excl.exists: all_exclusions.update(class_excl.to_dict().get('chapters', {}))
            except: pass
    academic_exclusions = user_data.get('academic_exclusions', {})
    all_exclusions.update(academic_exclusions)
    # Build flat chapter list with completion status for left panel
    syllabus_flat = {}
    for subject_name, subject_data in syllabus.items():
        chapters = subject_data.get('chapters', {})
        syllabus_flat[subject_name] = {}
        for chapter_name in chapters.keys():
            exclusion_key = f"{subject_name}::{chapter_name}"
            is_excluded = all_exclusions.get(exclusion_key, False)
            is_done = False
            # Check completion even if excluded (but UI will show it as excluded)
            is_done = chapters_completed.get(subject_name, {}).get(chapter_name, False)
            syllabus_flat[subject_name][chapter_name] = {
                'completed': is_done,
                'excluded': is_excluded
            }
    # Goals and tasks for right panel
    goals = user_data.get('goals', [])
    tasks = user_data.get('tasks', [])
    results = user_data.get('exam_results', [])
    # Stats for results
    total_exams = len(results)
    avg_percentage = 0
    avg_percentage = calculate_average_percentage(results)
    # Subjects for goal dropdown
    subjects = list(syllabus.keys())
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'syllabus': syllabus,
        'syllabus_flat': syllabus_flat,
        'progress_data': progress_data,
        'goals': goals,
        'tasks': tasks,
        'results': sorted(results, key=lambda x: x.get('date', ''), reverse=True),
        'total_exams': total_exams,
        'avg_percentage': avg_percentage,
        'subjects': subjects,
        'test_types': TEST_TYPES,
        'settings': user_data.get('settings', {}),
        'in_institution': bool(user_data.get('institution_id')),
        'has_class': bool(user_data.get('class_ids'))
    }
    return render_template('academic_dashboard.html', **context)
@app.route('/master-library')
@require_login
def master_library():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'library_data': ACADEMIC_SYLLABI,
        'active_nav': 'library',
        'in_institution': bool(user_data.get('institution_id')),
        'has_class': bool(user_data.get('class_ids'))
    }
    return render_template('master_library.html', **context)
@app.route('/academic/subject/<subject_name>/chapter/<chapter_name>')
@require_login
def chapter_detail(subject_name, chapter_name):
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    purpose = user_data.get('purpose')
    syllabus_purpose = {
        'school': 'school',
        'exam_prep': 'exam',
        'after_tenth': 'after_tenth'
    }.get(purpose, purpose)
    syllabus = {}
    if purpose == 'school' and user_data.get('school'):
        school = user_data['school']
        subject_combination = school.get('subject_combination')
        syllabus = get_syllabus(syllabus_purpose, school.get('board'), school.get('grade'), subject_combination=subject_combination)
    elif purpose == 'exam_prep' and user_data.get('exam'):
        syllabus = get_syllabus(syllabus_purpose, user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        syllabus = get_syllabus(syllabus_purpose, 'CBSE', at.get('grade'), at.get('subjects', []))
    subject_data = syllabus.get(subject_name, {})
    if not subject_data:
        flash('Subject not found', 'error')
        return redirect(url_for('academic_dashboard'))
    chapters = subject_data.get('chapters', {})
    chapter_data = chapters.get(chapter_name, {})
    if not chapter_data:
        flash('Chapter not found', 'error')
        return redirect(url_for('academic_dashboard'))
    topics = chapter_data.get('topics', [])
    chapters_completed = user_data.get('chapters_completed', {})
    is_completed = chapters_completed.get(subject_name, {}).get(chapter_name, False)
    context = {
        'user': user_data,
        'name': user_data.get('name'),
        'subject_name': subject_name,
        'chapter_name': chapter_name,
        'topics': topics,
        'is_completed': is_completed,
        'in_institution': bool(user_data.get('institution_id')),
        'has_class': bool(user_data.get('class_ids'))
    }
    return render_template('chapter_detail.html', **context)
@app.route('/academic/toggle_chapter', methods=['POST'])
@require_login
def toggle_chapter_completion():
    uid = session['uid']
    subject_name = request.form.get('subject_name')
    chapter_name = request.form.get('chapter_name')
    if not subject_name or not chapter_name:
        flash('Invalid request', 'error')
        return redirect(url_for('academic_dashboard'))
    user_data = get_user_data(uid)
    chapters_completed = user_data.get('chapters_completed', {})
    if subject_name not in chapters_completed:
        chapters_completed[subject_name] = {}
    current_status = chapters_completed[subject_name].get(chapter_name, False)
    chapters_completed[subject_name][chapter_name] = not current_status
    db.collection('users').document(uid).update({'chapters_completed': chapters_completed})
    # Redirect back to academic dashboard (the chapter list lives there now)
    return redirect(url_for('academic_dashboard'))
@app.route('/academic/toggle_chapter_exclusion', methods=['POST'])
@require_login
def toggle_chapter_exclusion():
    uid = session['uid']
    subject_name = None
    chapter_name = None
    if not subject_name or not chapter_name:
        subject_name = request.form.get('subject_name')
        chapter_name = request.form.get('chapter_name')
    if not subject_name or not chapter_name:
        return redirect(url_for('academic_dashboard'))
    key = f"{subject_name}::{chapter_name}"
    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    exclusions = user_data.get('academic_exclusions', {})
    # Toggle exclusion (REVERSIBLE)
    if exclusions.get(key):
        exclusions.pop(key)
    else:
        exclusions[key] = True
    user_ref.update({'academic_exclusions': exclusions})
    return redirect(url_for('academic_dashboard'))
# ============================================================
# STUDY MODE (Pomodoro) ChatGPT
# ============================================================
@app.route('/study-mode')
@require_login
def study_mode():
    uid = session['uid']
    user_data = get_user_data(uid)
    name = user_data.get('name', 'Student') if user_data else 'Student'
    todos = db.collection('users').document(uid).collection('study_todos').stream()
    todo_list = [{'id': t.id, **t.to_dict()} for t in todos]
    return render_template(
        'study_mode.html',
        name=name,
        todos=todo_list,
        user=user_data,
        in_institution=bool(user_data.get('institution_id')),
        has_class=bool(user_data.get('class_ids'))
    )
@app.route('/study-mode/time', methods=['POST'])
@require_login
def study_time():
    uid = session['uid']
    data = request.json
    seconds = int(data.get('seconds', 0))
    local_hour = data.get('local_hour')
    local_weekday = data.get('local_weekday')
    session_break = data.get('session_break', False)
    # Get user data for timezone conversion
    user_data = get_user_data(uid)
    db.collection('users').document(uid).set({
        'study_mode': {'total_seconds': Increment(seconds)}
    }, merge=True)
    # Record/Update session for heatmap
    # Using YYYY-MM-DD-HH as a unique key for the hour to avoid document spam
    now = datetime.utcnow()
    hour_id = now.strftime("%Y-%m-%d-%H")
    # If session_break is True, create a unique session by adding timestamp
    if session_break:
        hour_id = f"{hour_id}-{int(now.timestamp())}"
    session_ref = db.collection('users').document(uid).collection('study_sessions').document(hour_id)
    session_data = {
        'start_time': get_current_time_for_user(user_data),  # Use user's timezone
        'duration_seconds': firestore.Increment(seconds),
        'last_updated': now.isoformat()
    }
    if local_hour is not None:
        session_data['local_hour'] = local_hour
    if local_weekday is not None:
        session_data['local_weekday'] = local_weekday
    session_ref.set(session_data, merge=True)
    return jsonify(ok=True)
@app.route('/study-mode/todo/add', methods=['POST'])
@require_login
def add_study_todo():
    uid = session['uid']
    text = request.json['text']
    db.collection('users').document(uid).collection('study_todos').add({
            'text': text,
            'done': False
        })
    return jsonify(ok=True)
@app.route('/study-mode/todo/<tid>/toggle', methods=['POST'])
@require_login
def toggle_study_todo(tid):
    uid = session['uid']
    ref = db.collection('users').document(uid).collection('study_todos').document(tid)
    doc = ref.get()
    ref.update({'done': not doc.to_dict().get('done', False)})
    return jsonify(ok=True)
@app.route('/study-mode/todo/<tid>/delete', methods=['POST'])
@require_login
def delete_study_todo(tid):
    uid = session['uid']
    db.collection('users').document(uid).collection('study_todos').document(tid).delete()
    return jsonify(ok=True)
#=============================================================================
# DOC - V1 - ChatGPT - Temporary Not Perfect
#=============================================================================
# ============================================================================
# GOALS (POST handler only — rendered inside academic_dashboard)
# ============================================================================
@app.route('/goals', methods=['GET', 'POST'])
@require_login
def goals_dashboard():
    uid = session['uid']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            title = request.form.get('title')
            if title:
                user_data = get_user_data(uid)
                goals = user_data.get('goals', [])
                goals.append({
                    'id': len(goals), 'title': title,
                    'description': request.form.get('description', ''),
                    'subject': request.form.get('subject', ''),
                    'target_date': request.form.get('target_date', ''),
                    'completed': False,
                    'created_at': datetime.utcnow().isoformat()
                })
                db.collection('users').document(uid).update({'goals': goals})
                flash('Goal added!', 'success')
        elif action == 'toggle':
            goal_id = int(request.form.get('goal_id'))
            user_data = get_user_data(uid)
            goals = user_data.get('goals', [])
            for g in goals:
                if g.get('id') == goal_id:
                    g['completed'] = not g.get('completed', False)
                    break
            db.collection('users').document(uid).update({'goals': goals})
        elif action == 'delete':
            goal_id = int(request.form.get('goal_id'))
            user_data = get_user_data(uid)
            goals = [g for g in user_data.get('goals', []) if g.get('id') != goal_id]
            db.collection('users').document(uid).update({'goals': goals})
            flash('Goal deleted!', 'success')
        return redirect(url_for('academic_dashboard'))
    # GET fallback — redirect to academic dashboard
    return redirect(url_for('academic_dashboard'))
@app.route('/tasks', methods=['GET', 'POST'])
@require_login
def tasks_dashboard():
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('logout'))
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            tasks = user_data.get('tasks', [])
            if action == 'add':
                title = request.form.get('title')
                if title:
                    new_task = {
                        'id': str(int(datetime.utcnow().timestamp() * 1000)),
                        'title': title,
                        'description': request.form.get('description', ''),
                        'goal_id': request.form.get('goal_id', ''),
                        'due_date': request.form.get('due_date', ''),
                        'completed': False,
                        'created_at': datetime.utcnow().isoformat(),
                        'updated_at': datetime.utcnow().isoformat()
                    }
                    tasks.append(new_task)
                    db.collection('users').document(uid).update({'tasks': tasks})
                    flash('Task added successfully!', 'success')
                else:
                    flash('Task title is required', 'error')
            elif action == 'toggle':
                task_id = request.form.get('task_id')
                for t in tasks:
                    if str(t.get('id')) == str(task_id):
                        t['completed'] = not t.get('completed', False)
                        t['updated_at'] = datetime.utcnow().isoformat()
                        break
                db.collection('users').document(uid).update({'tasks': tasks})
            elif action == 'delete':
                task_id = request.form.get('task_id')
                tasks = [t for t in tasks if str(t.get('id')) != str(task_id)]
                db.collection('users').document(uid).update({'tasks': tasks})
                flash('Task deleted!', 'success')
        except Exception as e:
            logger.error(f"Task action error: {str(e)}")
            flash(f"An error occurred: {str(e)}", 'error')
        # Redirect back to the referrer or a default page
        referrer = request.referrer or ''
        if 'tasks' in referrer or 'dashboard' in referrer:
            return redirect(referrer)
        return redirect(url_for('profile_dashboard'))
    # GET: Render tasks dashboard
    context = {
        'tasks': user_data.get('tasks', []),
        'goals': user_data.get('goals', []),
        'user': user_data,
        'name': user_data.get('name', 'Student'),
        'settings': user_data.get('settings', {})
    }
    return render_template('tasks_dashboard.html', **context)
# ============================================================================
# RESULTS
# ============================================================================
@app.route('/results', methods=['POST'])
@require_login
def results_dashboard():
    uid = session['uid']
    action = request.form.get('action')
    user_data = get_user_data(uid)
    results = user_data.get('exam_results', [])
    if action == 'add':
        test_types = request.form.get('test_types')          # dropdown value
        subject = request.form.get('subject', '')
        score = request.form.get('score')
        max_score = request.form.get('max_score')
        exam_date = request.form.get('exam_date')
        if test_types and score:
            results.append({
                'id': int(datetime.utcnow().timestamp() * 1000),  # robust unique id
                'test_types': test_types,
                'subject': subject,
                'score': float(score),
                'max_score': float(max_score) if max_score else 100.0,
                'exam_date': exam_date,
                'created_at': datetime.utcnow().isoformat()
            })
            db.collection('users').document(uid).update({
                'exam_results': results
            })
            flash('Result added!', 'success')
    elif action == 'delete':
        result_id = request.form.get('result_id')
        if result_id:
            results = [
                r for r in results
                if str(r.get('id')) != str(result_id)
            ]
            db.collection('users').document(uid).update({
                'exam_results': results
            })
            flash('Result deleted!', 'success')
    return redirect(url_for('academic_dashboard'))
# ============================================================================
# STATISTICS
# ============================================================================
@app.route('/statistics')
@require_login
def statistics_dashboard():
    uid = session['uid']
    user = get_user_data(uid)
    # --- PRODUCTIVITY STATS ---
    goals = user.get('goals', [])
    tasks = user.get('tasks', [])
    total_goals = len(goals)
    completed_goals = sum(1 for g in goals if g.get('completed'))
    goals_pct = round((completed_goals / total_goals) * 100) if total_goals > 0 else 0
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.get('completed'))
    tasks_pct = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
    # --- EXAM ANALYTICS ---
    results = user.get('exam_results', [])
    # 1. Overall Average per Test Type (Timeline Bar Chart)
    exam_map = {}
    timeline = []
    # 2. Subject-wise Performance (Line Chart)
    # Structure: {'Math': [{'date': '...', 'pct': 80}, ...], 'Science': ...}
    subject_performance = {}
    for r in results:
        if not r.get('max_score'):
            continue
        pct = (r['score'] / r['max_score']) * 100
        # For Overall Stats
        et = r.get('test_types') # Changed from 'test_type' to 'test_types' to match data entry
        if et:
            exam_map.setdefault(et, []).append(pct)
        if r.get('exam_date'):
            timeline.append({
                'date': r['exam_date'],
                'percentage': round(pct, 2)
            })
            # For Subject Stats
            subj = r.get('subject')
            if subj:
                subject_performance.setdefault(subj, []).append({
                    'date': r['exam_date'],
                    'percentage': round(pct, 2)
                })
    exam_avg = {
        k: round(sum(v) / len(v), 2)
        for k, v in exam_map.items()
    }
    timeline = sorted(timeline, key=lambda x: x['date'])
    # Sort subject performance by date too
    for subj in subject_performance:
        subject_performance[subj] = sorted(subject_performance[subj], key=lambda x: x['date'])
    return render_template(
        'statistics.html',
        exam_avg=exam_avg,
        timeline=timeline,
        streak=user.get('login_streak', 0),
        productivity={
            'goals': {'total': total_goals, 'completed': completed_goals, 'pct': goals_pct},
            'tasks': {'total': total_tasks, 'completed': completed_tasks, 'pct': tasks_pct}
        },
        subject_performance=subject_performance,
        subjects=sorted(list(subject_performance.keys())), # Only show subjects that have data
        name=user.get('name', 'Student'),
        user=user,
        in_institution=bool(user.get('institution_id')),
        has_class=bool(user.get('class_ids'))
    )

# ============================================================================
# LEGACY / COMPATIBILITY ROUTES
# ============================================================================
@app.route('/dashboard/highschool')
@require_login
def dashboard_highschool():
    return redirect(url_for('profile_dashboard'))
@app.route('/dashboard/exam')
@require_login
def dashboard_exam():
    return redirect(url_for('profile_dashboard'))
@app.route('/dashboard/after_tenth')
@require_login
def dashboard_after_tenth():
    return redirect(url_for('profile_dashboard'))
@app.route('/todo', methods=['GET', 'POST'])
@require_login
def todo():
    return redirect(url_for('academic_dashboard'))
@app.route('/about')
@require_login
def about():
    uid = session['uid']
    user_data = get_user_data(uid)
    return render_template('about.html', user=user_data, name=user_data.get('name') if user_data else 'Student', in_institution=bool(user_data.get('institution_id')) if user_data else False, has_class=bool(user_data.get('class_ids')) if user_data else False)
@app.route('/settings', methods=['GET', 'POST'])
@require_login
def settings():
    """User settings page for account preferences and academic configuration"""
    uid = session['uid']
    user_data = get_user_data(uid) or {}
    if request.method == 'POST':
        action = request.form.get('action', 'general')
        if action == 'general':
            # Handle appearance and notification settings
            theme = request.form.get('theme', 'dark')
            email_notifications = request.form.get('email_notifications') == 'on'
            updates = {
                'settings': {
                    'theme': theme,
                    'email_notifications': email_notifications
                }
            }
            db.collection('users').document(uid).update(updates)
            flash('General settings updated successfully!', 'success')
        elif action == 'academic':
            # Handle academic configuration change with WARNING
            confirm_delete = request.form.get('confirm_delete') == 'on'
            if not confirm_delete:
                flash('You must confirm data deletion to change academic settings.', 'error')
                return redirect(url_for('settings'))
            new_purpose = request.form.get('purpose')
            new_board = request.form.get('board')
            new_grade = request.form.get('grade')
            
            # Validation: CBSE grades 11-12 require subject combination
            if new_purpose == 'school' and new_board == 'CBSE' and new_grade in ['11', '12']:
                subject_combination = request.form.get('subject_combination')
                if not subject_combination:
                    flash('Subject combination is required for CBSE grades 11-12.', 'error')
                    return redirect(url_for('settings'))
            # Fields to clear when changing academic config
            updates = {
                'purpose': new_purpose,
                'chapters_completed': {},  # Clear all progress
                'exam_results': [],        # Clear exam results
                'time_studied': 0,         # Reset study time
                'highschool': None,
                'school': None,
                'exam': None,
                'after_tenth': None,
            }
            # Set new academic data based on purpose
            if new_purpose == 'school':
                school_data = {'board': new_board, 'grade': new_grade}
                # Add subject combination for CBSE grades 11-12
                if new_board == 'CBSE' and new_grade in ['11', '12']:
                    subject_combination = request.form.get('subject_combination')
                    if subject_combination:
                        school_data['subject_combination'] = subject_combination
                updates['school'] = school_data
            elif new_purpose == 'exam_prep':
                exam_type = request.form.get('exam_type', 'JEE')
                updates['exam'] = {'type': exam_type}
            db.collection('users').document(uid).update(updates)
            flash('Academic configuration updated. All previous progress has been reset.', 'success')
        elif action == 'account':
            # Handle account updates
            name = request.form.get('name')
            has_public_profile = request.form.get('has_public_profile') == 'true'
            
            updates = {}
            if name:
                updates['name'] = name
            
            # Update public profile consent
            updates['has_public_profile'] = has_public_profile
            
            # Update privacy settings if public profile is enabled
            if has_public_profile:
                profile_visibility = {
                    'name': request.form.get('visibility_name') == 'true',
                    'purpose': request.form.get('visibility_purpose') == 'true',
                    'academic_summary': request.form.get('visibility_academic_summary') == 'true',
                    'about': request.form.get('visibility_about') == 'true',
                    'grade': request.form.get('visibility_grade') == 'true',
                    'school': request.form.get('visibility_school') == 'true',
                    'skills': request.form.get('visibility_skills') == 'true',
                    'subjects': request.form.get('visibility_subjects') == 'true'
                }
                updates['profile_visibility'] = profile_visibility
            else:
                # If disabling public profile, keep existing visibility settings for future re-enable
                updates['profile_visibility'] = user_data.get('profile_visibility', {})
            
            if updates:
                db.collection('users').document(uid).update(updates)
                flash('Profile settings updated!', 'success')
        return redirect(url_for('settings'))
    # Get current settings or defaults
    current_settings = user_data.get('settings', {})
    # Get available options for academic configuration
    available_boards = ['CBSE', 'ICSE', 'IB', 'IGCSE', 'State Board']
    available_grades = ['8', '9', '10', '11', '12']
    available_exams = ['JEE', 'NEET', 'SAT', 'ACT', 'GRE', 'GMAT', 'CAT', 'UPSC', 'SSC', 'Bank PO', 'Other']
    return render_template('settings.html',
                         user=user_data,
                         name=user_data.get('name') or 'Student',
                         settings=current_settings,
                         available_boards=available_boards,
                         available_grades=available_grades,
                         available_exams=available_exams,
                         in_institution=bool(user_data.get('institution_id')),
                         has_class=bool(user_data.get('class_ids')))
@app.route('/api/tutorial/complete', methods=['POST'])
@require_login
def tutorial_complete():
    """API endpoint to save tutorial completion status"""
    uid = session['uid']
    
    try:
        data = request.get_json() or {}
        completed = data.get('completed', False)
        
        # Update user's tutorial completion status
        db.collection('users').document(uid).update({
            'tutorial_completed': completed,
            'tutorial_completed_at': datetime.utcnow().isoformat() if completed else None
        })
        
        logger.info("tutorial_completion_saved", user_id=uid, completed=completed)
        
        return jsonify({
            'success': True,
            'message': 'Tutorial status saved successfully'
        })
    
    except Exception as e:
        logger.error("tutorial_completion_error", error=str(e), user_id=uid)
        return jsonify({
            'success': False,
            'message': 'Failed to save tutorial status'
        }), 500
@app.route('/contact', methods=['GET', 'POST'])
@require_login
def contact():
    """Contact/Support page for user inquiries - sends email to support team"""
    uid = session['uid']
    user_data = get_user_data(uid) or {}
    if request.method == 'POST':
        subject = request.form.get('subject')
        message = request.form.get('message')
        category = request.form.get('category', 'general')
        if not subject or not message:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('contact'))
        # Build email content
        email_body = f"""
New Support Request from StudyOS
User Details:
- Name: {user_data.get('name', 'Unknown')}
- Email: {user_data.get('email', 'Unknown')}
- User ID: {uid}
- Category: {category}
Subject: {subject}
Message:
{message}
---
This email was sent from the StudyOS contact form.
        """
        try:
            # Send email to support (sample email - user will change later)
            msg = Message(
                subject=f"[StudyOS Support] {subject}",
                sender=app.config.get('MAIL_DEFAULT_SENDER', 'noreply@studyos.app'),
                recipients=['support@studyos.example.com'],  # Sample email - change this
                body=email_body
            )
            mail.send(msg)
            # Also store in Firestore as backup
            ticket = {
                'uid': uid,
                'user_email': user_data.get('email'),
                'user_name': user_data.get('name'),
                'subject': subject,
                'message': message,
                'category': category,
                'status': 'open',
                'created_at': datetime.utcnow().isoformat(),
                'email_sent': True
            }
            db.collection('support_tickets').add(ticket)
            flash('Your message has been sent! We will get back to you within 24-48 hours.', 'success')
            logger.info("support_ticket_created", user_id=uid, subject=subject, category=category)
        except Exception as e:
            logger.error("contact_email_error", error=str(e), user_id=uid)
            # Still store ticket even if email fails
            ticket = {
                'uid': uid,
                'user_email': user_data.get('email'),
                'user_name': user_data.get('name'),
                'subject': subject,
                'message': message,
                'category': category,
                'status': 'open',
                'created_at': datetime.utcnow().isoformat(),
                'email_sent': False,
                'email_error': str(e)
            }
            db.collection('support_tickets').add(ticket)
            flash('Your message has been saved. Our team will review it shortly.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html',
                         user=user_data,
                         name=user_data.get('name') or 'Student',
                         in_institution=bool(user_data.get('institution_id')),
                         has_class=bool(user_data.get('class_ids')))
# ============================================================================
# INSTITUTIONAL ECOSYSTEM (PHASE 2)
# ============================================================================
# Legacy require_role deprecated. Use require_institution_role instead.
@app.route('/institution/join', methods=['GET', 'POST'])
@require_login
def institution_join():
    """Redirect to student join class if student, or teacher join if applicable."""
    account_type = _get_account_type()
    if account_type == 'teacher':
        return redirect(url_for('institution_teacher_join'))
    return redirect(url_for('student_join_class'))
@app.route('/institution/dashboard')
@require_institution_role(['admin', 'teacher'])
def institution_dashboard_redirect():
    """Redirect legacy dashboard to specific V2 dashboards."""
    account_type = _get_account_type()
    if account_type == 'admin':
        return redirect(url_for('institution_admin_dashboard'))
    return redirect(url_for('institution_teacher_dashboard'))
@app.route('/institution/generate_invite', methods=['POST'])
@require_institution_role(['admin', 'teacher'])
def generate_invite():
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    class_id = request.form.get('class_id')
    role = request.form.get('role', 'student')
    # Generate 6-char code
    code = _generate_code(6)
    db.collection('invites').add({
        'code': code,
        'institution_id': inst_id,
        'class_id': class_id,
        'role': role,
        'created_by': uid,
        'created_at': datetime.utcnow().isoformat(),
        'used': False,
        'one_time': True # or configurable
    })
    return jsonify({'code': code})
@app.route('/institution/nudge', methods=['POST'])
@require_institution_role(['teacher', 'admin'])
def send_nudge():
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    student_uid = request.json.get('student_uid')
    message = request.json.get('message', 'Your teacher has sent you a reminder to stay on track!')
    if not inst_id:
        return jsonify({'success': False, 'message': 'No institution context found.'}), 400
    # Create notification
    db.collection('institutions').document(inst_id).collection('notifications').add({
        'recipient_uid': student_uid,
        'sender_uid': uid,
        'sender_name': profile.get('name', 'Instructor'),
        'message': message,
        'type': 'nudge',
        'read': False,
        'created_at': datetime.utcnow().isoformat()
    })
    return jsonify({'success': True, 'message': 'Nudge sent!'})
@app.route('/institution/broadcast', methods=['POST'])
@require_institution_role(['teacher', 'admin'])
def broadcast_message():
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    message = request.form.get('message')
    class_id = request.form.get('class_id')
    if not message:
        return jsonify({'error': 'Message required'}), 400
    # Get target students
    student_uids = []
    if class_id:
        class_doc = db.collection(CLASSES_COL).document(class_id).get()
        if class_doc.exists:
            student_uids = class_doc.to_dict().get('student_uids', [])
    else:
        # Broadcast to all students in institution
        users_ref = db.collection('users').where('institution_id', '==', inst_id)
        student_uids = [u.id for u in users_ref.stream()]
    if student_uids:
        batch = db.batch()
        notif_ref = db.collection('institutions').document(inst_id).collection('notifications')
        for s_uid in student_uids:
            batch.set(notif_ref.document(), {
                'recipient_uid': s_uid,
                'sender_uid': uid,
                'sender_name': profile.get('name', 'Instructor'),
                'message': message,
                'type': 'broadcast',
                'read': False,
                'created_at': datetime.utcnow().isoformat()
            })
        batch.commit()
    flash(f'Message sent to {len(student_uids)} students!', 'success')
    dest = 'institution_admin_dashboard' if profile.get('account_type') == 'admin' else 'institution_teacher_dashboard'
    return redirect(url_for(dest))
@app.route('/institution/class/<class_id>/syllabus', methods=['GET', 'POST'])
@require_institution_role(['teacher', 'admin'])
def manage_class_syllabus(class_id):
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    # Verify class belongs to institution
    class_doc = db.collection(CLASSES_COL).document(class_id).get()
    if not class_doc.exists or class_doc.to_dict().get('institution_id') != inst_id:
        abort(403)
    class_data = class_doc.to_dict()
    if request.method == 'POST':
        # Handle exclusion toggle
        subject = request.form.get('subject')
        chapter = request.form.get('chapter')
        action = request.form.get('action')  # 'exclude' or 'include'
        exclusion_key = f"{subject}::{chapter}"
        exclusions_ref = db.collection('classes').document(class_id).collection('excluded_chapters').document('current')
        exclusions_doc = exclusions_ref.get()
        exclusions = exclusions_doc.to_dict().get('chapters', {}) if exclusions_doc.exists else {}
        if action == 'exclude':
            exclusions[exclusion_key] = True
        else:
            exclusions.pop(exclusion_key, None)
        exclusions_ref.set({'chapters': exclusions})
        flash(f'Chapter {chapter} {"excluded" if action == "exclude" else "included"}!', 'success')
        return redirect(url_for('manage_class_syllabus', class_id=class_id))
    # Get current exclusions
    exclusions_doc = db.collection('classes').document(class_id).collection('excluded_chapters').document('current').get()
    exclusions = exclusions_doc.to_dict().get('chapters', {}) if exclusions_doc.exists else {}
    # Get syllabus based on class metadata
    purpose = class_data.get('purpose', 'highschool')
    original_purpose = class_data.get('original_purpose', 'school')
    board = class_data.get('board', 'CBSE')
    grade = class_data.get('grade', '10')
    subject_combination = class_data.get('subject_combination')
    
    # Determine syllabus purpose based on original purpose
    if original_purpose == 'school':
        syllabus_purpose = 'school'
        syllabus = get_syllabus(syllabus_purpose, board, grade, subject_combination=subject_combination)
    elif original_purpose == 'exam':
        syllabus_purpose = 'exam'
        # For exam purpose, use the exam type directly
        syllabus = get_syllabus(syllabus_purpose, purpose)  # purpose contains exam type (JEE/NEET)
    else:
        syllabus_purpose = 'school'  # fallback
        syllabus = get_syllabus(syllabus_purpose, board, grade, subject_combination=subject_combination)
    if not syllabus:
        syllabus = {} # Fallback to empty if not found
    context = {
        'profile': profile,
        'class_id': class_id,
        'class_data': class_data,
        'syllabus': syllabus,
        'exclusions': exclusions
    }
    return render_template('class_syllabus.html', **context)
@app.route('/institution/student/<student_uid>')
@require_institution_role(['teacher', 'admin'])
def student_detail(student_uid):
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    # Get student data
    student_doc = db.collection('users').document(student_uid).get()
    if not student_doc.exists:
        abort(404)
    student_data = student_doc.to_dict()
    # Verify student belongs to same institution
    if student_data.get('institution_id') != inst_id:
        abort(403)
    # Calculate progress
    progress_data = calculate_academic_progress(student_data)
    # Get recent results
    results = student_data.get('exam_results', [])
    recent_results = sorted(results, key=lambda x: x.get('date', ''), reverse=True)[:5]
    # Get study sessions (if available)
    sessions_ref = db.collection('users').document(student_uid).collection('study_sessions').order_by('start_time', direction=firestore.Query.DESCENDING).limit(10)
    sessions = [s.to_dict() for s in sessions_ref.stream()]
    context = {
        'profile': profile,
        'student': student_data,
        'student_uid': student_uid,
        'progress_data': progress_data,
        'recent_results': recent_results,
        'sessions': sessions
    }
    return render_template('student_detail.html', **context)
@app.route('/institution/students')
@require_institution_role(['teacher', 'admin'])
def all_students():
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    if not inst_id:
        flash('No institution assigned.', 'error')
        return redirect(url_for('profile_dashboard'))
    
    # Get analytics data including risk detection
    analytics = _get_institution_analytics(inst_id)
    at_risk_data = {student['uid']: student for student in analytics.get('at_risk', [])}
    
    # Get all students in institution
    students_ref = db.collection('users').where('institution_id', '==', inst_id)
    students_docs = list(students_ref.stream())
    students_list = []
    for s_doc in students_docs:
        s_data = s_doc.to_dict()
        s_data['uid'] = s_doc.id
        
        # Add risk detection data from analytics
        risk_info = at_risk_data.get(s_doc.id, {})
        if risk_info:
            s_data['risk_level'] = risk_info.get('risk_level', risk_info.get('status', 'healthy'))
            s_data['status'] = risk_info.get('status', 'healthy')
            s_data['explanation'] = risk_info.get('explanation', '')
            s_data['ai_detected'] = risk_info.get('ai_detected', False)
            s_data['readiness_score'] = risk_info.get('readiness_score', 0)
            s_data['readiness_summary'] = risk_info.get('readiness_summary', '')
        else:
            # Default to healthy if not in risk list
            s_data['risk_level'] = 'healthy'
            s_data['status'] = 'healthy'
            s_data['explanation'] = ''
            s_data['ai_detected'] = False
            s_data['readiness_score'] = 0
            s_data['readiness_summary'] = ''
        
        # Calculate quick stats
        progress = calculate_academic_progress(s_data, uid=s_doc.id)
        s_data['progress_overall'] = progress.get('overall', 0)
        
        # Last login
        last_login = s_data.get('last_login_date', '')
        if last_login:
            try:
                last_date = datetime.fromisoformat(last_login).date() if isinstance(last_login, (str, datetime)) else last_login
                days_ago = (date.today() - last_date).days
                s_data['days_inactive'] = days_ago
            except:
                s_data['days_inactive'] = 999
        else:
            s_data['days_inactive'] = 999
        
        # Get class names
        class_ids = s_data.get('class_ids', [])
        class_names = []
        for cid in class_ids:
            c_doc = db.collection(CLASSES_COL).document(cid).get()
            if c_doc.exists:
                class_names.append(c_doc.to_dict().get('name', cid))
        s_data['class_names'] = ', '.join(class_names) if class_names else 'No class'
        students_list.append(s_data)
    
    # Sort by name
    students_list.sort(key=lambda x: x.get('name', ''))
    context = {
        'profile': profile,
        'students': students_list,
        'total_students': len(students_list),
    }
    return render_template('all_students.html', **context)
@app.route('/institution/teacher/settings')
@require_institution_role(['teacher'])
def institution_teacher_settings():
    uid = session['uid']
    profile = _get_teacher_profile(uid)
    inst_id = profile.get('institution_id')
    # Get institution data
    institution = {}
    if inst_id:
        inst_doc = db.collection('institutions').document(inst_id).get()
        if inst_doc.exists:
            institution = inst_doc.to_dict()
    # Get teacher's classes
    classes_docs = db.collection('classes').where('teacher_id', '==', uid).stream()
    classes = [{'id': c.id, **c.to_dict()} for c in classes_docs]
    # Get all students in institution
    students_docs = db.collection('users').where('institution_id', '==', inst_id).stream()
    students = [{'id': s.id, **s.to_dict()} for s in students_docs]
    logger.info("fetched_students", count=len(students), institution_id=inst_id)
    # Populate students for each class
    for cls in classes:
        cls['students'] = [s['id'] for s in students if cls['id'] in s.get('class_ids', [])]
        logger.info("class_student_count", class_name=cls.get('name', cls['id']), class_id=cls['id'], student_count=len(cls['students']))
    context = {
        'profile': profile,
        'institution': institution,
        'institution_id': inst_id,
        'classes': classes,
        'settings': profile.get('settings', {})
    }
    return render_template('institution_teacher_settings.html', **context)
@app.route('/institution/admin/settings')
@require_institution_role(['admin'])
def institution_admin_settings():
    uid = session['uid']
    profile = _get_admin_profile(uid)
    inst_id = profile.get('institution_id')
    # Get institution data
    institution = {}
    if inst_id:
        inst_doc = db.collection('institutions').document(inst_id).get()
        if inst_doc.exists:
            institution = inst_doc.to_dict()
    # Get all classes in institution
    classes_docs = db.collection('classes').where('institution_id', '==', inst_id).stream()
    classes = [{'id': c.id, **c.to_dict()} for c in classes_docs]
    # Get all students in institution
    students_docs = db.collection('users').where('institution_id', '==', inst_id).stream()
    students = [{'id': s.id, **s.to_dict()} for s in students_docs]
    logger.info("fetched_students", count=len(students), institution_id=inst_id)
    # Populate students for each class
    for cls in classes:
        cls['students'] = [s['id'] for s in students if cls['id'] in s.get('class_ids', [])]
        logger.info("class_student_count", class_name=cls.get('name', cls['id']), class_id=cls['id'], student_count=len(cls['students']))
    context = {
        'profile': profile,
        'institution': institution,
        'institution_id': inst_id,
        'classes': classes,
        'settings': profile.get('settings', {})
    }
    return render_template('institution_admin_settings.html', **context)
# ============================================================================
# SCLERA AI INSTITUTIONAL ANALYTICS API ROUTES
# ============================================================================
@app.route('/api/user/profile')
@require_login
def get_user_profile():
    """Get current user profile for SCLERA AI"""
    uid = session['uid']
    user_data = get_user_data(uid)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    # Get user role from institution system
    profile = _get_any_profile(uid)
    account_type = profile.get('account_type', 'student') if profile else 'student'
    return jsonify({
        'name': user_data.get('name', 'User'),
        'email': user_data.get('email'),
        'role': account_type,
        'initials': ''.join([word[0] for word in user_data.get('name', 'User').split()[:2]]).upper()
    })
@app.route('/api/sclera/threads/<mode>/create', methods=['POST'])
@require_login
def create_sclera_thread(mode):
    """Create a new SCLERA AI thread"""
    uid = session['uid']
    if mode not in ['academic', 'institutional', 'research']:
        return jsonify({'error': 'Invalid mode'}), 400
    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403
    data = request.json or {}
    title = data.get('title', f'New {mode.title()} Analysis')
    try:
        thread_data = {
            'title': title,
            'mode': mode,
            'created_at': datetime.utcnow().isoformat(),
            'last_message_at': datetime.utcnow().isoformat(),
            'message_count': 0
        }
        # Create thread document
        thread_ref = db.collection('users').document(uid).collection('sclera_threads').document()
        thread_ref.set(thread_data)
        return jsonify({
            'success': True,
            'thread_id': thread_ref.id,
            'thread': {**thread_data, 'thread_id': thread_ref.id}
        })
    except Exception as e:
        logger.error(f"SCLERA create thread error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/api/sclera/threads/<mode>/<thread_id>/delete', methods=['DELETE'])
@require_login
def delete_sclera_thread(mode, thread_id):
    """Delete a SCLERA AI thread"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400
    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403
    try:
        # Delete thread document (messages will be deleted by Firestore rules)
        thread_ref = db.collection('users').document(uid).collection('sclera_threads').document(thread_id)
        thread_doc = thread_ref.get()
        if not thread_doc.exists:
            return jsonify({'success': False, 'error': 'Thread not found'}), 404
        thread_ref.delete()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"SCLERA delete thread error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/api/sclera/threads/<mode>/<thread_id>/export')
@require_login
def export_sclera_thread(mode, thread_id):
    """Export a SCLERA AI thread conversation"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400
    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403
    format_type = request.args.get('format', 'text')
    if format_type not in ['text', 'markdown', 'json']:
        return jsonify({'error': 'Invalid format. Use text, markdown, or json'}), 400
    try:
        # Get AI assistant for export functionality
        ai_assistant = get_ai_assistant()
        # Export the thread
        exported_data = ai_assistant.export_thread(uid, mode, format_type, thread_id)
        if exported_data is None:
            return jsonify({'error': 'Failed to export thread'}), 500
        # Return the exported data as plain text (works for all formats)
        return exported_data, 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        logger.error(f"SCLERA export thread error: {str(e)}")
        return jsonify({'error': 'Failed to export thread', 'details': str(e)}), 500
@app.route('/api/sclera/threads/<mode>/<thread_id>/history')
@require_login
def get_sclera_thread_history(mode, thread_id):
    """Get conversation history for a SCLERA AI thread"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400
    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403
    try:
        # Get thread messages (simplified - no ordering to avoid issues)
        messages_ref = db.collection('users').document(uid).collection('sclera_threads').document(thread_id).collection('messages')
        messages_docs = messages_ref.stream()
        history = []
        for msg_doc in messages_docs:
            msg_data = msg_doc.to_dict()
            history.append({
                'role': msg_data.get('role'),
                'content': msg_data.get('content'),
                'timestamp': msg_data.get('timestamp')
            })
        # Sort in memory instead of Firestore
        history.sort(key=lambda x: x.get('timestamp', ''))
        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"SCLERA thread history error: {str(e)}")
        return jsonify({'history': [], 'error': str(e)}), 500
@app.route('/api/sclera/threads/<mode>')
@require_login
def get_sclera_threads(mode):
    """Get all threads for a SCLERA AI mode"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400
    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403
    try:
        # Get all threads for this mode
        threads_ref = db.collection('users').document(uid).collection('sclera_threads')
        thread_docs = list(threads_ref.where('mode', '==', mode).stream())
        threads = []
        for doc in thread_docs:
            thread_data = doc.to_dict()
            threads.append({
                'thread_id': doc.id,
                'title': thread_data.get('title', 'Untitled'),
                'mode': thread_data.get('mode'),
                'created_at': thread_data.get('created_at'),
                'last_message_at': thread_data.get('last_message_at'),
                'message_count': thread_data.get('message_count', 0)
            })
        # Sort by last message (most recent first)
        threads.sort(key=lambda x: x.get('last_message_at', ''), reverse=True)
        # Find active thread (most recent one)
        active_thread_id = threads[0]['thread_id'] if threads else None
        return jsonify({
            'threads': threads,
            'active_thread_id': active_thread_id
        })
    except Exception as e:
        logger.error(f"SCLERA get threads error: {str(e)}")
        return jsonify({'threads': [], 'active_thread_id': None, 'error': str(e)}), 500
@app.route('/api/test/gemini', methods=['GET'])
def test_gemini():
    """Test endpoint to list all available Gemini models"""
    try:
        import google.generativeai as genai
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return jsonify({
                'status': 'error',
                'message': 'GEMINI_API_KEY environment variable is not set',
                'api_key_set': False
            }), 500
        # Configure with just the API key
        genai.configure(api_key=api_key)
        try:
            # Get all available models
            models = genai.list_models()
            # Get detailed information about each model
            model_info = []
            for model in models:
                try:
                    # Test if model supports generateContent
                    try:
                        test_model = genai.GenerativeModel(model.name)
                        response = test_model.generate_content("Test", stream=False)
                        supports_generate = True
                    except:
                        supports_generate = False
                    model_info.append({
                        'name': model.name,
                        'display_name': getattr(model, 'display_name', 'N/A'),
                        'description': getattr(model, 'description', 'N/A'),
                        'input_token_limit': getattr(model, 'input_token_limit', 'N/A'),
                        'output_token_limit': getattr(model, 'output_token_limit', 'N/A'),
                        'supported_generation_methods': getattr(model, 'supported_generation_methods', []),
                        'supports_generate_content': supports_generate
                    })
                except Exception as e:
                    model_info.append({
                        'name': str(model),
                        'error': f"Could not get model info: {str(e)}"
                    })
            return jsonify({
                'status': 'success',
                'api_key_set': True,
                'api_key_prefix': api_key[:5] + '...' + api_key[-4:] if api_key else None,
                'available_models': model_info,
                'model_count': len(model_info)
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Failed to list models: {str(e)}',
                'api_key_set': True,
                'api_key_prefix': api_key[:5] + '...' + api_key[-4:] if api_key else None,
                'error_type': type(e).__name__
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'api_key_set': 'GEMINI_API_KEY' in os.environ,
            'api_key_prefix': os.getenv('GEMINI_API_KEY', '')[:5] + '...' + os.getenv('GEMINI_API_KEY', '')[-4:] if os.getenv('GEMINI_API_KEY') else None
        }), 500
@app.route('/api/sclera/chat/<mode>', methods=['POST'])
@require_login
def sclera_chat(mode):
    """Send a message to SCLERA AI and get response"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400
    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403
    data = request.json or {}
    message = data.get('message', '').strip()
    force_new_thread = data.get('force_new_thread', False)  # New parameter
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    try:
        # Get threads for this mode
        threads_ref = db.collection('users').document(uid).collection('sclera_threads')
        thread_docs = list(threads_ref.where('mode', '==', mode).stream())
        # Determine which thread to use
        if force_new_thread or not thread_docs:
            # Create new thread
            thread_data = {
                'title': f'New {mode.replace("_", " ").title()} Conversation',
                'mode': mode,
                'created_at': get_current_time_for_user({'uid': uid}),  # Use user's timezone
                'last_message_at': get_current_time_for_user({'uid': uid}),  # Use user's timezone
                'message_count': 0
            }
            thread_ref = threads_ref.document()
            thread_ref.set(thread_data)
            logger.info(f"Created new thread {thread_ref.id} for {mode}")
        else:
            # Use most recent thread (sort by last_message_at descending)
            thread_docs.sort(key=lambda doc: doc.to_dict().get('last_message_at', ''), reverse=True)
            thread_ref = thread_docs[0].reference
        # Save user message
        message_data = {
            'role': 'user',
            'content': message,
            'timestamp': get_current_time_for_user({'uid': uid})  # Use user's timezone
        }
        thread_ref.collection('messages').add(message_data)
        # Update thread metadata
        thread_ref.update({
            'last_message_at': get_current_time_for_user({'uid': uid}),  # Use user's timezone
            'message_count': firestore.Increment(1)
        })
        # Generate AI response using the correct AI assistant
        ai_response = generate_sclera_response(message, mode, uid)
        # Save AI response
        ai_message_data = {
            'role': 'assistant',
            'content': ai_response,
            'timestamp': get_current_time_for_user({'uid': uid})  # Use user's timezone
        }
        thread_ref.collection('messages').add(ai_message_data)
        # Update thread metadata again
        thread_ref.update({
            'last_message_at': get_current_time_for_user({'uid': uid})  # Use user's timezone
        })
        return jsonify({
            'response': ai_response,
            'thread_id': thread_ref.id  # Return thread ID so frontend knows which thread was used
        })
    except Exception as e:
        logger.error(f"SCLERA chat error: {str(e)}")
        return jsonify({'error': 'Failed to process message', 'details': str(e)}), 500
def generate_sclera_response(message, mode, uid):
    """Generate AI response based on mode and context"""
    try:
        # Get AI assistant - now handles missing API gracefully
        try:
            ai_assistant = get_ai_assistant()
            error_msg = getattr(ai_assistant, 'error_message', None)
            # Check if AI assistant is available
            if not hasattr(ai_assistant, 'ai_available') or not ai_assistant.ai_available:
                if not error_msg:
                    error_msg = 'AI Assistant is not available. No specific error information was provided.'
                logger.error(f"AI Assistant not available: {error_msg}")
                # Provide a more detailed error message to the user
                return (
                    "I'm sorry, but the AI Assistant is currently unavailable.\n\n"
                    f"**Error Details:** {error_msg}\n\n"
                    "**Possible Solutions:**\n"
                    "1. Verify that your GEMINI_API_KEY is correctly set and has access to the Gemini API\n"
                    "2. Check your internet connection\n"
                    "3. Ensure you have the latest version of the google-generativeai package\n"
                    "4. Try again in a few moments if the issue is temporary\n\n"
                    "If the problem persists, please contact support with the error details above."
                )
        except Exception as e:
            error_msg = f"Failed to initialize AI Assistant: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (
                "I'm sorry, but the AI Assistant encountered an error during initialization.\n\n"
                f"**Error Details:** {error_msg}\n\n"
                "Please check the server logs for more information and contact support if the issue persists."
            )
        try:
            # Get user context
            user_data = get_user_data(uid)
            profile = _get_any_profile(uid)
            # Create context based on mode
            context = {
                'user_name': user_data.get('name', 'Student') if user_data else 'Student',
                'purpose': profile.get('account_type', 'student') if profile else 'student',
                'mode': mode  # Add mode to context for better model responses
            }
            # Add academic context if available
            try:
                academic_context = ai_assistant.get_academic_context(user_data or {})
                context.update(academic_context)
            except Exception as e:
                logger.warning(f"Could not load academic context: {str(e)}")
            # Generate response based on mode
            try:
                if mode == 'academic_planner':
                    response = ai_assistant.generate_planning_response(message, context)
                elif mode == 'doubt_solver':
                    response = ai_assistant.generate_doubt_response(message, context)
                elif mode == 'institutional':
                    context['purpose'] = 'institutional'
                    response = ai_assistant.generate_planning_response(message, context)
                else:
                    response = ai_assistant.generate_planning_response(message, context)
                # Format response based on mode
                if mode == 'institutional' and not any(keyword in response.lower() for keyword in ['analysis', 'assessment', 'recommendations']):
                    response = (
                        f"# Analysis Results\n\n"
                        f"{response}\n\n"
                        "## Strategic Insights\n\n"
                        "Based on your query, the institutional data suggests the following key points:"
                    )
                return response
            except Exception as e:
                error_details = f"Error in {mode} response generation: {str(e)}"
                logger.error(error_details, exc_info=True)
                return (
                    f"I encountered an error while generating a response.\n\n"
                    f"**Error Details:** {error_details}\n\n"
                    "The error has been logged. Please try again or contact support if the issue persists."
                )
        except Exception as e:
            error_details = f"Error processing request: {str(e)}"
            logger.error(error_details, exc_info=True)
            return (
                "An error occurred while processing your request.\n\n"
                f"**Error Details:** {error_details}\n\n"
                "Please try again or contact support if the issue persists."
            )
    except Exception as e:
        error_details = f"Unexpected error in generate_sclera_response: {str(e)}"
        logger.error(error_details, exc_info=True)
        return (
            "An unexpected error occurred. The development team has been notified.\n\n"
            f"**Error:** {error_details}"
        )
    except Exception as e:
        logger.error(f"SCLERA response generation error: {str(e)}")
        # Fallback responses based on mode
        if mode == 'institutional':
            return f"""Analysis Results:
Based on your query: "{message}"
**Key Findings:**
- Institutional data indicates trends requiring attention
- Comparative analysis shows opportunities for improvement
- Strategic interventions recommended for optimal outcomes
**Recommended Actions:**
- Implement targeted support programs
- Monitor key performance indicators
- Develop comprehensive improvement strategies
**Next Steps:**
Would you like me to generate a detailed report or analyze specific metrics further?"""
        elif mode == 'academic_planner':
            return f"""Academic Planning Response:
For your question about: "{message}"
**Study Recommendations:**
- Focus on core concepts and foundational principles
- Practice regularly with diverse problem sets
- Utilize active recall and spaced repetition techniques
**Resource Suggestions:**
- Review course materials and supplementary texts
- Join study groups for collaborative learning
- Seek clarification on challenging topics promptly
**Goal Setting:**
- Break down large objectives into manageable tasks
- Track progress and adjust strategies as needed
- Celebrate achievements and maintain motivation
How else can I assist with your academic planning?"""
        else:  # doubt_solver
            return f"""Doubt Resolution Response:
I understand you're asking about: "{message[:50]}..."
**Step-by-step explanation:**
1. Let's break down your question
2. Here's the key concept you need to understand
3. Related examples and applications
4. Practice problems to help you master this
**Additional Resources:**
- Textbook references for this topic
- Online tutorials and video explanations
- Practice exercises at your level
Would you like me to explain any specific part in more detail?"""
@app.route('/api/sclera/threads/<mode>/<thread_id>/rename', methods=['POST'])
@require_login
def rename_sclera_thread(mode, thread_id):
    """Rename a SCLERA AI conversation thread"""
    uid = session['uid']
    if mode not in ['academic_planner', 'institutional', 'doubt_solver']:
        return jsonify({'error': 'Invalid mode'}), 400
    # Check institutional access
    if mode == 'institutional':
        profile = _get_any_profile(uid)
        institutional_roles = ['administrator', 'curriculum_director', 'institution_teacher', 'admin']
        if not profile or profile.get('account_type') not in institutional_roles:
            return jsonify({'error': 'Access denied: Institutional mode requires administrator privileges'}), 403
    data = request.json or {}
    new_title = data.get('title', '').strip()
    if not new_title:
        return jsonify({'error': 'Title is required'}), 400
    # Map mode to chatbot_type for AIAssistant
    mode_mapping = {
        'academic_planner': 'planning',
        'doubt_solver': 'doubt',
        'institutional': 'planning'  # institutional uses planning responses
    }
    chatbot_type = mode_mapping.get(mode)
    if not chatbot_type:
        return jsonify({'error': 'Invalid mode'}), 400
    try:
        # Rename SCLERA thread directly in Firestore
        thread_ref = db.collection('users').document(uid).collection('sclera_threads').document(thread_id)
        thread_doc = thread_ref.get()
        if not thread_doc.exists:
            return jsonify({'error': 'Thread not found'}), 404
        # Update the thread title
        thread_ref.update({'title': new_title.strip()})
        return jsonify({'success': True, 'message': 'Thread renamed successfully'})
    except Exception as e:
        logger.error(f"SCLERA rename thread error: {str(e)}")
        return jsonify({'error': 'Failed to rename thread', 'details': str(e)}), 500
@app.route('/api/notifications', methods=['GET'])
@require_login
def get_notifications():
    """API endpoint for students to fetch their notifications"""
    uid = session['uid']
    profile = _get_any_profile(uid)
    if not profile:
        return jsonify({'notifications': []})
    inst_id = profile.get('institution_id')
    if not inst_id:
        return jsonify({'notifications': []})
    # Get all unread notifications for this user in their institution
    # We remove order_by to avoid the need for a composite index
    try:
        notifs_ref = db.collection('institutions').document(inst_id).collection('notifications').where('recipient_uid', '==', uid).where('read', '==', False)
        notifications = []
        # Calling stream() with a simple query (single field filter or multiple equality filters)
        # usually doesn't require a composite index unless combined with order_by or inequalities.
        for n in notifs_ref.stream():
            n_data = n.to_dict()
            n_data['id'] = n.id
            notifications.append(n_data)
        # Sort in memory by created_at descending
        notifications.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        # Limit to 10 for the response
        return jsonify({'notifications': notifications[:10]})
    except Exception as e:
        print(f"Notification error: {e}")
        return jsonify({'notifications': [], 'error': str(e)})
@app.route('/api/notifications/<notif_id>/mark_read', methods=['POST'])
@require_login
def mark_notification_read(notif_id):
    """Mark a notification as read"""
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
    if not inst_id:
        return jsonify({'error': 'No institution'}), 400
    notif_ref = db.collection('institutions').document(inst_id).collection('notifications').document(notif_id)
    notif_doc = notif_ref.get()
    if notif_doc.exists:
        notif_data = notif_doc.to_dict()
        # Verify this notification belongs to the user
        if notif_data.get('recipient_uid') == uid:
            notif_ref.update({'read': True})
            return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404
# ============================================================================
# DOCS SYSTEM API ROUTES
# ============================================================================
DOCS_COL = 'documents'
FOLDERS_COL = 'folders'
DOC_VERSIONS_COL = 'document_versions'
def docs_login_guard():
    """Check if user is logged in for docs routes"""
    if 'uid' not in session:
        if request.is_json:
            return jsonify({'error': 'Authentication required', 'message': 'Please log in to access documents'}), 401
        return redirect(url_for('login'))
    return None
@app.route('/docs')
def docs_dashboard():
    """Main docs dashboard"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    # Get user's academic data for subjects
    user_doc = db.collection('users').document(user_id).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    # Get available subjects based on user's academic path
    subjects = []
    purpose = user_data.get('purpose', '')
    if purpose == 'school' and user_data.get('school'):
        school = user_data['school']
        subjects = get_available_subjects('highschool', school.get('board'), school.get('grade'))
    elif purpose == 'exam_prep' and user_data.get('exam'):
        subjects = get_available_subjects('exam', user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        subjects = get_available_subjects('after_tenth', 'CBSE', at.get('grade'))
    # Get user's folders and documents - use simpler queries first
    try:
        folders_ref = db.collection(FOLDERS_COL).where('owner_id', '==', user_id).where('deleted', '==', False).stream()
        folders = []
        for folder in folders_ref:
            folder_data = folder.to_dict()
            folder_data['id'] = folder.id
            # Convert timestamps to strings for JSON serialization
            if 'created_at' in folder_data and folder_data['created_at']:
                folder_data['created_at'] = folder_data['created_at'].isoformat() if hasattr(folder_data['created_at'], 'isoformat') else str(folder_data['created_at'])
            if 'updated_at' in folder_data and folder_data['updated_at']:
                folder_data['updated_at'] = folder_data['updated_at'].isoformat() if hasattr(folder_data['updated_at'], 'isoformat') else str(folder_data['updated_at'])
            folders.append(folder_data)
        # Sort folders by order_index in Python instead of Firestore
        folders.sort(key=lambda x: x.get('order_index', 0))
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error getting folders in dashboard: {str(e)}")
        # Fallback if index not ready - get all folders and filter
        try:
            folders = []
            all_folders = db.collection(FOLDERS_COL).where('owner_id', '==', user_id).stream()
            for folder in all_folders:
                folder_data = folder.to_dict()
                folder_data['id'] = folder.id
                if not folder_data.get('deleted', False):
                    # Convert timestamps to strings
                    if 'created_at' in folder_data and folder_data['created_at']:
                        folder_data['created_at'] = folder_data['created_at'].isoformat() if hasattr(folder_data['created_at'], 'isoformat') else str(folder_data['created_at'])
                    if 'updated_at' in folder_data and folder_data['updated_at']:
                        folder_data['updated_at'] = folder_data['updated_at'].isoformat() if hasattr(folder_data['updated_at'], 'isoformat') else str(folder_data['updated_at'])
                    folders.append(folder_data)
            folders.sort(key=lambda x: x.get('order_index', 0))
        except Exception as fallback_error:
            logger.error(f"Fallback folders also failed: {str(fallback_error)}")
            folders = []
    try:
        documents_ref = db.collection(DOCS_COL).where('owner_id', '==', user_id).where('deleted', '==', False).stream()
        documents = []
        for doc in documents_ref:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            # Convert timestamps to strings for JSON serialization
            if 'created_at' in doc_data and doc_data['created_at']:
                doc_data['created_at'] = doc_data['created_at'].isoformat() if hasattr(doc_data['created_at'], 'isoformat') else str(doc_data['created_at'])
            if 'updated_at' in doc_data and doc_data['updated_at']:
                doc_data['updated_at'] = doc_data['updated_at'].isoformat() if hasattr(doc_data['updated_at'], 'isoformat') else str(doc_data['updated_at'])
            documents.append(doc_data)
        # Sort documents by updated_at in Python
        documents.sort(key=lambda x: x.get('updated_at', datetime(1970, 1, 1)), reverse=True)
    except Exception as e:
        # Log error for debugging
        logger.error(f"Error getting documents in dashboard: {str(e)}")
        # Fallback if index not ready
        try:
            documents = []
            all_docs = db.collection(DOCS_COL).where('owner_id', '==', user_id).stream()
            for doc in all_docs:
                doc_data = doc.to_dict()
                doc_data['id'] = doc.id
                if not doc_data.get('deleted', False):
                    # Convert timestamps to strings
                    if 'created_at' in doc_data and doc_data['created_at']:
                        doc_data['created_at'] = doc_data['created_at'].isoformat() if hasattr(doc_data['created_at'], 'isoformat') else str(doc_data['created_at'])
                    if 'updated_at' in doc_data and doc_data['updated_at']:
                        doc_data['updated_at'] = doc_data['updated_at'].isoformat() if hasattr(doc_data['updated_at'], 'isoformat') else str(doc_data['updated_at'])
                    documents.append(doc_data)
            documents.sort(key=lambda x: x.get('updated_at', datetime(1970, 1, 1)), reverse=True)
        except Exception as fallback_error:
            logger.error(f"Fallback documents also failed: {str(fallback_error)}")
            documents = []
    # Get user settings for theme
    settings = {}
    try:
        user_doc = db.collection('users').document(user_id).get()
        if user_doc.exists:
            user_data_full = user_doc.to_dict()
            settings = user_data_full.get('settings', {})
    except Exception as e:
        print(f"Error getting user settings: {e}")
        user_data_full = {}
    # Determine institution and class status for topnav
    in_institution = bool(user_data_full.get('institution_id')) if user_data_full else False
    has_class = bool(user_data_full.get('class_ids')) if user_data_full else False
    return render_template('docs_dashboard.html', folders=folders, documents=documents, settings=settings, subjects=subjects, in_institution=in_institution, has_class=has_class)
@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Get all documents for user"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    folder_id = request.args.get('folder_id')
    try:
        if folder_id:
            query = db.collection(DOCS_COL).where('folder_id', '==', folder_id).where('owner_id', '==', user_id).where('deleted', '==', False)
        else:
            query = db.collection(DOCS_COL).where('owner_id', '==', user_id).where('deleted', '==', False)
        documents = []
        for doc in query.stream():
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            documents.append(doc_data)
        # Sort by updated_at in Python
        documents.sort(key=lambda x: x.get('updated_at', datetime(1970, 1, 1)), reverse=True)
        return jsonify({'documents': documents})
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error getting documents: {str(e)}")
        # Fallback if index not ready
        try:
            documents = []
            all_docs = db.collection(DOCS_COL).where('owner_id', '==', user_id).stream()
            for doc in all_docs:
                doc_data = doc.to_dict()
                doc_data['id'] = doc.id
                if not doc_data.get('deleted', False):
                    if not folder_id or doc_data.get('folder_id') == folder_id:
                        documents.append(doc_data)
            documents.sort(key=lambda x: x.get('updated_at', datetime(1970, 1, 1)), reverse=True)
            return jsonify({'documents': documents})
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {str(fallback_error)}")
            return jsonify({'error': f'Failed to load documents: {str(e)}', 'documents': []}), 500
@app.route('/api/documents', methods=['POST'])
def create_document():
    """Create new document"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    data = request.get_json()
    # Validate required fields
    if not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400
    try:
        # Create document
        doc_data = {
            'title': data.get('title'),
            'content': data.get('content', ''),
            'subject': data.get('subject', None),
            'owner_id': user_id,
            'folder_id': data.get('folder_id', None),
            'word_count': 0,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'deleted': False
        }
        doc_ref = db.collection(DOCS_COL).add(doc_data)
        doc_id = doc_ref[1].id
        created_doc = doc_ref[1].get().to_dict()
        created_doc['id'] = doc_id
        # Convert timestamps to strings for JSON serialization
        if 'created_at' in created_doc and created_doc['created_at']:
            if hasattr(created_doc['created_at'], 'isoformat'):
                created_doc['created_at'] = created_doc['created_at'].isoformat()
            else:
                created_doc['created_at'] = str(created_doc['created_at'])
        if 'updated_at' in created_doc and created_doc['updated_at']:
            if hasattr(created_doc['updated_at'], 'isoformat'):
                created_doc['updated_at'] = created_doc['updated_at'].isoformat()
            else:
                created_doc['updated_at'] = str(created_doc['updated_at'])
        return jsonify({'document': created_doc}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/documents/<doc_id>', methods=['GET'])
def get_document(doc_id):
    """Get specific document"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    doc_ref = db.collection(DOCS_COL).document(doc_id).get()
    if not doc_ref.exists:
        return jsonify({'error': 'Document not found'}), 404
    doc_data = doc_ref.to_dict()
    doc_data['id'] = doc_ref.id
    # Check permission
    if doc_data.get('owner_id') != user_id:
        return jsonify({'error': 'Access denied'}), 403
    return jsonify({'document': doc_data})
@app.route('/api/documents/<doc_id>/export/<format>')
def export_document(doc_id, format):
    """Export document in different formats"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    doc_ref = db.collection(DOCS_COL).document(doc_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({'error': 'Document not found'}), 404
    doc_data = doc.to_dict()
    # Check permission
    if doc_data.get('owner_id') != user_id:
        return jsonify({'error': 'Access denied'}), 403
    content = doc_data.get('content', '')
    title = doc_data.get('title', 'Untitled Document')
    if format == 'markdown':
        # Simple markdown conversion
        from flask import Response
        markdown_content = f"# {title}\n\n{content}"
        return Response(markdown_content, mimetype='text/plain', headers={
            'Content-Disposition': f'attachment; filename="{title}.md"'
        })
    elif format == 'html':
        from flask import Response
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div>{content}</div>
</body>
</html>"""
        return Response(html_content, mimetype='text/html', headers={
            'Content-Disposition': f'attachment; filename="{title}.html"'
        })
    elif format == 'txt':
        from flask import Response
        return Response(f"{title}\n\n{content}", mimetype='text/plain', headers={
            'Content-Disposition': f'attachment; filename="{title}.txt"'
        })
    elif format == 'pdf':
        # For PDF, we'll return a simple text-based approach
        # In production, you'd use a proper PDF library
        from flask import Response
        return Response(f"{title}\n\n{content}", mimetype='text/plain', headers={
            'Content-Disposition': f'attachment; filename="{title}.txt"'
        })
    else:
        return jsonify({'error': 'Unsupported format'}), 400
@app.route('/api/documents/<doc_id>', methods=['PUT'])
def update_document(doc_id):
    """Update document"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    data = request.get_json()
    doc_ref = db.collection(DOCS_COL).document(doc_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({'error': 'Document not found'}), 404
    doc_data = doc.to_dict()
    # Check permission
    if doc_data.get('owner_id') != user_id:
        return jsonify({'error': 'Access denied'}), 403
    # Update document
    update_data = {
        'title': data.get('title', doc_data.get('title')),
        'content': data.get('content', doc_data.get('content')),
        'folder_id': data.get('folder_id', doc_data.get('folder_id')),
        'updated_at': firestore.SERVER_TIMESTAMP,
        'word_count': data.get('word_count', doc_data.get('word_count', 0)),
        'subject': data.get('subject', doc_data.get('subject', '')),
        'tags': data.get('tags', doc_data.get('tags', [])),
        'starred': data.get('starred', doc_data.get('starred', False))
    }
    doc_ref.update(update_data)
    # Create version if significant change
    if data.get('create_version', False):
        version_data = {
            'document_id': doc_id,
            'content': update_data['content'],
            'word_count': update_data['word_count'],
            'created_at': firestore.SERVER_TIMESTAMP,
            'author_id': user_id,
            'change_type': data.get('change_type', 'edited')
        }
        db.collection(DOC_VERSIONS_COL).add(version_data)
    # Return updated document
    updated_doc = doc_ref.get().to_dict()
    updated_doc['id'] = doc_id
    return jsonify({'document': updated_doc})
@app.route('/api/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Soft delete document"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    doc_ref = db.collection(DOCS_COL).document(doc_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({'error': 'Document not found'}), 404
    doc_data = doc.to_dict()
    # Check permission
    if doc_data.get('owner_id') != user_id:
        return jsonify({'error': 'Access denied'}), 403
    doc_ref.update({'deleted': True, 'deleted_at': firestore.SERVER_TIMESTAMP})
    return jsonify({'message': 'Document deleted'})
@app.route('/api/folders', methods=['GET'])
def get_folders():
    """Get all folders for user"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    try:
        folders = []
        for folder in db.collection(FOLDERS_COL).where('owner_id', '==', user_id).where('deleted', '==', False).stream():
            folder_data = folder.to_dict()
            folder_data['id'] = folder.id
            folders.append(folder_data)
        # Sort by order_index in Python
        folders.sort(key=lambda x: x.get('order_index', 0))
        return jsonify({'folders': folders})
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error getting folders: {str(e)}")
        # Fallback if index not ready
        try:
            folders = []
            all_folders = db.collection(FOLDERS_COL).where('owner_id', '==', user_id).stream()
            for folder in all_folders:
                folder_data = folder.to_dict()
                folder_data['id'] = folder.id
                if not folder_data.get('deleted', False):
                    folders.append(folder_data)
            folders.sort(key=lambda x: x.get('order_index', 0))
            return jsonify({'folders': folders})
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {str(fallback_error)}")
            return jsonify({'error': f'Failed to load folders: {str(e)}', 'folders': []}), 500
@app.route('/api/folders', methods=['POST'])
def create_folder():
    """Create new folder"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    data = request.get_json()
    # Get next order index - use simpler query
    try:
        existing_folders = list(db.collection(FOLDERS_COL).where('owner_id', '==', user_id).where('parent_id', '==', data.get('parent_id', None)).where('deleted', '==', False).stream())
        order_index = len(existing_folders)
    except Exception as e:
        # Fallback - get all and filter
        all_folders = list(db.collection(FOLDERS_COL).where('owner_id', '==', user_id).stream())
        filtered_folders = [f for f in all_folders if not f.to_dict().get('deleted', False) and f.to_dict().get('parent_id') == data.get('parent_id', None)]
        order_index = len(filtered_folders)
    folder_data = {
        'name': data.get('name', 'New Folder'),
        'parent_id': data.get('parent_id'),
        'owner_id': user_id,
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP,
        'order_index': order_index,
        'deleted': False,
        'expanded': True
    }
    folder_ref = db.collection(FOLDERS_COL).add(folder_data)
    folder_id = folder_ref[1].id
    # Get the created folder to return proper data
    created_folder = folder_ref[1].get()
    folder_response = created_folder.to_dict()
    folder_response['id'] = folder_id
    # Convert timestamps to strings for JSON serialization
    if 'created_at' in folder_response and folder_response['created_at']:
        folder_response['created_at'] = folder_response['created_at'].isoformat() if hasattr(folder_response['created_at'], 'isoformat') else str(folder_response['created_at'])
    if 'updated_at' in folder_response and folder_response['updated_at']:
        folder_response['updated_at'] = folder_response['updated_at'].isoformat() if hasattr(folder_response['updated_at'], 'isoformat') else str(folder_response['updated_at'])
    return jsonify({'folder': folder_response}), 201
@app.route('/api/folders/<folder_id>', methods=['PUT'])
def update_folder(folder_id):
    """Update folder"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    data = request.get_json()
    folder_ref = db.collection(FOLDERS_COL).document(folder_id)
    folder = folder_ref.get()
    if not folder.exists:
        return jsonify({'error': 'Folder not found'}), 404
    folder_data = folder.to_dict()
    # Check permission
    if folder_data.get('owner_id') != user_id:
        return jsonify({'error': 'Access denied'}), 403
    update_data = {
        'name': data.get('name', folder_data.get('name')),
        'parent_id': data.get('parent_id', folder_data.get('parent_id')),
        'order_index': data.get('order_index', folder_data.get('order_index')),
        'expanded': data.get('expanded', folder_data.get('expanded', True)),
        'updated_at': firestore.SERVER_TIMESTAMP
    }
    folder_ref.update(update_data)
    updated_folder = folder_ref.get().to_dict()
    updated_folder['id'] = folder_id
    return jsonify({'folder': updated_folder})
@app.route('/api/folders/<folder_id>', methods=['DELETE'])
def delete_folder(folder_id):
    """Soft delete folder and its contents"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    folder_ref = db.collection(FOLDERS_COL).document(folder_id)
    folder = folder_ref.get()
    if not folder.exists:
        return jsonify({'error': 'Folder not found'}), 404
    folder_data = folder.to_dict()
    # Check permission
    if folder_data.get('owner_id') != user_id:
        return jsonify({'error': 'Access denied'}), 403
    try:
        # Delete all documents in this folder
        docs_in_folder = db.collection(DOCS_COL).where('folder_id', '==', folder_id).where('deleted', '==', False).stream()
        for doc in docs_in_folder:
            doc.reference.update({
                'deleted': True,
                'deleted_at': firestore.SERVER_TIMESTAMP
            })
        # Delete all subfolders
        subfolders = db.collection(FOLDERS_COL).where('parent_id', '==', folder_id).where('deleted', '==', False).stream()
        for subfolder in subfolders:
            subfolder.reference.update({
                'deleted': True,
                'deleted_at': firestore.SERVER_TIMESTAMP
            })
        # Delete the folder itself
        folder_ref.update({'deleted': True, 'deleted_at': firestore.SERVER_TIMESTAMP})
        return jsonify({'message': 'Folder and contents deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/documents/<doc_id>/versions', methods=['GET'])
def get_document_versions(doc_id):
    """Get document version history"""
    guard_resp = docs_login_guard()
    if guard_resp:
        return guard_resp
    user_id = session['uid']
    # Check document permission
    doc_ref = db.collection(DOCS_COL).document(doc_id).get()
    if not doc_ref.exists:
        return jsonify({'error': 'Document not found'}), 404
    doc_data = doc_ref.to_dict()
    if doc_data.get('owner_id') != user_id:
        return jsonify({'error': 'Access denied'}), 403
    try:
        versions = []
        for version in db.collection(DOC_VERSIONS_COL).where('document_id', '==', doc_id).order_by('created_at', direction=firestore.Query.DESCENDING).stream():
            version_data = version.to_dict()
            version_data['id'] = version.id
            versions.append(version_data)
    except Exception as e:
        # Fallback - get all and sort in Python
        versions = []
        all_versions = list(db.collection(DOC_VERSIONS_COL).where('document_id', '==', doc_id).stream())
        for version in all_versions:
            version_data = version.to_dict()
            version_data['id'] = version.id
            versions.append(version_data)
        versions.sort(key=lambda x: x.get('created_at', datetime(1970, 1, 1)), reverse=True)
    return jsonify({'versions': versions})


# ─────────────────────────────────────────────────────────────────────────────
# 2A. PDF REPORT GENERATION
# ─────────────────────────────────────────────────────────────────────────────
 
@app.route('/institution/teacher/class/<class_id>/report')
@require_teacher_v2
def generate_class_report(class_id):
    """Generate and download a PDF report for an entire class."""
    from report_generator import generate_class_report_pdf
    from flask import make_response
    import io
 
    uid = session['uid']
    profile = _get_teacher_profile(uid) or {}
    institution_id = profile.get('institution_id')
 
    # Verify teacher owns this class
    class_doc = db.collection(CLASSES_COL).document(class_id).get()
    if not class_doc.exists:
        abort(404)
    class_data = class_doc.to_dict()
    if class_data.get('teacher_id') != uid or class_data.get('institution_id') != institution_id:
        abort(403)
 
    # Fetch institution name
    inst_doc = db.collection(INSTITUTIONS_COL).document(institution_id).get()
    institution_name = inst_doc.to_dict().get('name', 'Institution') if inst_doc.exists else 'Institution'
 
    # Fetch analytics (heatmap + at-risk)
    analytics = _get_institution_analytics(institution_id, class_ids=[class_id])
    at_risk_map = {s['uid']: s for s in analytics.get('at_risk', [])}
 
    # Fetch all students in class
    student_uids = class_data.get('student_uids', [])
    students = []
    for sid in student_uids:
        s_doc = db.collection('users').document(sid).get()
        if not s_doc.exists:
            continue
        s_data = s_doc.to_dict()
        s_data['uid'] = sid
 
        progress = calculate_academic_progress(s_data, uid=sid)
        s_data['progress_overall'] = progress.get('overall', 0)
 
        # Last active
        last_login = s_data.get('last_login_date', '')
        try:
            last_date = datetime.fromisoformat(last_login).date()
            s_data['days_inactive'] = (date.today() - last_date).days
        except Exception:
            s_data['days_inactive'] = 999
 
        # Avg exam score
        results = s_data.get('exam_results', [])
        pcts = []
        for r in results:
            try:
                sc = float(r.get('score', 0))
                mx = float(r.get('max_score', 100))
                if mx:
                    pcts.append((sc / mx) * 100)
            except Exception:
                pass
        s_data['avg_exam_score'] = round(sum(pcts) / len(pcts), 1) if pcts else 0
 
        # Merge risk info
        risk_info = at_risk_map.get(sid, {})
        s_data['risk_level'] = risk_info.get('risk_level', risk_info.get('status', 'healthy'))
        s_data['readiness_score'] = risk_info.get('readiness_score', 0)
        s_data['explanation'] = risk_info.get('explanation', '')
        students.append(s_data)
 
    # Clusters (from class doc if already computed)
    clusters = class_data.get('clusters', [])
 
    try:
        pdf_bytes = generate_class_report_pdf(
            class_data=class_data,
            teacher_name=profile.get('name', 'Teacher'),
            institution_name=institution_name,
            students=students,
            at_risk=analytics.get('at_risk', []),
            heatmap_data=analytics.get('heatmap', {}),
            clusters=clusters,
        )
        response = make_response(pdf_bytes)
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in class_data.get('name', 'class'))
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="report_{safe_name}.pdf"'
        return response
    except RuntimeError as e:
        flash(str(e), 'error')
        return redirect(url_for('institution_teacher_dashboard'))
    except Exception as e:
        logger.error(f"Class report generation error: {e}")
        flash('Failed to generate report. Please try again.', 'error')
        return redirect(url_for('institution_teacher_dashboard'))
 
 
@app.route('/institution/teacher/student/<student_uid>/report')
@require_teacher_v2
def generate_student_report(student_uid):
    """Generate and download a PDF report for an individual student."""
    from report_generator import generate_student_report_pdf
    from flask import make_response
 
    uid = session['uid']
    profile = _get_teacher_profile(uid) or {}
    institution_id = profile.get('institution_id')
 
    # Fetch student
    s_doc = db.collection('users').document(student_uid).get()
    if not s_doc.exists:
        abort(404)
    s_data = s_doc.to_dict()
 
    # Verify student belongs to same institution
    if s_data.get('institution_id') != institution_id:
        abort(403)
 
    # Verify student is in one of teacher's classes
    teacher_class_ids = set()
    for c in db.collection(CLASSES_COL).where('teacher_id', '==', uid).stream():
        teacher_class_ids.add(c.id)
    student_class_ids = set(s_data.get('class_ids', []))
    if not teacher_class_ids.intersection(student_class_ids):
        abort(403)
 
    # Find class name
    class_name = ""
    for cid in student_class_ids.intersection(teacher_class_ids):
        c_doc = db.collection(CLASSES_COL).document(cid).get()
        if c_doc.exists:
            class_name = c_doc.to_dict().get('name', '')
            break
 
    progress_data = calculate_academic_progress(s_data, uid=student_uid)
    results = s_data.get('exam_results', [])
    recent_results = sorted(results, key=lambda x: x.get('date', ''), reverse=True)[:10]
 
    sessions_ref = (db.collection('users').document(student_uid)
                    .collection('study_sessions')
                    .order_by('start_time', direction=firestore.Query.DESCENDING)
                    .limit(20))
    sessions = [s.to_dict() for s in sessions_ref.stream()]
 
    # Risk info from Firestore predictions
    risk_info = {}
    rp = s_data.get('risk_prediction', {})
    rdp = s_data.get('readiness_prediction', {})
    if rp:
        risk_info['risk_level'] = rp.get('risk', 'healthy')
        risk_info['explanation'] = rp.get('explanation', '')
    if rdp:
        risk_info['readiness_score'] = rdp.get('readiness_score', 0)
        risk_info['readiness_summary'] = rdp.get('summary', '')
 
    try:
        pdf_bytes = generate_student_report_pdf(
            student_data=s_data,
            student_uid=student_uid,
            progress_data=progress_data,
            recent_results=recent_results,
            sessions=sessions,
            class_name=class_name,
            risk_info=risk_info,
        )
        response = make_response(pdf_bytes)
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in s_data.get('name', student_uid))
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="report_{safe_name}.pdf"'
        return response
    except RuntimeError as e:
        flash(str(e), 'error')
        return redirect(url_for('student_detail', student_uid=student_uid))
    except Exception as e:
        logger.error(f"Student report generation error: {e}")
        flash('Failed to generate report. Please try again.', 'error')
        return redirect(url_for('student_detail', student_uid=student_uid))
 
 
# ─────────────────────────────────────────────────────────────────────────────
# 2B. CUSTOM SYLLABUS UPLOAD
# ─────────────────────────────────────────────────────────────────────────────
 
@app.route('/institution/class/<class_id>/custom-syllabus', methods=['GET', 'POST'])
@require_institution_role(['teacher', 'admin'])
def custom_syllabus_upload(class_id):
    """Handle custom syllabus upload — Gemini extraction + preview storage."""
    import io, json
 
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
 
    class_doc = db.collection(CLASSES_COL).document(class_id).get()
    if not class_doc.exists or class_doc.to_dict().get('institution_id') != inst_id:
        abort(403)
    class_data = class_doc.to_dict()
 
    if request.method == 'GET':
        # Fetch already-linked custom syllabi for display
        custom_syllabi = []
        for cid in class_data.get('custom_syllabus_ids', []):
            cs_doc = db.collection('custom_syllabi').document(cid).get()
            if cs_doc.exists:
                cs = cs_doc.to_dict()
                cs['id'] = cid
                custom_syllabi.append(cs)
 
        return render_template('custom_syllabus.html',
                               profile=profile,
                               class_id=class_id,
                               class_data=class_data,
                               custom_syllabi=custom_syllabi)
 
    action = request.form.get('action', 'extract')
 
    # ── EXTRACT: receive text/PDF → call Gemini → return preview ──────────
    if action == 'extract':
        raw_text = request.form.get('syllabus_text', '').strip()
 
        # If a PDF was uploaded, extract text from it
        uploaded_file = request.files.get('syllabus_pdf')
        if uploaded_file and uploaded_file.filename:
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
                    raw_text = "\n".join(
                        page.extract_text() or "" for page in pdf.pages
                    )
            except ImportError:
                flash('PDF text extraction requires pdfplumber. Install it or paste text manually.', 'warning')
            except Exception as e:
                flash(f'Could not read PDF: {e}', 'error')
                return redirect(url_for('custom_syllabus_upload', class_id=class_id))
 
        if not raw_text:
            flash('Please upload a PDF or paste syllabus text.', 'error')
            return redirect(url_for('custom_syllabus_upload', class_id=class_id))
 
        # Call Gemini to extract structure
        extracted = _extract_syllabus_with_gemini(raw_text)
        if extracted is None:
            flash('Gemini extraction failed. Please try again or add chapters manually.', 'error')
            return redirect(url_for('custom_syllabus_upload', class_id=class_id))
 
        # Store preview in Firestore temporarily (not session to avoid cookie size limits)
        import uuid
        preview_id = str(uuid.uuid4())
        
        # Store in temporary collection with TTL (expires after 1 hour)
        db.collection('temp_syllabus_previews').document(preview_id).set({
            'class_id': class_id,
            'extracted': extracted,
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat()
        })
        
        # Store only the preview ID in session
        session['syllabus_preview_id'] = preview_id
        flash(f'Extracted {len(extracted)} chapters. Review and confirm below.', 'success')
        return redirect(url_for('custom_syllabus_preview', class_id=class_id))
 
    # ── MANUAL: create subject from scratch ───────────────────────────────
    elif action == 'manual':
        subject_name = request.form.get('subject_name', '').strip()
        chapters_raw = request.form.get('chapters_json', '[]')
        try:
            chapters = json.loads(chapters_raw)
        except Exception:
            flash('Invalid chapter data.', 'error')
            return redirect(url_for('custom_syllabus_upload', class_id=class_id))
 
        if not subject_name or not chapters:
            flash('Subject name and at least one chapter are required.', 'error')
            return redirect(url_for('custom_syllabus_upload', class_id=class_id))
 
        _save_custom_syllabus(class_id, subject_name, chapters, uid, inst_id)
        flash(f'Subject "{subject_name}" added to class syllabus.', 'success')
        return redirect(url_for('manage_class_syllabus', class_id=class_id))
 
    flash('Unknown action.', 'error')
    return redirect(url_for('custom_syllabus_upload', class_id=class_id))


@app.route('/institution/class/<class_id>/custom-syllabus/<custom_id>/edit', methods=['GET', 'POST'])
@require_institution_role(['teacher', 'admin'])
def edit_custom_syllabus(class_id, custom_id):
    """Edit an existing custom syllabus with rich content."""
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')

    # Verify permissions
    class_doc = db.collection(CLASSES_COL).document(class_id).get()
    if not class_doc.exists or class_doc.to_dict().get('institution_id') != inst_id:
        abort(403)
    
    # Get the custom syllabus
    cs_doc = db.collection('custom_syllabi').document(custom_id).get()
    if not cs_doc.exists:
        abort(404)
    
    syllabus_data = cs_doc.to_dict()
    
    # Verify the teacher created this syllabus or is admin
    if syllabus_data.get('created_by') != uid and profile.get('account_type') != 'admin':
        abort(403)

    if request.method == 'POST':
        subject_name = request.form.get('subject_name', '').strip()
        chapters_raw = request.form.get('chapters_json', '[]')
        
        try:
            chapters = json.loads(chapters_raw)
        except Exception:
            flash('Invalid chapter data.', 'error')
            return redirect(request.url)

        if not subject_name or not chapters:
            flash('Subject name and at least one chapter are required.', 'error')
            return redirect(request.url)

        # Update the syllabus
        db.collection('custom_syllabi').document(custom_id).update({
            'name': subject_name,
            'chapters': chapters,
            'updated_at': datetime.utcnow().isoformat(),
            'updated_by': uid
        })
        
        flash(f'Syllabus "{subject_name}" updated successfully!', 'success')
        return redirect(url_for('manage_class_syllabus', class_id=class_id))

    # GET request - prepare data for editing
    return render_template('edit_custom_syllabus.html',
                           profile=profile,
                           class_id=class_id,
                           class_data=class_doc.to_dict(),
                           syllabus_data=syllabus_data,
                           custom_id=custom_id)


@app.route('/institution/class/<class_id>/custom-syllabus/preview', methods=['GET', 'POST'])
@require_institution_role(['teacher', 'admin'])
def custom_syllabus_preview(class_id):
    """Show Gemini-extracted preview; on confirm, save to Firestore."""
    import json
 
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
 
    class_doc = db.collection(CLASSES_COL).document(class_id).get()
    if not class_doc.exists or class_doc.to_dict().get('institution_id') != inst_id:
        abort(403)
 
    # Get preview data from Firestore using preview ID
    preview_id = session.get('syllabus_preview_id')
    if not preview_id:
        flash('Preview session expired. Please re-upload.', 'warning')
        return redirect(url_for('custom_syllabus_upload', class_id=class_id))

    try:
        preview_doc = db.collection('temp_syllabus_previews').document(preview_id).get()
        if not preview_doc.exists:
            flash('Preview data not found. Please re-upload.', 'warning')
            return redirect(url_for('custom_syllabus_upload', class_id=class_id))
        
        preview_data = preview_doc.to_dict()
        
        # Verify this preview belongs to the correct class
        if preview_data.get('class_id') != class_id:
            flash('Invalid preview data. Please re-upload.', 'warning')
            return redirect(url_for('custom_syllabus_upload', class_id=class_id))
        
        # Check if preview has expired
        expires_at = preview_data.get('expires_at')
        if expires_at:
            from datetime import datetime
            if datetime.utcnow() > datetime.fromisoformat(expires_at.replace('Z', '+00:00')):
                flash('Preview expired. Please re-upload.', 'warning')
                return redirect(url_for('custom_syllabus_upload', class_id=class_id))
        
        extracted = preview_data.get('extracted', [])
        
    except Exception as e:
        logger.error(f"Error fetching preview data: {e}")
        flash('Error loading preview. Please re-upload.', 'error')
        return redirect(url_for('custom_syllabus_upload', class_id=class_id))
 
    if request.method == 'POST':
        subject_name = request.form.get('subject_name', '').strip()
        selected_indices_raw = request.form.getlist('selected_chapters')
        selected_indices = {int(i) for i in selected_indices_raw if i.isdigit()}
 
        if not subject_name:
            flash('Please enter a subject name.', 'error')
        else:
            confirmed_chapters = [
                ch for i, ch in enumerate(extracted) if i in selected_indices
            ]
            if confirmed_chapters:
                _save_custom_syllabus(class_id, subject_name, confirmed_chapters, uid, inst_id)
                
                # Clean up temporary preview data from Firestore
                preview_id = session.get('syllabus_preview_id')
                if preview_id:
                    try:
                        db.collection('temp_syllabus_previews').document(preview_id).delete()
                    except Exception as e:
                        logger.warning(f"Failed to cleanup preview data: {e}")
                
                session.pop('syllabus_preview_id', None)
                flash(f'Added {len(confirmed_chapters)} chapters under "{subject_name}".', 'success')
                return redirect(url_for('manage_class_syllabus', class_id=class_id))
            else:
                flash('Select at least one chapter.', 'error')
 
    return render_template('custom_syllabus_preview.html',
                           profile=profile,
                           class_id=class_id,
                           class_data=class_doc.to_dict(),
                           extracted=extracted)
 
 
@app.route('/institution/class/<class_id>/custom-syllabus/<custom_id>/delete', methods=['POST'])
@require_institution_role(['teacher', 'admin'])
def delete_custom_syllabus(class_id, custom_id):
    """Remove a custom syllabus from the class."""
    uid = session['uid']
    profile = _get_any_profile(uid)
    inst_id = profile.get('institution_id')
 
    class_doc = db.collection(CLASSES_COL).document(class_id).get()
    if not class_doc.exists or class_doc.to_dict().get('institution_id') != inst_id:
        abort(403)
 
    try:
        db.collection(CLASSES_COL).document(class_id).update({
            'custom_syllabus_ids': firestore.ArrayRemove([custom_id])
        })
        # Optionally also delete the custom_syllabi document (only if not shared)
        cs_doc = db.collection('custom_syllabi').document(custom_id).get()
        if cs_doc.exists and cs_doc.to_dict().get('created_by') == uid:
            db.collection('custom_syllabi').document(custom_id).delete()
        flash('Custom syllabus removed.', 'success')
    except Exception as e:
        logger.error(f"Delete custom syllabus error: {e}")
        flash('Failed to remove custom syllabus.', 'error')
 
    return redirect(url_for('manage_class_syllabus', class_id=class_id))
 
 
# ─────────────────────────────────────────────────────────────────────────────
# 2C. EXTRA STUDENT STATS FOR FILTERS (update all_students route helper)
# ─────────────────────────────────────────────────────────────────────────────
# Replace the existing `all_students` route's per-student computation block
# OR call this helper — paste it just before the all_students route in sclera.py
 
def _enrich_student_for_list(s_data: dict, sid: str) -> dict:
    """
    Compute avg_exam_score and study_time_week for a student dict.
    Call this inside all_students() before appending to students_list.
    """
    # Avg exam score
    results = s_data.get('exam_results', [])
    pcts = []
    for r in results:
        try:
            sc = float(r.get('score', 0))
            mx = float(r.get('max_score', 100))
            if mx:
                pcts.append(round((sc / mx) * 100, 1))
        except Exception:
            pass
    s_data['avg_exam_score'] = round(sum(pcts) / len(pcts), 1) if pcts else 0
 
    # Study time this week (minutes)
    seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    try:
        week_sessions = (db.collection('users').document(sid)
                         .collection('study_sessions')
                         .where('start_time', '>=', seven_days_ago)
                         .stream())
        s_data['study_time_week'] = sum(
            s.to_dict().get('duration_seconds', 0) // 60 for s in week_sessions
        )
    except Exception:
        s_data['study_time_week'] = 0
 
    return s_data
 
 
# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────
 
def _extract_syllabus_with_gemini(text: str) -> list | None:
    """
    Call Gemini to extract chapters + rich topic content from raw syllabus text.
    Returns a list of {chapter: str, topics: [rich topic objects]} dicts or None on failure.
    """
    import json, google.generativeai as genai

    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return None

    # Get the active AI assistant to use its working model
    try:
        ai_assistant = get_ai_assistant()
        logger.info(f"AI assistant available: {hasattr(ai_assistant, 'ai_available')}")
        if hasattr(ai_assistant, 'ai_available') and ai_assistant.ai_available and hasattr(ai_assistant, 'model'):
            # Use the active model from AI assistant
            model = ai_assistant.model
            model_name = getattr(ai_assistant, 'model_name', 'unknown')
            logger.info(f"Using active AI assistant model: {model_name}")
        else:
            # Fallback: configure and use the working flash-lite-latest model
            logger.info("AI assistant not available, using fallback model")
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('models/gemini-flash-lite-latest')
            logger.info("Using fallback model: models/gemini-flash-lite-latest")
    except Exception as e:
        # If AI assistant fails, fallback to direct model creation
        logger.error(f"Failed to get AI assistant: {e}")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('models/gemini-flash-lite-latest')
        logger.info("Using emergency fallback model: models/gemini-flash-lite-latest")
 
    prompt = (
        "You are an academic syllabus parser. Your task is to analyze the given syllabus text and create a well-structured, equally divided academic outline.\n\n"
        "CRITICAL: You MUST return valid JSON ONLY. No explanations, no markdown, no extra text.\n\n"
        "IMPORTANT REQUIREMENTS:\n"
        "1. EQUALLY DIVIDE the content into logical chapters (aim for 3-8 chapters depending on content length)\n"
        "2. For each chapter, create 3-6 main topics that are equally comprehensive\n"
        "3. Provide DETAILED explanations for each topic (2-4 comprehensive paragraphs)\n"
        "4. Generate 5-8 key points for each topic that summarize the main concepts\n"
        "5. Create a comprehensive list of educational resources for each topic\n\n"
        "JSON FORMAT REQUIREMENTS:\n"
        "- Return ONLY a JSON array: [{...}, {...}]\n"
        "- Each object must have exactly two keys: 'chapter' and 'topics'\n"
        "- All strings must be properly quoted and escaped\n"
        "- No trailing commas\n"
        "- All arrays and objects must be properly closed\n\n"
        "STRUCTURE:\n"
        "[\n"
        "  {\n"
        '    "chapter": "Chapter Name",\n'
        '    "topics": [\n'
        '      {\n'
        '        "name": "Topic Name",\n'
        '        "overview": "2-3 sentence overview",\n'
        '        "explanations": ["Paragraph 1", "Paragraph 2", "Paragraph 3"],\n'
        '        "key_points": ["Point 1", "Point 2", "Point 3", "Point 4", "Point 5"],\n'
        '        "images": [\n'
        '          {"url": "https://example.com/img1.jpg", "caption": "Description"}\n'
        '        ],\n'
        '        "resources": {\n'
        '          "videos": [\n'
        '            {"title": "Video Title", "url": "https://example.com/video1", "description": "Video description"}\n'
        '          ],\n'
        '          "pdfs": [\n'
        '            {"title": "PDF Title", "url": "https://example.com/pdf1", "description": "PDF description"}\n'
        '          ],\n'
        '          "practice": [\n'
        '            {"title": "Practice Title", "url": "https://example.com/practice1", "description": "Practice description"}\n'
        '          ]\n'
        '        }\n'
        '      }\n'
        '    ]\n'
        '  }\n'
        "]\n\n"
        "CONTENT GUIDELINES:\n"
        "- Make chapters roughly equal in scope and importance\n"
        "- Each topic should have substantial, detailed explanations\n"
        "- Key points should be concise but comprehensive summaries\n"
        "- Resources should be specific, educational, and relevant\n"
        '- Use placeholder URLs like "https://example.com/video1" for resources\n'
        "- If the original text doesn't have enough detail, expand with relevant educational content\n"
        "- Double-check all JSON syntax before returning\n\n"
        f"Syllabus text to process:\n{text[:6000]}"
    )
 
    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        logger.info(f"Raw model response: {raw[:200]}...")  # Log first 200 chars for debugging
        
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        # Try to parse JSON, with repair attempts
        try:
            parsed = json.loads(raw.strip())
            logger.info(f"Successfully parsed JSON: {type(parsed)} with {len(parsed) if isinstance(parsed, list) else 'unknown'} items")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {raw}")
            
            # Attempt basic JSON repair for common issues
            try:
                # Fix common JSON issues from AI models
                raw_repaired = raw.strip()
                
                # Fix 1: Remove markdown fences completely
                if raw_repaired.startswith("```"):
                    parts = raw_repaired.split("```")
                    if len(parts) >= 2:
                        raw_repaired = parts[1]
                        if raw_repaired.startswith("json"):
                            raw_repaired = raw_repaired[4:].strip()
                
                # Fix 2: Resources array with mixed types (strings and objects)
                if '"resources": [' in raw_repaired and '": "https://' in raw_repaired:
                    # Convert string resources to proper object format
                    import re
                    # Find and fix malformed resources arrays
                    resources_pattern = r'"resources": \[([^\]]+)\]'
                    matches = re.findall(resources_pattern, raw_repaired)
                    for match in matches:
                        resources_content = match
                        # Check if it's mixed strings and objects
                        if '": "' in resources_content and not resources_content.startswith('{'):
                            # Try to convert to proper format
                            fixed_resources = '[]'  # Default to empty array
                            logger.warning("Fixed malformed resources array - set to empty")
                            raw_repaired = raw_repaired.replace(match, f'"resources": {fixed_resources}')
                
                # Fix 3: Trailing commas and missing quotes
                raw_repaired = raw_repaired.replace('",\n    }', '"\n    }')  # Fix trailing commas
                raw_repaired = raw_repaired.replace(',\n]', '\n]')  # Fix trailing commas in arrays
                raw_repaired = raw_repaired.replace(',\n  }', '\n  }')  # Fix trailing commas in objects
                
                # Fix 4: Unclosed quotes and brackets
                open_braces = raw_repaired.count('{') - raw_repaired.count('}')
                open_brackets = raw_repaired.count('[') - raw_repaired.count(']')
                
                if open_braces > 0:
                    raw_repaired += '}' * open_braces
                    logger.warning(f"Added {open_braces} closing braces")
                if open_brackets > 0:
                    raw_repaired += ']' * open_brackets
                    logger.warning(f"Added {open_brackets} closing brackets")
                
                # Fix 5: Remove any text before/after JSON
                raw_repaired = raw_repaired.strip()
                if raw_repaired.startswith('[') and raw_repaired.endswith(']'):
                    # Looks like a JSON array, try parsing
                    pass
                elif raw_repaired.startswith('{') and raw_repaired.endswith('}'):
                    # Single object, wrap in array
                    raw_repaired = f'[{raw_repaired}]'
                    logger.info("Wrapped single object in array")
                else:
                    # Try to extract JSON from the middle
                    import re
                    json_match = re.search(r'(\[.*?\]|\{.*?\})', raw_repaired, re.DOTALL)
                    if json_match:
                        raw_repaired = json_match.group(1)
                        logger.info("Extracted JSON from response")
                
                logger.info(f"Attempting to parse repaired JSON...")
                parsed = json.loads(raw_repaired)
                logger.info("Successfully repaired and parsed JSON")
                
            except Exception as repair_error:
                logger.error(f"JSON repair failed: {repair_error}")
                logger.error(f"Attempted repair: {raw_repaired[:500]}...")
                return None
            
        logger.info(f"Parsed response type: {type(parsed)}")
        
        # Handle different response formats from different models
        if isinstance(parsed, list):
            logger.info("Processing list response format")
            result = []
            for item in parsed:
                if not item:
                    continue
                    
                # Handle both dict and string items
                if isinstance(item, str):
                    # Simple string format - create basic chapter structure
                    result.append({
                        "chapter": item,
                        "topics": []
                    })
                elif isinstance(item, dict):
                    if not item.get("chapter"):
                        continue
                    
                    chapter_data = {"chapter": str(item["chapter"])}
                    topics = item.get("topics", [])
                    
                    # Handle both old string format and new rich format
                    processed_topics = []
                    for topic in topics:
                        if isinstance(topic, str):
                            # Backward compatibility: convert string to rich format
                            processed_topics.append({
                                "name": topic,
                                "overview": f"Study of {topic}",
                                "explanations": [f"Key concepts and principles of {topic}."],
                                "key_points": [f"Understanding {topic} is essential for this chapter."],
                                "images": [],
                                "resources": {"videos": [], "pdfs": [], "practice": []}
                            })
                        elif isinstance(topic, dict):
                            # New rich format - ensure all required fields exist
                            resources = topic.get("resources", {})
                            if isinstance(resources, dict):
                                resources_data = {
                                    "videos": list(resources.get("videos", [])),
                                    "pdfs": list(resources.get("pdfs", [])),
                                    "practice": list(resources.get("practice", []))
                                }
                            else:
                                # If resources is not a dict (e.g., it's a list or None), create empty structure
                                resources_data = {"videos": [], "pdfs": [], "practice": []}
                            
                            processed_topics.append({
                                "name": str(topic.get("name", "")),
                                "overview": str(topic.get("overview", f"Study of {topic.get('name', 'topic')}")),
                                "explanations": list(topic.get("explanations", [])),
                                "key_points": list(topic.get("key_points", [])),
                                "images": list(topic.get("images", [])),
                                "resources": resources_data
                            })
                    
                    chapter_data["topics"] = processed_topics
                    result.append(chapter_data)
                else:
                    logger.warning(f"Unexpected item type in list: {type(item)}")
                    continue
            
            return result
            
        elif isinstance(parsed, dict):
            logger.info("Processing dict response format")
            # Handle dict response if models return single object
            if "chapters" in parsed:
                parsed = parsed["chapters"]
                # Reuse list processing logic inline
                result = []
                for item in parsed:
                    if not item:
                        continue
                    if isinstance(item, str):
                        result.append({
                            "chapter": item,
                            "topics": []
                        })
                    elif isinstance(item, dict) and item.get("chapter"):
                        chapter_data = {"chapter": str(item["chapter"])}
                        topics = item.get("topics", [])
                        processed_topics = []
                        for topic in topics:
                            if isinstance(topic, str):
                                processed_topics.append({
                                    "name": topic,
                                    "overview": f"Study of {topic}",
                                    "explanations": [f"Key concepts and principles of {topic}."],
                                    "key_points": [f"Understanding {topic} is essential for this chapter."],
                                    "images": [],
                                    "resources": {"videos": [], "pdfs": [], "practice": []}
                                })
                            elif isinstance(topic, dict):
                                resources = topic.get("resources", {})
                                if isinstance(resources, dict):
                                    resources_data = {
                                        "videos": list(resources.get("videos", [])),
                                        "pdfs": list(resources.get("pdfs", [])),
                                        "practice": list(resources.get("practice", []))
                                    }
                                else:
                                    resources_data = {"videos": [], "pdfs": [], "practice": []}
                                
                                processed_topics.append({
                                    "name": str(topic.get("name", "")),
                                    "overview": str(topic.get("overview", f"Study of {topic.get('name', 'topic')}")),
                                    "explanations": list(topic.get("explanations", [])),
                                    "key_points": list(topic.get("key_points", [])),
                                    "images": list(topic.get("images", [])),
                                    "resources": resources_data
                                })
                        chapter_data["topics"] = processed_topics
                        result.append(chapter_data)
                return result
            elif "chapter" in parsed and parsed.get("chapter"):
                # Handle single chapter response (common with Gemma models)
                logger.info("Processing single chapter response")
                chapter_data = {"chapter": str(parsed["chapter"])}
                topics = parsed.get("topics", [])
                
                processed_topics = []
                for topic in topics:
                    if isinstance(topic, str):
                        processed_topics.append({
                            "name": topic,
                            "overview": f"Study of {topic}",
                            "explanations": [f"Key concepts and principles of {topic}."],
                            "key_points": [f"Understanding {topic} is essential for this chapter."],
                            "images": [],
                            "resources": {"videos": [], "pdfs": [], "practice": []}
                        })
                    elif isinstance(topic, dict):
                        resources = topic.get("resources", {})
                        if isinstance(resources, dict):
                            resources_data = {
                                "videos": list(resources.get("videos", [])),
                                "pdfs": list(resources.get("pdfs", [])),
                                "practice": list(resources.get("practice", []))
                            }
                        else:
                            resources_data = {"videos": [], "pdfs": [], "practice": []}
                        
                        processed_topics.append({
                            "name": str(topic.get("name", "")),
                            "overview": str(topic.get("overview", f"Study of {topic.get('name', 'topic')}")),
                            "explanations": list(topic.get("explanations", [])),
                            "key_points": list(topic.get("key_points", [])),
                            "images": list(topic.get("images", [])),
                            "resources": resources_data
                        })
                
                chapter_data["topics"] = processed_topics
                return [chapter_data]  # Return as single-item list
            else:
                logger.error("Dict response doesn't contain 'chapters' or 'chapter' key")
                return None
        else:
            logger.error(f"Unexpected response format: {type(parsed)}")
            return None
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Gemini syllabus extraction error: {error_msg}")
        
        # If it's a quota error, try with a different model
        if "429" in error_msg or "quota" in error_msg.lower():
            logger.info("Quota exceeded, trying alternative models...")
            
            # Try Gemma models as fallback
            fallback_models = [
                'models/gemma-3-4b-it', 
                'models/gemma-3n-e4b-it'
            ]
            
            for fallback_model in fallback_models:
                try:
                    logger.info(f"Trying fallback model: {fallback_model}")
                    genai.configure(api_key=api_key)
                    fallback_model_instance = genai.GenerativeModel(fallback_model)
                    response = fallback_model_instance.generate_content(prompt)
                    
                    raw = response.text.strip()
                    if raw.startswith("```"):
                        raw = raw.split("```")[1]
                        if raw.startswith("json"):
                            raw = raw[4:]
                    
                    try:
                        parsed = json.loads(raw.strip())
                    except json.JSONDecodeError as parse_error:
                        logger.warning(f"Fallback model {fallback_model} returned invalid JSON: {parse_error}")
                        continue
                    
                    if isinstance(parsed, list):
                        logger.info(f"Successfully extracted syllabus with fallback model: {fallback_model}")
                        # Process the response the same way as above
                        result = []
                        for item in parsed:
                            if not item:
                                continue
                            if isinstance(item, str):
                                result.append({
                                    "chapter": item,
                                    "topics": []
                                })
                            elif isinstance(item, dict) and item.get("chapter"):
                                chapter_data = {"chapter": str(item["chapter"])}
                                topics = item.get("topics", [])
                                processed_topics = []
                                for topic in topics:
                                    if isinstance(topic, str):
                                        processed_topics.append({
                                            "name": topic,
                                            "overview": f"Study of {topic}",
                                            "explanations": [f"Key concepts and principles of {topic}."],
                                            "key_points": [f"Understanding {topic} is essential for this chapter."],
                                            "images": [],
                                            "resources": {"videos": [], "pdfs": [], "practice": []}
                                        })
                                    elif isinstance(topic, dict):
                                        resources = topic.get("resources", {})
                                        if isinstance(resources, dict):
                                            resources_data = {
                                                "videos": list(resources.get("videos", [])),
                                                "pdfs": list(resources.get("pdfs", [])),
                                                "practice": list(resources.get("practice", []))
                                            }
                                        else:
                                            resources_data = {"videos": [], "pdfs": [], "practice": []}
                                        
                                        processed_topics.append({
                                            "name": str(topic.get("name", "")),
                                            "overview": str(topic.get("overview", f"Study of {topic.get('name', 'topic')}")),
                                            "explanations": list(topic.get("explanations", [])),
                                            "key_points": list(topic.get("key_points", [])),
                                            "images": list(topic.get("images", [])),
                                            "resources": resources_data
                                        })
                                chapter_data["topics"] = processed_topics
                                result.append(chapter_data)
                        return result
                        
                except Exception as fallback_error:
                    logger.warning(f"Fallback model {fallback_model} failed: {fallback_error}")
                    continue

    return None
 
 
def _save_custom_syllabus(class_id: str, subject_name: str,
                           chapters: list, teacher_uid: str, inst_id: str):
    """
    Persist a custom syllabus document and link it to the class.
    """
    doc_ref = db.collection('custom_syllabi').document()
    doc_ref.set({
        'name': subject_name,
        'chapters': chapters,          # [{chapter, topics}]
        'created_by': teacher_uid,
        'created_at': datetime.utcnow().isoformat(),
        'institution_id': inst_id,
        'class_id': class_id,
    })
    # Link to class
    db.collection(CLASSES_COL).document(class_id).update({
        'custom_syllabus_ids': firestore.ArrayUnion([doc_ref.id])
    })
    logger.info(f"Custom syllabus '{subject_name}' saved as {doc_ref.id} for class {class_id}")

# ============================================================================
# STUDENT: View class custom syllabus
# Route: GET /class/<class_id>/syllabus
# Access: any logged-in student enrolled in the class
# ============================================================================
@app.route('/class/<class_id>/syllabus')
@require_login
def view_class_syllabus(class_id):
    """Student-facing view of all custom syllabi for a class."""
    uid = session['uid']
 
    # Verify the student is enrolled in this class
    class_doc = db.collection(CLASSES_COL).document(class_id).get()
    if not class_doc.exists:
        abort(404)
    class_data = class_doc.to_dict()
 
    enrolled_uids = class_data.get('student_uids', [])
    if uid not in enrolled_uids:
        abort(403)
 
    # Load all custom syllabi linked to this class
    custom_syllabi = []
    syllabus_ids = class_data.get('custom_syllabus_ids', [])
    logger.info(f"Class {class_id} has syllabus IDs: {syllabus_ids}")
    
    for cid in syllabus_ids:
        cs_doc = db.collection('custom_syllabi').document(cid).get()
        if cs_doc.exists:
            cs = cs_doc.to_dict()
            cs['id'] = cid
            custom_syllabi.append(cs)
            logger.info(f"Loaded syllabus: {cs.get('name', 'Unnamed')} with {len(cs.get('chapters', []))} chapters")
        else:
            logger.warning(f"Syllabus document {cid} not found")

    logger.info(f"Total custom syllabi loaded: {len(custom_syllabi)}")
    
    # Sort by created_at ascending (oldest subject first)
    custom_syllabi.sort(key=lambda x: x.get('created_at', ''))
 
    return render_template('student_class_syllabus.html',
                           class_id=class_id,
                           class_data=class_data,
                           custom_syllabi=custom_syllabi)
# ============================================================================
# ERROR HANDLERS
# ============================================================================
@app.errorhandler(400)
def bad_request(error):
    """Handle bad request errors"""
    logger.warning("bad_request", error=str(error), path=request.path)
    if request.is_json:
        return jsonify({'error': 'Bad request', 'message': str(error)}), 400
    return render_template('error.html', error_code=400, error_message="Bad request"), 400
@app.errorhandler(403)
def forbidden(error):
    """Handle forbidden errors"""
    logger.security_event("forbidden_access", user_id=session.get('uid'), ip_address=request.remote_addr)
    if request.is_json:
        return jsonify({'error': 'Forbidden', 'message': 'Access denied'}), 403
    return render_template('error.html', error_code=403, error_message="Access denied"), 403
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    logger.warning("page_not_found", path=request.path, ip=request.remote_addr)
    if request.is_json:
        return jsonify({'error': 'Not found', 'message': 'Resource not found'}), 404
    return render_template('error.html', error_code=404, error_message="Page not found"), 404
@app.errorhandler(429)
def rate_limit_handler(error):
    """Handle rate limit exceeded"""
    logger.security_event("rate_limit_exceeded", user_id=session.get('uid'), ip_address=request.remote_addr)
    if request.is_json:
        return jsonify({'error': 'Too many requests', 'message': 'Rate limit exceeded. Please try again later.'}), 429
    return render_template('error.html', error_code=429, error_message="Too many requests. Please try again later."), 429
@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.error("internal_server_error", error=str(error), path=request.path, traceback=traceback.format_exc())
    if request.is_json:
        return jsonify({'error': 'Internal server error', 'message': 'Something went wrong'}), 500
    return render_template('error.html', error_code=500, error_message="Internal server error"), 500
# ============================================================================
# REQUEST LOGGING
# ============================================================================
@app.before_request
def log_request():
    """Log all incoming requests"""
    # Skip login guard for API routes
    if request.path.startswith('/api/'):
        return None
    
    guard_resp = _institution_login_guard()
    if guard_resp is not None:
        return guard_resp
    logger.debug("request_started",
                 method=request.method,
                 path=request.path,
                 ip=request.remote_addr,
                 user_agent=str(request.user_agent))
@app.after_request
def log_response(response):
    """Log all responses"""
    logger.info("request_completed",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                ip=request.remote_addr)
    return response

@app.route('/institution/admin/update-ai-predictions', methods=['POST'])
@require_admin_v2
def update_ai_predictions():
    """Manually trigger AI predictions update for all students"""
    try:
        data = request.get_json() or {}
        batch_size = data.get('batch_size', 20)
        force_update = data.get('force_update', False)
        
        # Get active students
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        students_query = db.collection('users').where('last_login_date', '>=', thirty_days_ago)
        
        student_uids = []
        for student_doc in students_query.stream():
            student_uids.append(student_doc.id)
        
        if not student_uids:
            return jsonify({'success': False, 'message': 'No active students found'})
        
        # Process students in batches
        processed_count = 0
        error_count = 0
        
        for i in range(0, len(student_uids), batch_size):
            batch_uids = student_uids[i:i + batch_size]
            
            for uid in batch_uids:
                try:
                    # Check if update is needed (unless forced)
                    if not force_update:
                        user_doc = db.collection('users').document(uid).get()
                        if user_doc.exists:
                            user_data = user_doc.to_dict()
                            risk_pred = user_data.get('risk_prediction', {})
                            if risk_pred:
                                last_updated = risk_pred.get('last_updated', '')
                                prompt_version = risk_pred.get('prompt_version', 'v1')
                                if last_updated:
                                    last_date = datetime.fromisoformat(last_updated)
                                    if ((datetime.utcnow() - last_date).days <= 7 and 
                                        prompt_version == 'v2'):
                                        continue  # Skip if predictions are fresh
                    
                    # Generate new predictions
                    risk_data, readiness_data = gemini_analytics.predict_student_risk_and_readiness(uid)
                    
                    if risk_data or readiness_data:
                        gemini_analytics.store_student_predictions(uid, risk_data, readiness_data)
                        processed_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    logger.error(f"Error updating predictions for {uid}: {e}")
                    error_count += 1
            
            # Small delay between batches to avoid rate limits
            if i + batch_size < len(student_uids):
                time.sleep(0.5)
        
        return jsonify({
            'success': True,
            'message': f'Updated predictions for {processed_count} students',
            'processed': processed_count,
            'errors': error_count
        })
        
    except Exception as e:
        logger.error(f"Error in update_ai_predictions: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    env = os.environ.get('FLASK_ENV', 'production')
    debug = env == 'development'
    port = int(os.environ.get('PORT', 5001))
    logger.info("application_startup", environment=env, debug=debug, port=port)
    
    # Register CLI commands
    register_cli_commands(app)
    
    app.run(debug=debug, host='0.0.0.0', port=port)
