# routes/teacher.py
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from extensions import db
from models import (
    Assignment,
    Teacher,
    Student,
    Class,
    Subject,
    Grade,
    Attendance,
    Announcement,
    User,
    Message,
)
from forms import MessageForm, UserForm, SubjectForm, ClassForm
from datetime import datetime, date
from decorators import roles_required

teacher_bp = Blueprint("teacher_bp", __name__, url_prefix="/teacher")


# ----------------------------------------------------
# 1. TEACHER DASHBOARD / ADMIN OVERVIEW
# ----------------------------------------------------
@teacher_bp.route("/dashboard")
@roles_required("teacher")
def teacher_dashboard():
    # Get current teacher profile
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("auth_bp.login"))

    # Get or set term/year/assessment from request
    term = request.args.get("term", "Term 1")
    year = request.args.get("year", type=int, default=datetime.utcnow().year)
    assessment_type = request.args.get("assessment", "Exam 1")

    # --- Get classes the teacher is assigned to ---
    assigned_classes = set()
    # as class teacher
    for cls in Class.query.filter_by(class_teacher_id=teacher.id).all():
        assigned_classes.add(cls)
    # as subject teacher (through teacher.classes many-to-many)
    for cls in teacher.classes:
        assigned_classes.add(cls)
    assigned_classes = list(assigned_classes)
    total_classes = len(assigned_classes)

    # --- Total students in those classes ---
    class_ids = [c.id for c in assigned_classes]
    total_students = Student.query.filter(Student.current_class_id.in_(class_ids)).count() if class_ids else 0

    # --- Grades entered by this teacher (for current term/year/assessment) ---
    # If Grade has a teacher_id column, use it; otherwise join via Subject
    # Assuming Grade model has a 'teacher_id' (if not, adjust accordingly)
    grades_entered= Grade.query.join(Subject).filter(Subject.teacher_id == teacher.id, Grade.term == term, Grade.year == year).count()
    recent_grades = Grade.query.join(Subject).filter(Subject.teacher_id == teacher.id).order_by(Grade.created_at.desc()).limit(10).all()

    # --- Upcoming assignments (if Assignment model exists) ---
    upcoming_assignments = []
    today = date.today()
    # Check if Assignment model is defined to avoid errors
    if 'Assignment' in globals() or hasattr( models, 'Assignment'):
        assignments = Assignment.query.filter(
            Assignment.teacher_id == teacher.user_id,
            Assignment.due_date >= today
        ).order_by(Assignment.due_date.asc()).limit(5).all()
        for assign in assignments:
            days_left = (assign.due_date - today).days
            upcoming_assignments.append({
                'title': assign.title,
                'class_name': assign.class_obj.name if assign.class_obj else 'N/A',
                'due_date': assign.due_date,
                'days_left': days_left
            })

    # --- Recent grades (last 10) for this teacher ---

    # Build stats dict
    stats = {
        'total_classes': total_classes,
        'total_students': total_students,
        'grades_entered': grades_entered,
        'pending_assignments': len(upcoming_assignments)
    }

    return render_template(
        "teacher_dashboard.html",
        stats=stats,
        recent_grades=recent_grades,
        upcoming_assignments=upcoming_assignments,
        term=term,
        year=year,
        assessment_type=assessment_type,
        # Keep any other existing variables if needed (e.g., is_admin)
        is_admin=False  # or current_user.role == "admin"
    )

# ----------------------------------------------------
# 2. MANAGE TEACHERS
# ----------------------------------------------------
@teacher_bp.route("/manage")
@login_required
@roles_required("teacher", "admin")
def manage_teachers():
    sort_option = request.args.get("sort", "name")

    # Determine order
    if sort_option == "name":
        order_by = User.full_name.asc()
    elif sort_option == "newest":
        order_by = User.id.desc()
    elif sort_option == "oldest":
        order_by = User.id.asc()
    else:
        order_by = User.full_name.asc()

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = 10  # Adjust as needed

    # Query teachers with their User relationship
    teachers = (
        Teacher.query.options(joinedload(Teacher.user))
        .join(User, Teacher.user_id == User.id)
        .order_by(order_by)
        .paginate(page=page, per_page=per_page)
    )

    # Additional data for dropdowns etc.
    subjects = Subject.query.all()
    classes = Class.query.all()
    users = User.query.all()

    return render_template(
        "teacher/teachers.html",
        teachers=teachers,
        subjects=subjects,
        classes=classes,
        users=users,
        sort_option=sort_option,
    )

