# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from sqlalchemy import func
from extensions import db


# -------------------- User --------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(20), nullable=False, default="parent")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    sent_messages = db.relationship(
        "Message", foreign_keys="Message.sender_id", backref="sender", lazy=True
    )
    received_messages = db.relationship(
        "Message", foreign_keys="Message.receiver_id", backref="receiver", lazy=True
    )
    # children of this user (when role == "parent")
    students_as_parent = db.relationship(
        "Student",
        back_populates="parent",
        foreign_keys="Student.parent_id",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # If a user account is also a student profile
    student_profile = db.relationship(
        "Student",
        back_populates="student_user_profile",
        foreign_keys="Student.user_id",
        uselist=False,
    )

    # If a user account is also a teacher profile (one-to-one)
    teacher_profile = db.relationship("Teacher", back_populates="user", uselist=False)

    notifications = db.relationship(
        "Notification", back_populates="user", lazy="select"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Role helpers (safe lowercase checks)
    def is_admin(self):
        return bool(self.role and self.role.lower() == "admin")

    def is_teacher(self):
        return bool(self.role and self.role.lower() == "teacher")

    def is_parent(self):
        return bool(self.role and self.role.lower() == "parent")

    def is_student(self):
        return bool(self.role and self.role.lower() == "student")

    def is_finance(self):
        return bool(self.role and self.role.lower() == "finance")

    @property
    def children(self):
        """Convenience alias used elsewhere in templates / routes."""
        return self.students_as_parent

    @property
    def primary_student_id(self):
        if self.is_student() and self.student_profile:
            return self.student_profile.id
        if self.is_parent() and self.students_as_parent:
            return self.students_as_parent[0].id
        return None

    def __repr__(self):
        return f"<User {self.username}>"


class_subject_teacher = db.Table(
    "class_subject_teacher",
    db.Column("class_id", db.Integer, db.ForeignKey("classes.id"), primary_key=True),
    db.Column("teacher_id", db.Integer, db.ForeignKey("teachers.id"), primary_key=True),
)


# -------------------- Class --------------------
class Class(db.Model):
    __tablename__ = "classes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    level = db.Column(db.String(50), nullable=False)

    # One class teacher (mini admin)
    class_teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("teachers.id"),
        nullable=True,
    )
    class_teacher = db.relationship(
        "Teacher",
        foreign_keys=[class_teacher_id],
        back_populates="classes_as_teacher",
        lazy="joined",
    )

    # Many-to-many: subject teachers

    subject_teachers = db.relationship(
        "Teacher",
        secondary=class_subject_teacher,
        backref="teaching_classes",
        lazy="select",
    )

    # Students in this class
    students = db.relationship(
        "Student",
        back_populates="current_class",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Subjects assigned to this class
    subjects = db.relationship("Subject", back_populates="class_", lazy="select")

    # Attendance records
    attendances = db.relationship(
        "Attendance",
        back_populates="class_obj",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self):
        return f"<Class {self.name}>"


# -------------------- Student --------------------
class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=True
    )
    admission_number = db.Column(db.String(50), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    current_class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=True)
    status = db.Column(db.String(20), default="active")
    pathway = db.Column(
        db.String(50), nullable=True
    )  # STEM / Social Sciences / Arts & Sports
    # backrefs / relationships
    student_user_profile = db.relationship(
        "User", back_populates="student_profile", foreign_keys=[user_id], uselist=False
    )

    parent = db.relationship(
        "User",
        back_populates="students_as_parent",
        foreign_keys=[parent_id],
        uselist=False,
    )

    current_class = db.relationship(
        "Class",
        back_populates="students",
        foreign_keys=[current_class_id],
        uselist=False,
    )

    attendances = db.relationship(
        "Attendance",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="select",
    )

    grades = db.relationship(
        "Grade", back_populates="student", cascade="all, delete-orphan", lazy="select"
    )

    fee_statements = db.relationship(
        "FeeStatement",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="select",
    )

    payments = db.relationship(
        "FeePayment",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def age(self):
        if self.date_of_birth:
            today = datetime.utcnow().date()
            return (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
        return None

    def get_total_fees_balance(self):
        """
        Sum balances across this student's fee_statements using Python properties.
        This avoids attempting SQL func.sum() on a Python @property.
        """
        return (
            sum((fs.balance or 0) for fs in self.fee_statements)
            if self.fee_statements
            else 0
        )

    def __repr__(self):
        return f"<Student {self.full_name}>"

    @classmethod
    def get_school_fees_balance(cls):
        # This works for all students
        return sum(student.get_total_fees_balance() for student in cls.query.all())

    # -------------------- Teacher --------------------
    # -------------------- Association Tables --------------------
    teacher_classes = db.Table(
        "teacher_classes",
        db.Column(
            "teacher_id", db.Integer, db.ForeignKey("teachers.id"), primary_key=True
        ),
        db.Column(
            "class_id", db.Integer, db.ForeignKey("classes.id"), primary_key=True
        ),
    )

    teacher_subjects = db.Table(
        "teacher_subjects",
        db.Column(
            "teacher_id", db.Integer, db.ForeignKey("teachers.id"), primary_key=True
        ),
        db.Column(
            "subject_id", db.Integer, db.ForeignKey("subjects.id"), primary_key=True
        ),
    )


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )  # One-to-one relationship to User
    user = db.relationship("User", back_populates="teacher_profile", lazy="joined")

    # Classes where this teacher is the class teacher (optional)
    classes_as_teacher = db.relationship(
        "Class",
        back_populates="class_teacher",
        lazy="select",
        foreign_keys="[Class.class_teacher_id]",
    )

    # Many-to-many: Classes where teacher teaches subjects
    classes = db.relationship(
        "Class",
        secondary="teacher_classes",  # association table
        lazy="select",
    )

    # Many-to-many: Subjects this teacher teaches
    subjects = db.relationship(
        "Subject",
        back_populates="teacher",
        secondary="teacher_subjects",  # association table
        lazy="select",
    )

    def __repr__(self):
        return f"<Teacher {self.id}>"

    def __repr__(self):
        return f"<Attendance {getattr(self.student, 'full_name', self.student_id)} {self.date} - {self.status}>"


# -------------------- Subject --------------------
class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    level = db.Column(db.String(50), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=True)
    compulsory = db.Column(db.Boolean, default=True)
    class_id = db.Column(
        db.Integer,
        db.ForeignKey("classes.id", name="fk_subject_class_id "),
        nullable=True,
    )
    pathway = db.Column(
        db.String(50), nullable=True
    )  # STEM, Social Sciences, Arts & Sports, or None
    level = db.Column(
        db.String(50), nullable=False
    )  # Primary, Junior Secondary, Senior Secondary
    class_ = db.relationship("Class", back_populates="subjects")
    teacher = db.relationship("Teacher", back_populates="subjects")

    # optional, for convenience
    grades = db.relationship(
        "Grade", back_populates="subject", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self):
        return f"<Subject {self.name}>"


# -------------------- Grade --------------------
class Grade(db.Model):
    __tablename__ = "grades"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    term = db.Column(db.String(20), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    marks = db.Column(db.Float, nullable=True)
    percentage = db.Column(db.Float, nullable=True)
    cbc_level = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student", back_populates="grades", lazy="joined")
    subject = db.relationship("Subject", back_populates="grades", lazy="joined")

    def grade_letter(self):
        """Return letter grade based on percentage (fallback safe)."""
        p = self.percentage or (self.marks if self.marks is not None else None)
        if p is None:
            return "N/A"
        try:
            p = float(p)
        except Exception:
            return "N/A"
        if p >= 63:
            return "EE1"
        if p >= 54:
            return "EE2"
        if p >= 45:
            return "ME1"
        if p >= 36:
            return "ME2"
        if p >= 27:
            return "AE1"
        if p >= 18:
            return "AE2"
        if p >= 9:
            return "BE1"
        return "BE2"

    def __repr__(self):
        return f"<Grade Student:{self.student_id} Subject:{self.subject_id}>"


# -------------------- Fee Statement --------------------
class FeeStatement(db.Model):
    __tablename__ = "fee_statements"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    term = db.Column(db.String(20), nullable=False)
    fee_type = db.Column(db.String(50), nullable=False)
    amount_due = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student", back_populates="fee_statements", lazy="joined")
    payments = db.relationship(
        "FeePayment",
        back_populates="fee_statement",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def amount_paid(self):
        return sum((p.amount_paid or 0) for p in self.payments)

    @property
    def balance(self):
        # amount_due - amount_paid
        return (self.amount_due or 0) - self.amount_paid

    @property
    def is_paid(self):
        return self.balance <= 0

    @property
    def is_overdue(self):
        return bool(
            self.due_date and self.due_date < datetime.utcnow() and self.balance > 0
        )

    def __repr__(self):
        return f"<FeeStatement {self.id}>"


# -------------------- Fee Payment --------------------
class FeePayment(db.Model):
    __tablename__ = "fee_payments"

    id = db.Column(db.Integer, primary_key=True)
    fee_statement_id = db.Column(
        db.Integer, db.ForeignKey("fee_statements.id"), nullable=False
    )
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50), nullable=True)
    receipt_no = db.Column(
        db.String(100),
        unique=True,
        default=lambda: f"RCPT-{str(uuid.uuid4())[:8].upper()}",
    )

    fee_statement = db.relationship(
        "FeeStatement", back_populates="payments", lazy="joined"
    )
    student = db.relationship("Student", back_populates="payments", lazy="joined")

    def __repr__(self):
        return f"<FeePayment Student:{self.student_id} Amount:{self.amount_paid}>"


# -------------------- Announcement --------------------
class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    content = db.Column(db.Text)
    priority = db.Column(
        db.String(20), default="normal"
    )  # optional: normal, high, urgent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# -------------------- Event --------------------
class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)


# -------------------- School Info --------------------
class SchoolInfo(db.Model):
    __tablename__ = "school_info"

    id = db.Column(db.Integer, primary_key=True)
    school_name = db.Column(db.String(255), nullable=False)
    motto = db.Column(db.String(255))
    contact_email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    website = db.Column(db.String(255))
    logo_file = db.Column(db.String(255))


# -------------------- Notification --------------------
class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="notifications", lazy="joined")


