# routes/fees.py
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    abort,send_file
)
from flask_login import login_required, current_user
from datetime import datetime, date
from extensions import db
from decorators import roles_required
from models import FeeStatement, FeePayment, Student, Notification, User, Class
from forms import (
    FeeStatementForm,
    FeePaymentForm,
    StudentForm,
    User,
)  # optional, if you use WTForms

import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
fee_bp = Blueprint(
    "fee_bp", __name__, url_prefix="/fees", template_folder="../templates/fees"
)
@fee_bp.route('/api/student/<int:student_id>/balance')
@login_required
def student_balance(student_id):
    student = Student.query.get_or_404(student_id)
    total_balance = student.get_total_fees_balance()  # your existing method
    return jsonify({
        'balance': total_balance,
        'details': f'Outstanding across {len(student.fee_statements)} statements'
    })

# -----------------------
# Helper: Render student fees (used by student and admin views)
# -----------------------
def _render_student_fees(student):
    """
    Prepares and renders the student fees page. Returns a Flask response.
    """
    # Fee statements for the student
    statements = (
        FeeStatement.query.filter_by(student_id=student.id)
        .order_by(FeeStatement.year.desc(), FeeStatement.term.desc())
        .all()
    )

    # Payments for those statements (or general payments linked by student_id)
    payments = (
        FeePayment.query.filter_by(student_id=student.id)
        .order_by(FeePayment.payment_date.desc())
        .all()
    )

    # aggregate calculations
    total_due = sum(s.amount_due for s in statements)
    # we assume FeeStatement has a property total_paid (or we sum payments)
    # but to be safe we'll compute from FeeStatement.payments if available else FeePayment records
    total_paid = 0.0
    # try to use each statement.total_paid if present; otherwise sum FeePayment entries
    statement_ids = [s.id for s in statements]
    if hasattr(FeeStatement, "payments"):
        total_paid = sum(getattr(s, "total_paid", 0.0) for s in statements)
    else:
        # fallback: sum FeePayment entries that are linked to student
        total_paid = sum(p.amount_paid for p in payments)

    total_balance = total_due - total_paid
    overdue_count = sum(1 for s in statements if getattr(s, "is_overdue", False))
    recent_payments = FeePayment.query.order_by(FeePayment.payment_date.desc()).limit(5).all()
    payments = (
        FeePayment.query.filter_by(student_id=student.id)
        .order_by(FeePayment.payment_date.desc())
        .all()
    )
    # Group statements and payments by year for easier template rendering
    fee_statements_by_year = {}
    payment_history_by_year = {}
    available_years = set()
    current_year = datetime.now().year

    for s in statements:
        year = getattr(s, "year", current_year)
        fee_statements_by_year.setdefault(year, []).append(s)
        available_years.add(year)

    for p in payments:
        year = p.payment_date.year if p.payment_date else current_year
        payment_history_by_year.setdefault(year, []).append(p)
        available_years.add(year)

    available_years = sorted(list(available_years), reverse=True)

    # You can construct a PaymentForm instance here if using WTForms
    payment_form = None
    try:
        payment_form = FeePaymentForm()
    except Exception:
        # If form class missing, ignore; templates should handle missing form gracefully
        payment_form = None

    return render_template(
        "student_fees.html",
        student=student,
        Student=Student,
        statements=statements,
        payments=payments,
        total_due=total_due,
        total_paid=total_paid,
        total_balance=total_balance,
        overdue_count=overdue_count,
        available_years=available_years,
        current_year=current_year,
        fee_statements_by_year=fee_statements_by_year,
        payment_history_by_year=payment_history_by_year,
        payment_history=payments,
        payment_form=payment_form,
        recent_payment=recent_payments
    )


