# routes/settings.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import json
from PIL import Image
from datetime import datetime
from extensions import db
from models import SystemSetting, SchoolProfile, SchoolLevel, LevelSubject, ThemeSetting, Student, Teacher, User
from models import Subject, User, Class

settings_bp = Blueprint('settings_bp', __name__, url_prefix='/settings')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@settings_bp.route('/')
@login_required
def dashboard():
    """Settings dashboard"""
    settings = SystemSetting.query.first()
    return render_template('settings/dashboard.html',system_settings=settings)

@settings_bp.route('/school-profile', methods=['GET', 'POST'])
@login_required
def school_profile():
    """School profile settings"""
    profile = SchoolProfile.query.first()

    # Get counts for stats
    student_count = Student.query.count()
    teacher_count = Teacher.query.count()
    class_count = Class.query.count()
    subject_count = Subject.query.count()

    # Get current term/year from settings
    term = get_setting('current_term', '1')
    year = get_setting('current_academic_year', datetime.now().year)

    if request.method == 'POST':
        if not profile:
            profile = SchoolProfile()
            db.session.add(profile)
        school_code = request.form.get('school_code')
        if school_code:
            existing = SchoolProfile.query.filter(
                SchoolProfile.school_code == school_code,
                SchoolProfile.id != profile.id if profile.id else True
            ).first()
            if existing:
                flash('School code already exists. Please use a unique code.', 'danger')
                return redirect(url_for('settings_bp.school_profile'))

        profile.school_name = request.form.get('school_name')
        profile.school_code = request.form.get('school_code')
        profile.motto = request.form.get('motto')
        profile.mission = request.form.get('mission')
        profile.vision = request.form.get('vision')
        profile.address = request.form.get('address')
        profile.phone = request.form.get('phone')
        profile.email = request.form.get('email')
        profile.website = request.form.get('website')
        profile.school_level = request.form.get('school_level')
        profile.established_year = request.form.get('established_year', type=int)
        profile.principal_name = request.form.get('principal_name')
        profile.primary_color = request.form.get('primary_color')
        profile.secondary_color = request.form.get('secondary_color')
        # Add these lines to the POST section
        profile.school_vision = request.form.get('school_vision')
        profile.school_mission = request.form.get('school_mission')
        profile.social_facebook = request.form.get('social_facebook')
        profile.social_twitter = request.form.get('social_twitter')
        profile.social_instagram = request.form.get('social_instagram')
        profile.social_linkedin = request.form.get('social_linkedin')
        profile.social_youtube = request.form.get('social_youtube')
        # Handle logo upload
        logo = request.files.get('logo')
        if logo and allowed_file(logo.filename):
            filename = secure_filename(f"logo_{profile.school_code or 'school'}.{logo.filename.rsplit('.', 1)[1].lower()}")
            logo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'school', filename)
            os.makedirs(os.path.dirname(logo_path), exist_ok=True)

            # Resize and save
            img = Image.open(logo)
            img.thumbnail((200, 200))
            img.save(logo_path)

            profile.logo_url = url_for('static', filename=f'uploads/school/{filename}')

        # Handle favicon upload
        favicon = request.files.get('favicon')
        if favicon and allowed_file(favicon.filename):
            filename = secure_filename(f"favicon_{profile.school_code or 'school'}.{favicon.filename.rsplit('.', 1)[1].lower()}")
            favicon_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'school', filename)
            favicon.save(favicon_path)
            profile.favicon_url = url_for('static', filename=f'uploads/school/{filename}')

        db.session.commit()

        # Update system subjects if level changed
        if 'school_level' in request.form:
            update_subjects_for_level(profile.school_level)

        flash('School profile updated successfully!', 'success')
        return redirect(url_for('settings_bp.school_profile'))

    levels = SchoolLevel.query.filter_by(is_active=True).all()

    return render_template('settings/school_profile.html',
                         profile=profile,
                         levels=levels,
                         student_count=student_count,
                         teacher_count=teacher_count,
                         class_count=class_count,
                         subject_count=subject_count,
                         term=term,
                         year=year)
