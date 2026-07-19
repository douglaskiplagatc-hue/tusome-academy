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
# utils/subject_filters.py
from config import Config

def get_available_grades():
    """Get grades available based on school type"""
    from flask import current_app
    school_type = current_app.config.get('SCHOOL_TYPE', 'full')
    return Config.SCHOOL_LEVELS.get(school_type, [1, 2, 3, 4, 5, 6, 7, 8, 9])

def filter_subjects_by_grade(subjects, grade):
    """Filter subjects by grade level"""
    return [s for s in subjects if s.level and str(grade) in s.level]
# utils/init_settings.py

from extensions import db
from models import SchoolProfile, SystemSetting
from datetime import datetime

def initialize_system_settings():
    """Initialize system settings if they don't exist"""

    # Create default school profile if not exists
    profile = SchoolProfile.query.first()
    if not profile:
        profile = SchoolProfile()
        profile.school_name = "Your School Name"
        profile.school_code = "SCH001"
        profile.motto = "Excellence in Education"
        profile.school_vision = "To be a center of academic excellence nurturing holistic development."
        profile.school_mission = "To provide quality education that empowers learners to reach their full potential."
        profile.address = "Your School Address"
        profile.phone = "0712345678"
        profile.email = "info@yourschool.ac.ke"
        profile.website = "www.yourschool.ac.ke"
        profile.school_level = "junior_secondary"
        profile.established_year = 2024
        profile.principal_name = "School Principal"
        profile.primary_color = "#006B3F"
        profile.secondary_color = "#0047AB"

        # Social Media (empty by default)
        profile.social_facebook = ""
        profile.social_twitter = ""
        profile.social_instagram = ""
        profile.social_linkedin = ""
        profile.social_youtube = ""

        db.session.add(profile)
        db.session.commit()
        print("✓ School profile initialized")

    # Initialize system settings
    default_settings = {
        'current_academic_year': str(datetime.now().year),
        'current_term': '1',
        'term_start_date': '',
        'term_end_date': '',
        'assessment_weight_exam': '60',
        'assessment_weight_cat': '30',
        'assessment_weight_assignment': '10',
        'enable_email_notifications': 'true',
        'enable_sms_notifications': 'false',
        'enable_parent_portal': 'true',
        'enable_student_portal': 'true',
        'session_timeout': '30',
        'max_login_attempts': '5',
        'password_expiry_days': '90',
        'enable_2fa': 'false',
        'backup_frequency': 'weekly',
        'log_retention_days': '30'
    }

    for key, default_value in default_settings.items():
        setting = SystemSetting.query.filter_by(key=key).first()
        if not setting:
            # Determine value type
            value_type = 'string'
            if default_value in ['true', 'false']:
                value_type = 'bool'
            elif default_value.isdigit():
                value_type = 'int'

            setting = SystemSetting(
                key=key,
                value=default_value,
                value_type=value_type,
                description=f"System setting for {key.replace('_', ' ').title()}"
            )
            db.session.add(setting)

    db.session.commit()
    print("✓ System settings initialized")

import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

sheets_service = None
if SERVICE_ACCOUNT_FILE:
    try:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        sheets_service = build('sheets', 'v4', credentials=credentials)
    except Exception as e:
        logging.error(f"Failed to initialize Google Sheets service: {e}")
else:
    logging.warning("GOOGLE_SHEETS_CREDENTIALS environment variable not set. Google Sheets integration disabled.")


def get_grades_sheet(sheet_name='Grades', range='A:Z'):
    """Fetch all data from a sheet."""
    sheet = sheets_service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f'{sheet_name}!{range}'
    ).execute()
    return result.get('values', [])

def update_grades_sheet(data, sheet_name='Grades', range='A:Z'):
    """Write data to sheet, overwriting existing."""
    body = {'values': data}
    result = sheets_service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f'{sheet_name}!{range}',
        valueInputOption='RAW',
        body=body
    ).execute()
    return result
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])

def verify_reset_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
    except:
        return None
    return email
