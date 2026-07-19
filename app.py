# app.py
from flask import Flask, redirect, url_for, request
from datetime import datetime
from extensions import db, login_manager, migrate, mail
from config import Config
from routes.__init__ import register_blueprints
from flask.cli import with_appcontext
import click
from models import Subject, User, SchoolProfile, SystemSetting
from flask_login import LoginManager
import os
import logging
from routes.reports import reports_bp

from services.reports.ncbe import marks_to_ncbe
from flask_wtf.csrf import CSRFProtect
from services.sms import sms_service
from services.email import mail
from scheduler import init_scheduler
from dotenv import load_dotenv
from flask_mail import Mail
from config import Config
from werkzeug.security import generate_password_hash
from sqlalchemy import text
mail = Mail()
csrf = CSRFProtect()
load_dotenv()
login_manager = LoginManager()
login_manager.login_view = "auth_bp.login"


@login_manager.user_loader
def load_user(user_id):
    """Given *user_id*, return the corresponding User object."""
    # Flask-Login expects a string, so we convert it to an integer
    return User.query.get(int(user_id))


# -------------------- App Factory -------------------- #
def create_app():
    app = Flask(__name__)

    # Load Config
    app.config.from_object(Config)

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'   # or 'Strict' if you prefer
    app.jinja_env.globals.update(marks_to_ncbe=marks_to_ncbe)
    csrf.init_app(app)
    csrf.exempt(reports_bp)  # Initialize extensions
    db.init_app(app)

    login_manager.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        db.create_all()

    sms_service.init_app(app)
    mail.init_app(app)
    login_manager.login_view = "auth_bp.login"

    @app.route("/update-schema")
    def update_schema():
        # Only run if schema update hasn't been done before
        if os.environ.get("SCHEMA_UPDATED"):
            return "Schema already updated."
        try:
            # Add school_id to system_settings (the table causing the error)
            db.session.execute(
                text(
                    "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS school_id INTEGER REFERENCES school_profiles(id)"
                )
            )
            # Add other missing columns similarly (repeat for other tables)
            db.session.commit()
            os.environ["SCHEMA_UPDATED"] = "true"
            return "Schema updated successfully."
        except Exception as e:
            return f"Error: {e}"

    @app.route("/debug-all")
    def debug_all():
        from extensions import db
        from sqlalchemy import inspect, text
        import traceback

        output = "<h1>Database Contents</h1>"
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            for table in tables:
                output += f"<h2>Table: {table}</h2>"
                columns = [col["name"] for col in inspector.get_columns(table)]
                output += "<table border='1' cellpadding='5'>"
                output += (
                    "</td>" + "".join(f"<th>{c}</th>" for c in columns) + "</table>"
                )

                # Use text() and quote table name (PostgreSQL is case‑sensitive)
                query = text(f'SELECT * FROM "{table}"')
                result = db.session.execute(query).fetchall()
                for row in result:
                    output += "<tr>"
                    for col in columns:
                        val = getattr(row, col)
                        if isinstance(val, str) and len(val) > 50:
                            val = val[:50] + "..."
                        output += f"<td>{val}</td>"
                    output += "</tr>"
                output += "</table><br><br>"
        except Exception as e:
            output += (
                f"<pre style='color:red'>Error: {e}\n{traceback.format_exc()}</pre>"
            )
        return output

    @app.template_filter('intcomma')
    def intcomma_filter(value):
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return value
    @app.context_processor
    def inject_school_settings():
        """Inject school profile settings into all templates - Fully dynamic from database"""

        # Get school profile from database (creates default if doesn't exist)
        profile = SchoolProfile.query.first()
        if not profile:
            # Create default profile with placeholder values
            profile = SchoolProfile()
            profile.school_name = "School Name Not Set"
            profile.motto = "School Motto Not Set"
            profile.school_vision = (
                "School Vision Not Set. Please configure in Settings."
            )
            profile.school_mission = (
                "School Mission Not Set. Please configure in Settings."
            )
            db.session.add(profile)
            db.session.commit()

        # Get additional system settings
        def get_setting(key, default=""):
            setting = SystemSetting.query.filter_by(key=key).first()
            if setting:
                return setting.get_value()
            return default

        # Return ALL school settings (no hardcoded defaults)
        return {
            # School Profile
            "school_name": profile.school_name,
            "school_motto": profile.motto,
            "school_vision": profile.school_vision,
            "school_mission": profile.school_mission,
            "school_phone": profile.phone or "",
            "school_email": profile.email or "",
            "school_address": profile.address or "",
            "school_website": profile.website or "",
            "school_logo": profile.logo_url,
            "school_favicon": profile.favicon_url,
            "school_level": profile.school_level or "junior_secondary",
            "established_year": profile.established_year,
            "principal_name": profile.principal_name,
            "school_code": profile.school_code,
            "primary_color": profile.primary_color or "#006B3F",
            "secondary_color": profile.secondary_color or "#0047AB",
            # Social Media
            "social_facebook": profile.social_facebook,
            "social_twitter": profile.social_twitter,
            "social_instagram": profile.social_instagram,
            "social_linkedin": profile.social_linkedin,
            "social_youtube": profile.social_youtube,
            # System Settings (from SystemSetting table)
            "current_term": get_setting("current_term", "1"),
            "current_academic_year": get_setting(
                "current_academic_year", str(datetime.now().year)
            ),
            "term_start_date": get_setting("term_start_date", ""),
            "term_end_date": get_setting("term_end_date", ""),
            "enable_parent_portal": get_setting("enable_parent_portal", True),
            "enable_student_portal": get_setting("enable_student_portal", True),
        }

    @app.context_processor
    def inject_now():
        """Inject current datetime into templates"""
        return {"now": datetime.now()}

    @app.context_processor
    def inject_current_date():
        """Inject current date into templates"""
        return {"current_date": datetime.now()}

    # ============== ROUTES ==============

    @app.route("/")
    def index():
        return redirect(url_for("auth_bp.login"))

    # ============== REGISTER BLUEPRINTS ==============
    register_blueprints(app)

    # ============== CLI COMMANDS ==============
    register_cli(app)

    # ============== SCHEDULER ==============
    init_scheduler(app)

    return app


