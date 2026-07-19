"""Report access control."""

from flask_login import current_user

from models import Teacher


def _same_school(user, student):
    if not getattr(user, "school_id", None) or not getattr(student, "school_id", None):
        return True
    return user.school_id == student.school_id


def can_view_student(student):
    user = current_user
    if not user.is_authenticated:
        return False
    if user.is_admin() or user.is_finance():
        return _same_school(user, student)
    if user.is_parent():
        return student.parent_id == user.id and _same_school(user, student)
    if user.is_student() and user.student_profile:
        return user.student_profile.id == student.id
    if user.is_teacher():
        return _teacher_can_view_student(user, student)
    return False


def can_view_class(class_obj):
    user = current_user
    if not user.is_authenticated:
        return False
    if user.is_admin() or user.is_finance():
        return True
    if user.is_teacher():
        teacher = Teacher.query.filter_by(user_id=user.id).first()
        if not teacher:
            return False
        if class_obj.class_teacher_id == teacher.id:
            return True
        if class_obj in teacher.classes:
            return True
        if class_obj in getattr(teacher, "teaching_classes", []):
            return True
    return False


def _teacher_can_view_student(user, student):
    if not student.current_class_id:
        return False
    from models import Class

    cls = Class.query.get(student.current_class_id)
    return cls and can_view_class(cls)


def require_report_hub_access():
    """Admin/finance/teacher may open the reports hub."""
    user = current_user
    return user.is_authenticated and (
        user.is_admin() or user.is_finance() or user.is_teacher()
    )
