# routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import (
    login_required,
    current_user,
    login_user,
    logout_user,
)  # <-- Added login_user/logout_user
from sqlalchemy import func
from datetime import datetime
from extensions import db
from models import (
    User,
    Student,
    Class,
    Subject,
    Grade,
    FeeStatement,
    FeePayment,
    Announcement,
    SchoolInfo,
    Notification,
)

# Assuming these forms exist in forms.py
from forms import (
    LoginForm,
    FeeStatementForm,
    FeePaymentForm,
    GradeForm,
    ClassForm,
    SubjectForm,
    AnnouncementForm,
    StudentForm,  # Add forms for other modules as needed
)

# Assuming these decorators exist in decorators.py
from decorators import admin_required, teacher_required, parent_required

# ------------------- BLUEPRINT DEFINITIONS ------------------- #
main_bp = Blueprint("main_bp", __name__)
auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")
admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")
class_bp = Blueprint("class_bp", __name__, url_prefix="/classes")
grade_bp = Blueprint("grade_bp", __name__, url_prefix="/grades")
fee_bp = Blueprint("fee_bp", __name__, url_prefix="/fees")
bulk_upload_bp = Blueprint("bulk_upload", __name__, url_prefix="/bulk_upload")
subject_bp = Blueprint("subject_bp", __name__, url_prefix="/subjects")
parent_bp = Blueprint("parent_bp", __name__, url_prefix="/parent")
teacher_bp = Blueprint("teacher_bp", __name__, url_prefix="/teacher")
student_bp = Blueprint("student_bp", __name__, url_prefix="/student")
settings_bp = Blueprint("settings_bp", __name__, url_prefix="/settings")
announcement_bp = Blueprint("announcement_bp", __name__, url_prefix="/announcements")


# ------------------- MAIN BLUEPRINT (ROOT) ------------------- #


@main_bp.route("/")
def dashboard():
    """Application root. Redirects logged-in users to their respective dashboards."""

    if current_user.role == "is_admin":
        return redirect(url_for("admin_bp.admin_dashboard"))

    else:
        if current_user.role == "is_parent":
            return redirect(url_for("parent_bp.parent_dashboard"))


# ------------------- AUTH BLUEPRINT (CRITICAL) ------------------- #


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handles user login."""
    if current_user.role:
        return redirect(url_for("main_bp.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get("next")
            return (
                redirect(next_page)
                if next_page
                else redirect(url_for("main_bp.dashboard"))
            )
        else:
            flash("Login Unsuccessful. Check email and password", "danger")

    return render_template("login.html", form=form, title="Login")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Handles user registration (optional, might only be for Admins to create users)."""
    # This route is often disabled or restricted to admin_required
    form = RegistrationForm()
    if form.validate_on_submit():
        # User creation logic here
        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("auth_bp.login"))

    return render_template("register.html", form=form, title="Register")


@auth_bp.route("/logout")
@login_required
def logout():
    """Logs the user out."""
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("main_bp.index"))


# Assuming models are imported: Student, Payment, Grade, Announcement, User, School, Class
# Assuming decorators are imported: admin_required, teacher_required, parent_required

# --- Admin Blueprint (admin_bp) ---


# Main Admin Dashboard View (url_for('admin_bp.admin_dashboard'))
@admin_bp.route("/admin_dashboard", methods=["GET", "POST"])
@admin_required
def admin_dashboard():
    all_Statements = FeeStatement.query.all()
    total_fees_due_calculated = sum(
        Statement.get_balance() for Statement in all_Statements
    )
    # Data required for the admin_dashboard.html template
    context = {
        "current_user": User.query.filter_by(id=1).first(),  # Example user
        "school": SchoolInfo.query.first(),
        "total_students": Student.query.count(),
        "total_parents": User.query.count(),
        "total_subjects": Subject.query.count(),
        # Complex data placeholders:
        # Complex data placeholders:
        "total_fees_due": total_fees_due_calculated,
        "recent_payments": FeePayment.query.order_by(FeePayment.payment_date.desc())
        .limit(5)
        .all(),
        "recent_students": Student.query.order_by(Student.admission_number.desc())
        .limit(5)
        .all(),
        "active_announcements": Announcement.query.filter_by(created_at=True).all(),
        # ... and other variables like total_fees_paid, class_distribution, recent_grades
    }
    return render_template("admin_dashboard.html", **context)


