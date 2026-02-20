from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from extensions import db, mail
from models import (
    Student,
    FeePayment,
    FeeStatement,
    SchoolInfo,
    FinanceAuditLog,
)
from decorators import api_roles_required
from io import BytesIO, StringIO
from datetime import datetime
import csv
import uuid
from flask import flash, redirect, url_for, render_template
from flask_mail import Message
from utils import generate_receipt_pdf, SchoolPDF

api_payments_bp = Blueprint("api_payments_bp", __name__, url_prefix="/api/payments")

# -------------------------------------------------
# UTILITIES
# -------------------------------------------------


def generate_receipt_no():
    year = datetime.utcnow().year
    return f"RCPT/{year}/{uuid.uuid4().hex[:6].upper()}"


def log_audit(action):
    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action=action,
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()


def send_receipt_email(student, pdf_bytes, receipt_no):
    if not student.email:
        return

    msg = Message(
        subject=f"Official Fee Receipt {receipt_no}",
        recipients=[student.email],
        body="Attached is your official payment receipt.",
    )
    msg.attach(
        f"receipt_{receipt_no}.pdf",
        "application/pdf",
        pdf_bytes,
    )
    mail.send(msg)


# -------------------------------------------------
# CREATE PAYMENT
# -------------------------------------------------


@api_payments_bp.route("", methods=["POST"])
@login_required
@api_roles_required("finance")
def create_payment():
    data = request.json

    payment = FeePayment(
        student_id=data["student_id"],
        fee_statement_id=data["fee_statement_id"],
        amount_paid=data["amount_paid"],
        payment_method=data["payment_method"],
        receipt_no=generate_receipt_no(),
        approved=False,
    )

    db.session.add(payment)
    db.session.commit()

    log_audit(f"Created payment {payment.receipt_no}")

    return jsonify(
        {
            "message": "Payment recorded (pending approval)",
            "receipt_no": payment.receipt_no,
        }
    ), 201


# -------------------------------------------------
# APPROVE PAYMENT (LOCK + SIGN)
# -------------------------------------------------


@api_payments_bp.route("/<int:payment_id>/approve", methods=["POST"])
@login_required
@api_roles_required("finance")
def approve_payment(payment_id):
    payment = FeePayment.query.get_or_404(payment_id)

    if payment.approved:
        return jsonify({"error": "Already approved"}), 400

    payment.approved = True
    payment.approved_by = current_user.id
    payment.approved_at = datetime.utcnow()

    db.session.commit()

    log_audit(f"Approved payment {payment.receipt_no}")

    # Generate receipt & email
    pdf = generate_receipt_pdf(payment)
    send_receipt_email(payment.student, pdf, payment.receipt_no)

    return jsonify({"payments": [], "message": "Payment approved & receipt sent"}), 200


# -------------------------------------------------
# RECEIPT PDF (DIGITAL SIGNATURE + WATERMARK)
# -------------------------------------------------


def generate_receipt_pdf(payment):
    pdf = SchoolPDF()
    pdf.add_page()
    pdf.watermark("PAID")

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "OFFICIAL PAYMENT RECEIPT", ln=True, align="C")
    pdf.ln(5)

    fields = [
        ("Receipt No", payment.receipt_no),
        ("Student", payment.student.full_name),
        ("Fee Type", payment.fee_statement.fee_type),
        ("Term", f"{payment.fee_statement.term} {payment.fee_statement.year}"),
        ("Amount Paid", f"KES {payment.amount_paid}"),
        ("Balance", f"KES {payment.fee_statement.balance}"),
        ("Method", payment.payment_method),
        ("Approved By", payment.approver.full_name),
        ("Approval Date", payment.approved_at),
    ]

    for label, value in fields:
        pdf.cell(60, 8, label, border=1)
        pdf.cell(0, 8, str(value), border=1, ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(
        0,
        10,
        f"Digitally signed by {payment.approver.full_name}",
        ln=True,
    )

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer.read()


@api_payments_bp.route("/<int:payment_id>/receipt", methods=["GET"])
@login_required
@api_roles_required("finance")
def download_receipt(payment_id):
    payment = FeePayment.query.get_or_404(payment_id)
    pdf_bytes = generate_receipt_pdf(payment)

    return send_file(
        BytesIO(pdf_bytes),
        download_name=f"receipt_{payment.receipt_no}.pdf",
        as_attachment=True,
    )


# -------------------------------------------------
# FEE AGING REPORT (AUDIT-GRADE)
# -------------------------------------------------


@api_payments_bp.route("/aging/pdf", methods=["GET"])
@login_required
@api_roles_required("finance")
def fee_aging_report():
    pdf = SchoolPDF(orientation="L")
    pdf.add_page()
    pdf.watermark("OFFICIAL")
    pdf.set_font("Arial", size=10)

    headers = ["Student", "Fee Type", "Balance", "Days Overdue"]
    for h in headers:
        pdf.cell(60, 8, h, border=1)
    pdf.ln()

    statements = FeeStatement.query.filter(FeeStatement.balance > 0).all()

    for fs in statements:
        days = (datetime.utcnow().date() - fs.due_date).days
        pdf.cell(60, 8, fs.student.full_name, border=1)
        pdf.cell(60, 8, fs.fee_type, border=1)
        pdf.cell(60, 8, str(fs.balance), border=1)
        pdf.cell(60, 8, str(max(days, 0)), border=1)
        pdf.ln()

    file = BytesIO()
    pdf.output(file)
    file.seek(0)

    log_audit("Generated fee aging report")

    return send_file(
        file,
        download_name="fee_aging_report.pdf",
        as_attachment=True,
    )


# -------------------------------------------------
# PAYMENTS REPORT (PDF)
# -------------------------------------------------


@api_payments_bp.route("/report/pdf", methods=["GET"])
@login_required
@api_roles_required("finance")
def payments_report():
    payments = FeePayment.query.all()
    pdf = SchoolPDF(orientation="L")
    pdf.add_page()
    pdf.watermark("OFFICIAL")

    pdf.set_font("Arial", size=9)
    headers = [
        "Receipt",
        "Student",
        "Paid",
        "Balance",
        "Method",
        "Approved",
    ]

    for h in headers:
        pdf.cell(45, 8, h, border=1)
    pdf.ln()

    for p in payments:
        pdf.cell(45, 8, p.receipt_no, border=1)
        pdf.cell(45, 8, p.student.full_name[:15], border=1)
        pdf.cell(45, 8, str(p.amount_paid), border=1)
        pdf.cell(45, 8, str(p.fee_statement.balance), border=1)
        pdf.cell(45, 8, p.payment_method, border=1)
        pdf.cell(45, 8, "Yes" if p.approved else "No", border=1)
        pdf.ln()

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)

    log_audit("Generated payments report")

    return send_file(
        buffer,
        download_name="payments_report.pdf",
        as_attachment=True,
    )


