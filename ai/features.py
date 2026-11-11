"""
Feature engineering for the AI-powered scheduler
"""
from typing import List, Dict, Any, Tuple
import numpy as np
from datetime import datetime, time

class FeatureEngineer:
    """Handles feature extraction and engineering for ML models"""
    
    @staticmethod
    def extract_temporal_features(time_slot: Any) -> Dict[str, Any]:
        """Extract temporal features from a time slot"""
        if hasattr(time_slot, 'start_time') and hasattr(time_slot, 'end_time'):
            start = time_slot.start_time
            end = time_slot.end_time
            duration = (end.hour - start.hour) * 60 + (end.minute - start.minute)
            
            return {
                'hour_of_day': start.hour,
                'minute_of_hour': start.minute,
                'day_of_week': start.weekday(),
                'is_morning': 6 <= start.hour < 12,
                'is_afternoon': 12 <= start.hour < 17,
                'is_evening': 17 <= start.hour < 22,
                'duration_minutes': duration,
                'is_peak_hour': (8 <= start.hour < 10) or (14 <= start.hour < 16),
                'is_weekend': start.weekday() >= 5
            }
        return {}
    
    @staticmethod
    def extract_teacher_features(teacher: Any) -> Dict[str, Any]:
        """Extract features related to a teacher"""
        if not teacher:
            return {}
            
        return {
            'teacher_id': getattr(teacher, 'id', None),
            'teacher_seniority': getattr(teacher, 'years_of_service', 0),
            'teacher_preferred_hours': getattr(teacher, 'preferred_hours_per_week', 0),
            'teacher_max_hours_per_day': getattr(teacher, 'max_hours_per_day', 8),
            'teacher_has_restrictions': bool(getattr(teacher, 'unavailable_times', [])),
            'teacher_course_count': len(getattr(teacher, 'courses', [])),
            'teacher_is_part_time': getattr(teacher, 'is_part_time', False)
        }
    
    @staticmethod
    def extract_room_features(room: Any) -> Dict[str, Any]:
        """Extract features related to a room"""
        if not room:
            return {}
            
        return {
            'room_id': getattr(room, 'id', None),
            'room_capacity': getattr(room, 'capacity', 0),
            'room_has_equipment': bool(getattr(room, 'equipment', [])),
            'room_type': getattr(room, 'room_type', 'standard'),
            'room_floor': getattr(room, 'floor', 0),
            'room_building': getattr(room, 'building', 'main')
        }
    
    @staticmethod
    def extract_course_features(course: Any) -> Dict[str, Any]:
        """Extract features related to a course"""
        if not course:
            return {}
            
        return {
            'course_id': getattr(course, 'id', None),
            'course_credits': getattr(course, 'credits', 0),
            'course_level': getattr(course, 'level', 0),
            'is_lab': getattr(course, 'is_lab', False),
            'is_elective': getattr(course, 'is_elective', False),
            'is_core': getattr(course, 'is_core', True),
            'expected_enrollment': getattr(course, 'expected_enrollment', 0),
            'has_prerequisites': bool(getattr(course, 'prerequisites', []))
        }
    
    @staticmethod
    def combine_features(
        time_features: Dict[str, Any],
        teacher_features: Dict[str, Any],
        room_features: Dict[str, Any],
        course_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine all features into a single feature dictionary"""
        features = {}
        
        # Add time features with prefix
        for k, v in time_features.items():
            features[f'time_{k}'] = v
            
        # Add teacher features with prefix
        for k, v in teacher_features.items():
            if v is not None:
                features[f'teacher_{k}'] = v
                
        # Add room features with prefix
        for k, v in room_features.items():
            if v is not None:
                features[f'room_{k}'] = v
                
        # Add course features with prefix
        for k, v in course_features.items():
            if v is not None:
                features[f'course_{k}'] = v
                
        # Add interaction features
        features.update(FeatureEngineer._create_interaction_features(
            time_features, teacher_features, room_features, course_features
        ))
        
        return features
    
    @staticmethod
    def _create_interaction_features(time, teacher, room, course):
        """Create interaction features between different entities"""
        features = {}
        
        # Teacher-time interactions
        if 'hour_of_day' in time and 'teacher_preferred_hours' in teacher:
            features['teacher_preferred_time'] = (
                time['hour_of_day'] >= 8 and 
                time['hour_of_day'] <= teacher['teacher_preferred_hours']
            )
            
        # Room-course interactions
        if 'room_capacity' in room and 'expected_enrollment' in course:
            features['room_suitability'] = (
                room['room_capacity'] >= course['expected_enrollment'] * 1.1  # 10% buffer
            )
            
        # Course-time interactions
        if 'hour_of_day' in time and 'is_lab' in course:
            features['is_lab_time'] = course['is_lab'] and (13 <= time['hour_of_day'] <= 17)
            
        return features
    
    @staticmethod
    def prepare_training_data(assignments: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare training data for ML models
        
        Args:
            assignments: List of assignment dictionaries with 'features' and 'label' keys
            
        Returns:
            Tuple of (features, labels) as numpy arrays
        """
        if not assignments:
            return np.array([]), np.array([])
            
        # Convert list of feature dicts to numpy array
        feature_vectors = []
        labels = []
        
        for assignment in assignments:
            features = assignment.get('features', {})
            label = assignment.get('label')
            
            if features and label is not None:
                feature_vectors.append(list(features.values()))
                labels.append(label)
        
        return np.array(feature_vectors), np.array(labels)