# -----------------------
# Admin: Dashboard listing students and balances
# GET /fees/admin
# -----------------------
@fee_bp.route("/admin", endpoint="admin_fees_dashboard")
@login_required
@roles_required("admin", "finance")
def admin_fees_dashboard():

    students = Student.query.order_by(Student.full_name).all()
    student_fees = []
    for s in students:
        statements = FeeStatement.query.filter_by(student_id=s.id).all()
        total_due = sum(st.amount_due for st in statements)
        # use statement.total_paid if present else compute from FeePayment
        if statements and hasattr(statements[0], "total_paid"):
            total_paid = sum(getattr(st, "total_paid", 0.0) for st in statements)
        else:
            total_paid = sum(
                p.amount_paid for p in FeePayment.query.filter_by(student_id=s.id).all()
            )
        balance = total_due - total_paid
        student_fees.append(
            {
                "student": s,
                "total_due": total_due,
                "total_paid": total_paid,
                "balance": balance,
            }
        )

    return render_template("admin_fees_dashboard.html", student_fees=student_fees)


# -----------------------
# Admin: View a specific student's fees (reuses student template)
# GET /fees/admin/student/<id># Admin: View a specific student's fees
# GET /fees/admin/student/<int:student_id>
@fee_bp.route("/admin/student/<int:student_id>", endpoint="admin_view_student_fees")
@login_required
@roles_required("admin", "finance")
def admin_view_student_fees(student_id):

    # get student by primary key 'id'
    student = Student.query.get_or_404(student_id)

    return _render_student_fees(student)
@fee_bp.route('/api/statement/<int:statement_id>', methods=['GET'])
@login_required
def api_statement_details(statement_id):
    """API endpoint to get statement details"""
    statement = FeeStatement.query.get_or_404(statement_id)

    # Check permissions
    if current_user.role not in ['admin', 'finance']:
        if current_user.role == 'student':
            if not current_user.student_profile or current_user.student_profile.id != statement.student_id:
                return jsonify({'success': False, 'message': 'Permission denied'}), 403
        elif current_user.role == 'parent':
            child_ids = [s.id for s in current_user.students]
            if statement.student_id not in child_ids:
                return jsonify({'success': False, 'message': 'Permission denied'}), 403

    student = Student.query.get(statement.student_id)

    return jsonify({
        'success': True,
        'id': statement.id,
        'student_id': statement.student_id,
        'student_name': student.full_name if student else 'Unknown',
        'term': statement.term,
        'year': statement.year,
        'fee_type': statement.fee_type,
        'amount_due': float(statement.amount_due),
        'amount_paid': float(statement.amount_paid),
        'balance': float(statement.balance),
        'is_paid': statement.is_paid,
        'is_overdue': statement.is_overdue,
        'due_date': statement.due_date.isoformat() if statement.due_date else None,
        'download_url': url_for('fee_bp.download_statement', student_id=statement.student_id, _external=True)
    })
@fee_bp.route('/statement/<int:student_id>/download', methods=['GET'])
@login_required
@roles_required('admin', 'finance')
def download_statement(student_id):
    # Get student
    student = Student.query.get_or_404(student_id)

    # Get all fee statements for this student, ordered by year/term
    statements = FeeStatement.query.filter_by(student_id=student_id)\
        .order_by(FeeStatement.year.desc(), FeeStatement.term.desc()).all()

    if not statements:
        flash('No fee statements found for this student.', 'warning')
        return redirect(url_for('fee_bp.admin_view_all_statements'))

    # Create a PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=72)

    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']

    # Custom style for table header
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading4'],
        alignment=1,  # center
        textColor=colors.white,
        backColor=colors.darkblue,
        fontSize=10
    )

    # Build content
    content = []

    # Title
    content.append(Paragraph(f"Fee Statement for {student.full_name}", title_style))
    content.append(Spacer(1, 0.25*inch))
    content.append(Paragraph(f"Student ID: {student.id} | Class: {student.current_class.name if student.current_class else 'N/A'}",
                             normal_style))
    content.append(Spacer(1, 0.25*inch))

    # Table data
    table_data = [['Term', 'Year', 'Fee Type', 'Amount Due (GHS)', 'Paid (GHS)', 'Balance (GHS)']]
    total_due = 0
    total_paid = 0
    total_balance = 0

    for stmt in statements:
        paid = stmt.amount_paid
        balance = stmt.balance
        total_due += stmt.amount_due
        total_paid += paid
        total_balance += balance
        table_data.append([
            stmt.term,
            str(stmt.year),
            stmt.fee_type,
            f"{stmt.amount_due:,.2f}",
            f"{paid:,.2f}",
            f"{balance:,.2f}"
        ])

    # Add totals row
    table_data.append([
        'TOTALS', '', '',
        f"{total_due:,.2f}",
        f"{total_paid:,.2f}",
        f"{total_balance:,.2f}"
    ])

    # Create table
    table = Table(table_data, colWidths=[1.2*inch, 0.8*inch, 1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))

    content.append(table)
    content.append(Spacer(1, 0.2*inch))

    # Overall balance and status
    overall_balance = total_due - total_paid
    status_text = "✅ Fully Paid" if overall_balance <= 0 else f"⚠️ Outstanding Balance: GHS {overall_balance:,.2f}"
    content.append(Paragraph(f"<b>Overall Status:</b> {status_text}", normal_style))

    # Due date info (if any)
    due_dates = [s.due_date for s in statements if s.due_date]
    if due_dates:
        latest_due = max(due_dates)
        content.append(Spacer(1, 0.1*inch))
        content.append(Paragraph(f"<b>Latest Due Date:</b> {latest_due.strftime('%B %d, %Y')}", normal_style))

    # Build PDF
    doc.build(content)
    buffer.seek(0)

    # Return PDF as attachment
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Fee_Statement_{student.full_name.replace(' ', '_')}_{student.id}.pdf",
        mimetype='application/pdf'
    )
