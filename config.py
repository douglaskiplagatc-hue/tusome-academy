import os
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tusome-secret-key-2024'
    SECURITY_PASSWORD_SALT = os.environ.get('SECURITY_PASSWORD_SALT') or 'password-reset-salt'
    FLASK_ENV = os.environ.get("FLASK_ENV") or "development"

    # Database configuration
    raw_database_url = os.environ.get('DATABASE_URL')
    if raw_database_url and raw_database_url.startswith('postgresql'):
        # Ensure sslmode=require for PostgreSQL
        parsed = urlparse(raw_database_url)
        if parsed.query:
            parsed = parsed._replace(query=parsed.query + '&sslmode=require')
        else:
            parsed = parsed._replace(query='sslmode=require')
        SQLALCHEMY_DATABASE_URI = urlunparse(parsed)
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 3600,
            'connect_args': {'sslmode': 'require'}
        }
    else:
        SQLALCHEMY_DATABASE_URI = raw_database_url or 'sqlite:///site.db'
        SQLALCHEMY_ENGINE_OPTIONS = {}

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail configuration (Mailtrap for development)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'sandbox.smtp.mailtrap.io')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 2525))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '814b4d08f495d6')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '8abfe28b4081fb')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@tusome.com')

    # JWT (if used elsewhere)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'another-super-secret-key'

    # Application settings
    SCHOOL_NAME = os.environ.get('SCHOOL_NAME') or 'TUSOME Secondary School'
    SCHOOL_ADDRESS = os.environ.get('SCHOOL_ADDRESS') or 'Nairobi, Kenya'
    SCHOOL_PHONE = os.environ.get('SCHOOL_PHONE') or '+254-700-000-000'
    SCHOOL_EMAIL = os.environ.get('SCHOOL_EMAIL') or 'info@tusome.ac.ke'
    SCHOOL_TYPE = os.environ.get('SCHOOL_TYPE', 'primary')
    SCHOOL_LEVELS = {
        'primary': [1, 2, 3, 4, 5, 6],
        'junior': [7, 8, 9],
        'senior': [10, 11, 12],
        'full': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    }

    # Pagination
    STUDENTS_PER_PAGE = 20
    GRADES_PER_PAGE = 50

    # SMS Configuration (Africa's Talking)
    SMS_API_KEY = os.environ.get('SMS_API_KEY', 'your_africas_talking_api_key')
    SMS_SENDER_ID = os.environ.get('SMS_SENDER_ID', 'TUSOME')

    # File uploads
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico'}

    # Debug: print DATABASE_URL (optional, remove in production)
    print("DATABASE_URL from env:", os.environ.get('DATABASE_URL'))
