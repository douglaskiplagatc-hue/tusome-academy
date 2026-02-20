# routes/__init__.py
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.classes import class_bp
from routes.grades import grade_bp
from routes.fees import fee_bp
from routes.bulk import bulk_bp
from routes.parents import parent_bp
from routes.reports import reports_bp
from routes.teacher import teacher_bp  # ✅ add
from routes.student import student_bp  # ✅ add
from routes.notification import notifications_bp
from routes.events import events_bp
from routes.timetable import timetable_bp
from routes.attendance import attendance_bp
from routes.api_payments import api_payments_bp
from routes.finance import finance_bp
from routes.dashboard import dashboard_bp
from routes.analytics import analytics_bp
from routes.payroll import payroll_bp
from routes.bursary import bursary_bp
from routes.audit import audit_bp
from routes.employee import employees_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(class_bp, url_prefix="/class")
    app.register_blueprint(grade_bp, url_prefix="/grades")
    app.register_blueprint(fee_bp, url_prefix="/fees")
    app.register_blueprint(bulk_bp, url_prefix="/bulk")
    app.register_blueprint(parent_bp, url_prefix="/parent")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")  # ✅ add
    app.register_blueprint(student_bp, url_prefix="/student")  # ✅ add
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(events_bp, url_prefix="/events")
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    app.register_blueprint(timetable_bp, url_prefix="/timetable")
    app.register_blueprint(api_payments_bp)
    app.register_blueprint(finance_bp, url_prefix="/finance")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(bursary_bp, url_prefix="/dashboard")
    app.register_blueprint(audit_bp, url_prefix="/audit")
    app.register_blueprint(payroll_bp, url_prefix="/payroll")
    app.register_blueprint(analytics_bp, url_prefix="/analytics")
    app.register_blueprint(employees_bp)