@teacher_bp.route("/api/teachers")
@login_required
@roles_required("teacher", "admin")
def api_get_teachers():
    """API endpoint for AJAX teacher list"""
    # Get filter parameters
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "")
    status = request.args.get("status", "all")
    subject_id = request.args.get("subject", None, type=int)
    sort = request.args.get("sort", "name")

    per_page = 10

    # Base query
    query = Teacher.query.options(joinedload(Teacher.user), joinedload(Teacher.subjects), joinedload(Teacher.classes)).join(User)

    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )

    # Apply status filter
    if status == "active":
        query = query.filter(Teacher.is_active == True)
    elif status == "inactive":
        query = query.filter(Teacher.is_active == False)

    # Apply subject filter
    if subject_id:
        query = query.filter(Teacher.subjects.any(id=subject_id))

    # Apply sorting
    if sort == "name":
        query = query.order_by(User.full_name.asc())
    elif sort == "newest":
        query = query.order_by(Teacher.id.desc())
    elif sort == "oldest":
        query = query.order_by(Teacher.id.asc())
    else:
        query = query.order_by(User.full_name.asc())

    # Paginate
    paginated = query.paginate(page=page, per_page=per_page)

    # Prepare response data
    teachers_data = []
    for teacher in paginated.items:
        teachers_data.append({
            "id": teacher.id,
            "full_name": teacher.user.full_name,
            "email": teacher.user.email,
            "is_active": teacher.is_active,
            "subjects": [{"id": s.id, "name": s.name} for s in teacher.subjects],
            "classes": [{"id": c.id, "name": c.name} for c in teacher.classes],
            "subject_ids": [s.id for s in teacher.subjects],
            "class_ids": [c.id for c in teacher.classes]
        })

    # Calculate statistics
    total_teachers = Teacher.query.count()
    active_teachers = Teacher.query.filter_by(is_active=True).count()
    inactive_teachers = Teacher.query.filter_by(is_active=False).count()

    # Get unique subjects count
    from sqlalchemy import func
    subject_count = db.session.query(func.count(db.distinct(teacher_subject.c.subject_id))).scalar() or 0

    return jsonify({
        "teachers": teachers_data,
        "pagination": {
            "current_page": paginated.page,
            "total_pages": paginated.pages,
            "total_items": paginated.total,
            "has_prev": paginated.has_prev,
            "has_next": paginated.has_next,
            "prev_num": paginated.prev_num,
            "next_num": paginated.next_num
        },
        "stats": {
            "total": total_teachers,
            "active": active_teachers,
            "inactive": inactive_teachers,
            "total_subjects": subject_count
        }
    })
