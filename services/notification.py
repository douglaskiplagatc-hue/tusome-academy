# services/notification.py
from extensions import db
from models import Notification, User, Student, FeeStatement, Grade
from services.sms import sms_service
from services.email import send_notification_email
from datetime import datetime, timedelta
import threading
import logging

def send_notification(user, title, message, notification_type='general'):
    """
    Central function to send a notification to a single user through all channels:
    - Save to database (always)
    - Send SMS (if user has a phone)
    - Send email (if user has an email)
    All external sends run in background threads.
    """
    if not user:
        logging.warning("send_notification called with None user")
        return

    # 1. Database record
    notif = Notification(
        user_id=user.id,
        title=title,
        message=message,
        type=notification_type,          # now matches the model
        created_at=datetime.utcnow()
    )
    db.session.add(notif)
    db.session.commit()   # commit early so record is saved even if later steps fail

    # 2. SMS (if phone exists)
    if hasattr(user, 'phone') and user.phone:
        threading.Thread(
            target=_send_sms_background,
            args=(user.phone, title, message)
        ).start()

    # 3. Email (if email exists)
    if hasattr(user, 'email') and user.email:
        threading.Thread(
            target=_send_email_background,
            args=(user.email, title, message)
        ).start()

def _send_sms_background(phone, title, message):
    try:
        sms_service.send_notification_sms(phone, title, message)
    except Exception as e:
        logging.error(f"Background SMS failed to {phone}: {e}")

def _send_email_background(email, title, message):
    try:
        send_notification_email(email, title, message)
    except Exception as e:
        logging.error(f"Background email failed to {email}: {e}")

# Convenience functions for specific notification types
def send_grade_notification(student, grade):
    """Notify parent about a new grade."""
    if student.parent:
        title = f"New Grade: {grade.subject.name}"
        message = (f"{student.full_name} scored {grade.percentage}% ({grade.grade_letter()}) "
                   f"in {grade.subject.name} for Term {grade.term}.")
        send_notification(student.parent, title, message, notification_type='grade')

def send_fee_reminder(student, total_balance):
    """Notify parent about overdue fees."""
    if student.parent:
        title = "Fee Payment Reminder"
        message = (f"Dear parent, your child {student.full_name} has an outstanding fee balance "
                   f"of KES {total_balance:,.2f}. Please clear at your earliest convenience.")
        send_notification(student.parent, title, message, notification_type='fee')

def send_bulk_notifications(users, title, message, notification_type='general'):
    """Send the same notification to multiple users."""
    for user in users:
        send_notification(user, title, message, notification_type)


# ==================== SCHEDULED JOBS ====================

def send_daily_reminders():
    """Send daily fee reminders to parents of students with overdue fees."""
    # Get all students with at least one fee statement
    students = Student.query.all()
    for student in students:
        if not student.parent:
            continue
        # Calculate total balance across all fee statements
        total_balance = sum((fs.balance or 0) for fs in student.fee_statements if fs.balance > 0)
        if total_balance > 0:
            title = "Daily Fee Reminder"
            message = (f"Dear parent, your child {student.full_name} has an outstanding fee balance "
                       f"of KES {total_balance:,.2f}. Please clear at your earliest convenience.")
            send_notification(student.parent, title, message, notification_type='fee_reminder')

def send_weekly_grade_summary():
    """Send a weekly summary of new grades to parents."""
    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    end_of_week = start_of_week + timedelta(days=4)          # Friday (end of day)

    recent_grades = Grade.query.filter(
        Grade.created_at >= start_of_week,
        Grade.created_at <= end_of_week + timedelta(days=1)
    ).all()

    grades_by_student = {}
    for grade in recent_grades:
        grades_by_student.setdefault(grade.student_id, []).append(grade)

    for student_id, grades in grades_by_student.items():
        student = Student.query.get(student_id)
        if student and student.parent:
            grade_lines = [f"{g.subject.name}: {g.percentage}% ({g.grade_letter()})" for g in grades]
            summary = "\n".join(grade_lines)
            title = f"Weekly Grade Summary for {student.full_name}"
            message = f"Grades posted this week:\n{summary}\n\nLogin to the parent portal for details."
            send_notification(student.parent, title, message, notification_type='grade_summary')