"""
Teacher model
"""
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional
from .user import Base

class Teacher(Base):
    """Teacher model"""
    __tablename__ = "teachers"
    
    # Base fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Teacher fields
    teacher_code = Column(String(20), unique=True, index=True, nullable=True) # e.g. BIT001
    salutation = Column(String(10), nullable=True) # Mr., Ms., Dr.
    title: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # Legacy field, maybe sync with salutation?
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    initials: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Verification status for auto-created teacher profiles
    verification_status: Mapped[str] = mapped_column(String(20), default='pending_verification', nullable=False)  # 'pending_verification', 'verified', 'rejected'
    
    # Availability - JSON format: {"monday": [1,2,3], "tuesday": [1,2,3,4]}
    availability = Column(JSON, default=dict)
    
    # Workload constraints
    max_hours_per_day = Column(Integer, default=6)
    max_hours_per_week = Column(Integer, default=30)
    min_hours_per_week = Column(Integer, default=16)  # Minimum weekly hours for multi-timetable
    single_timetable_hours = Column(Integer, default=8)  # Target hours for single timetable
    
    # Lab teaching capability
    can_teach_labs = Column(Boolean, default=False)
    
    # Faculty assignment rules (for validation)
    max_theory_subjects = Column(Integer, default=2)  # Maximum theory subjects per faculty
    max_lab_subjects = Column(Integer, default=1)  # Maximum lab subjects per faculty
    
    # User relationship (for multi-user support)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="teachers", foreign_keys=[user_id])
    
    # Relationships
    subjects = relationship("Subject", back_populates="teacher")
    assignments = relationship("TeacherAssignment", back_populates="teacher", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Teacher(name='{self.name}', initials='{self.initials}', email='{self.email}')>"
    
    def get_available_slots(self, day):
        """Get available time slots for a specific day.
        If no availability is configured (None), treat as fully available (periods 1..9).
        If availability is explicitly set to empty list [], treat as unavailable.
        """
        try:
            avail = self.availability or {}
        except Exception:
            avail = {}
        slots = avail.get(day.lower())
        if slots is None:
            # No availability configured for this day - default to all 9 periods
            return [1,2,3,4,5,6,7,8,9]
        # If slots is explicitly set (even if empty), return it as-is
        return slots
    
    def is_available(self, day, period):
        """Check if teacher is available for a specific day and period"""
        available_slots = self.get_available_slots(day)
        return period in available_slots
    
    def get_total_assigned_hours(self, session, section_id=None):
        """Calculate total assigned hours for this teacher"""
        from .teacher_assignment import TeacherAssignment
        query = session.query(TeacherAssignment).filter(
            TeacherAssignment.teacher_id == self.id
        )
        if section_id is not None:
            query = query.filter(TeacherAssignment.section_id == section_id)
        
        assignments = query.all()
        return sum(a.assigned_hours for a in assignments)
    
    def get_subject_counts(self, session, section_id=None):
        """Get count of theory and lab subjects assigned"""
        from .teacher_assignment import TeacherAssignment
        from .subject import Subject
        
        query = session.query(TeacherAssignment, Subject).join(
            Subject, TeacherAssignment.subject_id == Subject.id
        ).filter(TeacherAssignment.teacher_id == self.id)
        
        if section_id is not None:
            query = query.filter(TeacherAssignment.section_id == section_id)
        
        assignments = query.all()
        theory_count = sum(1 for _, subj in assignments if subj.subject_type == 'theory')
        lab_count = sum(1 for _, subj in assignments if subj.subject_type in ['lab', 'integrated'])
        
        return {'theory': theory_count, 'lab': lab_count}