# ----------------------------------------------------
# 3. ADD TEACHER
# ----------------------------------------------------
@teacher_bp.route("/add", methods=["GET", "POST"])
@login_required
@roles_required("teacher", "admin")
def add_teacher():
    if request.method == "POST":
        full_name = request.form["full_name"]
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        is_active = True if request.form.get("is_active") else False

        # Check duplicate
        if User.query.filter(
            (User.username == username) | (User.email == email)
        ).first():
            flash("Username or email already exists!", "danger")
            return redirect(url_for("teacher_bp.add_teacher"))

        # Create User with role "teacher"
        new_user = User(
            full_name=full_name,
            username=username,
            email=email,
            role="teacher",
            is_active=is_active,
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()  # Get new_user.id

        # Create corresponding Teacher record
        new_teacher = Teacher(user_id=new_user.id)
        db.session.add(new_teacher)

        db.session.commit()
        flash("Teacher added successfully.", "success")
        return redirect(url_for("teacher_bp.manage_teachers"))

    return render_template("teacher/add_teacher.html")
# ----------------------------------------------------
# 4. EDIT TEACHER
# ---------------------------------------------------
@teacher_bp.route("/edit/<int:teacher_id>", methods=["GET", "POST"])
@login_required
@roles_required("teacher", "admin")
def edit_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    subjects = Subject.query.order_by(Subject.name).all()
    classes = Class.query.order_by(Class.name).all()

    if request.method == "POST":
        # Update user info
        user = teacher.user
        user.full_name = request.form.get("full_name")
        user.username = request.form.get("username")
        user.email = request.form.get("email")

        # Update subjects
        selected_subject_ids = request.form.getlist("subject_ids")
        teacher.subjects = (
            Subject.query.filter(Subject.id.in_(selected_subject_ids)).all()
            if selected_subject_ids
            else []
        )

        # Update classes
        selected_class_ids = request.form.getlist("class_ids")
        teacher.classes = (
            Class.query.filter(Class.id.in_(selected_class_ids)).all()
            if selected_class_ids
            else []
        )

        db.session.commit()
        flash(f"{user.full_name} updated successfully!", "success")
        return redirect(url_for("teacher_bp.manage_teachers"))

    return render_template(
        "teacher/edit_teacher.html", teacher=teacher, subjects=subjects, classes=classes
    )


# ----------------------------------------------------
# 5. DELETE TEACHER
# ----------------------------------------------------
@teacher_bp.route("/delete/<int:teacher_id>")
@login_required
@roles_required("teacher", "admin")
def delete_teacher(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    db.session.delete(teacher)
    db.session.commit()
    flash("Teacher deleted successfully.", "success")
    return redirect(url_for("teacher_bp.manage_teachers"))


# ----------------------------------------------------
# 6. ASSIGN SUBJECTS TO TEACHER
# ----------------------------------------------------
@teacher_bp.route("/assign_subjects/<int:teacher_id>", methods=["POST"])
@login_required
@roles_required("teacher", "admin")
def assign_subjects(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    selected_subject_ids = request.form.getlist("subjects")

    # Clear previous assignments
    teacher.subjects = []

    # Assign selected subjects
    for sid in selected_subject_ids:
        subject = Subject.query.get(int(sid))
        if subject:
            teacher.subjects.append(subject)

    db.session.commit()
    flash(f"Subjects updated for {teacher.full_name}.", "success")
    return redirect(url_for("teacher_bp.manage_teachers"))


# -----------------------------------------
# 2. VIEW STUDENTS IN A CLASS
# -----------------------------------------
@teacher_bp.route("/class/<int:class_id>/students")
@login_required
def class_students(class_id):
    the_class = Class.query.get_or_404(class_id)
    if the_class.teacher_id != current_user.id:
        abort(403)

    students = Student.query.filter_by(current_class_id=class_id).all()

    return render_template(
        "teacher/class_students.html",
        the_class=the_class,
        students=students,
    )


# -----------------------------------------
# 3. VIEW SUBJECTS FOR A CLASS (AUTO FILTERED)
# -----------------------------------------
@teacher_bp.route("/class/<int:class_id>/subjects")
@login_required
def class_subjects(class_id):
    the_class = Class.query.get_or_404(class_id)

    subjects = Subject.query.filter_by(
        class_id=class_id, teacher_id=current_user.id
    ).all()

    return render_template(
        "teacher/class_subjects.html",
        the_class=the_class,
        subjects=subjects,
    )


# -----------------------------------------
# 4. ENTER GRADES FOR A CLASS + SUBJECT
# -----------------------------------------
@teacher_bp.route(
    "/class/<int:class_id>/subject/<int:subject_id>/grades", methods=["GET", "POST"]
)
@login_required
def enter_grades(class_id, subject_id):
    the_class = Class.query.get_or_404(class_id)
    subject = Subject.query.get_or_404(subject_id)

    if subject.teacher_id != current_user.id:
        abort(403)

    students = Student.query.filter_by(current_class_id=class_id).all()

    if request.method == "POST":
        term = request.form.get("term")
        year = request.form.get("year", datetime.now().year)

        for student in students:
            mark = request.form.get(f"mark_{student.id}")
            if mark:
                mark = float(mark)

                grade = Grade(
                    student_id=student.id,
                    teacher_id=current_user.id,
                    class_id=class_id,
                    subject_id=subject_id,
                    year=year,
                    term=term,
                    marks=mark,
                    created_at=datetime.utcnow(),
                )
                db.session.add(grade)

        db.session.commit()
        flash("Marks submitted successfully!", "success")
        return redirect(url_for("teacher_bp.teacher_dashboard"))

    return render_template(
        "teacher/enter_grades.html",
        the_class=the_class,
        subject=subject,
        students=students,
        terms=["Term 1", "Term 2", "Term 3"],
    )


# -----------------------------------------
# 5. AJAX: GET STUDENT GRADE HISTORY
# -----------------------------------------
@teacher_bp.route("/student/<int:student_id>/grades")
@login_required
def student_grade_history(student_id):
    grades = (
        Grade.query.filter_by(student_id=student_id)
        .order_by(Grade.year.desc(), Grade.term.desc())
        .all()
    )
    return jsonify(
        [
            {
                "subject": g.subject.name,
                "marks": g.marks,
                "percentage": g.percentage,
                "term": g.term,
                "year": g.year,
                "date": g.created_at.strftime("%Y-%m-%d"),
            }
            for g in grades
        ]
    )


# -----------------------------------------
# 6. TAKE ATTENDANCE FOR A CLASS
# -----------------------------------------
@teacher_bp.route("/attendance")
@login_required
@roles_required("teacher")
def attendance_select_class():
    """Show a list of classes the teacher can take attendance for."""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("auth_bp.login"))

    # Get classes where teacher is either class teacher or subject teacher
    assigned_classes = set()
    # as class teacher
    for cls in Class.query.filter_by(class_teacher_id=teacher.id).all():
        assigned_classes.add(cls)
    # as subject teacher
    for cls in teacher.classes:
        assigned_classes.add(cls)

    return render_template("teacher/select_class_attendance.html", classes=assigned_classes)


@teacher_bp.route("/attendance/<int:class_id>", methods=["GET", "POST"])
@login_required
@roles_required("teacher")
def take_attendance(class_id):
    """Take or edit attendance for a specific class on a given date."""
    cls = Class.query.get_or_404(class_id)
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("auth_bp.login"))

    # Permission check: teacher must be class teacher or subject teacher of this class
    if cls.class_teacher_id != teacher.id and teacher not in cls.subject_teachers:
        abort(403)

    # Get date from query string or default to today
    date_str = request.args.get("date")
    if date_str:
        try:
            att_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            att_date = datetime.utcnow().date()
    else:
        att_date = datetime.utcnow().date()

    students = Student.query.filter_by(current_class_id=class_id).order_by(Student.full_name).all()

    if request.method == "POST":
        # Save attendance for each student
        for student in students:
            status = request.form.get(f"status_{student.id}")
            if status and status in ["Present", "Absent", "Late", "Excused"]:
                # Check if attendance already exists for this student, class, date
                att = Attendance.query.filter_by(
                    student_id=student.id,
                    class_id=class_id,
                    date=att_date
                ).first()
                if att:
                    att.status = status
                    att.updated_at = datetime.utcnow()
                else:
                    att = Attendance(
                        student_id=student.id,
                        class_id=class_id,
                        date=att_date,
                        status=status
                    )
                    db.session.add(att)
            # If status is empty, do nothing (keep as is)
        db.session.commit()
        flash(f"Attendance for {att_date.strftime('%d %b %Y')} saved.", "success")
        return redirect(url_for("teacher_bp.take_attendance", class_id=class_id, date=att_date.strftime("%Y-%m-%d")))

    # GET: load existing attendance for this date
    existing_attendance = {}
    for att in Attendance.query.filter_by(class_id=class_id, date=att_date).all():
        existing_attendance[att.student_id] = att.status
    from datetime import timedelta

    date_prev = att_date - timedelta(days=1)
    date_next = att_date + timedelta(days=1)
    return render_template(
        "teacher/take_attendance.html",
        class_obj=cls,
        students=students,
        date=att_date,
        existing_attendance=existing_attendance,
        date_prev=date_prev.strftime("%Y-%m-%d"),
        date_next=date_next.strftime("%Y-%m-%d")
    )

# -----------------------------------------
# 7. ATTENDANCE REPORT
# -----------------------------------------
@teacher_bp.route("/attendance-report")
@login_required
def attendance_report():
    classes = Class.query.filter_by(teacher_id=current_user.id).all()

    report = []
    for c in classes:
        total = (
            Attendance.query.join(Student)
            .filter(Student.current_class_id == c.id)
            .count()
        )

        absents = (
            Attendance.query.join(Student)
            .filter(Student.current_class_id == c.id, Attendance.status == "Absent")
            .count()
        )

        report.append(
            {
                "class": c,
                "total": total,
                "absents": absents,
                "rate": round((absents / total) * 100, 1) if total else 0,
            }
        )

    return render_template("teacher/attendance_report.html", report=report)


# -----------------------------------------
# 8. VIEW TIMETABLE (OPTIONAL TABLE)
# -----------------------------------------
@teacher_bp.route("/timetable")
@login_required
def teacher_timetable():
    # If you implement a timetable table later, fill this.
    return render_template("teacher/timetable.html")


# -----------------------------------------
# 9. TEACHER PROFILE
# -----------------------------------------
@teacher_bp.route("/profile")
@login_required
@roles_required("teacher")
def profile():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("teacher_bp.teacher_dashboard"))
    return render_template("teacher/teacher_profile.html", teacher=teacher)

