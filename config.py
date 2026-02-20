import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tusome-secret-key-2024'
    

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///site.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'another-super-secret-key'

    
    # Application settings
    SCHOOL_NAME = os.environ.get('SCHOOL_NAME') or 'TUSOME Secondary School'
    SCHOOL_ADDRESS = os.environ.get('SCHOOL_ADDRESS') or 'Nairobi, Kenya'
    SCHOOL_PHONE = os.environ.get('SCHOOL_PHONE') or '+254-700-000-000'
    SCHOOL_EMAIL = os.environ.get('SCHOOL_EMAIL') or 'info@tusome.ac.ke'
    
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT= 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'your_email@gmail.com'
    MAIL_PASSWORD= 'your_email_password'
    MAIL_DEFAULT_SENDER = 'your_email@gmail.com'
    # Pagination
    STUDENTS_PER_PAGE = 20
    GRADES_PER_PAGE = 50
    # SMS Configuration (Fill this in with your Africa's Talking API key)
    SMS_API_KEY = 'your_africas_talking_api_key'
    SMS_SENDER_ID = 'TUSOME'
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
