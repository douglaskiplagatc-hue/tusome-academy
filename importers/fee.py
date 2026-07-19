from importers.base import BaseImporter
from models import Student, FeePayment
from extensions import db
from datetime import datetime, timezone

class FeeImporter(BaseImporter):
    entity_type = "fee"
    required_columns = ["admission_number", "amount", "payment_date"]
    optional_columns = ["payment_method", "reference", "notes", "term", "year"]
    sample_rows = [
        {"admission_number": "S001", "amount": "5000.00", "payment_date": "2025-01-15",
         "payment_method": "M-Pesa", "reference": "ABC123", "notes": "Term 1 fees",
         "term": "Term 1", "year": "2025"}
    ]

    def process_row(self, row_num: int, row: dict) -> None:
        admission = row.get("admission_number", "").strip()
        amount_str = row.get("amount", "").strip()
        payment_date_str = row.get("payment_date", "").strip()
        if not admission or not amount_str or not payment_date_str:
            raise ValueError("admission_number, amount, and payment_date are required")

        student = Student.query.filter_by(admission_number=admission).first()
        if not student:
            raise ValueError(f"Student '{admission}' not found")

        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            raise ValueError(f"Invalid amount: {amount_str}")

        payment_date = self.parse_date(payment_date_str)
        if not payment_date:
            raise ValueError(f"Invalid payment date: {payment_date_str}")

        # Optional fields
        term = row.get("term", "").strip() or "Term 1"
        year = int(row.get("year", datetime.now(timezone.utc).year))

        fee = FeePayment(
            student_id=student.id,
            amount=amount,
            payment_date=payment_date,
            payment_method=row.get("payment_method", "").strip(),
            reference=row.get("reference", "").strip(),
            notes=row.get("notes", "").strip(),
            term=term,
            year=year
        )
        db.session.add(fee)
