"""Build report payloads for templates and exports."""

from datetime import datetime

from sqlalchemy import distinct, func
from sqlalchemy.orm import joinedload

from models import Class, FeeStatement, Grade, Student, Subject, Teacher, User
from services.reports.context import DEFAULT_ASSESSMENT, DEFAULT_TERM
from services.reports.context import (
    classes_query,
    parse_grade_filters,
    school_header,
    students_query,
    teachers_query,
)
from services.reports.ncbe import average_marks, marks_to_ncbe, marks_to_remarks


def _subject_label(subject):
    code = getattr(subject, "code", None)
    if code:
        return code[:8]
    name = subject.name or ""
    return name[:6] if len(name) > 6 else name


def _grades_index(class_obj, term, year, assessment):
    """Map (student_id, subject_id) -> Grade for one class/period."""
    student_ids = [s.id for s in class_obj.students]
    if not student_ids:
        return {}
    rows = Grade.query.filter(
        Grade.student_id.in_(student_ids),
        Grade.term == term,
        Grade.year == year,
        Grade.assessment_type == assessment,
    ).all()
    return {(g.student_id, g.subject_id): g for g in rows}


def build_student_report_card(student, term, year, assessment, school_id=None):
    grades = Grade.query.filter_by(
        student_id=student.id,
        term=term,
        year=year,
        assessment_type=assessment,
    ).all()
    subject_marks = {g.subject.name: g.marks for g in grades}
    class_subjects = list(student.current_class.subjects) if student.current_class else []

    grade_rows = []
    mark_values = []
    for subject in class_subjects:
        marks = subject_marks.get(subject.name)
        if marks is not None:
            mark_values.append(marks)
        grade_rows.append(
            {
                "subject": subject,
                "marks": marks,
                "level": marks_to_ncbe(marks),
                "remarks": marks_to_remarks(marks),
            }
        )

    return {
        "student": student,
        "class": student.current_class,
        "term": term,
        "year": year,
        "assessment": assessment,
        "subjects": class_subjects,
        "subject_marks": subject_marks,
        "grade_rows": grade_rows,
        "average": average_marks(mark_values),
        "school_name": school_header(school_id or getattr(student, "school_id", None)),
        "date_generated": datetime.now(),
    }


def build_class_grade_report(class_obj, term, year, assessment):
    students = list(class_obj.students)
    subjects = list(class_obj.subjects)
    index = _grades_index(class_obj, term, year, assessment)

    grade_matrix = []
    all_student_averages = []

    for student in students:
        row_marks = {}
        values = []
        for sub in subjects:
            g = index.get((student.id, sub.id))
            m = g.marks if g else None
            row_marks[sub.id] = m
            if m is not None:
                values.append(m)
        avg = average_marks(values)
        if avg is not None:
            all_student_averages.append(avg)
        grade_matrix.append(
            {
                "student": student,
                "marks": row_marks,
                "average": avg,
                "ncbe_level": marks_to_ncbe(avg),
            }
        )

    subject_averages = {}
    for sub in subjects:
        marks = [row["marks"][sub.id] for row in grade_matrix if row["marks"][sub.id] is not None]
        subject_averages[sub.id] = sum(marks) / len(marks) if marks else 0

    for sub in subjects:
        sub.short_name = _subject_label(sub)

    return {
        "class": class_obj,
        "term": term,
        "year": year,
        "assessment": assessment,
        "students": grade_matrix,
        "subjects": subjects,
        "subject_averages": subject_averages,
        "class_average": average_marks(all_student_averages) or 0,
        "date_generated": datetime.now(),
    }


def build_student_list(school_id=None):
    students = (
        students_query(school_id)
        .options(joinedload(Student.current_class), joinedload(Student.parent))
        .all()
    )
    return {
        "students": students,
        "school_name": school_header(school_id),
        "date_generated": datetime.now(),
    }


def build_fee_summary(school_id=None):
    q = FeeStatement.query.options(joinedload(FeeStatement.student))
    if school_id:
        q = q.filter_by(school_id=school_id)
    fee_statements = q.all()
    total_due = sum(fs.amount_due for fs in fee_statements)
    total_paid = sum(fs.amount_paid for fs in fee_statements)
    total_balance = sum(fs.balance for fs in fee_statements)
    return {
        "fee_statements": fee_statements,
        "total_due": total_due,
        "total_paid": total_paid,
        "total_balance": total_balance,
        "school_name": school_header(school_id),
        "date_generated": datetime.now(),
    }


def build_teachers_list(school_id=None):
    teachers = teachers_query(school_id)
    rows = []
    for t in teachers:
        teacher_profile = Teacher.query.filter_by(user_id=t.id).first()
        classes = []
        if teacher_profile:
            classes = [c.name for c in teacher_profile.classes]
        rows.append(
            {
                "name": t.full_name or t.username,
                "email": t.email,
                "phone": t.phone or "",
                "classes": ", ".join(classes) if classes else "—",
            }
        )
    return {
        "teachers": teachers,
        "table_rows": rows,
        "school_name": school_header(school_id),
        "date_generated": datetime.now(),
    }


