from importers.base import BaseImporter
from models import Student, User, Class
from extensions import db
from datetime import datetime, timezone

class StudentImporter(BaseImporter):
    entity_type = "student"
    required_columns = ["admission_number", "full_name"]
    optional_columns = ["class_name", "parent_username", "parent_email", "date_of_birth"]
    sample_rows = [
        {"admission_number": "S001", "full_name": "Alice Mwikali",
         "class_name": "Grade 8 Blue", "parent_username": "parent1",
         "parent_email": "parent1@example.com", "date_of_birth": "2010-05-15"}
    ]

    def process_row(self, row_num: int, row: dict) -> None:
        admission = row.get("admission_number", "").strip()
        full_name = row.get("full_name", "").strip()
        if not admission or not full_name:
            raise ValueError("Admission number and full name are required")

        # Find parent
        parent = None
        parent_username = row.get("parent_username", "").strip()
        parent_email = row.get("parent_email", "").strip()
        if parent_username:
            parent = User.query.filter_by(username=parent_username, role="parent").first()
            if not parent:
                self.warnings.append(f"Row {row_num}: Parent username '{parent_username}' not found")
        if not parent and parent_email:
            parent = User.query.filter_by(email=parent_email, role="parent").first()
            if not parent:
                self.warnings.append(f"Row {row_num}: Parent email '{parent_email}' not found")

        # Find or create class
        class_name = row.get("class_name", "").strip()
        class_obj = None
        if class_name:
            class_obj = self._get_or_create_class(class_name)
            if not class_obj:
                self.warnings.append(f"Row {row_num}: Could not find/create class '{class_name}'")

        # Date of birth
        dob = None
        dob_str = row.get("date_of_birth", "").strip()
        if dob_str:
            dob = self.parse_date(dob_str)
            if not dob:
                raise ValueError(f"Invalid date format: {dob_str}")

        # Update or create
        student = Student.query.filter_by(admission_number=admission).first()
        if student:
            student.full_name = full_name
            if parent: student.parent_id = parent.id
            if class_obj: student.current_class_id = class_obj.id
            if dob: student.date_of_birth = dob
            self.warnings.append(f"Row {row_num}: Updated existing student {admission}")
        else:
            student = Student(
                admission_number=admission,
                full_name=full_name,
                parent_id=parent.id if parent else None,
                current_class_id=class_obj.id if class_obj else None,
                date_of_birth=dob or datetime.now(timezone.utc).date(),
                status="active"
            )
            db.session.add(student)

    def _get_or_create_class(self, class_name: str):
        # Try exact match first
        cls = Class.query.filter_by(name=class_name).first()
        if cls:
            return cls
        # Parse grade and stream
        parts = class_name.split()
        grade = None
        stream = None
        for part in parts:
            if part.isdigit():
                grade = int(part)
            elif part.upper() in {"GREEN", "YELLOW", "RED", "BLUE", "WHITE", "EAST", "WEST"}:
                stream = part.upper()
        if grade is None:
            return None
        # Try by level/stream
        if stream:
            cls = Class.query.filter_by(level=str(grade), stream=stream).first()
        else:
            cls = Class.query.filter_by(level=str(grade), stream=None).first()
        if not cls:
            cls = Class(name=class_name, level=str(grade), stream=stream)
            db.session.add(cls)
            db.session.flush()
            self.warnings.append(f"Row: Auto-created class '{class_name}'")
        return cls
