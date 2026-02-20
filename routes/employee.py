from flask import Blueprint, render_template, redirect, url_for, flash, request

from models import Employee

employees_bp = Blueprint("employees", __name__, url_prefix="/employees")


@employees_bp.route("/dashboard")
def dashboard():
    search = request.args.get("search", "")
    role_filter = request.args.get("role", "")
    status_filter = request.args.get("status", "")

    query = Employee.query

    if search:
        query = query.filter(
            or_(
                Employee.first_name.ilike(f"%{search}%"),
                Employee.last_name.ilike(f"%{search}%"),
                Employee.staff_number.ilike(f"%{search}%"),
            )
        )
    if role_filter:
        query = query.filter(Employee.role == role_filter)
    if status_filter:
        if status_filter == "active":
            query = query.filter(Employee.active.is_(True))
        elif status_filter == "inactive":
            query = query.filter(Employee.active.is_(False))

    employees = query.order_by(Employee.first_name).all()
    return render_template(
        "employees/dashboard.html",
        employees=employees,
        search=search,
        role_filter=role_filter,
        status_filter=status_filter,
    )


@employees_bp.route("/create", methods=["GET", "POST"])
def create_employee():
    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        staff_number = request.form.get("staff_number")
        role = request.form.get("role")
        department = request.form.get("department")
        employment_type = request.form.get("employment_type")
        national_id = request.form.get("national_id")

        # 🔒 Validation: required fields
        if not first_name or not last_name or not role or not staff_number:
            flash("Please fill all required fields", "danger")
            return redirect(url_for("employees.create_employee"))

        # 🔒 Prevent duplicate staff number
        exists = Employee.query.filter_by(staff_number=staff_number).first()
        if exists:
            flash("Staff number already exists", "danger")
            return redirect(url_for("employees.create_employee"))

        employee = Employee(
            first_name=first_name,
            last_name=last_name,
            staff_number=staff_number,
            role=role,
            department=department,
            employment_type=employment_type,
            national_id=national_id,
            active=True,
        )

        db.session.add(employee)
        db.session.commit()

        flash("Worker added successfully", "success")
        return redirect(url_for("employees.list_employees"))

    return render_template("employees/create_employee.html")


@employees_bp.route("/<int:employee_id>/toggle", methods=["POST"])
def toggle_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    employee.active = not employee.active
    db.session.commit()

    status = "activated" if employee.active else "deactivated"
    flash(f"Employee {status} successfully.", "success")
    return redirect(url_for("employees.list_employees"))


@employees_bp.route("/<int:employee_id>/edit", methods=["GET", "POST"])
def edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    if employee.salaries:
        flash("Cannot edit employee with existing salaries.", "warning")
        return redirect(url_for("employees.dashboard"))

    if request.method == "POST":
        employee.first_name = request.form.get("first_name")
        employee.last_name = request.form.get("last_name")
        staff_number = request.form.get("staff_number")
        employee.role = request.form.get("role")
        employee.department = request.form.get("department")
        employee.employment_type = request.form.get("employment_type")
        employee.national_id = request.form.get("national_id")

        # Validate required fields
        if (
            not employee.first_name
            or not employee.last_name
            or not staff_number
            or not employee.role
        ):
            flash("Please fill all required fields", "danger")
            return redirect(url_for("employees.edit_employee", employee_id=employee.id))

        # Prevent duplicate staff number
        exists = Employee.query.filter(
            Employee.staff_number == staff_number, Employee.id != employee.id
        ).first()
        if exists:
            flash("Staff number already exists", "danger")
            return redirect(url_for("employees.edit_employee", employee_id=employee.id))

        employee.staff_number = staff_number
        db.session.commit()

        flash("Employee updated successfully", "success")
        return redirect(url_for("employees.list_employees"))

    return render_template("employees/edit_employee.html", employee=employee)


@employees_bp.route("/")
def list_employees():
    employees = Employee.query.order_by(Employee.first_name).all()
    return render_template("employees/list_employees.html", employees=employees)


@employees_bp.route("/<int:employee_id>/profile")
def employee_profile(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    salaries = (
        StaffSalary.query.filter_by(staff_id=employee.id)
        .order_by(StaffSalary.year.desc(), StaffSalary.month.desc())
        .all()
    )
    return render_template(
        "employees/profile.html", employee=employee, salaries=salaries
    )
@employees_bp.route("/audit-logs")
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template("employees/audit_logs.html", logs=logs)