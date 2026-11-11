"""
Database models for the AI Timetable Generator
"""
from .user import Base, User
from .teacher import Teacher
from .subject import Subject
from .timetable import Timetable
from .section import Section
from .teacher_assignment import TeacherAssignment
from .allowed_domain import AllowedDomain

__all__ = [
    'Base',
    'User',
    'Teacher',
    'Subject',
    'Timetable',
    'Section',
    'TeacherAssignment',
    'AllowedDomain'
]
