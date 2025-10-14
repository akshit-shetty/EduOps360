"""
Configuration file for EduOps360
Centralized configuration management
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""
    
    # Flask Configuration
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    SESSION_TYPE = 'filesystem'
    SESSION_TIMEOUT_HOURS = int(os.getenv('SESSION_TIMEOUT_HOURS', 24))
    
    # Database Configuration - SQLite
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'eduops360.db')
    
    # Email Configuration (Office 365)
    SMTP_SERVER = os.getenv('EMAIL_SMTP_SERVER', 'smtp-mail.outlook.com')
    SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('EMAIL_ADDRESS', '')
    SMTP_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
    NOREPLY_EMAIL = os.getenv('NOREPLY_EMAIL', 'noreply@eduops360.com')
    NOREPLY_NAME = os.getenv('NOREPLY_NAME', 'EduOps360 System')
    
    # OTP Configuration
    OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', 10))
    OTP_LENGTH = int(os.getenv('OTP_LENGTH', 6))
    
    # Application Constants
    LOW_GRADES = ['C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'IF', 'I']
    COURSE_COLUMNS = [
        'DBA 805 Grade', 'DBA 806 / DBA 808 Grade', 'DBA 863 Grade',
        'DBA 860 Grade', 'DBA 861 Grade', 'DBA 862 Grade', 'DBA 864 Grade'
    ]
    ACTIVE_STATUSES = ['Active', 'Active / Deferred In', 'Active (Prospective Deferral)']

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(env='default'):
    """Get configuration based on environment"""
    return config.get(env, config['default'])
