# bulk/routes.py
import csv
import json
import logging
import threading
from io import StringIO

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    Response,
    jsonify,
    current_app,
)
from flask_login import login_required, current_user
from extensions import db
from models import BulkImportResult,Subject,LevelSubject
from forms import BulkUploadForm
from bulk.registry import IMPORTER_REGISTRY
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

bulk_bp = Blueprint("bulk_bp", __name__, url_prefix="/bulk")


# ---------- Helper functions ----------
def convert_wide_grades(rows, headers, defaults=None):
    if defaults is None:
        defaults = {}

    meta_cols = {'admission_number', 'exam_type', 'term', 'year'}
    subject_codes = [h for h in headers if h not in meta_cols]

    long_rows = []
    for row in rows:
        d = dict(zip(headers, row))
        admission = d.get('admission_number', '').strip()
        exam = d.get('exam_type', '').strip() or defaults.get('exam_type', 'Exam 1')
        term = d.get('term', '').strip() or defaults.get('term', 'Term 1')
        year = d.get('year', '').strip() or defaults.get('year', str(datetime.now().year))

        for code in subject_codes:
            marks = d.get(code, '').strip()
            if marks:
                long_rows.append([admission, code.lower(), marks, exam, term, year])

    return {
        'headers': ['admission_number', 'subject', 'marks', 'exam_type', 'term', 'year'],
        'rows': long_rows,
        'total_rows': len(long_rows)
    }
def _save_results(results: dict, school_id: Optional[int] = None) -> None:
    db.session.rollback()

    import_id = results["import_id"]
    record = BulkImportResult.query.get(import_id)

    if record is None:
        record = BulkImportResult(
            id=import_id,
            school_id=school_id,
            status=results["status"],
            total_records=results["total_records"],
            processed=results["processed"],
            success=results["success"],
            errors_json=json.dumps(results["errors"]),
            warnings_json=json.dumps(results["warnings"]),
            details_json=json.dumps(results["details"]),
            progress=results.get("progress", 0),
            start_time=datetime.fromisoformat(results["start_time"])
            if results.get("start_time")
            else None,
            end_time=datetime.fromisoformat(results["end_time"])
            if results.get("end_time")
            else None,
        )
        db.session.add(record)
    else:
        record.school_id = school_id
        record.status = results["status"]
        record.total_records = results["total_records"]
        record.processed = results["processed"]
        record.success = results["success"]
        record.errors_json = json.dumps(results["errors"])
        record.warnings_json = json.dumps(results["warnings"])
        record.details_json = json.dumps(results["details"])
        record.progress = results.get("progress", 0)
        if results.get("start_time"):
            record.start_time = datetime.fromisoformat(results["start_time"])
        if results.get("end_time"):
            record.end_time = datetime.fromisoformat(results["end_time"])

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("Failed to save import results")
        raise


def _load_results(import_id: str) -> dict | None:
    record = BulkImportResult.query.get(import_id)
    return record.to_dict() if record else None


# ---------- Background import function (used only in async mode) ----------
def _run_import_thread(app, importer, parsed, school_id, initial_results):
    try:
        with app.app_context():
            logger.info(f"Thread started for {importer.import_id}")
            results = importer.process(parsed)
            _save_results(results, school_id=school_id)
            logger.info(f"Thread finished. Success: {results['success']}")
    except Exception as e:
        logger.exception(f"Thread failed for {importer.import_id}")
        try:
            with app.app_context():
                error_results = {
                    "import_id": importer.import_id,
                    "status": "failed",
                    "total_records": parsed.get("total_rows", 0),
                    "processed": 0,
                    "success": 0,
                    "errors": [str(e)],
                    "warnings": [],
                    "details": [],
                    "progress": 0,
                    "start_time": initial_results["start_time"],
                    "end_time": datetime.now(timezone.utc).isoformat(),
                }
                _save_results(error_results, school_id=school_id)
        except Exception:
            logger.exception("Failed to save error results")


