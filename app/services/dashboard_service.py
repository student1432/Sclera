"""
Dashboard service layer.
Handles personal academic dashboard functionality including goals, tasks, study time, and performance analytics.
"""

from app.models.firestore_helpers import get_document, update_document, set_document, add_to_subcollection, query_collection
from app.models.profile import calculate_average_percentage
from firebase_config import db
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import calendar


def get_dashboard_data(user_id: str) -> Dict:
    """
    Get comprehensive dashboard data for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        Dashboard data dictionary
    """
    user_data = get_document('users', user_id)
    if not user_data:
        return {}
    
    # Get study sessions
    study_sessions = get_study_sessions(user_id, limit=50)
    
    # Calculate metrics
    total_study_time = user_data.get('time_studied', 0)
    study_streak = calculate_study_streak(study_sessions)
    weekly_goal_progress = calculate_weekly_goal_progress(user_id, study_sessions)
    
    # Get goals and tasks
    goals = user_data.get('goals', [])
    tasks = user_data.get('tasks', [])
    
    # Get exam results
    exam_results = user_data.get('exam_results', [])
    recent_results = get_recent_exam_results(exam_results, limit=5)
    
    # Get study heatmap data
    heatmap_data = generate_study_heatmap(study_sessions)
    
    return {
        'user_profile': {
            'name': user_data.get('name', ''),
            'purpose': user_data.get('purpose', ''),
            'study_preferences': user_data.get('study_preferences', {}),
        },
        'study_metrics': {
            'total_study_time': total_study_time,
            'study_streak': study_streak,
            'weekly_goal_progress': weekly_goal_progress,
            'sessions_this_week': len([s for s in study_sessions if is_this_week(s.get('start_time'))]),
            'average_session_length': calculate_average_session_length(study_sessions)
        },
        'goals': {
            'total': len(goals),
            'completed': len([g for g in goals if g.get('completed', False)]),
            'active': len([g for g in goals if not g.get('completed', False)]),
            'recent_goals': goals[:5]  # Most recent 5 goals
        },
        'tasks': {
            'total': len(tasks),
            'completed': len([t for t in tasks if t.get('completed', False)]),
            'pending': len([t for t in tasks if not t.get('completed', False)]),
            'due_soon': get_tasks_due_soon(tasks)
        },
        'performance': {
            'recent_exams': recent_results,
            'average_score': calculate_average_percentage(exam_results),
            'performance_trend': calculate_performance_trend(exam_results)
        },
        'heatmap': heatmap_data,
        'recent_activity': get_recent_activity(user_id, limit=10)
    }


def create_goal(user_id: str, title: str, description: str, target_date: str, goal_type: str = 'academic') -> Tuple[bool, str]:
    """
    Create a new goal for a user.
    
    Args:
        user_id: User ID
        title: Goal title
        description: Goal description
        target_date: Target completion date (ISO format)
        goal_type: Type of goal (academic, personal, study)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        user_data = get_document('users', user_id)
        if not user_data:
            return False, 'User not found'
        
        goals = user_data.get('goals', [])
        
        new_goal = {
            'id': generate_goal_id(),
            'title': title,
            'description': description,
            'target_date': target_date,
            'goal_type': goal_type,
            'completed': False,
            'created_at': get_current_timestamp(),
            'completed_at': None,
            'progress': 0
        }
        
        goals.append(new_goal)
        update_document('users', user_id, {'goals': goals})
        
        return True, 'Goal created successfully'
        
    except Exception as e:
        return False, f'Error creating goal: {str(e)}'


def update_goal_progress(user_id: str, goal_id: str, progress: int) -> Tuple[bool, str]:
    """
    Update progress for a goal.
    
    Args:
        user_id: User ID
        goal_id: Goal ID
        progress: Progress percentage (0-100)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        user_data = get_document('users', user_id)
        if not user_data:
            return False, 'User not found'
        
        goals = user_data.get('goals', [])
        goal_found = False
        
        for goal in goals:
            if goal['id'] == goal_id:
                goal['progress'] = max(0, min(100, progress))
                goal['completed'] = progress >= 100
                if goal['completed'] and not goal.get('completed_at'):
                    goal['completed_at'] = get_current_timestamp()
                goal_found = True
                break
        
        if not goal_found:
            return False, 'Goal not found'
        
        update_document('users', user_id, {'goals': goals})
        return True, 'Goal progress updated successfully'
        
    except Exception as e:
        return False, f'Error updating goal progress: {str(e)}'


