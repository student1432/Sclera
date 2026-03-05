"""
File serving routes.
Handles uploads, profile pictures, banners, and file downloads.
"""

from flask import Blueprint, send_from_directory, abort, request, jsonify, session, redirect, url_for, flash, render_template
from app.models.auth import require_login
from app.models.firestore_helpers import get_document
from utils import logger, file_upload_security
from firebase_config import db
from firebase_admin import firestore
from datetime import datetime
import os
from werkzeug.utils import secure_filename

files_bp = Blueprint('files', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov'
}

# Upload folders
UPLOAD_FOLDER = 'uploads'
PROFILE_PICTURES_FOLDER = 'static/profile_pictures'
PROFILE_BANNERS_FOLDER = 'static/profile_banners'


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@files_bp.route('/uploads/<filename>')
@require_login
def serve_upload(filename):
    """Serve uploaded files from local storage."""
    try:
        # Validate filename to prevent directory traversal
        if not file_upload_security.validate_filename(filename):
            abort(400)
        
        # Check if user has access to this file
        uid = session['uid']
        file_doc = db.collection('uploads').where('filename', '==', filename).where('uploaded_by', '==', uid).limit(1).get()
        
        if not file_doc:
            abort(404)
        
        return send_from_directory(UPLOAD_FOLDER, filename)
    
    except FileNotFoundError:
        abort(404)
    except Exception as e:
        logger.error(f"File serving error: {str(e)}")
        abort(500)


@files_bp.route('/profile_pictures/<filename>')
def serve_profile_picture(filename):
    """Serve profile pictures from local storage."""
    try:
        # Validate filename
        if not file_upload_security.validate_filename(filename):
            abort(400)
        
        return send_from_directory(PROFILE_PICTURES_FOLDER, filename)
    
    except FileNotFoundError:
        # Return default profile picture
        return send_from_directory(
            os.path.join('static'),
            'default-profile.png'
        ), 404


@files_bp.route('/profile_banners/<filename>')
def serve_profile_banner(filename):
    """Serve profile banners from local storage."""
    try:
        # Validate filename
        if not file_upload_security.validate_filename(filename):
            abort(400)
        
        return send_from_directory(PROFILE_BANNERS_FOLDER, filename)
    
    except FileNotFoundError:
        abort(404)


@files_bp.route('/download/class_file/<file_id>', methods=['GET'])
@require_login
def download_class_file(file_id):
    """Download a class file."""
    try:
        uid = session['uid']
        
        # Get file document
        file_doc = db.collection('class_files').document(file_id).get()
        if not file_doc.exists:
            abort(404)
        
        file_data = file_doc.to_dict()
        
        # Check if user has access (is member of the class)
        class_id = file_data.get('class_id')
        user_data = get_document('users', uid)
        
        if not user_data or class_id not in user_data.get('class_ids', []):
            abort(403)
        
        filename = file_data.get('filename')
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        if not os.path.exists(filepath):
            abort(404)
        
        return send_from_directory(
            os.path.dirname(filepath),
            os.path.basename(filepath),
            as_attachment=True,
            download_name=file_data.get('original_filename', filename)
        )
    
    except Exception as e:
        logger.error(f"Download class file error: {str(e)}")
        abort(500)


@files_bp.route('/student/class/files', methods=['GET'])
@require_login
def student_files():
    """View files for student's classes."""
    try:
        uid = session['uid']
        user_data = get_document('users', uid)
        
        if not user_data:
            flash('User profile not found', 'error')
            return redirect(url_for('dashboard.profile'))
        
        class_ids = user_data.get('class_ids', [])
        if not class_ids:
            flash('You are not enrolled in any classes', 'info')
            return render_template('student_files.html', files=[])
        
        # Get all files from student's classes
        all_files = []
        for class_id in class_ids:
            class_files = db.collection('class_files').where('class_id', '==', class_id).stream()
            
            for file_doc in class_files:
                file_data = file_doc.to_dict()
                file_data['id'] = file_doc.id
                
                # Get class info
                class_doc = db.collection('classes').document(class_id).get()
                if class_doc.exists:
                    class_info = class_doc.to_dict()
                    file_data['class_name'] = class_info.get('name', 'Unknown Class')
                
                all_files.append(file_data)
        
        # Sort by upload date
        all_files.sort(key=lambda x: x.get('uploaded_at', datetime.min), reverse=True)
        
        return render_template('student_files.html', files=all_files, user_data=user_data)
    
    except Exception as e:
        logger.error(f"Student files error: {str(e)}")
        flash('Error loading class files', 'error')
        return redirect(url_for('dashboard.profile'))


