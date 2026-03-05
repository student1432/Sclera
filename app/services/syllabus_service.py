"""
Syllabus service layer.
Handles syllabus management, chapter progress tracking, and exclusion system.
"""

from templates.academic_data import get_syllabus, get_available_subjects, ACADEMIC_SYLLABI
from app.models.firestore_helpers import get_document, update_document, set_document, get_subcollection
from app.models.profile import calculate_academic_progress
from firebase_config import db
from typing import Dict, List, Optional, Tuple


def get_user_syllabus(user_data: Dict) -> Dict:
    """
    Get syllabus for a user based on their purpose and profile.
    
    Args:
        user_data: User data dictionary
        
    Returns:
        Syllabus dictionary or empty dict if not found
    """
    purpose = user_data.get('purpose', 'school')
    syllabus_purpose = {
        'school': 'school',
        'exam_prep': 'exam',
        'after_tenth': 'after_tenth'
    }.get(purpose, purpose)
    
    if purpose == 'school' and user_data.get('school'):
        school = user_data['school']
        subject_combination = school.get('subject_combination')
        return get_syllabus(syllabus_purpose, school.get('board'), school.get('grade'), subject_combination=subject_combination)
    elif purpose == 'exam_prep' and user_data.get('exam'):
        return get_syllabus(syllabus_purpose, user_data['exam'].get('type'))
    elif purpose == 'after_tenth' and user_data.get('after_tenth'):
        at = user_data['after_tenth']
        return get_syllabus(syllabus_purpose, 'CBSE', at.get('grade'), at.get('subjects', []))
    
    return {}


def get_chapter_progress(user_id: str, subject: str, chapter_id: str) -> Optional[Dict]:
    """
    Get progress data for a specific chapter.
    
    Args:
        user_id: User ID
        subject: Subject name
        chapter_id: Chapter ID
        
    Returns:
        Chapter progress data or None if not found
    """
    user_data = get_document('users', user_id)
    if not user_data:
        return None
    
    chapters_completed = user_data.get('chapters_completed', {})
    subject_progress = chapters_completed.get(subject, {})
    return subject_progress.get(chapter_id)


