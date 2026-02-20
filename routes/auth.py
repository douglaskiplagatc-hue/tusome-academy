from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import check_password_hash
from models import User
from forms import LoginForm,SchoolInfoForm
from extensions import db

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")



@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    school = SchoolInfoForm()
    if request.method == "POST":
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

    return render_template("login.html", form=form, school=school )


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth_bp.login"))
