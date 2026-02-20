from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from models import Student, Attendance
from extensions import db
from forms import AttendanceForm
from datetime import date

attendance_bp = Blueprint("attendance_bp", __name__, url_prefix="/attendance")


@attendance_bp.route("/", methods=["GET", "POST"])
@login_required
def mark_attendance():
    form = AttendanceForm()
    form.set_class_choices()
    students = []

    if form.validate_on_submit():
        class_id = form.class_id.data
        attendance_date = form.date.data

        # Load students of the selected class
        students = (
            Student.query.filter_by(current_class_id=class_id)
            .order_by(Student.full_name)
            .all()
        )

        if "save_attendance" in request.form:
            # Save submitted attendance
            for student in students:
                status = request.form.get(f"status_{student.id}")
                att = Attendance.query.filter_by(
                    student_id=student.id, date=attendance_date
                ).first()
                if not att:
                    att = Attendance(
                        student_id=student.id, date=attendance_date, status=status
                    )
                    db.session.add(att)
                else:
                    att.status = status
            db.session.commit()
            flash("Attendance saved successfully", "success")
            return redirect(url_for("attendance_bp.mark_attendance"))

    return render_template("attendance.html", form=form, students=students)
