# routes/bulk_upload.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from io import StringIO
import csv
from datetime import datetime
from collections import defaultdict

from extensions import db
from models import User, Student, Class, Grade, Subject
from forms import BulkUploadForm

bulk_bp = Blueprint("bulk_bp", __name__, url_prefix="/admin/bulk")

# ----------------- Constants -----------------
# KICD CBC achievement level thresholds (marks percentage)
CBC_LEVELS = {
    'Exceeding Expectations': (80, 100),
    'Meeting Expectations': (60, 79),
    'Approaching Expectations': (40, 59),
    'Below Expectations': (0, 39)
}

# ----------------- Utilities -----------------
def normalise_headers(headers_row):
    """Normalize header strings: strip, lower, replace spaces with underscore."""
    return [h.strip().lower().replace(" ", "_") for h in headers_row]

def parse_csv_content(file_stream_bytes):
    """Return rows (list of lists) from a CSV file bytes stream. Handles BOM and common encodings."""
    text = file_stream_bytes.decode("utf-8-sig")  # removes BOM if present
    reader = csv.reader(StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]  # drop empty rows
    return rows

def parse_class_grade_from_name(class_name):
    """
    Try to extract grade number from class name.
    e.g. "Grade 7 Blue" -> 7, "Grade 6" -> 6.
    Returns int grade if found, else None.
    """
    if not class_name:
        return None
    parts = class_name.split()
    for p in parts:
        try:
            v = int(p)
            return v
        except Exception:
            # remove non-digit suffixes like "7A"
            digits = ''.join(ch for ch in p if ch.isdigit())
            if digits:
                try:
                    return int(digits)
                except Exception:
                    continue
    return None

def find_subject_for_student(subject_name, class_grade):
    """
    Find a Subject object based on subject_name and class_grade.
    - If class_grade < 7 -> prefer subjects whose Subject.level indicates 'primary' or 'lower'
    - If class_grade >=7 -> prefer subjects whose Subject.level indicates 'secondary' or 'upper'
    - If Subject.level is not set or no match, fall back to matching by name only.
    """
    name_norm = subject_name.strip().lower()

    # First, exact name match (case‑insensitive)
    sub = Subject.query.filter(Subject.name.ilike(subject_name)).first()
    if sub:
        return sub

    # Then try level-based search if class_grade known
    if class_grade is not None:
        try:
            if class_grade < 7:
                sub = Subject.query.filter(Subject.level.ilike("%primary%")).filter(
                    Subject.name.ilike(f"%{name_norm}%")).first()
            else:
                sub = Subject.query.filter(Subject.level.ilike("%secondary%")).filter(
                    Subject.name.ilike(f"%{name_norm}%")).first()
            if sub:
                return sub
        except Exception:
            pass

    # Fallback: loose name match
    sub = Subject.query.filter(Subject.name.ilike(f"%{name_norm}%")).first()
    return sub

def derive_cbc_level(marks):
    """Return CBC achievement level for given marks (0-100)."""
    for level, (low, high) in CBC_LEVELS.items():
        if low <= marks <= high:
            return level
    return "Below Expectations"  # fallback

# ----------------- Row processors -----------------
def process_parents(rows):
    """
    rows: list of lists where rows[0] are headers normalized
    Headers expected: username,email,full_name,phone
    Returns dict: {"success": int, "errors": [str,...]}
    """
    results = {"success": 0, "errors": []}
    if not rows or len(rows) < 2:
        results["errors"].append("Empty CSV or missing header/rows.")
        return results

    headers = normalise_headers(rows[0])
    expected = ["username", "email", "full_name", "phone"]
    if not all(h in headers for h in expected):
        results["errors"].append(f"Invalid parent headers. Expected exactly: {', '.join(expected)}")
        return results

    idx = {h: headers.index(h) for h in headers}

    for i, row in enumerate(rows[1:], start=2):
        try:
            data = {h: (row[idx[h]].strip() if idx[h] < len(row) and row[idx[h]] is not None else "") for h in expected}
            if not data["username"] or not data["email"]:
                raise ValueError("Missing username or email.")

            if User.query.filter((User.email == data["email"]) | (User.username == data["username"])).first():
                results["errors"].append(f"Row {i}: User with username/email already exists ({data['username']}/{data['email']}).")
                continue

            new_user = User(
                username=data["username"],
                email=data["email"],
                full_name=data.get("full_name"),
                phone=data.get("phone"),
                role="parent",
                password_hash=generate_password_hash("password123"),
                is_active=True
            )
            db.session.add(new_user)
            db.session.commit()
            results["success"] += 1
        except Exception as e:
            db.session.rollback()
            results["errors"].append(f"Row {i}: {e}")

    return results