# Quick Action: Add New Student (url_for('admin_bp.add_student'))
# The final URL will be /admin/users if url_prefix='/admin' was used above
@admin_bp.route("/users", methods=["GET", "POST"])
def manage_students():
    """
    Handles displaying the list of users and processing new user creation.
    """
    # --- GET Request (Display the User List) ---
    if request.method == "GET":
        # 1. Fetch all users from the database
        students = Student.query.all()

        # 2. Render the template, passing the user list
        return render_template("admin/manage_students.html", students=students)

    # --- POST Request (Handle Form Submission) ---
    if request.method == "POST":
        # 1. Extract form data
        full_name = request.form.get("full_name")
        admission_number = request.form.get("admission_number")
        parent_id = request.form.get("parent_id")  # Remember to hash passwords!

        return redirect(url_for("admin_bp.manage_users"))

    # If somehow neither GET nor POST, though highly unlikely with methods=['GET', 'POST']
    return "Method Not Allowed", 405


@admin_bp.route("/students/add", methods=["GET", "POST"])
@admin_required
def add_student():
    # form = StudentRegistrationForm()
    # if form.validate_on_submit(): ...
    return render_template("admin/add_student.html", title="Add Student")


# Quick Action: Add New User (Teacher/Parent/Admin) (url_for('admin_bp.add_user'))
@admin_bp.route("/users/add", methods=["GET", "POST"])
@admin_required
def add_user():
    # form = UserRegistrationForm()
    return render_template("admin/add_user.html", title="Add User")


@admin_bp.route("/users", methods=["GET", "POST"])
def manage_users():
    """
    Handles displaying the list of users and processing new user creation.
    """
    # --- GET Request (Display the User List) ---
    if request.method == "GET":
        # 1. Fetch all users from the database
        users = User.query.all()

        # 2. Render the template, passing the user list
        return render_template("admin/manage_users.html", users=users)

    # --- POST Request (Handle Form Submission) ---
    if request.method == "POST":
        # 1. Extract form data
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")  # Remember to hash passwords!

        # 2. Basic validation (simplified)
        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("admin_bp.manage_users"))

        # 3. Create and save the new user (Placeholder logic)
        try:
            new_user = User(username=username, email=email)
            # new_user.set_password(password) # You would use a method to hash the password
            # db.session.add(new_user)
            # db.session.commit()

            flash(f'User "{username}" created successfully!', "success")

        except Exception as e:
            # Handle unique constraints, database errors, etc.
            flash(f"Error creating user: {str(e)}", "danger")

        # Redirect back to the GET route to prevent form re-submission
        return redirect(url_for("admin_bp.manage_users"))

    # If somehow neither GET nor POST, though highly unlikely with methods=['GET', 'POST']
    return "Method Not Allowed", 405


# Quick Action: Add Fee Payment (url_for('admin_bp.add_fee_payment'))
@admin_bp.route("/fees/payment/add", methods=["GET", "POST"])
@admin_required
def add_fee_payment():
    # form = FeePaymentForm()
    return render_template("admin/record_payment.html", title="Record Payment")


# --- Grade Blueprint (grade_bp) ---


# Quick Action: Add Grade (url_for('grade_bp.add_grade'))
@grade_bp.route("/add", methods=["GET", "POST"])
@teacher_required
def add_grade():
    students = Student.query.order_by(Student.full_name).all()
    subjects = Subject.query.all()
    return render_template(
        "grades/add_grade.html", students=students, subjects=subjects, title="Add Grade"
    )


# --- Other Links ---


# General Announcements Page (url_for('misc_bp.announcements'))
@admin_bp.route("/announcements")
def announcements():
    announcements = Announcement.query.order_by(Announcement.date.desc()).all()
    return render_template(
        "announcements/list.html", announcements=announcements, title="Announcements"
    )


