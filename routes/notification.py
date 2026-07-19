# notifications_bp.py
from flask import Blueprint, render_template, redirect, request, flash, url_for,abort
from flask_login import login_required,current_user
from extensions import db
from models import Notification, User
from datetime import datetime
from decorators import roles_required
from services.notification import send_bulk_notifications   # <-- central bulk sender



notifications_bp = Blueprint("notifications_bp", __name__, url_prefix="/admin/notifications")
# ---------------- LIST ----------------
@notifications_bp.route("/")
@login_required
@roles_required("admin", "finance")
def manage_notifications():
    notifications = Notification.query.order_by(Notification.created_at.desc()).all()
    users = User.query.all()

    return render_template(
        "manage_notifications.html", notifications=notifications, users=users
    )

from flask import jsonify
from flask_login import login_required, current_user

@notifications_bp.route('/api/notifications/unread-count')
@login_required
def get_unread_count():
    # Replace 'Notification' with your actual Model name
    # and 'is_read' with your boolean field name
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()

    return jsonify({'count': count})
# ---------------- CREATE ----------------
@notifications_bp.route("/add", methods=["POST"])
@login_required
@roles_required("admin", "finance")
def add_notification():
    target = request.form["target"]
    title = request.form["title"]
    message = request.form["message"]

    # Determine the list of users
    if target == "all":
        users = User.query.all()
    elif target == "teachers":
        users = User.query.filter_by(role="teacher").all()
    elif target == "parents":
        users = User.query.filter_by(role="parent").all()
    elif target == "students":
        users = User.query.filter_by(role="student").all()
    else:
        # Assume it's a user ID
        user = User.query.get(int(target))
        users = [user] if user else []

    # For each user, create database record and send real‑time alerts
    for user in users:
        # Database notification (always saved)
        notif = Notification(
            user_id=user.id,
            title=title,
            message=message,
            created_at=datetime.utcnow()
        )
        db.session.add(notif)

        # Try to send SMS if the user has a phone number
        if hasattr(user, 'phone') and user.phone:
            try:
                sms_service.send_notification_sms(user, title, message)
            except Exception as e:
                print(f"SMS failed for {user.email}: {e}")

        # Try to send email if the user has an email address
        if hasattr(user, 'email') and user.email:
            try:
                send_notification_email(user, title, message)
            except Exception as e:
                print(f"Email failed for {user.email}: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Notification sent'})

    db.session.commit()
    flash("Notification sent successfully!", "success")
    return redirect(url_for("notifications_bp.manage_notifications"))



# ---------------- EDIT ----------------
@notifications_bp.route("/edit/<int:id>", methods=["POST"])
@roles_required("admin", "finance")
def edit_notification(id):
    notif = Notification.query.get_or_404(id)
    notif.title = request.form["title"]
    notif.message = request.form["message"]

    db.session.commit()
    flash("Notification updated!", "success")
    return redirect(url_for("notifications_bp.manage_notifications"))


# ---------------- DELETE ----------------
@notifications_bp.route("/delete/<int:id>")

@roles_required("admin", "finance")
def delete_notification(id):
    notif = Notification.query.get_or_404(id)
    db.session.delete(notif)
    db.session.commit()

    flash("Notification deleted!", "danger")
    return redirect(url_for("notifications_bp.manage_notifications"))



@notifications_bp.route('/api/notifications/unread-count')
@login_required
def unread_count():
    """Return the number of unread notifications for the current user."""
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

@notifications_bp.route('/api/notifications/recent')
@login_required
def recent_notifications():
    """Return the most recent notifications for the current user."""
    limit = request.args.get('limit', 10, type=int)
    notifs = Notification.query.filter_by(user_id=current_user.id)\
                                .order_by(Notification.created_at.desc())\
                                .limit(limit).all()
    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
        } for n in notifs]
    })

@notifications_bp.route('/api/notifications/<int:id>/mark-read', methods=['POST'])
@login_required
def mark_read(id):
    """Mark a single notification as read (must belong to current user)."""
    notif = Notification.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@notifications_bp.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications for the current user as read."""
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})
