from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db
from models import (
    Student,
    Grade,
    FeeStatement,
    FeePayment,
    Announcement,
    Notification,
    Attendance,
    Event,
    Message,
)

parent_bp = Blueprint("parent_bp", __name__, url_prefix="/parent")


# ----------------------------------------------------
# 0. Guard function
# ----------------------------------------------------
def parent_required():
    if not current_user.is_parent():
        abort(403)


@parent_bp.route("/dashboard")
@login_required
def parent_dashboard():
    # ensure only parents access
    if not getattr(current_user, "is_parent", lambda: False)():
        abort(403)

    # children as list (works if relationship is lazy='dynamic' or list)
    try:
        children = list(current_user.children)
    except TypeError:
        # if children is not iterable, fallback to query
        children = Student.query.filter_by(parent_id=current_user.id).all()

    # collect child ids for efficient queries
    child_ids = [c.id for c in children]

    # total balance across all children (safe Python computation using model properties)
    total_balance = sum(c.get_total_fees_balance() for c in children) if children else 0

    # recent grades for all children (most recent N)
    recent_grades = []
    if child_ids:
        recent_grades = (
            Grade.query.filter(Grade.student_id.in_(child_ids))
            .order_by(Grade.created_at.desc())
            .limit(20)
            .all()
        )

    # fee statements for all children (recent)
    fee_statements = []
    if child_ids:
        fee_statements = (
            FeeStatement.query.filter(FeeStatement.student_id.in_(child_ids))
            .order_by(
                FeeStatement.due_date.asc().nulls_last(), FeeStatement.created_at.desc()
            )
            .all()
        )

    # announcements and notifications
    announcements = (
        Announcement.query.order_by(Announcement.created_at.desc()).limit(10).all()
    )
    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(10)
        .all()
    )

    # prepare small performance summary per child (average percentage)
    performance_summary = {}
    for c in children:
        grades_for_child = [g for g in recent_grades if g.student_id == c.id]
        if grades_for_child:
            # compute average of available percentages (skip None)
            vals = [
                (g.percentage or 0)
                for g in grades_for_child
                if g.percentage is not None
            ]
            avg = sum(vals) / len(vals) if vals else None
        else:
            avg = None
        performance_summary[c.id] = {"avg": avg, "count": len(grades_for_child)}

    return render_template(
        "parent_dashboard.html",
        children=children,
        total_balance=total_balance,
        recent_grades=recent_grades,
        fee_statements=fee_statements,
        announcements=announcements,
        notifications=notifications,
        performance_summary=performance_summary,
        title="Parent Dashboard",
    )


# ----------------------------------------------------
# 2. View a single child profile
# ----------------------------------------------------
@parent_bp.route("/child/<int:student_id>")
@login_required
def child_detail(student_id):
    parent_required()

    child = Student.query.get_or_404(student_id)

    if child.parent_id != current_user.id:
        abort(403)

    grades = Grade.query.filter_by(student_id=child.id).order_by(
        Grade.year.desc(), Grade.term.desc()
    )
    statements = FeeStatement.query.filter_by(student_id=child.id)
    payments = FeePayment.query.filter_by(student_id=child.id).order_by(
        FeePayment.payment_date.desc()
    )

    attendance = Attendance.query.filter_by(student_id=child.id).order_by(
        Attendance.date.desc()
    )

    return render_template(
        "parent/child_detail.html",
        child=child,
        grades=grades,
        statements=statements,
        payments=payments,
        attendance=attendance,
    )


# ----------------------------------------------------
# 3. Child Grades — Table + charts


@parent_bp.route("/child/grades")
@login_required
def child_grades():
    parent_required()

    # Get the child of the logged-in parent
    child = Student.query.filter_by(parent_id=current_user.id).first_or_404()

    grades = (
        Grade.query.filter_by(student_id=child.id)
        .order_by(Grade.year.desc(), Grade.term.desc())
        .all()
    )

    return render_template("parent/student_grade.html", child=child, grades=grades)