@fee_bp.route("/admin/statements", methods=["GET", "POST"], endpoint="admin_view_all_statements")
@login_required
@roles_required("admin", "finance")
def admin_view_all_statements():
    form=FeeStatementForm()
    page = request.args.get("page", 1, type=int)
    paginated_statements = FeeStatement.query.paginate(page=page, per_page=10, error_out=False)

    statements = FeeStatement.query.order_by(
        FeeStatement.year.desc(), FeeStatement.term.desc()
    ).all()
    students = Student.query.order_by(Student.full_name).all()
    classes = Class.query.order_by(Class.name).all
    statement_data = []
    total_invoiced = 0
    total_paid = 0
    recent_payments = FeePayment.query.order_by(FeePayment.payment_date.desc()).limit(5).all()
    classes = Class.query.order_by(Class.name).all()
    current_year = datetime.now().year
    overdue_count = sum(1 for stmt in statements if stmt.is_overdue)
    for stmt in statements:
        student = Student.query.get(stmt.student_id) if stmt.student_id else None
        paid = stmt.amount_paid
        balance = stmt.balance
        total_invoiced += stmt.amount_due
        total_paid += paid

        statement_data.append({
            "statement": stmt,
            "student": student,
            "student_name": student.full_name if student else "General",
            "amount_due": stmt.amount_due,
            "term": stmt.term,
            "year": stmt.year,
            "fee_type": stmt.fee_type,
            "amount_paid": paid,
            "balance": balance,
            "is_paid": stmt.is_paid,
            "is_overdue": stmt.is_overdue,
        })

    # Calculate totals for summary cards
    outstanding_balance = total_invoiced - total_paid
    payment_percentage = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0

    # Get latest due date
    latest_due_date = None
    for stmt in statements:
        if stmt.due_date and (latest_due_date is None or stmt.due_date > latest_due_date):
            latest_due_date = stmt.due_date

    return render_template(
        "fee_statement.html",
        statements=statement_data,
        students=students,
        feestatements=paginated_statements,
        student=statements[0].student if statements else None,
        transactions=statement_data,  # Reuse statement_data as transactions
        total_invoiced=total_invoiced,
        total_paid=total_paid,
        outstanding_balance=outstanding_balance,
        payment_percentage=payment_percentage,
        due_date=latest_due_date.strftime('%B %d, %Y') if latest_due_date else None,
        form=form,recent_payments=recent_payments,
    classes=classes,
    current_year=current_year,
    overdue_count=overdue_count
    )

