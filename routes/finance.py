from flask import Blueprint, render_template
from flask import Blueprint, render_template
from flask import Blueprint, render_template
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
from sqlalchemy import func
from datetime import datetime
from extensions import db

finance_bp = Blueprint("finance_bp", __name__, url_prefix="/finance")


@finance_bp.route("/")
@login_required
def finance_dashboard():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    # KPI calculations
    total_billed = sum(f.amount_due for f in FeeStatement.query.all())
    total_collected = sum(p.amount_paid for p in FeePayment.query.all())
    total_outstanding = total_billed - total_collected
    pending_approvals = StaffSalary.query.filter_by(approved=False).count()
    total_students = Student.query.count()

    # Outstanding statements
    outstanding_statements = (
        FeeStatement.query.outerjoin(FeePayment)
        .group_by(FeeStatement.id)
        .having(
            (
                FeeStatement.amount_due
                - func.coalesce(func.sum(FeePayment.amount_paid), 0)
            )
            > 0
        )
        .all()
    )

    # Recent payments
    recent_payments = (
        FeePayment.query.order_by(FeePayment.payment_date.desc()).limit(10).all()
    )

    # Overdue count
    overdue_count = sum(
        1
        for fs in outstanding_statements
        if fs.due_date and fs.due_date < datetime.utcnow()
    )

    return render_template(
        "finance/dashboard.html",
        total_billed=total_billed,
        total_collected=total_collected,
        total_outstanding=total_outstanding,
        pending_approvals=pending_approvals,
        total_students=total_students,
        outstanding_statements=outstanding_statements,
        recent_payments=recent_payments,
        overdue_count=overdue_count,
    )


@finance_bp.route("/payroll")
@login_required
@roles_required("finance")
def payroll_dashboard():
    payrolls = Payroll.query.all()
    return render_template(
        "finance/payroll_dashboard.html",
        payrolls=payrolls,
        total_payroll=sum(p.net_salary for p in payrolls),
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
    payroll = Payroll.query.get_or_404(payroll_id)
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