# ---------- Routes ----------
@bulk_bp.route("/", methods=["GET", "POST"])
@login_required
def bulk_upload_view():
    form = BulkUploadForm()

    # Build template info with proper structure
    template_info = {}

    # First, add the manually defined templates
    manual_templates = {
        "student": {
            "label": "Students",
            "description": "Import Students",
            "formats": ["csv", "xlsx"],
            "columns": [
                {"name": "full_name", "required": True, "type": "string"},
                {"name": "email", "required": False, "type": "string"},
                {"name": "phone", "required": False, "type": "string"},
                {"name": "admission_number", "required": True, "type": "string"},
                {"name": "current_class_id", "required": True, "type": "integer"},
                {"name": "date_of_birth", "required": False, "type": "date"},
                {"name": "gender", "required": False, "type": "string"},
                {"name": "guardian_name", "required": False, "type": "string"},
                {"name": "guardian_phone", "required": False, "type": "string"},
                {"name": "guardian_email", "required": False, "type": "string"},
                {"name": "address", "required": False, "type": "string"}
            ]
        },
        "teacher": {
            "label": "Teachers",
            "description": "Import Teachers",
            "formats": ["csv", "xlsx"],
            "columns": [
                {"name": "full_name", "required": True, "type": "string"},
                {"name": "email", "required": True, "type": "string"},
                {"name": "phone", "required": False, "type": "string"},
                {"name": "employee_id", "required": True, "type": "string"},
                {"name": "department", "required": False, "type": "string"},
                {"name": "date_of_birth", "required": False, "type": "date"},
                {"name": "gender", "required": False, "type": "string"},
                {"name": "address", "required": False, "type": "string"}
            ]
        },
        "grade": {
            "label": "Grades",
            "description": "Import Grades",
            "formats": ["csv", "xlsx"],
            "columns": [
                {"name": "student_id", "required": True, "type": "integer"},
                {"name": "subject", "required": True, "type": "string"},
                {"name": "score", "required": True, "type": "float"},
                {"name": "grade", "required": False, "type": "string"},
                {"name": "exam_type", "required": True, "type": "string"},
                {"name": "term", "required": True, "type": "string"},
                {"name": "year", "required": True, "type": "integer"},
                {"name": "class_id", "required": True, "type": "integer"}
            ]
        },
        "fee": {
            "label": "Fee Statements",
            "description": "Import Fee Statements",
            "formats": ["csv", "xlsx"],
            "columns": [
                {"name": "student_id", "required": True, "type": "integer"},
                {"name": "fee_type", "required": True, "type": "string"},
                {"name": "amount_due", "required": True, "type": "float"},
                {"name": "term", "required": True, "type": "string"},
                {"name": "year", "required": True, "type": "integer"},
                {"name": "due_date", "required": False, "type": "date"},
                {"name": "description", "required": False, "type": "string"}
            ]
        },
        "payment": {
            "label": "Payments",
            "description": "Import Payments",
            "formats": ["csv", "xlsx"],
            "columns": [
                {"name": "student_id", "required": True, "type": "integer"},
                {"name": "fee_statement_id", "required": True, "type": "integer"},
                {"name": "amount_paid", "required": True, "type": "float"},
                {"name": "payment_method", "required": True, "type": "string"},
                {"name": "payment_date", "required": False, "type": "date"},
                {"name": "receipt_no", "required": False, "type": "string"},
                {"name": "reference", "required": False, "type": "string"}
            ]
        },
        "class": {
            "label": "Classes",
            "description": "Import Classes",
            "formats": ["csv", "xlsx"],
            "columns": [
                {"name": "name", "required": True, "type": "string"},
                {"name": "grade_level", "required": False, "type": "string"},
                {"name": "teacher_id", "required": False, "type": "integer"},
                {"name": "capacity", "required": False, "type": "integer"}
            ]
        },
        "subject": {
            "label": "Subjects",
            "description": "Import Subjects",
            "formats": ["csv", "xlsx"],
            "columns": [
                {"name": "name", "required": True, "type": "string"},
                {"name": "code", "required": True, "type": "string"},
                {"name": "class_id", "required": True, "type": "integer"},
                {"name": "teacher_id", "required": False, "type": "integer"}
            ]
        },
        "attendance": {
            "label": "Attendance",
            "description": "Import Attendance",
            "formats": ["csv", "xlsx"],
            "columns": [
                {"name": "student_id", "required": True, "type": "integer"},
                {"name": "date", "required": True, "type": "date"},
                {"name": "status", "required": True, "type": "string"},
                {"name": "class_id", "required": True, "type": "integer"}
            ]
        },
        "parent_user": {
            "label": "Parent Users",
            "description": "Import Parent Users",
            "formats": ["csv", "xlsx"],
            "columns": [
                {"name": "full_name", "required": True, "type": "string"},
                {"name": "email", "required": True, "type": "string"},
                {"name": "phone", "required": True, "type": "string"},
                {"name": "student_id", "required": True, "type": "integer"}
            ]
        }
    }

    # Add all templates from manual_templates
    for key, meta in manual_templates.items():
        template_info[key] = {
            "label": meta.get("label", key.title()),
            "description": meta.get("description", ""),
            "formats": meta.get("formats", ["csv", "xlsx"]),
            "columns": meta.get("columns", []),
            "column_count": len(meta.get("columns", []))
        }

    # Also get from IMPORTER_REGISTRY if available
    if IMPORTER_REGISTRY:
        for key, meta in IMPORTER_REGISTRY.items():
            if key not in template_info:
                # Try to get columns from the importer class
                columns = []
                try:
                    importer_class = meta.get("class")
                    if importer_class:
                        # Check if the class has required_columns and optional_columns
                        importer_instance = importer_class()
                        if hasattr(importer_instance, 'required_columns') and hasattr(importer_instance, 'optional_columns'):
                            for col in importer_instance.required_columns:
                                columns.append({"name": col, "required": True, "type": "string"})
                            for col in importer_instance.optional_columns:
                                columns.append({"name": col, "required": False, "type": "string"})
                except Exception:
                    columns = []

                template_info[key] = {
                    "label": meta.get("label", key.title()),
                    "description": meta.get("description", ""),
                    "formats": ["csv", "xlsx"],
                    "columns": columns,
                    "column_count": len(columns)
                }

    if request.method == "POST":
        upload_type = request.form.get("upload_type")
        if upload_type not in IMPORTER_REGISTRY and upload_type not in manual_templates:
            flash("Invalid upload type selected", "danger")
            return render_template(
                "bulk_import_index.html", form=form, templates=template_info
            )

        file = request.files.get("file")
        if not file:
            flash("Please select a file to upload", "warning")
            return render_template(
                "bulk_import_index.html", form=form, templates=template_info
            )

        # Get the importer class
        importer_class = IMPORTER_REGISTRY.get(upload_type)
        if not importer_class:
            flash(f"No importer found for {upload_type}", "danger")
            return render_template(
                "bulk_import_index.html", form=form, templates=template_info
            )

        importer = importer_class["class"]()
        school_id = getattr(current_user, "school_id", None)

        # Defaults for grade imports
        defaults = {}
        if upload_type == 'grade':
            defaults['exam_type'] = request.form.get('default_exam_type', 'Exam 1')
            defaults['term'] = request.form.get('default_term', 'Term 1')
            defaults['year'] = request.form.get('default_year', str(datetime.now().year))

        initial_results = {
            "import_id": importer.import_id,
            "status": "pending",
            "total_records": 0,
            "processed": 0,
            "success": 0,
            "errors": [],
            "warnings": [],
            "details": [],
            "progress": 0,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": None,
        }
        parsed = None

        try:
            ext = importer.validate_file(file)
            parsed = importer.parse_file(file, ext)

            # Wide‑to‑long conversion for grades
            if upload_type == 'grade':
                from services.grade_utils import convert_wide_grades
                known_subject_codes = {s.code for s in Subject.query.all()}
                if any(col in known_subject_codes for col in parsed['headers']):
                    parsed = convert_wide_grades(parsed['rows'], parsed['headers'], defaults)
                if 'subject' not in parsed['headers'] or 'marks' not in parsed['headers']:
                    parsed = convert_wide_grades(parsed['rows'], parsed['headers'], defaults)

            initial_results["total_records"] = parsed["total_rows"]
            _save_results(initial_results, school_id=school_id)

            # Synchronous mode
            results = importer.process(parsed)
            _save_results(results, school_id=school_id)
            flash("Import completed!", "success")
            return redirect(
                url_for("bulk_bp.import_results", import_id=importer.import_id)
            )

        except Exception as e:
            logger.exception("Bulk import setup failed")
            flash(f"Import setup failed: {str(e)}", "danger")
            db.session.rollback()
            return render_template(
                "bulk_import_index.html", form=form, templates=template_info
            )

    year_default = datetime.now().year
    import_id = request.args.get("import_id")

    return render_template(
        "bulk_import_index.html",
        form=form,
        templates=template_info,
        IMPORTER_REGISTRY=IMPORTER_REGISTRY,
        year_default=year_default,
        import_id=import_id
    )