# ----------------------------------------------------
def class_teacher_required():
    if not current_user.is_class_teacher():
        abort(403)


# ----------------------------------------------------
# 1. Manage teachers page
# ----------------------------------------------------
@teacher_bp.route("/assignments/<int:class_id>", methods=["GET", "POST"])
@login_required
@roles_required("teacher", "admin")
def assign_teachers(class_id):
    class_ = Class.query.get_or_404(class_id)
    class_teacher_required()

    # Fetch all subjects for this class
    subjects = Subject.query.filter_by(class_id=class_id).all()

    # Fetch all teachers
    teachers = Teacher.query.order_by(Teacher.full_name).all()

    # Fetch existing teacher-subject assignments
    existing_assignments = {
        ts.subject_id: ts.teacher_id
        for ts in TeacherSubject.query.filter_by(class_id=class_id).all()
    }

    if request.method == "POST":
        # Process submitted assignments
        for subject in subjects:
            teacher_id = request.form.get(f"subject_{subject.id}")
            assignment = TeacherSubject.query.filter_by(
                class_id=class_id, subject_id=subject.id
            ).first()
            if teacher_id:
                teacher_id = int(teacher_id)
                if assignment:
                    assignment.teacher_id = teacher_id
                else:
                    assignment = TeacherSubject(
                        class_id=class_id, subject_id=subject.id, teacher_id=teacher_id
                    )
                    db.session.add(assignment)
            else:
                # Remove assignment if teacher not selected
                if assignment:
                    db.session.delete(assignment)

        db.session.commit()
        flash("Teacher assignments updated successfully.", "success")
        return redirect(url_for("teacher_mgmt_bp.assign_teachers", class_id=class_id))

    return render_template(
        "teacher_mgmt/assign_teachers.html",
        class_=class_,
        subjects=subjects,
        teachers=teachers,
        existing_assignments=existing_assignments,
    )