class Timetable(db.Model):
    __tablename__ = "timetable"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    day = db.Column(db.String(16), nullable=False)  # e.g., Monday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    room = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class_obj = db.relationship("Class", backref="timetable_entries")
    subject = db.relationship("Subject")
    teacher = db.relationship("User")

    def __repr__(self):
        return (
            f"<Timetable {self.class_id} {self.day} {self.start_time}-{self.end_time}>"
        )


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", name="fk_messages_sender_id"),
    )
    receiver_id = db.Column(
        db.Integer, db.ForeignKey("users.id", name="fk_messages_receiver_id")
    )

    subject = db.Column(db.String(255))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)


# -------------------- Attendance --------------------
class Attendance(db.Model):
    __tablename__ = "attendances"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", name="fk_attendance_student_id"),
        nullable=False,
    )
    class_id = db.Column(
        db.Integer,
        db.ForeignKey("classes.id", name="fk_attendance_class_id"),
        nullable=False,
    )
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.utcnow().date())
    status = db.Column(db.String(20), nullable=False)  # Present, Absent, Late, Excused
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    student = db.relationship("Student", back_populates="attendances", lazy="joined")
    class_obj = db.relationship("Class", back_populates="attendances", lazy="joined")

    def __repr__(self):
        return f"<Attendance {self.student.full_name} {self.date} - {self.status}>"

    # -------------------- Staff Salary --------------------


