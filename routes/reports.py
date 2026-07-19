# routes/reports.py — thin controllers; logic in services/reports/
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from decorators import roles_required
from models import Class, Student
from routes import dashboard
from services.reports.access import can_view_class, can_view_student, require_report_hub_access
from services.reports.builders import (
    build_class_grade_report,
    build_fee_summary,
    build_hub_preview,
    build_student_list,
    build_student_report_card,
    class_grades_csv_rows,
    fee_summary_csv_rows,
    build_reports_dashboard,
    get_report_catalog,
    hub_statistics,
    student_list_csv_rows,
    teachers_csv_rows,
)
from services.reports.context import (
    classes_query,
    parse_grade_filters,
    parse_hub_request,
    school_header,
)
from services.reports.exporters import csv_response, pdf_fee_summary, pdf_student_report_card

reports_bp = Blueprint("reports_bp", __name__)


def _school_id():
    return getattr(current_user, "school_id", None)


# ---------- Student Report Card ----------
@reports_bp.route("/student/<int:student_id>/report_card")
@login_required
def student_report_card(student_id):
    student = Student.query.get_or_404(student_id)
    if not can_view_student(student):
        abort(403)
    filters = parse_grade_filters(request.args)
    ctx = build_student_report_card(
        student,
        filters["term"],
        filters["year"],
        filters["assessment"],
        school_id=_school_id(),
    )
    if request.args.get("export") == "pdf":
        return pdf_student_report_card(
            student,
            filters["term"],
            filters["year"],
            filters["assessment"],
            ctx["school_name"],
        )
    return render_template("reports/student_report_card.html", **ctx)


# ---------- Class Grade Report ----------
@reports_bp.route("/class/<int:class_id>/grades")
@login_required
def class_grade_report(class_id):
    cls = Class.query.get_or_404(class_id)
    if not can_view_class(cls):
        abort(403)
    filters = parse_grade_filters(request.args)
    ctx = build_class_grade_report(
        cls, filters["term"], filters["year"], filters["assessment"]
    )
    if request.args.get("export") == "csv":
        headers, rows = class_grades_csv_rows(
            cls, filters["term"], filters["year"], filters["assessment"]
        )
        return csv_response(
            f"class_{cls.name}_{filters['term']}_{filters['year']}.csv".replace(" ", "_"),
            headers,
            rows,
        )
    return render_template("reports/class_grade_report.html", **ctx)


# ---------- School Student List ----------
@reports_bp.route("/school/students")
@login_required
@roles_required("admin", "finance", "teacher")
def school_student_list():
    if request.args.get("export") == "csv":
        headers, rows = student_list_csv_rows(_school_id())
        return csv_response("student_register.csv", headers, rows)
    ctx = build_student_list(_school_id())
    return render_template("reports/student_list.html", **ctx)


# ---------- Fee Summary ----------
@reports_bp.route("/fees/summary")
@login_required
@roles_required("admin", "finance")
def fee_summary():
    ctx = build_fee_summary(_school_id())
    if request.args.get("export") == "csv":
        headers, rows = fee_summary_csv_rows(_school_id())
        return csv_response("fee_summary.csv", headers, rows)
    if request.args.get("export") == "pdf":
        return pdf_fee_summary(
            ctx["fee_statements"],
            ctx["school_name"],
            {
                "due": ctx["total_due"],
                "paid": ctx["total_paid"],
                "balance": ctx["total_balance"],
            },
        )
    return render_template("reports/fee_summary.html", **ctx)


# ---------- Generic CSV (frontend JSON) ----------
@reports_bp.route("/export/csv", methods=["POST"])
@login_required
def export_csv():
    data = request.get_json()
    if not data:
        abort(400)
    return csv_response(
        data.get("filename", "report.csv"),
        data.get("headers", []),
        data.get("rows", []),
    )