@bulk_bp.route("/results/<import_id>")
@login_required
def import_results(import_id):
    results = _load_results(import_id)
    if not results:
        flash("Import results not found", "danger")
        return redirect(url_for("bulk_bp.bulk_upload_view"))
    # Create a proper results page (bulk_results.html) that shows errors, etc.
    return render_template("bulk_results.html", results=results)


@bulk_bp.route("/processing/<import_id>")
@login_required
def import_processing(import_id):
    results = _load_results(import_id)
    if not results:
        flash("Import job not found", "warning")
        return redirect(url_for("bulk_bp.bulk_upload_view"))
    return render_template(
        "bulk_processing.html", import_id=import_id, initial_status=results["status"]
    )


@bulk_bp.route("/status/<import_id>")
@login_required
def import_status(import_id):
    results = _load_results(import_id)
    if not results:
        return jsonify({"error": "Not found"}), 404
    return jsonify(results)


@bulk_bp.route("/templates/<template_type>")
@login_required
def download_template(template_type):
    meta = IMPORTER_REGISTRY.get(template_type)
    if not meta:
        return "Invalid template type", 404

    importer = meta["class"]()
    headers = importer.required_columns + importer.optional_columns
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for sample in importer.sample_rows:
        writer.writerow([sample.get(col, "") for col in headers])
    output.seek(0)
    filename = meta.get("template_filename", f"{template_type}_template.csv")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"},
    )