def build_hub_preview(report_type, school_id=None, **filters):
    """Tabular rows for the reports hub preview table."""
    if report_type == "students":
        data = build_student_list(school_id)
        return [
            {
                "admission": s.admission_number,
                "name": s.full_name,
                "class": s.current_class.name if s.current_class else "N/A",
                "status": s.status,
            }
            for s in data["students"]
        ]
    if report_type == "teachers":
        return build_teachers_list(school_id)["table_rows"]
    if report_type == "fees":
        data = build_fee_summary(school_id)
        return [
            {
                "student": fs.student.full_name,
                "term": fs.term,
                "year": fs.year,
                "due": fs.amount_due,
                "paid": fs.amount_paid,
                "balance": fs.balance,
            }
            for fs in data["fee_statements"]
        ]
    if report_type == "grades":
        class_id = filters.get("class_id")
        if not class_id:
            return []
        cls = Class.query.get(class_id)
        if not cls:
            return []
        data = build_class_grade_report(
            cls,
            filters["term"],
            filters["year"],
            filters["assessment"],
        )
        rows = []
        for row in data["students"]:
            entry = {
                "admission": row["student"].admission_number,
                "name": row["student"].full_name,
                "average": f"{row['average']:.1f}" if row["average"] is not None else "—",
                "level": row["ncbe_level"],
            }
            for sub in data["subjects"]:
                m = row["marks"].get(sub.id)
                entry[sub.name] = m if m is not None else "—"
            rows.append(entry)
        return rows
    return []


def student_list_csv_rows(school_id=None):
    data = build_student_list(school_id)
    headers = ["Admission No", "Full Name", "Class", "Parent Phone", "Status"]
    rows = []
    for s in data["students"]:
        rows.append(
            [
                s.admission_number,
                s.full_name,
                s.current_class.name if s.current_class else "",
                s.parent.phone if s.parent else "",
                s.status,
            ]
        )
    return headers, rows


def fee_summary_csv_rows(school_id=None):
    data = build_fee_summary(school_id)
    headers = ["Student", "Term", "Year", "Amount Due", "Amount Paid", "Balance"]
    rows = [
        [
            fs.student.full_name,
            fs.term,
            fs.year,
            fs.amount_due,
            fs.amount_paid,
            fs.balance,
        ]
        for fs in data["fee_statements"]
    ]
    return headers, rows


def teachers_csv_rows(school_id=None):
    data = build_teachers_list(school_id)
    headers = ["Name", "Email", "Phone", "Classes"]
    rows = [
        [r["name"], r["email"], r["phone"], r["classes"]] for r in data["table_rows"]
    ]
    return headers, rows


def class_grades_csv_rows(class_obj, term, year, assessment):
    data = build_class_grade_report(class_obj, term, year, assessment)
    headers = ["Admission No", "Student Name"]
    headers.extend(sub.name for sub in data["subjects"])
    headers.extend(["Average", "NCBE Level"])
    rows = []
    for row in data["students"]:
        line = [row["student"].admission_number, row["student"].full_name]
        for sub in data["subjects"]:
            m = row["marks"].get(sub.id)
            line.append(m if m is not None else "")
        line.append(
            f"{row['average']:.1f}" if row["average"] is not None else ""
        )
        line.append(row["ncbe_level"])
        rows.append(line)
    return headers, rows


def hub_statistics(school_id=None, include_fees=True):
    """Summary metrics for the reports command center."""
    q_students = Student.query
    q_teachers = User.query.filter_by(role="teacher")
    if school_id:
        q_students = q_students.filter_by(school_id=school_id)
        q_teachers = q_teachers.filter_by(school_id=school_id)

    stats = {
        "student_count": q_students.count(),
        "teacher_count": q_teachers.count(),
        "class_count": len(classes_query(school_id)),
        "fee_due": 0,
        "fee_paid": 0,
        "fee_balance": 0,
    }
    if include_fees:
        summary = build_fee_summary(school_id)
        stats["fee_due"] = summary["total_due"]
        stats["fee_paid"] = summary["total_paid"]
        stats["fee_balance"] = summary["total_balance"]
    return stats


def get_report_catalog(can_fees=True):
    """Metadata for report type cards on the hub."""
    catalog = [
        {
            "id": "students",
            "title": "Student Register",
            "description": "Full enrollment list with class assignment and parent contacts.",
            "icon": "fa-user-graduate",
            "supports_pdf": False,
            "supports_csv": True,
            "full_page": "school_student_list",
        },
        {
            "id": "teachers",
            "title": "Teaching Staff",
            "description": "Staff directory with email, phone, and assigned classes.",
            "icon": "fa-chalkboard-teacher",
            "supports_pdf": False,
            "supports_csv": True,
            "full_page": None,
        },
        {
            "id": "grades",
            "title": "Academic Performance",
            "description": "Class grade matrices and individual CBC report cards.",
            "icon": "fa-chart-line",
            "supports_pdf": True,
            "supports_csv": True,
            "full_page": None,
        },
    ]
    if can_fees:
        catalog.insert(
            2,
            {
                "id": "fees",
                "title": "Fee Summary",
                "description": "Outstanding balances, payments, and term-wise fee statements.",
                "icon": "fa-coins",
                "supports_pdf": True,
                "supports_csv": True,
                "full_page": "fee_summary",
            },
        )
    return catalog