def process_students(rows):
    """
    Expected headers:
    admission_number, full_name, parent_email, class_name, date_of_birth(YYYY-MM-DD)
    """
    results = {"success": 0, "errors": []}
    if not rows or len(rows) < 2:
        results["errors"].append("Empty CSV or missing header/rows.")
        return results

    headers = normalise_headers(rows[0])
    expected = ["admission_number", "full_name", "parent_email", "class_name", "date_of_birth"]
    if not all(h in headers for h in expected):
        results["errors"].append(f"Invalid student headers. Expected exactly: {', '.join(expected)}")
        return results

    idx = {h: headers.index(h) for h in headers}

    for i, row in enumerate(rows[1:], start=2):
        try:
            def val(h):
                return row[idx[h]].strip() if idx[h] < len(row) and row[idx[h]] is not None else ""

            admission_number = val("admission_number")
            full_name = val("full_name")
            parent_email = val("parent_email")
            class_name = val("class_name")
            dob_raw = val("date_of_birth")

            if not admission_number or not full_name or not parent_email or not class_name or not dob_raw:
                raise ValueError("Missing one of required fields: admission_number, full_name, parent_email, class_name, date_of_birth.")

            parent = User.query.filter_by(email=parent_email, role="parent").first()
            if not parent:
                raise ValueError(f"Parent with email {parent_email} not found. Upload parents first.")

            class_obj = Class.query.filter_by(name=class_name).first()
            if not class_obj:
                raise ValueError(f"Class '{class_name}' not found. Create class first.")

            try:
                dob = datetime.strptime(dob_raw, "%Y-%m-%d").date()
            except Exception:
                raise ValueError("date_of_birth must be YYYY-MM-DD")

            if Student.query.filter_by(admission_number=admission_number).first():
                results["errors"].append(f"Row {i}: Student with admission number {admission_number} already exists.")
                continue

            new_student = Student(
                admission_number=admission_number,
                full_name=full_name,
                parent_id=parent.id,
                current_class_id=class_obj.id,
                date_of_birth=dob,
                status="active"
            )
            db.session.add(new_student)
            db.session.commit()
            results["success"] += 1
        except Exception as e:
            db.session.rollback()
            results["errors"].append(f"Row {i}: {e}")

    return results

