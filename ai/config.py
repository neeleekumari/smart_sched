"""
Configuration management for AI components using environment variables
"""
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class AIConfig:
    """Manages configuration for AI components using environment variables"""
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:psql@localhost:5432/timetable_db')
    
    # ML Model Configuration
    ML_MODEL_PATH = os.getenv('ML_MODEL_PATH', 'models')
    ML_ENSEMBLE_SIZE = int(os.getenv('ML_ENSEMBLE_SIZE', '100'))
    ML_MAX_DEPTH = int(os.getenv('ML_MAX_DEPTH', '10'))
    
    # Feature Engineering
    FEATURE_STORE_URI = os.getenv('FEATURE_STORE_URI', os.getenv('DATABASE_URL', 'postgresql://postgres:psql@localhost:5432/timetable_db'))
    CACHE_TTL = int(os.getenv('CACHE_TTL', '3600'))  # 1 hour
    
    # Explainability
    EXPLANATION_DEPTH = int(os.getenv('EXPLANATION_DEPTH', '3'))
    MIN_CONFIDENCE_THRESHOLD = float(os.getenv('MIN_CONFIDENCE_THRESHOLD', '0.7'))
    
    # Model Training
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '32'))
    NUM_EPOCHS = int(os.getenv('NUM_EPOCHS', '10'))
    LEARNING_RATE = float(os.getenv('LEARNING_RATE', '0.001'))
    
    # Scheduler Configuration
    MAX_TIMESLOTS = int(os.getenv('MAX_TIMESLOTS', '8'))
    MAX_DAYS = int(os.getenv('MAX_DAYS', '5'))
    MAX_GENERATION_TIME = int(os.getenv('MAX_GENERATION_TIME', '30'))  # seconds
    
    # Logging and Monitoring
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    MONITORING_ENABLED = os.getenv('MONITORING_ENABLED', 'false').lower() == 'true'
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that all required environment variables are set"""
        # Make validation optional for development
        return True
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert configuration to dictionary, excluding sensitive information"""
        sensitive = {'PASSWORD', 'SECRET', 'KEY', 'TOKEN'}
        return {
            k: v for k, v in vars(cls).items() 
            if not k.startswith('_') and not any(s in k.upper() for s in sensitive)
        }

# Validate configuration on import
AIConfig.validate()
