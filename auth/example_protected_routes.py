"""
Example protected routes demonstrating teacher verification system

Add these routes to your api/app.py file to use them
"""
from flask import Blueprint, jsonify, request
from auth.decorators import require_auth, require_teacher, require_verified_teacher, require_admin
from models import Teacher, User

# Create blueprint for teacher routes
teacher_bp = Blueprint('teacher', __name__, url_prefix='/api/teacher')


@teacher_bp.route('/profile', methods=['GET'])
@require_teacher
def get_teacher_profile(current_user, db, **kwargs):
    """Get current teacher's profile - requires teacher role"""
    try:
        teacher = db.query(Teacher).filter(Teacher.email == current_user.email).first()
        
        if not teacher:
            return jsonify({
                'error': 'Teacher profile not found',
                'message': 'Your teacher profile is being created. Please try again in a moment.'
            }), 404
        
        return jsonify({
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'email': current_user.email,
                'role': current_user.role,
                'full_name': current_user.full_name
            },
            'teacher': {
                'id': teacher.id,
                'name': teacher.name,
                'initials': teacher.initials,
                'email': teacher.email,
                'phone': teacher.phone,
                'verification_status': teacher.verification_status,
                'can_teach_labs': teacher.can_teach_labs,
                'max_hours_per_day': teacher.max_hours_per_day,
                'max_hours_per_week': teacher.max_hours_per_week
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@teacher_bp.route('/dashboard', methods=['GET'])
@require_verified_teacher
def teacher_dashboard(current_user, current_teacher, db, **kwargs):
    """Teacher dashboard - requires verified teacher status"""
    try:
        # Get teacher's assigned subjects
        from models import Subject, TeacherAssignment
        
        # Get subjects assigned to this teacher
        assignments = db.query(TeacherAssignment).filter(
            TeacherAssignment.teacher_id == current_teacher.id
        ).all()
        
        subject_ids = [a.subject_id for a in assignments]
        subjects = db.query(Subject).filter(Subject.id.in_(subject_ids)).all() if subject_ids else []
        
        # Get teacher's timetables
        from models import Timetable
        timetables = db.query(Timetable).filter(
            Timetable.user_id == current_user.id
        ).limit(10).all()
        
        return jsonify({
            'teacher': {
                'id': current_teacher.id,
                'name': current_teacher.name,
                'initials': current_teacher.initials,
                'verification_status': current_teacher.verification_status
            },
            'stats': {
                'total_subjects': len(subjects),
                'total_timetables': len(timetables),
                'max_hours_per_week': current_teacher.max_hours_per_week
            },
            'subjects': [{
                'id': s.id,
                'name': s.name,
                'code': s.code,
                'credits': s.credits,
                'type': s.subject_type
            } for s in subjects],
            'recent_timetables': [{
                'id': t.id,
                'name': t.name,
                'created_at': t.created_at.isoformat() if t.created_at else None
            } for t in timetables]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@teacher_bp.route('/availability', methods=['GET', 'PUT'])
@require_verified_teacher
def manage_availability(current_user, current_teacher, db, **kwargs):
    """Manage teacher availability - requires verified teacher status"""
    try:
        if request.method == 'GET':
            # Get current availability
            return jsonify({
                'teacher_id': current_teacher.id,
                'availability': current_teacher.availability or {}
            }), 200
        
        elif request.method == 'PUT':
            # Update availability
            data = request.get_json()
            availability = data.get('availability', {})
            
            # Validate availability format
            valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            for day, periods in availability.items():
                if day.lower() not in valid_days:
                    return jsonify({'error': f'Invalid day: {day}'}), 400
                if not isinstance(periods, list):
                    return jsonify({'error': f'Periods must be a list for {day}'}), 400
            
            current_teacher.availability = availability
            db.commit()
            
            return jsonify({
                'message': 'Availability updated successfully',
                'availability': current_teacher.availability
            }), 200
            
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500


# Admin routes for teacher verification
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


@admin_bp.route('/teachers/pending', methods=['GET'])
@require_admin
def get_pending_teachers(current_user, db, **kwargs):
    """Get all teachers pending verification - admin only"""
    try:
        pending_teachers = db.query(Teacher).filter(
            Teacher.verification_status == 'pending_verification'
        ).all()
        
        return jsonify({
            'count': len(pending_teachers),
            'teachers': [{
                'id': t.id,
                'name': t.name,
                'email': t.email,
                'initials': t.initials,
                'verification_status': t.verification_status,
                'created_at': t.created_at.isoformat() if t.created_at else None
            } for t in pending_teachers]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/teachers/<int:teacher_id>/verify', methods=['POST'])
@require_admin
def verify_teacher(teacher_id, current_user, db, **kwargs):
    """Verify a teacher - admin only"""
    try:
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
        
        if not teacher:
            return jsonify({'error': 'Teacher not found'}), 404
        
        data = request.get_json() or {}
        action = data.get('action', 'verify')  # 'verify' or 'reject'
        
        if action == 'verify':
            teacher.verification_status = 'verified'
            message = f'Teacher {teacher.name} has been verified'
        elif action == 'reject':
            teacher.verification_status = 'rejected'
            message = f'Teacher {teacher.name} has been rejected'
        else:
            return jsonify({'error': 'Invalid action. Use "verify" or "reject"'}), 400
        
        db.commit()
        
        return jsonify({
            'message': message,
            'teacher': {
                'id': teacher.id,
                'name': teacher.name,
                'email': teacher.email,
                'verification_status': teacher.verification_status
            }
        }), 200
        
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/teachers', methods=['GET'])
@require_admin
def list_all_teachers(current_user, db, **kwargs):
    """List all teachers with their verification status - admin only"""
    try:
        teachers = db.query(Teacher).all()
        
        return jsonify({
            'count': len(teachers),
            'teachers': [{
                'id': t.id,
                'name': t.name,
                'email': t.email,
                'initials': t.initials,
                'verification_status': t.verification_status,
                'can_teach_labs': t.can_teach_labs,
                'created_at': t.created_at.isoformat() if t.created_at else None
            } for t in teachers]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Example: How to register these blueprints in your api/app.py
"""
# Add to api/app.py:

from auth.example_protected_routes import teacher_bp, admin_bp

# Register blueprints
app.register_blueprint(teacher_bp)
app.register_blueprint(admin_bp)
"""