def process_grades(rows):
    """
    Supports both:
    - Long format: headers = admission_number, subject_name, exam_type, marks, term, year
    - Wide format: headers = admission_number, term, year, exam_type, [subject1, subject2, ...]
    Returns dict: {"success": int, "errors": [str,...]}
    """
    results = {"success": 0, "errors": []}
    if not rows or len(rows) < 2:
        results["errors"].append("Empty CSV or missing header/rows.")
        return results

    headers = normalise_headers(rows[0])
    idx = {h: i for i, h in enumerate(headers)}

    # ----- Long format check -----
    long_required = ["admission_number", "subject_name", "exam_type", "marks", "term", "year"]
    if all(h in headers for h in long_required):
        # Process long format (existing logic, updated to use derive_cbc_level)
        for i, row in enumerate(rows[1:], start=2):
            try:
                def val(h):
                    return row[idx[h]].strip() if idx[h] < len(row) and row[idx[h]] is not None else ""

                admission = val("admission_number")
                subject_name = val("subject_name")
                exam_type = val("exam_type")
                marks_raw = val("marks")
                term = val("term")
                year_raw = val("year")

                if not admission or not subject_name or not exam_type or not marks_raw or not term or not year_raw:
                    raise ValueError("Missing required grade fields.")

                if exam_type not in ["Exam 1", "Exam 2", "Exam 3", "Summative"]:
                    raise ValueError(f"exam_type must be one of: Exam 1, Exam 2, Exam 3, Summative (got '{exam_type}').")

                student = Student.query.filter_by(admission_number=admission).first()
                if not student:
                    raise ValueError(f"Student with admission number {admission} not found.")

                class_grade = None
                if student.current_class:
                    class_grade = parse_class_grade_from_name(student.current_class.name)

                subject = find_subject_for_student(subject_name, class_grade)
                if not subject:
                    raise ValueError(f"Subject '{subject_name}' not found for class '{student.current_class.name if student.current_class else '?'}'.")

                try:
                    marks = float(marks_raw)
                except:
                    raise ValueError("Marks must be a number.")
                if not (0 <= marks <= 100):
                    raise ValueError("Marks must be between 0 and 100.")

                try:
                    year = int(year_raw)
                except:
                    raise ValueError("Year must be an integer.")

                existing = Grade.query.filter_by(
                    student_id=student.id,
                    subject_id=subject.id,
                    exam_type=exam_type,
                    term=term,
                    year=year
                ).first()
                if existing:
                    raise ValueError("A grade for this student, subject, exam_type, term, year already exists.")

                cbc_level = derive_cbc_level(marks)

                grade = Grade(
                    student_id=student.id,
                    subject_id=subject.id,
                    exam_type=exam_type,
                    term=term,
                    year=year,
                    marks=marks,
                    percentage=marks,
                    numeric_marks=marks,
                    cbc_level=cbc_level
                )
                db.session.add(grade)
                db.session.commit()
                results["success"] += 1

            except Exception as e:
                db.session.rollback()
                results["errors"].append(f"Row {i}: {e}")
        return results

    # ----- Wide format check -----
    wide_required = ["admission_number", "term", "year", "exam_type"]
    if all(h in headers for h in wide_required):
        # Identify subject columns (everything except wide_required)
        subject_cols = [h for h in headers if h not in wide_required]
        if not subject_cols:
            results["errors"].append("No subject columns found in wide format CSV.")
            return results

        for i, row in enumerate(rows[1:], start=2):
            row_success = True  # flag to track if at least one grade inserted for this row
            try:
                def val(h):
                    return row[idx[h]].strip() if idx[h] < len(row) and row[idx[h]] is not None else ""

                admission = val("admission_number")
                term = val("term")
                year_raw = val("year")
                exam_type = val("exam_type")

                if not admission or not term or not year_raw or not exam_type:
                    raise ValueError("Missing admission_number, term, year, or exam_type.")

                if exam_type not in ["Exam 1", "Exam 2", "Exam 3", "Summative"]:
                    raise ValueError(f"Invalid exam_type: {exam_type}")

                try:
                    year = int(year_raw)
                except:
                    raise ValueError("Year must be an integer.")

                student = Student.query.filter_by(admission_number=admission).first()
                if not student:
                    raise ValueError(f"Student with admission number {admission} not found.")

                class_grade = None
                if student.current_class:
                    class_grade = parse_class_grade_from_name(student.current_class.name)

                # Process each subject column
                for subject_name in subject_cols:
                    marks_raw = val(subject_name)
                    if marks_raw == "":
                        continue  # skip empty cells

                    subject = find_subject_for_student(subject_name, class_grade)
                    if not subject:
                        results["errors"].append(f"Row {i}, subject '{subject_name}': Subject not found.")
                        row_success = False
                        continue

                    try:
                        marks = float(marks_raw)
                    except:
                        results["errors"].append(f"Row {i}, subject '{subject_name}': Marks must be a number.")
                        row_success = False
                        continue

                    if not (0 <= marks <= 100):
                        results["errors"].append(f"Row {i}, subject '{subject_name}': Marks must be 0-100.")
                        row_success = False
                        continue

                    # Check duplicate
                    existing = Grade.query.filter_by(
                        student_id=student.id,
                        subject_id=subject.id,
                        exam_type=exam_type,
                        term=term,
                        year=year
                    ).first()
                    if existing:
                        results["errors"].append(f"Row {i}, subject '{subject_name}': Duplicate grade exists.")
                        row_success = False
                        continue

                    cbc_level = derive_cbc_level(marks)

                    grade = Grade(
                        student_id=student.id,
                        subject_id=subject.id,
                        exam_type=exam_type,
                        term=term,
                        year=year,
                        marks=marks,
                        percentage=marks,
                        numeric_marks=marks,
                        cbc_level=cbc_level
                    )
                    db.session.add(grade)

                # After processing all subjects, commit if at least one grade was added successfully
                if row_success:
                    db.session.commit()
                    results["success"] += 1
                else:
                    db.session.rollback()

            except Exception as e:
                db.session.rollback()
                results["errors"].append(f"Row {i}: {e}")

        return results

    # If neither format matched
    results["errors"].append("CSV headers do not match long format (admission_number,subject_name,exam_type,marks,term,year) or wide format (admission_number,term,year,exam_type + subject columns).")
    return results

# ----------------- Blueprint Route -----------------
@bulk_bp.route("/", methods=["GET", "POST"])
@login_required
def bulk_upload_view():
    form = BulkUploadForm()
    upload_results = None

    if form.validate_on_submit():
        f = form.file.data
        upload_type = form.upload_type.data
        filename = secure_filename(f.filename or "")
        if not filename:
            flash("No file selected.", "danger")
            return render_template("bulk_import.html", form=form)

        ext = filename.lower().rsplit(".", 1)[-1]

        if ext != "csv":
            flash("Only CSV files are supported currently. Please save your spreadsheet as CSV (UTF-8).", "danger")
            return render_template("bulk_import.html", form=form)

        try:
            file_bytes = f.stream.read()
            rows = parse_csv_content(file_bytes)

            if upload_type == "parent_user":
                upload_results = process_parents(rows)
            elif upload_type == "student":
                upload_results = process_students(rows)
            elif upload_type == "grade":
                upload_results = process_grades(rows)
            else:
                flash("Invalid upload type selected.", "danger")
                return render_template("bulk_import.html", form=form)

            if upload_results:
                success = upload_results.get("success", 0)
                errors = upload_results.get("errors", [])
                if success:
                    flash(f"✅ {success} records processed successfully.", "success")
                if errors:
                    flash(f"⚠ {len(errors)} error(s) encountered. See details below.", "warning")
                    for e in errors:
                        flash(e, "danger")

        except Exception as e:
            current_app.logger.exception("Bulk upload unexpected error")
            flash(f"Unexpected error processing file: {e}", "danger")

    else:
        if form.errors:
            for field, errs in form.errors.items():
                for err in errs:
                    flash(f"{field}: {err}", "danger")

    return render_template("bulk_import.html", form=form, upload_results=upload_results)