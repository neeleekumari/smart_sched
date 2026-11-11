"""
Main timetable generator using direct assignment approach
"""
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import random

from models import Teacher, Subject, Timetable, User, Section
from .multi_timetable_generator import MultiTimetableGenerator, WorkloadConfig

class TimetableGenerator:
    """Main timetable generator class with multi-timetable support"""
    
    def __init__(self, db_session: Session, user: User, config: Optional[WorkloadConfig] = None):
        self.db = db_session
        self.user = user
        self.timeout_seconds: int = 300  # Default 5 minutes
        self.find_multiple_solutions: bool = False
        self.solutions_count: int = 1
        self.enable_heuristics: bool = True
        self.config = config or WorkloadConfig()
        
        # Multi-timetable generator
        self.multi_gen = MultiTimetableGenerator(db_session, user, self.config)
    
    def generate_timetable(self,
                          teachers: List[Teacher],
                          subjects: List[Subject],
                          timetable_name: str = "Generated Timetable",
                          extra_info: Optional[Dict[str, Any]] = None,
                          sections: Optional[List[Section]] = None,
                          generation_mode: str = 'single') -> Tuple[bool, Optional[Any], List[str]]:
        """Generate timetable(s) - single or multi based on mode
        
        Args:
            teachers: List of teachers
            subjects: List of subjects
            timetable_name: Base name for timetable(s)
            extra_info: Additional metadata
            sections: List of sections (for multi-timetable mode)
            generation_mode: 'single' or 'multi'
            
        Returns:
            Tuple of (success, timetable(s), errors)
        """
        
        if generation_mode == 'multi' and sections:
            # Multi-timetable generation
            return self.multi_gen.generate_multi_timetables(
                teachers, subjects, sections, timetable_name, extra_info
            )
        else:
            # Single timetable generation (backward compatible)
            return self.multi_gen.generate_single_timetable(
                teachers, subjects, timetable_name, extra_info
            )
    
    def _validate_input_data(self, teachers: List[Teacher], subjects: List[Subject]) -> Tuple[bool, List[str]]:
        """Validate all input data"""
        errors = []
        
        # Validate teachers
        for teacher in teachers:
            if not teacher.name:  # type: ignore[misc]
                errors.append(f"Teacher {teacher.id} has no name")
            if teacher.max_hours_per_week <= 0:  # type: ignore[misc]
                errors.append(f"Teacher {teacher.name} has invalid max hours per week")
            if teacher.max_hours_per_day <= 0:  # type: ignore[misc]
                errors.append(f"Teacher {teacher.name} has invalid max hours per day")
        
        # Validate subjects
        for subject in subjects:
            if not subject.name:  # type: ignore[misc]
                errors.append(f"Subject {subject.id} has no name")
            if not subject.code:  # type: ignore[misc]
                errors.append(f"Subject {subject.name} has no code")
            if subject.credits < 0:  # type: ignore[misc]
                errors.append(f"Subject {subject.name} has invalid credits")
            if subject.class_size <= 0:  # type: ignore[misc]
                errors.append(f"Subject {subject.name} has invalid class size")
        
        # Check teacher-subject assignments
        for subject in subjects:
            if subject.teacher_id and not any(t.id == subject.teacher_id for t in teachers):  # type: ignore[misc]
                errors.append(f"Subject {subject.name} assigned to non-existent teacher")
        
        return len(errors) == 0, errors
    

    def _validate_timetable(self, timetable_entries: List[Dict], 
                           teachers: List[Teacher], 
                           subjects: List[Subject]) -> Tuple[bool, List[str]]:
        """Validate a complete timetable"""
        errors = []
        
        # Check for teacher double booking
        teacher_schedule = {}
        for entry in timetable_entries:
            if entry.get('is_break') or entry.get('teacher_id') is None:
                continue
            
            key = (entry.get('day'), entry.get('period'))
            teacher_id = entry.get('teacher_id')
            if key in teacher_schedule:
                teacher_name = next((t.name for t in teachers if t.id == teacher_id), str(teacher_id))
                errors.append(f"Teacher {teacher_name} double booked at {entry.get('day')} period {entry.get('period')}")
            else:
                teacher_schedule[key] = teacher_id
        
        # Check teacher availability
        for entry in timetable_entries:
            if entry.get('is_break') or entry.get('teacher_id') is None:
                continue
            
            teacher = next((t for t in teachers if t.id == entry.get('teacher_id')), None)  # type: ignore[misc]
            if teacher is not None and not teacher.is_available(entry.get('day'), entry.get('period')):
                errors.append(f"Teacher {teacher.name} not available at {entry.get('day')} period {entry.get('period')}")
        
        return len(errors) == 0, errors
    

    def _generate_timetable(self, teachers: List[Teacher], subjects: List[Subject],
                                  timetable_name: str,
                                  extra_info: Optional[Dict[str, Any]] = None) -> Optional[Timetable]:
        """Generate a timetable using direct assignment approach"""

        # Define basic days and periods (no complex time slots)
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        
        # Get time configuration from extra_info
        time_config = extra_info.get('time_config', {}) if extra_info else {}
        num_teaching_periods = time_config.get('num_periods', 8)
        breaks_config = time_config.get('breaks', [])
        num_breaks = len(breaks_config)
        
        # Total periods = teaching periods + breaks (breaks are additional, not replacements)
        total_periods = num_teaching_periods + num_breaks
        periods = list(range(1, total_periods + 1))  # All period slots including breaks
        timetable = Timetable(
            name=timetable_name,
            description=f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            user_id=self.user.id,
            days=days,
            periods=periods,
            generation_time=datetime.now(),
            total_subjects=len(subjects),
            total_teachers=len(teachers),
            total_rooms=0  # No longer using rooms
        )
        # Persist extra info if provided
        if isinstance(extra_info, dict):
            timetable.programme_name = extra_info.get('programme_name') or extra_info.get('programmeName')  # type: ignore[assignment]
            timetable.term_label = extra_info.get('term_label') or extra_info.get('termLabel')  # type: ignore[assignment]
            timetable.semester = extra_info.get('semester')  # type: ignore[assignment]
            timetable.wef_date = extra_info.get('wef_date') or extra_info.get('wefDate')  # type: ignore[assignment]
            try:
                timetable.class_strength = int(extra_info.get('class_strength') or extra_info.get('classStrength') or 0) or None  # type: ignore[assignment]
            except Exception:
                timetable.class_strength = None  # type: ignore[assignment]
            timetable.logo_data_url = extra_info.get('logo_data_url') or extra_info.get('logoDataUrl')  # type: ignore[assignment]
            # sections may be a list of dicts - ensure they are JSON serializable
            sections_data = extra_info.get('sections') or extra_info.get('sections_meta')
            if sections_data:
                # Convert to ensure no SimpleNamespace objects and normalize keys
                if isinstance(sections_data, list):
                    normalized_sections = []
                    for section in sections_data:
                        if hasattr(section, 'items') or isinstance(section, dict):
                            sec_dict = dict(section) if hasattr(section, 'items') else section
                            # Normalize keys: ensure we have standard keys
                            normalized = {
                                'name': sec_dict.get('name', ''),
                                'classStrength': sec_dict.get('classStrength') or sec_dict.get('class_strength', ''),
                                'classTeacher': sec_dict.get('classTeacher') or sec_dict.get('class_teacher', ''),
                                'lectureHall': sec_dict.get('lectureHall') or sec_dict.get('lecture_hall') or sec_dict.get('hall', '')
                            }
                            normalized_sections.append(normalized)
                        else:
                            normalized_sections.append(section)
                    timetable.sections_meta = normalized_sections  # type: ignore[assignment]
                elif hasattr(sections_data, 'items'):
                    timetable.sections_meta = [dict(sections_data)]  # type: ignore[assignment]
                else:
                    timetable.sections_meta = sections_data  # type: ignore[assignment]
            else:
                timetable.sections_meta = None  # type: ignore[assignment]

        # Create entries and track teacher assignments globally
        entries = []
        # Track which teachers are assigned to which slots: {(day, period): set(teacher_ids)}
        teacher_assignments = {}

        # Create all possible time slots (excluding break periods)
        breaks_config = time_config.get('breaks', [])
        break_periods = self._calculate_break_periods(time_config, breaks_config)
        
        all_slots = []
        for day in days:
            for period in periods:
                if period not in break_periods:  # Skip break periods
                    all_slots.append((day, period))
        
        # Shuffle all slots to randomize allocation
        random.shuffle(all_slots)

        # Assign subjects to time slots with proper distribution
        for subject in subjects:
            required_hours = subject.weekly_hours if hasattr(subject, 'weekly_hours') and subject.weekly_hours > 0 else (subject.credits or 2)
            assigned_hours = 0

            # Find the assigned teacher (supports multiple teachers)
            # Note: teacher can be None for subjects like NSS, MP that don't require a teacher
            teacher = self._select_teacher_for_subject(subject, teachers)

            # Get hall from sections meta
            hall = 'Hall 1'  # Default hall
            if extra_info and extra_info.get('sections'):
                sections = extra_info.get('sections', [])
                if sections and len(sections) > 0:
                    hall = sections[0].get('hall') or sections[0].get('lectureHall') or 'Hall 1'

            # Track days used for this subject to ensure distribution
            days_used = set()
            
            # Try to assign required hours across different days
            slot_candidates = all_slots.copy()
            random.shuffle(slot_candidates)  # Shuffle again for this subject
            
            for slot_day, slot_period in slot_candidates:
                if assigned_hours >= required_hours:  # type: ignore[misc]
                    break
                
                slot_key = (slot_day, slot_period)

                # Check if this slot is already occupied by the same teacher (if teacher exists)
                if teacher:
                    teacher_assigned_to_slot = teacher_assignments.get(slot_key, set())
                    if teacher.id in teacher_assigned_to_slot:
                        continue

                # Check if this slot is already occupied by any entry
                slot_occupied = any(
                    entry.get('day') == slot_day and entry.get('period') == slot_period
                    for entry in entries
                )
                if slot_occupied:
                    continue

                # Check if teacher is available for this slot (if teacher exists)
                if teacher and not teacher.is_available(slot_day, slot_period):  # type: ignore[misc]
                    continue
                
                # Prevent consecutive periods on the same day for the same subject
                has_adjacent_slot = any(
                    entry.get('day') == slot_day and 
                    entry.get('subject_id') == subject.id and
                    abs(entry.get('period', 0) - slot_period) == 1
                    for entry in entries
                )
                if has_adjacent_slot:
                    continue
                
                # Prefer to spread across different days (but allow same day if needed) - if teacher exists
                # Skip this slot if we haven't used all days yet and this day is already used
                if teacher and slot_day in days_used and len(days_used) < min(required_hours, len(days)):  # type: ignore[misc]
                    # Try to find a slot on a different day first
                    has_unused_day_available = any(
                        (d, p) != slot_key and 
                        d not in days_used and 
                        not any(entry.get('day') == d and entry.get('period') == p for entry in entries) and
                        teacher.id not in teacher_assignments.get((d, p), set())  # type: ignore[misc]
                        for d, p in slot_candidates
                    )
                    if has_unused_day_available:
                        continue  # Skip this slot, try to find one on unused day
                
                # Assign subject to this slot
                entry = {
                    'day': slot_day,
                    'period': slot_period,
                    'subject_id': subject.id,
                    'teacher_id': teacher.id if teacher else None,
                    'hall': hall,
                    'is_lab_block': False,  # Will be set to True when lab blocks are properly placed
                    'lab_block_position': None,  # Will be 1 or 2 for lab blocks
                    'lab_block_id': None,  # Will link both slots of a lab block
                    'is_break': False
                }
                entries.append(entry)

                # Track this teacher's assignment to this slot (if teacher exists)
                if teacher:
                    if slot_key not in teacher_assignments:
                        teacher_assignments[slot_key] = set()
                    teacher_assignments[slot_key].add(teacher.id)
                
                # Track day usage
                days_used.add(slot_day)

                assigned_hours += 1

        # Add break entries based on configuration
        for day in days:
            for period, break_name in break_periods.items():
                entry = {
                    'day': day,
                    'period': period,
                    'subject_id': None,
                    'teacher_id': None,
                    'hall': None,
                    'is_lab_block': False,
                    'lab_block_position': None,
                    'lab_block_id': None,
                    'is_break': True,
                    'break_type': break_name.lower()
                }
                entries.append(entry)

        timetable.entries_data = entries  # type: ignore[assignment]
        
        # Generate and store timings
        timings = self._generate_timings(time_config, break_periods)
        timetable.timings = timings  # type: ignore[assignment]
        timetable.time_config = time_config  # type: ignore[assignment]
        
        return timetable
    
    def _generate_timings(self, time_config: dict, break_periods: dict) -> dict:
        """Generate time labels for each period slot
        
        Args:
            time_config: Configuration with start_time, end_time, num_periods, breaks
            break_periods: Dict mapping period slot number to break name
            
        Returns:
            Dict mapping period slot number to time range string (e.g., "09:00 - 10:00")
        """
        start_time = time_config.get('start_time', '09:00')
        num_teaching_periods = time_config.get('num_periods', 8)
        breaks_config = time_config.get('breaks', [])
        
        # Parse start time
        start_hour, start_min = map(int, start_time.split(':'))
        current_minutes = start_hour * 60 + start_min
        
        # Calculate total break duration
        total_break_minutes = sum(b.get('duration', 15) for b in breaks_config)
        
        # Parse end time to get total available time
        end_time = time_config.get('end_time', '17:00')
        end_hour, end_min = map(int, end_time.split(':'))
        total_minutes = (end_hour * 60 + end_min) - current_minutes
        
        # Teaching time (excluding breaks)
        teaching_minutes = total_minutes - total_break_minutes
        
        # Duration per teaching period
        period_duration = teaching_minutes / num_teaching_periods
        
        # Parse breaks with their exact times
        breaks_with_time = []
        for b in breaks_config:
            break_start = b.get('start_time', '')
            if break_start:
                try:
                    break_hour, break_min = map(int, break_start.split(':'))
                    break_time_minutes = break_hour * 60 + break_min
                    breaks_with_time.append({
                        'name': b.get('name', 'Break'),
                        'time_minutes': break_time_minutes,
                        'duration': b.get('duration', 15)
                    })
                except (ValueError, AttributeError):
                    pass
        
        breaks_with_time.sort(key=lambda x: x['time_minutes'])
        
        # Create timeline of teaching blocks and breaks
        timeline = []
        current_time = start_hour * 60 + start_min
        
        for break_info in breaks_with_time:
            break_start = break_info['time_minutes']
            break_end = break_start + break_info['duration']
            
            # Add teaching time before this break
            if break_start > current_time:
                timeline.append({
                    'type': 'teaching_block',
                    'start': current_time,
                    'end': break_start,
                    'duration': break_start - current_time
                })
            
            # Add the break
            timeline.append({
                'type': 'break',
                'name': break_info['name'],
                'start': break_start,
                'end': break_end,
                'duration': break_info['duration']
            })
            
            current_time = break_end
        
        # Add remaining teaching time after last break
        end_hour, end_min = map(int, end_time.split(':'))
        end_minutes = end_hour * 60 + end_min
        if current_time < end_minutes:
            timeline.append({
                'type': 'teaching_block',
                'start': current_time,
                'end': end_minutes,
                'duration': end_minutes - current_time
            })
        
        # Calculate total teaching time
        total_teaching_time = sum(seg['duration'] for seg in timeline if seg['type'] == 'teaching_block')
        
        # Generate timings for each period slot
        timings = {}
        period_slot = 1
        periods_assigned = 0
        
        for segment in timeline:
            if segment['type'] == 'break':
                # This slot is a break
                start_h = int(segment['start'] // 60)
                start_m = int(segment['start'] % 60)
                end_h = int(segment['end'] // 60)
                end_m = int(segment['end'] % 60)
                timings[period_slot] = f"{start_h:02d}:{start_m:02d} - {end_h:02d}:{end_m:02d}"
                period_slot += 1
            else:
                # This is a teaching block - divide it into periods
                block_proportion = segment['duration'] / total_teaching_time
                periods_in_block = round(block_proportion * num_teaching_periods)
                
                # Ensure we don't exceed total periods
                if periods_assigned + periods_in_block > num_teaching_periods:
                    periods_in_block = num_teaching_periods - periods_assigned
                
                # Divide this block into equal periods
                if periods_in_block > 0:
                    period_duration_in_block = segment['duration'] / periods_in_block
                    block_start = segment['start']
                    
                    for i in range(periods_in_block):
                        start_time = block_start + (i * period_duration_in_block)
                        end_time = start_time + period_duration_in_block
                        
                        start_h = int(start_time // 60)
                        start_m = int(start_time % 60)
                        end_h = int(end_time // 60)
                        end_m = int(end_time % 60)
                        
                        timings[period_slot] = f"{start_h:02d}:{start_m:02d} - {end_h:02d}:{end_m:02d}"
                        period_slot += 1
                        periods_assigned += 1
        
        return timings
    
    def _select_teacher_for_subject(self, subject: Subject, all_teachers: List[Teacher]) -> Optional[Teacher]:
        """Select an appropriate teacher for a subject, considering multi-teacher assignments.
        
        Args:
            subject: The subject to assign a teacher for
            all_teachers: List of all available teachers
            
        Returns:
            Selected teacher or None if no teacher available
        """
        from models.teacher_assignment import TeacherAssignment
        
        # Get all eligible teachers from TeacherAssignment table
        assignments = self.db.query(TeacherAssignment).filter(
            TeacherAssignment.subject_id == subject.id,
            TeacherAssignment.section_id == None,  # Global assignments
            TeacherAssignment.is_eligible == True
        ).all()
        
        eligible_teacher_ids = [a.teacher_id for a in assignments] if assignments else []
        
        # If no assignments found, fall back to legacy teacher_id
        if not eligible_teacher_ids and subject.teacher_id:
            eligible_teacher_ids = [subject.teacher_id]
        
        if not eligible_teacher_ids:
            return None
        
        # Get teacher objects
        eligible_teachers = [t for t in all_teachers if t.id in eligible_teacher_ids]
        
        if not eligible_teachers:
            return None
        
        # For single timetable, just pick the first eligible teacher
        # (or could use random.choice for variety)
        return eligible_teachers[0]
    
    def _calculate_break_periods(self, time_config: dict, breaks_config: list) -> dict:
        """Calculate which period number each break falls into based on start times
        
        Breaks are ADDITIONAL periods, not replacements. If user specifies 6 periods + 2 breaks,
        we create 8 total period slots, with 2 of them being breaks.
        
        Strategy: Simulate the schedule from start to end, inserting breaks at their specified times.
        """
        if not breaks_config:
            return {}
        
        start_time = time_config.get('start_time', '09:00')
        num_teaching_periods = time_config.get('num_periods', 8)
        
        # Parse start time
        start_hour, start_min = map(int, start_time.split(':'))
        
        # Calculate total break duration
        total_break_minutes = sum(b.get('duration', 15) for b in breaks_config)
        
        # Parse end time to get total available time
        end_time = time_config.get('end_time', '17:00')
        end_hour, end_min = map(int, end_time.split(':'))
        total_minutes = (end_hour * 60 + end_min) - (start_hour * 60 + start_min)
        
        # Available teaching time
        teaching_minutes = total_minutes - total_break_minutes
        
        # Duration per teaching period
        period_duration = teaching_minutes / num_teaching_periods
        
        # Parse and sort breaks by start time
        breaks_with_time = []
        for b in breaks_config:
            break_start = b.get('start_time', '')
            if break_start:
                try:
                    break_hour, break_min = map(int, break_start.split(':'))
                    break_time_minutes = break_hour * 60 + break_min
                    breaks_with_time.append({
                        'name': b.get('name', 'Break'),
                        'time_minutes': break_time_minutes,
                        'duration': b.get('duration', 15)
                    })
                except (ValueError, AttributeError):
                    pass
        
        breaks_with_time.sort(key=lambda x: x['time_minutes'])
        
        # Create a timeline of all time segments (teaching blocks between breaks)
        # This ensures breaks are at exact times and teaching periods fill the gaps
        timeline = []
        current_time = start_hour * 60 + start_min
        
        for break_info in breaks_with_time:
            break_start = break_info['time_minutes']
            break_end = break_start + break_info['duration']
            
            # Add teaching time before this break (if any)
            if break_start > current_time:
                timeline.append({
                    'type': 'teaching_block',
                    'start': current_time,
                    'end': break_start,
                    'duration': break_start - current_time
                })
            
            # Add the break
            timeline.append({
                'type': 'break',
                'name': break_info['name'],
                'start': break_start,
                'end': break_end,
                'duration': break_info['duration']
            })
            
            current_time = break_end
        
        # Add remaining teaching time after last break
        end_hour, end_min = map(int, end_time.split(':'))
        end_minutes = end_hour * 60 + end_min
        if current_time < end_minutes:
            timeline.append({
                'type': 'teaching_block',
                'start': current_time,
                'end': end_minutes,
                'duration': end_minutes - current_time
            })
        
        # Now distribute teaching periods across teaching blocks
        # Calculate how many periods fit in each block proportionally
        total_teaching_time = sum(seg['duration'] for seg in timeline if seg['type'] == 'teaching_block')
        
        # Assign periods to blocks based on their proportion of total teaching time
        period_slot = 1
        break_periods = {}
        periods_assigned = 0
        
        for segment in timeline:
            if segment['type'] == 'break':
                # This slot is a break
                break_periods[period_slot] = segment['name']
                period_slot += 1
            else:
                # This is a teaching block - calculate how many periods fit here
                block_proportion = segment['duration'] / total_teaching_time
                periods_in_block = round(block_proportion * num_teaching_periods)
                
                # Ensure we don't exceed total periods
                if periods_assigned + periods_in_block > num_teaching_periods:
                    periods_in_block = num_teaching_periods - periods_assigned
                
                # Add teaching period slots for this block
                for _ in range(periods_in_block):
                    # period_slot is a teaching period (not in break_periods dict)
                    period_slot += 1
                    periods_assigned += 1
        
        return break_periods
    
    def regenerate_timetable(self, timetable_id: int) -> Tuple[bool, Optional[Timetable], List[str]]:
        """Regenerate an existing timetable"""
        # Get existing timetable
        timetable = self.db.query(Timetable).filter(
            Timetable.id == timetable_id,
            Timetable.user_id == self.user.id
        ).first()
        
        if not timetable:
            return False, None, ["Timetable not found"]
        
        # Get associated data
        teachers = self.db.query(Teacher).filter(Teacher.user_id == self.user.id).all()
        subjects = self.db.query(Subject).filter(Subject.user_id == self.user.id).all()

        # Delete old timetable
        self.db.delete(timetable)
        self.db.commit()

        # Generate new timetable (no rooms parameter needed)
        return self.generate_timetable(
            teachers, subjects,
            f"{timetable.name} (Regenerated)"
        )
    
    def get_generation_statistics(self) -> Dict[str, Any]:
        """Get basic statistics about timetable generation"""
        return {
            'approach': 'direct_assignment',
            'supports_double_booking_prevention': True,
            'supports_teacher_availability': True,
            'supports_subject_credits': True
        }
