"""
Institution management blueprint.
Handles admin and teacher functionality, class management, and institution analytics.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.models.auth import require_admin_v2, require_teacher_v2, get_admin_profile, get_teacher_profile, generate_code
from app.models.firestore_helpers import get_document, update_document, set_document, delete_document, query_collection
from app.models.profile import get_institution_analytics
from utils import logger
from firebase_config import db
from datetime import datetime

institution_bp = Blueprint('institution', __name__)


@institution_bp.route('/admin/dashboard')
@require_admin_v2
def institution_admin_dashboard():
    """Admin dashboard with institution analytics and management."""
    uid = session['uid']
    admin_profile = get_admin_profile(uid)
    
    if not admin_profile:
        flash('Admin profile not found', 'error')
        return redirect(url_for('auth.login_admin'))
    
    institution_id = admin_profile.get('institution_id')
    
    # Get institution data
    institution_data = get_document('institutions', institution_id)
    
    # Get analytics
    analytics = get_institution_analytics(institution_id)
    
    # Get teachers
    teachers = []
    teacher_ids = institution_data.get('teacher_ids', [])
    for teacher_id in teacher_ids:
        teacher_data = get_document('institution_teachers', teacher_id)
        if teacher_data:
            teachers.append(teacher_data)
    
    # Get students count
    students_count = len(institution_data.get('student_ids', []))
    
    context = {
        'admin_profile': admin_profile,
        'institution': institution_data,
        'teachers': teachers,
        'students_count': students_count,
        'analytics': analytics
    }
    
    return render_template('institution_admin_dashboard.html', **context)


@institution_bp.route('/admin/teacher_invite', methods=['POST'])
@require_admin_v2
def institution_admin_create_teacher_invite():
    """Create a teacher invite code."""
    uid = session['uid']
    admin_profile = get_admin_profile(uid)
    
    if not admin_profile:
        flash('Admin profile not found', 'error')
        return redirect(url_for('auth.login_admin'))
    
    institution_id = admin_profile.get('institution_id')
    
    # Generate invite code
    code = generate_code(8)
    
    # Store invite
    invite_data = {
        'code': code,
        'institution_id': institution_id,
        'created_by': uid,
        'created_at': get_current_timestamp(),
        'used': False,
        'used_by': None,
        'used_at': None
    }
    
    set_document('teacher_invites', code, invite_data)
    
    flash(f'Teacher invite code generated: {code}', 'success')
    return redirect(url_for('institution.institution_admin_dashboard'))


@institution_bp.route('/admin/teachers/<teacher_uid>/disable', methods=['POST'])
@require_admin_v2
def institution_admin_disable_teacher(teacher_uid):
    """Disable a teacher account."""
    uid = session['uid']
    admin_profile = get_admin_profile(uid)
    
    if not admin_profile:
        flash('Admin profile not found', 'error')
        return redirect(url_for('auth.login_admin'))
    
    # Update teacher status
    update_document('institution_teachers', teacher_uid, {'status': 'disabled'})
    
    flash('Teacher disabled.', 'success')
    return redirect(url_for('institution.institution_admin_dashboard'))


@institution_bp.route('/admin/teachers/<teacher_uid>/delete', methods=['POST'])
@require_admin_v2
def institution_admin_delete_teacher(teacher_uid):
    """Delete a teacher account."""
    uid = session['uid']
    admin_profile = get_admin_profile(uid)
    
    if not admin_profile:
        flash('Admin profile not found', 'error')
        return redirect(url_for('auth.login_admin'))
    
    institution_id = admin_profile.get('institution_id')
    
    # Get teacher data
    teacher_data = get_document('institution_teachers', teacher_uid)
    if teacher_data:
        # Remove from institution
        teacher_ids = query_collection('institutions', filters=[('id', '==', institution_id)])
        if teacher_ids:
            institution_data = teacher_ids[0]
            current_teacher_ids = institution_data.get('teacher_ids', [])
            if teacher_uid in current_teacher_ids:
                current_teacher_ids.remove(teacher_uid)
                update_document('institutions', institution_id, {'teacher_ids': current_teacher_ids})
    
    # Delete teacher account
    delete_document('institution_teachers', teacher_uid)
    
    flash('Teacher deleted.', 'success')
    return redirect(url_for('institution.institution_admin_dashboard'))


@institution_bp.route('/admin/students/<student_uid>/remove', methods=['POST'])
@require_admin_v2
def institution_admin_remove_student(student_uid):
    """Remove a student from institution (keeps personal account)."""
    uid = session['uid']
    admin_profile = get_admin_profile(uid)
    
    if not admin_profile:
        flash('Admin profile not found', 'error')
        return redirect(url_for('auth.login_admin'))
    
    institution_id = admin_profile.get('institution_id')
    
    # Get student data
    student_data = get_document('users', student_uid)
    if student_data:
        # Remove from institution
        student_ids = query_collection('institutions', filters=[('id', '==', institution_id)])
        if student_ids:
            institution_data = student_ids[0]
            current_student_ids = institution_data.get('student_ids', [])
            if student_uid in current_student_ids:
                current_student_ids.remove(student_uid)
                update_document('institutions', institution_id, {'student_ids': current_student_ids})
        
        # Remove institution reference from student
        update_document('users', student_uid, {'institution_id': None})
    
    flash('Student removed from institution (personal dashboard preserved).', 'success')
    return redirect(url_for('institution.institution_admin_dashboard'))


@institution_bp.route('/admin/students/<student_uid>/delete', methods=['POST'])
@require_admin_v2
def institution_admin_delete_student(student_uid):
    """Delete a student account completely."""
    uid = session['uid']
    admin_profile = get_admin_profile(uid)
    
    if not admin_profile:
        flash('Admin profile not found', 'error')
        return redirect(url_for('auth.login_admin'))
    
    institution_id = admin_profile.get('institution_id')
    
    # Get student data
    student_data = get_document('users', student_uid)
    if student_data:
        # Remove from institution
        student_ids = query_collection('institutions', filters=[('id', '==', institution_id)])
        if student_ids:
            institution_data = student_ids[0]
            current_student_ids = institution_data.get('student_ids', [])
            if student_uid in current_student_ids:
                current_student_ids.remove(student_uid)
                update_document('institutions', institution_id, {'student_ids': current_student_ids})
    
    # Delete student account
    delete_document('users', student_uid)
    
    flash('Student deleted (account disabled).', 'success')
    return redirect(url_for('institution.institution_admin_dashboard'))


@institution_bp.route('/teacher/dashboard')
@require_teacher_v2
def institution_teacher_dashboard():
    """Teacher dashboard with classes and student management."""
    uid = session['uid']
    teacher_profile = get_teacher_profile(uid)
    
    if not teacher_profile:
        flash('Teacher profile not found', 'error')
        return redirect(url_for('auth.login_teacher'))
    
    institution_id = teacher_profile.get('institution_id')
    
    # Get institution data
    institution_data = get_document('institutions', institution_id)
    
    # Get teacher's classes
    classes = query_collection('classes', filters=[('teacher_id', '==', uid)])
    
    return render_template('institution_teacher_dashboard.html',
                         teacher_profile=teacher_profile,
                         institution=institution_data,
                         classes=classes)


@institution_bp.route('/teacher/join', methods=['GET', 'POST'])
@require_teacher_v2
def institution_teacher_join():
    """Teacher joins an institution using invite code."""
    uid = session['uid']
    teacher_profile = get_teacher_profile(uid)
    
    if not teacher_profile:
        flash('Teacher profile not found', 'error')
        return redirect(url_for('auth.login_teacher'))
    
    if request.method == 'POST':
        invite_code = request.form.get('invite_code', '').strip().upper()
        
        if not invite_code:
            flash('Invite code is required', 'error')
            return redirect(url_for('institution.institution_teacher_join'))
        
        # Get invite
        invite_data = get_document('teacher_invites', invite_code)
        if not invite_data or invite_data.get('used'):
            flash('Invalid or used invite code', 'error')
            return redirect(url_for('institution.institution_teacher_join'))
        
        institution_id = invite_data.get('institution_id')
        
        # Update teacher with institution
        update_document('institution_teachers', uid, {
            'institution_id': institution_id,
            'status': 'active'
        })
        
        # Add teacher to institution
        institution_data = get_document('institutions', institution_id)
        if institution_data:
            teacher_ids = institution_data.get('teacher_ids', [])
            if uid not in teacher_ids:
                teacher_ids.append(uid)
                update_document('institutions', institution_id, {'teacher_ids': teacher_ids})
        
        # Mark invite as used
        update_document('teacher_invites', invite_code, {
            'used': True,
            'used_by': uid,
            'used_at': get_current_timestamp()
        })
        
        flash('Successfully joined institution!', 'success')
        return redirect(url_for('institution.institution_teacher_dashboard'))
    
    return render_template('institution_teacher_join.html', profile=teacher_profile)


@institution_bp.route('/teacher/classes/create', methods=['GET', 'POST'])
@require_teacher_v2
def institution_teacher_create_class():
    """Teacher creates a class and generates multi-use invite code."""
    uid = session['uid']
    teacher_profile = get_teacher_profile(uid)
    
    if not teacher_profile:
        flash('Teacher profile not found', 'error')
        return redirect(url_for('auth.login_teacher'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        grade = request.form.get('grade')
        subject = request.form.get('subject')
        description = request.form.get('description', '').strip()
        
        if not all([name, grade, subject]):
            flash('Name, grade, and subject are required', 'error')
            return redirect(url_for('institution.institution_teacher_create_class'))
        
        institution_id = teacher_profile.get('institution_id')
        
        # Generate class invite code
        invite_code = generate_code(6)
        
        # Create class
        class_id = f"class_{uid}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        class_data = {
            'id': class_id,
            'name': name,
            'grade': grade,
            'subject': subject,
            'description': description,
            'teacher_id': uid,
            'teacher_name': teacher_profile.get('name', ''),
            'institution_id': institution_id,
            'invite_code': invite_code,
            'student_ids': [],
            'created_at': get_current_timestamp(),
            'status': 'active'
        }
        
        set_document('classes', class_id, class_data)
        
        flash(f'Class created successfully! Invite code: {invite_code}', 'success')
        return redirect(url_for('institution.institution_teacher_classes'))
    
    return render_template('institution_teacher_create_class.html', profile=teacher_profile)


@institution_bp.route('/teacher/classes')
@require_teacher_v2
def institution_teacher_classes():
    """List teacher's classes with invite codes and actions."""
    uid = session['uid']
    teacher_profile = get_teacher_profile(uid)
    
    if not teacher_profile:
        flash('Teacher profile not found', 'error')
        return redirect(url_for('auth.login_teacher'))
    
    # Get teacher's classes
    classes = query_collection('classes', filters=[('teacher_id', '==', uid)])
    
    return render_template('institution_teacher_classes.html',
                         classes=classes,
                         profile=teacher_profile)


@institution_bp.route('/teacher/class/<class_id>/delete', methods=['POST'])
@require_teacher_v2
def delete_class(class_id):
    """Delete a class and all associated data."""
    uid = session['uid']
    teacher_profile = get_teacher_profile(uid)
    
    if not teacher_profile:
        flash('Teacher profile not found', 'error')
        return redirect(url_for('auth.login_teacher'))
    
    # Verify ownership
    class_data = get_document('classes', class_id)
    if not class_data or class_data.get('teacher_id') != uid:
        flash('Class not found or access denied', 'error')
        return redirect(url_for('institution.institution_teacher_classes'))
    
    # Remove class from all students
    student_ids = class_data.get('student_ids', [])
    for student_id in student_ids:
        student_data = get_document('users', student_id)
        if student_data:
            class_ids = student_data.get('class_ids', [])
            if class_id in class_ids:
                class_ids.remove(class_id)
                update_document('users', student_id, {'class_ids': class_ids})
    
    # Delete class
    delete_document('classes', class_id)
    
    flash('Class deleted successfully', 'success')
    return redirect(url_for('institution.institution_teacher_classes'))


# Helper function
def get_current_timestamp():
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat()
