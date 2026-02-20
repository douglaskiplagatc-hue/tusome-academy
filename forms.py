from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    IntegerField,
    FloatField,
    BooleanField,
    SubmitField,
    PasswordField,
    DateField,
    HiddenField,
    SelectMultipleField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    Email,
    NumberRange,
    Optional,
    ValidationError,
    EqualTo,
)
from datetime import datetime
from extensions import db
from models import (
    User,
    Student,
    Subject,
    FeeStatement,
    Class,
    Teacher,
    Grade,
    FeeStatement,
    FeePayment,
    Announcement,
    SchoolInfo,
    Notification,
)
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    SelectField,
    IntegerField,
    FloatField,
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from datetime import datetime
from models import Student, User, Subject


# -------------------- Login Form --------------------
class LoginForm(FlaskForm):
    email = StringField("Email or Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")
    submit = SubmitField("Login")


# -------------------- User Form --------------------
class UserForm(FlaskForm):
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=3, max=120)]
    )
    full_name = StringField("Full Name", validators=[DataRequired()])
    phone = StringField("Phone Number", validators=[Length(max=10)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    is_active = BooleanField("Active", default=True)
    role = SelectField(
        "Role",
        choices=[
            ("admin", "Admin"),
            ("teacher", "Teacher"),
            ("parent", "Parent"),
            ("finance", "Finance"),
            ("student", "Student"),
        ],
        validators=[DataRequired()],
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password")]
    )

    submit = SubmitField("Add User")


class EditUserForm(FlaskForm):
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=4, max=20)]
    )
    email = StringField("Email", validators=[DataRequired(), Email()])
    full_name = StringField(
        "Full Name", validators=[DataRequired(), Length(min=2, max=100)]
    )
    phone = StringField("Phone Number", validators=[Length(max=20)])
    role = SelectField(
        "Role",
        choices=[
            ("admin", "Administrator"),
            ("teacher", "Teacher"),
            ("parent", "Parent"),
        ],
        validators=[DataRequired()],
    )
    password = PasswordField("Password", validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[EqualTo("password", message="Passwords must match")],
    )
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Update User")


class ChangePasswordForm(FlaskForm):
    old_password = PasswordField("Old Password", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password", validators=[DataRequired(), Length(min=6)]
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="Passwords must match"),
        ],
    )
    submit = SubmitField("Change Password")


class StudentForm(FlaskForm):
    full_name = StringField(
        "Full Name", validators=[DataRequired(), Length(min=2, max=100)]
    )
    admission_number = StringField(
        "Admission Number", validators=[DataRequired(), Length(min=2, max=50)]
    )
    date_of_birth = DateField(
        "Date of Birth",
        format="%Y-%m-%d",
        validators=[DataRequired(message="Date of birth is required.")],
    )

    # Choose one way to identify parent — here I keep dropdown
    parent_username_select = SelectField(
        "Select Parent (optional)", coerce=str, validators=[Optional()]
    )
    parent_username_input = StringField(
        "Or Enter New Parent Username",
        validators=[Optional()],
        render_kw={"placeholder": "Enter new parent’s username"},
    )

    # Choose one class field (matches Student model’s FK)
    current_class_id = SelectField(
        "Current Class", coerce=int, validators=[DataRequired()]
    )

    submit = SubmitField("Add Student")


