"""
Comprehensive error reporting system for timetable generation.

This module provides structured error reporting with detailed messages,
error codes, and actionable suggestions for resolving issues.
"""
from typing import List, Dict, Any, Tuple, Optional, Set
from models import Subject, Teacher


class TimetableError:
    """Represents a timetable generation error or warning."""
    
    def __init__(self, 
                 error_type: str,
                 code: str,
                 message: str,
                 details: Dict[str, Any],
                 suggestions: List[str]):
        """
        Initialize a timetable error.
        
        Args:
            error_type: 'error' for critical errors, 'warning' for non-critical issues
            code: Error code (e.g., 'INSUFFICIENT_HOURS', 'NO_CONSECUTIVE_SLOTS')
            message: Human-readable description of the error
            details: Dictionary with specific error details
            suggestions: List of actionable recommendations
        """
        self.type = error_type
        self.code = code
        self.message = message
        self.details = details
        self.suggestions = suggestions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format."""
        return {
            'type': self.type,
            'code': self.code,
            'message': self.message,
            'details': self.details,
            'suggestions': self.suggestions
        }
    
    def __str__(self) -> str:
        """String representation of the error."""
        prefix = "❌ ERROR" if self.type == 'error' else "⚠️  WARNING"
        result = f"{prefix} [{self.code}]: {self.message}\n"
        
        if self.details:
            result += "Details:\n"
            for key, value in self.details.items():
                result += f"  - {key}: {value}\n"
        
        if self.suggestions:
            result += "Suggestions:\n"
            for suggestion in self.suggestions:
                result += f"  • {suggestion}\n"
        
        return result


class ErrorReporter:
    """Factory for creating structured timetable errors."""
    
    @staticmethod
    def insufficient_hours_error(
        total_slots: int,
        break_slots: int,
        available_slots: int,
        total_subject_hours: int,
        deficit: int,
        subjects: List[Subject]
    ) -> TimetableError:
        """
        Generate error for insufficient subject hours to fill all slots.
        
        Args:
            total_slots: Total number of time slots in the timetable
            break_slots: Number of break slots
            available_slots: Number of non-break slots
            total_subject_hours: Sum of all subject credits
            deficit: Number of unfilled slots
            subjects: List of all subjects
        
        Returns:
            TimetableError instance
        """
        # Calculate subject breakdown
        subject_breakdown = []
        for subject in subjects:
            if subject.credits > 0:
                subject_breakdown.append(f"{subject.name} ({subject.credits}h)")
        
        details = {
            'total_slots': total_slots,
            'break_slots': break_slots,
            'available_slots': available_slots,
            'total_subject_hours': total_subject_hours,
            'deficit': deficit,
            'subject_breakdown': ', '.join(subject_breakdown) if subject_breakdown else 'None'
        }
        
        suggestions = [
            f"Add {deficit} more hours of subjects to the curriculum",
            "Increase credits for existing subjects",
            "Reduce the number of teaching periods per day",
            "Add more break periods to reduce available teaching slots"
        ]
        
        message = (
            f"Cannot fill all time slots with available subjects. "
            f"Need {deficit} more subject hours to complete the timetable."
        )
        
        return TimetableError(
            error_type='error',
            code='INSUFFICIENT_HOURS',
            message=message,
            details=details,
            suggestions=suggestions
        )
    
    @staticmethod
    def no_consecutive_slots_error(
        affected_subjects: List[Subject],
        days: List[str],
        reason: str = 'All consecutive slot pairs are occupied or separated by breaks'
    ) -> TimetableError:
        """
        Generate error for inability to place lab blocks.
        
        Args:
            affected_subjects: List of lab/integrated subjects that couldn't be placed
            days: List of days checked
            reason: Specific reason why placement failed
        
        Returns:
            TimetableError instance
        """
        subject_names = [s.name for s in affected_subjects]
        
        details = {
            'affected_subjects': subject_names,
            'num_affected': len(affected_subjects),
            'days_checked': days,
            'reason': reason
        }
        
        suggestions = [
            "Reduce the number of subjects scheduled to free up consecutive slots",
            "Adjust break times to create more consecutive slot pairs",
            "Increase the number of teaching periods per day",
            "Consider converting some lab subjects to theory subjects if appropriate",
            "Reschedule breaks to different times to create consecutive teaching blocks"
        ]
        
        message = (
            f"Cannot place lab blocks for {len(affected_subjects)} subject(s): "
            f"{', '.join(subject_names)}. {reason}."
        )
        
        return TimetableError(
            error_type='error',
            code='NO_CONSECUTIVE_SLOTS',
            message=message,
            details=details,
            suggestions=suggestions
        )
    
    @staticmethod
    def teacher_conflict_error(
        teacher: Teacher,
        conflicts: List[Tuple[str, int]],
        conflict_type: str = 'double_booking'
    ) -> TimetableError:
        """
        Generate error for teacher scheduling conflicts.
        
        Args:
            teacher: Teacher with the conflict
            conflicts: List of (day, period) tuples where conflicts occur
            conflict_type: Type of conflict ('double_booking', 'availability', 'workload')
        
        Returns:
            TimetableError instance
        """
        conflict_descriptions = [f"{day} period {period}" for day, period in conflicts[:5]]
        if len(conflicts) > 5:
            conflict_descriptions.append(f"and {len(conflicts) - 5} more")
        
        details = {
            'teacher_name': teacher.name,
            'teacher_id': teacher.id,
            'conflict_type': conflict_type,
            'num_conflicts': len(conflicts),
            'conflict_slots': conflict_descriptions
        }
        
        if conflict_type == 'double_booking':
            message = f"Teacher {teacher.name} is double-booked at {len(conflicts)} time slot(s)"
            suggestions = [
                "Assign different teachers to some subjects",
                "Reduce the number of subjects this teacher handles",
                "Adjust the timetable to avoid overlapping assignments"
            ]
        elif conflict_type == 'availability':
            message = f"Teacher {teacher.name} is not available at {len(conflicts)} assigned time slot(s)"
            suggestions = [
                "Update teacher availability to include these time slots",
                "Assign a different teacher to subjects in these slots",
                "Reschedule these subjects to times when the teacher is available"
            ]
        elif conflict_type == 'workload':
            message = f"Teacher {teacher.name} exceeds workload limits at {len(conflicts)} time slot(s)"
            suggestions = [
                "Increase teacher's max_hours_per_day or max_hours_per_week limits",
                "Distribute subjects to other available teachers",
                "Reduce the number of subjects assigned to this teacher"
            ]
        else:
            message = f"Teacher {teacher.name} has scheduling conflicts at {len(conflicts)} time slot(s)"
            suggestions = [
                "Review teacher assignments and availability",
                "Adjust the timetable to resolve conflicts"
            ]
        
        return TimetableError(
            error_type='error',
            code='TEACHER_CONFLICT',
            message=message,
            details=details,
            suggestions=suggestions
        )
    
    @staticmethod
    def teacher_workload_exceeded_error(
        teacher: Teacher,
        current_hours: int,
        max_hours: int,
        period_type: str = 'weekly'
    ) -> TimetableError:
        """
        Generate error for teacher workload limit exceeded.
        
        Args:
            teacher: Teacher exceeding workload
            current_hours: Current assigned hours
            max_hours: Maximum allowed hours
            period_type: 'daily' or 'weekly'
        
        Returns:
            TimetableError instance
        """
        details = {
            'teacher_name': teacher.name,
            'teacher_id': teacher.id,
            'current_hours': current_hours,
            'max_hours': max_hours,
            'excess_hours': current_hours - max_hours,
            'period_type': period_type
        }
        
        message = (
            f"Teacher {teacher.name} has {current_hours} {period_type} hours, "
            f"exceeding the maximum of {max_hours} hours"
        )
        
        suggestions = [
            f"Increase teacher's max_hours_per_{period_type.replace('ly', '')} limit to at least {current_hours}",
            "Assign some subjects to other available teachers",
            f"Reduce the number of {period_type} hours for this teacher by {current_hours - max_hours}"
        ]
        
        return TimetableError(
            error_type='error',
            code='WORKLOAD_EXCEEDED',
            message=message,
            details=details,
            suggestions=suggestions
        )
    
    @staticmethod
    def partial_lab_block_warning(
        subject: Subject,
        reason: str = 'No consecutive slots available'
    ) -> TimetableError:
        """
        Generate warning for lab subject without complete lab block.
        
        Args:
            subject: Lab/integrated subject without lab block
            reason: Reason why lab block couldn't be placed
        
        Returns:
            TimetableError instance
        """
        details = {
            'subject_name': subject.name,
            'subject_id': subject.id,
            'subject_type': subject.subject_type,
            'reason': reason
        }
        
        message = f"Lab subject '{subject.name}' does not have a complete lab block. {reason}."
        
        suggestions = [
            "Enable 'require_complete_filling' to make this a critical error",
            "Adjust the timetable to create consecutive slots for this lab",
            "Consider rescheduling other subjects to free up consecutive slots"
        ]
        
        return TimetableError(
            error_type='warning',
            code='PARTIAL_LAB_BLOCK',
            message=message,
            details=details,
            suggestions=suggestions
        )
    
    @staticmethod
    def empty_slots_remaining_warning(
        empty_slots: List[Tuple[str, int]],
        subjects_at_capacity: List[Subject]
    ) -> TimetableError:
        """
        Generate warning for remaining empty slots after filling attempt.
        
        Args:
            empty_slots: List of (day, period) tuples that remain empty
            subjects_at_capacity: List of subjects that have reached their credit limit
        
        Returns:
            TimetableError instance
        """
        slot_descriptions = [f"{day} period {period}" for day, period in empty_slots[:5]]
        if len(empty_slots) > 5:
            slot_descriptions.append(f"and {len(empty_slots) - 5} more")
        
        subject_names = [s.name for s in subjects_at_capacity]
        
        details = {
            'num_empty_slots': len(empty_slots),
            'empty_slots': slot_descriptions,
            'subjects_at_capacity': subject_names,
            'num_subjects_at_capacity': len(subjects_at_capacity)
        }
        
        message = (
            f"{len(empty_slots)} time slot(s) remain empty. "
            f"All {len(subjects_at_capacity)} subject(s) have reached their credit limits."
        )
        
        suggestions = [
            "Increase credits for existing subjects to fill more slots",
            "Add additional subjects to the curriculum",
            "Enable 'require_complete_filling' to make this a critical error",
            "Reduce the number of teaching periods per day to match available subject hours"
        ]
        
        return TimetableError(
            error_type='warning',
            code='EMPTY_SLOTS_REMAINING',
            message=message,
            details=details,
            suggestions=suggestions
        )
    
    @staticmethod
    def subject_hour_mismatch_error(
        subject: Subject,
        expected_hours: int,
        actual_hours: int
    ) -> TimetableError:
        """
        Generate error for subject with incorrect total hours.
        
        Args:
            subject: Subject with hour mismatch
            expected_hours: Expected hours (from credits)
            actual_hours: Actual assigned hours
        
        Returns:
            TimetableError instance
        """
        details = {
            'subject_name': subject.name,
            'subject_id': subject.id,
            'expected_hours': expected_hours,
            'actual_hours': actual_hours,
            'difference': actual_hours - expected_hours
        }
        
        if actual_hours > expected_hours:
            message = (
                f"Subject '{subject.name}' has {actual_hours} hours assigned, "
                f"exceeding the expected {expected_hours} hours"
            )
            suggestions = [
                f"Reduce subject hours by {actual_hours - expected_hours}",
                f"Increase subject credits to {actual_hours} to match assigned hours"
            ]
        else:
            message = (
                f"Subject '{subject.name}' has only {actual_hours} hours assigned, "
                f"but requires {expected_hours} hours"
            )
            suggestions = [
                f"Add {expected_hours - actual_hours} more hours for this subject",
                f"Reduce subject credits to {actual_hours} to match assigned hours",
                "Enable empty slot filling to automatically assign remaining hours"
            ]
        
        return TimetableError(
            error_type='error',
            code='SUBJECT_HOUR_MISMATCH',
            message=message,
            details=details,
            suggestions=suggestions
        )
    
    @staticmethod
    def poor_distribution_warning(
        subject: Subject,
        total_hours: int,
        days_used: int
    ) -> TimetableError:
        """
        Generate warning for poor subject distribution across days.
        
        Args:
            subject: Subject with poor distribution
            total_hours: Total hours assigned
            days_used: Number of days the subject appears on
        
        Returns:
            TimetableError instance
        """
        details = {
            'subject_name': subject.name,
            'subject_id': subject.id,
            'total_hours': total_hours,
            'days_used': days_used
        }
        
        if days_used == 1:
            message = f"Subject '{subject.name}' has all {total_hours} hours on a single day"
        else:
            message = f"Subject '{subject.name}' has {total_hours} hours spread across only {days_used} day(s)"
        
        suggestions = [
            "Enable 'prefer_day_distribution' to spread subjects across more days",
            "Manually adjust the timetable to distribute hours more evenly",
            "Consider if concentrated scheduling is intentional for this subject"
        ]
        
        return TimetableError(
            error_type='warning',
            code='POOR_DISTRIBUTION',
            message=message,
            details=details,
            suggestions=suggestions
        )
    
    @staticmethod
    def consecutive_periods_warning(
        subject: Subject,
        day: str,
        periods: List[int]
    ) -> TimetableError:
        """
        Generate warning for consecutive periods of same subject (non-lab).
        
        Args:
            subject: Subject with consecutive periods
            day: Day where consecutive periods occur
            periods: List of consecutive period numbers
        
        Returns:
            TimetableError instance
        """
        details = {
            'subject_name': subject.name,
            'subject_id': subject.id,
            'day': day,
            'periods': periods
        }
        
        message = (
            f"Subject '{subject.name}' has consecutive periods on {day}: "
            f"periods {', '.join(map(str, periods))}"
        )
        
        suggestions = [
            "Set 'max_consecutive_same_subject' to 1 to prevent consecutive periods",
            "Manually reschedule to avoid back-to-back classes",
            "Consider if consecutive scheduling is intentional (e.g., for double periods)"
        ]
        
        return TimetableError(
            error_type='warning',
            code='CONSECUTIVE_PERIODS',
            message=message,
            details=details,
            suggestions=suggestions
        )
    
    @staticmethod
    def lab_block_integrity_error(
        subject: Subject,
        issue: str,
        details_dict: Dict[str, Any]
    ) -> TimetableError:
        """
        Generate error for lab block integrity issues.
        
        Args:
            subject: Subject with lab block issue
            issue: Description of the integrity issue
            details_dict: Additional details about the issue
        
        Returns:
            TimetableError instance
        """
        details = {
            'subject_name': subject.name,
            'subject_id': subject.id,
            'issue': issue,
            **details_dict
        }
        
        message = f"Lab block integrity issue for '{subject.name}': {issue}"
        
        suggestions = [
            "Regenerate the timetable to fix lab block placement",
            "Verify that lab block placement logic is working correctly",
            "Check that consecutive slots are properly identified and assigned"
        ]
        
        return TimetableError(
            error_type='error',
            code='LAB_BLOCK_INTEGRITY',
            message=message,
            details=details,
            suggestions=suggestions
        )
    
    @staticmethod
    def format_errors_for_display(errors: List[TimetableError]) -> str:
        """
        Format a list of errors for console display.
        
        Args:
            errors: List of TimetableError instances
        
        Returns:
            Formatted string for display
        """
        if not errors:
            return "✅ No errors or warnings"
        
        # Separate errors and warnings
        critical_errors = [e for e in errors if e.type == 'error']
        warnings = [e for e in errors if e.type == 'warning']
        
        result = []
        
        if critical_errors:
            result.append(f"\n{'='*60}")
            result.append(f"CRITICAL ERRORS ({len(critical_errors)})")
            result.append(f"{'='*60}\n")
            for error in critical_errors:
                result.append(str(error))
        
        if warnings:
            result.append(f"\n{'='*60}")
            result.append(f"WARNINGS ({len(warnings)})")
            result.append(f"{'='*60}\n")
            for warning in warnings:
                result.append(str(warning))
        
        return '\n'.join(result)
    
    @staticmethod
    def has_critical_errors(errors: List[TimetableError]) -> bool:
        """
        Check if any errors are critical (type='error').
        
        Args:
            errors: List of TimetableError instances
        
        Returns:
            True if any critical errors exist
        """
        return any(e.type == 'error' for e in errors)