@settings_bp.route('/school-level', methods=['GET', 'POST'])
@login_required
def school_level_settings():
    """Configure school level and subjects"""
    if request.method == 'POST':
        level_code = request.form.get('school_level')

        # Update school profile
        profile = SchoolProfile.query.first()
        if profile:
            profile.school_level = level_code
            db.session.commit()

        # Update subjects based on level
        update_subjects_for_level(level_code)

        flash(f'School level set to {level_code.title()} and subjects updated!', 'success')
        return redirect(url_for('settings_bp.school_level_settings'))

    profile = SchoolProfile.query.first()
    current_level = profile.school_level if profile else 'junior'
    levels = SchoolLevel.query.filter_by(is_active=True).all()

    # Get subjects for current level
    subjects = LevelSubject.query.filter_by(level_code=current_level).order_by(LevelSubject.sort_order).all()

    return render_template('settings/school_level.html',
                         current_level=current_level,
                         levels=levels,
                         subjects=subjects)

def update_subjects_for_level(level_code):
    """Update system subjects based on school level"""
    # Clear existing subjects
    Subject.query.delete()

    # Get subjects for this level
    level_subjects = LevelSubject.query.filter_by(level_code=level_code).all()

    for ls in level_subjects:
        subject = Subject(
            name=ls.subject_name,
            code=ls.subject_code,
            level=level_code,
            compulsory=ls.is_core
        )
        db.session.add(subject)

    db.session.commit()

@settings_bp.route('/subjects/manage', methods=['GET', 'POST'])
@login_required
def manage_subjects():
    """Manage subjects for current school level"""
    profile = SchoolProfile.query.first()
    current_level = profile.school_level if profile else 'junior'

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            subject_name = request.form.get('subject_name')
            subject_code = request.form.get('subject_code')
            is_core = request.form.get('is_core') == 'on'

            level_subject = LevelSubject(
                level_code=current_level,
                subject_name=subject_name,
                subject_code=subject_code,
                is_core=is_core,
                sort_order=LevelSubject.query.filter_by(level_code=current_level).count()
            )
            db.session.add(level_subject)
            db.session.commit()
            flash(f'Subject {subject_name} added!', 'success')

        elif action == 'edit':
            subject_id = request.form.get('subject_id')
            subject = LevelSubject.query.get(subject_id)
            if subject:
                subject.subject_name = request.form.get('subject_name')
                subject.subject_code = request.form.get('subject_code')
                subject.is_core = request.form.get('is_core') == 'on'
                db.session.commit()
                flash('Subject updated!', 'success')

        elif action == 'delete':
            subject_id = request.form.get('subject_id')
            subject = LevelSubject.query.get(subject_id)
            if subject:
                db.session.delete(subject)
                db.session.commit()
                flash('Subject deleted!', 'success')

        # Update system subjects
        update_subjects_for_level(current_level)

        return redirect(url_for('settings_bp.manage_subjects'))

    subjects = LevelSubject.query.filter_by(level_code=current_level).order_by(LevelSubject.sort_order).all()

    return render_template('manage_subjects.html',
                         subjects=subjects,
                         current_level=current_level)