# --- Parent Blueprint (parent_bp) ---


@parent_bp.route("/")
@parent_required
def parent_dashboard():
    # Assuming 'current_user' is the logged-in Parent object
    children = Student.query.filter_by(parent_id=current_user.id).all()

    # Collect IDs for filtering grades and fees
    child_ids = [child.id for child in children]

    context = {
        "current_user": current_user,
        "children": children,
        "total_balance": sum(child.get_total_fees_balance() for child in children),
        "recent_grades": Grade.query.filter(Grade.student_id.in_(child_ids))
        .order_by(Grade.date.desc())
        .all(),
        "announcements": Announcement.query.filter_by(target="parent").limit(5).all(),
        "fee_statements": FeeStatement.query.filter(
            FeeStatement.student_id.in_(child_ids)
        )
        .order_by(FeeStatement.date.desc())
        .all(),
    }
    return render_template("parent_dashboard.html", **context)


# --- Teacher Blueprint (teacher_bp) ---


@teacher_bp.route("/")
@teacher_required
def teacher_dashboard():
    # Assuming 'current_user' is the logged-in Teacher object
    teacher_class = Class.query.filter_by(teacher_id=current_user.id).first()

    if teacher_class:
        class_name = teacher_class.name
        students = Student.query.filter_by(class_id=teacher_class.id).all()
        # Placeholder for complex aggregation logic
        performance_data = calculate_class_performance(teacher_class)
    else:
        class_name = None
        students = []
        performance_data = []

    return render_template(
        "teacher_dashboard.html",
        class_name=class_name,
        students=students,
        performance_data=performance_data,
        title="Teacher Dashboard",
    )


# Helper function to get the data (must be defined elsewhere)
def calculate_class_performance(teacher_class):
    # Logic to query grades for all students in the class and calculate subject averages
    # Example: return [('Math', 85.5), ('Science', 79.2), ('English', 90.1)]
    return []


# ------------------- ADMIN, CLASS, GRADES, FEES, BULK, PARENT (EXISTING ROUTES) ------------------- #
# ... (Your existing routes are copied here, but I will skip them for brevity in this response) ...


# ------------------- STUDENT BLUEPRINT (COMPLETING CRUD) ------------------- #


@student_bp.route("/")
@admin_required
def students():
    students = Student.query.all()
    return render_template(
        "admin/students.html", students=students, title="Manage Students"
    )


@student_bp.route("/add", methods=["GET", "POST"])
@admin_required
def add_student():
    form = StudentForm()
    if form.validate_on_submit():
        # Add student logic
        flash("Student added successfully.", "success")
        return redirect(url_for("student_bp.student_list"))
    return render_template("admin/add_student.html", form=form, title="Add Student")


@student_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_student(id):
    student = Student.query.get_or_404(id)
    form = StudentForm(obj=student)
    if form.validate_on_submit():
        # Update student logic
        flash("Student updated successfully.", "success")
        return redirect(url_for("student_bp.student_list"))
    return render_template(
        "admin/edit_student.html", form=form, student=student, title="Edit Student"
    )


# ------------------- SUBJECT BLUEPRINT (COMPLETING CRUD) ------------------- #


@subject_bp.route("/")
@admin_required
def subjects():
    subjects = Subject.query.all()
    return render_template(
        "admin/subjects.html", subjects=subjects, title="Manage Subjects"
    )


@subject_bp.route("/add", methods=["GET", "POST"])
@admin_required
def add_subject():
    form = SubjectForm()
    if form.validate_on_submit():
        # Add subject logic
        flash("Subject added successfully.", "success")
        return redirect(url_for("subject_bp.subject_list"))
    return render_template("admin/add_subject.html", form=form, title="Add Subject")


# ------------------- ANNOUNCEMENT BLUEPRINT (COMPLETING CRUD) ------------------- #


@announcement_bp.route("/")
@login_required
def announcements():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template(
        "announcements/list.html", announcements=announcements, title="Announcements"
    )


