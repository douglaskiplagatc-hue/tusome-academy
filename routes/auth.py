from flask import Blueprint, render_template, redirect, url_for, flash, request,jsonify,session
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import check_password_hash

from forms import LoginForm,SchoolInfoForm
from extensions import db
from models import User, SchoolProfile
from utils import generate_reset_token, verify_reset_token
from flask_mail import Message
from extensions import mail

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")


# If you have a blueprint named 'auth_bp'
@auth_bp.route('/api/auth-status')
def auth_status():
    return jsonify({'authenticated': current_user.is_authenticated})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_finance():
            return redirect(url_for("finance_bp.finance_dashboard"))
        if current_user.is_admin():
            return redirect(url_for("admin_bp.admin_dashboard"))
        elif current_user.is_teacher():
            return redirect(url_for("teacher_bp.teacher_dashboard"))
        elif current_user.is_parent():
            return redirect(url_for("parent_bp.parent_dashboard"))
        elif current_user.is_student():
            return redirect(url_for("student_bp.student_dashboard"))
        return redirect(url_for("admin_bp.admin_dashboard"))

    form = LoginForm()
    school = SchoolInfoForm()
    if request.method == "POST":
        session.clear()
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password", "danger")
            return redirect(url_for("auth_bp.login"))

        login_user(user)
        flash(f"Welcome back, {user.username}!", "success")

        # ✅ Redirect based on role
        if user.is_finance():
            return redirect(url_for("finance_bp.finance_dashboard"))

        if user.is_admin():
            return redirect(url_for("admin_bp.admin_dashboard"))
        elif user.is_teacher():
            return redirect(url_for("teacher_bp.teacher_dashboard"))
        elif user.is_parent():
            return redirect(url_for("parent_bp.parent_dashboard"))
        elif user.is_student():
            return redirect(url_for("student_bp.student_dashboard"))
        else:
            return redirect(url_for("auth_bp.login"))

    return render_template("login.html", hide_overlay=True,form=form, school=school )


@auth_bp.route("/logout", methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth_bp.login"))
 # assuming you have mail in extensions

# ----- Forgot Password (request reset) -----
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_reset_token(email)
            reset_url = url_for('auth_bp.reset_password', token=token, _external=True)
            # Send email
            msg = Message('Password Reset Request',
                          sender='noreply@yourschool.com',
                          recipients=[email])
            msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email.
This link expires in 1 hour.
'''
            mail.send(msg)
            flash('A password reset link has been sent to your email address.', 'info')
        else:
            # Don't reveal if email exists or not – security best practice
            flash('If that email address is registered, you will receive a reset link.', 'info')
        return redirect(url_for('auth_bp.forgot_password'))
    return render_template('forgot_password.html')

# ----- Reset Password (with token) -----
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    email = verify_reset_token(token)
    if not email:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth_bp.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(request.url)
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(request.url)

        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(password)
            db.session.commit()
            flash('Your password has been reset. You can now log in.', 'success')
            return redirect(url_for('auth_bp.login'))
        else:
            flash('User not found.', 'danger')
            return redirect(url_for('auth_bp.forgot_password'))

    return render_template('reset_password.html')

@auth_bp.route('/register-school', methods=['GET', 'POST'])
def register_school():
    # No global admin check – every school registers its own admin.

    if request.method == 'POST':
        # School details
        school_name = request.form.get('school_name')
        school_code = request.form.get('school_code')
        school_motto = request.form.get('school_motto')
        school_address = request.form.get('school_address')
        school_phone = request.form.get('school_phone')
        school_email = request.form.get('school_email')
        school_level = request.form.get('school_level', 'junior')

        # Admin user details
        admin_username = request.form.get('admin_username')
        admin_email = request.form.get('admin_email')
        admin_password = request.form.get('admin_password')
        confirm_password = request.form.get('confirm_password')

        if not all([school_name, admin_username, admin_email, admin_password]):
            flash('School name, admin username, email and password are required.', 'danger')
            return redirect(request.url)

        if admin_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(request.url)

        if not admin_password or len(admin_password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(request.url)

        # Ensure the admin email is globally unique (can’t be reused across schools)
        if User.query.filter_by(email=admin_email).first():
            flash('Email already registered. Please use a different email.', 'danger')
            return redirect(request.url)

        if User.query.filter_by(username=admin_username).first():
            flash('Username already taken.', 'danger')
            return redirect(request.url)

        # 1. Create the school profile
        profile = SchoolProfile(
            school_name=school_name,
            school_code=school_code,
            motto=school_motto,
            address=school_address,
            phone=school_phone,
            email=school_email,
            school_level=school_level,
            primary_color='#006B3F',
            secondary_color='#0047AB'
        )
        db.session.add(profile)
        db.session.flush()   # to get profile.id

        # 2. Create the admin user linked to this school
        admin = User(
            username=admin_username,
            email=admin_email,
            full_name='School Administrator',
            role='admin',
            is_active=True,
            school_id=profile.id
        )
        admin.set_password(admin_password)
        db.session.add(admin)

        db.session.commit()

        login_user(admin)
        flash(f'Registration successful! Welcome, {admin_username}.', 'success')
        return redirect(url_for('admin_bp.admin_dashboard'))

    return render_template('auth/register_school.html')
