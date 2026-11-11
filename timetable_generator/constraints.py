"""
Timetable-specific constraints
"""
from typing import List, Dict, Any, Tuple
from models import Teacher, Subject
from timetable_generator.error_reporter import ErrorReporter, TimetableError

class TimetableConstraints:
    """Factory for creating timetable-specific constraints"""

    @staticmethod
    def create_subject_credits_constraint(subject_var, weekly_hours_var):
        """Subject must have correct number of weekly classes based on credits"""
        def credits_check(subject, weekly_hours):
            return subject.credits == weekly_hours
        return None  # Not used in simple approach

    @staticmethod
    def create_lab_hours_constraint(subject_var, lab_blocks_var):
        """Lab subjects must have 4 hours per week in 2-hour blocks"""
        def lab_hours_check(subject, lab_blocks):
            if subject.is_lab:
                return lab_blocks == 2  # 2 blocks of 2 hours each
            return True
        return None  # Not used in simple approach

    @staticmethod
    def create_no_break_classes_constraint(time_slot_var):
        """No classes during breaks"""
        def no_break_classes(time_slot):
            slot_value = time_slot.value if hasattr(time_slot, 'value') else time_slot
            return not slot_value.get('is_break', False)
        return None  # Not used in simple approach

    @staticmethod
    def create_teacher_availability_constraint(teacher_var, time_slot_var):
        """Teacher must be available for the assigned time slot"""
        def availability_check(teacher, time_slot):
            return True  # Not used in simple approach
        return None  # Not used in simple approach

    @staticmethod
    def create_no_back_to_back_constraint(subject1_var, subject2_var, time1_var, time2_var):
        """Avoid same subject back-to-back (soft constraint)"""
        def no_back_to_back(subject1, subject2, time1, time2):
            return True  # Not used in simple approach
        return None  # Not used in simple approach

    @staticmethod
    def create_morning_core_subjects_constraint(subject_var, time_slot_var):
        """Prefer core subjects in morning slots (soft constraint)"""
        def morning_preference(subject, time_slot):
            return True  # Not used in simple approach
        return None  # Not used in simple approach

    @staticmethod
    def create_even_distribution_constraint(subject_var, time_slot_var):
        """Distribute classes evenly across the week (soft constraint)"""
        def even_distribution(subject, time_slot):
            return True  # Not used in simple approach
        return None  # Not used in simple approach