# ----------------------------------------------------
# 1. Manage Teachers
# ----------------------------------------------------


# ----------------------------------------------------
# 2. Add Teacher
# ----------------------------------------------------


@teacher_bp.route("/my_classes")
@login_required
@roles_required("teacher")
def my_classes():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("auth_bp.login"))

    # Combine classes where teacher is class teacher + classes where teacher teaches subjects
    assigned_classes = set()
    # as class teacher
    for cls in Class.query.filter_by(class_teacher_id=teacher.id).all():
        assigned_classes.add(cls)
    # as subject teacher (through many-to-many relationship)
    for cls in teacher.classes:
        assigned_classes.add(cls)

    return render_template("teacher/my_classes.html", classes=assigned_classes)

# Grades
@teacher_bp.route("/grades/add")
@login_required
def add_grade():
    # Load classes and subjects for grade entry
    return render_template("teacher/add_grade.html")


@teacher_bp.route("/grades/view")
@login_required
def manage_grades():
    # View all grades for classes the teacher handles
    grades = Grade.query.filter(Grade.teacher_id == current_user.id).all()
    return render_template("teacher/manage_grades.html", grades=grades)


# Attendance
@teacher_bp.route("/attendance")
@login_required
def attendance_register():
    classes = Class.query.all()
    return render_template(
        "teacher/student_attendance.html", classes=classes, student=Student
    )


