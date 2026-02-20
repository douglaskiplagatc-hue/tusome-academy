from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import FeePayment, FeeStatement, Student, User, StaffSalary
from sqlalchemy import func
from datetime import datetime

dashboard_bp = Blueprint("dashboard_bp", __name__, url_prefix="/dashboard")
