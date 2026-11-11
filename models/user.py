"""
User model for authentication and data isolation
"""
from sqlalchemy import Column, String, Boolean, Integer, DateTime
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

# Shared Base for all models
Base = declarative_base()

class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    # Base fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # User fields
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    role = Column(String(20), default='user', nullable=False)  # 'user', 'teacher', 'admin'
    
    # Institute details (for Admins)
    institute_name = Column(String(200), nullable=True)
    institute_code = Column(String(20), nullable=True)
    
    # Relationships
    teachers = relationship("Teacher", back_populates="user", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="user", cascade="all, delete-orphan")
    timetables = relationship("Timetable", back_populates="user", cascade="all, delete-orphan")
    sections = relationship("Section", back_populates="user", cascade="all, delete-orphan")
    teacher_assignments = relationship("TeacherAssignment", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"