def _scoped_grade_query(school_id, term, year, assessment):
    q = Grade.query.filter_by(
        term=term, year=year, assessment_type=assessment
    )
    if school_id:
        q = q.filter_by(school_id=school_id)
    return q


def build_reports_dashboard(
    school_id=None,
    can_fees=True,
    term=None,
    year=None,
    assessment=None,
):
    """
    Full reports-system snapshot: KPIs, fees, academics, per-class breakdown,
    and inventory of every report type with record counts.
    """
    term = term or DEFAULT_TERM
    year = year or datetime.now().year
    assessment = assessment or DEFAULT_ASSESSMENT

    stats = hub_statistics(school_id, include_fees=can_fees)
    gq = _scoped_grade_query(school_id, term, year, assessment)

    grade_entries = gq.count()
    students_graded = (
        gq.with_entities(func.count(distinct(Grade.student_id))).scalar() or 0
    )
    subjects_graded = (
        gq.with_entities(func.count(distinct(Grade.subject_id))).scalar() or 0
    )
    student_total = stats["student_count"] or 0
    grade_coverage = (
        round(students_graded / student_total * 100, 1) if student_total else 0
    )

    subject_total = Subject.query
    if school_id:
        subject_total = subject_total.filter_by(school_id=school_id)
    subject_total = subject_total.count()

    fee_block = None
    if can_fees:
        fq = FeeStatement.query
        if school_id:
            fq = fq.filter_by(school_id=school_id)
        statements = fq.all()
        overdue = sum(1 for fs in statements if fs.is_overdue)
        paid_count = sum(1 for fs in statements if fs.is_paid)
        pending = len(statements) - paid_count
        due = stats["fee_due"] or 0
        collection_rate = round((stats["fee_paid"] / due * 100), 1) if due else 0
        fee_block = {
            "statement_count": len(statements),
            "overdue_count": overdue,
            "paid_count": paid_count,
            "pending_count": pending,
            "collection_rate": collection_rate,
            "due": stats["fee_due"],
            "paid": stats["fee_paid"],
            "balance": stats["fee_balance"],
        }

    class_rows = []
    for cls in classes_query(school_id):
        sq = Student.query.filter_by(current_class_id=cls.id)
        if school_id:
            sq = sq.filter_by(school_id=school_id)
        n_students = sq.count()
        graded_in_class = (
            gq.join(Student, Grade.student_id == Student.id)
            .filter(Student.current_class_id == cls.id)
            .with_entities(func.count(distinct(Grade.student_id)))
            .scalar()
            or 0
        )
        class_coverage = (
            round(graded_in_class / n_students * 100, 1) if n_students else 0
        )
        class_rows.append(
            {
                "id": cls.id,
                "name": cls.name,
                "students": n_students,
                "subjects": len(cls.subjects),
                "graded": graded_in_class,
                "coverage": class_coverage,
            }
        )

    catalog = get_report_catalog(can_fees=can_fees)
    modules = []
    counts = {
        "students": student_total,
        "teachers": stats["teacher_count"],
        "fees": fee_block["statement_count"] if fee_block else 0,
        "grades": grade_entries,
    }
    for item in catalog:
        formats = ["Preview", "HTML"]
        if item.get("supports_csv"):
            formats.append("CSV")
        if item.get("supports_pdf"):
            formats.append("PDF")
        modules.append(
            {
                **item,
                "record_count": counts.get(item["id"], 0),
                "formats": formats,
            }
        )

    return {
        "period": {"term": term, "year": year, "assessment": assessment},
        "stats": stats,
        "academic": {
            "grade_entries": grade_entries,
            "students_graded": students_graded,
            "subjects_graded": subjects_graded,
            "subject_total": subject_total,
            "coverage_pct": grade_coverage,
            "ungraded_students": max(student_total - students_graded, 0),
        },
        "fees": fee_block,
        "classes": class_rows,
        "modules": modules,
        "endpoints": [
            {
                "label": "Reports hub",
                "path": "/reports/generate",
                "icon": "fa-gauge-high",
            },
            {
                "label": "Student register",
                "path": "school_student_list",
                "icon": "fa-list",
            },
            {
                "label": "Fee summary",
                "path": "fee_summary",
                "icon": "fa-receipt",
                "requires_fees": True,
            },
            {
                "label": "Class grade matrix",
                "path": "class_grade_report",
                "icon": "fa-table",
            },
            {
                "label": "Student report card",
                "path": "student_report_card",
                "icon": "fa-id-card",
            },
        ],
    }