class EditStudentForm(FlaskForm):
    full_name = StringField(
        "Full Name", validators=[DataRequired(), Length(min=2, max=100)]
    )
    admission_number = StringField(
        "Admission Number", validators=[DataRequired(), Length(min=2, max=50)]
    )
    date_of_birth = DateField(
        "Date of Birth (DD-MM-YYYY)", format="%d-%m-%y", validators=[DataRequired()]
    )
    current_class = SelectField(
        "Current Class", coerce=int, validators=[DataRequired()]
    )
    parent_username = StringField("Parent Username", validators=[DataRequired()])
    status = SelectField(
        "Status",
        choices=[("Active", "Active"), ("Inactive", "Inactive")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Update Student")


# -------------------- Class Form --------------------
class ClassForm(FlaskForm):
    name = StringField("Class Name", validators=[DataRequired(), Length(max=50)])
    teacher_id = SelectField(
        "Assigned Teacher", coerce=int, validators=[Optional()], choices=[]
    )
    submit = SubmitField("Add Class")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher_id.choices = [
            (u.id, u.full_name)
            for u in User.query.filter_by(role="teacher").order_by("full_name").all()
        ]
        self.teacher_id.choices.insert(0, (0, "--- No Teacher Assigned ---"))

    @staticmethod
    def query():
        pass


# -------------------- Subject Form --------------------
class SubjectForm(FlaskForm):
    name = StringField("Subject Name", validators=[DataRequired()])
    code = StringField("Subject Code", validators=[DataRequired()])
    submit = SubmitField("Add Subject")


# -------------------- Grade Form --------------------
class GradeForm(FlaskForm):
    student_id = SelectField("Student", coerce=int, validators=[DataRequired()])
    parent_id = SelectField("Parent", coerce=int, validators=[DataRequired()])

    subject_name = SelectField("Subject", coerce=int, validators=[DataRequired()])
    term = SelectField(
        "Term",
        choices=[("Term 1", "Term 1"), ("Term 2", "Term 2"), ("Term 3", "Term 3")],
        validators=[DataRequired()],
    )
    year = IntegerField(
        "Year",
        validators=[DataRequired(), NumberRange(min=2000, max=datetime.now().year)],
    )
    grading_system = SelectField(
        "Grading System",
        choices=[("numeric", "Numeric (0–100)"), ("cbc", "CBC Performance Level")],
        default="numeric",
        validators=[DataRequired()],
    )

    # Numeric marks (KCPE/KCSE style)
    numeric_marks = IntegerField(
        "Numeric Marks",
        validators=[
            NumberRange(min=0, max=100, message="Marks must be between 0 and 100")
        ],
    )

    # CBC performance levels
    cbc_marks = SelectField(
        "CBC Performance Level",
        choices=[
            ("EE1", "Exceding Expectation1"),
            ("EE2", "Exceding Expectation2"),
            ("ME1", "Meeting Expectation1"),
            ("ME2", "Meeting Expectation2"),
            ("AE1", "Aproaching Expectation1"),
            ("AE2", "Aproaching Expectation2"),
            ("BE1", "Below Expectation1"),
            ("BE2", "Below Expectation2"),
        ],
    )
    submit = SubmitField("Add Grade")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.student_id.choices = [
            (s.id, f"{s.full_name} (ADM: {s.admission_number})")
            for s in Student.query.all()
        ]

        self.parent_id.choices = [
            (p.id, p.username)
            for p in User.query.filter_by(role="parent").order_by(User.username).all()
        ]
        self.subject_name.choices = [(sub.id, sub.name) for sub in Subject.query.all()]


class FeeStatementForm(FlaskForm):
    year = IntegerField("Year", validators=[DataRequired(), NumberRange(min=2000)])
    term = SelectField(
        "Term",
        choices=[("Term 1", "Term 1"), ("Term 2", "Term 2"), ("Term 3", "Term 3")],
        validators=[DataRequired()],
    )
    class_id = SelectField(
        "Class",
        coerce=int,
        validators=[DataRequired()],
    )
    fee_type = SelectField(
        "Fee Type",
        choices=[
            ("Tuition", "Tuition"),
            ("Examination", "Examination"),
            ("Trip", "Trip"),
            ("Repairs and Mantainance", "Repairs and Mantainance"),
            ("Boarding", "Boarding"),
            ("Stationery", "Stationery"),
        ],
        validators=[DataRequired()],
    )
    amount_due = FloatField(
        "Amount Due", validators=[DataRequired(), NumberRange(min=0)]
    )
    submit = SubmitField("Generate Fee Statements")


class FeePaymentForm(FlaskForm):
    student = SelectField("Student", coerce=int, validators=[DataRequired()])
    fee_statement = SelectField(
        "Fee Statement", coerce=int, validators=[DataRequired()]
    )
    amount_paid = FloatField(
        "Amount Paid", validators=[DataRequired(), NumberRange(min=0)]
    )
    payment_method = SelectField(
        "Payment Method",
        choices=[
            ("CASH", "Cash"),
            ("BANK TRANSFER", "Bank Transfer"),
            ("M-PESA", "M-Pesa"),
        ],
        validators=[DataRequired()],
    )
    method = StringField("Payment Details (optional)")
    receipt_no = StringField(
        "Receipt Number", validators=[DataRequired(), Length(max=100)]
    )
    submit = SubmitField("Add Payment")

    def __init__(self, *args, **kwargs):
        super(FeePaymentForm, self).__init__(*args, **kwargs)
        self.student.choices = [(s.id, s.full_name) for s in Student.query.all()]
        self.fee_statement.choices = [
            (
                fs.id,
                f"{fs.student.full_name} - {fs.term} {fs.year} -Balance: {fs.amount_due - fs.get_total_payments()}",
            )
            for fs in FeeStatement.query.all()
        ]


class NewsForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    content = TextAreaField("Content", validators=[DataRequired()])
    submit = SubmitField("Publish News")


class SchoolInfoForm(FlaskForm):
    school_name = StringField("School Name", validators=[DataRequired()])
    motto = StringField("Motto")
    contact_email = StringField("Contact Email", validators=[DataRequired(), Email()])
    phone = StringField("Contact Phone")
    address = StringField("Address")
    website = StringField("Website")
    logo_file = HiddenField("Logo File")
    submit = SubmitField("Update Info")


class SchoolForm(FlaskForm):
    school_name = StringField("School Name", validators=[DataRequired()])
    name = StringField("School Name", validators=[DataRequired(), Length(max=255)])
    motto = StringField("School Motto", validators=[DataRequired(), Length(max=255)])
    contact_email = StringField(
        "School Email", validators=[DataRequired(), Length(max=20)]
    )
    website = StringField(
        "School Website", validators=[DataRequired(), Length(max=100)]
    )
    address = StringField("Address", validators=[Length(max=255)])
    phone = StringField("Phone", validators=[Length(max=50)])
    submit = SubmitField("Save")


class UserSearchForm(FlaskForm):
    search_query = StringField("Search for users...", validators=[Optional()])


class GradeImportForm(FlaskForm):
    file = HiddenField("File")
    term = SelectField(
        "Term",
        choices=[("Term 1", "Term 1"), ("Term 2", "Term 2"), ("Term 3", "Term 3")],
        validators=[DataRequired()],
    )
    year = IntegerField("Year", validators=[DataRequired()])
    submit = SubmitField("Import Grades")


class StudentAnalyticsForm(FlaskForm):
    """
    Form to select a student for analytics reporting.
    """

    student_id = SelectField("Select Student", coerce=int, validators=[DataRequired()])
    submit = SubmitField("View Analytics")

    def __init__(self, *args, **kwargs):
        super(StudentAnalyticsForm, self).__init__(*args, **kwargs)
        self.student_id.choices = [(0, "Select Student")] + [
            (s.id, s.full_name) for s in Student.query.order_by(Student.full_name).all()
        ]


class AnnouncementForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(min=2, max=100)])
    content = TextAreaField("Content", validators=[DataRequired()])
    submit = SubmitField("Publish Announcement")


class AddNewsForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=150)])
    content = TextAreaField("Content", validators=[DataRequired()])
    submit = SubmitField("Publish News")


class AssignClassForm(FlaskForm):
    class_id = SelectField("Select Class", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Assign Class")


class EditStudentForm(FlaskForm):
    # Assuming student details are tied to a User record
    username = StringField("Username", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    admission_number = StringField("Admission Number", validators=[DataRequired()])
    # Add other fields as needed (e.g., date_of_birth, gender)
    submit = SubmitField("Update Student")


class PromoteStudentsForm(FlaskForm):
    # The 'class_choices' will be set dynamically in the route
    target_class = SelectField("Promote to Class:", validators=[DataRequired()])
    submit = SubmitField("Promote Selected Students")


# forms.py (Add this new form)

# ... (other imports) ...

from flask_wtf.file import FileField, FileRequired, FileAllowed


# -------------------- Bulk Upload Form --------------------
class BulkUploadForm(FlaskForm):
    upload_type = SelectField(
        "Data Type to Upload",
        choices=[
            ("parent_user", "Parents (Users)"),
            ("student", "Students"),
            ("grade", "Grades"),
        ],
        validators=[DataRequired()],
    )
    file = FileField(
        "Select CSV File",
        validators=[
            FileRequired(),
            FileAllowed(["csv"], "Only CSV files are allowed!"),
        ],
    )
    submit = SubmitField("Process Bulk Upload")


class AttendanceForm(FlaskForm):
    class_id = SelectField("Class", coerce=int, validators=[DataRequired()])
    date = DateField("Date", format="%Y-%m-%d", validators=[DataRequired()])
    submit = SubmitField("Load Students")

    def set_class_choices(self):
        # Populate choices dynamically from Class table
        self.class_id.choices = [
            (c.id, c.name) for c in Class.query.order_by(Class.name).all()
        ]


class MessageForm(FlaskForm):
    subject = StringField("Subject", validators=[DataRequired()])
    content = TextAreaField("Message", validators=[DataRequired()])
    submit = SubmitField("Send")


class MultiAssignSubjectsForm(FlaskForm):
    class_id = SelectField("Select Class", coerce=int, validators=[DataRequired()])
    subjects = SelectMultipleField(
        "Select Subjects", coerce=int, validators=[DataRequired()]
    )
    submit = SubmitField("Assign Subjects")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_id.choices = [
            (c.id, c.name) for c in Class.query.order_by(Class.name).all()
        ]
        self.subjects.choices = [
            (s.id, s.name) for s in Subject.query.order_by(Subject.name).all()
        ]


class StaffSalaryForm(FlaskForm):
    staff_id = SelectField("Staff", coerce=int, choices=[])
    month = SelectField(
        "Month",
        choices=[(i, i) for i in range(1, 13)],
        coerce=int,
        validators=[DataRequired()],
    )
    year = IntegerField("Year", validators=[DataRequired(), NumberRange(min=2000)])
    basic_pay = FloatField("Basic Pay", validators=[DataRequired()])
    allowances = FloatField("Allowances", default=0)
    deductions = FloatField("Deductions", default=0)
    bank_account = StringField("Bank Account Number", validators=[DataRequired()])
    bank_name = StringField("Bank Name", validators=[DataRequired()])
    submit = SubmitField("Add Salary")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.staff_id.choices = [
            (u.id, u.full_name)
            for u in User.query.filter(
                User.role.in_(["teacher", "finance", "admin"])
            ).all()
        ]


class EmployeeForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    national_id = StringField("National ID")

    role = SelectField(
        "Role",
        choices=[
            ("teacher", "Teacher"),
            ("admin", "Admin"),
            ("finance", "Finance"),
            ("driver", "Driver"),
            ("cook", "Cook"),
            ("guard", "Guard"),
            ("casual", "Casual Worker"),
            ("bom", "BOM Staff"),
        ],
        validators=[DataRequired()],
    )

    employment_type = SelectField(
        "Employment Type",
        choices=[
            ("permanent", "Permanent"),
            ("contract", "Contract"),
            ("casual", "Casual"),
        ],
    )

    department = StringField("Department")
    bank_name = StringField("Bank Name")
    bank_account = StringField("Bank Account")

    submit = SubmitField("Save Employee")
