"""
Multi-timetable generator with workload configuration support
"""
from typing import List, Dict, Any, Tuple, Optional, Set
from datetime import datetime
from sqlalchemy.orm import Session
import random

from models import Teacher, Subject, Timetable, User, Section
from timetable_generator.error_reporter import ErrorReporter, TimetableError


class WorkloadConfig:
    """Configuration for workload distribution in timetables"""
    
    def __init__(self):
        self.multi_timetable_min_hours = 4
        self.multi_timetable_max_hours = 8
        self.single_timetable_target_hours = 6
        self.max_theory_subjects = 10
        self.max_lab_subjects = 5
        self.require_rest_between_classes = True
        self.use_csp_solver = False
        self.use_ml_optimization = False
        
        # New configuration options for advanced constraints
        self.require_complete_filling = False  # Enforce no empty slots (default: False for backward compatibility)
        self.allow_partial_lab_blocks = False  # Allow lab subjects without full blocks
        self.max_consecutive_same_subject = 1  # Max consecutive periods (except labs)
        self.prefer_day_distribution = True  # Prefer spreading across days


class MultiTimetableGenerator:
    """Generator for multiple timetables with section support"""
    
    def __init__(self, db_session: Session, user: User, config: Optional[WorkloadConfig] = None):
        self.db = db_session
        self.user = user
        self.config = config or WorkloadConfig()
        # Track which teachers are assigned to which subjects across sections
        self.subject_teacher_tracker = {}  # {subject_id: [teacher_ids_used]}
    
    def generate_multi_timetables(self,
                                  teachers: List[Teacher],
                                  subjects: List[Subject],
                                  sections: List[Section],
                                  timetable_name: str,
                                  extra_info: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[Timetable], List[str]]:
        """Generate multiple timetables, one for each section, preventing concurrent teacher and room conflicts across sections"""
        
        timetables = []
        errors = []
        
        # Reset teacher tracker for new generation
        self.subject_teacher_tracker = {}
        
        # Global assignments tracking across ALL sections
        global_teacher_assignments: Dict[Tuple[str, int], Set[int]] = {}
        global_room_assignments: Dict[Tuple[str, int], Set[str]] = {}
        
        for section in sections:
            # Filter subjects for this section
            section_subjects = self._filter_subjects_for_section(subjects, section)
            
            if not section_subjects:
                errors.append(f"No subjects found for section {section.name}")
                continue
            
            # Generate timetable for this section
            section_name = f"{timetable_name} - {section.name}"
            timetable = self._generate_single_timetable_internal(
                teachers, section_subjects, section_name, extra_info, section,
                global_teacher_assignments=global_teacher_assignments,
                global_room_assignments=global_room_assignments
            )
            
            if timetable:
                self.db.add(timetable)
                self.db.flush()
                timetables.append(timetable)
            else:
                errors.append(f"Failed to generate timetable for section {section.name}")
        
        if timetables:
            self.db.commit()
            return True, timetables, errors
        else:
            self.db.rollback()
            return False, [], errors
    
    def generate_single_timetable(self,
                                  teachers: List[Teacher],
                                  subjects: List[Subject],
                                  timetable_name: str,
                                  extra_info: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[Timetable], List[str]]:
        """Generate a single timetable"""
        
        timetable = self._generate_single_timetable_internal(
            teachers, subjects, timetable_name, extra_info, None
        )
        
        if timetable:
            self.db.add(timetable)
            self.db.commit()
            return True, timetable, []
        else:
            return False, None, ["Failed to generate timetable"]
    
    def _generate_single_timetable_internal(self,
                                           teachers: List[Teacher],
                                           subjects: List[Subject],
                                           timetable_name: str,
                                           extra_info: Optional[Dict[str, Any]] = None,
                                           section: Optional[Section] = None,
                                           global_teacher_assignments: Optional[Dict[Tuple[str, int], Set[int]]] = None,
                                           global_room_assignments: Optional[Dict[Tuple[str, int], Set[str]]] = None) -> Optional[Timetable]:
        """Internal method to generate a single timetable"""
        
        # Initialize tracking maps if not provided
        if global_teacher_assignments is None:
            global_teacher_assignments = {}
        if global_room_assignments is None:
            global_room_assignments = {}
            
        # Define basic days
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        
        # Get time configuration from extra_info
        time_config = extra_info.get('time_config', {}) if extra_info else {}
        if time_config.get('days'):
            days = time_config.get('days')
            
        num_teaching_periods = time_config.get('num_periods') or time_config.get('periods') or 8
        if isinstance(num_teaching_periods, list):
            num_teaching_periods = len(num_teaching_periods)
        num_teaching_periods = int(num_teaching_periods)
        
        breaks_config = time_config.get('breaks', [])
        num_breaks = len(breaks_config)
        
        # Total periods = teaching periods + breaks (breaks are additional, not replacements)
        total_periods = num_teaching_periods + num_breaks
        periods = list(range(1, total_periods + 1))  # All period slots including breaks
        
        # Create timetable object
        timetable = Timetable(
            name=timetable_name,
            description=f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            user_id=self.user.id,
            days=days,
            periods=periods,
            generation_time=datetime.now(),
            total_subjects=len(subjects),
            total_teachers=len(teachers),
            total_rooms=0,
            section_id=section.id if section else None
        )
        
        # Persist extra info if provided
        if isinstance(extra_info, dict):
            timetable.programme_name = extra_info.get('programme_name') or extra_info.get('programmeName')
            timetable.term_label = extra_info.get('term_label') or extra_info.get('termLabel')
            timetable.semester = extra_info.get('semester')
            timetable.wef_date = extra_info.get('wef_date') or extra_info.get('wefDate')
            timetable.logo_data_url = extra_info.get('logo_data_url') or extra_info.get('logoDataUrl')
            
            # Handle section-specific metadata
            if section:
                # For multi-timetable generation, store ONLY this section's info
                sections_data = extra_info.get('sections') or extra_info.get('sections_meta')
                
                if sections_data and isinstance(sections_data, list):
                    # Find the metadata for THIS specific section
                    section_meta = None
                    for sec in sections_data:
                        if hasattr(sec, 'items') or isinstance(sec, dict):
                            sec_dict = dict(sec) if hasattr(sec, 'items') else sec
                            if sec_dict.get('name') == section.name:
                                section_meta = sec_dict
                                break
                    
                    if section_meta:
                        # Store only this section's metadata
                        class_teacher_name = section_meta.get('classTeacher') or section_meta.get('class_teacher', '')
                        
                        # If no class teacher name but section has class_teacher_id, get teacher name
                        if not class_teacher_name and section.class_teacher_id:
                            class_teacher = next((t for t in teachers if t.id == section.class_teacher_id), None)
                            if class_teacher:
                                class_teacher_name = class_teacher.name
                        
                        normalized = {
                            'name': section_meta.get('name', section.name),
                            'classStrength': section_meta.get('classStrength') or section_meta.get('class_strength', '') or section.class_strength,
                            'classTeacher': class_teacher_name,
                            'lectureHall': section_meta.get('lectureHall') or section_meta.get('lecture_hall') or section_meta.get('hall', '') or section.lecture_hall
                        }
                        timetable.sections_meta = [normalized]
                        
                        # Also set individual fields for backward compatibility
                        timetable.class_strength = int(normalized['classStrength']) if normalized['classStrength'] else section.class_strength
                    else:
                        # No metadata found, use section object data
                        class_teacher_name = ''
                        if section.class_teacher_id:
                            class_teacher = next((t for t in teachers if t.id == section.class_teacher_id), None)
                            if class_teacher:
                                class_teacher_name = class_teacher.name
                        
                        timetable.sections_meta = [{
                            'name': section.name,
                            'classStrength': section.class_strength or '',
                            'classTeacher': class_teacher_name,
                            'lectureHall': section.lecture_hall or ''
                        }]
                        timetable.class_strength = section.class_strength
                else:
                    # No sections data, use section object
                    class_teacher_name = ''
                    if section.class_teacher_id:
                        class_teacher = next((t for t in teachers if t.id == section.class_teacher_id), None)
                        if class_teacher:
                            class_teacher_name = class_teacher.name
                    
                    timetable.sections_meta = [{
                        'name': section.name,
                        'classStrength': section.class_strength or '',
                        'classTeacher': class_teacher_name,
                        'lectureHall': section.lecture_hall or ''
                    }]
                    timetable.class_strength = section.class_strength
            else:
                # Single timetable - store all sections or class_strength from extra_info
                try:
                    timetable.class_strength = int(extra_info.get('class_strength') or extra_info.get('classStrength') or 0) or None
                except Exception:
                    timetable.class_strength = None
                
                sections_data = extra_info.get('sections') or extra_info.get('sections_meta')
                if sections_data:
                    if isinstance(sections_data, list):
                        normalized_sections = []
                        for sec in sections_data:
                            if hasattr(sec, 'items') or isinstance(sec, dict):
                                sec_dict = dict(sec) if hasattr(sec, 'items') else sec
                                normalized = {
                                    'name': sec_dict.get('name', ''),
                                    'classStrength': sec_dict.get('classStrength') or sec_dict.get('class_strength', ''),
                                    'classTeacher': sec_dict.get('classTeacher') or sec_dict.get('class_teacher', ''),
                                    'lectureHall': sec_dict.get('lectureHall') or sec_dict.get('lecture_hall') or sec_dict.get('hall', '')
                                }
                                normalized_sections.append(normalized)
                            else:
                                normalized_sections.append(sec)
                        timetable.sections_meta = normalized_sections
                    elif hasattr(sections_data, 'items'):
                        timetable.sections_meta = [dict(sections_data)]
                    else:
                        timetable.sections_meta = sections_data
                else:
                    timetable.sections_meta = None
        
        # Generate entries using three-phase approach
        entries = []
        teacher_assignments = global_teacher_assignments
        room_assignments = global_room_assignments
        
        # Create all possible time slots (excluding break periods)
        breaks_config = time_config.get('breaks', [])
        break_periods = self._calculate_break_periods(time_config, breaks_config)
        
        # Get hall from section or sections meta
        hall = 'Hall 1'  # Default hall
        if section and section.lecture_hall:
            hall = section.lecture_hall
        elif extra_info and extra_info.get('sections'):
            sections = extra_info.get('sections', [])
            if section:
                for s in sections:
                    if (s.get('name') or s.get('section_name')) == section.name:
                        hall = s.get('lectureHall') or s.get('lecture_hall') or s.get('hall') or hall
                        break
            elif sections and len(sections) > 0:
                hall = sections[0].get('hall') or sections[0].get('lectureHall') or 'Hall 1'
        
        # Track occupied slots for this timetable
        occupied_slots = set()
        
        # Initialize LabBlockPlacer
        from timetable_generator.lab_block_placer import LabBlockPlacer
        lab_placer = LabBlockPlacer()
        
        # PHASE 1: Assign lab blocks for lab and integrated subjects (including 0-credit subjects)
        lab_subjects = [s for s in subjects if s.requires_lab_block()]
        failed_lab_subjects = []
        lab_days_for_subject = {}  # {subject_id: day}
        
        for subject in lab_subjects:
            # Get teacher for this subject
            teacher = self._select_teacher_for_subject(subject, teachers, section)
            
            # Find available consecutive slots
            consecutive_slots = lab_placer.find_consecutive_slots(
                days, periods, break_periods, occupied_slots
            )
            
            # Try to place lab block
            lab_block_placed = False
            for day, period1, period2 in consecutive_slots:
                if lab_placer.can_place_lab_block(
                    day, period1, period2, teacher, occupied_slots, teacher_assignments,
                    hall=hall, room_assignments=room_assignments
                ):
                    # Place the lab block
                    entry1, entry2 = lab_placer.place_lab_block(
                        subject, teacher, day, period1, period2, hall
                    )
                    entries.append(entry1)
                    entries.append(entry2)
                    
                    # Mark slots as occupied
                    occupied_slots.add((day, period1))
                    occupied_slots.add((day, period2))
                    
                    # Track teacher assignments
                    if teacher:
                        teacher_assignments.setdefault((day, period1), set()).add(teacher.id)
                        teacher_assignments.setdefault((day, period2), set()).add(teacher.id)
                        
                    # Track room assignments
                    if hall:
                        room_assignments.setdefault((day, period1), set()).add(hall)
                        room_assignments.setdefault((day, period2), set()).add(hall)
                    
                    lab_days_for_subject[subject.id] = day
                    lab_block_placed = True
                    break
            
            if not lab_block_placed:
                failed_lab_subjects.append(subject)
        
        # Handle failed lab block placements
        if failed_lab_subjects:
            if not self.config.allow_partial_lab_blocks:
                # Critical error if partial lab blocks not allowed
                error = ErrorReporter.no_consecutive_slots_error(
                    affected_subjects=failed_lab_subjects,
                    days=days,
                    reason='All consecutive slot pairs are occupied or separated by breaks'
                )
                print(str(error))
                return None
            else:
                # Warning if partial lab blocks are allowed
                for subject in failed_lab_subjects:
                    warning = ErrorReporter.partial_lab_block_warning(
                        subject=subject,
                        reason='No consecutive slots available'
                    )
                    print(str(warning))
        
        # PHASE 2: Assign theory hours for all subjects
        for subject in subjects:
            # Calculate theory hours needed
            theory_hours = subject.get_theory_hours()
            
            if theory_hours <= 0:
                continue
            
            # Get teacher for this subject
            teacher = self._select_teacher_for_subject(subject, teachers, section)
            
            # Create list of available slots
            available_slots = []
            for day in days:
                for period in periods:
                    if period not in break_periods and (day, period) not in occupied_slots:
                        available_slots.append((day, period))
            
            # Integrated course rule: if subject had a lab block, try to avoid placing theory on the same day if possible
            subject_lab_day = lab_days_for_subject.get(subject.id)
            
            # Shuffle for randomization
            random.shuffle(available_slots)
            
            # Prefer days other than lab day for integrated courses
            if subject_lab_day:
                available_slots.sort(key=lambda slot: 1 if slot[0] == subject_lab_day else 0)
            
            # Track days used for distribution
            days_used = set()
            assigned_hours = 0
            
            for slot_day, slot_period in available_slots:
                if assigned_hours >= theory_hours:
                    break
                
                slot_key = (slot_day, slot_period)
                
                # Check room availability
                if hall and hall in room_assignments.get(slot_key, set()):
                    continue
                
                # Check if teacher is available (if teacher exists)
                if teacher and not teacher.is_available(slot_day, slot_period):
                    continue
                
                # Check if teacher is already assigned to this slot
                if teacher:
                    teacher_assigned_to_slot = teacher_assignments.get(slot_key, set())
                    if teacher.id in teacher_assigned_to_slot:
                        continue
                    
                    # Check teacher workload constraints
                    daily_hours = sum(1 for entry in entries 
                                     if entry.get('teacher_id') == teacher.id 
                                     and entry.get('day') == slot_day
                                     and not entry.get('is_break', False))
                    
                    if hasattr(teacher, 'max_hours_per_day') and teacher.max_hours_per_day:
                        if daily_hours + 1 > teacher.max_hours_per_day:
                            continue
                    
                    weekly_hours = sum(1 for entry in entries 
                                      if entry.get('teacher_id') == teacher.id
                                      and not entry.get('is_break', False))
                    
                    if hasattr(teacher, 'max_hours_per_week') and teacher.max_hours_per_week:
                        if weekly_hours + 1 > teacher.max_hours_per_week:
                            continue
                
                # Prevent consecutive periods for same subject (except lab blocks)
                if self.config.max_consecutive_same_subject > 0:
                    has_adjacent_slot = False
                    for entry in entries:
                        if (entry.get('day') == slot_day and 
                            entry.get('subject_id') == subject.id and
                            abs(entry.get('period', 0) - slot_period) == 1 and
                            not entry.get('is_lab_block', False)):
                            has_adjacent_slot = True
                            break
                    
                    if has_adjacent_slot:
                        continue
                
                # Prefer to spread across different days (if configured)
                if self.config.prefer_day_distribution:
                    if slot_day in days_used and len(days_used) < min(theory_hours, len(days)):
                        has_unused_day_available = any(
                            d != slot_day and d not in days_used and
                            any(p for p in periods if p not in break_periods and (d, p) not in occupied_slots)
                            for d in days
                        )
                        if has_unused_day_available:
                            continue
                
                # Assign subject to this slot
                entry = {
                    'day': slot_day,
                    'period': slot_period,
                    'subject_id': subject.id,
                    'teacher_id': teacher.id if teacher else None,
                    'hall': hall,
                    'is_lab_block': False,
                    'lab_block_position': None,
                    'lab_block_id': None,
                    'is_break': False
                }
                entries.append(entry)
                
                # Mark slot as occupied
                occupied_slots.add(slot_key)
                
                # Track teacher & room assignments
                if teacher:
                    teacher_assignments.setdefault(slot_key, set()).add(teacher.id)
                if hall:
                    room_assignments.setdefault(slot_key, set()).add(hall)
                
                # Track day usage
                days_used.add(slot_day)
                assigned_hours += 1
        
        # PHASE 3: Fill empty slots (if any remain)
        empty_slots = self._find_empty_slots(entries, days, periods, break_periods)
        if empty_slots:
            self._fill_empty_slots(
                empty_slots, subjects, teachers, entries, 
                occupied_slots, teacher_assignments, hall, days,
                room_assignments=room_assignments
            )
        
        # Validate complete filling if required
        if self.config.require_complete_filling:
            remaining_empty_slots = self._find_empty_slots(entries, days, periods, break_periods)
            if remaining_empty_slots:
                # Calculate total subject hours
                total_subject_hours = sum(s.credits for s in subjects if s.credits > 0)
                total_slots = len(days) * len([p for p in periods if p not in break_periods])
                
                error = ErrorReporter.insufficient_hours_error(
                    total_slots=len(days) * len(periods),
                    break_slots=len(break_periods),
                    available_slots=total_slots,
                    total_subject_hours=total_subject_hours,
                    deficit=len(remaining_empty_slots),
                    subjects=subjects
                )
                print(str(error))
                return None
        
        # Add break entries based on configuration
        # Note: Break entries also include lab block fields for consistency
        for day in days:
            for period, break_name in break_periods.items():
                entries.append({
                    'day': day,
                    'period': period,
                    'subject_id': None,
                    'teacher_id': None,
                    'hall': None,
                    'is_lab_block': False,  # Breaks are never lab blocks
                    'lab_block_position': None,
                    'lab_block_id': None,
                    'is_break': True,
                    'break_type': break_name.lower()
                })
        
        timetable.entries_data = entries
        
        # Validate class teacher assignment
        if section:
            self._validate_class_teacher_assignment(section, entries)
        
        # Generate and store timings
        timings = self._generate_timings(time_config, break_periods)
        timetable.timings = timings
        timetable.time_config = time_config
        
        return timetable
    
    def _generate_timings(self, time_config: dict, break_periods: dict) -> dict:
        """Generate time labels for each period slot.
        
        This method is backward compatible and works with both legacy timetables
        (theory subjects only) and new timetables (with lab blocks). It generates
        time labels based on the time configuration regardless of subject types.
        
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
        
        if not breaks_with_time and breaks_config:
            direct_breaks = {}
            for b in breaks_config:
                if 'period' in b:
                    direct_breaks[int(b['period'])] = b.get('name', 'Break')
            if direct_breaks:
                return direct_breaks
        
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
    
    def _find_empty_slots(self, entries: List[Dict], days: List[str], 
                          periods: List[int], break_periods: Dict[int, str]) -> List[Tuple[str, int]]:
        """Find all empty (unfilled) non-break time slots in the timetable.
        
        Args:
            entries: Current timetable entries
            days: List of days in the timetable
            periods: List of all period numbers
            break_periods: Dict mapping period numbers to break names
            
        Returns:
            List of (day, period) tuples representing empty slots
        """
        # Create set of all occupied slots
        occupied = set()
        for entry in entries:
            if not entry.get('is_break', False):
                occupied.add((entry['day'], entry['period']))
        
        # Find all non-break slots that are not occupied
        empty_slots = []
        for day in days:
            for period in periods:
                # Skip break periods
                if period in break_periods:
                    continue
                
                # Check if slot is empty
                if (day, period) not in occupied:
                    empty_slots.append((day, period))
        
        return empty_slots
    
    def _fill_empty_slots(self, empty_slots: List[Tuple[str, int]],
                         subjects: List[Subject], teachers: List[Teacher],
                         entries: List[Dict], occupied_slots: set,
                         teacher_assignments: Dict[Tuple[str, int], set],
                         hall: str, days: List[str],
                         room_assignments: Optional[Dict[Tuple[str, int], set]] = None) -> None:
        """Fill empty slots with subjects that need more hours, guaranteeing no empty/gap slots remain.
        
        Strategy:
        1. Calculate hour deficit for each subject (required hours - assigned hours)
        2. Sort subjects by deficit (descending) to prioritize those needing more hours
        3. Pass 1: Strict constraints (teacher workload, consecutive check, day distribution, room check)
        4. Pass 2: Relaxed workload & distribution (teacher availability, room availability, no teacher double-booking)
        5. Pass 3: Fallback filling (guarantees every single slot is filled, no '-' free periods left)
        
        Args:
            empty_slots: List of (day, period) tuples for empty slots
            subjects: List of all subjects
            teachers: List of all teachers
            entries: Current timetable entries (modified in place)
            occupied_slots: Set of occupied (day, period) tuples (modified in place)
            teacher_assignments: Dict tracking teacher assignments (modified in place)
            hall: Hall name to use for new entries
            days: List of days in the timetable
            room_assignments: Dict tracking room assignments across timetables (modified in place)
        """
        if room_assignments is None:
            room_assignments = {}
            
        # Calculate current hours for each subject
        subject_hours = {}
        for subject in subjects:
            assigned = sum(1 for entry in entries 
                          if entry.get('subject_id') == subject.id and not entry.get('is_break', False))
            
            # Required hours based on weekly_hours
            required = subject.weekly_hours
            
            subject_hours[subject.id] = {
                'subject': subject,
                'assigned': assigned,
                'required': required,
                'deficit': required - assigned
            }
        
        # Pre-assign teachers to subjects to avoid re-selection for each slot
        subject_teacher_map = {}
        for info in subject_hours.values():
            subject = info['subject']
            teacher = self._select_teacher_for_subject(subject, teachers, None)
            subject_teacher_map[subject.id] = teacher
            
        # Try to fill each empty slot
        for slot_day, slot_period in empty_slots:
            slot_key = (slot_day, slot_period)
            if slot_key in occupied_slots:
                continue
                
            slot_filled = False
            
            # Create a prioritized list of subjects for THIS slot
            candidates = []
            for info in subject_hours.values():
                subject = info['subject']
                # Determine priority:
                # Priority 1: Has real deficit (credits/weekly_hours > assigned) -> 1000 + deficit
                # Priority 2: Zero credit course that has 0 assigned -> 500
                # Priority 3: Zero credit course that has >0 assigned -> 200 - assigned
                # Priority 4: Normal course that already met required -> 50 - assigned (to balance)
                if info['required'] > info['assigned']:
                    score = 1000 + (info['required'] - info['assigned'])
                elif subject.credits == 0 and info['assigned'] == 0:
                    score = 500
                elif subject.credits == 0:
                    score = 200 - info['assigned']
                else:
                    score = 50 - info['assigned']
                    
                candidates.append((score, info))
                
            candidates.sort(key=lambda x: x[0], reverse=True)
            
            # Three passes:
            # Pass 1: Strict constraints (workload, consecutive periods, day distribution, room check)
            # Pass 2: Relaxed constraints (teacher availability, room availability, no teacher double-booking)
            # Pass 3: Fallback guarantee (fill slot with any available subject so no empty '-' slot remains)
            
            for pass_num in [1, 2, 3]:
                if slot_filled:
                    break
                    
                for score, subject_info in candidates:
                    subject = subject_info['subject']
                    teacher = subject_teacher_map.get(subject.id)
                    
                    # In Pass 1 and 2, check room availability
                    if hall and room_assignments and pass_num in [1, 2]:
                        if hall in room_assignments.get(slot_key, set()):
                            continue
                    
                    # Teacher checks
                    if teacher:
                        if not teacher.is_available(slot_day, slot_period):
                            if pass_num < 3:
                                continue
                            else:
                                teacher = None
                        
                        if teacher:
                            teacher_assigned_to_slot = teacher_assignments.get(slot_key, set())
                            if teacher.id in teacher_assigned_to_slot:
                                if pass_num < 3:
                                    continue
                                else:
                                    teacher = None
                    
                    # Workload & distribution constraints (pass 1 only)
                    if teacher and pass_num == 1:
                        daily_hours = sum(1 for entry in entries 
                                         if entry.get('teacher_id') == teacher.id 
                                         and entry.get('day') == slot_day
                                         and not entry.get('is_break', False))
                        
                        if hasattr(teacher, 'max_hours_per_day') and teacher.max_hours_per_day:
                            if daily_hours + 1 > teacher.max_hours_per_day:
                                continue
                        
                        weekly_hours = sum(1 for entry in entries 
                                          if entry.get('teacher_id') == teacher.id
                                          and not entry.get('is_break', False))
                        
                        if hasattr(teacher, 'max_hours_per_week') and teacher.max_hours_per_week:
                            if weekly_hours + 1 > teacher.max_hours_per_week:
                                continue
                        
                        if self.config.max_consecutive_same_subject > 0:
                            has_adjacent_slot = False
                            for entry in entries:
                                if (entry.get('day') == slot_day and 
                                    entry.get('subject_id') == subject.id and
                                    abs(entry.get('period', 0) - slot_period) == 1 and
                                    not entry.get('is_lab_block', False)):
                                    has_adjacent_slot = True
                                    break
                            
                            if has_adjacent_slot:
                                continue
                        
                        if self.config.prefer_day_distribution:
                            days_used = set(entry.get('day') for entry in entries 
                                           if entry.get('subject_id') == subject.id 
                                           and not entry.get('is_break', False))
                            
                            if slot_day in days_used:
                                unused_days = set(days) - days_used
                                if unused_days and subject_info['deficit'] > 1:
                                    has_slots_on_unused_days = any(
                                        (d, p) in empty_slots and d in unused_days 
                                        for d, p in empty_slots
                                    )
                                    if has_slots_on_unused_days:
                                        continue
                    
                    # All checks passed for this candidate - assign to slot
                    entry = {
                        'day': slot_day,
                        'period': slot_period,
                        'subject_id': subject.id,
                        'teacher_id': teacher.id if teacher else None,
                        'hall': hall,
                        'is_lab_block': False,
                        'lab_block_position': None,
                        'lab_block_id': None,
                        'is_break': False
                    }
                    entries.append(entry)
                    occupied_slots.add(slot_key)
                    
                    if teacher:
                        teacher_assignments.setdefault(slot_key, set()).add(teacher.id)
                    if hall:
                        room_assignments.setdefault(slot_key, set()).add(hall)
                    
                    subject_info['assigned'] += 1
                    subject_info['deficit'] -= 1
                    slot_filled = True
                    break
    
    def _filter_subjects_for_section(self, subjects: List[Subject], section: Section) -> List[Subject]:
        """Filter subjects that are relevant for a specific section"""
        # For now, return all subjects
        # In the future, this could filter based on section-specific assignments
        return subjects
    
    def _select_teacher_for_subject(self, subject: Subject, all_teachers: List[Teacher], section: Optional[Section] = None) -> Optional[Teacher]:
        """Select an appropriate teacher for a subject, considering multi-teacher assignments.
        
        This method is backward compatible and works with all subject types (theory, lab, integrated).
        It does not need special handling for lab blocks as teacher selection is independent of
        whether the subject requires consecutive slots.
        
        For multi-section generation, this tries to assign different teachers to different sections
        when multiple teachers are available for a subject.
        
        IMPORTANT: Prioritizes class teacher to ensure they teach at least one subject to their section.
        
        Args:
            subject: The subject to assign a teacher for (any type: theory, lab, or integrated)
            all_teachers: List of all available teachers
            section: The section being generated (None for single timetable)
            
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
        
        # PRIORITY: If section has a class teacher, check if they can teach this subject
        class_teacher_id = None
        if section and hasattr(section, 'class_teacher_id') and section.class_teacher_id:
            class_teacher_id = section.class_teacher_id
        elif section and hasattr(section, 'classTeacherId') and section.classTeacherId:
            class_teacher_id = section.classTeacherId
        
        # Check if class teacher needs to be assigned to this section
        if class_teacher_id and section:
            section_key = f"section_{section.id}_class_teacher_assigned"
            class_teacher_assigned = getattr(self, section_key, False)
            
            # If class teacher is eligible and hasn't been assigned yet, prioritize them
            if not class_teacher_assigned and class_teacher_id in eligible_teacher_ids:
                class_teacher = next((t for t in eligible_teachers if t.id == class_teacher_id), None)
                if class_teacher:
                    # Mark that class teacher has been assigned to this section
                    setattr(self, section_key, True)
                    
                    # Track usage
                    if subject.id not in self.subject_teacher_tracker:
                        self.subject_teacher_tracker[subject.id] = []
                    self.subject_teacher_tracker[subject.id].append(class_teacher.id)
                    
                    return class_teacher
        
        # If only one teacher available, use it
        if len(eligible_teachers) == 1:
            selected_teacher = eligible_teachers[0]
        else:
            # Multiple teachers available - try to distribute across sections
            used_teachers = self.subject_teacher_tracker.get(subject.id, [])
            
            # Find teachers not yet used for this subject
            available_teachers = [t for t in eligible_teachers if t.id not in used_teachers]
            
            if available_teachers:
                # Select a teacher that hasn't been used yet
                selected_teacher = random.choice(available_teachers)
            else:
                # All teachers have been used, select one with least usage
                # For now, just pick randomly from eligible teachers
                selected_teacher = random.choice(eligible_teachers)
        
        # Track usage
        if subject.id not in self.subject_teacher_tracker:
            self.subject_teacher_tracker[subject.id] = []
        self.subject_teacher_tracker[subject.id].append(selected_teacher.id)
        
        return selected_teacher
    
    def _validate_class_teacher_assignment(self, section: Section, entries: List[Dict]) -> None:
        """Validate that the class teacher teaches at least one subject to their section.
        
        Args:
            section: The section to validate
            entries: List of timetable entries
        """
        # Get class teacher ID
        class_teacher_id = None
        if hasattr(section, 'class_teacher_id') and section.class_teacher_id:
            class_teacher_id = section.class_teacher_id
        elif hasattr(section, 'classTeacherId') and section.classTeacherId:
            class_teacher_id = section.classTeacherId
        
        if not class_teacher_id:
            # No class teacher assigned, skip validation
            return
        
        # Check if class teacher appears in any entry
        class_teacher_assigned = any(
            entry.get('teacher_id') == class_teacher_id and not entry.get('is_break', False)
            for entry in entries
        )
        
        if not class_teacher_assigned:
            # Log warning but don't fail generation
            print(f"⚠️  Warning: Class teacher (ID: {class_teacher_id}) for section '{section.name}' "
                  f"is not teaching any subject. Consider assigning them to at least one subject.")
        else:
            # Count how many subjects the class teacher is teaching
            subject_count = sum(
                1 for entry in entries 
                if entry.get('teacher_id') == class_teacher_id and not entry.get('is_break', False)
            )
            print(f"✅ Class teacher (ID: {class_teacher_id}) for section '{section.name}' "
                  f"is teaching {subject_count} subject(s).")
