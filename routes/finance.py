from flask import Blueprint, render_template,redirect,url_for,request,flash
from flask_login import login_required, current_user
from decorators import roles_required
from models import (
    FeeStatement,
    FeePayment,
    Student,
    User,
    StaffSalary,
    FinanceAuditLog,
    SalaryPaymentExecution,
    SalaryApprovalLog,

)
from forms import StaffSalaryForm
from sqlalchemy import func,extract
from datetime import datetime,timedelta
from extensions import db

finance_bp = Blueprint("finance_bp", __name__, url_prefix="/finance")

from calendar import month_name
@finance_bp.route("/dashboard")
@login_required
@roles_required("finance", "admin")
def finance_dashboard():
    # 1. Basic KPIs
    # Total billed: sum of amount_due of all fee statements
    total_billed = db.session.query(func.sum(FeeStatement.amount_due)).scalar() or 0
    # Total collected: sum of amount_paid across all fee payments
    total_collected = db.session.query(func.sum(FeePayment.amount_paid)).scalar() or 0
    # Total outstanding = total billed - total collected
    total_outstanding = total_billed - total_collected

    # Overdue statements: those with balance > 0 and due_date < today
    today = datetime.now().date()
    paid_subq = db.session.query(
    FeePayment.fee_statement_id,
    func.coalesce(func.sum(FeePayment.amount_paid), 0).label('total_paid')
).group_by(FeePayment.fee_statement_id).subquery()

# Main query
    overdue_statements = FeeStatement.query.outerjoin(
    paid_subq, FeeStatement.id == paid_subq.c.fee_statement_id
).filter(
    (FeeStatement.amount_due - func.coalesce(paid_subq.c.total_paid, 0)) > 0,
    FeeStatement.due_date < today
).order_by(FeeStatement.due_date).all()

    overdue_count = len(overdue_statements)
    overdue_total = sum(fs.balance for fs in overdue_statements)
    # Collection rate
    collection_rate = (total_collected / total_billed * 100) if total_billed > 0 else 0

    # 2. Monthly collected & outstanding (for current year)
    current_year = datetime.now().year
    monthly_collected = []
    monthly_outstanding = []
    months = list(range(1, 13))
    for month in months:
        # Collected in this month
        collected = db.session.query(func.sum(FeePayment.amount_paid)).filter(
            extract('year', FeePayment.payment_date) == current_year,
            extract('month', FeePayment.payment_date) == month
        ).scalar() or 0
        monthly_collected.append(collected)

        # Outstanding: sum of balances of fee statements that were due in this month?
        # Simpler: use total billed for the month? Not perfect, but we use a placeholder.
        # For demonstration, we'll use total billed in that month from fee statements.
        billed = db.session.query(func.sum(FeeStatement.amount_due)).filter(
            extract('year', FeeStatement.created_at) == current_year,
            extract('month', FeeStatement.created_at) == month
        ).scalar() or 0
        monthly_outstanding.append(billed - collected)  # approximate outstanding for month

    # 3. Expense distribution – you need an Expense model; if not, use dummy data or skip
    # For now, we create dummy data (replace with actual expenses table if exists)
    expense_distribution = [250000, 120000, 80000, 45000, 30000, 20000]  # Salaries, Infrastructure, etc.

    # 4. Recent payments (last 10)
    recent_payments = FeePayment.query.order_by(FeePayment.payment_date.desc()).limit(10).all()

    # 5. Outstanding statements (balance > 0)
    paid_subq = db.session.query(
    FeePayment.fee_statement_id,
    func.coalesce(func.sum(FeePayment.amount_paid), 0).label('total_paid')
).group_by(FeePayment.fee_statement_id).subquery()

# Main query: balance = amount_due - total_paid
    outstanding_statements = FeeStatement.query.outerjoin(
    paid_subq, FeeStatement.id == paid_subq.c.fee_statement_id
).filter(
    (FeeStatement.amount_due - func.coalesce(paid_subq.c.total_paid, 0)) > 0
).order_by(
    (FeeStatement.amount_due - func.coalesce(paid_subq.c.total_paid, 0)).desc()
).all()
    # 6. Additional stats
    # Average payment per student (total collected / number of students who paid at least once)
    students_who_paid = db.session.query(FeePayment.student_id).distinct().count()
    avg_payment_per_student = total_collected / students_who_paid if students_who_paid > 0 else 0

    # Highest single payment
    highest_payment_record = FeePayment.query.order_by(FeePayment.amount_paid.desc()).first()
    highest_payment = highest_payment_record.amount_paid if highest_payment_record else 0
    highest_payment_student = highest_payment_record.student.full_name if highest_payment_record else "N/A"

    # Collection efficiency (balance < 30 days old maybe, but we use a simple metric)
    # For demonstration, we use percentage of statements fully paid.
    total_statements = FeeStatement.query.count()
    fully_paid_statements = FeeStatement.query.filter(FeeStatement.balance <= 0).count()
    collection_efficiency = (fully_paid_statements / total_statements * 100) if total_statements else 0

    # 7. Growth (compare with previous term) – dummy for now
    collection_growth = 12.5  # placeholder

    # 8. For charts, we also need grade filter data – we'll compute per student class
    # We'll leave that to frontend filtering using DataTables.

    return render_template(
        "finance/dashboard.html",
        total_collected=total_collected,
        total_outstanding=total_outstanding,
        total_billed=total_billed,
        collection_rate=collection_rate,
        overdue_count=overdue_count,
        overdue_total=overdue_total,
        monthly_collected=monthly_collected,
        monthly_outstanding=monthly_outstanding,
        expense_distribution=expense_distribution,
        recent_payments=recent_payments,
        outstanding_statements=outstanding_statements,
        avg_payment_per_student=avg_payment_per_student,
        highest_payment=highest_payment,
        highest_payment_student=highest_payment_student,
        collection_efficiency=collection_efficiency,
        collection_growth=collection_growth,
        current_date=datetime.now()
    )