@files_bp.route('/profile/resume')
@require_login
def profile_resume():
    """View and manage resume."""
    try:
        uid = session['uid']
        user_data = get_document('users', uid)
        
        if not user_data:
            flash('User profile not found', 'error')
            return redirect(url_for('dashboard.profile'))
        
        # Get resume files
        resume_files = db.collection('user_files').where('user_id', '==', uid).where('file_type', '==', 'resume').stream()
        
        resumes = []
        for resume_doc in resume_files:
            resume_data = resume_doc.to_dict()
            resume_data['id'] = resume_doc.id
            resumes.append(resume_data)
        
        return render_template('profile_resume.html', resumes=resumes, user_data=user_data)
    
    except Exception as e:
        logger.error(f"Profile resume error: {str(e)}")
        flash('Error loading resume', 'error')
        return redirect(url_for('dashboard.profile'))


@files_bp.route('/profile/edit', methods=['GET', 'POST'])
@require_login
def profile_edit():
    """Edit user profile."""
    try:
        uid = session['uid']
        user_data = get_document('users', uid)
        
        if not user_data:
            flash('User profile not found', 'error')
            return redirect(url_for('dashboard.profile'))
        
        if request.method == 'POST':
            # Handle profile picture removal
            if request.form.get('remove_picture') == 'yes':
                current_picture = user_data.get('profile_picture')
                if current_picture and current_picture != 'default-profile.png':
                    try:
                        os.remove(os.path.join(PROFILE_PICTURES_FOLDER, current_picture))
                    except FileNotFoundError:
                        pass
                
                db.collection('users').document(uid).update({
                    'profile_picture': 'default-profile.png',
                    'updated_at': datetime.utcnow()
                })
                flash('Profile picture removed', 'success')
                return redirect(url_for('files.profile_edit'))
            
            # Handle profile picture upload
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Add timestamp to prevent conflicts
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{uid}_{timestamp}_{filename}"
                    
                    # Remove old picture if not default
                    current_picture = user_data.get('profile_picture')
                    if current_picture and current_picture != 'default-profile.png':
                        try:
                            os.remove(os.path.join(PROFILE_PICTURES_FOLDER, current_picture))
                        except FileNotFoundError:
                            pass
                    
                    # Save new picture
                    file.save(os.path.join(PROFILE_PICTURES_FOLDER, filename))
                    
                    # Update database
                    db.collection('users').document(uid).update({
                        'profile_picture': filename,
                        'updated_at': datetime.utcnow()
                    })
                    
                    flash('Profile picture updated', 'success')
                    return redirect(url_for('dashboard.profile'))
            
            # Handle profile information updates
            name = request.form.get('name', '').strip()
            grade = request.form.get('grade', '').strip()
            board = request.form.get('board', '').strip()
            bio = request.form.get('bio', '').strip()
            
            updates = {}
            if name:
                updates['name'] = name
            if grade:
                updates['grade'] = grade
            if board:
                updates['board'] = board
            if bio:
                updates['bio'] = bio
            
            if updates:
                updates['updated_at'] = datetime.utcnow()
                db.collection('users').document(uid).update(updates)
                flash('Profile updated successfully', 'success')
                return redirect(url_for('dashboard.profile'))
        
        return render_template('profile_edit.html', user_data=user_data)
    
    except Exception as e:
        logger.error(f"Profile edit error: {str(e)}")
        flash('Error updating profile', 'error')
        return redirect(url_for('dashboard.profile'))


@files_bp.route('/upload/profile_picture', methods=['POST'])
@require_login
def upload_profile_picture():
    """Upload profile picture via AJAX."""
    try:
        uid = session['uid']
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        # Validate file
        validation_result = file_upload_security.validate_file(file)
        if not validation_result['valid']:
            return jsonify({'error': validation_result['error']}), 400
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{uid}_{timestamp}_{filename}"
        
        # Save file
        file.save(os.path.join(PROFILE_PICTURES_FOLDER, filename))
        
        # Update user profile
        db.collection('users').document(uid).update({
            'profile_picture': filename,
            'updated_at': datetime.utcnow()
        })
        
        return jsonify({
            'success': True,
            'filename': filename,
            'url': url_for('files.serve_profile_picture', filename=filename)
        })
    
    except Exception as e:
        logger.error(f"Upload profile picture error: {str(e)}")
        return jsonify({'error': 'Failed to upload profile picture'}), 500
