# utils.py
# Utility functions for grades, CBC rubrics, and styling
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime


def numeric_to_cbc(mark: float) -> str:
    """
    Converts a numeric mark (0-100) to a CBC rubric.
    """
    mark = float(mark)
    if mark >= 90:
        return "EE1"
    elif mark >= 80:
        return "EE2"
    elif mark >= 70:
        return "EE3"
    elif mark >= 60:
        return "ME1"
    elif mark >= 50:
        return "ME2"
    elif mark >= 40:
        return "ME3"
    elif mark >= 30:
        return "BE1"
    elif mark >= 20:
        return "BE2"
    else:
        return "BE3"


def rubric_color(rubric: str) -> str:
    """
    Returns a color associated with the CBC rubric for styling.
    """
    colors = {
        "EE1": "green",
        "EE2": "limegreen",
        "EE3": "yellowgreen",
        "ME1": "yellow",
        "ME2": "orange",
        "ME3": "darkorange",
        "BE1": "red",
        "BE2": "darkred",
        "BE3": "maroon",
    }
    return colors.get(rubric, "black")


def generate_receipt_pdf(payment):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    doc.build([])
    buffer.seek(0)
    return buffer


# utils.py


class SchoolPDF:
    def __init__(self, title="Document"):
        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30,
        )
        self.styles = getSampleStyleSheet()
        self.story = []
        self.title = title

    def header(self, school_name):
        self.story.append(Paragraph(school_name, self.styles["Title"]))
        self.story.append(Spacer(1, 12))
        self.story.append(Paragraph(self.title, self.styles["Heading2"]))
        self.story.append(Spacer(1, 20))

    def paragraph(self, text):
        self.story.append(Paragraph(text, self.styles["Normal"]))

    def table(self, data):
        table = Table(data, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ]
            )
        )
        self.story.append(table)
        self.story.append(Spacer(1, 12))

    def build(self):
        self.doc.build(self.story)
        self.buffer.seek(0)
        return self.buffer
