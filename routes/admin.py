# routes/admin.py
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional
from extensions import db
from models import (
    Student,
    User,
    Grade,
    FeePayment,
    Announcement,
    Class,
    Teacher,
    SchoolInfo,
    FeeStatement,
    Timetable,
    Event,
    Subject,
)
from sqlalchemy import func
from functools import wraps
from decorators import roles_required
from forms import (
    EditStudentForm,
    PromoteStudentsForm,
    AnnouncementForm,
    UserForm,
    StudentForm,
    EditStudentForm,
    EditUserForm,
    MultiAssignSubjectsForm,
    EmployeeForm,
)
from sqlalchemy.orm import joinedload

admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_dashboard():
    school = SchoolInfo.query.all()
    total_students = Student.query.count()
    total_users = User.query.count()
    total_fees_due = Student.get_school_fees_balance()
    total_payments = db.session.query(func.sum(FeePayment.amount_paid)).scalar() or 0
    recent_students = Student.query.order_by(Student.id.desc()).limit(5).all()
    recent_payments = (
        FeePayment.query.order_by(FeePayment.payment_date.desc()).limit(5).all()
    )
    recent_grades = Grade.query.order_by(Grade.id.desc()).limit(5).all()
    announcements = (
        Announcement.query.order_by(Announcement.created_at.desc()).limit(5).all()
    )
    class_data = Class.query.all()
    return render_template(
        "admin_dashboard.html",
        title="Dashboard",
        school=school,
        class_data=class_data,
        total_students=total_students,
        total_fees_due=total_fees_due,
        total_users=total_users,
        total_payments=total_payments,
        recent_students=recent_students,
        recent_payments=recent_payments,
        recent_grades=recent_grades,
        announcements=announcements,
    )


@admin_bp.route("/manage/users", methods=["GET"])
@login_required
@roles_required("admin")
def manage_users():
    # 1. Get the current page number for pagination
    page = request.args.get("page", 1, type=int)

    # 2. Fetch the users data using pagination (e.g., 10 users per page)
    # The result is stored in a variable named 'paginated_users'
    paginated_users = User.query.paginate(page=page, per_page=10, error_out=False)

    # 3. PASS THE PAGINATION OBJECT to the template using the variable name 'users'.
    # This satisfies {% if users.pages > 1 %}
    return render_template(
        "users.html",  # Assuming manage_users renders users.html
        users=paginated_users,
        user=paginated_users,  # FIX: Passing the data object under the name 'users'
        title="Manage Users",
    )


