"""
Section model for multi-timetable support
"""
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .user import Base

class Section(Base):
    """Section/Class model - represents different sections that need separate timetables"""
    __tablename__ = "sections"
    
    # Base fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Section details
    name = Column(String(100), nullable=False)  # e.g., "Section A", "Class 1-B"
    semester = Column(String(20), nullable=True)  # e.g., "1", "2", "3"
    programme = Column(String(200), nullable=True)  # e.g., "Computer Science"
    class_strength = Column(Integer, default=30)
    lecture_hall = Column(String(100), nullable=True)  # Assigned hall
    class_teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    
    # User relationship (for multi-user support)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="sections")
    
    # Relationships
    class_teacher = relationship("Teacher", foreign_keys=[class_teacher_id])
    timetables = relationship("Timetable", back_populates="section")
    teacher_assignments = relationship("TeacherAssignment", back_populates="section", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Section(name='{self.name}', semester='{self.semester}', programme='{self.programme}')>"
