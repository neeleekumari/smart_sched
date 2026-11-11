"""
Teacher Conflict Resolver
Handles teacher assignment conflicts across sections and semesters
"""
from typing import List, Dict, Set, Tuple, Optional
from models import Teacher, Subject, Section
import logging

logger = logging.getLogger(__name__)


class TeacherConflictResolver:
    """
    Resolves teacher conflicts across multiple sections and semesters
    Implements the three critical rules:
    1. One teacher cannot be in two places at the same time
    2. Teacher cooldown/rest time between classes
    3. Semester-wise conflict detection
    """
    
    def __init__(self, require_rest_time: bool = True):
        self.require_rest_time = require_rest_time
        # Global schedule: {(day, period): {teacher_id: (section_id, semester, subject_id)}}
        self.global_schedule: Dict[Tuple[str, int], Dict[int, Tuple[Optional[int], Optional[str], int]]] = {}
        # Teacher timeline: {teacher_id: {day: [periods]}}
        self.teacher_timeline: Dict[int, Dict[str, List[int]]] = {}
    
    def reset(self):
        """Reset the conflict resolver state"""
        self.global_schedule = {}
        self.teacher_timeline = {}
    
    def can_assign_teacher(self, 
                          teacher_id: int,
                          day: str,
                          period: int,
                          section_id: Optional[int],
                          semester: Optional[str],
                          subject_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if a teacher can be assigned to a specific time slot
        
        Returns:
            (can_assign, reason_if_not)
        """
        slot_key = (day, period)
        
        # Rule A: Check if teacher is already assigned at this time
        if slot_key in self.global_schedule:
            if teacher_id in self.global_schedule[slot_key]:
                existing = self.global_schedule[slot_key][teacher_id]
                existing_section, existing_semester, existing_subject = existing
                return False, f"Teacher already teaching at {day} Period {period} (Section {existing_section}, Semester {existing_semester})"
        
        # Rule B: Check rest time (no consecutive periods)
        if self.require_rest_time:
            if teacher_id in self.teacher_timeline:
                if day in self.teacher_timeline[teacher_id]:
                    assigned_periods = self.teacher_timeline[teacher_id][day]
                    # Check for adjacent periods
                    if (period - 1) in assigned_periods or (period + 1) in assigned_periods:
                        return False, f"Teacher needs rest time (has class at adjacent period on {day})"
        
        # Rule C: Semester-wise conflict (already covered by Rule A, but explicit check)
        # If teacher is teaching ANY semester at this time, they can't teach another
        if slot_key in self.global_schedule:
            if teacher_id in self.global_schedule[slot_key]:
                return False, f"Teacher already assigned at {day} Period {period}"
        
        return True, None
    
    def assign_teacher(self,
                      teacher_id: int,
                      day: str,
                      period: int,
                      section_id: Optional[int],
                      semester: Optional[str],
                      subject_id: int):
        """
        Assign a teacher to a time slot
        Updates global schedule and teacher timeline
        """
        slot_key = (day, period)
        
        # Update global schedule
        if slot_key not in self.global_schedule:
            self.global_schedule[slot_key] = {}
        self.global_schedule[slot_key][teacher_id] = (section_id, semester, subject_id)
        
        # Update teacher timeline
        if teacher_id not in self.teacher_timeline:
            self.teacher_timeline[teacher_id] = {}
        if day not in self.teacher_timeline[teacher_id]:
            self.teacher_timeline[teacher_id][day] = []
        self.teacher_timeline[teacher_id][day].append(period)
    
    def unassign_teacher(self,
                        teacher_id: int,
                        day: str,
                        period: int):
        """
        Unassign a teacher from a time slot (for backtracking)
        """
        slot_key = (day, period)
        
        # Remove from global schedule
        if slot_key in self.global_schedule:
            if teacher_id in self.global_schedule[slot_key]:
                del self.global_schedule[slot_key][teacher_id]
                if not self.global_schedule[slot_key]:
                    del self.global_schedule[slot_key]
        
        # Remove from teacher timeline
        if teacher_id in self.teacher_timeline:
            if day in self.teacher_timeline[teacher_id]:
                if period in self.teacher_timeline[teacher_id][day]:
                    self.teacher_timeline[teacher_id][day].remove(period)
                if not self.teacher_timeline[teacher_id][day]:
                    del self.teacher_timeline[teacher_id][day]
    
    def get_teacher_workload(self, teacher_id: int) -> int:
        """Get total hours assigned to a teacher"""
        if teacher_id not in self.teacher_timeline:
            return 0
        
        total_hours = 0
        for day, periods in self.teacher_timeline[teacher_id].items():
            total_hours += len(periods)
        return total_hours
    
    def get_conflicts_report(self) -> List[str]:
        """Generate a report of all conflicts in the current schedule"""
        conflicts = []
        
        for slot_key, teachers in self.global_schedule.items():
            day, period = slot_key
            if len(teachers) > 1:
                teacher_ids = list(teachers.keys())
                conflicts.append(f"Multiple teachers at {day} Period {period}: {teacher_ids}")
        
        return conflicts
    
    def validate_schedule(self) -> Tuple[bool, List[str]]:
        """
        Validate the entire schedule for conflicts
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Check for double bookings
        for slot_key, teachers in self.global_schedule.items():
            day, period = slot_key
            for teacher_id, assignment in teachers.items():
                section_id, semester, subject_id = assignment
                
                # Count how many times this teacher appears at this slot
                count = sum(1 for t_id in teachers.keys() if t_id == teacher_id)
                if count > 1:
                    errors.append(f"Teacher {teacher_id} double-booked at {day} Period {period}")
        
        # Check rest time violations
        if self.require_rest_time:
            for teacher_id, days_schedule in self.teacher_timeline.items():
                for day, periods in days_schedule.items():
                    sorted_periods = sorted(periods)
                    for i in range(len(sorted_periods) - 1):
                        if sorted_periods[i+1] - sorted_periods[i] == 1:
                            errors.append(f"Teacher {teacher_id} has consecutive periods on {day}: {sorted_periods[i]}, {sorted_periods[i+1]}")
        
        return len(errors) == 0, errors


class TeacherSelector:
    """
    Selects optimal teacher for a subject from multiple eligible teachers
    Implements load balancing and conflict minimization
    """
    
    def __init__(self, 
                 conflict_resolver: TeacherConflictResolver,
                 min_hours: int = 16,
                 max_hours: int = 18):
        self.conflict_resolver = conflict_resolver
        self.min_hours = min_hours
        self.max_hours = max_hours
    
    def select_teacher_for_slot(self,
                               eligible_teachers: List[Teacher],
                               subject: Subject,
                               day: str,
                               period: int,
                               section_id: Optional[int],
                               semester: Optional[str]) -> Optional[Teacher]:
        """
        Select the best teacher for a given slot from eligible teachers
        
        Selection criteria (in order):
        1. Teacher must be available at this time
        2. Teacher must not have conflicts
        3. Teacher with lowest current workload (load balancing)
        4. Teacher with most remaining capacity
        """
        candidates = []
        
        for teacher in eligible_teachers:
            # Check availability
            if not teacher.is_available(day, period):
                continue
            
            # Check conflicts
            can_assign, reason = self.conflict_resolver.can_assign_teacher(
                teacher.id, day, period, section_id, semester, subject.id
            )
            if not can_assign:
                continue
            
            # Calculate current workload
            current_workload = self.conflict_resolver.get_teacher_workload(teacher.id)
            
            # Calculate remaining capacity
            remaining_capacity = self.max_hours - current_workload
            
            # Score: prefer teachers with lower workload but still within range
            # Avoid overloading or underloading
            if current_workload >= self.max_hours:
                continue  # Already at max
            
            score = remaining_capacity  # Higher score = more capacity
            
            candidates.append((teacher, score, current_workload))
        
        if not candidates:
            return None
        
        # Sort by score (descending) and workload (ascending for tie-breaking)
        candidates.sort(key=lambda x: (-x[1], x[2]))
        
        return candidates[0][0]
    
    def get_workload_distribution(self, teachers: List[Teacher]) -> Dict[int, int]:
        """Get workload distribution across all teachers"""
        distribution = {}
        for teacher in teachers:
            distribution[teacher.id] = self.conflict_resolver.get_teacher_workload(teacher.id)
        return distribution