# ----------------------------------------------------
# 4. Child Attendance
# ----------------------------------------------------
@parent_bp.route("/child/<int:student_id>/attendance")
@login_required
def child_attendance(student_id):
    parent_required()

    child = Student.query.get_or_404(student_id)
    if child.parent_id != current_user.id:
        abort(403)

    attendance = (
        Attendance.query.filter_by(student_id=child.id)
        .order_by(Attendance.date.desc())
        .all()
    )

    return render_template(
        "parent/child_attendance.html", child=child, attendance=attendance
    )


# ----------------------------------------------------
# 5. Child Fee Records
# ----------------------------------------------------
@parent_bp.route("/child/<int:student_id>/fees")
@login_required
def child_fees(student_id):
    parent_required()

    child = Student.query.get_or_404(student_id)
    if child.parent_id != current_user.id:
        abort(403)

    statements = FeeStatement.query.filter_by(student_id=child.id).all()
    FeePayment.payment_date.desc()
    payments = FeePayment.query.filter_by(student_id=child.id).order_by()

    return render_template(
        "parent/child_fees.html",
        child=child,
        statements=statements,
        payments=payments,
        student_id=child.id,
    )


# ----------------------------------------------------
# 6. Notifications Page
# ----------------------------------------------------
@parent_bp.route("/notifications")
@login_required
def notifications():
    parent_required()

    notes = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    )

    return render_template("parent/notifications.html", notifications=notes)


# ----------------------------------------------------
# 7. Mark Notification as read
# ----------------------------------------------------
@parent_bp.route("/notifications/read/<int:note_id>")
@login_required
def mark_read(note_id):
    parent_required()

    note = Notification.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        abort(403)

    note.is_read = True
    db.session.commit()

    return redirect(url_for("parent_bp.notifications"))


# ----------------------------------------------------
# 8. Parent Profile / Settings
# ----------------------------------------------------
@parent_bp.route("/profile")
@login_required
def profile():
    parent_required()
    return render_template("parent/profile.html", parent=current_user)


@parent_bp.route("/fees")
@login_required
def manage_fees_for_student():
    statements = []
    payments = []
    for child in current_user.children:
        statements += child.fee_statements
        payments += child.payments
    return render_template(
        "parent/child_fees.html",
        statements=statements,
        payments=payments,
        child=child,
    )


@parent_bp.route("/events")
@login_required
def upcoming_events():
    event = Event.query.order_by(Event.start_time.asc()).all()
    return render_template(
        "events/view.html",
        event=event,
    )


# ---------------------- VIEW ALL MESSAGES ----------------------
@parent_bp.route("/messages")
@login_required
def parent_messages():
    msgs = (
        Message.query.filter_by(receiver_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )
    return render_template("parent/message.html", messages=msgs)


# ---------------------- VIEW SINGLE MESSAGE ----------------------
@parent_bp.route("/message/<int:message_id>")
@login_required
def view_message(message_id):
    msg = Message.query.get_or_404(message_id)

    # Mark as read
    if msg.receiver_id == current_user.id:
        msg.is_read = True
        db.session.commit()

    return render_template("parent/view_message.html", message=msg)


# ---------------------- COMPOSE MESSAGE ----------------------
@parent_bp.route("/compose", methods=["GET", "POST"])
@login_required
def compose_message():
    form = MessageForm()

    if form.validate_on_submit():
        # By default parent sends to admin
        admin = User.query.filter_by(role="admin").first()

        new_msg = Message(
            sender_id=current_user.id,
            receiver_id=admin.id,
            subject=form.subject.data,
            content=form.content.data,
        )

        db.session.add(new_msg)
        db.session.commit()
        flash("Message sent successfully!", "success")

        return redirect(url_for("parent_bp.messages"))

    return render_template("parent/compose_message.html", form=form)