@announcement_bp.route("/create", methods=["GET", "POST"])
@admin_required
def add_announcement():
    form = AnnouncementForm()
    if form.validate_on_submit():
        # Create announcement logic
        flash("Announcement posted successfully.", "success")
        return redirect(url_for("announcement_bp.announcement_list"))
    return render_template(
        "announcements/create.html", form=form, title="New Announcement"
    )


fee_bp = Blueprint("fee_bp", __name__, url_prefix="/fees")


@fee_bp.route("/structure", methods=["GET", "POST"])
def manage_fees():
    """Route to define and manage fee structures and types."""
    # Placeholder: Logic for fee structure setup
    return render_template("fees/manage_fees.html", title="Manage Fee Structures")


@fee_bp.route("/statements", methods=["GET"])
def view_fee_statements():
    """Route to view a list of all generated fee statements."""
    # Placeholder: Logic to list statements
    return render_template("fees/view_fee_statements.html", title="Fee Statements")


grade_bp = Blueprint("grade_bp", __name__, url_prefix="/grades")


@grade_bp.route("/", methods=["GET", "POST"])
def manage_grades():
    """Route to display and manage student grades and assessment results."""
    # Placeholder: Logic for displaying/recording grades
    return render_template("grades/manage_grades.html", title="Manage Grades")


class_bp = Blueprint("class_bp", __name__, url_prefix="/classes")


@class_bp.route("/", methods=["GET", "POST"])
def manage_classes():
    """Route to display and manage class/section records."""
    # Placeholder: Logic for listing/adding classes
    return render_template("classes/manage_classes.html", title="Manage Classes")


@bulk_upload_bp.route("/upload", methods=["GET", "POST"])
def bulk_upload():
    """Route to handle uploading CSV/Excel files for bulk data entry."""
    # Placeholder: Logic for file upload and processing
    return render_template("bulk/bulk_upload.html", title="Bulk Data Entry")


# Ensure this matches the name used in url_for('admin_bp.manage_users'), etc.
admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")


# --- Routes from previous discussion (Manage Users) ---
@admin_bp.route("/users", methods=["GET", "POST"])
def manage_users():
    """Route to display and manage user accounts."""
    # (Existing implementation goes here)
    return render_template("admin/manage_users.html")


# --- New Routes Required by admin_dashboard.html ---


@admin_bp.route("/students/add", methods=["GET", "POST"])
def add_student():
    """Route to handle the form for adding a new student."""
    return render_template("admin/add_student.html", title="Add New Student")


@admin_bp.route("/users/add", methods=["GET", "POST"])
def add_user():
    """Route to handle the form for adding a new user (admin, teacher, etc.)."""
    return render_template("admin/add_user.html", title="Add New User")


@admin_bp.route("/payments/record", methods=["GET", "POST"])
def add_fee_payment():
    """Route to record a new fee payment."""
    return render_template("fees/record_payment.html", title="Record Fee Payment")


grade_bp = Blueprint("grade_bp", __name__, url_prefix="/grades")

# --- New Route Required by admin_dashboard.html ---


@grade_bp.route("/add", methods=["GET", "POST"])
def add_grade():
    """Route to handle the form for adding a new grade entry/result."""
    return render_template("grades/add_grade.html", title="Add Student Grade")


# ------------------- SETTINGS BLUEPRINT ------------------- #


@settings_bp.route("/")
@admin_required
def general_settings():
    # form = SettingsForm(obj=SchoolInfo.query.first())
    # Settings view and form handling
    return render_template("admin/settings.html", title="General Settings")


# ------------------- REGISTER ALL BLUEPRINTS (FINAL) ------------------- #


def register_blueprints(app):
    app.register_blueprint(main_bp)  # <-- CRITICAL: Register the root blueprint
    app.register_blueprint(
        auth_bp
    )  # <-- CRITICAL: Register the authentication blueprint
    app.register_blueprint(admin_bp)
    app.register_blueprint(class_bp)
    app.register_blueprint(grade_bp)
    app.register_blueprint(fee_bp)
    app.register_blueprint(bulk_upload_bp)
    app.register_blueprint(parent_bp)
    app.register_blueprint(subject_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(announcement_bp)
    app.register_blueprint(teacher_bp)
