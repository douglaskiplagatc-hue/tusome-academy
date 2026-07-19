from importers.parent import ParentImporter
from importers.student import StudentImporter
from importers.grade import GradeImporter
from importers.teacher import TeacherImporter
from importers.class_ import ClassImporter
from importers.subject import SubjectImporter
from importers.fee import FeeImporter
from importers.attendance import AttendanceImporter

# Map entity type (used in form) to importer class and metadata
IMPORTER_REGISTRY = {
    "parent_user": {
        "class": ParentImporter,
        "label": "Parent Users",
        "description": "Parent Users",
        "template_filename": "parents_template.csv",
    },
    "teacher": {
        "class": TeacherImporter,
        "label": "Teachers",
        "description": "Create teacher accounts.",
        "template_filename": "teachers_template.csv",
    },
    "student": {
        "class": StudentImporter,
        "label": "Students",
        "description": "Register or update students.",
        "template_filename": "students_template.csv",
    },
    "grade": {
        "class": GradeImporter,
        "label": "Grades",
        "description": "Import student marks.",
        "template_filename": "grades_template.csv",
    },
    "class": {
        "class": ClassImporter,
        "label": "Classes",
        "description": "Create class records.",
        "template_filename": "classes_template.csv",
    },
    "subject": {
        "class": SubjectImporter,
        "label": "Subjects",
        "description": "Create subject records.",
        "template_filename": "subjects_template.csv",
    },
    "fee": {
        "class": FeeImporter,
        "label": "Fee Payments",
        "description": "Log fee payments for students.",
        "template_filename": "fees_template.csv",
    },
    "attendance": {
        "class": AttendanceImporter,
        "label": "Attendance",
        "description": "Record daily attendance.",
        "template_filename": "attendance_template.csv",
    },
}
