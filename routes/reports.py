# reports.py
from flask import (
    Blueprint,
    render_template,
    request,
    send_file,
    flash,
    redirect,
    url_for,
)
from flask_login import login_required, current_user
import csv
import io
from fpdf import FPDF  # pip install fpdf2
from datetime import datetime
from decorators import roles_required

reports_bp = Blueprint("reports_bp", __name__, url_prefix="/reports")


# ----------------------------------------------------
# Helper: Generate PDF
# ----------------------------------------------------
def generate_pdf(report_data, report_type):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"{report_type.title()} Report", ln=True, align="C")
    pdf.ln(10)

    if not report_data:
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, "No data available for selected filters.", ln=True)
        return pdf

    pdf.set_font("Arial", "B", 12)
    # Table headers
    headers = list(report_data[0].keys())
    col_width = pdf.w / (len(headers) + 1)
    for header in headers:
        pdf.cell(col_width, 10, str(header).title(), border=1)
    pdf.ln()

    pdf.set_font("Arial", "", 12)
    # Table rows
    for row in report_data:
        for value in row.values():
            pdf.cell(col_width, 10, str(value), border=1)
        pdf.ln()

    return pdf


# ----------------------------------------------------
# Admin Reports Dashboard
# ----------------------------------------------------
@reports_bp.route("/generate", methods=["GET", "POST"])
@login_required
@roles_required("admin", "finance")
def generate_reports():
    report_data = []
    selected_type = None
    start_date = None
    end_date = None
    export_type = None

    if request.method == "POST":
        selected_type = request.form.get("report_type")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        export_type = request.form.get("export_type")

        # Generate data based on selected report type
        # TODO: Replace below with actual database queries
        if selected_type == "students":
            report_data = [
                {
                    "ID": 1,
                    "Name": "John Doe",
                    "Class": "Grade 1",
                    "Enrollment Date": "2025-01-15",
                },
                {
                    "ID": 2,
                    "Name": "Jane Smith",
                    "Class": "Grade 2",
                    "Enrollment Date": "2025-02-10",
                },
            ]
        elif selected_type == "teachers":
            report_data = [
                {
                    "ID": 1,
                    "Name": "Mr. Kamau",
                    "Subject": "Math",
                    "Hire Date": "2020-03-01",
                },
                {
                    "ID": 2,
                    "Name": "Ms. Achieng",
                    "Subject": "English",
                    "Hire Date": "2019-08-12",
                },
            ]
        elif selected_type == "fees":
            report_data = [
                {
                    "Student": "John Doe",
                    "Amount Due": 5000,
                    "Paid": 3000,
                    "Balance": 2000,
                },
            ]
        elif selected_type == "grades":
            report_data = [
                {"Student": "John Doe", "Subject": "Math", "Grade": "A"},
            ]

        # Export logic
        if export_type == "csv":
            si = io.StringIO()
            writer = csv.DictWriter(si, fieldnames=report_data[0].keys())
            writer.writeheader()
            writer.writerows(report_data)
            output = io.BytesIO()
            output.write(si.getvalue().encode("utf-8"))
            output.seek(0)
            filename = (
                f"{selected_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            return send_file(
                output, mimetype="text/csv", as_attachment=True, download_name=filename
            )
        elif export_type == "pdf":
            pdf = generate_pdf(report_data, selected_type)
            output = io.BytesIO()
            pdf.output(output)
            output.seek(0)
            filename = (
                f"{selected_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            return send_file(
                output,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=filename,
            )

    return render_template(
        "admin/reports.html",
        report_data=report_data,
        selected_type=selected_type,
        start_date=start_date,
        end_date=end_date,
    )


@reports_bp.route("/reports", methods=["GET", "POST"])
@login_required
def finance_reports():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    report_type = None
    export_type = None
    report_data = []

    if request.method == "POST":
        report_type = request.form.get("report_type")
        export_type = request.form.get("export_type")

        # ----------------- Prepare Data -----------------
        if report_type == "student_fees":
            report_data = [
                {
                    "Student": f.student.full_name,
                    "Term": f.term,
                    "Year": f.year,
                    "Amount Due": f.amount_due,
                    "Paid": f.amount_paid,
                    "Balance": f.balance,
                }
                for f in FeeStatement.query.order_by(FeeStatement.year.desc()).all()
            ]
        elif report_type == "teacher_payroll":
            report_data = [
                {
                    "Teacher": s.staff.full_name,
                    "Month": s.month,
                    "Year": s.year,
                    "Total Pay": s.total_pay,
                    "Paid": s.paid,
                    "Approved": s.approved,
                }
                for s in StaffSalary.query.order_by(StaffSalary.year.desc()).all()
            ]
        elif report_type == "department_budgets":
            academic_salaries = sum(
                s.total_pay
                for s in StaffSalary.query.join(User)
                .filter(User.role == "teacher")
                .all()
            )
            admin_salaries = sum(
                s.total_pay
                for s in StaffSalary.query.join(User)
                .filter(User.role.in_(["finance", "admin"]))
                .all()
            )
            report_data = [
                {"Department": "Academic", "Expenditure": academic_salaries},
                {
                    "Department": "Administration & Finance",
                    "Expenditure": admin_salaries,
                },
            ]
        elif report_type == "income_vs_expense":
            total_income = sum(f.amount_due for f in FeeStatement.query.all())
            total_paid_salary = sum(
                s.total_pay for s in StaffSalary.query.filter_by(paid=True).all()
            )
            report_data = [
                {"Category": "Total Billed Fees", "Amount": total_income},
                {"Category": "Total Salaries Paid", "Amount": total_paid_salary},
                {"Category": "Net Balance", "Amount": total_income - total_paid_salary},
            ]

        # ----------------- Export CSV -----------------
        if export_type == "csv" and report_data:
            si = io.StringIO()
            writer = csv.DictWriter(si, fieldnames=report_data[0].keys())
            writer.writeheader()
            writer.writerows(report_data)
            output = io.BytesIO()
            output.write(si.getvalue().encode("utf-8"))
            output.seek(0)
            filename = (
                f"{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            return send_file(
                output,
                mimetype="text/csv",
                as_attachment=True,
                download_name=filename,
            )

        # ----------------- Export PDF -----------------
        elif export_type == "pdf" and report_data:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(
                0,
                10,
                f"{report_type.replace('_', ' ').title()} Report",
                ln=True,
                align="C",
            )
            pdf.ln(10)

            pdf.set_font("Arial", "B", 12)
            headers = list(report_data[0].keys())
            col_width = pdf.w / (len(headers) + 1)
            for header in headers:
                pdf.cell(col_width, 10, str(header), border=1)
            pdf.ln()

            pdf.set_font("Arial", "", 12)
            for row in report_data:
                for value in row.values():
                    pdf.cell(col_width, 10, str(value), border=1)
                pdf.ln()

            output = io.BytesIO()
            pdf.output(output)
            output.seek(0)
            filename = (
                f"{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            return send_file(
                output,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=filename,
            )

    return render_template("finance/reports.html", report_type=report_type)