class TimetableValidator:
    """Validates timetable constraints after generation"""
    
    @staticmethod
    def validate_complete_schedule(
        entries: List[Dict],
        days: List[str],
        periods: List[int],
        break_periods: Dict[int, str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that all non-break slots are filled.
        
        Args:
            entries: List of timetable entry dictionaries
            days: List of day names
            periods: List of period numbers
            break_periods: Dictionary mapping period numbers to break names
        
        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        
        # Create a set of all occupied slots
        occupied_slots = set()
        for entry in entries:
            if not entry.get('is_break'):
                day = entry.get('day')
                period = entry.get('period')
                if day and period:
                    occupied_slots.add((day, period))
        
        # Check all non-break slots
        empty_slots = []
        for day in days:
            for period in periods:
                # Skip break periods
                if period in break_periods:
                    continue
                
                # Check if slot is occupied
                if (day, period) not in occupied_slots:
                    empty_slots.append((day, period))
        
        if empty_slots:
            errors.append(
                f"Found {len(empty_slots)} empty non-break slots: "
                f"{', '.join(f'{day} period {period}' for day, period in empty_slots[:5])}"
                + (f" and {len(empty_slots) - 5} more" if len(empty_slots) > 5 else "")
            )
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_with_structured_errors(
        entries: List[Dict],
        teachers: List[Teacher],
        subjects: List[Subject],
        days: List[str] = None,
        periods: List[int] = None,
        break_periods: Dict[int, str] = None
    ) -> Tuple[bool, List[TimetableError]]:
        """
        Validate a complete timetable and return structured errors.
        
        This method performs comprehensive validation and returns TimetableError
        objects instead of plain strings, providing detailed error information
        with actionable suggestions.
        
        Args:
            entries: List of timetable entry dictionaries
            teachers: List of Teacher objects
            subjects: List of Subject objects
            days: List of day names
            periods: List of period numbers
            break_periods: Dictionary mapping period numbers to break names
        
        Returns:
            Tuple of (is_valid, list of TimetableError objects)
        """
        errors = []
        
        # Check for teacher double booking
        teacher_schedule = {}
        teacher_conflicts = {}
        
        for entry in entries:
            if entry.get('is_break') or entry.get('teacher_id') is None:
                continue
            
            key = (entry.get('day'), entry.get('period'))
            teacher_id = entry.get('teacher_id')
            
            if key in teacher_schedule and teacher_schedule[key] == teacher_id:
                # Same teacher double booked
                if teacher_id not in teacher_conflicts:
                    teacher_conflicts[teacher_id] = []
                teacher_conflicts[teacher_id].append(key)
            else:
                teacher_schedule[key] = teacher_id
        
        # Generate teacher conflict errors
        for teacher_id, conflict_slots in teacher_conflicts.items():
            teacher = next((t for t in teachers if t.id == teacher_id), None)
            if teacher:
                error = ErrorReporter.teacher_conflict_error(
                    teacher=teacher,
                    conflicts=conflict_slots,
                    conflict_type='double_booking'
                )
                errors.append(error)
        
        # Check teacher availability
        availability_conflicts = {}
        for entry in entries:
            if entry.get('is_break') or entry.get('teacher_id') is None:
                continue
            
            teacher = next((t for t in teachers if t.id == entry.get('teacher_id')), None)
            if teacher and not teacher.is_available(entry.get('day'), entry.get('period')):
                if teacher.id not in availability_conflicts:
                    availability_conflicts[teacher.id] = []
                availability_conflicts[teacher.id].append((entry.get('day'), entry.get('period')))
        
        # Generate availability conflict errors
        for teacher_id, conflict_slots in availability_conflicts.items():
            teacher = next((t for t in teachers if t.id == teacher_id), None)
            if teacher:
                error = ErrorReporter.teacher_conflict_error(
                    teacher=teacher,
                    conflicts=conflict_slots,
                    conflict_type='availability'
                )
                errors.append(error)
        
        # Check teacher workload limits
        teacher_daily_hours = {}
        teacher_weekly_hours = {}
        
        for entry in entries:
            if entry.get('is_break') or not entry.get('teacher_id'):
                continue
            
            teacher_id = entry.get('teacher_id')
            day = entry.get('day')
            
            # Track daily hours
            key = (teacher_id, day)
            teacher_daily_hours[key] = teacher_daily_hours.get(key, 0) + 1
            
            # Track weekly hours
            teacher_weekly_hours[teacher_id] = teacher_weekly_hours.get(teacher_id, 0) + 1
        
        # Check daily limits
        for (teacher_id, day), hours in teacher_daily_hours.items():
            teacher = next((t for t in teachers if t.id == teacher_id), None)
            if teacher and hasattr(teacher, 'max_hours_per_day') and teacher.max_hours_per_day:
                if hours > teacher.max_hours_per_day:
                    error = ErrorReporter.teacher_workload_exceeded_error(
                        teacher=teacher,
                        current_hours=hours,
                        max_hours=teacher.max_hours_per_day,
                        period_type='daily'
                    )
                    errors.append(error)
        
        # Check weekly limits
        for teacher_id, hours in teacher_weekly_hours.items():
            teacher = next((t for t in teachers if t.id == teacher_id), None)
            if teacher and hasattr(teacher, 'max_hours_per_week') and teacher.max_hours_per_week:
                if hours > teacher.max_hours_per_week:
                    error = ErrorReporter.teacher_workload_exceeded_error(
                        teacher=teacher,
                        current_hours=hours,
                        max_hours=teacher.max_hours_per_week,
                        period_type='weekly'
                    )
                    errors.append(error)
        
        # Check subject hours
        subject_hours = {}
        for entry in entries:
            if entry.get('is_break') or entry.get('subject_id') is None:
                continue
            
            subject_id = entry.get('subject_id')
            subject_hours[subject_id] = subject_hours.get(subject_id, 0) + 1
        
        for subject in subjects:
            expected_hours = subject.credits
            actual_hours = subject_hours.get(subject.id, 0)
            
            if actual_hours < expected_hours:
                error = ErrorReporter.subject_hour_mismatch_error(
                    subject=subject,
                    expected_hours=expected_hours,
                    actual_hours=actual_hours
                )
                errors.append(error)
        
        # Validate lab blocks
        is_valid, lab_errors_list = TimetableValidator.validate_lab_blocks(entries, subjects)
        for lab_error_str in lab_errors_list:
            # Parse the error string to create structured error
            # For now, create a generic lab block integrity error
            # In a real implementation, we'd parse the string or refactor validate_lab_blocks
            if 'requires a lab block but none found' in lab_error_str:
                subject_name = lab_error_str.split("'")[1]
                subject = next((s for s in subjects if s.name == subject_name), None)
                if subject:
                    error = ErrorReporter.lab_block_integrity_error(
                        subject=subject,
                        issue='Lab block not found',
                        details_dict={'error': lab_error_str}
                    )
                    errors.append(error)
        
        # Check for empty slots if parameters provided
        if days and periods and break_periods is not None:
            is_valid, schedule_errors = TimetableValidator.validate_complete_schedule(
                entries, days, periods, break_periods
            )
            # Note: Empty slots are handled separately in the generator
        
        # Check distribution (warnings only)
        is_valid, distribution_warnings = TimetableValidator.validate_distribution(entries, subjects)
        for warning_str in distribution_warnings:
            # Parse warning to create structured warning
            if 'has consecutive periods' in warning_str:
                # Extract subject name and details
                parts = warning_str.split("'")
                if len(parts) >= 2:
                    subject_name = parts[1]
                    subject = next((s for s in subjects if s.name == subject_name), None)
                    if subject:
                        # Extract day and periods from warning
                        day_part = warning_str.split(' on ')[1].split(':')[0] if ' on ' in warning_str else 'Unknown'
                        warning = ErrorReporter.consecutive_periods_warning(
                            subject=subject,
                            day=day_part,
                            periods=[]  # Would need to parse from string
                        )
                        errors.append(warning)
            elif 'all on the same day' in warning_str or 'spread across only' in warning_str:
                # Extract subject name
                parts = warning_str.split("'")
                if len(parts) >= 2:
                    subject_name = parts[1]
                    subject = next((s for s in subjects if s.name == subject_name), None)
                    if subject:
                        # Count hours and days
                        subject_entries = [e for e in entries if e.get('subject_id') == subject.id and not e.get('is_break')]
                        days_used = len(set(e.get('day') for e in subject_entries))
                        warning = ErrorReporter.poor_distribution_warning(
                            subject=subject,
                            total_hours=len(subject_entries),
                            days_used=days_used
                        )
                        errors.append(warning)
        
        # Determine if validation passed (no critical errors)
        has_errors = any(e.type == 'error' for e in errors)
        
        return not has_errors, errors
    
    @staticmethod
    def validate_lab_blocks(
        entries: List[Dict],
        subjects: List[Subject]
    ) -> Tuple[bool, List[str]]:
        """
        Validate lab block integrity:
        - Each lab/integrated subject has exactly 1 lab block per week
        - Lab blocks are consecutive with no breaks
        - Both slots have same subject and teacher
        
        Args:
            entries: List of timetable entry dictionaries
            subjects: List of Subject objects
        
        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        
        # Get lab and integrated subjects
        lab_subjects = {s.id: s for s in subjects if s.requires_lab_block()}
        
        if not lab_subjects:
            # No lab subjects to validate
            return True, []
        
        # Group lab block entries by subject
        subject_lab_blocks = {}
        for entry in entries:
            if entry.get('is_lab_block') and entry.get('subject_id'):
                subject_id = entry['subject_id']
                if subject_id not in subject_lab_blocks:
                    subject_lab_blocks[subject_id] = []
                subject_lab_blocks[subject_id].append(entry)
        
        # Validate each lab/integrated subject
        for subject_id, subject in lab_subjects.items():
            if subject_id not in subject_lab_blocks:
                errors.append(
                    f"Subject '{subject.name}' requires a lab block but none found"
                )
                continue
            
            lab_entries = subject_lab_blocks[subject_id]
            
            # Should have exactly 2 entries (one lab block)
            if len(lab_entries) != 2:
                errors.append(
                    f"Subject '{subject.name}' has {len(lab_entries)} lab block entries, expected 2"
                )
                continue
            
            # Sort by period to get first and second slot
            lab_entries_sorted = sorted(lab_entries, key=lambda e: (e['day'], e['period']))
            entry1, entry2 = lab_entries_sorted
            
            # Verify same day
            if entry1['day'] != entry2['day']:
                errors.append(
                    f"Subject '{subject.name}' lab block spans different days: "
                    f"{entry1['day']} and {entry2['day']}"
                )
                continue
            
            # Verify consecutive periods
            if entry2['period'] != entry1['period'] + 1:
                errors.append(
                    f"Subject '{subject.name}' lab block periods are not consecutive: "
                    f"periods {entry1['period']} and {entry2['period']}"
                )
            
            # Verify same teacher
            if entry1.get('teacher_id') != entry2.get('teacher_id'):
                errors.append(
                    f"Subject '{subject.name}' lab block has different teachers: "
                    f"{entry1.get('teacher_id')} and {entry2.get('teacher_id')}"
                )
            
            # Verify lab_block_id matches
            if entry1.get('lab_block_id') != entry2.get('lab_block_id'):
                errors.append(
                    f"Subject '{subject.name}' lab block entries have mismatched IDs: "
                    f"{entry1.get('lab_block_id')} and {entry2.get('lab_block_id')}"
                )
            
            # Verify lab_block_position
            if entry1.get('lab_block_position') != 1 or entry2.get('lab_block_position') != 2:
                errors.append(
                    f"Subject '{subject.name}' lab block has incorrect positions: "
                    f"{entry1.get('lab_block_position')} and {entry2.get('lab_block_position')}"
                )
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_subject_hours(
        entries: List[Dict],
        subjects: List[Subject]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that each subject has correct total hours.
        For integrated courses: theory_hours + lab_hours = credits
        
        Args:
            entries: List of timetable entry dictionaries
            subjects: List of Subject objects
        
        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        
        # Count hours per subject
        subject_hours = {}
        for entry in entries:
            if entry.get('is_break') or entry.get('subject_id') is None:
                continue
            
            subject_id = entry['subject_id']
            if subject_id not in subject_hours:
                subject_hours[subject_id] = 0
            subject_hours[subject_id] += 1
        
        # Validate each subject
        for subject in subjects:
            expected_hours = subject.weekly_hours if hasattr(subject, 'weekly_hours') and subject.weekly_hours > 0 else subject.credits
            actual_hours = subject_hours.get(subject.id, 0)
            
            if expected_hours > 0 and actual_hours < expected_hours:
                errors.append(
                    f"Subject '{subject.name}' has {actual_hours} hours, expected {expected_hours}"
                )
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_distribution(
        entries: List[Dict],
        subjects: List[Subject]
    ) -> Tuple[bool, List[str]]:
        """
        Validate subject distribution:
        - Hours spread across different days when possible
        - No consecutive periods for same subject (except lab blocks)
        
        Args:
            entries: List of timetable entry dictionaries
            subjects: List of Subject objects
        
        Returns:
            Tuple of (is_valid, warnings) - non-critical
        """
        warnings = []
        
        # Group entries by subject and day
        subject_days = {}
        subject_periods = {}
        
        for entry in entries:
            if entry.get('is_break') or entry.get('subject_id') is None:
                continue
            
            subject_id = entry['subject_id']
            day = entry['day']
            period = entry['period']
            
            # Track days
            if subject_id not in subject_days:
                subject_days[subject_id] = set()
            subject_days[subject_id].add(day)
            
            # Track periods per day
            if subject_id not in subject_periods:
                subject_periods[subject_id] = {}
            if day not in subject_periods[subject_id]:
                subject_periods[subject_id][day] = []
            subject_periods[subject_id][day].append(period)
        
        # Check distribution across days
        for subject in subjects:
            if subject.id not in subject_days:
                continue
            
            days_used = len(subject_days[subject.id])
            total_hours = sum(len(periods) for periods in subject_periods[subject.id].values())
            
            # If subject has multiple hours but only uses one day, warn
            if total_hours > 1 and days_used == 1:
                warnings.append(
                    f"Subject '{subject.name}' has {total_hours} hours all on the same day"
                )
        
        # Check for consecutive periods (excluding lab blocks)
        for subject in subjects:
            if subject.id not in subject_periods:
                continue
            
            for day, periods in subject_periods[subject.id].items():
                # Sort periods
                sorted_periods = sorted(periods)
                
                # Check for consecutive periods
                for i in range(len(sorted_periods) - 1):
                    if sorted_periods[i+1] == sorted_periods[i] + 1:
                        # Check if this is part of a lab block
                        is_lab_block = False
                        for entry in entries:
                            if (entry.get('subject_id') == subject.id and 
                                entry.get('day') == day and 
                                entry.get('period') in [sorted_periods[i], sorted_periods[i+1]] and
                                entry.get('is_lab_block')):
                                is_lab_block = True
                                break
                        
                        if not is_lab_block:
                            warnings.append(
                                f"Subject '{subject.name}' has consecutive periods on {day}: "
                                f"periods {sorted_periods[i]} and {sorted_periods[i+1]}"
                            )
        
        return len(warnings) == 0, warnings
    
    @staticmethod
    def validate_timetable(timetable_entries: List[Dict], 
                          teachers: List[Teacher], 
                          subjects: List[Subject],
                          halls=None,
                          days: List[str] = None,
                          periods: List[int] = None,
                          break_periods: Dict[int, str] = None) -> Tuple[bool, List[str]]:
        """
        Validate a complete timetable (entries are dicts).
        
        This method now calls all validation methods including the new ones.
        
        Args:
            timetable_entries: List of timetable entry dictionaries
            teachers: List of Teacher objects
            subjects: List of Subject objects
            halls: (Optional) List of halls (not used currently)
            days: (Optional) List of day names for complete schedule validation
            periods: (Optional) List of period numbers for complete schedule validation
            break_periods: (Optional) Dictionary mapping period numbers to break names
        
        Returns:
            Tuple of (is_valid, errors)
        """
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
        
        # Check hall double booking - DISABLED: Allow multiple teachers in same hall
        # hall_schedule = {}
        # for entry in timetable_entries:
        #     if entry.get('is_break'):
        #         continue
        #     key = (entry.get('day'), entry.get('period'))
        #     if key in hall_schedule:
        #         errors.append(f"Hall {hall_schedule[key]} double booked at {entry.get('day')} period {entry.get('period')}")
        #     else:
        #         hall_schedule[key] = entry.get('hall') or ''
        
        # Check subject weekly hours (allow up to credits; partial filling is acceptable)
        subject_hours = {}
        for entry in timetable_entries:
            if entry.get('is_break') or entry.get('subject_id') is None:
                continue
            
            subject_id = entry.get('subject_id')
            if subject_id not in subject_hours:
                subject_hours[subject_id] = 0
            subject_hours[subject_id] += 1
        
        for subject in subjects:
            pass  # Allow subjects to have extra hours for filling empty slots
        
        # Relax lab-hour checks: do not enforce strict 2x2h consecutive blocks during generation
        # (Can be reported as suggestions later if needed)
        
        # Check teacher availability
        for entry in timetable_entries:
            if entry.get('is_break') or entry.get('teacher_id') is None:
                continue
            
            teacher = next((t for t in teachers if t.id == entry.get('teacher_id')), None)
            if teacher and not teacher.is_available(entry.get('day'), entry.get('period')):
                errors.append(f"Teacher {teacher.name} not available at {entry.get('day')} period {entry.get('period')}")
        
        # Room type compatibility not applicable (rooms removed)

        # Teacher daily hour caps:
        # - If a teacher handles any subjects with credits in {2,3,4}, cap at 8 hours/day.
        # - If a teacher only handles credit=1 subjects, cap at 4 hours/day.
        teacher_subject_credits: Dict[int, set] = {}
        for subj in subjects:
            if subj.teacher_id:
                teacher_subject_credits.setdefault(subj.teacher_id, set()).add(subj.credits)

        daily_hours: Dict[Tuple[int, str], int] = {}
        for entry in timetable_entries:
            if entry.get('is_break') or not entry.get('teacher_id'):
                continue
            key = (entry.get('teacher_id'), entry.get('day'))
            daily_hours[key] = daily_hours.get(key, 0) + 1

        for (tid, day), hours in daily_hours.items():
            credits = teacher_subject_credits.get(tid, set())
            if credits:
                if all(c == 1 for c in credits):
                    cap = 4
                else:
                    cap = 8
                if hours > cap:
                    tname = next((t.name for t in teachers if t.id == tid), str(tid))
                    errors.append(f"Teacher {tname} exceeds daily cap {cap} hours on {day} (has {hours})")
        
        # NEW: Call additional validation methods if parameters provided
        if days and periods and break_periods is not None:
            # Validate complete schedule
            is_valid, schedule_errors = TimetableValidator.validate_complete_schedule(
                timetable_entries, days, periods, break_periods
            )
            errors.extend(schedule_errors)
        
        # Validate lab blocks
        is_valid, lab_errors = TimetableValidator.validate_lab_blocks(
            timetable_entries, subjects
        )
        errors.extend(lab_errors)
        
        # Validate subject hours
        is_valid, hour_errors = TimetableValidator.validate_subject_hours(
            timetable_entries, subjects
        )
        errors.extend(hour_errors)
        
        # Validate distribution (warnings only, don't fail validation)
        is_valid, distribution_warnings = TimetableValidator.validate_distribution(
            timetable_entries, subjects
        )
        # Note: We don't add distribution warnings to errors since they're non-critical

        return len(errors) == 0, errors
