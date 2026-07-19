from importers.base import BaseImporter
from models import Student, Subject, Grade
from extensions import db
from datetime import datetime, timezone

class GradeImporter(BaseImporter):
    entity_type = "grade"
    required_columns = ["admission_number", "subject", "marks"]
    optional_columns = ["exam_type", "term", "year"]
    sample_rows = [
        {"admission_number": "S001", "subject": "math",
         "marks": "78.5", "exam_type": "Exam 1", "term": "Term 1", "year": "2025"}
    ]

    def process_row(self, row_num: int, row: dict) -> None:
        admission = row.get("admission_number", "").strip()
        subject_code = row.get("subject", "").strip().lower()   # accept codes like 'math', 'eng'
        marks_str = row.get("marks", "").strip()

        if not admission or not subject_code or not marks_str:
            raise ValueError("Missing admission_number, subject, or marks")

        # Validate marks
        try:
            marks = float(marks_str)
            if not (0 <= marks <= 100):
                raise ValueError("Marks must be between 0 and 100")
        except ValueError:
            raise ValueError(f"Invalid marks value: {marks_str}")

        # Find the student
        student = Student.query.filter_by(admission_number=admission).first()
        if not student:
            raise ValueError(f"Student '{admission}' not found")

        # Determine the student's school level from their class
        if not student.current_class:
            raise ValueError(f"Student '{admission}' has no class assigned")
        student_level = student.current_class.level   # e.g. "Junior Secondary"

        # Find the subject by its **code** AND the student's level
        subject = Subject.query.filter(
            Subject.code.ilike(subject_code),
            Subject.level == student_level
        ).first()
        if not subject:
            raise ValueError(
                f"Subject '{subject_code}' not found for level '{student_level}'"
            )

        exam_type = row.get("exam_type", "Exam 1").strip()
        term = row.get("term", "Term 1").strip()
        year = int(row.get("year", datetime.now(timezone.utc).year))

        cbc_level = self.derive_cbc_level(marks)

        # Upsert: avoid duplicate grade for same student/subject/assessment/term/year
        grade = Grade.query.filter_by(
            student_id=student.id,
            subject_id=subject.id,
            assessment_type=exam_type,
            term=term,
            year=year
        ).first()
        if grade:
            grade.marks = marks
            grade.percentage = marks
            grade.cbc_level = cbc_level
            self.warnings.append(f"Row {row_num}: Updated existing grade")
        else:
            grade = Grade(
                student_id=student.id,
                subject_id=subject.id,
                assessment_type=exam_type,
                term=term,
                year=year,
                marks=marks,
                percentage=marks,
                cbc_level=cbc_level
            )
            db.session.add(grade)