@admin_bp.route("/students", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def manage_students():
    # Load students WITH joined relationships (no ambiguity)
    students = (
        Student.query.options(joinedload(Student.parent))
        .options(joinedload(Student.current_class))
        .order_by(Student.full_name)
        .all()
    )

    promote_form = PromoteStudentsForm()

    available_classes = Class.query.order_by(Class.name).all()
    promote_form.target_class.choices = [(str(c.id), c.name) for c in available_classes]

    if promote_form.validate_on_submit():
        flash("Please use the 'Promote All Students' button/link.", "info")
        return redirect(url_for("admin_bp.manage_students"))

    return render_template(
        "view_all_students.html",
        students=students,
        promote_form=promote_form,
        title="Manage Students",
    )


# --------------------------------------------------------------------------------------------------


@admin_bp.route("/student/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_student(student_id):
    """Handles editing student details."""
    student = Student.query.get_or_404(student_id)  # <-- This is your student

    # Use the same object for the form
    form = EditStudentForm(obj=student)  # Populate form fields from existing data

    if form.validate_on_submit():
        # Update Student details
        student.full_name = form.full_name.data
        student.current_class_id = form.current_class_id.data
        student.admission_number = form.admission_number.data

        db.session.commit()
        flash(f"Student {student.admission_number} details updated.", "success")
        return redirect(url_for("admin_bp.manage_students"))

    # Populate form for GET
    form.admission_number.data = student.admission_number
    form.full_name.data = student.full_name
    form.current_class_id.data = student.current_class_id

    return render_template(
        "edit_student.html",
        form=form,
        student=student,
        title=f"Edit {student.full_name}",
    )


@admin_bp.route("/student/delete/<int:student_id>", methods=["POST"])
@login_required
@roles_required("admin")
def delete_student(student_id):
    """Handles deleting a student (POST only)."""
    student = Student.query.get_or_404(student_id)
    user_record = User.query.get(student.user_id)

    try:
        # Delete student record first (due to foreign key constraints)
        db.session.delete(student)
        # Delete associated user record
        db.session.delete(user_record)
        db.session.commit()
        flash(
            f"Student {user_record.username} and their profile have been deleted.",
            "success",
        )
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting student: {e}", "danger")

    return redirect(url_for("admin_bp.manage_students"))


@admin_bp.route("/students/promote", methods=["POST"])
@login_required
@roles_required("admin")
def promote_students():
    """Handles promoting *all* students from one class level to the next."""

    # 1. Get the class levels in order
    classes_in_order = Class.query.order_by(Class.level_order).all()

    promoted_count = 0
    # 2. Iterate through classes to promote students to the next level
    for i in range(len(classes_in_order) - 1):
        current_class = classes_in_order[i]
        next_class = classes_in_order[i + 1]

        students_to_promote = Student.query.filter_by(class_id=current_class.id).all()

        for student in students_to_promote:
            student.class_id = next_class.id
            promoted_count += 1

    # 3. Handle students in the final class (e.g., graduation/leaving)
    if classes_in_order:
        final_class = classes_in_order[-1]
        graduating_students = Student.query.filter_by(class_id=final_class.id).all()
        # You would typically move these students to an 'alumni' status or delete them
        for student in graduating_students:
            # Example: Deleting graduating students
            db.session.delete(student.user)
            db.session.delete(student)

        promoted_count += len(graduating_students)

    db.session.commit()

    flash(
        f"Successfully completed promotion cycle! {promoted_count} student records were updated (promoted or graduated).",
        "success",
    )
    return redirect(url_for("admin_bp.manage_students"))


@admin_bp.route("/add_student", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def add_student():
    form = StudentForm()

    # Parent dropdown
    parents = User.query.filter_by(role="parent").order_by(User.full_name).all()
    form.parent_username_select.choices = [(p.id, p.full_name) for p in parents]

    # Class dropdown
    classes = Class.query.order_by(Class.name).all()
    form.current_class_id.choices = [(c.id, c.name) for c in classes]

    if form.validate_on_submit():
        try:
            # Prevent duplicate admission number
            if Student.query.filter_by(
                admission_number=form.admission_number.data
            ).first():
                flash("⚠️ Admission number already exists.", "warning")
                return redirect(url_for("admin_bp.add_student"))

            # Determine parent
            if form.parent_username_input.data:
                # New parent entered manually
                parent = User.query.filter_by(
                    username=form.parent_username_input.data.strip(), role="parent"
                ).first()
            else:
                # Selected from dropdown (stores parent ID)
                parent = User.query.get(form.parent_username_select.data)

            if not parent:
                flash("❌ Parent not found.", "danger")
                return redirect(url_for("admin_bp.add_student"))

            # Create student
            new_student = Student(
                full_name=form.full_name.data,
                admission_number=form.admission_number.data,
                date_of_birth=form.date_of_birth.data,
                parent_id=parent.id,  # ✔ FIXED
                current_class_id=form.current_class_id.data,
            )

            db.session.add(new_student)
            db.session.commit()

            flash(f"✅ Student {new_student.full_name} added successfully!", "success")
            return redirect(url_for("admin_bp.manage_students"))

        except Exception as e:
            db.session.rollback()
            flash(f"Database error: {e}", "danger")

    return render_template("add_student.html", form=form)


UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"csv", "xlsx"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route("/add_user", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def add_user():
    form = UserForm()

    if form.validate_on_submit():
        try:
            # Create user
            user = User(
                username=form.username.data,
                full_name=form.full_name.data,
                email=form.email.data,
                role=form.role.data,
                phone=form.phone.data,
            )
            user.set_password(form.password.data)

            db.session.add(user)
            db.session.commit()

            flash(f"User {user.full_name} added successfully!", "success")
            return redirect(url_for("admin_bp.manage_users"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error creating user: {e}", "danger")

    return render_template("add_user.html", form=form)


@admin_bp.route("/bulk_upload_users", methods=["POST"])
@roles_required("admin")
def bulk_upload_users():
    file = request.files.get("file")

    if not file or file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("admin.add_user"))

    if not allowed_file(file.filename):
        flash("Invalid file type. Please upload CSV or Excel.", "error")
        return redirect(url_for("admin.add_user"))

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(filepath)

    # Process file
    if filename.endswith(".csv"):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)

    # Expected columns: name, email, password, role
    for _, row in df.iterrows():
        if not User.query.filter_by(email=row["email"]).first():
            new_user = User(
                name=row["name"], email=row["email"], role=row.get("role", "user")
            )
            new_user.set_password(row["password"])
            db.session.add(new_user)
    db.session.commit()
    flash("Bulk user upload successful!", "success")

    return redirect(url_for("admin.add_user"))


@admin_bp.route("/add_announcement", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def add_announcement():
    form = AnnouncementForm()

    if form.validate_on_submit():
        # Manual addition
        news = announcements(
            title=form.title.data,
            content=form.content.data,
        )
        db.session.add(announcements)
        db.session.commit()
        flash(f"Announcement {Announcement.tittle} added successfully!", "success")
        return redirect(url_for("manage_announcements"))

    return render_template("add_announcement.html", form=form)


# Quick Action: View Announcements
@admin_bp.route("/announcements", methods=["GET"])
@login_required
@roles_required("admin")
def announcements():
    all_announcements = Announcement.query.all()
    return render_template("manage_announcements.html", title="Announcements")


@admin_bp.route("/user/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_user(user_id):
    # 1. Fetch the existing user (object to be edited)
    user_to_edit = User.query.get_or_404(user_id)

    # 2. Initialize the form, passing the user object to populate existing data
    form = EditUserForm(obj=user_to_edit)

    # 3. Handle POST Request (Form Submission)
    if form.validate_on_submit():
        # Update user object fields with form data
        user_to_edit.username = form.username.data
        user_to_edit.full_name = form.full_name.data
        user_to_edit.phone = form.phone.data
        user_to_edit.email = form.email.data
        user_to_edit.role = form.role.data
        user_to_edit.password = form.password.data
        user_to_edit.confirm_password = form.confirm_password.data
        form.populate_obj(user_to_edit)

        # You might also update the password separately if changed
        if form.password.data:
            user_to_edit.set_password(form.password.data)

        db.session.commit()
        flash(f"User {user_to_edit.full_name}'s profile has been updated.", "success")
        return redirect(url_for("admin_bp.manage_users"))

    # 4. Handle GET Request (Display Form)
    return render_template(
        "edit_user.html",
        title="Edit User",
        form=form,
        user=user_to_edit,  # Pass the user object to the template
    )


# ---------------- LIST ----------------
@admin_bp.route("/")
@login_required
def manage_subjects():
    if not current_user.is_admin():
        abort(403)

    subjects = Subject.query.order_by(Subject.name.asc()).all()
    return render_template("manage_subjects.html", subjects=subjects)


# ---------------- ADD ----------------
@admin_bp.route("/add", methods=["POST"])
@login_required
def add_subject():
    if not current_user.is_admin():
        abort(403)

    subject = Subject(
        name=request.form["name"],
        code=request.form["code"],
        level=request.form["level"],
        compulsory=True if request.form["compulsory"] == "1" else False,
    )

    db.session.add(subject)
    db.session.commit()
    flash("Subject added successfully!", "success")
    return redirect(url_for("admin_bp.manage_subjects"))


# ---------------- EDIT ----------------
@admin_bp.route("/edit/<int:id>", methods=["POST"])
@login_required
def edit_subject(id):
    if not current_user.is_admin():
        abort(403)

    subject = Subject.query.get_or_404(id)

    subject.name = request.form["name"]
    subject.code = request.form["code"]
    subject.level = request.form["level"]
    subject.compulsory = True if request.form["compulsory"] == "1" else False

    db.session.commit()
    flash("Subject updated successfully!", "success")
    return redirect(url_for("admin_bp.manage_subjects"))


# ---------------- DELETE ----------------
@admin_bp.route("/delete/<int:id>")
@login_required
def delete_subject(id):
    if not current_user.is_admin():
        abort(403)

    subject = Subject.query.get_or_404(id)
    db.session.delete(subject)
    db.session.commit()

    flash("Subject deleted!", "danger")
    return redirect(url_for("admin_bp.manage_subjects"))


@admin_bp.route("/messages")
@login_required
def messages():
    msgs = (
        Message.query.filter_by(receiver_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )
    return render_template("admin/messages.html", messages=msgs)


@admin_bp.route("/message/<int:message_id>")
@login_required
def view_message(message_id):
    msg = Message.query.get_or_404(message_id)

    if msg.receiver_id == current_user.id:
        msg.is_read = True
        db.session.commit()

    return render_template("admin/view_message.html", message=msg)


@admin_bp.route("/reply/<int:message_id>", methods=["GET", "POST"])
@login_required
def reply_message(message_id):
    form = MessageForm()
    msg = Message.query.get_or_404(message_id)

    if form.validate_on_submit():
        reply = Message(
            sender_id=current_user.id,
            receiver_id=msg.sender_id,
            subject="RE: " + msg.subject,
            content=form.content.data,
        )
        db.session.add(reply)
        db.session.commit()

        flash("Reply sent.", "success")
        return redirect(url_for("admin_bp.messages"))

    return render_template("admin/compose_message.html", form=form, reply_to=msg)


from utils import numeric_to_cbc, rubric_color


@admin_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_grade():
    if current_user.role != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("teacher_bp.teacher_dashboard"))

    # --- Get all classes ---
    classes = Class.query.order_by(Class.name).all()

    # --- Determine selected class ---
    selected_class = None
    class_id = request.args.get("class_id", type=int)
    if class_id:
        selected_class = Class.query.get(class_id)

    # --- Subjects taught by this teacher in the selected class ---
    subjects = []
    if selected_class:
        subjects = Subject.query.filter_by(
            teacher_id=current_user.id, class_id=selected_class.id
        ).all()

    # --- Students in the selected class ---
    students = []
    if selected_class:
        students = Student.query.filter_by(class_id=selected_class.id).all()

    # --- Existing grades ---
    existing_grades = {}
    if students:
        for student in students:
            # Fetch grades for this student, teacher, and class
            grade = Grade.query.filter_by(
                student_id=student.id,
                teacher_id=current_user.id,
                class_id=selected_class.id,
            ).first()
            if grade:
                existing_grades[student.id] = grade

    # --- Handle form submission ---
    if request.method == "POST" and selected_class:
        subject_id = int(request.form.get("subject_id"))
        term = request.form.get("term")
        year = int(request.form.get("year", datetime.now().year))

        for student in students:
            mark_input = request.form.get(f"mark_{student.id}")
            if mark_input:
                try:
                    mark = float(mark_input)
                    rubrics = numeric_to_cbc(mark)
                    # Check if grade exists
                    grade = Grade.query.filter_by(
                        student_id=student.id,
                        teacher_id=current_user.id,
                        class_id=selected_class.id,
                        subject_id=subject_id,
                        term=term,
                        year=year,
                    ).first()
                    if grade:
                        grade.marks = mark
                        grade.rubrics = rubrics
                    else:
                        grade = Grade(
                            student_id=student.id,
                            teacher_id=current_user.id,
                            class_id=selected_class.id,
                            subject_id=subject_id,
                            year=year,
                            term=term,
                            marks=mark,
                            rubrics=rubrics,
                            created_at=datetime.utcnow(),
                        )
                        db.session.add(grade)
                except ValueError:
                    flash(f"Invalid mark for {student.full_name}", "warning")
        db.session.commit()
        flash("Grades submitted successfully!", "success")
        return redirect(url_for("grade_bp.add_grade", class_id=selected_class.id))

    return render_template(
        "add_grade.html",
        classes=classes,
        subjects=subjects,
        selected_class=selected_class,
        students=students,
        terms=["Term 1", "Term 2", "Term 3"],
        year=datetime.now().year,
        existing_grades=existing_grades,
        rubric_color=rubric_color,
    )


# admin_routes.py or your admin blueprint

from sqlalchemy.orm import joinedload


@admin_bp.route("/teacher/<int:teacher_id>/assign-subjects", methods=["GET", "POST"])
def assign_subjects_to_teacher(teacher_id):
    # Get the correct teacher with user info
    teacher = Teacher.query.options(joinedload(Teacher.user)).get_or_404(teacher_id)

    # All subjects in the school
    subjects = Subject.query.order_by(Subject.name).all()

    if request.method == "POST":
        for s in subjects:
            checkbox_value = request.form.get(f"subject_{s.id}")
            if checkbox_value:  # assign teacher
                if s not in teacher.subjects:
                    teacher.subjects.append(s)
            else:  # remove teacher
                if s in teacher.subjects:
                    teacher.subjects.remove(s)

        db.session.commit()
        return redirect(url_for("teacher_bp.manage_teachers"))

    return render_template("assign_subjects.html", teacher=teacher, subjects=subjects)


@admin_bp.route("/assign-subjects", methods=["GET", "POST"])
def assign_class_subjects():
    form = MultiAssignSubjectsForm()

    # If a class is selected, filter out already assigned subjects
    if request.method == "POST" and form.class_id.data:
        selected_class = Class.query.get(form.class_id.data)
        assigned_subject_ids = [s.id for s in selected_class.subjects]
        # Only include subjects not already assigned
        available_subjects = Subject.query.filter(
            ~Subject.id.in_(assigned_subject_ids)
        ).all()
        form.subjects.choices = [(s.id, s.name) for s in available_subjects]
    else:
        form.subjects.choices = [(s.id, s.name) for s in Subject.query.all()]

    if form.validate_on_submit():
        class_obj = Class.query.get(form.class_id.data)
        subjects_to_assign = Subject.query.filter(
            Subject.id.in_(form.subjects.data)
        ).all()

        # Extra safety: skip subjects already assigned
        subjects_to_assign = [
            s for s in subjects_to_assign if s not in class_obj.subjects
        ]

        if subjects_to_assign:
            for subject in subjects_to_assign:
                class_obj.subjects.append(subject)
            db.session.commit()
            flash(
                f"Assigned {len(subjects_to_assign)} subject(s) to {class_obj.name}",
                "success",
            )
        else:
            flash("Selected subjects are already assigned to this class.", "warning")
        return redirect(url_for("admin_bp.assign_class_subjects"))

    # Display current assignments
    assignments = []
    for c in Class.query.order_by(Class.name).all():
        for s in c.subjects:
            assignments.append(
                {
                    "class_name": c.name,
                    "subject_name": s.name,
                    "teacher_name": s.teacher.user.full_name
                    if s.teacher
                    else "Unassigned",
                }
            )

    return render_template(
        "assign_class_subjects.html", form=form, assignments=assignments
    )


@admin_bp.route("/update-subject-teacher", methods=["POST"])
def update_subject_teacher():
    teachers = Teacher.query.all()  # make sure this is present and passed to template
    subject_id = request.form.get("subject_id")
    teacher_id = request.form.get("teacher_id")

    subject = Subject.query.get(subject_id)
    teacher = Teacher.query.get(teacher_id)

    if subject and teacher:
        subject.teacher = teacher
        db.session.commit()
        flash(f"{subject.name} is now assigned to {teacher.user.full_name}", "success")
    else:
        flash("Invalid subject or teacher selected", "danger")

    return redirect(url_for("admin_bp.assign_class_subjects"))


@admin_bp.route("/employees/create", methods=["GET", "POST"])
def create_employee():
    form = EmployeeForm()

    if form.validate_on_submit():
        employee = Employee(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            national_id=form.national_id.data,
            role=form.role.data,
            employment_type=form.employment_type.data,
            department=form.department.data,
            bank_name=form.bank_name.data,
            bank_account=form.bank_account.data,
        )

        db.session.add(employee)
        db.session.commit()

        flash("Employee added successfully", "success")
        return redirect(url_for("hr_bp.employee_list"))

    return render_template("hr/create_employee.html", form=form)
