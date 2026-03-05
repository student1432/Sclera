"""
Syllabus/Curriculum Management blueprint.
Handles syllabus browsing, chapter progress tracking, and exclusion management.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.models.auth import require_login
from app.models.firestore_helpers import get_document
from app.services.syllabus_service import (
    get_user_syllabus, get_chapter_progress, update_chapter_progress,
    get_syllabus_exclusions, add_personal_exclusion, remove_personal_exclusion,
    get_subject_progress, get_available_subjects_for_user, get_overall_progress_summary
)
from utils import logger

syllabus_bp = Blueprint('syllabus', __name__)


@syllabus_bp.route('/')
@require_login
def syllabus_home():
    """Main syllabus page showing overall progress and available subjects."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get overall progress summary
    progress_summary = get_overall_progress_summary(uid)
    
    # Get available subjects
    subjects = get_available_subjects_for_user(user_data)
    
    # Get subject-wise progress
    subject_progress = {}
    for subject in subjects:
        subject_progress[subject] = get_subject_progress(uid, subject)
    
    return render_template('syllabus_home.html', 
                         progress_summary=progress_summary,
                         subjects=subjects,
                         subject_progress=subject_progress,
                         user_data=user_data)


@syllabus_bp.route('/subject/<subject>')
@require_login
def subject_detail(subject):
    """Detailed view of a specific subject with chapters and progress."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get subject progress
    progress_data = get_subject_progress(uid, subject)
    
    if 'error' in progress_data:
        flash('Subject not found in your syllabus', 'error')
        return redirect(url_for('syllabus.syllabus_home'))
    
    return render_template('subject_detail.html',
                         subject=subject,
                         progress_data=progress_data,
                         user_data=user_data)


@syllabus_bp.route('/chapter/<subject>/<chapter_id>')
@require_login
def chapter_detail(subject, chapter_id):
    """Detailed view of a specific chapter."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get chapter progress
    chapter_progress = get_chapter_progress(uid, subject, chapter_id)
    
    # Get subject data to find chapter info
    syllabus = get_user_syllabus(user_data)
    subject_data = syllabus.get(subject, {})
    chapters = subject_data.get('chapters', {})
    chapter_info = chapters.get(chapter_id, {})
    
    if not chapter_info:
        flash('Chapter not found', 'error')
        return redirect(url_for('syllabus.subject_detail', subject=subject))
    
    return render_template('chapter_detail.html',
                         subject=subject,
                         chapter_id=chapter_id,
                         chapter_info=chapter_info,
                         chapter_progress=chapter_progress,
                         user_data=user_data)


@syllabus_bp.route('/update_progress', methods=['POST'])
@require_login
def update_progress():
    """Update chapter progress via AJAX."""
    uid = session['uid']
    
    subject = request.form.get('subject')
    chapter_id = request.form.get('chapter_id')
    completed = request.form.get('completed', 'false').lower() == 'true'
    notes = request.form.get('notes', '')
    
    if not all([subject, chapter_id]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    success, message = update_chapter_progress(uid, subject, chapter_id, completed, notes=notes)
    
    if success:
        # Get updated progress data
        progress_data = get_subject_progress(uid, subject)
        return jsonify({
            'success': True,
            'message': message,
            'progress_data': progress_data
        })
    else:
        return jsonify({'success': False, 'message': message}), 400


@syllabus_bp.route('/exclusions')
@require_login
def exclusions():
    """View and manage syllabus exclusions."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get all exclusions
    exclusions_data = get_syllabus_exclusions(uid)
    
    return render_template('exclusions.html',
                         exclusions_data=exclusions_data,
                         user_data=user_data)


@syllabus_bp.route('/exclusions/add', methods=['POST'])
@require_login
def add_exclusion():
    """Add a personal syllabus exclusion."""
    uid = session['uid']
    
    subject = request.form.get('subject')
    chapter_id = request.form.get('chapter_id')
    reason = request.form.get('reason', '')
    
    if not all([subject, chapter_id]):
        flash('Subject and chapter are required', 'error')
        return redirect(url_for('syllabus.exclusions'))
    
    success, message = add_personal_exclusion(uid, subject, chapter_id, reason)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('syllabus.exclusions'))


@syllabus_bp.route('/exclusions/remove', methods=['POST'])
@require_login
def remove_exclusion():
    """Remove a personal syllabus exclusion."""
    uid = session['uid']
    
    subject = request.form.get('subject')
    chapter_id = request.form.get('chapter_id')
    
    if not all([subject, chapter_id]):
        flash('Subject and chapter are required', 'error')
        return redirect(url_for('syllabus.exclusions'))
    
    success, message = remove_personal_exclusion(uid, subject, chapter_id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('syllabus.exclusions'))


@syllabus_bp.route('/progress')
@require_login
def progress_overview():
    """Comprehensive progress overview across all subjects."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get overall progress summary
    progress_summary = get_overall_progress_summary(uid)
    
    # Get detailed progress for each subject
    subjects = get_available_subjects_for_user(user_data)
    subject_details = {}
    
    for subject in subjects:
        subject_details[subject] = get_subject_progress(uid, subject)
    
    return render_template('progress_overview.html',
                         progress_summary=progress_summary,
                         subject_details=subject_details,
                         subjects=subjects,
                         user_data=user_data)


@syllabus_bp.route('/api/subjects')
@require_login
def api_subjects():
    """API endpoint to get available subjects."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        return jsonify({'error': 'User not found'}), 404
    
    subjects = get_available_subjects_for_user(user_data)
    return jsonify({'subjects': subjects})


@syllabus_bp.route('/api/subject/<subject>/progress')
@require_login
def api_subject_progress(subject):
    """API endpoint to get subject progress."""
    uid = session['uid']
    
    progress_data = get_subject_progress(uid, subject)
    
    if 'error' in progress_data:
        return jsonify({'error': progress_data['error']}), 404
    
    return jsonify(progress_data)


@syllabus_bp.route('/api/progress/summary')
@require_login
def api_progress_summary():
    """API endpoint to get overall progress summary."""
    uid = session['uid']
    
    progress_summary = get_overall_progress_summary(uid)
    return jsonify(progress_summary)
