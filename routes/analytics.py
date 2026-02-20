from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import FeeStatement, Student
from datetime import datetime
analytics_bp = Blueprint("analytics_bp", __name__, url_prefix="/analytics")


@analytics_bp.route("/")
@login_required
def analytics_dashboard():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    total_billed = sum(f.amount_due for f in FeeStatement.query.all())
    total_collected = sum(f.amount_paid for f in FeeStatement.query.all())
    total_outstanding = total_billed - total_collected
    all_statements = FeeStatement.query.all()

    # Filter using the balance property
    overdue_statements = [
        fs
        for fs in all_statements
        if fs.balance > 0 and fs.due_date and fs.due_date < datetime.utcnow()
    ]

    overdue_count = len(overdue_statements)

    # Per student aggregation
    student_data = []
    for s in Student.query.all():
        total_due = sum(f.amount_due for f in s.fee_statements)
        total_paid = sum(f.amount_paid for f in s.fee_statements)
        balance = total_due - total_paid
        overdue = sum(1 for f in s.fee_statements if f.is_overdue)
        student_data.append(
            {
                "student": s,
                "total_due": total_due,
                "total_paid": total_paid,
                "balance": balance,
                "overdue_count": overdue,
            }
        )

    return render_template(
        "analytics.html",
        total_billed=total_billed,
        overdue_statements=overdue_statements,
        total_collected=total_collected,
        total_outstanding=total_outstanding,
        overdue_count=overdue_count,
        student_data=student_data,
    )


@analytics_bp.route("/parent")
@login_required
def parent_portal():
    if not current_user.is_parent():
        return "Access Denied", 403
    return render_template("parent_portal.html")


@analytics_bp.route("/reports")
@login_required
def financial_reports():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403
    return render_template("reports.html")


from flask import Blueprint, render_template
from flask_login import login_required, current_user
from datetime import datetime
from models import Student, FeeStatement, StaffSalary


@analytics_bp.route("/")
@login_required
def dashboard():
    if not current_user.is_admin() and not current_user.is_finance():
        return "Access Denied", 403

    # ------------------ FEES / ANALYTICS ------------------
    total_billed = sum(f.amount_due for f in FeeStatement.query.all())
    total_collected = sum(f.amount_paid for f in FeeStatement.query.all())
    total_outstanding = total_billed - total_collected
    overdue_count = FeeStatement.query.filter(
        FeeStatement.balance > 0, FeeStatement.due_date < datetime.utcnow()
    ).count()

    student_data = []
    for s in Student.query.all():
        total_due = sum(f.amount_due for f in s.fee_statements)
        total_paid = sum(f.amount_paid for f in s.fee_statements)
        balance = total_due - total_paid
        overdue = sum(1 for f in s.fee_statements if f.is_overdue)
        student_data.append(
            {
                "student": s,
                "total_due": total_due,
                "total_paid": total_paid,
                "balance": balance,
                "overdue_count": overdue,
            }
        )

    # ------------------ PAYROLL ------------------
    salaries = StaffSalary.query.order_by(
        StaffSalary.year.desc(), StaffSalary.month.desc()
    ).all()
    total_payroll = sum(s.net_pay for s in salaries)
    pending_payrolls = sum(1 for s in salaries if not s.paid)
    paid_payrolls = sum(1 for s in salaries if s.paid)

    # ------------------ Pass to dashboard template ------------------
    return render_template(
        "dashboard.html",
        # Analytics / Fees
        total_billed=total_billed,
        total_collected=total_collected,
        total_outstanding=total_outstanding,
        overdue_count=overdue_count,
        student_data=student_data,
        # Payroll
        salaries=salaries,
        total_payroll=total_payroll,
        pending_payrolls=pending_payrolls,
        paid_payrolls=paid_payrolls,
    )