@reports_bp.route("/")
@reports_bp.route("/generate", methods=["GET", "POST"])
@login_required
def generate_reports() -> str:
    """Main reports dashboard and generation hub."""
    # ------------------------------------------------------------------
    # 1. Permission check
    # ------------------------------------------------------------------
    if not require_report_hub_access():
        abort(403)

    school_id: Optional[int] = getattr(current_user, "school_id", None)

    # ------------------------------------------------------------------
    # 2. Fetch base data for filters (classes & students)
    # ------------------------------------------------------------------
    classes: List[Class] = classes_query(school_id)

    students_query = Student.query
    if school_id is not None:
        students_query = students_query.filter_by(school_id=school_id)
    students: List[Student] = students_query.order_by(Student.full_name).all()

    # ------------------------------------------------------------------
    # 3. Parse filters & form inputs (with defaults)
    # ------------------------------------------------------------------
    # GET uses request.values, POST uses request.form
    input_source = request.values if request.method == "GET" else request.form

    filters: Dict[str, Union[str, int]] = parse_grade_filters(input_source)
    selected_type: str = input_source.get("report_type", "students")
    start_date: str = input_source.get("start_date", "")
    end_date: str = input_source.get("end_date", "")

    # ------------------------------------------------------------------
    # 4. Handle POST (report generation / export)
    # ------------------------------------------------------------------
    report_data: Optional[List[Dict[str, Any]]] = None
    if request.method == "POST":
        hub: Dict[str, Any] = parse_hub_request(request.form)
        export_type: str = hub.get("export_type", "")
        selected_type = hub.get("report_type", selected_type)
        start_date = hub.get("start_date", start_date)
        end_date = hub.get("end_date", end_date)
        filters = hub  # reuse the parsed hub dict (contains term, year, assessment, etc.)

        # ---- 4a. Dedicated report pages (redirects) ----
        if selected_type == "fees":
            if not (current_user.is_admin() or current_user.is_finance()):
                flash("Fee reports require admin or finance access.", "warning")
            elif export_type not in ("csv", "pdf"):
                return redirect(url_for("reports_bp.fee_summary"))

        if selected_type == "students" and not export_type:
            return redirect(url_for("reports_bp.school_student_list"))

        # ---- 4b. Grade report redirects (student or class) ----
        if selected_type == "grades":
            student_id: Optional[int] = hub.get("student_id")
            class_id: Optional[int] = hub.get("class_id")
            q_params: Dict[str, Union[str, int]] = {
                "term": hub.get("term", ""),
                "year": hub.get("year", datetime.now().year),
                "assessment": hub.get("assessment", ""),
            }

            if export_type in ("pdf", "csv"):
                q_params["export"] = export_type

            if student_id and export_type != "csv":
                return redirect(
                    url_for(
                        "reports_bp.student_report_card",
                        student_id=student_id,
                        **q_params,
                    )
                )
            if class_id and export_type != "csv":
                return redirect(
                    url_for(
                        "reports_bp.class_grade_report",
                        class_id=class_id,
                        **q_params,
                    )
                )
            flash("Select a class or student for grade reports.", "warning")
            # fall through to preview

        # ---- 4c. CSV exports from hub ----
        if export_type == "csv":
            if selected_type == "fees" and not (current_user.is_admin() or current_user.is_finance()):
                flash("Fee export requires admin or finance access.", "warning")
            elif selected_type == "students":
                headers, rows = student_list_csv_rows(school_id)
                return csv_response("students.csv", headers, rows)
            elif selected_type == "teachers":
                headers, rows = teachers_csv_rows(school_id)
                return csv_response("teachers.csv", headers, rows)
            elif selected_type == "fees":
                headers, rows = fee_summary_csv_rows(school_id)
                return csv_response("fee_summary.csv", headers, rows)
            elif selected_type == "grades" and hub.get("class_id"):
                cls = Class.query.get(hub["class_id"])
                if cls:
                    headers, rows = class_grades_csv_rows(
                        cls, hub.get("term"), hub.get("year"), hub.get("assessment")
                    )
                    return csv_response("class_grades.csv", headers, rows)

        # ---- 4d. PDF exports from hub ----
        if export_type == "pdf":
            if selected_type == "fees" and not (current_user.is_admin() or current_user.is_finance()):
                flash("Fee export requires admin or finance access.", "warning")
            elif selected_type == "fees":
                ctx = build_fee_summary(school_id)
                return pdf_fee_summary(
                    ctx["fee_statements"],
                    ctx["school_name"],
                    {
                        "due": ctx["total_due"],
                        "paid": ctx["total_paid"],
                        "balance": ctx["total_balance"],
                    },
                )
            elif selected_type == "grades" and hub.get("student_id"):
                student = Student.query.get(hub["student_id"])
                if student and can_view_student(student):
                    ctx = build_student_report_card(
                        student,
                        hub.get("term"),
                        hub.get("year"),
                        hub.get("assessment"),
                        school_id=school_id,
                    )
                    return pdf_student_report_card(
                        student,
                        hub.get("term"),
                        hub.get("year"),
                        hub.get("assessment"),
                        ctx["school_name"],
                    )

        # ---- 4e. Preview data (for dashboard display) ----
        if selected_type == "fees" and not (current_user.is_admin() or current_user.is_finance()):
            report_data = []   # empty preview, but we don't flash here (will show empty table)
        else:
            report_data = build_hub_preview(
                selected_type,
                school_id=school_id,
                **hub
            )

    # ------------------------------------------------------------------
    # 5. Build dashboard widgets & statistics (always run)
    # ------------------------------------------------------------------
    can_fees: bool = current_user.is_admin() or current_user.is_finance()
    hub_stats: Dict[str, Any] = hub_statistics(school_id, include_fees=can_fees)

    raw_dashboard = build_reports_dashboard(
        school_id,
        can_fees=can_fees,
        term=filters.get("term"),
        year=filters.get("year"),
        assessment=filters.get("assessment"),
    )

    # Dashboard cards (from builders.py) – ensure they are a list of dicts
    dashboard_items: List[Dict[str, Any]] = []
    for item in raw_dashboard:
        if isinstance(item, dict):
            # Ensure required keys exist (defaults if missing)
            item.setdefault("title", "Untitled Card")
            item.setdefault("value", 0)
            item.setdefault("icon", "📄")
            item.setdefault("url", None)
            item.setdefault("color", "#6c757d")
            dashboard_items.append(item)
        else:
            # If it's a string, treat it as the title and supply defaults
            dashboard_items.append({
                "title": str(item),
                "value": 0,
                "icon": "📄",
                "url": None,
                "color": "#6c757d"
            })
    # ------------------------------------------------------------------
    # 6. Render the dashboard
    # ------------------------------------------------------------------
    return render_template(
        "reports/dashboard.html",
        classes=classes,
        students=students,
        selected_type=selected_type,
        start_date=start_date,
        end_date=end_date,
        report_data=report_data,
        report_row_count=len(report_data) if report_data else 0,
        filters=filters,
        dashboard=dashboard_items,
        terms=["Term 1", "Term 2", "Term 3"],
        assessments=["Exam 1", "Exam 2", "Exam 3", "Summative"],
        year_default=datetime.now().year,
        school_name=school_header(school_id),
        hub_stats=hub_stats,
        can_fees=can_fees,
        report_catalog=get_report_catalog(can_fees=can_fees),
        generated_at_str=datetime.now().strftime('%B %d, %Y at %I:%M %p'),
    )