def create_task(user_id: str, title: str, description: str, due_date: str, priority: str = 'medium', subject: str = None) -> Tuple[bool, str]:
    """
    Create a new task for a user.
    
    Args:
        user_id: User ID
        title: Task title
        description: Task description
        due_date: Due date (ISO format)
        priority: Priority level (low, medium, high)
        subject: Related subject (optional)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        user_data = get_document('users', user_id)
        if not user_data:
            return False, 'User not found'
        
        tasks = user_data.get('tasks', [])
        
        new_task = {
            'id': generate_task_id(),
            'title': title,
            'description': description,
            'due_date': due_date,
            'priority': priority,
            'subject': subject,
            'completed': False,
            'created_at': get_current_timestamp(),
            'completed_at': None
        }
        
        tasks.append(new_task)
        update_document('users', user_id, {'tasks': tasks})
        
        return True, 'Task created successfully'
        
    except Exception as e:
        return False, f'Error creating task: {str(e)}'


def complete_task(user_id: str, task_id: str) -> Tuple[bool, str]:
    """
    Mark a task as completed.
    
    Args:
        user_id: User ID
        task_id: Task ID
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        user_data = get_document('users', user_id)
        if not user_data:
            return False, 'User not found'
        
        tasks = user_data.get('tasks', [])
        task_found = False
        
        for task in tasks:
            if task['id'] == task_id:
                task['completed'] = True
                task['completed_at'] = get_current_timestamp()
                task_found = True
                break
        
        if not task_found:
            return False, 'Task not found'
        
        update_document('users', user_id, {'tasks': tasks})
        return True, 'Task completed successfully'
        
    except Exception as e:
        return False, f'Error completing task: {str(e)}'


