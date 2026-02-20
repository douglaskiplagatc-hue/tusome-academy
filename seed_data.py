# seed_full_json.py
import os
import random
import logging
import json
from datetime import date, datetime, timedelta
from extensions import db
from app import create_app, register_cli
from extensions import db
from werkzeug.security import generate_password_hash
from app import db

from models import (
    User,
    Teacher,
    Student,
    Subject,
    Class,
    Grade,
    Attendance,
    Event,
    Notification,
    Message,
    Employee,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ---------- CONFIG ----------
NUM_TEACHERS = 10
STUDENTS_PER_CLASS = 10

CLASS_NAMES = [
    ("Grade 1", "Primary"),
    ("Grade 2", "Primary"),
    ("Grade 3", "Primary"),
    ("Grade 4", "Primary"),
    ("Grade 5", "Primary"),
    ("Grade 6", "Primary"),
    ("Grade 7", "Junior Secondary"),
    ("Grade 8", "Junior Secondary"),
    ("Grade 9", "Junior Secondary"),
    ("Grade 10", "Senior Secondary"),
]

FIRST_NAMES = [
    "John",
    "Mary",
    "Paul",
    "Grace",
    "James",
    "Anna",
    "Peter",
    "Faith",
    "David",
    "Ruth",
]
LAST_NAMES = [
    "Kamau",
    "Wanjiru",
    "Otieno",
    "Mwangi",
    "Njoroge",
    "Ouma",
    "Mutua",
    "Kimani",
    "Kiptoo",
    "Amani",
]

PATHWAYS = ["STEM", "Social Sciences", "Arts & Sports"]


def rand_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


# ---------- SEED FUNCTION ----------
def seed():
    logging.info("Starting full seed...")

    # ---------- 1) Users ----------
    logging.info("Seeding users...")
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(
            username="admin",
            full_name="Admin User",
            email="admin@tusome.com",
            role="admin",
        )
        admin.password_hash = generate_password_hash(
            os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
        )
        db.session.add(admin)

    parent = User.query.filter_by(username="parent1").first()
    if not parent:
        parent = User(
            username="parent1",
            full_name="Parent User",
            email="parent1@example.com",
            role="parent",
        )
        parent.password_hash = generate_password_hash(
            os.getenv("PARENT_PASSWORD", "Parent123!")
        )
        db.session.add(parent)

    teacher_users = []
    for i in range(1, NUM_TEACHERS + 1):
        uname = f"teacher{i}"
        user = User.query.filter_by(username=uname).first()
        if not user:
            user = User(
                username=uname,
                full_name=rand_name(),
                email=f"{uname}@tusome.com",
                role="teacher",
            )
            user.password_hash = generate_password_hash(
                os.getenv("TEACHER_PASSWORD", "Teacher123!")
            )
            db.session.add(user)
        teacher_users.append(user)
    db.session.commit()

    # ---------- 2) Classes ----------
    logging.info("Seeding classes...")
    classes = []
    for cname, level in CLASS_NAMES:
        cls = Class.query.filter_by(name=cname).first()
        if not cls:
            cls = Class(name=cname, level=level)
            db.session.add(cls)
        classes.append(cls)
    db.session.commit()

    # ---------- 3) Subjects ----------
    logging.info("Seeding subjects from JSON...")
    created_subjects = []

    with open("subjects_cbc.json") as f:
        subjects_data = json.load(f)

    def add_subject(subj_data, level, pathway=None, class_id=None):
        s = Subject.query.filter_by(code=subj_data["code"]).first()
        if not s:
            s = Subject(
                name=subj_data["name"],
                code=subj_data["code"],
                level=level,
                compulsory=subj_data.get("compulsory", False),
                pathway=pathway,
                class_id=class_id,  # Only assign class for Primary/Junior
            )
            db.session.add(s)
        else:
            s.name = subj_data["name"]
            s.level = level
            s.compulsory = subj_data.get("compulsory", False)
            s.pathway = pathway
            s.class_id = class_id
        created_subjects.append(s)

    # Primary subjects (assign to all primary classes)
    primary_classes = [cls for cls in classes if cls.level == "Primary"]
    for cls in primary_classes:
        for subj in subjects_data["Primary"]:
            add_subject(subj, "Primary", class_id=cls.id)

    # Junior Secondary subjects
    junior_classes = [cls for cls in classes if cls.level == "Junior Secondary"]
    for cls in junior_classes:
        for subj in subjects_data["Junior Secondary"]:
            add_subject(subj, "Junior Secondary", class_id=cls.id)

    # Senior Secondary Core subjects (no class_id)
    for subj in subjects_data["Senior Secondary"]["core"]:
        add_subject(subj, "Senior Secondary", pathway="Core", class_id=None)

    # Senior Secondary Pathways (no class_id)
    for pathway_name, subs in subjects_data["Senior Secondary"]["pathways"].items():
        for subj in subs:
            add_subject(subj, "Senior Secondary", pathway=pathway_name, class_id=None)

    db.session.commit()
    logging.info(f"✅ Seeded {len(created_subjects)} subjects successfully.")

    # ---------- 4) Teacher profiles ----------
    logging.info("Seeding teacher profiles...")
    teacher_profiles = []
    for idx, cls in enumerate(classes):
        if idx >= len(teacher_users):
            break
        user = teacher_users[idx]
        tp = Teacher.query.filter_by(user_id=user.id).first()
        if not tp:
            tp = Teacher(user_id=user.id)
            db.session.add(tp)
        else:
            tp.class_id = cls.id
        cls.class_teacher_id = user.id
        teacher_profiles.append(tp)
    db.session.commit()

    for user in teacher_users[len(classes) :]:
        tp = Teacher.query.filter_by(user_id=user.id).first()
        if not tp:
            tp = Teacher(user_id=user.id)
            db.session.add(tp)
            teacher_profiles.append(tp)
    db.session.commit()

    # Assign subjects to teachers
    logging.info("Assigning subjects to teachers...")
    teacher_for_subjects = teacher_profiles[: max(7, len(teacher_profiles))]
    for i, subj in enumerate(created_subjects):
        assigned_teacher = teacher_for_subjects[i % len(teacher_for_subjects)]
        subj.teacher_id = assigned_teacher.user_id
        # Employees
    logging.info("Seeding employees...")
    db.session.commit()

    e = Employee(
        first_name="John",
        last_name="Doe",
        role="Support Staff",
        national_id="34567890",
        staff_number="0712345678",
    )

    db.session.add(e)
    db.session.commit()
    logging.info("✅ Employees seeded successfully.")

    # ---------- 5) Students ----------
    logging.info("Seeding students...")
    all_students = []
    for cls in classes:
        for n in range(STUDENTS_PER_CLASS):
            adm_no = f"{cls.name.replace(' ', '')[:4].upper()}{n + 1:03d}"
            student = Student.query.filter_by(admission_number=adm_no).first()
            if not student:
                pathway = None
                if cls.level == "Senior Secondary":
                    pathway = random.choice(PATHWAYS)
                student = Student(
                    full_name=rand_name(),
                    admission_number=adm_no,
                    date_of_birth=date(2015, 5, 10)
                    if cls.level != "Senior Secondary"
                    else date(2008, 1, 1),
                    parent_id=parent.id,
                    current_class_id=cls.id,
                    pathway=pathway,
                )
                db.session.add(student)
            all_students.append(student)
    db.session.commit()

    logging.info("✅ Students seeded successfully.")


# ---------- MAIN ----------
if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        register_cli(app)
        seed()
