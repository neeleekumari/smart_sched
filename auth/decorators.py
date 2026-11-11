"""
Authentication decorators for protecting routes
"""
from functools import wraps
from flask import request, jsonify
from .token_manager import TokenManager
from models import User, Teacher
from sqlalchemy.orm import Session

def get_current_user(db: Session, token: str):
    """Extract and verify user from JWT token"""
    try:
        token_manager = TokenManager()
        payload = token_manager.verify_token(token)
        
        if not payload:
            return None, "Invalid or expired token"
        
        user_id = payload.get("sub")
        if not user_id:
            return None, "Invalid token payload"
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            return None, "User not found or inactive"
        
        return user, None
        
    except Exception as e:
        return None, str(e)


def require_auth(f):
    """Decorator to require authentication for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1].strip()
        if not token:
            return jsonify({'error': 'Missing token'}), 401
        
        # Get database session from kwargs or create new one
        from api.app import SessionLocal
        db = SessionLocal()
        
        try:
            user, error = get_current_user(db, token)
            
            if error:
                return jsonify({'error': error}), 401
            
            # Add user to kwargs
            kwargs['current_user'] = user
            kwargs['db'] = db
            
            return f(*args, **kwargs)
            
        finally:
            db.close()
    
    return decorated_function


def require_teacher(f):
    """Decorator to require teacher role for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1].strip()
        if not token:
            return jsonify({'error': 'Missing token'}), 401
        
        # Get database session
        from api.app import SessionLocal
        db = SessionLocal()
        
        try:
            user, error = get_current_user(db, token)
            
            if error:
                return jsonify({'error': error}), 401
            
            # Check if user has teacher role
            if user.role != 'teacher':
                return jsonify({'error': 'Teacher access required'}), 403
            
            # Add user to kwargs
            kwargs['current_user'] = user
            kwargs['db'] = db
            
            return f(*args, **kwargs)
            
        finally:
            db.close()
    
    return decorated_function


def require_verified_teacher(f):
    """Decorator to require verified teacher status for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1].strip()
        if not token:
            return jsonify({'error': 'Missing token'}), 401
        
        # Get database session
        from api.app import SessionLocal
        db = SessionLocal()
        
        try:
            user, error = get_current_user(db, token)
            
            if error:
                return jsonify({'error': error}), 401
            
            # Check if user has teacher role
            if user.role != 'teacher':
                return jsonify({'error': 'Teacher access required'}), 403
            
            # Check if teacher profile exists and is verified
            teacher = db.query(Teacher).filter(Teacher.email == user.email).first()
            
            if not teacher:
                return jsonify({
                    'error': 'Teacher profile not found',
                    'message': 'Please contact administrator to create your teacher profile'
                }), 403
            
            if teacher.verification_status not in ['verified', 'pending_verification']:
                return jsonify({
                    'error': 'Teacher verification required',
                    'message': f'Your teacher account is {teacher.verification_status}. Please contact administrator for verification.',
                    'verification_status': teacher.verification_status
                }), 403
            
            # Add user and teacher to kwargs
            kwargs['current_user'] = user
            kwargs['current_teacher'] = teacher
            kwargs['db'] = db
            
            return f(*args, **kwargs)
            
        finally:
            db.close()
    
    return decorated_function


def require_admin(f):
    """Decorator to require admin role for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1].strip()
        if not token:
            return jsonify({'error': 'Missing token'}), 401
        
        # Get database session
        from api.app import SessionLocal
        db = SessionLocal()
        
        try:
            user, error = get_current_user(db, token)
            
            if error:
                return jsonify({'error': error}), 401
            
            # Check if user is admin
            if not user.is_admin:
                return jsonify({'error': 'Admin access required'}), 403
            
            # Add user to kwargs
            kwargs['current_user'] = user
            kwargs['db'] = db
            
            return f(*args, **kwargs)
            
        finally:
            db.close()
    
    return decorated_function
