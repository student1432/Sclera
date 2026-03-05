"""
User profile utilities.
Handles user data retrieval, profile initialization, and academic calculations.
"""

from firebase_config import db
from templates.academic_data import get_syllabus, get_available_subjects, ACADEMIC_SYLLABI
from datetime import datetime, timedelta
from firebase_admin import firestore
Increment = firestore.Increment


def get_user_data(uid: str) -> dict:
    """
    Get user data from Firestore.
    
    Args:
        uid: User ID
        
    Returns:
        User data dictionary or empty dict if not found
    """
    user_doc = db.collection('users').document(uid).get()
    if user_doc.exists:
        return user_doc.to_dict()
    return {}


def initialize_profile_fields(uid: str):
    """
    Initialize default profile fields for a new user.
    
    Args:
        uid: User ID
    """
    user_doc = db.collection('users').document(uid).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    
    defaults = {
        'about': '',
        'skills': [],
        'hobbies': [],
        'certificates': [],
        'achievements': [],
        'chapters_completed': {},
        'time_studied': 0,
        'goals': [],
        'tasks': [],
        'todos': [],
        'milestones': [],
        'exam_results': [],
        'connections': {
            'accepted': [],
            'pending_sent': [],
            'pending_received': []
        },
        'bubbles': [],
        'academic_sharing_consents': {},
        'profile_visibility': {
            'name': True,
            'email': False,
            'institution': False,
            'academic_progress': True,
            'study_streaks': True,
            'goals': True,
            'connections': True
        },
        'study_preferences': {
            'daily_target_minutes': 120,
            'preferred_subjects': [],
            'difficulty_preference': 'medium',
            'study_reminders': True,
            'break_reminders': True
        },
        'privacy_settings': {
            'profile_public': False,
            'show_in_search': False,
            'allow_connection_requests': True
        }
    }
    
    # Only set fields that don't exist
    updates = {}
    for key, value in defaults.items():
        if key not in user_data:
            updates[key] = value
    
    if updates:
        db.collection('users').document(uid).update(updates)


def calculate_academic_progress(user_data: dict, uid: str = None) -> dict:
    """
    Calculate academic progress with 3-tier exclusion system.
    
    Args:
        user_data: User data dictionary
        uid: User ID (optional)
        
    Returns:
        Academic progress metrics dictionary
    """
    purpose = user_data.get('purpose', 'school')
    inst_id = user_data.get('institution_id')
    class_ids = user_data.get('class_ids', [])
    chapters_completed = user_data.get('chapters_completed', {})
    
    # Level 1: Institution Exclusions
    institution_exclusions = {}
    if inst_id:
        try:
            inst_excl_doc = db.collection('institutions').document(inst_id).collection('syllabus_exclusions').document('current').get()
            if inst_excl_doc.exists:
                institution_exclusions = inst_excl_doc.to_dict().get('chapters', {})
        except Exception:
            pass
    
    # Level 2: Class Exclusions (aggregate from all classes)
    class_exclusions = {}
    if class_ids:
        try:
            for class_id in class_ids:
                class_excl_doc = db.collection('classes').document(class_id).collection('syllabus_exclusions').document('current').get()
                if class_excl_doc.exists:
                    class_exclusions.update(class_excl_doc.to_dict().get('chapters', {}))
        except Exception:
            pass
    
    # Level 3: Personal Exclusions
    personal_exclusions = user_data.get('syllabus_exclusions', {}).get('chapters', {})
    
    # Combine all exclusions (higher priority overrides lower)
    all_exclusions = {}
    all_exclusions.update(institution_exclusions)
    all_exclusions.update(class_exclusions)
    all_exclusions.update(personal_exclusions)
    
    # Get syllabus based on purpose
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
            'completed_chapters': 0,
            'excluded_chapters': len(all_exclusions)
        }
    
    # Calculate progress
    chapters_by_subject = {}
    total_chapters = 0
    total_completed = 0
    
    for subject_name, subject_data in syllabus.items():
        chapters = subject_data.get('chapters', {})
        subject_completed_data = chapters_completed.get(subject_name, {})
        subject_valid_count = 0
        subject_completed_count = 0
        
        for chapter_id, chapter_info in chapters.items():
            chapter_key = f"{subject_name}_{chapter_id}"
            
            # Skip if excluded
            if chapter_key in all_exclusions:
                continue
            
            total_chapters += 1
            subject_valid_count += 1
            
            # Check if completed
            if subject_completed_data.get(chapter_id, {}).get('completed', False):
                total_completed += 1
                subject_completed_count += 1
        
        if subject_valid_count > 0:
            chapters_by_subject[subject_name] = {
                'completed': subject_completed_count,
                'total': subject_valid_count,
                'percentage': round((subject_completed_count / subject_valid_count) * 100, 1)
            }
    
    overall_percentage = round((total_completed / total_chapters) * 100, 1) if total_chapters > 0 else 0
    
    return {
        'overall': overall_percentage,
        'by_subject': chapters_by_subject,
        'total_chapters': total_chapters,
        'completed_chapters': total_completed,
        'excluded_chapters': len(all_exclusions)
    }