class StaffSalary(db.Model):
    __tablename__ = "staff_salaries"
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(
    db.Integer,
    db.ForeignKey(
        "employees.id",
        name="fk_staff_salaries_employee"
    ),
    nullable=False
)

    __table_args__ = (
    db.UniqueConstraint(
        "staff_id", "month", "year",
        name="uq_staff_salary_period"
    ),
)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    salary_source = db.Column(db.String(20), default="BOM")
    basic_pay = db.Column(db.Float, nullable=False)
    allowances = db.Column(db.Float, default=0)
    approved = db.Column(db.Float, default=0)
    deductions = db.Column(db.Float, default=0)
    total_pay = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    payment_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default="pending")
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    bank_account = db.Column(db.String(50), nullable=False)  # New: bank account
    bank_name = db.Column(db.String(100), nullable=True)  # Optional bank name

    staff = db.relationship("Employee", foreign_keys=[staff_id], backref="salary_records")
    approver = db.relationship("User", foreign_keys=[approved_by])

    @property
    def net_pay(self):
        return (self.basic_pay + self.allowances) - self.deductions

    def calculate_tax(gross):
        if gross <= 24000:
            return gross * 0.10
        elif gross <= 32333:
            return gross * 0.25
            return gross * 0.25
        else:
            return gross * 0.30

    def calculate_nssf(basic):
        return min(basic * 0.06, 1080)

    def calculate_nhif(basic):
        if basic <= 5999:
            return 150
        elif basic <= 7999:
            return 300
        elif basic <= 11999:
            return 400
        elif basic <= 14999:
            return 500
        elif basic <= 19999:
            return 600
        elif basic <= 24999:
            return 750
        elif basic <= 29999:
            return 850
        elif basic <= 34999:
            return 900
        elif basic <= 39999:
            return 950
        elif basic <= 44999:
            return 1000
        else:
            return 1700


