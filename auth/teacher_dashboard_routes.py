"""
Teacher Dashboard API Routes
Provides endpoints for teacher timetable, workload stats, and upcoming classes
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, time
from sqlalchemy import and_, or_
from auth.decorators import require_verified_teacher
from models import Timetable, Teacher, Subject, Section

teacher_dashboard_bp = Blueprint('teacher_dashboard', __name__, url_prefix='/api/teacher')


def get_current_day_name():
    """Get current day name (Monday, Tuesday, etc.)"""
    return datetime.now().strftime('%A')


def get_current_time():
    """Get current time as time object"""
    return datetime.now().time()


def parse_time_slot(time_str):
    """
    Parse time slot string to get start and end times
    Examples: "9:00-10:00", "09:00-10:00 AM"
    Returns: (start_time, end_time) as time objects
    """
    try:
        # Remove AM/PM if present and clean up
        time_str = time_str.replace('AM', '').replace('PM', '').strip()
        
        # Split by dash or hyphen
        if '-' in time_str:
            start_str, end_str = time_str.split('-')
        elif '–' in time_str:
            start_str, end_str = time_str.split('–')
        else:
            return None, None
        
        # Parse start time
        start_str = start_str.strip()
        if ':' in start_str:
            hour, minute = map(int, start_str.split(':'))
            start_time = time(hour, minute)
        else:
            start_time = time(int(start_str), 0)
        
        # Parse end time
        end_str = end_str.strip()
        if ':' in end_str:
            hour, minute = map(int, end_str.split(':'))
            end_time = time(hour, minute)
        else:
            end_time = time(int(end_str), 0)
        
        return start_time, end_time
    except Exception as e:
        print(f"Error parsing time slot '{time_str}': {e}")
        return None, None


@teacher_dashboard_bp.route('/timetable', methods=['GET'])
@require_verified_teacher
def get_teacher_timetable(current_user, current_teacher, db, **kwargs):
    """
    Get timetable for logged-in teacher
    """
    try:
        teacher_id = current_teacher.id
        teacher_email = current_teacher.email
        
        # Get all active timetables
        # Teachers view timetables created by admins, so we don't filter by user_id
        timetables = db.query(Timetable).filter(
            Timetable.is_active == True
        ).all()
        
        teacher_classes = []
        all_days = set()
        all_periods = set()
        
        for timetable in timetables:
            entries = timetable.entries_data or [] # use entries_data if model changed, or entries if property
            # Fallback to check if 'entries' attribute exists or is a property wrapper around entries_data
            if not entries and hasattr(timetable, 'entries'):
                 entries = timetable.entries

            days = timetable.days or []
            periods = timetable.periods or []
            timings = timetable.timings or {}
            
            # Add to sets
            all_days.update(days)
            all_periods.update(periods)
            
            for entry in entries:
                # Skip breaks and empty slots
                if entry.get('is_break') or not entry.get('subject_id'):
                    continue
                
                # Check if this entry is for the current teacher
                entry_teacher_id = entry.get('teacher_id')
                
                # Handle potential type mismatch (int vs str)
                if str(entry_teacher_id) == str(teacher_id):
                    # Get subject details
                    subject = db.query(Subject).filter(Subject.id == entry['subject_id']).first()
                    
                    if subject:
                        # Get section name
                        section_name = timetable.section.name if timetable.section else entry.get('section', 'N/A')
                        
                        # Get time from timings
                        period_num = entry.get('period')
                        time_slot = timings.get(str(period_num), 'N/A')
                        
                        teacher_classes.append({
                            'day': entry.get('day'),
                            'period': period_num,
                            'time': time_slot,
                            'subject': subject.name,
                            'subject_code': subject.code,
                            'section': section_name,
                            'room': entry.get('hall', 'N/A'),
                            'type': subject.subject_type,
                            'is_lab_block': entry.get('is_lab_block', False)
                        })
        
        # Sort days and periods
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        sorted_days = sorted(all_days, key=lambda x: day_order.index(x) if x in day_order else 999)
        sorted_periods = sorted(all_periods)
        
        return jsonify({
            'timetable': teacher_classes,
            'days': sorted_days,
            'periods': sorted_periods,
            'teacher': {
                'name': current_teacher.name,
                'initials': current_teacher.initials,
                'email': current_teacher.email
            }
        }), 200
        
    except Exception as e:
        print(f"Error in get_teacher_timetable: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@teacher_dashboard_bp.route('/workload', methods=['GET'])
@require_verified_teacher
def get_teacher_workload(current_user, current_teacher, db, **kwargs):
    """
    Get workload statistics for logged-in teacher
    """
    try:
        teacher_id = current_teacher.id
        
        # Get all active timetables
        timetables = db.query(Timetable).filter(
            Timetable.is_active == True
        ).all()
        
        total_hours = 0
        theory_hours = 0
        lab_hours = 0
        subject_hours = {}
        total_slots = 0
        
        for timetable in timetables:
            entries = timetable.entries_data or []
            if not entries and hasattr(timetable, 'entries'):
                 entries = timetable.entries
            
            for entry in entries:
                # Count total slots (excluding breaks)
                if not entry.get('is_break'):
                    total_slots += 1
                
                # Skip breaks and empty slots
                if entry.get('is_break') or not entry.get('subject_id'):
                    continue
                
                # Check if this entry is for the current teacher
                entry_teacher_id = entry.get('teacher_id')
                
                if str(entry_teacher_id) == str(teacher_id):
                    # Get subject details
                    subject = db.query(Subject).filter(Subject.id == entry['subject_id']).first()
                    
                    if subject:
                        # Count hours (1 slot = 1 hour)
                        hours = 1
                        
                        # Lab blocks might be 2 hours
                        if entry.get('is_lab_block'):
                            hours = 2
                        
                        total_hours += hours
                        
                        if subject.subject_type == 'lab' or subject.subject_type == 'integrated':
                            lab_hours += hours
                        else:
                            theory_hours += hours
                        
                        # Track per subject
                        subject_key = f"{subject.id}"
                        if subject_key not in subject_hours:
                            subject_hours[subject_key] = {
                                'name': subject.name,
                                'code': subject.code,
                                'type': subject.subject_type,
                                'hours': 0
                            }
                        subject_hours[subject_key]['hours'] += hours
        
        # Calculate free slots (this calculation is a bit vague across all timetables, but okay for now)
        # Maybe free slots should be based on total possible slots in a week?
        # For now, let's just use what we have
        free_slots = max(0, 40 - total_hours) # Assuming 40 hour week
        
        return jsonify({
            'total_hours': total_hours,
            'theory_hours': theory_hours,
            'lab_hours': lab_hours,
            'free_slots': free_slots,
            'subjects': list(subject_hours.values()),
            'teacher': {
                'name': current_teacher.name,
                'max_hours_per_week': current_teacher.max_hours_per_week
            }
        }), 200
        
    except Exception as e:
        print(f"Error in get_teacher_workload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@teacher_dashboard_bp.route('/upcoming', methods=['GET'])
@require_verified_teacher
def get_upcoming_classes(current_user, current_teacher, db, **kwargs):
    """
    Get upcoming classes for today
    """
    try:
        teacher_id = current_teacher.id
        current_day = get_current_day_name()
        current_time_obj = get_current_time()
        
        # Get all active timetables
        timetables = db.query(Timetable).filter(
            Timetable.is_active == True
        ).all()
        
        today_classes = []
        next_class = None
        
        for timetable in timetables:
            entries = timetable.entries_data or []
            if not entries and hasattr(timetable, 'entries'):
                 entries = timetable.entries

            timings = timetable.timings or {}
            
            for entry in entries:
                # Skip breaks and empty slots
                if entry.get('is_break') or not entry.get('subject_id'):
                    continue
                
                # Check if this is today and for current teacher
                if entry.get('day') == current_day and str(entry.get('teacher_id')) == str(teacher_id):
                    # Get subject details
                    subject = db.query(Subject).filter(Subject.id == entry['subject_id']).first()
                    
                    if subject:
                        # Get section name
                        section_name = timetable.section.name if timetable.section else entry.get('section', 'N/A')
                        
                        # Get time from timings
                        period_num = entry.get('period')
                        time_slot = timings.get(str(period_num), 'N/A')
                        
                        # Parse time to determine if upcoming
                        start_time, end_time = parse_time_slot(time_slot)
                        
                        class_info = {
                            'time': time_slot,
                            'subject': subject.name,
                            'subject_code': subject.code,
                            'section': section_name,
                            'room': entry.get('hall', 'N/A'),
                            'type': subject.subject_type,
                            'period': period_num,
                            'start_time': start_time.strftime('%H:%M') if start_time else None,
                            'end_time': end_time.strftime('%H:%M') if end_time else None
                        }
                        
                        # Determine status
                        if start_time and end_time:
                            if current_time_obj < start_time:
                                class_info['status'] = 'upcoming'
                                
                                # Calculate time until class
                                time_diff = datetime.combine(datetime.today(), start_time) - datetime.combine(datetime.today(), current_time_obj)
                                minutes = int(time_diff.total_seconds() / 60)
                                
                                if minutes < 60:
                                    class_info['starts_in'] = f"{minutes} minutes"
                                else:
                                    hours = minutes // 60
                                    mins = minutes % 60
                                    class_info['starts_in'] = f"{hours}h {mins}m"
                                
                                # Set as next class if it's the earliest upcoming
                                if next_class is None or start_time < parse_time_slot(next_class['time'])[0]:
                                    next_class = class_info
                                    
                            elif current_time_obj >= start_time and current_time_obj <= end_time:
                                class_info['status'] = 'ongoing'
                            else:
                                class_info['status'] = 'completed'
                        else:
                            class_info['status'] = 'unknown'
                        
                        today_classes.append(class_info)
        
        # Sort today's classes by period
        today_classes.sort(key=lambda x: x['period'])
        
        return jsonify({
            'next_class': next_class,
            'today_classes': today_classes,
            'current_day': current_day,
            'current_time': current_time_obj.strftime('%H:%M')
        }), 200
        
    except Exception as e:
        print(f"Error in get_upcoming_classes: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
