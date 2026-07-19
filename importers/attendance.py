from importers.base import BaseImporter
from models import Student, Attendance
from extensions import db
from datetime import datetime, timezone

class AttendanceImporter(BaseImporter):
    entity_type = "attendance"
    required_columns = ["admission_number", "date", "status"]
    optional_columns = ["check_in_time", "check_out_time", "remarks"]
    sample_rows = [
        {"admission_number": "S001", "date": "2025-01-15", "status": "Present",
         "check_in_time": "08:00", "check_out_time": "15:30", "remarks": "On time"}
    ]

    def process_row(self, row_num: int, row: dict) -> None:
        admission = row.get("admission_number", "").strip()
        date_str = row.get("date", "").strip()
        status = row.get("status", "").strip()
        if not admission or not date_str or not status:
            raise ValueError("admission_number, date, and status are required")

        student = Student.query.filter_by(admission_number=admission).first()
        if not student:
            raise ValueError(f"Student '{admission}' not found")

        att_date = self.parse_date(date_str)
        if not att_date:
            raise ValueError(f"Invalid date: {date_str}")

        # Check for duplicate
        existing = Attendance.query.filter_by(
            student_id=student.id,
            date=att_date
        ).first()
        if existing:
            existing.status = status
            existing.check_in_time = row.get("check_in_time", "").strip() or None
            existing.check_out_time = row.get("check_out_time", "").strip() or None
            existing.remarks = row.get("remarks", "").strip() or None
            self.warnings.append(f"Row {row_num}: Updated attendance for {admission} on {date_str}")
        else:
            att = Attendance(
                student_id=student.id,
                date=att_date,
                status=status,
                check_in_time=row.get("check_in_time", "").strip() or None,
                check_out_time=row.get("check_out_time", "").strip() or None,
                remarks=row.get("remarks", "").strip() or None
            )
            db.session.add(att)