def record_study_session(user_id: str, start_time: str, end_time: str, subject: str = None, notes: str = None) -> Tuple[bool, str]:
    """
    Record a study session for a user.
    
    Args:
        user_id: User ID
        start_time: Session start time (ISO format)
        end_time: Session end time (ISO format)
        subject: Subject studied (optional)
        notes: Session notes (optional)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Calculate session duration
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
        
        if duration_minutes <= 0:
            return False, 'Invalid session duration'
        
        # Create session data
        session_data = {
            'start_time': start_time,
            'end_time': end_time,
            'duration_minutes': duration_minutes,
            'subject': subject,
            'notes': notes,
            'created_at': get_current_timestamp()
        }
        
        # Add to study sessions subcollection
        session_id = add_to_subcollection('users', user_id, 'study_sessions', session_data)
        
        if not session_id:
            return False, 'Failed to record study session'
        
        # Update user's total study time
        from firebase_config import db
        update_document('users', user_id, {
            'time_studied': db.field_increment(duration_minutes),
            'last_study_session': start_time
        })
        
        return True, 'Study session recorded successfully'
        
    except Exception as e:
        return False, f'Error recording study session: {str(e)}'


def get_study_sessions(user_id: str, limit: int = None, subject: str = None) -> List[Dict]:
    """
    Get study sessions for a user.
    
    Args:
        user_id: User ID
        limit: Maximum number of sessions to return
        subject: Filter by subject (optional)
        
    Returns:
        List of study session dictionaries
    """
    filters = []
    if subject:
        filters.append(('subject', '==', subject))
    
    sessions = query_collection(
        collection=f'users/{user_id}/study_sessions',
        filters=filters,
        order_by='start_time',
        direction='DESC',
        limit=limit
    )
    
    return sessions


def calculate_study_streak(study_sessions: List[Dict]) -> int:
    """
    Calculate current study streak in days.
    
    Args:
        study_sessions: List of study session dictionaries
        
    Returns:
        Current streak in days
    """
    if not study_sessions:
        return 0
    
    # Get unique study days
    study_days = set()
    for session in study_sessions:
        start_time = session.get('start_time')
        if start_time:
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00')).date()
                study_days.add(dt)
            except:
                continue
    
    if not study_days:
        return 0
    
    # Sort days and calculate streak
    sorted_days = sorted(study_days, reverse=True)
    today = datetime.utcnow().date()
    
    streak = 0
    current_date = today
    
    for day in sorted_days:
        if day == current_date or day == current_date - timedelta(days=1):
            streak += 1
            current_date = day
        else:
            break
    
    return streak


def generate_study_heatmap(study_sessions: List[Dict]) -> Dict:
    """
    Generate study heatmap data for the last 365 days.
    
    Args:
        study_sessions: List of study session dictionaries
        
    Returns:
        Heatmap data dictionary
    """
    heatmap_data = defaultdict(int)
    today = datetime.utcnow().date()
    
    # Initialize all days for the past year
    for i in range(365):
        date = today - timedelta(days=i)
        heatmap_data[date.isoformat()] = 0
    
    # Add study time to each day
    for session in study_sessions:
        start_time = session.get('start_time')
        duration = session.get('duration_minutes', 0)
        
        if start_time and duration > 0:
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00')).date()
                if dt.isoformat() in heatmap_data:
                    heatmap_data[dt.isoformat()] += duration
            except:
                continue
    
    return dict(heatmap_data)


def get_recent_exam_results(exam_results: List[Dict], limit: int = 5) -> List[Dict]:
    """
    Get most recent exam results.
    
    Args:
        exam_results: List of exam result dictionaries
        limit: Maximum number of results to return
        
    Returns:
        List of recent exam results
    """
    # Sort by date (most recent first)
    sorted_results = sorted(exam_results, key=lambda x: x.get('date', ''), reverse=True)
    return sorted_results[:limit]


def calculate_performance_trend(exam_results: List[Dict]) -> str:
    """
    Calculate performance trend based on recent exam results.
    
    Args:
        exam_results: List of exam result dictionaries
        
    Returns:
        Trend string ('improving', 'declining', 'stable')
    """
    if len(exam_results) < 2:
        return 'stable'
    
    # Get last 4 results
    sorted_results = sorted(exam_results, key=lambda x: x.get('date', ''), reverse=True)[:4]
    
    if len(sorted_results) < 2:
        return 'stable'
    
    try:
        # Calculate trend
        scores = [float(r.get('percentage', 0)) for r in sorted_results]
        if len(scores) >= 2:
            recent_avg = sum(scores[:2]) / 2
            older_avg = sum(scores[2:]) / 2 if len(scores) > 2 else recent_avg
            
            if recent_avg > older_avg + 5:
                return 'improving'
            elif recent_avg < older_avg - 5:
                return 'declining'
            else:
                return 'stable'
    except:
        pass
    
    return 'stable'


def get_tasks_due_soon(tasks: List[Dict], days: int = 3) -> List[Dict]:
    """
    Get tasks that are due soon.
    
    Args:
        tasks: List of task dictionaries
        days: Number of days to look ahead
        
    Returns:
        List of tasks due soon
    """
    today = datetime.utcnow().date()
    due_date_limit = today + timedelta(days=days)
    
    due_soon = []
    for task in tasks:
        if task.get('completed', False):
            continue
        
        due_date_str = task.get('due_date')
        if not due_date_str:
            continue
        
        try:
            due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')).date()
            if today <= due_date <= due_date_limit:
                due_soon.append(task)
        except:
            continue
    
    # Sort by due date
    due_soon.sort(key=lambda x: x.get('due_date', ''))
    return due_soon


def get_recent_activity(user_id: str, limit: int = 10) -> List[Dict]:
    """
    Get recent user activity.
    
    Args:
        user_id: User ID
        limit: Maximum number of activities to return
        
    Returns:
        List of recent activities
    """
    activities = []
    
    # Get recent study sessions
    study_sessions = get_study_sessions(user_id, limit=limit)
    for session in study_sessions:
        activities.append({
            'type': 'study_session',
            'description': f"Studied {session.get('subject', 'general')} for {session.get('duration_minutes', 0)} minutes",
            'timestamp': session.get('start_time'),
            'data': session
        })
    
    # Get recent goal completions
    user_data = get_document('users', user_id)
    goals = user_data.get('goals', [])
    recent_goals = [g for g in goals if g.get('completed_at')] if goals else []
    
    for goal in recent_goals:
        activities.append({
            'type': 'goal_completed',
            'description': f"Completed goal: {goal.get('title', '')}",
            'timestamp': goal.get('completed_at'),
            'data': goal
        })
    
    # Sort by timestamp and limit
    activities.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return activities[:limit]


# Helper functions
def generate_goal_id() -> str:
    """Generate a unique goal ID."""
    import uuid
    return f"goal_{uuid.uuid4().hex[:8]}"


def generate_task_id() -> str:
    """Generate a unique task ID."""
    import uuid
    return f"task_{uuid.uuid4().hex[:8]}"


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat()


def is_this_week(timestamp: str) -> bool:
    """Check if a timestamp is from this week."""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        today = datetime.utcnow().date()
        week_start = today - timedelta(days=today.weekday())
        return week_start <= dt.date() <= week_start + timedelta(days=6)
    except:
        return False


def calculate_average_session_length(sessions: List[Dict]) -> float:
    """Calculate average session length in minutes."""
    if not sessions:
        return 0.0
    
    total_duration = sum(s.get('duration_minutes', 0) for s in sessions)
    return round(total_duration / len(sessions), 1)


def calculate_weekly_goal_progress(user_id: str, study_sessions: List[Dict]) -> Dict:
    """Calculate weekly goal progress."""
    user_data = get_document('users', user_id)
    if not user_data:
        return {'target': 0, 'current': 0, 'percentage': 0}
    
    preferences = user_data.get('study_preferences', {})
    weekly_target = preferences.get('weekly_target_minutes', 600)  # Default 10 hours
    
    # Get this week's study time
    this_week_sessions = [s for s in study_sessions if is_this_week(s.get('start_time', ''))]
    this_week_time = sum(s.get('duration_minutes', 0) for s in this_week_sessions)
    
    percentage = min(100, round((this_week_time / weekly_target) * 100, 1)) if weekly_target > 0 else 0
    
    return {
        'target': weekly_target,
        'current': this_week_time,
        'percentage': percentage
    }
