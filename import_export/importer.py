"""
Data import functionality for teachers, subjects, and rooms
"""
import pandas as pd
import json
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from models import Teacher, Subject, User
from config import Config

class DataImporter:
    """Import data from various formats"""
    
    def __init__(self, db_session: Session, user: User):
        self.db = db_session
        self.user = user
    
    def import_teachers_from_excel(self, file_path: str) -> Tuple[bool, List[str], List[Teacher]]:
        """Import teachers from Excel file"""
        try:
            df = pd.read_excel(file_path)
            return self._import_teachers_from_dataframe(df)
        except Exception as e:
            return False, [f"Error reading Excel file: {str(e)}"], []
    
    def import_teachers_from_csv(self, file_path: str) -> Tuple[bool, List[str], List[Teacher]]:
        """Import teachers from CSV file"""
        try:
            df = pd.read_csv(file_path)
            return self._import_teachers_from_dataframe(df)
        except Exception as e:
            return False, [f"Error reading CSV file: {str(e)}"], []
    
    def import_teachers_from_json(self, file_path: str) -> Tuple[bool, List[str], List[Teacher]]:
        """Import teachers from JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                return False, ["JSON file must contain a list of teachers"], []
            
            teachers = []
            errors = []
            
            for i, teacher_data in enumerate(data):
                try:
                    teacher = self._create_teacher_from_dict(teacher_data)
                    teachers.append(teacher)
                except Exception as e:
                    errors.append(f"Error processing teacher {i+1}: {str(e)}")
            
            return len(errors) == 0, errors, teachers
            
        except Exception as e:
            return False, [f"Error reading JSON file: {str(e)}"], []
    
    def _import_teachers_from_dataframe(self, df: pd.DataFrame) -> Tuple[bool, List[str], List[Teacher]]:
        """Import teachers from pandas DataFrame"""
        required_columns = ['name', 'email']
        optional_columns = ['phone', 'max_hours_per_day', 'max_hours_per_week', 'can_teach_labs']
        
        # Check required columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return False, [f"Missing required columns: {missing_columns}"], []
        
        teachers = []
        errors = []
        
        for index, row in df.iterrows():
            try:
                teacher_data = {
                    'name': str(row['name']).strip(),
                    'email': str(row['email']).strip(),
                    'phone': str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else None,
                    'max_hours_per_day': int(row.get('max_hours_per_day', 6)),
                    'max_hours_per_week': int(row.get('max_hours_per_week', 30)),
                    'can_teach_labs': bool(row.get('can_teach_labs', False)),
                    'availability': self._parse_availability(row.get('availability', '{}'))
                }
                
                teacher = self._create_teacher_from_dict(teacher_data)
                teachers.append(teacher)
                
            except Exception as e:
                errors.append(f"Error processing row {index+1}: {str(e)}")
        
        return len(errors) == 0, errors, teachers
    
    def _create_teacher_from_dict(self, data: Dict[str, Any]) -> Teacher:
        """Create Teacher object from dictionary"""
        teacher = Teacher(
            name=data['name'],
            email=data.get('email'),
            phone=data.get('phone'),
            max_hours_per_day=data.get('max_hours_per_day', 6),
            max_hours_per_week=data.get('max_hours_per_week', 30),
            can_teach_labs=data.get('can_teach_labs', False),
            availability=data.get('availability', {}),
            user_id=self.user.id
        )
        return teacher
    
    def _parse_availability(self, availability_str: str) -> Dict[str, List[int]]:
        """Parse availability string to dictionary"""
        if isinstance(availability_str, dict):
            return availability_str
        
        try:
            if isinstance(availability_str, str):
                return json.loads(availability_str)
        except:
            pass
        
        # Default availability (all days, all periods)
        return {
            'monday': list(range(1, 10)),
            'tuesday': list(range(1, 10)),
            'wednesday': list(range(1, 10)),
            'thursday': list(range(1, 10)),
            'friday': list(range(1, 10))
        }
    
    def import_subjects_from_excel(self, file_path: str) -> Tuple[bool, List[str], List[Subject]]:
        """Import subjects from Excel file"""
        try:
            df = pd.read_excel(file_path)
            return self._import_subjects_from_dataframe(df)
        except Exception as e:
            return False, [f"Error reading Excel file: {str(e)}"], []
    
    def import_subjects_from_csv(self, file_path: str) -> Tuple[bool, List[str], List[Subject]]:
        """Import subjects from CSV file"""
        try:
            df = pd.read_csv(file_path)
            return self._import_subjects_from_dataframe(df)
        except Exception as e:
            return False, [f"Error reading CSV file: {str(e)}"], []
    
    def _import_subjects_from_dataframe(self, df: pd.DataFrame) -> Tuple[bool, List[str], List[Subject]]:
        """Import subjects from pandas DataFrame"""
        required_columns = ['name', 'code', 'credits', 'subject_type']
        optional_columns = ['description', 'class_size', 'teacher_name']
        
        # Check required columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return False, [f"Missing required columns: {missing_columns}"], []
        
        subjects = []
        errors = []
        
        for index, row in df.iterrows():
            try:
                subject_data = {
                    'name': str(row['name']).strip(),
                    'code': str(row['code']).strip(),
                    'credits': int(row['credits']),
                    'subject_type': str(row['subject_type']).strip().lower(),
                    'description': str(row.get('description', '')).strip() if pd.notna(row.get('description')) else None,
                    'class_size': int(row.get('class_size', 30)),
                    'teacher_name': str(row.get('teacher_name', '')).strip() if pd.notna(row.get('teacher_name')) else None
                }
                
                # Validate subject type
                if subject_data['subject_type'] not in ['theory', 'lab']:
                    raise ValueError(f"Invalid subject type: {subject_data['subject_type']}")
                
                subject = self._create_subject_from_dict(subject_data)
                subjects.append(subject)
                
            except Exception as e:
                errors.append(f"Error processing row {index+1}: {str(e)}")
        
        return len(errors) == 0, errors, subjects
    
    def _create_subject_from_dict(self, data: Dict[str, Any]) -> Subject:
        """Create Subject object from dictionary"""
        subject = Subject(
            name=data['name'],
            code=data['code'],
            credits=data['credits'],
            subject_type=data['subject_type'],
            description=data.get('description'),
            class_size=data.get('class_size', 30),
            user_id=self.user.id
        )
        
        # Assign teacher if specified
        if data.get('teacher_name'):
            teacher = self.db.query(Teacher).filter(
                Teacher.name == data['teacher_name'],
                Teacher.user_id == self.user.id
            ).first()
            if teacher:
                subject.teacher_id = teacher.id
        
        return subject
    
    def save_imported_data(self, teachers: List[Teacher] = None, 
                          subjects: List[Subject] = None) -> Tuple[bool, List[str]]:
        """Save imported data to database"""
        errors = []
        
        try:
            if teachers:
                for teacher in teachers:
                    self.db.add(teacher)
            
            if subjects:
                for subject in subjects:
                    self.db.add(subject)
            
            # Rooms removed
            
            self.db.commit()
            return True, []
            
        except Exception as e:
            self.db.rollback()
            return False, [f"Database error: {str(e)}"]
    
    def get_import_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get templates for import files"""
        return {
            'teachers': {
                'required_columns': ['name', 'email'],
                'optional_columns': ['phone', 'max_hours_per_day', 'max_hours_per_week', 'can_teach_labs', 'availability'],
                'example': {
                    'name': 'Dr. John Smith',
                    'email': 'john.smith@university.edu',
                    'phone': '+1234567890',
                    'max_hours_per_day': 6,
                    'max_hours_per_week': 30,
                    'can_teach_labs': True,
                    'availability': '{"monday": [1,2,3,4,5], "tuesday": [1,2,3,4,5]}'
                }
            },
            'subjects': {
                'required_columns': ['name', 'code', 'credits', 'subject_type'],
                'optional_columns': ['description', 'class_size', 'teacher_name'],
                'example': {
                    'name': 'Data Structures',
                    'code': 'CS201',
                    'credits': 3,
                    'subject_type': 'theory',
                    'description': 'Introduction to data structures',
                    'class_size': 30,
                    'teacher_name': 'Dr. John Smith'
                }
            },
            # Rooms template removed
        }