class FinanceAuditLog(db.Model):
    __tablename__ = "finance_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    action = db.Column(db.String(100))
    entity = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)


class SalaryApprovalLog(db.Model):
    __tablename__ = "salary_approval_logs"

    id = db.Column(db.Integer, primary_key=True)
    salary_id = db.Column(db.Integer, db.ForeignKey("staff_salaries.id"))

    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    note = db.Column(db.String(255))
    decision = db.Column(db.String(20))  # APPROVED / REJECTED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    audit_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SalaryPaymentExecution(db.Model):
    __tablename__ = "salary_payment_executions"

    id = db.Column(db.Integer, primary_key=True)
    salary_id = db.Column(
        db.Integer, db.ForeignKey("staff_salaries.id"), nullable=False
    )

    gateway = db.Column(db.String(50))  # BANK / MPESA
    reference = db.Column(db.String(100))
    status = db.Column(db.String(30))  # QUEUED / SUCCESS / FAILED
    response_payload = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    salary = db.relationship("StaffSalary", backref="executions")


class Bursary(db.Model):
    __tablename__ = "bursaries"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    term = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student", lazy="joined")


class Scholarship(db.Model):
    __tablename__ = "scholarships"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    term = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student", lazy="joined")


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)

    # Identity
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    national_id = db.Column(db.String(20), unique=True, nullable=True)

    # Employment
    staff_number = db.Column(db.String(30), unique=True, nullable=True)
    role = db.Column(
        db.String(50), nullable=False
    )  # teacher, admin, driver, cook, guard
    department = db.Column(db.String(50), nullable=True)

    employment_type = db.Column(
        db.String(20),
        default="permanent",  # permanent, contract, casual
    )

    date_hired = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)

    # Payment
    bank_name = db.Column(db.String(100), nullable=True)
    bank_account = db.Column(db.String(50), nullable=True)

    # Optional system user link
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    user = db.relationship("User", backref="employee", uselist=False)

    salaries = db.relationship("StaffSalary", backref="employee", lazy=True)

    def __repr__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"
