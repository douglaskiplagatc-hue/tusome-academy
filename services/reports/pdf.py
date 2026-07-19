"""PDF generation for reports (ReportLab)."""

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models import Grade
from services.reports.ncbe import marks_to_ncbe


def generate_student_report_card_pdf(student, term, year, assessment, school_name="TUSOME SCHOOL"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=20,
        alignment=1,
    )
    story = [
        Paragraph(f"{school_name}<br/>STUDENT REPORT CARD", title_style),
        Spacer(1, 12),
    ]

    class_name = student.current_class.name if student.current_class else "N/A"
    info = [
        ["Student Name:", student.full_name],
        ["Admission Number:", student.admission_number],
        ["Class:", class_name],
        ["Term:", f"{term} {year} | {assessment}"],
        ["Date:", datetime.now().strftime("%Y-%m-%d")],
    ]
    story.append(_info_table(info))
    story.append(Spacer(1, 16))

    grades = (
        Grade.query.filter_by(
            student_id=student.id,
            term=term,
            year=year,
            assessment_type=assessment,
        )
        .all()
    )
    if grades:
        data = [["Subject", "Marks", "NCBE Level"]]
        total = 0
        count = 0
        for g in grades:
            marks = g.marks
            data.append(
                [
                    g.subject.name,
                    f"{marks:.0f}" if marks is not None else "—",
                    marks_to_ncbe(marks),
                ]
            )
            if marks is not None:
                total += marks
                count += 1
        if count:
            data.append(["Average", f"{total / count:.1f}", ""])
        story.append(Paragraph("ACADEMIC PERFORMANCE", styles["Heading2"]))
        story.append(Spacer(1, 8))
        story.append(_grades_table(data))

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_fee_statement_pdf(fee_statements, school_name, totals):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FeeTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=20,
        alignment=1,
    )
    story = [
        Paragraph(f"{school_name}<br/>FEE SUMMARY", title_style),
        Spacer(1, 12),
    ]

    if not fee_statements:
        story.append(Paragraph("No fee records found.", styles["Normal"]))
    else:
        data = [["Student", "Term", "Year", "Due", "Paid", "Balance"]]
        for fs in fee_statements:
            data.append(
                [
                    fs.student.full_name,
                    fs.term,
                    str(fs.year),
                    f"{fs.amount_due:,.2f}",
                    f"{fs.amount_paid:,.2f}",
                    f"{fs.balance:,.2f}",
                ]
            )
        data.append(
            [
                "TOTAL",
                "",
                "",
                f"{totals['due']:,.2f}",
                f"{totals['paid']:,.2f}",
                f"{totals['balance']:,.2f}",
            ]
        )
        story.append(_grades_table(data))

    doc.build(story)
    buffer.seek(0)
    return buffer


def _info_table(rows):
    t = Table(rows, colWidths=[2 * inch, 4 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return t


def _grades_table(data):
    t = Table(data, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return t
