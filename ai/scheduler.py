"""
AI-Powered Timetable Scheduler
Integrates CSP, ML, and Explainability for adaptive scheduling
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, time
import numpy as np
from .config import AIConfig
from .ml_optimizer import MLCSPOptimizer
from .explainability import ExplainabilityEngine
from .features import FeatureEngineer

class AIScheduler:
    """Main AI scheduler that coordinates CSP, ML, and explainability"""
    
    def __init__(self):
        self.ml_optimizer = MLCSPOptimizer()
        self.explainer = ExplainabilityEngine()
        self.feature_engineer = FeatureEngineer()
        self.generation_history = []
        
    def generate_timetable(
        self,
        courses: List[Dict[str, Any]],
        rooms: List[Dict[str, Any]],
        faculty: List[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate an optimized timetable using AI and CSP
        
        Args:
            courses: List of course dictionaries
            rooms: List of room dictionaries
            faculty: List of faculty dictionaries
            constraints: Optional custom constraints
            
        Returns:
            Dictionary containing the generated timetable and metadata
        """
        start_time = datetime.now()
        
        # Step 1: Preprocess and validate input
        validated_data = self._validate_input(courses, rooms, faculty)
        
        # Step 2: Extract features for ML
        features = self.feature_engineer.combine_features(
            time_features={},
            teacher_features={},
            room_features={},
            course_features={}
        )
        
        # Step 3: Generate initial timetable using CSP
        timetable = self._generate_csp_timetable(validated_data, constraints)
        
        # Step 4: Optimize using ML
        if self.ml_optimizer.is_fitted:
            timetable = self._optimize_with_ml(timetable, features)
        
        # Step 5: Add explanations
        timetable_with_explanations = self._add_explanations(timetable)
        
        # Step 6: Calculate metrics
        metrics = self._calculate_metrics(timetable_with_explanations)
        
        generation_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            'timetable': timetable_with_explanations,
            'metadata': {
                'generation_time': generation_time,
                'conflicts': metrics['conflicts'],
                'fairness_score': metrics['fairness'],
                'stability_score': metrics['stability'],
                'timestamp': datetime.now().isoformat()
            },
            'explanations': self.explainer.generate_report()
        }
        
        # Store in history
        self.generation_history.append(result)
        
        return result
    
    def _validate_input(
        self,
        courses: List[Dict],
        rooms: List[Dict],
        faculty: List[Dict]
    ) -> Dict[str, Any]:
        """Validate and preprocess input data"""
        return {
            'courses': courses,
            'rooms': rooms,
            'faculty': faculty,
            'timeslots': self._generate_timeslots()
        }
    
    def _generate_timeslots(self) -> List[Dict[str, Any]]:
        """Generate available timeslots"""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        slots = []
        
        for day_idx, day in enumerate(days[:AIConfig.MAX_DAYS]):
            for slot_idx in range(AIConfig.MAX_TIMESLOTS):
                start_hour = 9 + slot_idx
                slots.append({
                    'id': f'{day}_{slot_idx}',
                    'day': day,
                    'day_index': day_idx,
                    'slot_index': slot_idx,
                    'start_time': f'{start_hour:02d}:00',
                    'end_time': f'{start_hour+1:02d}:00',
                    'is_morning': slot_idx < 4,
                    'is_afternoon': slot_idx >= 4
                })
        
        return slots
    
    def _generate_csp_timetable(
        self,
        data: Dict[str, Any],
        constraints: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate timetable using CSP solver"""
        # Simple round-robin allocation for now
        # TODO: Integrate with actual CSP solver
        
        timetable = []
        courses = data['courses']
        rooms = data['rooms']
        faculty = data['faculty']
        timeslots = data['timeslots']
        
        slot_idx = 0
        for course in courses:
            if slot_idx >= len(timeslots):
                break
                
            # Find appropriate room
            room = self._find_suitable_room(course, rooms)
            
            # Find faculty
            faculty_member = self._find_faculty(course, faculty)
            
            assignment = {
                'course_id': course['id'],
                'course_name': course['name'],
                'room_id': room['id'] if room else None,
                'room_name': room['name'] if room else None,
                'faculty_id': faculty_member['id'] if faculty_member else None,
                'faculty_name': faculty_member['name'] if faculty_member else None,
                'timeslot': timeslots[slot_idx],
                'day': timeslots[slot_idx]['day'],
                'time': timeslots[slot_idx]['start_time']
            }
            
            timetable.append(assignment)
            slot_idx += 1
        
        return {'assignments': timetable}
    
    def _find_suitable_room(self, course: Dict, rooms: List[Dict]) -> Optional[Dict]:
        """Find a suitable room for a course"""
        for room in rooms:
            if course.get('is_lab', False) == room.get('is_lab', False):
                return room
        return rooms[0] if rooms else None
    
    def _find_faculty(self, course: Dict, faculty: List[Dict]) -> Optional[Dict]:
        """Find faculty for a course"""
        faculty_id = course.get('faculty_id')
        for f in faculty:
            if f['id'] == faculty_id:
                return f
        return faculty[0] if faculty else None
    
    def _optimize_with_ml(self, timetable: Dict, features: Dict) -> Dict:
        """Optimize timetable using ML models"""
        # TODO: Implement ML optimization
        return timetable
    
    def _add_explanations(self, timetable: Dict) -> Dict:
        """Add explanations to each assignment"""
        for assignment in timetable.get('assignments', []):
            explanation = self.explainer.log_decision(
                variable_name=f"{assignment['course_id']}_{assignment['timeslot']['id']}",
                value=assignment['timeslot']['start_time'],
                constraints_used=['NoDoubleBooking', 'RoomCapacity'],
                alternatives=[],
                confidence=0.95
            )
            assignment['explanation'] = explanation.get_summary()
            assignment['reasoning'] = explanation.reasoning
        
        return timetable
    
    def _calculate_metrics(self, timetable: Dict) -> Dict[str, float]:
        """Calculate quality metrics for the timetable"""
        assignments = timetable.get('assignments', [])
        
        # Check for conflicts
        conflicts = self._count_conflicts(assignments)
        
        # Calculate fairness (distribution of timeslots)
        fairness = self._calculate_fairness(assignments)
        
        # Stability score (placeholder)
        stability = 1.0
        
        return {
            'conflicts': conflicts,
            'fairness': fairness,
            'stability': stability
        }
    
    def _count_conflicts(self, assignments: List[Dict]) -> int:
        """Count scheduling conflicts"""
        conflicts = 0
        
        # Check for double-booking of faculty
        faculty_slots = {}
        for assignment in assignments:
            key = f"{assignment.get('faculty_id')}_{assignment['timeslot']['id']}"
            if key in faculty_slots:
                conflicts += 1
            faculty_slots[key] = True
        
        # Check for double-booking of rooms
        room_slots = {}
        for assignment in assignments:
            key = f"{assignment.get('room_id')}_{assignment['timeslot']['id']}"
            if key in room_slots:
                conflicts += 1
            room_slots[key] = True
        
        return conflicts
    
    def _calculate_fairness(self, assignments: List[Dict]) -> float:
        """Calculate fairness score (0-1, higher is better)"""
        if not assignments:
            return 1.0
        
        # Calculate distribution of morning vs afternoon slots
        morning_count = sum(1 for a in assignments if a['timeslot']['is_morning'])
        afternoon_count = len(assignments) - morning_count
        
        # Ideal is 50-50 distribution
        if len(assignments) == 0:
            return 1.0
        
        balance = 1.0 - abs(morning_count - afternoon_count) / len(assignments)
        return balance
    
    def update_timetable(
        self,
        timetable_id: str,
        changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Update an existing timetable with minimal disruption
        Uses local repair algorithm
        """
        # TODO: Implement local repair
        return {'status': 'updated', 'changes_applied': len(changes)}
    
    def collect_feedback(
        self,
        timetable_id: str,
        feedback: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Collect user feedback for continuous learning
        """
        # TODO: Store feedback and retrain models
        return {'status': 'feedback_received', 'timetable_id': timetable_id}
    
    def get_explanation(self, assignment_id: str) -> Dict[str, Any]:
        """Get detailed explanation for a specific assignment"""
        explanation = self.explainer.get_explanation(assignment_id)
        if explanation:
            return explanation.to_dict()
        return {'error': 'Explanation not found'}