@fee_bp.route("/admin/bulk-generate-all", methods=["POST"], endpoint="admin_bulk_generate_all")
@login_required
@roles_required("admin", "finance")
def admin_bulk_generate_all():
    """Generate fee statements for ALL students with duplicate checking"""

    # Get form data
    term = request.form.get("term")
    year = request.form.get("year", type=int)
    fee_type = request.form.get("fee_type")
    amount_due = request.form.get("amount_due", type=float)
    due_date_str = request.form.get("due_date")

    # Validate required fields
    if not all([term, year, fee_type, amount_due]):
        flash("All fields are required!", "danger")
        return redirect(url_for("fee_bp.admin_view_all_statements"))

    if amount_due <= 0:
        flash("Amount must be greater than 0!", "danger")
        return redirect(url_for("fee_bp.admin_view_all_statements"))

    # Parse due date if provided
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        except ValueError:
            flash("Invalid due date format!", "danger")
            return redirect(url_for("fee_bp.admin_view_all_statements"))

    # Get all active students
    students = Student.query.filter_by(status="active").all()

    if not students:
        flash("No active students found in the system!", "warning")
        return redirect(url_for("fee_bp.admin_view_all_statements"))

    # Track statistics
    created_count = 0
    skipped_count = 0
    skipped_students = []

    try:
        for student in students:
            # Check if a statement already exists for this student with same term, year, fee type
            existing = FeeStatement.query.filter_by(
                student_id=student.id,
                term=term,
                year=year,
                fee_type=fee_type
            ).first()

            if existing:
                skipped_count += 1
                skipped_students.append(student.full_name)
                continue  # Skip this student

            # Create new fee statement
            new_statement = FeeStatement(
                student_id=student.id,
                term=term,
                year=year,
                fee_type=fee_type,
                amount_due=amount_due,
                due_date=due_date
            )
            db.session.add(new_statement)
            created_count += 1

        db.session.commit()

        # Build success message
        message = f"✅ Generated {created_count} fee statements for {len(students)} students."
        if skipped_count > 0:
            message += f" ⚠️ Skipped {skipped_count} student(s) who already had statements for {term} {year} - {fee_type}."
            if len(skipped_students) <= 5:
                message += f" Skipped: {', '.join(skipped_students)}"
            else:
                message += f" Skipped: {', '.join(skipped_students[:5])} and {skipped_count - 5} more."

        flash(message, "success" if created_count > 0 else "warning")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Database error: {str(e)}", "danger")

    return redirect(url_for("fee_bp.admin_view_all_statements"))
