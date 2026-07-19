"""CSV and PDF HTTP responses for reports."""

import csv
import io

from flask import send_file

from services.reports.pdf import generate_fee_statement_pdf, generate_student_report_card_pdf


def csv_response(filename, headers, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    if headers:
        writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    output = io.BytesIO()
    output.write(buf.getvalue().encode("utf-8"))
    output.seek(0)
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


def pdf_student_report_card(student, term, year, assessment, school_name):
    buffer = generate_student_report_card_pdf(
        student, term, year, assessment, school_name=school_name
    )
    name = f"report_card_{student.admission_number}_{term}_{year}.pdf".replace(" ", "_")
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=name,
    )


def pdf_fee_summary(fee_statements, school_name, totals):
    buffer = generate_fee_statement_pdf(fee_statements, school_name, totals)
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="fee_summary.pdf",
    )
