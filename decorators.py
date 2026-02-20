import io, csv, re

from functools import wraps
from flask import redirect, url_for, flash, abort, jsonify
from flask_login import current_user
from sqlalchemy import func
from extensions import db
from models import FeeStatement, Student, User



def get_dashboard_stats():
    """Return all dashboard statistics as a dictionary."""
    total_students = Student.query.count()
    total_teachers = User.query.filter_by(role="teacher").count()
    total_parents = User.query.filter_by(role="parent").count()
    total_fees_due = (
        db.session.query(func.sum(FeeStatement.amount_due))
        .filter_by(is_paid=False)
        .scalar()
        or 0
    )
    total_fees_paid = (
        db.session.query(func.sum(FeeStatement.amount_due))
        .filter_by(is_paid=True)
        .scalar()
        or 0
    )

    return {
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_parents": total_parents,
        "total_fees_due": total_fees_due,
        "total_fees_paid": total_fees_paid,
    }


def read_uploaded_file(file):
    """
    Reads an uploaded CSV or Excel file and returns its content
    as a list of normalized dictionaries (lowercase keys, stripped values).
    """

    filename = file.filename.lower()

    if filename.endswith(".csv"):
        stream = io.StringIO(file.stream.read().decode("utf-8"), newline=None)
        reader = csv.DictReader(stream)
        rows = list(reader)

    elif filename.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(file.stream)
            rows = df.to_dict("records")

        except Exception as e:
            raise ValueError(f"Error reading Excel file: {e}")

    else:
        raise ValueError("Unsupported file type. Please upload a CSV or Excel file.")

    # ✅ Normalize headers + values
    normalized_rows = []
    for row in rows:
        normalized_row = {
            str(k).strip().lower(): (str(v).strip() if v is not None else "")
            for k, v in row.items()
        }
        normalized_rows.append(normalized_row)

    return normalized_rows


def process_parent_bulk_upload(data_rows):
    """
    Process bulk upload of parent records.
    data_rows is expected to be a list of dicts with parent details.
    """
    for row in data_rows:
        try:
            # Example structure: {"username": "...", "email": "...", "phone": "..."}
            username = row.get("username")
            email = row.get("email")
            phone = row.get("phone")

            # Create linked user account
            user = User(username=username, email=email, role="parent")
            db.session.add(user)
            db.session.flush()  # ensure user.id is available

            # Create parent profile
            parent = Parent(user_id=user.id, phone=phone)
            db.session.add(parent)

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error processing row {row}: {e}")
            continue

    db.session.commit()
    print("✅ Parent bulk upload complete.")


def api_roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Unauthorized"}), 401

            if current_user.role not in roles:
                return jsonify({"error": "Forbidden"}), 403

            return f(*args, **kwargs)

        return wrapper

    return decorator


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth_bp.login"))

            if current_user.role not in roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("auth_bp.login"))

            return f(*args, **kwargs)

        return wrapper

    return decorator


def normalize_class_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


from sqlalchemy.exc import SQLAlchemyError
from flask import flash, redirect, url_for
from models import (
    Student,
    Subject,
    Grade,
    SchoolInfo,
)  # adjust SchoolSetting name to your config model
from extensions import db

# Known descriptor canonical forms (KICD style)
DESCRIPTORS = {
    "EXCEEDING EXPECTATIONS": "Exceeding Expectations",
    "MEETING EXPECTATIONS": "Meeting Expectations",
    "APPROACHING EXPECTATIONS": "Approaching Expectations",
    "BELOW EXPECTATIONS": "Below Expectations",
}

# Short / alternate codes mapping
ALTS = {
    "EE": "Exceeding Expectations",
    "ME": "Meeting Expectations",
    "AE": "Approaching Expectations",
    "BE": "Below Expectations",
    "E": "Exceeding Expectations",
    "M": "Meeting Expectations",
    "A": "Approaching Expectations",
    "BE": "Below Expectations",
}


def normalize_descriptor(token: str):
    """Return canonical descriptor or None."""
    if not token:
        return None
    tok = token.strip().upper()
    # exact match of long form
    if tok in DESCRIPTORS:
        return DESCRIPTORS[tok]
    # abbreviations / short forms
    if tok in ALTS:
        return ALTS[tok]
    # try removing non letters (e.g. 'Exceeding' => match)
    simplified = "".join(ch for ch in tok if ch.isalpha())
    for k, v in DESCRIPTORS.items():
        if simplified in "".join(ch for ch in k if ch.isalpha()):
            return v
    return None


def load_school_cbc_mapping(school_id):
    """
    Optional: load numeric mapping for descriptors from DB if configured.
    Example table SchoolSetting has key like 'cbc_mapping' storing JSON:
    {"Exceeding Expectations":95, "Meeting Expectations":75, ...}
    """
    try:
        s = SchoolSetting.query.filter_by(
            school_id=school_id, key="cbc_mapping"
        ).first()
        if s and s.value:  # assume JSON stored as text
            import json

            return json.loads(s.value)
    except Exception:
        pass
    return None


def normalize_cbc(value: str):
    """Normalize any CBC descriptor or code to canonical form."""
    if not value:
        return None
    v = value.strip().upper()
    if v in CBC_DESCRIPTORS:
        return CBC_DESCRIPTORS[v]
    if v in CBC_ALTS:
        return CBC_ALTS[v]
    return None


def convert_to_cbc(marks: float) -> str:
    """Convert numeric marks into a CBC level (school can customize thresholds)."""
    if marks >= 80:
        return "Exceeding Expectations"
    elif marks >= 50:
        return "Meeting Expectations"
    elif marks >= 30:
        return "Approaching Expectations"
    else:
        return "Below Expectations"