@finance_bp.route("/payroll")
@login_required
@roles_required("finance")
def payroll_dashboard():
    payrolls = StaffSalary.query.all()
    return render_template(
        "finance/payroll_dashboard.html",
        payrolls=payrolls,
        total_payroll=sum(p.net_salary for p in payrolls if p.net_salary),
        pending_payrolls=sum(1 for p in payrolls if p.status == "PENDING"),
        paid_payrolls=sum(1 for p in payrolls if p.status == "PAID"),
    )


@finance_bp.route("/salary-approvals")
@login_required
@roles_required("finance")
def salary_approvals():
    pending = StaffSalary.query.filter_by(status="PENDING").all()
    return render_template("finance/salary_approvals.html", pending=pending)


@finance_bp.route("/salary/<int:payroll_id>/approve", methods=["POST"])
@login_required
@roles_required("finance")
def approve_salary(payroll_id):
    payroll = StaffSalary.query.get_or_404(payroll_id)
    payroll.status = "PAID"
    db.session.commit()
    return redirect(url_for("finance_bp.salary_approvals"))


@finance_bp.route("/budgeting")
@login_required
def budgeting_dashboard():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    # Annual and term totals
    current_year = datetime.utcnow().year
    current_term = "Term 1"  # can be dynamic
    # Projected income = total billed
    projected_income = sum(
        f.amount_due for f in FeeStatement.query.filter_by(year=current_year).all()
    )
    actual_income = sum(
        p.amount_paid
        for p in FeePayment.query.join(FeeStatement)
        .filter(FeeStatement.year == current_year)
        .all()
    )

    # Total salaries paid this year
    total_salary_budget = sum(
        s.total_pay for s in StaffSalary.query.filter_by(year=current_year).all()
    )
    total_salary_paid = sum(
        s.total_pay
        for s in StaffSalary.query.filter_by(year=current_year, paid=True).all()
    )

    # Department-wise expenditure (use class or staff roles as proxy)
    # Example: Academic Dept = teachers' salaries, Admin Dept = finance/admin salaries
    academic_salaries = sum(
        s.total_pay
        for s in StaffSalary.query.join(
            StaffSalary.staff
        )  # explicitly join the 'staff' relationship
        .filter(User.role == "teacher", StaffSalary.year == current_year)
        .all()
    )

    # Admin/Finance salaries
    admin_salaries = sum(
        s.total_pay
        for s in StaffSalary.query.join(
            StaffSalary.staff
        )  # still join the staff member
        .filter(User.role.in_(["admin", "finance"]), StaffSalary.year == current_year)
        .all()
    )

    return render_template(
        "finance/budgeting.html",
        projected_income=projected_income,
        actual_income=actual_income,
        total_salary_budget=total_salary_budget,
        total_salary_paid=total_salary_paid,
        academic_salaries=academic_salaries,
        admin_salaries=admin_salaries,
        current_year=current_year,
        current_term=current_term,
    )


@finance_bp.route("/report")
@login_required
@roles_required("finance")  # only finance can see
def financial_report():
    student= Student.query.all()
    f= FeePayment.query.all()
    current_year = datetime.utcnow().year

    # Total fees billed and collected
    total_billed = sum(
        f.amount_due for f in FeeStatement.query.filter_by(year=current_year).all()
    )
    total_collected = sum(
        p.amount_paid
        for p in FeePayment.query.join(FeeStatement)
        .filter(FeeStatement.year == current_year)
        .all()
    )
    total_outstanding = total_billed - total_collected

    # Overdue feesfrom sqlalchemy import func, select

    # Subquery to calculate total paid per fee statement
    subquery = (
        db.session.query(
            FeeStatement.id.label("fs_id"),
            FeeStatement.amount_due,
            FeeStatement.due_date,
            func.coalesce(func.sum(FeePayment.amount_paid), 0).label("total_paid"),
        )
        .outerjoin(FeePayment, FeeStatement.id == FeePayment.fee_statement_id)
        .group_by(FeeStatement.id)
        .subquery()
    )

    # Main query: only overdue balances
    overdue_fees = (
        db.session.query(subquery)
        .filter(subquery.c.due_date < datetime.utcnow())
        .filter(subquery.c.amount_due > subquery.c.total_paid)
        .all()
    )

    # Salaries
    total_salary_budget = sum(
        s.total_pay for s in StaffSalary.query.filter_by(year=current_year).all()
    )
    total_salary_paid = sum(
        s.total_pay
        for s in StaffSalary.query.filter_by(year=current_year, paid=True).all()
    )

    # Department-wise salary
    academic_salaries = sum(
        s.total_pay
        for s in StaffSalary.query.join(StaffSalary.staff)
        .filter(User.role == "teacher", StaffSalary.year == current_year)
        .all()
    )
    admin_salaries = sum(
        s.total_pay
        for s in StaffSalary.query.join(StaffSalary.staff)
        .filter(User.role.in_(["admin", "finance"]), StaffSalary.year == current_year)
        .all()
    )

    total_students = Student.query.count()

    return render_template(
        "finance/financial_report.html",
        student=student,
        f=f,
        total_billed=total_billed,
        total_collected=total_collected,
        total_outstanding=total_outstanding,
        overdue_fees=overdue_fees,
        total_salary_budget=total_salary_budget,
        total_salary_paid=total_salary_paid,
        academic_salaries=academic_salaries,
        admin_salaries=admin_salaries,
        total_students=total_students,
        current_year=current_year,
    )
