"""
Teacher Assignment model for tracking faculty subject allocations
"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .user import Base

class TeacherAssignment(Base):
    """Tracks which teacher teaches which subject in which section"""
    __tablename__ = "teacher_assignments"
    
    # Base fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Assignment details
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)  # Null for global eligibility
    
    # Assignment metadata
    is_primary = Column(Boolean, default=True)  # Primary teacher for this subject
    is_eligible = Column(Boolean, default=True)  # Teacher is eligible to teach this subject
    assigned_hours = Column(Integer, default=0)  # Weekly hours assigned (updated after generation)
    semester = Column(Integer, nullable=True)  # Semester for this assignment
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="teacher_assignments")
    
    # Relationships
    teacher = relationship("Teacher", back_populates="assignments")
    subject = relationship("Subject", back_populates="assignments")
    section = relationship("Section", back_populates="teacher_assignments")
    
    def __repr__(self):
        return f"<TeacherAssignment(teacher_id={self.teacher_id}, subject_id={self.subject_id}, section_id={self.section_id})>"
