# app.py
from flask import Flask, redirect, url_for
from datetime import datetime
from extensions import db, login_manager, migrate, mail
from config import Config
from routes.__init__ import register_blueprints
from flask.cli import with_appcontext
import click
from models import Subject, User
from flask_login import LoginManager
from livereload import Server
from template_debugger import debug_template_context

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
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "your-secret-key"

    # Initialize Extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    login_manager.login_view = "auth_bp.login"

    # Add `now` to Jinja templates
    @app.context_processor
    def inject_now():
        return {"now": datetime.now()}

    # ✅ New: Add a root route to redirect to the login page
    @app.route("/")
    def index():
        return redirect(url_for("auth_bp.login"))

    # Register Blueprints
    # ... (rest of the function) ...

    # Register Blueprints
    register_blueprints(app)

    # Register CLI Commands
    register_cli(app)

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


# -------------------- App Runner -------------------- #
app = create_app()
if app.debug:
    debug_template_context(app)
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    server = Server(app.wsgi_app)
    server.watch("templates/")  # Watch HTML files
    server.watch("static/")  # Watch CSS/JS files
    server.serve(port=5500, host="127.0.0.1", debug=True)