# Announcements
@teacher_bp.route("/announcements")
@login_required
def post_announcement():
    announcements = Announcement.query.filter_by(created_at=current_user.id).all()
    return render_template("teacher/announcements.html", announcements=announcements)


@teacher_bp.route("/messages")
@login_required
def messages():
    msgs = (
        Message.query.filter_by(receiver_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )
    return render_template("teacher/messages.html", messages=msgs)


@teacher_bp.route("/message/<int:message_id>")
@login_required
def view_message(message_id):
    msg = Message.query.get_or_404(message_id)

    if msg.receiver_id == current_user.id:
        msg.is_read = True
        db.session.commit()

    return render_template("teacher/view_message.html", message=msg)


@teacher_bp.route("/compose", methods=["GET", "POST"])
@login_required
def compose_message():
    form = MessageForm()

    if form.validate_on_submit():
        # Send to admin by default
        admin = User.query.filter_by(role="admin").first()

        new_msg = Message(
            sender_id=current_user.id,
            receiver_id=admin.id,
            subject=form.subject.data,
            content=form.content.data,
        )
        db.session.add(new_msg)
        db.session.commit()

        flash("Message sent successfully.", "success")
        return redirect(url_for("teacher_bp.messages"))

    return render_template("teacher/compose_message.html", form=form)


@teacher_bp.route("/assignments", methods=["GET", "POST"])
@login_required
def manage_assignments():
    if current_user.role != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("auth_bp.login"))

    # Handle Add/Edit form submission
    if request.method == "POST":
        assignment_id = request.form.get("assignment_id")
        title = request.form.get("title")
        description = request.form.get("description")
        due_date = request.form.get("due_date")

        if not title or not due_date:
            flash("Title and Due Date are required.", "warning")
            return redirect(url_for("teacher_bp.manage_assignments"))

        if assignment_id:  # Editing existing assignment
            assignment = Assignment.query.get_or_404(assignment_id)
            if assignment.teacher_id != current_user.id:
                flash("Access denied.", "danger")
                return redirect(url_for("teacher_bp.manage_assignments"))

            assignment.title = title
            assignment.description = description
            assignment.due_date = due_date
            flash("Assignment updated successfully.", "success")
        else:  # Adding new assignment
            new_assignment = Assignment(
                title=title,
                description=description,
                due_date=due_date,
                teacher_id=current_user.id,
            )
            db.session.add(new_assignment)
            flash("Assignment added successfully.", "success")

        db.session.commit()
        return redirect(url_for("teacher_bp.manage_assignments"))

    # Handle delete via query param
    delete_id = request.args.get("delete_id")
    if delete_id:
        assignment = Assignment.query.get_or_404(delete_id)
        if assignment.teacher_id != current_user.id:
            flash("Access denied.", "danger")
            return redirect(url_for("teacher_bp.manage_assignments"))
        db.session.delete(assignment)
        db.session.commit()
        flash("Assignment deleted successfully.", "success")
        return redirect(url_for("teacher_bp.manage_assignments"))

    assignments = Assignment.query.filter_by(teacher_id=current_user.id).all()
    return render_template("teacher/manage_assignments.html", assignments=assignments)


