from importers.base import BaseImporter
from models import User,Teacher
from werkzeug.security import generate_password_hash
from extensions import db
from datetime import datetime, timezone
import re
from flask_login import current_user
class TeacherImporter(BaseImporter):
    entity_type = "teacher"
    required_columns = ["username", "email", "full_name"]
    optional_columns = ["password"]
    sample_rows = [
        {"username": "teacher1", "email": "teacher1@example.com",
         "full_name": "Jane Smith", "password": "password123"}
    ]

    def process_row(self, row_num: int, row: dict) -> None:
        username = row.get("username", "").strip()
        email = row.get("email", "").strip()
        full_name = row.get("full_name", "").strip()

        if not username or not email or not full_name:
            raise ValueError("Username, email, and full_name are required")

    # Check if teacher already exists (by username or user)
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
        # But also check if a Teacher record exists for this user
            existing_teacher = Teacher.query.filter_by(user_id=existing_user.id).first()
            if existing_teacher:
                self.warnings.append(f"Row {row_num}: Teacher '{username}' already exists, skipping")
                return
        # If user exists but no Teacher record, we can still create the Teacher link
        # (so don't return yet – fall through to create Teacher only)
            user = existing_user
        else:
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                raise ValueError(f"Invalid email format: {email}")

            user = User(
                username=username,
                email=email,
                full_name=full_name,
                role="teacher",
                is_active=True,
                password_hash=generate_password_hash(row.get("password", "password123")),
                created_at=datetime.now(timezone.utc)
        )
            db.session.add(user)
            db.session.flush()  # get user.id before creating Teacher

    # Create Teacher record if not already present
        if not Teacher.query.filter_by(user_id=user.id).first():
            teacher = Teacher(
                user_id=user.id,
            # If you have a school_id field and need to set it, get it from current_user or the route’s school_id.
            # For now, we’ll leave it None; you can later pass school_id to the importer.
                school_id=getattr(current_user, 'school_id', None)
        )
            db.session.add(teacher)
            db.session.flush()