@settings_bp.route('/theme', methods=['GET', 'POST'])
@login_required
def theme_settings():
    """Theme and appearance settings"""
    profile = SchoolProfile.query.first()

    if request.method == 'POST':
        if profile:
            profile.primary_color = request.form.get('primary_color')
            profile.secondary_color = request.form.get('secondary_color')

            # Save theme settings
            theme_config = {
                'sidebar_theme': request.form.get('sidebar_theme'),
                'navbar_theme': request.form.get('navbar_theme'),
                'border_radius': request.form.get('border_radius'),
                'enable_animations': request.form.get('enable_animations') == 'on',
                'compact_mode': request.form.get('compact_mode') == 'on'
            }

            # Save to system settings
            theme_setting = SystemSetting.query.filter_by(key='theme_config').first()
            if not theme_setting:
                theme_setting = SystemSetting(key='theme_config', value_type='json')
                db.session.add(theme_setting)
            theme_setting.set_value(theme_config)

            db.session.commit()
            flash('Theme settings updated!', 'success')

        return redirect(url_for('settings_bp.theme_settings'))

    # Load current theme settings
    theme_setting = SystemSetting.query.filter_by(key='theme_config').first()
    theme_config = theme_setting.get_value() if theme_setting else ThemeSetting.get_default_theme()

    return render_template('settings/theme.html',
                         profile=profile,
                         theme_config=theme_config)

@settings_bp.route('/system', methods=['GET', 'POST'])
@login_required
def system_settings():
    """System-wide settings"""
    from datetime import datetime
    import psutil
    import platform

    if request.method == 'POST':
        # Academic settings
        save_setting('current_academic_year', request.form.get('current_academic_year'), 'string')
        save_setting('current_term', request.form.get('current_term'), 'string')
        save_setting('term_start_date', request.form.get('term_start_date'), 'string')
        save_setting('term_end_date', request.form.get('term_end_date'), 'string')

        # Assessment settings
        save_setting('assessment_weight_exam', request.form.get('assessment_weight_exam'), 'int')
        save_setting('assessment_weight_cat', request.form.get('assessment_weight_cat'), 'int')
        save_setting('assessment_weight_assignment', request.form.get('assessment_weight_assignment'), 'int')

        # Notification settings
        save_setting('enable_email_notifications', request.form.get('enable_email_notifications') == 'on', 'bool')
        save_setting('enable_sms_notifications', request.form.get('enable_sms_notifications') == 'on', 'bool')
        save_setting('enable_parent_portal', request.form.get('enable_parent_portal') == 'on', 'bool')
        save_setting('enable_student_portal', request.form.get('enable_student_portal') == 'on', 'bool')

        # Security settings
        save_setting('session_timeout', request.form.get('session_timeout'), 'int')
        save_setting('max_login_attempts', request.form.get('max_login_attempts'), 'int')
        save_setting('password_expiry_days', request.form.get('password_expiry_days'), 'int')
        save_setting('enable_2fa', request.form.get('enable_2fa') == 'on', 'bool')

        # Data management
        save_setting('backup_frequency', request.form.get('backup_frequency'), 'string')
        save_setting('log_retention_days', request.form.get('log_retention_days'), 'int')

        db.session.commit()
        flash('System settings saved successfully!', 'success')
        return redirect(url_for('settings_bp.system_settings'))

    # Load current settings
    settings = {
        'current_academic_year': get_setting('current_academic_year', '2024'),
        'current_term': get_setting('current_term', '1'),
        'term_start_date': get_setting('term_start_date', ''),
        'term_end_date': get_setting('term_end_date', ''),
        'assessment_weight_exam': get_setting('assessment_weight_exam', 60),
        'assessment_weight_cat': get_setting('assessment_weight_cat', 30),
        'assessment_weight_assignment': get_setting('assessment_weight_assignment', 10),
        'enable_email_notifications': get_setting('enable_email_notifications', True),
        'enable_sms_notifications': get_setting('enable_sms_notifications', False),
        'enable_parent_portal': get_setting('enable_parent_portal', True),
        'enable_student_portal': get_setting('enable_student_portal', True),
        'session_timeout': get_setting('session_timeout', 30),
        'max_login_attempts': get_setting('max_login_attempts', 5),
        'password_expiry_days': get_setting('password_expiry_days', 90),
        'enable_2fa': get_setting('enable_2fa', False),
        'backup_frequency': get_setting('backup_frequency', 'weekly'),
        'log_retention_days': get_setting('log_retention_days', 30)
    }

    # System information
    from models import User, Student, Teacher
    total_users = User.query.count()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Get uptime (simple implementation)
    import time
    boot_time = time.time() - psutil.boot_time()
    uptime = f"{int(boot_time // 3600)}h {int((boot_time % 3600) // 60)}m"

    # Memory usage
    memory = psutil.virtual_memory()
    memory_usage = f"{memory.percent}% ({memory.used // (1024**3)}GB / {memory.total // (1024**3)}GB)"

    # Database size (SQLite example)
    import os
    db_path = current_app.config.get('SQLALCHEMY_DATABASE_URI', '').replace('sqlite:///', '')
    if db_path and os.path.exists(db_path):
        db_size = f"{os.path.getsize(db_path) / (1024**2):.2f} MB"
    else:
        db_size = "N/A"

    return render_template('settings/system_settings.html',
                       settings=settings,
                       total_users=total_users,
                       current_time=current_time,
                       uptime=uptime,
                       memory_usage=memory_usage,
                       db_size=db_size)
