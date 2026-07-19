"""Shared report context: school header and filter parsing."""

from datetime import datetime

from models import Class, SchoolProfile, Student, User


DEFAULT_TERM = "Term 1"
DEFAULT_ASSESSMENT = "Exam 1"
VALID_TERMS = ("Term 1", "Term 2", "Term 3")
VALID_ASSESSMENTS = ("Exam 1", "Exam 2", "Exam 3", "Summative")


def school_header(school_id=None):
    if school_id:
        profile = SchoolProfile.query.get(school_id)
        if profile:
            return profile.school_name
    profile = SchoolProfile.query.first()
    return profile.school_name if profile else "TUSOME SCHOOL"


def parse_grade_filters(args_or_form):
    """Read term/year/assessment from query string or form."""
    source = args_or_form
    term = source.get("term", DEFAULT_TERM)
    if term not in VALID_TERMS:
        term = DEFAULT_TERM
    year = source.get("year", type=int) or datetime.now().year
    assessment = source.get("assessment", DEFAULT_ASSESSMENT)
    if assessment not in VALID_ASSESSMENTS:
        assessment = DEFAULT_ASSESSMENT
    class_id = source.get("class_id", type=int)
    student_id = source.get("student_id", type=int)
    return {
        "term": term,
        "year": year,
        "assessment": assessment,
        "class_id": class_id,
        "student_id": student_id,
    }


def parse_hub_request(form):
    report_type = (form.get("report_type") or "students").strip()
    export_type = (form.get("export_type") or "").strip()
    filters = parse_grade_filters(form)
    filters["report_type"] = report_type
    filters["export_type"] = export_type
    filters["start_date"] = form.get("start_date") or ""
    filters["end_date"] = form.get("end_date") or ""
    return filters


def students_query(school_id=None):
    q = Student.query
    if school_id:
        q = q.filter_by(school_id=school_id)
    return q.order_by(Student.current_class_id, Student.full_name)


def classes_query(school_id=None):
    q = Class.query.order_by(Class.name)
    return q.all()


def teachers_query(school_id=None):
    q = User.query.filter_by(role="teacher")
    if school_id:
        q = q.filter_by(school_id=school_id)
    return q.order_by(User.full_name).all()
