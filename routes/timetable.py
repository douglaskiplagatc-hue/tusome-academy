from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from extensions import db
from models import Timetable, Class, Subject, User
from datetime import datetime, time

timetable_bp = Blueprint("timetable_bp", __name__, url_prefix="/admin/timetable")

# Helper: parse time from "HH:MM" or "HH:MM:SS"
def parse_time(val):
    if not val:
        return None
    try:
        return datetime.strptime(val, "%H:%M").time()
    except ValueError:
        try:
            return datetime.strptime(val, "%H:%M:%S").time()
        except ValueError:
            return None

# Manage view: weekly grid for a selected class
@timetable_bp.route("/", methods=["GET"])
@login_required
def manage_timetable():
    # Optionally restrict to admin/teacher:
    # if not current_user.is_admin(): abort(403)

    class_id = request.args.get("class_id", type=int)
    classes = Class.query.order_by(Class.name).all()
    subjects = Subject.query.order_by(Subject.name).all()
    teachers = User.query.filter_by(role="teacher").order_by(User.full_name).all()

    entries = []
    if class_id:
        entries = Timetable.query.filter_by(class_id=class_id).order_by(Timetable.day, Timetable.start_time).all()

    # Build a map day -> list(entries) for template convenience
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    grid = {d: [] for d in days}
    for e in entries:
        grid.setdefault(e.day, []).append(e)

    return render_template(
        "timetable/manage.html",
        classes=classes,
        subjects=subjects,
        teachers=teachers,
        selected_class_id=class_id,
        grid=grid,
        days=days,
    )

# Add entry (form)
@timetable_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_entry():
    # if not current_user.is_admin(): abort(403)
    if request.method == "POST":
        class_id = request.form.get("class_id", type=int)
        subject_id = request.form.get("subject_id", type=int)
        teacher_id = request.form.get("teacher_id", type=int)
        day = request.form.get("day")
        start_time = parse_time(request.form.get("start_time"))
        end_time = parse_time(request.form.get("end_time"))
        room = request.form.get("room", "").strip() or None

        if not (class_id and subject_id and teacher_id and day and start_time and end_time):
            flash("Missing required fields", "danger")
            return redirect(url_for("timetable_bp.manage_timetable", class_id=class_id))

        entry = Timetable(
            class_id=class_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            day=day,
            start_time=start_time,
            end_time=end_time,
            room=room,
        )
        db.session.add(entry)
        db.session.commit()
        flash("Timetable entry added", "success")
        return redirect(url_for("timetable_bp.manage_timetable", class_id=class_id))

    # GET -> show form
    classes = Class.query.all()
    subjects = Subject.query.all()
    teachers = User.query.filter_by(role="teacher").all()
    return render_template("timetable/form.html", action="Add", classes=classes, subjects=subjects, teachers=teachers, entry=None)

# Edit entry
@timetable_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_entry(id):
    entry = Timetable.query.get_or_404(id)
    # if not current_user.is_admin(): abort(403)
    if request.method == "POST":
        entry.class_id = request.form.get("class_id", type=int)
        entry.subject_id = request.form.get("subject_id", type=int)
        entry.teacher_id = request.form.get("teacher_id", type=int)
        entry.day = request.form.get("day")
        start_time = parse_time(request.form.get("start_time"))
        end_time = parse_time(request.form.get("end_time"))
        entry.start_time = start_time
        entry.end_time = end_time
        entry.room = request.form.get("room", "").strip() or None
        db.session.commit()
        flash("Timetable updated", "success")
        return redirect(url_for("timetable_bp.manage_timetable", class_id=entry.class_id))

    classes = Class.query.all()
    subjects = Subject.query.all()
    teachers = User.query.filter_by(role="teacher").all()
    return render_template("timetable/form.html", action="Edit", entry=entry, classes=classes, subjects=subjects, teachers=teachers)

# Delete
@timetable_bp.route("/delete/<int:id>", methods=["POST","GET"])
@login_required
def delete_entry(id):
    entry = Timetable.query.get_or_404(id)
    class_id = entry.class_id
    db.session.delete(entry)
    db.session.commit()
    flash("Entry deleted", "danger")
    return redirect(url_for("timetable_bp.manage_timetable", class_id=class_id))

# AJAX: quick update (drag/drop or inline modify)
@timetable_bp.route("/ajax/update", methods=["POST"])
@login_required
def ajax_update():
    # expects JSON: {id, day, start_time, end_time, room, teacher_id, subject_id}
    data = request.get_json(force=True)
    if not data:
        return jsonify({"ok": False, "error": "no data"}), 400

    entry = Timetable.query.get(data.get("id"))
    if not entry:
        return jsonify({"ok": False, "error": "entry not found"}), 404

    # optional permission check
    # if not current_user.is_admin(): return jsonify({"ok":False}),403

    entry.day = data.get("day", entry.day)
    st = parse_time(data.get("start_time")) or entry.start_time
    et = parse_time(data.get("end_time")) or entry.end_time
    entry.start_time = st
    entry.end_time = et
    entry.room = data.get("room", entry.room)
    teacher_id = data.get("teacher_id")
    subject_id = data.get("subject_id")
    if teacher_id:
        entry.teacher_id = int(teacher_id)
    if subject_id:
        entry.subject_id = int(subject_id)

    db.session.commit()
    return jsonify({"ok": True, "id": entry.id})