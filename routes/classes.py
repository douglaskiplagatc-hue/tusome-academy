# routes/classes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import db
from models import Class, Teacher
from forms import ClassForm

class_bp = Blueprint("class_bp", __name__, url_prefix="/classes")


@class_bp.route("/", methods=["GET", "POST"])
@login_required
def manage_classes():
    classes = Class.query.options(
        db.joinedload(Class.subject_teachers).joinedload(Teacher.user),
        db.joinedload(Class.class_teacher).joinedload(Teacher.user)
    ).all()

    teachers = Teacher.query.options(
        db.joinedload(Teacher.user)
    ).all()

    form = ClassForm()
    form.teacher_id.choices = [(0, "Unassigned")] + [
        (t.id, t.user.full_name if t.user else f"Teacher {t.id}") for t in teachers
    ]

    # CREATE CLASS
    if form.validate_on_submit():
        teacher_id = int(form.teacher_id.data)

        new_class = Class(
            name=form.name.data,
            class_teacher_id=teacher_id if teacher_id != 0 else None,
        )

        db.session.add(new_class)
        db.session.commit()

        flash(f"Class '{new_class.name}' added successfully!", "success")
        return redirect(url_for("class_bp.manage_classes"))

    return render_template(
        "manage_classes.html",
        classes=classes,
        teachers=teachers,
        form=form,
        title="Manage Classes",
    )


@class_bp.route("/<int:class_id>/delete", methods=["POST"])
@login_required
def delete_class(class_id):
    class_obj = Class.query.get_or_404(class_id)

    try:
        db.session.delete(class_obj)
        db.session.commit()
        flash(f"Class '{class_obj.name}' deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting class: {e}", "danger")

    return redirect(url_for("class_bp.manage_classes"))


@class_bp.route("/<int:class_id>/edit", methods=["POST"])
@login_required
def edit_class(class_id):
    class_obj = Class.query.get_or_404(class_id)

    new_name = request.form.get("name", "").strip()
    class_teacher_id = request.form.get("class_teacher_id", type=int)
    subject_teacher_ids = request.form.getlist("subject_teacher_ids")  # FIXED

    # UPDATE NAME
    if new_name and new_name != class_obj.name:
        exists = Class.query.filter(
            Class.name == new_name,
            Class.id != class_id
        ).first()

        if exists:
            flash(f'Class name "{new_name}" already exists!', "warning")
            return redirect(url_for("class_bp.manage_classes"))

        class_obj.name = new_name

    # UPDATE CLASS TEACHER
    class_obj.class_teacher_id = class_teacher_id or None

    # UPDATE SUBJECT TEACHERS (WORKING)
    if subject_teacher_ids:
        class_obj.subject_teachers = Teacher.query.filter(
            Teacher.id.in_(subject_teacher_ids)
        ).all()
    else:
        class_obj.subject_teachers = []

    try:
        db.session.commit()
        flash("Class updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating class: {e}", "danger")

    print("\n=== DEBUG ===")
    print("Subject Teacher IDs submitted:", subject_teacher_ids)
    print("Subject Teachers now saved:", [t.id for t in class_obj.subject_teachers])
    print("=================\n")

    return redirect(url_for("class_bp.manage_classes"))