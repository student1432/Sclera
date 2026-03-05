"""
Personal Academic Dashboard blueprint.
Handles personal dashboard, goals, tasks, study tracking, and performance analytics.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.models.auth import require_login
from app.models.firestore_helpers import get_document
from app.services.dashboard_service import (
    get_dashboard_data, create_goal, update_goal_progress, create_task, complete_task,
    record_study_session, get_study_sessions, calculate_study_streak, generate_study_heatmap
)
from app.services.syllabus_service import get_overall_progress_summary
from utils import logger
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/profile')
@require_login
def profile_dashboard():
    """Main user profile dashboard."""
    uid = session['uid']
    
    # Get comprehensive dashboard data
    dashboard_data = get_dashboard_data(uid)
    
    if not dashboard_data:
        flash('Unable to load dashboard data', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('profile_dashboard.html', **dashboard_data)


@dashboard_bp.route('/goals')
@require_login
def goals():
    """Goals management page."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    goals = user_data.get('goals', [])
    
    # Sort goals: active first, then completed
    active_goals = [g for g in goals if not g.get('completed', False)]
    completed_goals = [g for g in goals if g.get('completed', False)]
    
    return render_template('goals.html',
                         active_goals=active_goals,
                         completed_goals=completed_goals,
                         user_data=user_data)


@dashboard_bp.route('/goals/create', methods=['POST'])
@require_login
def create_goal_endpoint():
    """Create a new goal."""
    uid = session['uid']
    
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    target_date = request.form.get('target_date')
    goal_type = request.form.get('goal_type', 'academic')
    
    if not all([title, target_date]):
        flash('Title and target date are required', 'error')
        return redirect(url_for('dashboard.goals'))
    
    success, message = create_goal(uid, title, description, target_date, goal_type)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('dashboard.goals'))


@dashboard_bp.route('/goals/<goal_id>/update', methods=['POST'])
@require_login
def update_goal_endpoint(goal_id):
    """Update goal progress."""
    uid = session['uid']
    
    progress = request.form.get('progress', type=int)
    if progress is None:
        return jsonify({'success': False, 'message': 'Progress value is required'}), 400
    
    success, message = update_goal_progress(uid, goal_id, progress)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400


@dashboard_bp.route('/tasks')
@require_login
def tasks():
    """Tasks management page."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    tasks = user_data.get('tasks', [])
    
    # Sort tasks: pending first, then completed
    pending_tasks = [t for t in tasks if not t.get('completed', False)]
    completed_tasks = [t for t in tasks if t.get('completed', False)]
    
    # Sort pending tasks by due date and priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    pending_tasks.sort(key=lambda x: (priority_order.get(x.get('priority', 'medium'), 1), x.get('due_date', '')))
    
    return render_template('tasks.html',
                         pending_tasks=pending_tasks,
                         completed_tasks=completed_tasks,
                         user_data=user_data)


@dashboard_bp.route('/tasks/create', methods=['POST'])
@require_login
def create_task_endpoint():
    """Create a new task."""
    uid = session['uid']
    
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    due_date = request.form.get('due_date')
    priority = request.form.get('priority', 'medium')
    subject = request.form.get('subject')
    
    if not all([title, due_date]):
        flash('Title and due date are required', 'error')
        return redirect(url_for('dashboard.tasks'))
    
    success, message = create_task(uid, title, description, due_date, priority, subject)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('dashboard.tasks'))


@dashboard_bp.route('/tasks/<task_id>/complete', methods=['POST'])
@require_login
def complete_task_endpoint(task_id):
    """Mark a task as completed."""
    uid = session['uid']
    
    success, message = complete_task(uid, task_id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('dashboard.tasks'))


@dashboard_bp.route('/timer')
@require_login
def study_timer():
    """Study timer page."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get recent study sessions
    recent_sessions = get_study_sessions(uid, limit=10)
    
    return render_template('study_timer.html',
                         recent_sessions=recent_sessions,
                         user_data=user_data)


@dashboard_bp.route('/timer/start', methods=['POST'])
@require_login
def start_study_session():
    """Start a new study session."""
    uid = session['uid']
    
    start_time = request.form.get('start_time')
    subject = request.form.get('subject')
    
    if not start_time:
        return jsonify({'success': False, 'message': 'Start time is required'}), 400
    
    # Store session start in session for later completion
    session['study_session'] = {
        'start_time': start_time,
        'subject': subject
    }
    
    return jsonify({'success': True, 'message': 'Study session started'})


@dashboard_bp.route('/timer/stop', methods=['POST'])
@require_login
def stop_study_session():
    """Stop the current study session."""
    uid = session['uid']
    
    end_time = request.form.get('end_time')
    notes = request.form.get('notes', '')
    
    if not end_time:
        return jsonify({'success': False, 'message': 'End time is required'}), 400
    
    # Get session data from Flask session
    session_data = session.get('study_session')
    if not session_data:
        return jsonify({'success': False, 'message': 'No active study session found'}), 400
    
    start_time = session_data['start_time']
    subject = session_data.get('subject')
    
    # Record the study session
    success, message = record_study_session(uid, start_time, end_time, subject, notes)
    
    if success:
        # Clear session data
        session.pop('study_session', None)
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400


@dashboard_bp.route('/analytics')
@require_login
def analytics():
    """Study analytics and performance page."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get dashboard data for analytics
    dashboard_data = get_dashboard_data(uid)
    
    # Get detailed study sessions for charts
    study_sessions = get_study_sessions(uid, limit=100)
    
    # Generate heatmap data
    heatmap_data = generate_study_heatmap(study_sessions)
    
    return render_template('analytics.html',
                         dashboard_data=dashboard_data,
                         study_sessions=study_sessions,
                         heatmap_data=heatmap_data,
                         user_data=user_data)


@dashboard_bp.route('/exams')
@require_login
def exams():
    """Exam results and performance page."""
    uid = session['uid']
    user_data = get_document('users', uid)
    
    if not user_data:
        flash('User data not found', 'error')
        return redirect(url_for('auth.login'))
    
    exam_results = user_data.get('exam_results', [])
    
    # Sort by date (most recent first)
    exam_results.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    return render_template('exams.html',
                         exam_results=exam_results,
                         user_data=user_data)


@dashboard_bp.route('/api/dashboard')
@require_login
def api_dashboard():
    """API endpoint to get dashboard data."""
    uid = session['uid']
    
    dashboard_data = get_dashboard_data(uid)
    return jsonify(dashboard_data)


@dashboard_bp.route('/api/study_sessions')
@require_login
def api_study_sessions():
    """API endpoint to get study sessions."""
    uid = session['uid']
    
    limit = request.args.get('limit', type=int, default=50)
    subject = request.args.get('subject')
    
    sessions = get_study_sessions(uid, limit=limit, subject=subject)
    return jsonify({'sessions': sessions})


@dashboard_bp.route('/api/heatmap')
@require_login
def api_heatmap():
    """API endpoint to get study heatmap data."""
    uid = session['uid']
    
    study_sessions = get_study_sessions(uid, limit=1000)
    heatmap_data = generate_study_heatmap(study_sessions)
    
    return jsonify(heatmap_data)


@dashboard_bp.route('/api/streak')
@require_login
def api_streak():
    """API endpoint to get current study streak."""
    uid = session['uid']
    
    study_sessions = get_study_sessions(uid, limit=365)
    streak = calculate_study_streak(study_sessions)
    
    return jsonify({'streak': streak})
