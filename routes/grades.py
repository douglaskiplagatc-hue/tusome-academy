# routes/grades.py

import logging
from datetime import datetime
from flask import Blueprint, render_template, flash, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from extensions import db
from decorators import roles_required, api_roles_required
from models import Grade, Student, Subject, Class, Teacher, LevelSubject, SchoolProfile
from sqlalchemy import or_

grade_bp = Blueprint("grade_bp", __name__, url_prefix="/grades")
logger = logging.getLogger(__name__)

# ------------------- Helper functions -------------------
def numeric_to_cbc(mark):
    """Convert numeric mark to CBC level (simplified)."""
    mark = float(mark)
    if mark >= 80:
        return "EE"
    elif mark >= 60:
        return "ME"
    elif mark >= 40:
        return "AE"
    else:
        return "BE"


# ------------------- Main grades overview (Excel‑style) -------------------
@grade_bp.route('/')
@login_required
@roles_required("admin")
def manage_grades():
    """
    Excel‑style gradebook with one tab per class stream.
    All data is rendered server‑side and passed to Alpine.js for interactive editing.
    """
    # ---- 1. Query Parameters ----
    assessment_type = request.args.get('assessment', 'Exam 1')
    term = request.args.get('term', 1, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    search = request.args.get('search', '').strip()
    classes = Class.query.all()
    subjects = Subject.query.all()
    # ---- 2. School Profile & Subject List ----
    profile = SchoolProfile.query.first()
    school_level = profile.school_level if profile else 'junior'

    # Static column definitions for assessments (used only for reference)
    assessment_columns = [
        {"id": 1, "name": "CAT 1", "max_score": 30},
        {"id": 2, "name": "CAT 2", "max_score": 30},
        {"id": 3, "name": "Exam", "max_score": 70}
    ]

    # Subjects from LevelSubject – these are the actual subjects taught
    level_subjects = LevelSubject.query.filter_by(level_code=school_level)\
                       .order_by(LevelSubject.sort_order).all()
    print("SCHOOL LEVEL:", school_level)
    print("LEVEL SUBJECT COUNT:", len(level_subjects))

    for ls in level_subjects:
        print(
            ls.id,
            ls.subject_code,
            ls.subject_name,
            ls.level_code
    )
    base_subjects = []
    for ls in level_subjects:
        base_subjects.append({
            'id': ls.id,
            'code': ls.subject_code,
            'short_name': ls.subject_name[:10],
            'name': ls.subject_name,
        })

    # ---- 3. Get all distinct (level, stream) pairs from active students ----
    class_streams = db.session.query(
        Class.level, Class.stream
    ).join(Student, Student.current_class_id == Class.id)\
     .filter(Student.status == 'active')\
     .group_by(Class.level, Class.stream)\
     .order_by(Class.level, Class.stream).all()

    # ---- 4. Build tabs (one per stream) with full student data ----
    tabs = []
    for level, stream in class_streams:
        # Students for this specific class
        student_query = Student.query.join(Student.current_class)\
            .filter(Student.status == 'active')\
            .filter(Class.level == level)\
            .filter(Class.stream == stream)

        if search:
            student_query = student_query.filter(
                or_(
                    Student.full_name.ilike(f'%{search}%'),
                    Student.admission_number.ilike(f'%{search}%')
                )
            )
        students = student_query.all()
        student_list = []
        # Prepare data structures

        subject_marks_collection = {subj['id']: [] for subj in base_subjects}
        all_marks = []

        for student in students:
            student_class = student.current_class
            stream_name = student_class.name
            grade_level_str = f"Grade {level}" if level else None

            subject_marks = {}
            marks_list = []

            for subj in base_subjects:
                # Find the subject record for this level
                subject_record = Subject.query.filter(
                    Subject.name == subj['name'],
                    Subject.level == grade_level_str
                ).first()

                marks = None
                if subject_record:
                    grade = Grade.query.filter_by(
                        student_id=student.id,
                        subject_id=subject_record.id,
                        assessment_type=assessment_type,
                        term=f'Term {term}',
                        year=year
                    ).first()
                    marks = grade.marks if grade else None
                    if marks is not None:
                        marks = int(marks)
                        marks_list.append(marks)
                        subject_marks_collection[subj['id']].append(marks)

                subject_marks[subj['id']] = marks

            # Average percentage for this student
            avg_percentage = sum(marks_list) / len(marks_list) if marks_list else 0
            level_code, _ = Grade.get_ncbe_level_and_points(avg_percentage)

            student_list.append({
                'id': student.id,
                'admission_number': student.admission_number,
                'full_name': student.full_name,
                'stream_name': stream_name,
                'subject_marks': subject_marks,
                'average': avg_percentage,
                'ncbe_level': level_code
            })
            all_marks.append(avg_percentage)

        # Subject‑level statistics for this tab
        subjects_with_stats = []
        for subj in base_subjects:
            marks = subject_marks_collection[subj['id']]
            if marks:
                class_avg = sum(marks) / len(marks)
                pass_rate = (sum(1 for m in marks if m >= 40) / len(marks)) * 100
            else:
                class_avg = 0
                pass_rate = 0
            subj_copy = subj.copy()
            subj_copy['class_avg'] = class_avg
            subj_copy['pass_rate'] = pass_rate
            subjects_with_stats.append(subj_copy)

        total_students = len(student_list)
        total_exceeding = sum(1 for s in student_list if s['average'] >= 80)
        total_meeting = sum(1 for s in student_list if 60 <= s['average'] < 80)
        total_approaching = sum(1 for s in student_list if 40 <= s['average'] < 60)
        total_below = sum(1 for s in student_list if s['average'] < 40)
        class_average = sum(all_marks) / total_students if total_students else 0
        class_pass_rate = (sum(1 for m in all_marks if m >= 40) / total_students * 100) if total_students else 0

        tabs.append({
            'grade': level,
            'stream': stream,
            'students': student_list,
            'subjects': subjects_with_stats,
            'summary': {
                'exceeding': total_exceeding,
                'meeting': total_meeting,
                'approaching': total_approaching,
                'below': total_below,
                'class_average': class_average,
                'pass_rate': class_pass_rate
            }
        })

    # ---- 5. Determine default class and subject IDs (for Alpine and UI) ----
    default_subject_id = base_subjects[0]['id'] if base_subjects else None
    if tabs:
        first_tab = tabs[0]
        first_class = Class.query.filter_by(
            level=first_tab['grade'],
            stream=first_tab['stream']
        ).first()
        if first_class:
            default_class_id = first_class.id

    default_subject_id = None

    # Use URL parameters if provided, otherwise fallback to defaults
    class_id = request.args.get('class_id') or default_class_id
    subject_id = request.args.get('subject_id') or default_subject_id

    class_obj = Class.query.get(class_id) if class_id else None
    subject_obj = Subject.query.get(subject_id) if subject_id else None

    # ---- 6. Prepare flattened student list for Alpine.js ----
    all_students = []
    for tab in tabs:
        for student in tab['students']:
            marks_dict = {}
            for subj in base_subjects:
                slug = subj['code'].lower().replace(' ', '_')
                marks_dict[slug] = student['subject_marks'].get(subj['id'])

            avg = student['average']
            status = 'complete' if avg >= 40 else 'warning'  # you can refine this

            all_students.append({
                'id': student['id'],
                'full_name': student['full_name'],
                'admission_number': student['admission_number'],
                'stream': student['stream_name'],
                'total': avg,
                'grade': student['ncbe_level'],
                'avatar': None,
                'status': status,
                **marks_dict
            })

    # ---- 7. Prepare columns for Alpine (one per subject) ----
    # Use 100 as max score (or you can calculate from assessment_columns)

        alpine_columns = []
        for subj in base_subjects:
            subject_record = Subject.query.filter_by(name=subj['name']).first()
            if not subject_record:
                continue
            alpine_columns.append({
                'id': subject_record.id,
                'slug': subj['code'].lower().replace(' ', '_'),
                'label': subj['short_name'],
                'max': subject_record.max_marks if subject_record.max_marks else 100
        })
        print(alpine_columns)
    print(f"📊 Total students for Alpine: {len(all_students)}")

    # ---- 8. Render template with all required data ----
    return render_template(
        'grades.html',
        tabs=tabs,                     # original structure for tab navigation
        students=all_students,         # flat list for Alpine table
        columns=alpine_columns,        # column definitions for Alpine
        term=term,
        year=year,
        classes=classes,
        subjects=subjects,
        student_list=student_list,
        class_id=class_obj.id if class_obj else None,
        subject_id=subject_obj.id if subject_obj else None,
        assessment_type=assessment_type
    )
# ------------------- Grade entry form (old add_grade route) -------------------
@grade_bp.route("/add", methods=["GET"])
@login_required
@roles_required("admin", "teacher")
def add_grade():
    """Teacher grade entry – spreadsheet view."""
    from models import SchoolProfile, Teacher, Class, Subject, Student, Grade

    term = request.args.get("term", "Term 1")
    year = request.args.get("year", type=int, default=datetime.utcnow().year)
    assessment = request.args.get("assessment", "Exam 1")
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    # Determine classes based on role
    if current_user.role == "teacher":
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        if not teacher:
            flash("Teacher profile not found. Please contact admin.", "danger")

        classes = teacher.classes
    else:
        # Admin sees all classes
        classes = Class.query.order_by(Class.name).all()
        teacher = None  # not used for admin

    if not classes:
        flash("No classes assigned to you.", "warning")
        return render_template("add_grade.html", classes_data=[], term=term, year=year, assessment=assessment)

    classes_data = []

    for cls in classes:
        # Get subjects for this class
        if teacher:
            # Teacher: only subjects they teach AND that belong to this class
            teacher_subject_ids = [sub.id for sub in teacher.subjects]
            subjects = Subject.query.filter(
                Subject.class_id == cls.id,
                Subject.id.in_(teacher_subject_ids)
            ).order_by(Subject.name).all()
        else:
            # Admin: all subjects of this class
            subjects = Subject.query.filter_by(class_id=cls.id).order_by(Subject.name).all()

        if not subjects:
            # Skip classes where the teacher has no subjects (or class has no subjects)
            continue

        students = Student.query.filter_by(current_class_id=cls.id).order_by(Student.full_name).all()
        if not students:
            continue
        subjects_data = [
            {'id': s.id, 'name': s.name, 'code': s.code}
            for s in subjects
]
        students_data = [
            {'id': s.id, 'admission_number': s.admission_number, 'full_name': s.full_name}
            for s in students
]


        # Fetch existing grades
        grades = Grade.query.filter(
            Grade.student_id.in_([s.id for s in students]),
            Grade.subject_id.in_([s.id for s in subjects]),
            Grade.term == term,
            Grade.year == year,
            Grade.assessment_type == assessment
        ).all()

        existing_levels = {}
        for g in grades:
            # Store as string key that matches the template's expected format
            existing_levels[f"[{g.student_id},{g.subject_id}]"] = g.cbc_level

        classes_data.append({
            'id': cls.id,
            'name': cls.name,
            'subjects': subjects_data,
            'students': students_data,
            'existing_levels': existing_levels
        })



    return render_template(
        "add_grade.html",
        classes_data=classes_data,
        term=term,
        year=year,
        assessment=assessment
    )


@grade_bp.route('/api/gradebook_data')
@login_required
@api_roles_required('teacher', 'admin')
def gradebook_data():
    class_id = request.args.get('class_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    term = request.args.get('term', type=int)
    year = request.args.get('year', type=int, default=datetime.now().year)
    # List of assessment types we want to show as columns
    assessment_types = request.args.getlist('assessments')  # e.g., cat1,cat2,assign,proj,mid,end

    if not class_id or not subject_id or not assessment_types:
        return jsonify({'success': False, 'message': 'Missing parameters'}), 400

    students = Student.query.join(Student.current_class)\
        .filter(Student.status == 'active', Student.current_class_id == class_id).all()

    result = []
    for s in students:
        student_marks = {}
        for atype in assessment_types:
            grade = Grade.query.filter_by(
                student_id=s.id, subject_id=subject_id,
                assessment_type=atype, term=f'Term {term}', year=year
            ).first()
            student_marks[atype] = grade.marks if grade else None
        result.append({
            'id': s.id,
            'admission_number': s.admission_number,
            'full_name': s.full_name,
            'avatar': s.photo_url or '',
            **student_marks   # spreads keys like cat1, cat2...
        })
    return jsonify({'students': result})

@grade_bp.route('/gradebook')
@login_required
@roles_required('teacher', 'admin')
def gradebook_page():
    # Get selection from query params, with sensible defaults
    class_id = request.args.get('class_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    term = request.args.get('term', 2, type=int)
    year = request.args.get('year', datetime.now().year, type=int)

    # If no class/subject selected, pick the first available (or show error)
    if not class_id:
        first_class = Class.query.filter(Class.students.any()).first()
        class_id = first_class.id if first_class else None
    if not subject_id:
        first_subject = Subject.query.first()
        subject_id = first_subject.id if first_subject else None

    # Get all classes and subjects for dropdowns
    classes = Class.query.order_by(Class.name).all()
    subjects = Subject.query.order_by(Subject.name).all()

    # Columns configuration (you can also fetch from DB if needed)
    columns = [
        {'slug': 'cat1', 'label': 'CAT 1', 'max': 15, 'weight': 0.15},
        {'slug': 'cat2', 'label': 'CAT 2', 'max': 15, 'weight': 0.15},
        {'slug': 'assign', 'label': 'Assign.', 'max': 10, 'weight': 0.10},
        {'slug': 'proj', 'label': 'Proj.', 'max': 10, 'weight': 0.10},
        {'slug': 'mid', 'label': 'Mid', 'max': 20, 'weight': 0.20},
        {'slug': 'end', 'label': 'End', 'max': 30, 'weight': 0.30},
    ]

    return render_template(
        'gradebook.html',
        class_id=class_id,
        subject_id=subject_id,
        term=term,
        year=year,
        columns=columns,
        classes=classes,
        subjects=subjects
    )
