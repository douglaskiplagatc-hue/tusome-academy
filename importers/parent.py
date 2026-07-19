from importers.base import BaseImporter
from models import User
from werkzeug.security import generate_password_hash
from extensions import db
import re
from datetime import datetime,time,timezone
class ParentImporter(BaseImporter):
    entity_type = "parent_user"
    required_columns = ["username", "email"]
    optional_columns = ["password", "full_name", "phone", "address"]
    sample_rows = [
        {"username": "parent1", "email": "parent1@example.com", "password": "password123",
         "full_name": "John Doe", "phone": "0712345678", "address": "Nairobi"}
    ]

    def process_row(self, row_num: int, row: dict) -> None:
        username = row.get("username")
        email = row.get("email")
        if not username or not email:
            raise ValueError("Username and email are required")

        # Check uniqueness
        if User.query.filter_by(username=username).first():
            self.warnings.append(f"Row {row_num}: User '{username}' already exists, skipping")
            return

        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            raise ValueError(f"Invalid email format: {email}")

        user = User(
            username=username,
            email=email,
            full_name=row.get("full_name", username),
            phone=row.get("phone", ""),
            
            role="parent",
            is_active=True,
            password_hash=generate_password_hash(row.get("password", "password123")),
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(user)