# -----------------------
@fee_bp.route(
    "/admin/add-statement", methods=["GET", "POST"], endpoint="admin_add_statement"
)
@login_required
@roles_required("admin", "finance")
def admin_add_statements():
    classes = Class.query.all()
    statements = FeeStatement.query.order_by(FeeStatement.created_at.desc()).all()
    form = FeeStatementForm()

    # Populate class dropdown dynamically
    form.class_id.choices = [(0, "All Classes")] + [(c.id, c.name) for c in classes]

    if form.validate_on_submit():
        term = form.term.data
        year = int(form.year.data)
        fee_type = form.fee_type.data
        amount_due = float(form.amount_due.data)
        class_id = int(form.class_id.data)

        # Get target students
        if class_id == 0:
            target_students = Student.query.all()
        else:
            target_students = Student.query.filter_by(current_class_id=class_id).all()

        added_count = 0
        for student in target_students:
            # Skip if statement exists
            existing = FeeStatement.query.filter_by(
                student_id=student.id, term=term, year=year, fee_type=fee_type
            ).first()
            if existing:
                continue

            new_statement = FeeStatement(
                student_id=student.id,
                term=term,
                year=year,
                fee_type=fee_type,
                amount_due=amount_due,
            )
            db.session.add(new_statement)
            added_count += 1

        try:
            db.session.commit()
            flash(f"✅ Fee statements added for {added_count} student(s).", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Database error: {e}", "danger")

        return redirect(url_for("fee_bp.admin_view_all_statements"))

    return render_template(
        "Add_fee_statement.html",
        statements=statements,
        form=form,
        classes=classes,
    )


# -----------------------
# Admin: Add payment (manual admin entry)
# POST /fees/admin/add-payment
# -----------------------
@fee_bp.route("/admin/add-payment", methods=["GET", "POST"], endpoint="admin_add_payment")
@login_required
@roles_required("admin")
def admin_add_payment():
    form = FeePaymentForm()

    # Populate student choices – use the correct field name 'student'
    students = Student.query.order_by(Student.full_name).all()
    form.student.choices = [(s.id, s.full_name) for s in students]   # <-- FIXED

    # Fetch recent payments for the side panel
    recent_payments = FeePayment.query.order_by(FeePayment.payment_date.desc()).limit(5).all()

    if form.validate_on_submit():
        # Now use form.student.data
        fee_statement = FeeStatement.query.get(form.fee_statement_id.data)
        if not fee_statement or fee_statement.student_id != form.student.data:
            flash("Invalid fee statement for this student.", "danger")
            return render_template("add_payment.html", form=form, recent_payments=recent_payments)

        payment = FeePayment(
            student_id=form.student.data,          # <-- FIXED
            fee_statement_id=form.fee_statement_id.data,
            amount_paid=form.amount_paid.data,
            payment_date=form.payment_date.data or datetime.utcnow(),
            payment_method=form.payment_method.data,

            receipt_no=form.receipt_no.data
        )
        db.session.add(payment)
        db.session.commit()

        # Send notification (optional)
        student = Student.query.get(form.student.data)   # <-- FIXED
        if student and student.parent:
            from services.notification import send_notification
            title = "Fee Payment Received"
            msg = f"KES {form.amount_paid.data:,.2f} received from {student.full_name}."
            send_notification(student.parent, title, msg, notification_type='fee')

        flash("Payment recorded successfully.", "success")
        return redirect(url_for("fee_bp.admin_fees_dashboard"))

    return render_template("add_payment.html", form=form, recent_payments=recent_payments)
# -----------------------
# Student/Parent: View fees for a student (this is the route you already had)
# GET /fees/student/<id>
@fee_bp.route("/student/<int:student_id>", endpoint="manage_fees_for_student")
@login_required
def manage_fees_for_student(student_id):
    student = Student.query.get_or_404(student_id)
    # student or parent allowed; admin should use /fees/admin/student/<id>

    if current_user.role == "student":
        # Student can only view their own fees
        # Check against the one-to-one relationship defined in models.py (student_profile)
        if (
            not current_user.student_profile
            or current_user.student_profile.id != student_id
        ):
            abort(403)  # <--- FIX: Added indentation

    elif current_user.role == "parent":
        # Parent can view fees for any of their linked children
        # Check against the one-to-many relationship defined in models.py (students)
        child_ids = [s.id for s in current_user.students]
        if student_id not in child_ids:
            abort(403)

    # If the user is an admin, they pass this check and continue.
    # If the user is a teacher, they will also pass, but typically this route
    # would be secured against teacher access if the admin route is separate.

    return _render_student_fees(student)


# -----------------------
# API: Return student fees as JSON
# GET /fees/student/<id>/data?format=json
# -----------------------
@fee_bp.route("/student/<int:student_id>/data", endpoint="student_fees_data")
@login_required
def student_fees_data(student_id):
    # permission same as manage_fees_for_student
    if current_user.role in ["student", "parent"]:
        user_student = getattr(current_user, "student_profile", None)
        if not user_student or user_student.id != student_id:
            abort(403)

    student = Student.query.get_or_404(student_id)
    statements = FeeStatement.query.filter_by(student_id=student.id).all()
    payments = FeePayment.query.filter_by(student_id=student.id).all()

    # serialise minimal info (avoid leaking sensitive data)
    def stmt_to_dict(s):
        return {
            "id": s.id,
            "fee_type": s.fee_type,
            "term": s.term,
            "year": s.year,
            "amount_due": float(s.amount_due),
            "balance": float(getattr(s, "balance", s.amount_due)),
        }

    def pay_to_dict(p):
        return {
            "id": p.id,
            "amount_paid": float(p.amount_paid),
            "payment_date": p.payment_date.isoformat() if p.payment_date else None,
            "method": getattr(p, "payment_method", getattr(p, "method", None)),
            "note": getattr(p, "note", None),
        }

    return jsonify(
        {
            "statements": [stmt_to_dict(s) for s in statements],
            "payments": [pay_to_dict(p) for p in payments],
        }
    )


# -----------------------
# Make a payment (supports form POST and JSON/AJAX)
# POST /fees/<fee_statement_id>/pay
# -----------------------
@fee_bp.route(
    "/student/make-payment/<int:fee_statement_id>",
    methods=["POST"],
    endpoint="make_payment",
)
@login_required
def make_payment(fee_statement_id):
    # find fee statement
    statement = FeeStatement.query.get_or_404(fee_statement_id)

    # permission checks:
    if current_user.role in ["student", "parent"]:
        user_student = getattr(current_user, "student_profile", None)
        if not user_student or user_student.id != statement.student_id:
            abort(403)

    # Accept JSON or form
    if request.is_json:
        data = request.get_json()
        try:
            amount = float(data.get("amount_paid", 0))
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Invalid amount"}), 400
        method = data.get("method", "Cash")
        note = data.get("note")
    else:
        try:
            amount = float(request.form.get("amount_paid", 0))
        except (TypeError, ValueError):
            amount = 0
        method = request.form.get("method", "Cash")
        note = request.form.get("note")

        # Also get transaction_ref if available
        receipt_no = request.form.get("receipt_no")

    if amount <= 0:
        if request.is_json:
            return jsonify(
                {"success": False, "message": "Amount must be greater than 0"}
            ), 400
        flash("Amount must be greater than 0", "danger")
        return redirect(
            url_for("fee_bp.manage_fees_for_student", student_id=statement.student_id)
        )

    # Create payment record - FIXED: removed 'statement' argument
    payment = FeePayment(
        student_id=statement.student_id,
        fee_statement_id=fee_statement_id,
        amount_paid=amount,
        payment_method=method,
        payment_date=datetime.utcnow(),

        receipt_no=receipt_no if 'receipt_no' in locals() else None
    )
    db.session.add(payment)
    db.session.commit()

    # Optionally trigger a Notification object if you have such a model
    try:
        if Notification and hasattr(Notification, "create_for_user"):
            Notification.create_for_user(
                user_id=getattr(current_user, "id", None),
                title="Payment recorded",
                body=f"Payment of {amount:.2f} recorded for {statement.fee_type} ({statement.term} {statement.year}).",
                data={"student_id": statement.student_id, "statement_id": statement.id},
            )
    except Exception as e:
        # Log the error but don't break the flow
        print(f"Notification error: {e}")
        # Don't rollback - the payment was already committed

    # Return JSON for AJAX or redirect for form
    if request.is_json:
        # recompute balance for this statement
        stmt_balance = getattr(statement, "balance", None)
        if stmt_balance is None:
            # compute: amount_due - sum(payments)
            related_payments = FeePayment.query.filter_by(
                fee_statement_id=statement.id
            ).all()
            stmt_balance = statement.amount_due - sum(
                p.amount_paid for p in related_payments
            )
        return jsonify(
            {
                "success": True,
                "message": "Payment recorded",
                "fee_balance": float(stmt_balance),
            }
        )

    flash("Payment recorded successfully!", "success")
    return redirect(
        url_for("fee_bp.manage_fees_for_student", student_id=statement.student_id)
    )

# -----------------------
# Admin: delete fee statement (POST)
# POST /fees/admin/<id>/delete-statement
# -----------------------
@fee_bp.route(
    "/admin/<int:statement_id>/delete-statement",
    methods=["POST"],
    endpoint="admin_delete_statement",
)
@login_required
@roles_required("admin")
def admin_delete_statement(statement_id):
    if current_user.role != "admin":
        abort(403)
    s = FeeStatement.query.get_or_404(statement_id)
    db.session.delete(s)
    db.session.commit()
    flash("Fee statement deleted.", "success")
    return redirect(url_for("fee_bp.admin_fees_dashboard"))


# -----------------------
# Admin: delete a payment (POST)
# POST /fees/admin/<payment_id>/delete-payment
# -----------------------
@fee_bp.route(
    "/admin/<int:payment_id>/delete-payment",
    methods=["POST"],
    endpoint="admin_delete_payment",
)
@login_required
@roles_required("admin")
def admin_delete_payment(payment_id):
    if current_user.role != "admin":
        abort(403)
    p = FeePayment.query.get_or_404(payment_id)
    db.session.delete(p)
    db.session.commit()
    flash("Payment deleted.", "success")
    return redirect(url_for("fee_bp.admin_view_student_fees", student_id=p.student_id))