@teacher_bp.route("/events")
@login_required
def events():
    # Only show events relevant to this teacher's classes (optional)
    teacher_classes = [cls.id for cls in current_user.classes]  # assuming relationship
    events = (
        Event.query.filter(
            (Event.class_id.in_(teacher_classes)) | (Event.is_general == True)
        )
        .order_by(Event.date.asc())
        .all()
    )

    return render_template("events/view.html", events=events)


@teacher_bp.route("/class/<int:class_id>")
@login_required
def class_view(class_id):
    cls = Class.query.get_or_404(class_id)

    # Only allow the class teacher to view the class
    if cls.class_teacher_id != current_user.id:
        abort(403)

    students = cls.students  # relationship from Class → Student

    return render_template("teacher/class_view.html", cls=cls, students=students)


@teacher_bp.route("/announcements")
def announcements():
    q = request.args.get("q", "")
    category = request.args.get("category", "")

    query = Announcement.query.order_by(Announcement.created_at.desc())

    if q:
        query = query.filter(Announcement.title.ilike(f"%{q}%"))

    if category:
        query = query.filter_by(category=category)

    announcements = query.all()

    return render_template("teacher/announcements.html", announcements=announcements)


@teacher_bp.route("/toggle/<int:teacher_id>", methods=["POST"])
@login_required
@roles_required("teacher", "admin")  # optional: only admins can toggle teachers
def toggle_teacher(teacher_id):
    teacher = User.query.filter_by(id=teacher_id, role="teacher").first_or_404()

    # Toggle the is_active field
    teacher.is_active = not teacher.is_active
    db.session.commit()

    status = "activated" if teacher.is_active else "deactivated"
    flash(f"Teacher {teacher.full_name} has been {status}.", "success")

    return redirect(url_for("teacher_bp.manage_teachers"))


@teacher_bp.route("/announcement/<int:announcement_id>")
def view_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    return render_template("teacher/view_announcement.html", announcement=announcement)
# Add to routes/teacher.py or teacher_routes.py

@teacher_bp.route('/grade-entry')
@login_required
@roles_required("teacher")
def grade_entry_dashboard():
    """Show teacher their assigned subjects and classes"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash("Teacher profile not found", "danger")
        return redirect(url_for('dashboard'))

    assignments = []
    for subject in teacher.subjects:
    # Determine the list of classes for this subject
        if subject.class_:
           class_list = [subject.class_]   # single class as a list
        else:
            class_list = teacher.classes     # all classes the teacher teaches

        for class_obj in class_list:
            assignments.append({
            'subject_id': subject.id,
            'subject_name': subject.name,
            'class_id': class_obj.id,
            'class_name': class_obj.name
        })

    return render_template('teacher/grade_dashboard.html', assignments=assignments)

@teacher_bp.route("/api/teachers/<int:teacher_id>/toggle", methods=["POST"])
@login_required
@roles_required("teacher", "admin")
def api_toggle_teacher_status(teacher_id):
    """API endpoint to toggle teacher status in real-time"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        teacher.is_active = not teacher.is_active
        db.session.commit()

        return jsonify({
            "success": True,
            "is_active": teacher.is_active,
            "message": f"Teacher {'activated' if teacher.is_active else 'deactivated'} successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
