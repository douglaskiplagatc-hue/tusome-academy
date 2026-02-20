# scripts/update_payroll_columns.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app
from extensions import db
from sqlalchemy import text

# Run inside app context
with app.app_context():
    # List of new columns to add (SQLite ignores if column exists in raw SQL)
    new_columns = [
        "salary_source TEXT DEFAULT 'TSC'",
        "extra_lessons FLOAT DEFAULT 0",
    ]

    for col_def in new_columns:
        sql = f"ALTER TABLE staff_salaries ADD COLUMN {col_def}"
        try:
            db.session.execute(text(sql))
            print(f"Added column: {col_def.split()[0]}")
        except Exception as e:
            # In SQLite, this will fail if the column already exists
            print(f"Could not add column '{col_def.split()[0]}': {e}")

    db.session.commit()
    print("Database update complete.")
