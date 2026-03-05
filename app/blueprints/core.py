"""
Core application routes.
Handles basic navigation, landing pages, and utility routes.
"""

from flask import Blueprint, render_template, redirect, url_for, session, flash
from app.models.auth import require_login
from firebase_config import db
from firebase_admin import firestore
from utils import logger
from datetime import datetime

core_bp = Blueprint('core', __name__)


@core_bp.route('/')
def index():
    """Main index route - redirect based on authentication status."""
    if 'uid' in session:
        return redirect(url_for('dashboard.profile'))
    return redirect(url_for('core.landing'))


@core_bp.route('/landing')
def landing():
    """Landing page for non-authenticated users."""
    return render_template('landing.html')


@core_bp.route('/institution/gateway')
def institution_gateway():
    """Gateway page for institution users to select their role (Teacher/Admin)."""
    return render_template('institution_gateway.html')


@core_bp.route('/student/join/class', methods=['GET', 'POST'])
@require_login
def student_join_class():
    """Student joins a class via multi-use invite code (overlay only)."""
    from flask import request
    from firebase_config import db
    from utils import logger
    from datetime import datetime
    
    uid = session['uid']
    
    if request.method == 'POST':
        invite_code = request.form.get('invite_code', '').strip().upper()
        
        if not invite_code:
            flash('Please enter an invite code', 'error')
            return render_template('student_join_class.html')
        
        try:
            # Find class by invite code
            classes_ref = db.collection('classes')
            query = classes_ref.where('invite_code', '==', invite_code).limit(1)
            classes = list(query.stream())
            
            if not classes:
                flash('Invalid invite code', 'error')
                return render_template('student_join_class.html')
            
            class_doc = classes[0]
            class_id = class_doc.id
            class_data = class_doc.to_dict()
            
            # Check if already a member
            if uid in class_data.get('student_ids', []):
                flash('You are already a member of this class', 'info')
                return render_template('student_join_class.html')
            
            # Add student to class
            class_ref = db.collection('classes').document(class_id)
            class_ref.update({
                'student_ids': firestore.ArrayUnion([uid]),
                'updated_at': datetime.utcnow()
            })
            
            # Add class to user's profile
            user_ref = db.collection('users').document(uid)
            user_ref.update({
                'class_ids': firestore.ArrayUnion([class_id]),
                'updated_at': datetime.utcnow()
            })
            
            flash('Successfully joined the class!', 'success')
            return redirect(url_for('dashboard.profile'))
            
        except Exception as e:
            logger.error("student_join_class_error", error=str(e), invite_code=invite_code)
            flash('An error occurred while joining the class', 'error')
    
    return render_template('student_join_class.html')
