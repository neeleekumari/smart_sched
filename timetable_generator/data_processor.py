"""
Data processing utilities for timetable generation
"""
from typing import List, Dict, Any, Tuple
import pandas as pd
from models import Teacher, Subject, User
from config import Config

class DataProcessor:
    """Processes and validates data for timetable generation"""
    
    def __init__(self, user: User):
        self.user = user
    
    def validate_teachers(self, teachers: List[Teacher]) -> Tuple[bool, List[str]]:
        """Validate teacher data"""
        errors = []
        
        for teacher in teachers:
            if not teacher.name:
                errors.append(f"Teacher {teacher.id} has no name")
            
            if teacher.max_hours_per_week <= 0:
                errors.append(f"Teacher {teacher.name} has invalid max hours per week")
            
            if teacher.max_hours_per_day <= 0:
                errors.append(f"Teacher {teacher.name} has invalid max hours per day")
        
        return len(errors) == 0, errors
    
    def validate_subjects(self, subjects: List[Subject]) -> Tuple[bool, List[str]]:
        """Validate subject data"""
        errors = []
        
        for subject in subjects:
            if not subject.name:
                errors.append(f"Subject {subject.id} has no name")
            
            if not subject.code:
                errors.append(f"Subject {subject.name} has no code")
            
            if subject.credits < 0:
                errors.append(f"Subject {subject.name} has invalid credits")
            
            # Allow a wider set of types or treat unknown as theory for generation
            if subject.subject_type not in ['theory', 'lab', 'integrated', 'none', None, '']:
                errors.append(f"Subject {subject.name} has invalid type")
            
            if subject.class_size <= 0:
                errors.append(f"Subject {subject.name} has invalid class size")
        
        return len(errors) == 0, errors
    
    def check_teacher_subject_assignments(self, teachers: List[Teacher], subjects: List[Subject]) -> Tuple[bool, List[str]]:
        """Check if all subjects have assigned teachers"""
        errors = []
        
        for subject in subjects:
            # Allow subject without assigned teacher; generator will attempt assignment
            if subject.teacher is not None and subject.teacher not in teachers:
                errors.append(f"Subject {subject.name} assigned to teacher not in the system")
        
        return len(errors) == 0, errors
    
    # Rooms removed: skip room capacity checks
    
    def calculate_workload(self, teachers: List[Teacher], subjects: List[Subject]) -> Dict[int, int]:
        """Calculate workload for each teacher"""
        workload = {}
        
        for teacher in teachers:
            teacher_subjects = [s for s in subjects if s.teacher_id == teacher.id]
            total_hours = sum(s.credits for s in teacher_subjects)
            workload[teacher.id] = total_hours
        
        return workload
    
    def check_workload_constraints(self, teachers: List[Teacher], subjects: List[Subject]) -> Tuple[bool, List[str]]:
        """Check if teacher workloads are within constraints"""
        errors = []
        workload = self.calculate_workload(teachers, subjects)
        
        for teacher in teachers:
            if teacher.id in workload:
                if workload[teacher.id] > teacher.max_hours_per_week:
                    errors.append(f"Teacher {teacher.name} workload {workload[teacher.id]} exceeds max {teacher.max_hours_per_week}")
        
        return len(errors) == 0, errors
    
    def get_lab_subjects(self, subjects: List[Subject]) -> List[Subject]:
        """Get all lab subjects"""
        return [s for s in subjects if s.is_lab]
    
    def get_theory_subjects(self, subjects: List[Subject]) -> List[Subject]:
        """Get all theory subjects"""
        return [s for s in subjects if not s.is_lab]
    
