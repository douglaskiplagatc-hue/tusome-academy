# bursary_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Student, User, Bursary, Scholarship, FeeStatement
from extensions import db
from datetime import datetime

bursary_bp = Blueprint("bursary_bp", __name__, url_prefix="/bursary")


# -------------------- List Bursaries & Scholarships --------------------
@bursary_bp.route("/")
@login_required
def list_bursaries():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    bursaries = Bursary.query.order_by(Bursary.id.desc()).all()
    scholarships = Scholarship.query.order_by(Scholarship.id.desc()).all()
    return render_template("bursary/list.html", bursaries=bursaries, scholarships=scholarships)


# -------------------- Add Bursary --------------------
@bursary_bp.route("/add_bursary", methods=["GET", "POST"])
@login_required
def add_bursary():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    students = Student.query.all()
    if request.method == "POST":
        student_id = request.form.get("student_id")
        amount = float(request.form.get("amount") or 0)
        term = request.form.get("term")
        year = int(request.form.get("year") or datetime.utcnow().year)

        bursary = Bursary(
            student_id=student_id,
            amount=amount,
            term=term,
            year=year,
            created_at=datetime.utcnow()
        )
        db.session.add(bursary)
        db.session.commit()
        flash("Bursary added successfully.", "success")
        return redirect(url_for("bursary_bp.list_bursaries"))

    return render_template("bursary/add_bursary.html", students=students)


# -------------------- Add Scholarship --------------------
@bursary_bp.route("/add_scholarship", methods=["GET", "POST"])
@login_required
def add_scholarship():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    students = Student.query.all()
    if request.method == "POST":
        student_id = request.form.get("student_id")
        amount = float(request.form.get("amount") or 0)
        term = request.form.get("term")
        year = int(request.form.get("year") or datetime.utcnow().year)

        scholarship = Scholarship(
            student_id=student_id,
            amount=amount,
            term=term,
            year=year,
            created_at=datetime.utcnow()
        )
        db.session.add(scholarship)
        db.session.commit()
        flash("Scholarship added successfully.", "success")
        return redirect(url_for("bursary_bp.list_bursaries"))

    return render_template("bursary/add_scholarship.html", students=students)