def calculate_average_percentage(results: list) -> float:
    """
    Calculate average percentage from exam results.
    
    Args:
        results: List of exam result dictionaries
        
    Returns:
        Average percentage rounded to 1 decimal place
    """
    valid_percentages = []
    for r in results:
        try:
            percentage = float(r.get('percentage', 0))
            if 0 <= percentage <= 100:
                valid_percentages.append(percentage)
        except (ValueError, TypeError):
            continue
    
    if not valid_percentages:
        return 0
    
    return round(sum(valid_percentages) / len(valid_percentages), 1)


def get_institution_analytics(institution_id: str, class_ids: list = None) -> dict:
    """
    Get institution analytics including heatmap and at-risk students.
    
    Args:
        institution_id: Institution ID
        class_ids: Optional list of class IDs to filter by
        
    Returns:
        Analytics dictionary with heatmap and at_risk data
    """
    # Get all student IDs in institution (or specific classes)
    all_student_ids = []
    
    if class_ids:
        # Get students from specific classes
        for class_id in class_ids:
            class_doc = db.collection('classes').document(class_id).get()
            if class_doc.exists:
                class_data = class_doc.to_dict()
                all_student_ids.extend(class_data.get('student_ids', []))
    else:
        # Get all students in institution
        institution_doc = db.collection('institutions').document(institution_id).get()
        if institution_doc.exists:
            institution_data = institution_doc.to_dict()
            all_student_ids = institution_data.get('student_ids', [])
    
    # Remove duplicates
    all_student_ids = list(set(all_student_ids))
    
    # Calculate heatmap data (last 30 days study activity)
    heatmap_data = defaultdict(int)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    for sid in all_student_ids:
        try:
            sessions = db.collection('users').document(sid).collection('study_sessions').where('start_time', '>=', thirty_days_ago.isoformat()).stream()
            for s in sessions:
                s_data = s.to_dict()
                h = s_data.get('local_hour')
                if h is not None:
                    heatmap_data[h] += 1
        except Exception:
            continue
    
    # Identify at-risk students
    at_risk_students = []
    for sid in all_student_ids:
        try:
            user_doc = db.collection('users').document(sid).get()
            if not user_doc.exists:
                continue
                
            user_data = user_doc.to_dict()
            
            # Risk factors
            risk_factors = []
            
            # 1. Low study time (less than 30 min/day average over last week)
            recent_sessions = user_data.get('recent_sessions', [])
            if len(recent_sessions) < 7:
                risk_factors.append('Low study frequency')
            
            # 2. Declining performance
            results = user_data.get('exam_results', [])
            if len(results) >= 2:
                sorted_res = sorted(results, key=lambda x: x.get('date', ''), reverse=True)
                try:
                    recent_avg = calculate_average_percentage(sorted_res[:2])
                    older_avg = calculate_average_percentage(sorted_res[2:4])
                    if recent_avg < older_avg - 10:
                        risk_factors.append('Declining performance')
                except:
                    pass
            
            # 3. No recent activity
            last_session = user_data.get('last_study_session')
            if last_session:
                days = (datetime.utcnow() - datetime.fromisoformat(last_session)).days
                if days > 7:
                    risk_factors.append('Inactive for 7+ days')
            else:
                risk_factors.append('No study sessions recorded')
            
            if risk_factors:
                at_risk_students.append({
                    'uid': sid,
                    'name': user_data.get('name', 'Unknown'),
                    'risk_factors': risk_factors,
                    'risk_level': len(risk_factors)
                })
                
        except Exception:
            continue
    
    return {
        'heatmap': dict(heatmap_data),
        'at_risk': at_risk_students
    }
