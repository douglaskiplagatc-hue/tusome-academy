# bulk/importers/base.py
import csv, json, re, uuid, logging,threading
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple, Callable
import pandas as pd
from flask import current_app,Blueprint,flash,jsonify,redirect,render_template,request,url_for,Response
from extensions import db
from models import BulkImportResult

from forms import BulkUploadForm
from flask_login import current_user
from flask import current_app
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)
bulk_bp = Blueprint("bulk_bp", __name__, url_prefix="/bulk")
class BaseImporter:
    """Base class for all bulk importers."""
    # Override in child classes
    entity_type: str = "base"
    required_columns: List[str] = []
    optional_columns: List[str] = []
    sample_rows: List[Dict[str, Any]] = []

    def __init__(self):
        self.import_id = str(uuid.uuid4())
        self.status = "pending"
        self.total_records = 0
        self.processed = 0
        self.success = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.details: List[Dict[str, Any]] = []
        self.progress = 0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def validate_file(self, file, allowed_extensions=None) -> str:
        if not file or file.filename == "":
            raise ValueError("No file selected")
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        allowed = allowed_extensions or {"csv", "xlsx", "xls", "json", "xml"}
        if ext not in allowed:
            raise ValueError(f"File type '{ext}' not allowed. Allowed: {', '.join(allowed)}")
        return ext

    def parse_file(self, file, file_ext: str) -> Dict[str, Any]:
        """Parse file into headers, rows, total_rows."""
        parser_map = {
            "csv": self._parse_csv,
            "xlsx": self._parse_excel, "xls": self._parse_excel,
            "json": self._parse_json, "xml": self._parse_xml,
        }
        parser = parser_map.get(file_ext)
        if not parser:
            raise ValueError(f"Unsupported file format: {file_ext}")
        return parser(file)

    def process(self,parsed: Dict[str, Any], progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Main entry point: validate headers, process rows, commit."""
        self.start_time = datetime.now(timezone.utc)
        self.total_records = parsed.get("total_rows", 0)
        self.status = "processing"
        import_id = self.import_id
        record = None
        progress= 0
        total = parsed["total_rows"]
        record = BulkImportResult.query.get(import_id)
        if record is None:
            raise RuntimeError(f"Import record {import_id} not found!")
        record.status = "processing"
        db.session.commit()
        try:
            self._validate_headers(parsed["headers"])
        except ValueError as e:
            self.status = "failed"
            self.errors.append(str(e))
            self._add_detail(1, "error", str(e), {})
            return self.get_results()

        headers = parsed["headers"]

        for idx, row in enumerate(parsed["rows"], start=2):
            self.processed = idx - 1
            self.progress = int((self.processed / max(self.total_records, 1)) * 100)
            if progress_callback:
                progress_callback(self.progress, self.processed, self.total_records)
            if idx % 10 == 0:   # update every 10 rows
                progress = int((idx + 1) / total * 100)
                record = BulkImportResult.query.get(self.import_id)
            if record:
                record.progress = progress
                db.session.commit()
            row_dict = dict(zip(headers, row))
            row_dict = {k: (v.strip() if isinstance(v, str) else v) for k, v in row_dict.items()}

            try:
                # Use savepoint to rollback individual row if needed
                savepoint = db.session.begin_nested()
                self.process_row(idx, row_dict)
                savepoint.commit()
                self.success += 1
                self._add_detail(idx, "success", "Processed successfully", row_dict)
            except Exception as exc:
                savepoint.rollback()
                full_msg = f"Row {idx}: {str(exc)}"
                self.errors.append(full_msg)
                self._add_detail(idx, "error", full_msg, row_dict)

        # Final commit
        try:
            db.session.commit()
            self.status = "completed" if not self.errors else "completed_with_errors"
        except Exception as exc:
            db.session.rollback()
            self.errors.append(f"Final commit error: {str(exc)}")
            self.status = "failed"

        self.end_time = datetime.now(timezone.utc)
        return self.get_results()

    def _validate_headers(self, headers: List[str]) -> None:
        missing = [col for col in self.required_columns if col not in headers]
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

    def _add_detail(self, row_num: int, status: str, message: str, row_data: Dict) -> None:
        preview = ", ".join(str(v)[:50] for v in list(row_data.values())[:3] if v is not None)
        self.details.append({
            "row_number": row_num,
            "status": status,
            "message": message,
            "record_id": row_data.get("admission_number") or row_data.get("username") or row_data.get("email") or "N/A",
            "name": row_data.get("full_name") or row_data.get("username") or "",
            "email": row_data.get("email", ""),
            "raw_data_preview": preview,
        })

    def get_results(self) -> Dict[str, Any]:
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        return {
            "import_id": self.import_id,
            "status": self.status,
            "total_records": self.total_records,
            "processed": self.processed,
            "success": self.success,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details,
            "progress": self.progress,
            "duration": duration,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

    # ---------- Row processing (must be overridden) ----------
    def process_row(self, row_num: int, row: Dict[str, Any]) -> None:
        raise NotImplementedError("Subclasses must implement process_row")

    # ---------- File parsers (shared) ----------
    def _parse_csv(self, file) -> Dict[str, Any]:
        content = file.read()
        for enc in ("utf-8", "utf-8-sig", "latin-1", "iso-8859-1"):
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not decode file")
        reader = csv.reader(StringIO(text))
        rows = [r for r in reader if any(cell.strip() for cell in r)]
        if not rows:
            raise ValueError("CSV file is empty")
        headers = [h.strip().lower().replace(" ", "_") for h in rows[0]]
        return {"headers": headers, "rows": rows[1:], "total_rows": len(rows) - 1}

    def _parse_excel(self, file) -> Dict[str, Any]:
        df = pd.read_excel(file, engine="openpyxl")
        if df.empty:
            raise ValueError("Excel file is empty")
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        df = df.dropna(how="all")
        rows = df.values.tolist()
        return {"headers": list(df.columns), "rows": rows, "total_rows": len(rows)}

    def _parse_json(self, file) -> Dict[str, Any]:
        text = file.read().decode("utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("data") or data.get("records") or [data]
        if not isinstance(data, list) or not data:
            raise ValueError("Invalid JSON format")
        headers = list(data[0].keys())
        rows = [[item.get(h, "") for h in headers] for item in data]
        return {"headers": headers, "rows": rows, "total_rows": len(rows)}

    def _parse_xml(self, file) -> Dict[str, Any]:
        import xml.etree.ElementTree as ET
        content = file.read().decode("utf-8")
        root = ET.fromstring(content)
        records = [{sub.tag: sub.text for sub in child} for child in root]
        if not records:
            raise ValueError("No records in XML")
        headers = list(records[0].keys())
        rows = [[rec.get(h, "") for h in headers] for rec in records]
        return {"headers": headers, "rows": rows, "total_rows": len(rows)}

    # ---------- Helper methods for child classes ----------
    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime.date]:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def derive_cbc_level(marks: float) -> str:
        CBC_LEVELS = {
            "Exceeding Expectations": (80, 100),
            "Meeting Expectations": (60, 79),
            "Approaching Expectations": (40, 59),
            "Below Expectations": (0, 39),
        }
        for level, (low, high) in CBC_LEVELS.items():
            if low <= marks <= high:
                return level
        return "Below Expectations"
def run_import():
    from app import app  # your Flask app instance
    with app.app_context():
        from bulk.routes import _save_results
        # now db.session is bound to this thread
        results = importer.process(parsed)
        _save_results(results)
