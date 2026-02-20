# routes/fees.py
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    abort,
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

fee_bp = Blueprint(
    "fee_bp", __name__, url_prefix="/fees", template_folder="../templates/fees"
)


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
@roles_required("admin")
def admin_view_student_fees(student_id):
    if current_user.role != "admin":
        abort(403)

    # get student by primary key 'id'
    student = Student.query.get_or_404(student_id)

    return _render_student_fees(student)


@fee_bp.route(
    "/admin/statements", methods=["GET", "POST"], endpoint="admin_view_all_statements"
)
@login_required
@roles_required("admin")
def admin_view_all_statements():
    if current_user.role != "admin":
        abort(403)

    page = request.args.get("page", 1, type=int)
    paginated_statements = FeeStatement.query.paginate(
        page=page, per_page=10, error_out=False
    )

    statements = FeeStatement.query.order_by(
        FeeStatement.year.desc(), FeeStatement.term.desc()
    ).all()
    statement_data = []
    for stmt in statements:
        student = Student.query.get(stmt.student_id) if stmt.student_id else None
        statement_data.append(
            {
                "statement": stmt,
                "student": student,
                "student_name": student.full_name if student else "General",
                "amount_due": stmt.amount_due,
                "term": stmt.term,
                "year": stmt.year,
                "fee_type": stmt.fee_type,
            }
        )

    # --- Form for modal ---
    form = FeeStatementForm()
    form.class_id.choices = [
        (c.id, c.name) for c in Class.query.order_by(Class.name).all()
    ]

    if form.validate_on_submit():
        selected_class = Class.query.get(form.class_id.data)
        students = Student.query.filter_by(current_class=selected_class.name).all()
        try:
            for student in students:
                new_statement = FeeStatement(
                    student_id=student.id,
                    term=form.term.data,
                    year=form.year.data,
                    fee_type=form.fee_type.data,
                    amount_due=form.amount_due.data,
                )
                db.session.add(new_statement)
            db.session.commit()
            flash(
                "✅ Fee statements generated for all students in the class!", "success"
            )
            return redirect(url_for("fee_bp.admin_view_all_statements"))
        except Exception as e:
            db.session.rollback()
            flash(f"Database error: {e}", "danger")

    return render_template(
        "fee_statement.html",
        statements=statement_data,
        feestatements=paginated_statements,
        form=form,
    )


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
@fee_bp.route(
    "/admin/add-payment", methods=["GET", "POST"], endpoint="admin_add_payment"
)
@login_required
@roles_required("admin")
def admin_add_payment():
    if current_user.role != "admin":
        abort(403)

    form = None
    try:
        form = FeePaymentForm()
        if (
            hasattr(form, "student")
            and getattr(form.student, "choices", None) is not None
        ):
            students = Student.query.order_by(Student.full_name).all()
            form.student.choices = [(s.id, s.full_name) for s in students]
    except Exception:
        form = None

    if request.method == "POST":
        if form and form.validate_on_submit():
            payment = FeePayment(
                student_id=form.student.data,
                fee_statement_id=getattr(form, "fee_statement_id", None).data
                if hasattr(form, "fee_statement_id")
                else None,
                amount_paid=float(form.amount_paid.data),
                payment_method=form.payment_method.data,
                payment_date=form.payment_date.data or datetime.utcnow(),
                note=getattr(form, "note", None).data
                if hasattr(form, "note", None)
                else None,
            )
            db.session.add(payment)
            db.session.commit()
            flash("Payment recorded.", "success")
            return redirect(url_for("fee_bp.admin_fees_dashboard"))
        else:
            # fallback non-WTForms handling
            student_id = request.form.get("student_id")
            amount_paid = request.form.get("amount_paid")
            if not (student_id and amount_paid):
                flash("Student and amount are required.", "danger")
            else:
                payment = FeePayment(
                    student_id=int(student_id),
                    amount_paid=float(amount_paid),
                    payment_method=request.form.get("payment_method", "Cash"),
                    payment_date=datetime.utcnow(),
                )
                db.session.add(payment)
                db.session.commit()
                flash("Payment recorded.", "success")
                return redirect(url_for("fee_bp.admin_fees_dashboard"))

    return render_template("add_payment.html", form=form)


# -----------------------
# Student/Parent: View fees for a student (this is the route you already had)
# GET /fees/student/<id>
@fee_bp.route("/student/<int:student_id>", endpoint="manage_fees_for_student")
@login_required
def manage_fees_for_student(student_id):
    student = Student.query.all()
    student = FeeStatement.query.get_or_404(student_id)
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
        user_student = getattr(current_user, "student", None)
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
    "/student/make-payment",
    methods=["POST"],
    endpoint="make_payment",
)
@login_required
@roles_required("admin")
def make_payment():
    # find fee statement
    statement = FeeStatement.query.get_or_404(fee_statement_id)

    # permission checks:
    if current_user.role in ["student", "parent"]:
        user_student = getattr(current_user, "student", None)
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

    if amount <= 0:
        if request.is_json:
            return jsonify(
                {"success": False, "message": "Amount must be greater than 0"}
            ), 400
        flash("Amount must be greater than 0", "danger")
        return redirect(
            url_for("fee_bp.manage_fees_for_student", student_id=statement.student_id)
        )

    # Create payment record
    payment = FeePayment(
        student_id=statement.student_id,
        fee_statement_id=fee_statement_id,
        amount_paid=amount,
        payment_method=method,
        statement=statement,
        payment_date=datetime.utcnow(),
        note=note,
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
    except Exception:
        # don't break on notification errors
        db.session.rollback()
        # don't abort - the payment was already committed; this is non-critical

        # In real app you'd log this exception

    # Return JSON for AJAX or redirect for form
    if request.is_json:
        # recompute balance for this statement if you have property
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
    flash("Payment recorded", "success")
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
