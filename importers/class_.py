from importers.base import BaseImporter
from models import Class
from extensions import db

class ClassImporter(BaseImporter):
    entity_type = "class"
    required_columns = ["name", "level"]
    optional_columns = ["stream", "class_teacher"]
    sample_rows = [
        {"name": "Grade 8 Blue", "level": "8", "stream": "Blue", "class_teacher": "Jane Smith"}
    ]

    def process_row(self, row_num: int, row: dict) -> None:
        name = row.get("name", "").strip()
        level = row.get("level", "").strip()
        if not name or not level:
            raise ValueError("Name and level are required")

        if Class.query.filter_by(name=name).first():
            self.warnings.append(f"Row {row_num}: Class '{name}' already exists, skipping")
            return

        cls = Class(
            name=name,
            level=level,
            stream=row.get("stream", "").strip() or None,
            class_teacher=row.get("class_teacher", "").strip() or None
        )
        db.session.add(cls)