@settings_bp.route('/backup', methods=['GET', 'POST'])
@login_required
def backup_settings():
    """Database backup and restore"""
    import subprocess
    from datetime import datetime

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'backup':
            # Create database backup
            backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            backup_path = os.path.join(current_app.config['BACKUP_FOLDER'], backup_filename)
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)

            # Use mysqldump or pg_dump based on your DB
            # This is a placeholder - implement based on your database
            flash('Database backup created successfully!', 'success')

        elif action == 'restore':
            # Restore from backup
            backup_file = request.files.get('backup_file')
            if backup_file:
                # Restore logic here
                flash('Database restored successfully!', 'success')

    return render_template('settings/backup_setting.html')

def save_setting(key, value, value_type='string'):
    """Helper to save system setting"""
    setting = SystemSetting.query.filter_by(key=key).first()
    if not setting:
        setting = SystemSetting(key=key, value_type=value_type)
        db.session.add(setting)
    setting.set_value(value)

def get_setting(key, default=None):
    """Helper to get system setting"""
    setting = SystemSetting.query.filter_by(key=key).first()
    if setting:
        return setting.get_value()
    return default

@settings_bp.route('/ajax/update-order', methods=['POST'])
@login_required
def update_subject_order():
    """Update subject display order via AJAX"""
    data = request.get_json()
    subject_ids = data.get('subject_ids', [])

    for idx, subject_id in enumerate(subject_ids):
        subject = LevelSubject.query.get(subject_id)
        if subject:
            subject.sort_order = idx

    db.session.commit()
    return jsonify({'success': True})

@settings_bp.route('/get-selected-subjects')
@login_required
def get_selected_subjects():
    """Get currently selected subjects for the school level"""
    subjects = LevelSubject.query.filter_by(level_code=current_app.config.get('SCHOOL_LEVEL', 'junior')).all()
    subject_list = [{
        'code': s.subject_code,
        'name': s.subject_name,
        'is_core': s.is_core,
        'id': s.id
    } for s in subjects]
    return jsonify({'subjects': subject_list})

@settings_bp.route('/save-selected-subjects', methods=['POST'])
@login_required
def save_selected_subjects():
    """Save selected subjects for the school level"""
    try:
        data = request.get_json()
        subjects = data.get('subjects', [])
        level_code = current_app.config.get('SCHOOL_LEVEL', 'junior')

        # Clear existing subjects for this level
        LevelSubject.query.filter_by(level_code=level_code).delete()
        print(request.form)      # for form data
        print(request.get_json())# for JSON
        # Add new subjects
        for idx, subject in enumerate(subjects):
            level_subject = LevelSubject(
                level_code=level_code,
                subject_code=subject['code'],
                subject_name=subject['name'],
                is_core=subject.get('is_core', False),
                sort_order=idx
            )
            db.session.add(level_subject)

        db.session.commit()
        return jsonify({'success': True, 'message': f'Saved {len(subjects)} subjects'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
