# routes/payroll.py

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime

from extensions import db
from decorators import roles_required
from models import StaffSalary, User
from forms import StaffSalaryForm
from sqlalchemy import extract, func

payroll_bp = Blueprint("payroll_bp", __name__, url_prefix="/payroll")


# ---------------------------------------------------------
# Payroll Dashboard (ONLY BOM + TOP_UP)
# ---------------------------------------------------------
@payroll_bp.route("/")
@login_required
@roles_required("admin", "finance")
def payroll_dashboard():
    trend_data = (
        db.session.query(
            extract("month", StaffSalary.payment_date).label("month"),
            func.sum(StaffSalary.paid).label("total"),
        )
        .group_by("month")
        .order_by("month")
        .all()
    )

    trend_months = [int(row.month) for row in trend_data]
    trend_amounts = [float(row.total) for row in trend_data]

    salaries = (
        StaffSalary.query.filter(StaffSalary.salary_source.in_(["BOM", "TOP_UP"]))
        .order_by(StaffSalary.year.desc(), StaffSalary.month.desc())
        .all()
    )

    total_payroll = sum(s.total_pay for s in salaries if not s.paid)
    pending_count = sum(1 for s in salaries if not s.paid)
    paid_count = sum(1 for s in salaries if s.paid)

    return render_template(
        "payroll/dashboard.html",
        salaries=salaries,
        trend_months=trend_months,
        trend_amounts=trend_amounts,
        total_payroll=total_payroll,
        pending_count=pending_count,
        paid_count=paid_count,
    )


# ---------------------------------------------------------
# Create Salary (TSC / BOM / TOP_UP)
# ---------------------------------------------------------
@payroll_bp.route("/create", methods=["GET", "POST"])
@login_required
@roles_required("admin", "finance")
def create_salary():
    form = StaffSalaryForm()
    form.staff_id.choices = [
    (e.id, f"{e.first_name} {e.last_name} ({e.role})")
    for e in Employee.query.filter_by(active=True).all()
]
    if form.validate_on_submit():
        exists = StaffSalary.query.filter_by(
            staff_id=form.staff_id.data, month=form.month.data, year=form.year.data
        ).first()
        if exists:
            flash("Salary already exists for this staff and period.", "danger")
            return redirect(url_for("payroll_bp.create_salary"))
        basic = form.basic_pay.data or 0
        allowances = form.allowances.data or 0
        manual_deductions = form.deductions.data or 0

        gross = basic + allowances

        tax = calculate_tax(gross)
        nssf = calculate_nssf(basic)
        nhif = calculate_nhif(basic)

        total_deductions = manual_deductions + tax + nssf + nhif
        total_pay = gross - total_deductions
        salary_source = form.salary_source.data

        salary = StaffSalary(
            staff_id=form.staff.data.id,
            month=form.month.data,
            year=form.year.data,
            basic_pay=basic,
            allowances=allowance,
            deductions=total_deductions,
            total_pay=total_pay,
            salary_source=salary_source,
            bank_account=form.bank_account.data,
            bank_name=form.bank_name.data,
            paid=True if salary_source == "TSC" else False,
            payment_date=datetime.utcnow() if salary_source == "TSC" else None,
            status="PAID" if salary_source == "TSC" else "PENDING",
        )

        db.session.add(salary)
        db.session.commit()

        flash("Salary record created successfully", "success")
        return redirect(url_for("payroll_bp.payroll_dashboard"))

    return render_template("payroll/create_salary.html", form=form)


# ---------------------------------------------------------
# Edit Salary (Blocked if already paid)
# ---------------------------------------------------------
@payroll_bp.route("/<int:salary_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "finance")
def edit_salary(salary_id):
    salary = StaffSalary.query.get_or_404(salary_id)

    if salary.paid:
        flash("Paid salaries cannot be edited", "warning")
        return redirect(url_for("payroll_bp.payroll_dashboard"))

    form = StaffSalaryForm(obj=salary)

    if form.validate_on_submit():
        salary.basic_pay = form.basic_pay.data
        salary.allowances = form.allowances.data
        salary.deductions = form.deductions.data
        salary.total_pay = (
            form.basic_pay.data + form.allowances.data
        ) - form.deductions.data
        salary.salary_source = form.salary_source.data
        salary.bank_account = form.bank_account.data
        salary.bank_name = form.bank_name.data

        db.session.commit()
        flash("Salary updated successfully", "success")
        return redirect(url_for("payroll_bp.payroll_dashboard"))

    return render_template(
        "payroll/edit_salary.html",
        form=form,
        salary=salary,
    )


# ---------------------------------------------------------
# Approve Salary (BLOCK TSC)
# ---------------------------------------------------------
@payroll_bp.route("/<int:salary_id>/approve", methods=["POST"])
@login_required
@roles_required("admin", "finance")
def approve_salary(salary_id):
    salary = StaffSalary.query.get_or_404(salary_id)

    if salary.salary_source == "TSC":
        flash(
            "TSC salaries are paid by government and cannot be approved here",
            "danger",
        )
        return redirect(url_for("payroll_bp.payroll_dashboard"))

    if salary.paid:
        flash("Salary already paid", "warning")
        return redirect(url_for("payroll_bp.payroll_dashboard"))

    salary.paid = True
    salary.payment_date = datetime.utcnow()
    salary.status = "PAID"

    db.session.commit()
    flash("Salary approved and marked as paid", "success")
    return redirect(url_for("payroll_bp.payroll_dashboard"))


# ---------------------------------------------------------
# Delete Salary (Admin only, unpaid only)
# ---------------------------------------------------------
@payroll_bp.route("/<int:salary_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_salary(salary_id):
    salary = StaffSalary.query.get_or_404(salary_id)

    if salary.paid:
        flash("Paid salaries cannot be deleted", "danger")
        return redirect(url_for("payroll_bp.payroll_dashboard"))

    db.session.delete(salary)
    db.session.commit()
    flash("Salary record deleted successfully", "success")
    return redirect(url_for("payroll_bp.payroll_dashboard"))