# -------------------- CLI Commands -------------------- #
def register_cli(app):
    @app.cli.command("seed_subjects")
    @with_appcontext
    def seed_subjects():
        """Seed CBC subjects into the database."""
        cbc_subjects = [
            ("English Activities", "ENGA", "Primary", True),
            ("Kiswahili", "KISW", "Primary", True),
            ("Environmental Activities", "ENV", "Primary", True),
            ("Mathematics", "MATH", "Primary", True),
            ("CRE", "CRE", "Primary", True),
            ("IRE", "IRE", "Primary", True),
            ("HRE", "HRE", "Primary", True),
            ("Creative Activities", "CREA", "Primary", True),
            ("English", "ENG", "Junior Secondary", True),
            ("Kiswahili", "KISW", "Junior Secondary", True),
            ("Kenya Sign Language", "KSL", "Junior Secondary", False),
            ("Mathematics", "MATH", "Junior Secondary", True),
            ("Integrated Science", "INTEGSCI", "Junior Secondary", True),
            ("Social Studies", "SST", "Junior Secondary", True),
            ("Business Studies", "BST", "Junior Secondary", False),
            ("Agriculture", "AGRI", "Junior Secondary", False),
            ("Pre-Technical & Career Studies", "PTCS", "Junior Secondary", True),
            ("CRE", "CRE", "Junior Secondary", True),
            ("IRE", "IRE", "Junior Secondary", True),
            ("HRE", "HRE", "Junior Secondary", True),
            ("Visual & Performing Arts", "VAPA", "Junior Secondary", False),
            ("Computer Science", "COMP", "Junior Secondary", False),
        ]

        added = 0
        for name, code, level, compulsory in cbc_subjects:
            existing = Subject.query.filter_by(code=code).first()
            if existing:
                existing.name = name
                existing.level = level
                existing.compulsory = compulsory
            else:
                db.session.add(
                    Subject(name=name, code=code, level=level, compulsory=compulsory)
                )
                added += 1
        db.session.commit()
        click.echo(f"✅ Seed complete! {added} subjects added or updated.")

    @app.cli.command("init_settings")
    @with_appcontext
    def init_settings():
        """Initialize system settings and school profile."""
        from utils.init_settings import initialize_system_settings

        initialize_system_settings()
        click.echo("✅ System settings initialized!")


# -------------------- App Runner -------------------- #
app = create_app()



if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    # Uncomment if you want to use livereload
    # server = Server(app.wsgi_app)

    # Standard Flask run
    app.run(debug=True, host="127.0.0.1", port=5500)
