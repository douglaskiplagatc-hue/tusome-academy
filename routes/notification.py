from flask import Blueprint, render_template, redirect, request, flash, url_for, abort
from flask_login import login_required, current_user
from extensions import db
from models import Notification, User
from datetime import datetime
from decorators import roles_required
notifications_bp = Blueprint(
    "notifications_bp", __name__, url_prefix="/admin/notifications"
)


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


# ---------------- CREATE ----------------
@notifications_bp.route("/add", methods=["POST"])
@login_required
@roles_required("admin", "finance")
def add_notification():
    target = request.form["target"]
    title = request.form["title"]
    message = request.form["message"]

    if target == "all":
        users = User.query.all()
    elif target == "teachers":
        users = User.query.filter_by(role="teacher").all()
    elif target == "parents":
        users = User.query.filter_by(role="parent").all()
    elif target == "students":
        users = User.query.filter_by(role="student").all()
    else:
        users = [User.query.get(int(target))]

    for user in users:
        notif = Notification(
            user_id=user.id, title=title, message=message, created_at=datetime.utcnow()
        )
        db.session.add(notif)

    db.session.commit()
    flash("Notification sent successfully!", "success")
    return redirect(url_for("notifications_bp.manage_notifications"))


# ---------------- EDIT ----------------
@notifications_bp.route("/edit/<int:id>", methods=["POST"])
@login_required
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
@login_required
@roles_required("admin", "finance")
def delete_notification(id):
    notif = Notification.query.get_or_404(id)
    db.session.delete(notif)
    db.session.commit()

    flash("Notification deleted!", "danger")
    return redirect(url_for("notifications_bp.manage_notifications"))
