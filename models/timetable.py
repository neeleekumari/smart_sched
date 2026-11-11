"""
Timetable models
"""
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .user import Base

class Timetable(Base):
    """Timetable model - stores entries as JSON data"""
    __tablename__ = "timetables"
    
    # Base fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Timetable fields
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    
    # Timetable structure
    days = Column(JSON, nullable=False, default=list)  # List of days
    periods = Column(JSON, nullable=False, default=list)  # List of periods with times
    timings = Column(JSON, nullable=True, default=dict)  # Period number -> time range mapping
    time_config = Column(JSON, nullable=True, default=dict)  # Store original time configuration
    
    # Entries stored as JSON array (no separate table)
    entries_data = Column(JSON, nullable=False, default=list)  # Array of entry objects
    
    # Generation metadata
    generation_time = Column(DateTime, nullable=True)
    total_subjects = Column(Integer, default=0)
    total_teachers = Column(Integer, default=0)
    total_rooms = Column(Integer, default=0)
    
    # Multi-timetable support
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)  # Null for single timetable
    generation_mode = Column(String(20), default='single')  # 'single' or 'multi'
    conflicts_detected = Column(Integer, default=0)
    workload_validated = Column(Boolean, default=False)

    # Display/owner metadata (persisted per timetable)
    programme_name = Column(String(200), nullable=True)
    term_label = Column(String(200), nullable=True)
    semester = Column(String(20), nullable=True)
    wef_date = Column(String(20), nullable=True)
    class_strength = Column(Integer, nullable=True)
    logo_data_url = Column(Text, nullable=True)
    sections_meta = Column(JSON, nullable=True)
    
    # User relationship (for multi-user support)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="timetables")
    
    # Section relationship
    section = relationship("Section", back_populates="timetables")
    
    def __repr__(self):
        return f"<Timetable(name='{self.name}', version={self.version})>"
    
    @property
    def entries(self):
        """Return entries from JSON data for compatibility"""
        return self.entries_data or []
    
    def get_entries_for_day(self, day):
        """Get all entries for a specific day"""
        return [entry for entry in self.entries if entry.get('day') == day]
    
    def get_entries_for_period(self, day, period):
        """Get entry for a specific day and period"""
        for entry in self.entries:
            if entry.get('day') == day and entry.get('period') == period:
                return entry
        return None
