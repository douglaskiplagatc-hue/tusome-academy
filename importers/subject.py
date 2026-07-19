from importers.base import BaseImporter
from models import Subject
from extensions import db

class SubjectImporter(BaseImporter):
    entity_type = "subject"
    required_columns = ["name", "code"]
    optional_columns = ["description", "department"]
    sample_rows = [
        {"name": "Mathematics", "code": "MAT", "description": "Algebra, Geometry", "department": "Science"}
    ]

    def process_row(self, row_num: int, row: dict) -> None:
        name = row.get("name", "").strip()
        code = row.get("code", "").strip()
        if not name or not code:
            raise ValueError("Name and code are required")

        if Subject.query.filter_by(code=code).first():
            self.warnings.append(f"Row {row_num}: Subject code '{code}' already exists, skipping")
            return

        subject = Subject(
            name=name,
            code=code,
            description=row.get("description", "").strip(),
            department=row.get("department", "").strip()
        )
        db.session.add(subject)