def update_chapter_progress(
    user_id: str,
    subject: str,
    chapter_id: str,
    completed: bool,
    completion_time: Optional[str] = None,
    notes: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Update progress for a specific chapter.
    
    Args:
        user_id: User ID
        subject: Subject name
        chapter_id: Chapter ID
        completed: Whether the chapter is completed
        completion_time: Completion timestamp (optional)
        notes: Chapter notes (optional)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        user_data = get_document('users', user_id)
        if not user_data:
            return False, 'User not found'
        
        chapters_completed = user_data.get('chapters_completed', {})
        
        # Ensure subject exists
        if subject not in chapters_completed:
            chapters_completed[subject] = {}
        
        # Update chapter progress
        chapter_data = chapters_completed[subject].get(chapter_id, {})
        chapter_data['completed'] = completed
        
        if completed and not chapter_data.get('completed_at'):
            chapter_data['completed_at'] = completion_time or get_current_timestamp()
        
        if notes:
            chapter_data['notes'] = notes
        
        chapters_completed[subject][chapter_id] = chapter_data
        
        # Update user document
        update_document('users', user_id, {'chapters_completed': chapters_completed})
        
        return True, 'Chapter progress updated successfully'
        
    except Exception as e:
        return False, f'Error updating chapter progress: {str(e)}'


def get_syllabus_exclusions(user_id: str) -> Dict:
    """
    Get all syllabus exclusions for a user (institution, class, personal).
    
    Args:
        user_id: User ID
        
    Returns:
        Dictionary of all exclusions combined
    """
    user_data = get_document('users', user_id)
    if not user_data:
        return {}
    
    # Get institution exclusions
    institution_exclusions = {}
    institution_id = user_data.get('institution_id')
    if institution_id:
        try:
            inst_excl_doc = db.collection('institutions').document(institution_id).collection('syllabus_exclusions').document('current').get()
            if inst_excl_doc.exists:
                institution_exclusions = inst_excl_doc.to_dict().get('chapters', {})
        except Exception:
            pass
    
    # Get class exclusions
    class_exclusions = {}
    class_ids = user_data.get('class_ids', [])
    if class_ids:
        try:
            for class_id in class_ids:
                class_excl_doc = db.collection('classes').document(class_id).collection('syllabus_exclusions').document('current').get()
                if class_excl_doc.exists:
                    class_exclusions.update(class_excl_doc.to_dict().get('chapters', {}))
        except Exception:
            pass
    
    # Get personal exclusions
    personal_exclusions = user_data.get('syllabus_exclusions', {}).get('chapters', {})
    
    # Combine all exclusions (higher priority overrides lower)
    all_exclusions = {}
    all_exclusions.update(institution_exclusions)
    all_exclusions.update(class_exclusions)
    all_exclusions.update(personal_exclusions)
    
    return {
        'institution': institution_exclusions,
        'class': class_exclusions,
        'personal': personal_exclusions,
        'combined': all_exclusions
    }


def add_personal_exclusion(user_id: str, subject: str, chapter_id: str, reason: str = '') -> Tuple[bool, str]:
    """
    Add a personal syllabus exclusion.
    
    Args:
        user_id: User ID
        subject: Subject name
        chapter_id: Chapter ID
        reason: Reason for exclusion
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        user_data = get_document('users', user_id)
        if not user_data:
            return False, 'User not found'
        
        # Get or create syllabus exclusions
        syllabus_exclusions = user_data.get('syllabus_exclusions', {})
        if 'chapters' not in syllabus_exclusions:
            syllabus_exclusions['chapters'] = {}
        
        # Add exclusion
        chapter_key = f"{subject}_{chapter_id}"
        syllabus_exclusions['chapters'][chapter_key] = {
            'reason': reason,
            'added_at': get_current_timestamp(),
            'added_by': 'personal'
        }
        
        # Update user document
        update_document('users', user_id, {'syllabus_exclusions': syllabus_exclusions})
        
        return True, 'Personal exclusion added successfully'
        
    except Exception as e:
        return False, f'Error adding personal exclusion: {str(e)}'


def remove_personal_exclusion(user_id: str, subject: str, chapter_id: str) -> Tuple[bool, str]:
    """
    Remove a personal syllabus exclusion.
    
    Args:
        user_id: User ID
        subject: Subject name
        chapter_id: Chapter ID
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        user_data = get_document('users', user_id)
        if not user_data:
            return False, 'User not found'
        
        syllabus_exclusions = user_data.get('syllabus_exclusions', {})
        chapters = syllabus_exclusions.get('chapters', {})
        
        chapter_key = f"{subject}_{chapter_id}"
        if chapter_key in chapters:
            del chapters[chapter_key]
            
            # Update user document
            update_document('users', user_id, {'syllabus_exclusions': syllabus_exclusions})
            return True, 'Personal exclusion removed successfully'
        else:
            return False, 'Exclusion not found'
            
    except Exception as e:
        return False, f'Error removing personal exclusion: {str(e)}'


def get_subject_progress(user_id: str, subject: str) -> Dict:
    """
    Get detailed progress for a specific subject.
    
    Args:
        user_id: User ID
        subject: Subject name
        
    Returns:
        Subject progress dictionary
    """
    user_data = get_document('users', user_id)
    if not user_data:
        return {}
    
    syllabus = get_user_syllabus(user_data)
    if subject not in syllabus:
        return {'error': 'Subject not found in syllabus'}
    
    subject_data = syllabus[subject]
    chapters = subject_data.get('chapters', {})
    chapters_completed = user_data.get('chapters_completed', {}).get(subject, {})
    
    # Get exclusions
    exclusions = get_syllabus_exclusions(user_id)
    combined_exclusions = exclusions['combined']
    
    progress_data = {
        'subject': subject,
        'total_chapters': len(chapters),
        'completed_chapters': 0,
        'excluded_chapters': 0,
        'remaining_chapters': 0,
        'chapters': []
    }
    
    for chapter_id, chapter_info in chapters.items():
        chapter_key = f"{subject}_{chapter_id}"
        chapter_progress = chapters_completed.get(chapter_id, {})
        
        chapter_data = {
            'id': chapter_id,
            'title': chapter_info.get('title', ''),
            'completed': chapter_progress.get('completed', False),
            'completed_at': chapter_progress.get('completed_at'),
            'notes': chapter_progress.get('notes', ''),
            'excluded': chapter_key in combined_exclusions,
            'exclusion_reason': combined_exclusions.get(chapter_key, {}).get('reason', '') if chapter_key in combined_exclusions else None
        }
        
        progress_data['chapters'].append(chapter_data)
        
        if chapter_data['completed']:
            progress_data['completed_chapters'] += 1
        elif chapter_data['excluded']:
            progress_data['excluded_chapters'] += 1
        else:
            progress_data['remaining_chapters'] += 1
    
    # Calculate percentage
    valid_chapters = progress_data['total_chapters'] - progress_data['excluded_chapters']
    if valid_chapters > 0:
        progress_data['completion_percentage'] = round((progress_data['completed_chapters'] / valid_chapters) * 100, 1)
    else:
        progress_data['completion_percentage'] = 0
    
    return progress_data


def get_available_subjects_for_user(user_data: Dict) -> List[str]:
    """
    Get list of available subjects for a user.
    
    Args:
        user_data: User data dictionary
        
    Returns:
        List of subject names
    """
    syllabus = get_user_syllabus(user_data)
    return list(syllabus.keys())


def get_overall_progress_summary(user_id: str) -> Dict:
    """
    Get overall progress summary for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        Overall progress summary
    """
    user_data = get_document('users', user_id)
    if not user_data:
        return {}
    
    return calculate_academic_progress(user_data, user_id)


def get_current_timestamp() -> str:
    """
    Get current timestamp in ISO format.
    
    Returns:
        ISO format timestamp string
    """
    from datetime import datetime
    return datetime.utcnow().isoformat()
