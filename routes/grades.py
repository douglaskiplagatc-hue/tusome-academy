# routes/grades.py
import logging
from datetime import datetime
from flask import Blueprint, render_template, flash, request, redirect, url_for, abort
from flask_login import login_required, current_user
from extensions import db
from decorators import roles_required
from models import Grade, Student, Subject, Class
from forms import GradeForm, SubjectForm, StudentForm, ClassForm
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

grade_bp = Blueprint("grade_bp", __name__, url_prefix="/grades")
# Setup logger
logger = logging.getLogger(__name__)
handler = logging.FileHandler("grades_errors.log")  # Logs will be written here
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.ERROR)


from collections import defaultdict


@grade_bp.route("/", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def manage_grades():
    form = GradeForm()
    
    # Get filter parameters
    selected_class = request.args.get("class")
    selected_subject = request.args.get("subject")
    selected_term = request.args.get("term")
    search = request.args.get("search", "").strip()

    # If no subject selected, default to the first subject (or show an error)
    subjects = Subject.query.order_by(Subject.name).all()
    if not selected_subject and subjects:
        selected_subject = subjects[0].name
    elif not subjects:
        flash("No subjects found. Please add subjects first.", "warning")
        return render_template("grades.html", form=form, subjects=[])

    # Base query for classes (all classes, used in filter dropdown)
    classes = Class.query.order_by(Class.name).all()
    # Base query for terms
    terms = ["Term 1", "Term 2", "Term 3"]

    # Build student query with filters
    student_query = Student.query
    if selected_class:
        student_query = student_query.filter(Student.current_class.has(Class.name == selected_class))
    if search:
        student_query = student_query.filter(Student.full_name.ilike(f"%{search}%"))
    
    # Get all matching students (order by name)
    students = student_query.order_by(Student.full_name).all()

    # Fetch all grades for these students for the selected subject and term (if any)
    grade_query = Grade.query.join(Subject).filter(
        Grade.student_id.in_([s.id for s in students]),
        Subject.name == selected_subject
    )
    if selected_term:
        grade_query = grade_query.filter(Grade.term == selected_term)
    
    grades = grade_query.all()

    # Organize grades by student and by exam_type for easy lookup
    grades_by_student = defaultdict(list)
    for g in grades:
        grades_by_student[g.student_id].append(g)

    # Group students by class for the accordion
    class_students = defaultdict(list)
    for s in students:
        class_students[s.current_class_id].append(s)

    # Compute achievement level counts (based on all grades in the filtered set)
    # Compute counts for achievement levels (short keys)
    counts = {
    "exceeding": 0,
    "meeting": 0,
    "approaching": 0,
    "below": 0
}
    for g in grades:
      if g.cbc_level == "Exceeding Expectations":
        counts["exceeding"] += 1
      elif g.cbc_level == "Meeting Expectations":
        counts["meeting"] += 1
      elif g.cbc_level == "Approaching Expectations":
        counts["approaching"] += 1
      else:
        counts["below"] += 1

    level_counts = {
        "Exceeding Expectations": 0,
        "Meeting Expectations": 0,
        "Approaching Expectations": 0,
        "Below Expectations": 0
    }
    for g in grades:
        level_counts[g.cbc_level] += 1   # assuming Grade model has cbc_level field

    # Compute average score per subject for the bar chart (across all grades, not just filtered)
    # If you want the chart to reflect only the filtered term, adjust accordingly.
    subject_avgs = {}
    all_subjects = Subject.query.all()
    for subj in all_subjects:
        subj_grades = Grade.query.filter_by(subject_id=subj.id).all()
        if subj_grades:
            avg = sum(g.marks for g in subj_grades) / len(subj_grades)
        else:
            avg = 0
        subject_avgs[subj.id] = round(avg, 1)

    # Placeholder for competencies and values (you'll need to implement these models)
    competencies = defaultdict(list)   # e.g., {student_id: [{'name':'Communication','level':'Exceeding','evidence':'...'}]}
    values = defaultdict(list)         # {student_id: [{'name':'Patriotism','rating':'Meeting'}]}

    # Pass data to template
    return render_template(
        "grades.html",
        form=form,
        subjects=subjects,
        classes=classes,
        terms=terms,
        selected_class=selected_class,
        selected_subject=selected_subject,
        selected_term=selected_term,
        search=search,
        class_students=dict(class_students),
        grades_by_student=dict(grades_by_student),
        level_counts=level_counts,
        subject_avgs=subject_avgs,
        competencies=competencies,
        values=values,
        counts=counts,
        current_year=datetime.utcnow().year
    )


@grade_bp.route("/student/<int:student_id>")
@login_required

def student_grades_data(student_id):
    # Example logic – replace with real DB calls
    grades = Grade.query.filter_by(student_id=student_id).all()
    if request.args.get("format") == "json":
        return jsonify([g.to_dict() for g in grades])
    return render_template("student_grades.html", grades=grades) @ grade_bp.route(
        "/add-grade", methods=["POST"]
    )


def numeric_to_cbc(mark):
    mark = float(mark)
    if mark >= 63:
        return "EE1"
    elif mark >= 54:
        return "EE2"
    elif mark >= 45:
        return "ME1"
    elif mark >= 36:
        return "ME2"
    elif mark >= 27:
        return "AA1"
    elif mark >= 18:
        return "AA2"
    elif mark >= 9:
        return "BE1"
    else:
        return "BE2"


def rubric_color(rubric):
    colors = {
        "EE1": "green",
        "EE2": "limegreen",
        "ME1": "yellowgreen",
        "ME2": "yellow",
        "AE1": "orange",
        "AE2": "darkorange",
        "BE1": "red",
        "BE2": "darkred",
    }
    return colors.get(rubric, "black")


from utils import numeric_to_cbc, rubric_color


@grade_bp.route("/add", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def add_grade():
    if current_user.role not in ["teacher", "admin"]:
        flash("Access denied.", "danger")
        return redirect(url_for("grade_bp.manage_grades"))

    # --- Get all classes ---
    classes = Class.query.order_by(Class.name).all()

    # --- Determine selected class ---
    selected_class = None
    class_id = request.args.get("class_id", type=int)
    if class_id:
        selected_class = Class.query.get(class_id)

    # --- Subjects taught by this teacher in the selected class ---
    subjects = []
    if selected_class:
        subjects = Subject.query.filter_by(
            teacher_id=user.id, class_id=selected_class.id
        ).all()

    # --- Students in the selected class ---
    students = []
    if selected_class:
        students = Student.query.filter_by(current_class_id=selected_class.id).all()

    # --- Existing grades ---
    existing_grades = {}
    if students:
        for student in students:
            # Fetch grades for this student, teacher, and class
            grade = Grade.query.filter_by(
                student_id=student.id,
                teacher_id=current_user.id,
                class_id=selected_class.id,
            ).first()
            if grade:
                existing_grades[student.id] = grade

    # --- Handle form submission ---
    if request.method == "POST" and selected_class:
        subject_id = int(request.form.get("subject_id"))
        term = request.form.get("term")
        year = int(request.form.get("year", datetime.now().year))

        for student in students:
            mark_input = request.form.get(f"mark_{student.id}")
            if mark_input:
                try:
                    mark = float(mark_input)
                    rubrics = numeric_to_cbc(mark)
                    # Check if grade exists
                    grade = Grade.query.filter_by(
                        student_id=student.id,
                        teacher_id=current_user.id,
                        class_id=selected_class.id,
                        subject_id=subject_id,
                        term=term,
                        year=year,
                    ).first()
                    if grade:
                        grade.marks = mark
                        grade.rubrics = rubrics
                    else:
                        grade = Grade(
                            student_id=student.id,
                            teacher_id=current_user.id,
                            class_id=selected_class.id,
                            subject_id=subject_id,
                            year=year,
                            term=term,
                            marks=mark,
                            rubrics=rubrics,
                            created_at=datetime.utcnow(),
                        )
                        db.session.add(grade)
                except ValueError:
                    flash(f"Invalid mark for {student.full_name}", "warning")
        db.session.commit()
        flash("Grades submitted successfully!", "success")
        return redirect(url_for("grade_bp.add_grade", class_id=selected_class.id))

    return render_template(
        "grades/add_grade.html",
        classes=classes,
        subjects=subjects,
        selected_class=selected_class,
        students=students,
        terms=["Term 1", "Term 2", "Term 3"],
        year=datetime.now().year,
        existing_grades=existing_grades,
        rubric_color=rubric_color,
    )
