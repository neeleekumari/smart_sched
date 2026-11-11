"""
Configuration settings for the AI Timetable Generator
"""
import os
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()

class Config:
    """Base configuration class"""
    
    # Database settings
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:psql@localhost:5432/timetable_db')
    # Security settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    
    # Teacher Email Domain Verification
    TEACHER_EMAIL_DOMAIN = os.getenv('TEACHER_EMAIL_DOMAIN', '@college.ac.in')
    
    # Application settings
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('HOST', 'localhost')
    PORT = int(os.getenv('PORT', 8000))
    
    # Timetable settings
    DEFAULT_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    DEFAULT_PERIODS = [
        '9:00-10:00', '10:00-11:00', '11:00-11:15',  # Short break
        '11:15-12:15', '12:15-1:15', '1:15-2:15',    # Lunch break
        '2:15-3:15', '3:15-4:15', '4:15-5:15'
    ]
    
    # Lab settings
    LAB_HOURS_PER_WEEK = 4
    LAB_BLOCK_DURATION = 2  # 2-hour blocks for labs
    
    # Export settings
    EXPORT_DIR = os.getenv('EXPORT_DIR', 'exports')
    MAX_EXPORT_FILES = 100

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False

class TestingConfig(Config):
    """Testing configuration"""
    DATABASE_URL = 'postgresql://<your_username>:<your_password>@localhost/timetable_test_db'
    TESTING = True

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