# -------------------------------------------------
# CSV EXPORT (COMPLIANCE SAFE)
# -------------------------------------------------


@api_payments_bp.route("/export/csv", methods=["GET"])
@login_required
@api_roles_required("finance")
def export_csv():
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Receipt", "Student", "Paid", "Balance", "Approved"])

    for p in FeePayment.query.all():
        writer.writerow(
            [
                p.receipt_no,
                p.student.full_name,
                p.amount_paid,
                p.fee_statement.balance,
                "Yes" if p.approved else "No",
            ]
        )

    log_audit("Exported payments CSV")

    output.seek(0)
    return send_file(
        BytesIO(output.getvalue().encode()),
        download_name="payments.csv",
        as_attachment=True,
    )


@api_payments_bp.route("/export/pdf", methods=["GET"])
@login_required
@api_roles_required("finance")
def fee_invoices():
    """
    Generate a PDF report of all fee payments (or filtered by query parameters)
    """
    # Optional filters
    student_id = request.args.get("student_id", type=int)
    class_id = request.args.get("class_id", type=int)
    term = request.args.get("term")
    year = request.args.get("year", type=int)

    # Query payments
    query = FeePayment.query.join(FeeStatement).join(Student)
    if student_id:
        query = query.filter(FeePayment.student_id == student_id)
    if class_id:
        query = query.filter(Student.current_class_id == class_id)
    if term:
        query = query.filter(FeeStatement.term == term)
    if year:
        query = query.filter(FeeStatement.year == year)

    payments = query.order_by(FeePayment.payment_date.desc()).all()
    if not payments:
        flash("⚠️ No payments found for the selected filters.", "warning")
        return redirect(url_for("finance_bp.finance_dashboard"))  # or whichever page

    # Get school info
    school = SchoolInfo.query.first()
    school_name = school.school_name if school else "My School"
    logo_file = school.logo_file if school and school.logo_file else None

    # --- Create PDF ---
    pdf = SchoolPDF(title="School Fee Payments Report")
    pdf.header(school_name)

    # Optional logo
    if logo_file:
        from reportlab.platypus import Image

        pdf.story.append(Image(logo_file, width=100, height=100))
        pdf.story.append(Spacer(1, 12))

    # Table headers
    table_data = [
        [
            "Receipt No",
            "Student Name",
            "Fee Type",
            "Term",
            "Year",
            "Amount Paid",
            "Payment Method",
            "Remaining Balance",
            "Overdue",
            "Date Paid",
        ]
    ]

    # Table rows
    for p in payments:
        table_data.append(
            [
                p.receipt_no,
                p.student.full_name,
                p.fee_statement.fee_type,
                p.fee_statement.term,
                p.fee_statement.year,
                f"{p.amount_paid:.2f}",
                p.payment_method,
                f"{p.fee_statement.balance:.2f}",
                "Yes" if getattr(p.fee_statement, "is_overdue", False) else "No",
                p.payment_date.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

    pdf.table(table_data)

    # Optional watermark / footer
    pdf.paragraph(f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    pdf.paragraph("Official document. School Finance Department.")

    buffer = pdf.build()

    return send_file(
        buffer,
        download_name=f"fee_report_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf",
        as_attachment=True,
        mimetype="application/pdf",
    )
