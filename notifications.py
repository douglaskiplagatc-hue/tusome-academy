# notifications.py
# notifications_bp.py
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from datetime import datetime, timedelta
from sqlalchemy import and_
from models import User, FeeStatement, StaffSalary, Notification, Student
from extensions import db
from notifications import notification_service

notifications_bp = Blueprint("notifications_bp", __name__, url_prefix="/notifications")


class NotificationService:
    @staticmethod
    def send_daily_reminders():
        """Send daily fee reminders for overdue payments"""
        overdue_fees = FeeStatement.query.filter(
            and_(
                FeeStatement.due_date < datetime.now().date(), FeeStatement.balance > 0
            )
        ).all()

        # Group by student
        student_fees = {}
        for fee in overdue_fees:
            if fee.student_id not in student_fees:
                student_fees[fee.student_id] = []
            student_fees[fee.student_id].append(fee)

        # Send notifications
        for student_id, fees in student_fees.items():
            student = Student.query.get(student_id)
            if student and student.parent.email:
                # Send email
                send_fee_reminder(student, fees)

                # Send SMS if phone number available
                if student.parent.phone:
                    total_balance = sum(fee.balance for fee in fees)
                    sms_service.send_fee_reminder_sms(student, total_balance)

    @staticmethod
    def notify_new_grades(student_id, grade_ids):
        """Notify parent of new grades"""
        student = Student.query.get(student_id)
        grades = Grade.query.filter(Grade.id.in_(grade_ids)).all()

        if student and grades and student.parent.email:
            # Send email notification
            send_grade_notification(student, grades)

            # Send SMS for latest grade
            if student.parent.phone and grades:
                latest_grade = grades[0]
                sms_service.send_grade_sms(student, latest_grade)


notification_service = NotificationService()


# --------------------- Dashboard ---------------------
@notifications_bp.route("/")
@login_required
def notifications_dashboard():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    # Fee alerts
    overdue_fees = FeeStatement.query.filter(
        FeeStatement.balance > 0, FeeStatement.due_date < datetime.utcnow()
    ).all()

    # Salary payment alerts
    pending_salaries = StaffSalary.query.filter_by(paid=False).all()
    paid_salaries = (
        StaffSalary.query.filter_by(paid=True)
        .order_by(StaffSalary.payment_date.desc())
        .limit(10)
        .all()
    )

    # General finance notifications
    general_notifications = Notification.query.order_by(
        Notification.created_at.desc()
    ).all()

    return render_template(
        "notifications/dashboard.html",
        overdue_fees=overdue_fees,
        pending_salaries=pending_salaries,
        paid_salaries=paid_salaries,
        general_notifications=general_notifications,
    )


# --------------------- Trigger Daily Fee Reminders ---------------------
@notifications_bp.route("/send_fee_reminders")
@login_required
def send_fee_reminders():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    notification_service.send_daily_reminders()
    flash("Daily fee reminders sent successfully.", "success")
    return redirect(url_for("notifications_bp.notifications_dashboard"))


# --------------------- Trigger Salary Notifications ---------------------
@notifications_bp.route("/notify_salary/<int:salary_id>")
@login_required
def notify_salary_payment(salary_id):
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    salary = StaffSalary.query.get_or_404(salary_id)
    if salary.paid:
        # Create notification for staff
        notif = Notification(
            user_id=salary.staff_id,
            title="Salary Paid",
            message=f"Your salary for {salary.month}/{salary.year} has been paid. Amount: KES {salary.total_pay}",
        )
        db.session.add(notif)
        db.session.commit()
        flash(f"Notification sent to {salary.staff.full_name}", "success")
    else:
        flash("Salary not yet paid.", "warning")

    return redirect(url_for("notifications_bp.notifications_dashboard"))
