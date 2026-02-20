
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

student_bp = Blueprint("student_bp", __name__, url_prefix="/student")


@student_bp.route("/dashboard")
@login_required
def student_dashboard():
    # Load student profile, attendance, etc.
    return render_template("student/dashboard.html", student=current_user)


@student_bp.route("/grades")
@login_required
def view_my_grades():
    # Load grades for current student
    grades = current_user.grades  # Assuming relationship
    return render_template("student/my_grades.html", grades=grades)


@student_bp.route("/fees")
@login_required
def manage_fees_for_student():
    # Load fees and payments for student
    statements = current_user.fee_statements
    payments = current_user.fee_payments
    return render_template(
        "student/my_fees.html", statements=statements, payments=payments
    )


@student_bp.route("/events")
@login_required
def upcoming_events():
    # Show upcoming school events
    events = Event.query.order_by(Event.start_date.asc()).all()
    return render_template("student/events.html", events=events)


@student_bp.route("/messages")
@login_required
def student_messages():
    messages = current_user.messages  # assuming messages relationship
    return render_template("student/messages.html", messages=messages)
