import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database with connection pooling and optimization
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://gpu_user:password@localhost:5432/gpu_priorities')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 0,
        'pool_size': 10,
        'connect_args': {
            'connect_timeout': 10,
            'application_name': 'gpu_priority_service'
        }
    }

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # OIDC Configuration (using Authlib)
    OIDC_CLIENT_ID = os.getenv('OIDC_CLIENT_ID')
    OIDC_CLIENT_SECRET = os.getenv('OIDC_CLIENT_SECRET')
    OIDC_DISCOVERY_URL = os.getenv('OIDC_DISCOVERY_URL')

    # Email Configuration with timeouts
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'gpu-priorities@localhost')
    MAIL_MAX_EMAILS = 10
    MAIL_SUPPRESS_SEND = os.getenv('MAIL_SUPPRESS_SEND', 'False').lower() == 'true'
    MAIL_ASCII_ATTACHMENTS = False

    # Application Settings
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@localhost')

    # Security
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    # Performance
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year for static files
    JSON_SORT_KEYS = False  # Faster JSON serialization

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
