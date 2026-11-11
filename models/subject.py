"""
Subject model
"""
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .user import Base

class Subject(Base):
    """Subject model"""
    __tablename__ = "subjects"
    
    # Base fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Subject fields
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    credits = Column(Integer, nullable=False)
    subject_type = Column(String(20), nullable=False)  # 'theory', 'lab', or 'integrated'
    abbreviation = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    
    # Class size for capacity planning
    class_size = Column(Integer, default=30)
    
    # User relationship (for multi-user support)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="subjects")
    
    # Teacher assignment (legacy - for backward compatibility with single teacher)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    teacher = relationship("Teacher", back_populates="subjects")
    
    # Multi-teacher assignments (NEW: supports multiple teachers per subject)
    assignments = relationship("TeacherAssignment", back_populates="subject", cascade="all, delete-orphan")
    
    def get_eligible_teachers(self, db_session):
        """Get all teachers eligible to teach this subject (from assignments)"""
        from models.teacher_assignment import TeacherAssignment
        assignments = db_session.query(TeacherAssignment).filter(
            TeacherAssignment.subject_id == self.id,
            TeacherAssignment.section_id == None  # Global assignments (not section-specific)
        ).all()
        
        # If no assignments exist, fall back to legacy teacher_id
        if not assignments and self.teacher_id:
            from models.teacher import Teacher
            teacher = db_session.query(Teacher).filter(Teacher.id == self.teacher_id).first()
            return [teacher] if teacher else []
        
        return [a.teacher for a in assignments if a.teacher]
    
    # Semester assignment
    semester = Column(String(20), nullable=True)  # e.g., "1", "2", "3", "4", "5", "6", "7", "8"
    
    def __repr__(self):
        return f"<Subject(name='{self.name}', code='{self.code}', credits={self.credits})>"
    
    @property
    def is_lab(self):
        """Check if subject is a lab"""
        return self.subject_type.lower() == 'lab'
    
    @property
    def is_integrated(self):
        """Check if subject is integrated (has both theory and lab components)"""
        return self.subject_type.lower() == 'integrated'
    
    @property
    def weekly_hours(self):
        """Get weekly hours based on credits or minimum default for 0-credit courses"""
        if self.credits > 0:
            return self.credits
        return self.get_theory_hours() + self.get_lab_hours()
    
    def get_theory_hours(self) -> int:
        """
        Calculate theory hours for this subject based on subject type.
        
        Returns:
            int: Number of theory hours per week
                - For 'theory' subjects: returns credits (or 2 if 0-credit)
                - For 'integrated' subjects: returns credits minus 2 (or 2 if <=2 credits)
                - For 'lab' subjects: returns 0
        """
        stype = (self.subject_type or 'theory').lower()
        if stype == 'theory':
            return self.credits if self.credits > 0 else 2
        elif stype == 'integrated':
            return max(1, self.credits - 2) if self.credits > 2 else 2
        return 0
    
    def get_lab_hours(self) -> int:
        """
        Calculate lab hours for this subject.
        
        Returns:
            int: Number of lab hours per week
                - For 'lab' or 'integrated' subjects: returns 2 (one 2-hour lab block)
                - For 'theory' subjects: returns 0
        """
        stype = (self.subject_type or 'theory').lower()
        if stype in ['lab', 'integrated']:
            return 2
        return 0
    
    def requires_lab_block(self) -> bool:
        """
        Check if subject needs a lab block (2 consecutive slots).
        
        Returns:
            bool: True if subject is 'lab' or 'integrated', False otherwise
        """
        stype = (self.subject_type or 'theory').lower()
        return stype in ['lab', 'integrated']
    
    def get_required_lab_blocks(self):
        """Get required lab blocks per week (1 block of 2 consecutive hours)"""
        if self.requires_lab_block():
            return 1  # 1 block of 2 hours
        return 0
    
    def is_theory_subject(self):
        """Check if subject is pure theory"""
        return (self.subject_type or 'theory').lower() == 'theory'
    
    def is_lab_subject(self):
        """Check if subject has lab component (lab or integrated)"""
        return (self.subject_type or 'theory').lower() in ['lab', 'integrated']
