from datetime import datetime
from flask import has_request_context, request, g
from models import db, Student, Grade, FeePayment, User
from sqlalchemy import event
import json


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = {'extend_existing': True}


    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20), nullable=False)  # INSERT, UPDATE, DELETE
    old_values = db.Column(db.Text)
    new_values = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))


class AuditLogger:
    @staticmethod
    def log_change(table_name, record_id, action, old_values=None, new_values=None, user_id=None):
        """Log database changes safely"""

        # Clean dicts from SQLAlchemy internals
        def clean_data(data):
            if not data:
                return None
            if isinstance(data, dict):
                return {k: str(v) for k, v in data.items() if not k.startswith("_")}
            return str(data)

        # Handle user_id
        current_user_id = user_id or getattr(g, "current_user_id", None)

        # Handle request safely
        ip = None
        ua = None
        if has_request_context():
            ip = request.remote_addr
            ua = request.headers.get("User-Agent")

        audit_log = AuditLog(
            table_name=table_name,
            record_id=record_id,
            action=action,
            old_values=json.dumps(clean_data(old_values)) if old_values else None,
            new_values=json.dumps(clean_data(new_values)) if new_values else None,
            user_id=current_user_id,
            ip_address=ip,
            user_agent=ua,
        )

        db.session.add(audit_log)


# ---- Event listeners ----
@event.listens_for(Student, "after_insert")
def log_student_insert(mapper, connection, target):
    AuditLogger.log_change("student", target.id, "INSERT", new_values=target.__dict__)


@event.listens_for(Student, "after_update")
def log_student_update(mapper, connection, target):
    AuditLogger.log_change("student", target.id, "UPDATE", new_values=target.__dict__)


@event.listens_for(Grade, "after_insert")
def log_grade_insert(mapper, connection, target):
    AuditLogger.log_change("grade", target.id, "INSERT", new_values=target.__dict__)


@event.listens_for(FeePayment, "after_insert")
def log_payment_insert(mapper, connection, target):
    AuditLogger.log_change("fee_payment", target.id, "INSERT", new_values=target.__dict__)
