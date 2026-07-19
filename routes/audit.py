# audit_bp.py
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import FinanceAuditLog, SalaryApprovalLog, SalaryPaymentExecution, User
from extensions import db

audit_bp = Blueprint("audit_bp", __name__, url_prefix="/audit")


# --------------------- Finance Audit Logs ---------------------
@audit_bp.route("/finance")
@login_required
def finance_audit_logs():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    logs = FinanceAuditLog.query.order_by(FinanceAuditLog.id.desc()).all()
    return render_template("audit/finance_logs.html", logs=logs)


# --------------------- Salary Approval Logs ---------------------
@audit_bp.route("/salary_approval")
@login_required
def salary_approval_logs():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    logs = SalaryApprovalLog.query.order_by(SalaryApprovalLog.created_at.desc()).all()
    return render_template("audit/salary_approval_logs.html", logs=logs)


# --------------------- Payment Execution Logs ---------------------
@audit_bp.route("/payment_execution")
@login_required
def payment_execution_logs():
    if not current_user.is_finance() and not current_user.is_admin():
        return "Access Denied", 403

    logs = SalaryPaymentExecution.query.order_by(SalaryPaymentExecution.created_at.desc()).all()
    return render_template("audit/payment_execution_logs.html", logs=logs)