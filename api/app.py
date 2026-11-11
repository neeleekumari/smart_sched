"""Look, there’s still no data showing up — even though all the details have already been fed in. So why isn’t it appearing? Is the backend even working or not?
Either way, make it work."""
"""Flask API Server for AI Timetable Generator Frontend
Provides REST API endpoints to connect the web frontend with the Python backend
"""

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import sys
import json
from datetime import datetime
import tempfile
import zipfile

# Add the parent directory to the path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import Config

# Create database engine
engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy.orm import joinedload
from models import Teacher, Subject, User, Timetable, Section, TeacherAssignment, AllowedDomain, Base

from auth.auth_manager import AuthManager
from auth.example_protected_routes import teacher_bp, admin_bp
from auth.admin_registration import admin_registration_bp
from auth.teacher_dashboard_routes import teacher_dashboard_bp
from import_export.importer import DataImporter
from import_export.exporter import TimetableExporter
from timetable_generator.generator import TimetableGenerator
from timetable_generator.multi_timetable_generator import WorkloadConfig

# Database setup function
def setup_database():
    """Create all database tables from SQLAlchemy models."""
    try:
        Base.metadata.create_all(bind=engine)
        return True
    except Exception as e:
        print(f"Database setup error: {e}")
        return False

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Register blueprints for teacher verification system
app.register_blueprint(teacher_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(admin_registration_bp)
app.register_blueprint(teacher_dashboard_bp)

# Security headers middleware
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    # Set proper Content-Type with charset
    if 'Content-Type' in response.headers and 'application/json' in response.headers['Content-Type']:
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
    
    # Use Content-Security-Policy instead of X-Frame-Options
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
    
    # Remove deprecated headers
    response.headers.pop('X-XSS-Protection', None)
    response.headers.pop('X-Frame-Options', None)
    response.headers.pop('Expires', None)
    
    # Use Cache-Control instead of Expires
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    
    # Add other security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

# File upload/storage configuration (disabled uploads/metadata persistence)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')  # legacy path; not created
DATA_DIR = os.path.join(BASE_DIR, 'data')       # legacy path; not created
META_JSON_PATH = os.path.join(DATA_DIR, 'timetable_meta.json')

def _safe_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    safe = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in name)
    return f"{safe}_{ts}{ext.lower()}"

def _make_initials(name: str) -> str:
    """Generate 3-letter initials from a name, focusing on stressed syllables.
    
    Examples:
        "Rashmi J" -> "RSJ" (first letter + stressed consonant + last initial)
        "John Smith" -> "JSM" (first initial + last name first 2 letters)
        "A B C" -> "ABC" (first letter of each word)
        "Rashmi" -> "RAS" (first 3 letters)
    """
    try:
        parts = [p for p in (name or '').replace('-', ' ').split() if p]
        if not parts:
            return ''
        
        if len(parts) == 1:
            # Single name: take first 3 letters
            return parts[0][:3].upper()
        
        elif len(parts) == 2:
            # Two names: intelligently extract 3 letters
            first = parts[0]
            last = parts[1]
            
            if len(last) == 1:
                # Last name is single letter (e.g., "Rashmi J" -> "RSJ")
                # Take first letter + stressed consonant + last initial
                # Find first consonant after position 0 (skip vowels for better pronunciation)
                vowels = 'aeiouAEIOU'
                stressed_letter = ''
                for i in range(1, len(first)):
                    if first[i] not in vowels:
                        stressed_letter = first[i]
                        break
                if not stressed_letter and len(first) > 1:
                    stressed_letter = first[1]  # Fallback to second letter
                
                initials = first[0] + stressed_letter + last[0]
            else:
                # Both names have multiple letters (e.g., "John Smith" -> "JSM")
                initials = first[0] + last[0] + (last[1] if len(last) > 1 else first[1] if len(first) > 1 else '')
            
            return initials[:3].upper()
        
        else:
            # Three or more names: take first letter of each
            initials = ''.join(p[0] for p in parts[:3])
            return initials[:3].upper()
            
    except Exception:
        return ''

# Initialize managers with database session
def get_auth_manager():
    """Get AuthManager with an active database session.
    Note: Do not close here; the manager uses this session during the request.
    """
    db = SessionLocal()
    return AuthManager(db)

def get_data_importer(user_id: int = 1):
    """Get DataImporter with an active database session and user.
    Note: Do not close here; the importer needs the session for its work.
    """
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Create a default user if none exists
        from auth.password_utils import PasswordUtils
        password_utils = PasswordUtils()
        hashed_password = password_utils.hash_password("admin123")
        user = User(username="admin", email="admin@example.com", hashed_password=hashed_password)
        db.add(user)
        db.commit()
        db.refresh(user)
    return DataImporter(db, user)

def get_or_create_default_user(db):
    """Ensure a default user exists and return it."""
    user = db.query(User).filter(User.id == 1).first()
    if user:
        return user
    from auth.password_utils import PasswordUtils
    password_utils = PasswordUtils()
    hashed_password = password_utils.hash_password("admin123")
    user = User(id=1, username="admin", email="admin@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_timetable_exporter():
    """Get TimetableExporter"""
    # NOTE: TimetableExporter may require db_session and user depending on implementation.
    # If the constructor signature differs, adjust accordingly.
    db = SessionLocal()
    user = get_or_create_default_user(db)
    exporter = TimetableExporter(db_session=db, user=user)  # type: ignore[arg-type]
    return exporter

def get_timetable_generator():
    """Get TimetableGenerator"""
    # Create a DB session and ensure a default user exists, then build the generator
    db = SessionLocal()
    user = get_or_create_default_user(db)
    return TimetableGenerator(db_session=db, user=user)

# API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return jsonify({
            'status': 'healthy',
            'message': 'AI Timetable Generator API is running',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Static serving for uploaded files (disabled)
@app.route('/uploads/<path:filename>', methods=['GET'])
def serve_upload(filename):
    return jsonify({'error': 'Uploads are disabled'}), 410

# Upload logo endpoint (disabled)
@app.route('/api/upload/logo', methods=['POST'])
def upload_logo():
    return jsonify({'error': 'Logo uploads are disabled'}), 410


@app.route('/api/timetables/<int:timetable_id>/entries', methods=['GET'])
def get_timetable_entries(timetable_id: int):
    """Return full timetable details including entries (stored as JSON).
    Structure:
    {
      id, name, days, periods,
      entries: [ { day, period, is_break, break_type, is_lab_block,
                   subject_id, teacher_id, hall } ],
      plus all metadata fields for display
    }
    """
    try:
        db = SessionLocal()
        tt = db.query(Timetable).filter(Timetable.id == timetable_id).first()
        if not tt:
            db.close()
            return jsonify({'error': 'Timetable not found'}), 404

        # Get section name if available
        section_name = None
        if tt.section:
            section_name = tt.section.name

        # Entries are stored as JSON, return directly
        payload = {
            'id': tt.id,
            'name': tt.name,
            'days': tt.days or [],
            'periods': tt.periods or [],
            'entries': tt.entries or [],
            'timings': tt.timings or {},  # Period slot -> time range mapping
            'time_config': tt.time_config or {},  # Original time configuration
            # Include all metadata for display
            'programme_name': tt.programme_name,
            'programmeName': tt.programme_name,  # alias
            'term_label': tt.term_label,
            'termLabel': tt.term_label,  # alias
            'semester': tt.semester,
            'wef_date': tt.wef_date,
            'wefDate': tt.wef_date,  # alias
            'class_strength': tt.class_strength,
            'classStrength': tt.class_strength,  # alias
            'logo_data_url': tt.logo_data_url,
            'logoDataUrl': tt.logo_data_url,  # alias
            'sections_meta': tt.sections_meta,
            'section': section_name,
        }
        db.close()
        return jsonify(payload)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/verify', methods=['GET'])
def verify():
    """Verify JWT in Authorization header and return user info"""
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        token = auth_header.split(' ', 1)[1].strip()
        if not token:
            return jsonify({'error': 'Missing token'}), 401

        auth_manager = get_auth_manager()
        valid, user = auth_manager.verify_token(token)
        
        allowed_domain = None
        if valid and user and user.role == 'admin':
            # Find the domain created by this admin
            domain_obj = auth_manager.db.query(AllowedDomain).filter(
                AllowedDomain.created_by_user_id == user.id,
                AllowedDomain.is_active == True
            ).first()
            
            # Removed fallback
                
            if domain_obj:
                allowed_domain = domain_obj.domain

        try:
            auth_manager.db.close()
        except Exception:
            pass

        if not valid or not user:
            return jsonify({'error': 'Invalid or expired token'}), 401

        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'allowed_domain': allowed_domain
            }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        
        if not data or not ('password' in data and ('email' in data or 'username' in data)):
            return jsonify({'error': 'Missing username/email or password'}), 400
        
        identifier = data.get('email') or data.get('username')
        auth_manager = get_auth_manager()
        success, user, token = auth_manager.authenticate_user(
            username=identifier,
            password=data['password']
        )
        
        allowed_domain = None
        if success and user and user.role == 'admin':
            # Find the domain created by this admin
            domain_obj = auth_manager.db.query(AllowedDomain).filter(
                AllowedDomain.created_by_user_id == user.id,
                AllowedDomain.is_active == True
            ).first()
            
            # Removed fallback to allow free entry if no domain is registered by this admin
                
            if domain_obj:
                allowed_domain = domain_obj.domain
        
        if success and user and token:
            try:
                auth_manager.db.close()
            except Exception:
                pass
            return jsonify({
                'message': 'Login successful',
                'token': token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'allowed_domain': allowed_domain
                }
            }), 200
        else:
            try:
                auth_manager.db.close()
            except Exception:
                pass
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
from auth.auth_manager import AuthManager
from auth.example_protected_routes import teacher_bp, admin_bp
from auth.admin_registration import admin_registration_bp
from auth.teacher_dashboard_routes import teacher_dashboard_bp
from import_export.importer import DataImporter
from import_export.exporter import TimetableExporter
from timetable_generator.generator import TimetableGenerator
from timetable_generator.multi_timetable_generator import WorkloadConfig

# Database setup function
def setup_database():
    """Create all database tables from SQLAlchemy models."""
    try:
        Base.metadata.create_all(bind=engine)
        return True
    except Exception as e:
        print(f"Database setup error: {e}")
        return False

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Register blueprints for teacher verification system
app.register_blueprint(teacher_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(admin_registration_bp)
app.register_blueprint(teacher_dashboard_bp)

# Security headers middleware
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    # Set proper Content-Type with charset
    if 'Content-Type' in response.headers and 'application/json' in response.headers['Content-Type']:
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
    
    # Use Content-Security-Policy instead of X-Frame-Options
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
    
    # Remove deprecated headers
    response.headers.pop('X-XSS-Protection', None)
    response.headers.pop('X-Frame-Options', None)
    response.headers.pop('Expires', None)
    
    # Use Cache-Control instead of Expires
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    
    # Add other security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

# File upload/storage configuration (disabled uploads/metadata persistence)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')  # legacy path; not created
DATA_DIR = os.path.join(BASE_DIR, 'data')       # legacy path; not created
META_JSON_PATH = os.path.join(DATA_DIR, 'timetable_meta.json')

def _safe_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    safe = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in name)
    return f"{safe}_{ts}{ext.lower()}"

def _make_initials(name: str) -> str:
    """Generate 3-letter initials from a name, focusing on stressed syllables.
    
    Examples:
        "Rashmi J" -> "RSJ" (first letter + stressed consonant + last initial)
        "John Smith" -> "JSM" (first initial + last name first 2 letters)
        "A B C" -> "ABC" (first letter of each word)
        "Rashmi" -> "RAS" (first 3 letters)
    """
    try:
        parts = [p for p in (name or '').replace('-', ' ').split() if p]
        if not parts:
            return ''
        
        if len(parts) == 1:
            # Single name: take first 3 letters
            return parts[0][:3].upper()
        
        elif len(parts) == 2:
            # Two names: intelligently extract 3 letters
            first = parts[0]
            last = parts[1]
            
            if len(last) == 1:
                # Last name is single letter (e.g., "Rashmi J" -> "RSJ")
                # Take first letter + stressed consonant + last initial
                # Find first consonant after position 0 (skip vowels for better pronunciation)
                vowels = 'aeiouAEIOU'
                stressed_letter = ''
                for i in range(1, len(first)):
                    if first[i] not in vowels:
                        stressed_letter = first[i]
                        break
                if not stressed_letter and len(first) > 1:
                    stressed_letter = first[1]  # Fallback to second letter
                
                initials = first[0] + stressed_letter + last[0]
            else:
                # Both names have multiple letters (e.g., "John Smith" -> "JSM")
                initials = first[0] + last[0] + (last[1] if len(last) > 1 else first[1] if len(first) > 1 else '')
            
            return initials[:3].upper()
        
        else:
            # Three or more names: take first letter of each
            initials = ''.join(p[0] for p in parts[:3])
            return initials[:3].upper()
            
    except Exception:
        return ''

# Initialize managers with database session
def get_auth_manager():
    """Get AuthManager with an active database session.
    Note: Do not close here; the manager uses this session during the request.
    """
    db = SessionLocal()
    return AuthManager(db)

def get_data_importer(user_id: int = 1):
    """Get DataImporter with an active database session and user.
    Note: Do not close here; the importer needs the session for its work.
    """
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Create a default user if none exists
        from auth.password_utils import PasswordUtils
        password_utils = PasswordUtils()
        hashed_password = password_utils.hash_password("admin123")
        user = User(username="admin", email="admin@example.com", hashed_password=hashed_password)
        db.add(user)
        db.commit()
        db.refresh(user)
    return DataImporter(db, user)

def get_or_create_default_user(db):
    """Ensure a default user exists and return it."""
    user = db.query(User).filter(User.id == 1).first()
    if user:
        return user
    from auth.password_utils import PasswordUtils
    password_utils = PasswordUtils()
    hashed_password = password_utils.hash_password("admin123")
    user = User(id=1, username="admin", email="admin@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_timetable_exporter():
    """Get TimetableExporter"""
    # NOTE: TimetableExporter may require db_session and user depending on implementation.
    # If the constructor signature differs, adjust accordingly.
    db = SessionLocal()
    user = get_or_create_default_user(db)
    exporter = TimetableExporter(db_session=db, user=user)  # type: ignore[arg-type]
    return exporter

def get_timetable_generator():
    """Get TimetableGenerator"""
    # Create a DB session and ensure a default user exists, then build the generator
    db = SessionLocal()
    user = get_or_create_default_user(db)
    return TimetableGenerator(db_session=db, user=user)

# API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return jsonify({
            'status': 'healthy',
            'message': 'AI Timetable Generator API is running',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Static serving for uploaded files (disabled)
@app.route('/uploads/<path:filename>', methods=['GET'])
def serve_upload(filename):
    return jsonify({'error': 'Uploads are disabled'}), 410

# Upload logo endpoint (disabled)
@app.route('/api/upload/logo', methods=['POST'])
def upload_logo():
    return jsonify({'error': 'Logo uploads are disabled'}), 410


@app.route('/api/timetables/<int:timetable_id>/entries', methods=['GET'])
def get_timetable_entries(timetable_id: int):
    """Return full timetable details including entries (stored as JSON).
    Structure:
    {
      id, name, days, periods,
      entries: [ { day, period, is_break, break_type, is_lab_block,
                   subject_id, teacher_id, hall } ],
      plus all metadata fields for display
    }
    """
    try:
        db = SessionLocal()
        tt = db.query(Timetable).filter(Timetable.id == timetable_id).first()
        if not tt:
            db.close()
            return jsonify({'error': 'Timetable not found'}), 404

        # Get section name if available
        section_name = None
        if tt.section:
            section_name = tt.section.name

        # Entries are stored as JSON, return directly
        payload = {
            'id': tt.id,
            'name': tt.name,
            'days': tt.days or [],
            'periods': tt.periods or [],
            'entries': tt.entries or [],
            'timings': tt.timings or {},  # Period slot -> time range mapping
            'time_config': tt.time_config or {},  # Original time configuration
            # Include all metadata for display
            'programme_name': tt.programme_name,
            'programmeName': tt.programme_name,  # alias
            'term_label': tt.term_label,
            'termLabel': tt.term_label,  # alias
            'semester': tt.semester,
            'wef_date': tt.wef_date,
            'wefDate': tt.wef_date,  # alias
            'class_strength': tt.class_strength,
            'classStrength': tt.class_strength,  # alias
            'logo_data_url': tt.logo_data_url,
            'logoDataUrl': tt.logo_data_url,  # alias
            'sections_meta': tt.sections_meta,
            'section': section_name,
        }
        db.close()
        return jsonify(payload)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# Authentication endpoints
@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ('username', 'email', 'password')):
            return jsonify({'error': 'Missing required fields'}), 400
        
        auth_manager = get_auth_manager()
        success, user, errors = auth_manager.register_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            full_name=data.get('full_name'),
            role=data.get('role'),
            salutation=data.get('salutation')  # Collect Salutation from Teacher registration
        )
        
        if success and user:
            try:
                auth_manager.db.close()
            except Exception:
                pass
            return jsonify({
                'message': 'User registered successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role
                }
            }), 201
        else:
            try:
                auth_manager.db.close()
            except Exception:
                pass
            print(f"Registration errors: {errors}")
            return jsonify({'error': errors or ['Registration failed']}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# Token verification endpoint
@app.route('/api/auth/verify', methods=['GET'])
def verify():
    """Verify JWT in Authorization header and return user info"""
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        token = auth_header.split(' ', 1)[1].strip()
        if not token:
            return jsonify({'error': 'Missing token'}), 401

        auth_manager = get_auth_manager()
        valid, user = auth_manager.verify_token(token)
        try:
            auth_manager.db.close()
        except Exception:
            pass

        if not valid or not user:
            return jsonify({'error': 'Invalid or expired token'}), 401
            
        # Get allowed domains
        allowed_domains = []
        if user.role == 'admin':
            domain_objs = auth_manager.db.query(AllowedDomain).filter(
                AllowedDomain.created_by_user_id == user.id,
                AllowedDomain.is_active == True
            ).all()
            allowed_domains = [d.domain for d in domain_objs]

        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'allowed_domain': allowed_domains[0] if allowed_domains else None,
                'allowed_domains': allowed_domains
            }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        
        if not data or not ('password' in data and ('email' in data or 'username' in data)):
            return jsonify({'error': 'Missing username/email or password'}), 400
        
        identifier = data.get('email') or data.get('username')
        auth_manager = get_auth_manager()
        success, user, token = auth_manager.authenticate_user(
            username=identifier,
            password=data['password']
        )
        
        if success and user and token:
            # Get allowed domains
            allowed_domains = []
            if user.role == 'admin':
                domain_objs = auth_manager.db.query(AllowedDomain).filter(
                    AllowedDomain.created_by_user_id == user.id,
                    AllowedDomain.is_active == True
                ).all()
                allowed_domains = [d.domain for d in domain_objs]

            try:
                auth_manager.db.close()
            except Exception:
                pass
            return jsonify({
                'message': 'Login successful',
                'token': token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'allowed_domain': allowed_domains[0] if allowed_domains else None,
                    'allowed_domains': allowed_domains
                }
            }), 200
        else:
            try:
                auth_manager.db.close()
            except Exception:
                pass
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/me', methods=['DELETE'])
def delete_current_user():
    """Delete the currently authenticated user account"""
    try:
        # Verify Token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1].strip()
        auth_manager = get_auth_manager()
        valid, user = auth_manager.verify_token(token)
        
        if not valid or not user:
            try: auth_manager.db.close()
            except: pass
            return jsonify({'error': 'Invalid or expired token'}), 401
            
        try:
            # Perform Deletion
            user_to_delete = auth_manager.db.merge(user)
            auth_manager.db.delete(user_to_delete)
            auth_manager.db.commit()
            return jsonify({'message': 'Account deleted successfully'}), 200
        finally:
            try: auth_manager.db.close()
            except: pass
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Data management endpoints
@app.route('/api/teachers', methods=['GET'])
def get_teachers():
    """Get all teachers"""
    try:
        db = SessionLocal()
        teachers = db.query(Teacher).all()
        db.close()
        
        return jsonify([{
            'id': t.id,
            'title': t.title or t.salutation or '', # Combine/fallback
            'salutation': t.salutation,
            'teacher_code': t.teacher_code,
            'name': t.name,
            'initials': t.initials,
            'email': t.email,
            'phone': t.phone,
            'max_hours_per_day': t.max_hours_per_day,
            'max_hours_per_week': t.max_hours_per_week,
            'can_teach_labs': t.can_teach_labs,
            'availability': t.availability,
            'created_at': t.created_at.isoformat() if t.created_at is not None else None
        } for t in teachers])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers', methods=['POST'])
def create_teacher():
    """Create a new teacher"""
    try:
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({'error': 'Name is required'}), 400
        
        db = SessionLocal()
        
        # Verify user to get institute code
        from auth.decorators import get_current_user
        auth_header = request.headers.get('Authorization', '')
        user = None
        
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            user, _ = get_current_user(db, token)
            
        if not user:
             user = get_or_create_default_user(db)

        # Allow explicit null/empty initials; otherwise normalize/generate
        raw_initials = data.get('initials')
        if raw_initials is None or (isinstance(raw_initials, str) and raw_initials.strip() == ''):
            initials = _make_initials(data['name'])
        else:
            # Normalize and validate to exactly 3 letters
            cleaned = ''.join([c for c in str(raw_initials).upper() if c.isalpha()])
            if len(cleaned) != 3:
                return jsonify({'error': 'Initials must be exactly 3 letters'}), 400
            initials = cleaned

        # Auto-generate teacher code
        auth_manager = AuthManager(db)
        # Find institute code
        inst_code = user.institute_code
        if not inst_code:
            # Fallback for manual creation: Find any admin with institute code
            admin_user = db.query(User).filter(User.is_admin == True, User.institute_code != None).first()
            inst_code = admin_user.institute_code if admin_user else "INST"
        
        generated_code = auth_manager.generate_teacher_code(inst_code)
        
        teacher = Teacher(
            title=data.get('title', ''),
            salutation=data.get('salutation'), # Capture salutation too
            teacher_code=generated_code,
            name=data['name'],
            initials=initials,
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            max_hours_per_day=data.get('max_hours_per_day', 6),
            max_hours_per_week=data.get('max_hours_per_week', 30),
            can_teach_labs=data.get('can_teach_labs', False),
            availability=data.get('availability', {}),
            user_id=user.id
        )
        
        db.add(teacher)
        db.commit()
        teacher_id = teacher.id
        db.close()
        
        return jsonify({
            'message': 'Teacher created successfully',
            'teacher_id': teacher_id
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/<int:teacher_id>', methods=['PUT'])
def update_teacher(teacher_id):
    """Update a teacher"""
    try:
        data = request.get_json()
        
        db = SessionLocal()
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
        
        if not teacher:
            db.close()
            return jsonify({'error': 'Teacher not found'}), 404
        
        # Update fields, with initials validation
        for field in ['title', 'name', 'email', 'phone', 'max_hours_per_day', 'max_hours_per_week', 'can_teach_labs', 'availability']:
            if field in data:
                setattr(teacher, field, data[field])
        if 'initials' in data:
            raw_initials = data.get('initials')
            if raw_initials is None or (isinstance(raw_initials, str) and raw_initials.strip() == ''):
                # if explicitly cleared, auto-generate from name
                teacher.initials = _make_initials(str(teacher.name))  # type: ignore[assignment]
            else:
                cleaned = ''.join([c for c in str(raw_initials).upper() if c.isalpha()])
                if len(cleaned) != 3:
                    db.close()
                    return jsonify({'error': 'Initials must be exactly 3 letters'}), 400
                teacher.initials = cleaned  # type: ignore[assignment]
        else:
            # If initials not provided and teacher has none, auto-generate
            if not teacher.initials:
                teacher.initials = _make_initials(str(teacher.name))  # type: ignore[assignment]
        
        db.commit()
        db.close()
        
        return jsonify({'message': 'Teacher updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/<int:teacher_id>', methods=['DELETE'])
def delete_teacher(teacher_id):
    """Delete a teacher and remove all their assignments"""
    try:
        db = SessionLocal()
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
        
        if not teacher:
            db.close()
            return jsonify({'error': 'Teacher not found'}), 404
        
        # Remove teacher from all subject assignments
        # Set teacher_id to NULL for subjects taught by this teacher
        db.query(Subject).filter(Subject.teacher_id == teacher_id).update(
            {Subject.teacher_id: None},
            synchronize_session=False
        )
        
        # Remove teacher as class teacher from all sections
        # Set class_teacher_id to NULL for sections where this teacher is class teacher
        db.query(Section).filter(Section.class_teacher_id == teacher_id).update(
            {Section.class_teacher_id: None},
            synchronize_session=False
        )
        
        # Now delete the teacher
        db.delete(teacher)
        db.commit()
        db.close()
        
        return jsonify({'message': 'Teacher deleted successfully. All assignments have been removed.'})
        
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    """Get all subjects, optionally filtered by semester"""
    try:
        db = SessionLocal()
        semester = request.args.get('semester')
        
        query = db.query(Subject)
        if semester:
            query = query.filter(Subject.semester == semester)
        subjects = query.all()
        
        result = []
        for s in subjects:
            # Get all assigned teachers for this subject
            assignments = db.query(TeacherAssignment).filter(
                TeacherAssignment.subject_id == s.id,
                TeacherAssignment.section_id == None  # Global assignments only
            ).all()
            
            teacher_ids = [a.teacher_id for a in assignments] if assignments else ([s.teacher_id] if s.teacher_id else [])
            
            result.append({
                'id': s.id,
                'name': s.name,
                'code': s.code,
                'credits': s.credits,
                'subject_type': s.subject_type,
                'type': s.subject_type,  # alias for frontend compatibility
                'abbreviation': s.abbreviation,
                'class_size': s.class_size,
                'teacher_id': s.teacher_id,  # Legacy single teacher
                'teacher_ids': teacher_ids,  # All assigned teachers
                'semester': s.semester,
                'created_at': s.created_at.isoformat() if s.created_at is not None else None
            })
        
        db.close()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/subjects', methods=['POST'])
def create_subject():
    """Create a new subject with optional multiple teachers"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ('name', 'code', 'credits')):
            return jsonify({'error': 'Name, code, and credits are required'}), 400
        
        db = SessionLocal()
        user = get_or_create_default_user(db)
        
        # Normalize aliases and values
        subj_type = (data.get('subject_type') or data.get('type') or 'theory').lower()
        if subj_type not in ['theory', 'lab', 'integrated']:
            subj_type = 'theory'
        
        # Handle teacher_id (legacy single teacher)
        teacher_id = data.get('teacher_id')
        if isinstance(teacher_id, str) and teacher_id.strip().lower() in ('', 'none', 'null'):
            teacher_id = None
        
        # Handle teacher_ids (new multi-teacher support)
        teacher_ids = data.get('teacher_ids', [])
        if not teacher_ids and teacher_id:
            teacher_ids = [teacher_id]
        
        subject = Subject(
            name=data['name'],
            code=data['code'],
            credits=data['credits'],
            subject_type=subj_type,
            abbreviation=data.get('abbreviation'),
            class_size=data.get('class_size', 30),
            teacher_id=teacher_ids[0] if teacher_ids else None,  # Set first as primary for legacy
            semester=data.get('semester'),
            user_id=user.id
        )
        
        db.add(subject)
        db.flush()  # Get subject.id without committing
        
        # Create teacher assignments if multiple teachers provided
        if teacher_ids:
            for idx, tid in enumerate(teacher_ids):
                if isinstance(tid, str) and tid.strip().lower() in ('', 'none', 'null'):
                    continue
                
                assignment = TeacherAssignment(
                    teacher_id=tid,
                    subject_id=subject.id,
                    section_id=None,  # Global assignment
                    is_primary=(idx == 0),
                    is_eligible=True,
                    user_id=user.id,
                    semester=int(subject.semester) if subject.semester else None
                )
                db.add(assignment)
        
        db.commit()
        subject_id = subject.id
        db.close()
        
        return jsonify({
            'message': 'Subject created successfully',
            'subject_id': subject_id,
            'teachers_assigned': len(teacher_ids)
        }), 201
        
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/subjects/<int:subject_id>', methods=['PUT'])
def update_subject(subject_id):
    """Update a subject with optional multiple teachers"""
    try:
        data = request.get_json()
        
        db = SessionLocal()
        user = get_or_create_default_user(db)
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        
        if not subject:
            db.close()
            return jsonify({'error': 'Subject not found'}), 404
        
        # Normalize incoming keys: allow 'type' as alias for 'subject_type'
        if 'type' in data and 'subject_type' not in data:
            data['subject_type'] = data['type']
        if 'teacher' in data and 'teacher_id' not in data:
            data['teacher_id'] = data['teacher']
        if 'teacher_id' in data and isinstance(data['teacher_id'], str) and data['teacher_id'].strip().lower() in ('', 'none', 'null'):
            data['teacher_id'] = None
        if 'subject_type' in data:
            st = (data['subject_type'] or '').lower()
            if st in ['theory', 'lab', 'integrated']:
                data['subject_type'] = st

        # Update fields (use correct model attribute names)
        for field in ['name', 'code', 'credits', 'subject_type', 'abbreviation', 'class_size', 'teacher_id', 'semester']:
            if field in data:
                setattr(subject, field, data[field])
        
        # Handle teacher_ids (new multi-teacher support)
        if 'teacher_ids' in data:
            teacher_ids = data['teacher_ids']
            
            # Remove existing global assignments
            db.query(TeacherAssignment).filter(
                TeacherAssignment.subject_id == subject_id,
                TeacherAssignment.section_id == None
            ).delete()
            
            # Create new assignments
            if teacher_ids:
                for idx, tid in enumerate(teacher_ids):
                    if isinstance(tid, str) and tid.strip().lower() in ('', 'none', 'null'):
                        continue
                    
                    assignment = TeacherAssignment(
                        teacher_id=tid,
                        subject_id=subject_id,
                        section_id=None,
                        is_primary=(idx == 0),
                        is_eligible=True,
                        user_id=user.id,
                        semester=int(subject.semester) if subject.semester else None
                    )
                    db.add(assignment)
                
                # Update legacy teacher_id
                subject.teacher_id = teacher_ids[0]
        
        db.commit()
        db.close()
        
        return jsonify({'message': 'Subject updated successfully'})
        
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/subjects/<int:subject_id>', methods=['DELETE'])
def delete_subject(subject_id):
    """Delete a subject"""
    try:
        db = SessionLocal()
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        
        if not subject:
            db.close()
            return jsonify({'error': 'Subject not found'}), 404
        
        # Note: Subjects may be referenced in timetable entries, but those are stored as JSON
        # so there's no foreign key constraint. We can safely delete the subject.
        
        db.delete(subject)
        db.commit()
        db.close()
        
        return jsonify({'message': 'Subject deleted successfully'})
        
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': str(e)}), 500

# Teacher Assignment API (NEW: Multi-teacher support)
@app.route('/api/subjects/<int:subject_id>/teachers', methods=['GET'])
def get_subject_teachers(subject_id):
    """Get all teachers assigned to a subject"""
    try:
        db = SessionLocal()
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        
        if not subject:
            db.close()
            return jsonify({'error': 'Subject not found'}), 404
        
        # Get all teacher assignments for this subject
        assignments = db.query(TeacherAssignment).filter(
            TeacherAssignment.subject_id == subject_id,
            TeacherAssignment.section_id == None  # Global assignments only
        ).all()
        
        result = []
        for assignment in assignments:
            teacher = assignment.teacher
            result.append({
                'assignment_id': assignment.id,
                'teacher_id': teacher.id,
                'teacher_name': teacher.name,
                'teacher_initials': teacher.initials,
                'is_primary': assignment.is_primary,
                'is_eligible': assignment.is_eligible
            })
        
        # Include legacy teacher_id if exists and not in assignments
        if subject.teacher_id:
            existing_ids = [a.teacher_id for a in assignments]
            if subject.teacher_id not in existing_ids:
                teacher = db.query(Teacher).filter(Teacher.id == subject.teacher_id).first()
                if teacher:
                    result.append({
                        'assignment_id': None,
                        'teacher_id': teacher.id,
                        'teacher_name': teacher.name,
                        'teacher_initials': teacher.initials,
                        'is_primary': True,
                        'is_eligible': True,
                        'legacy': True
                    })
        
        db.close()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/subjects/<int:subject_id>/teachers', methods=['POST'])
def assign_teachers_to_subject(subject_id):
    """Assign multiple teachers to a subject"""
    try:
        data = request.get_json()
        teacher_ids = data.get('teacher_ids', [])
        
        if not teacher_ids:
            return jsonify({'error': 'teacher_ids array is required'}), 400
        
        db = SessionLocal()
        user = get_or_create_default_user(db)
        
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            db.close()
            return jsonify({'error': 'Subject not found'}), 404
        
        # Remove existing assignments (except section-specific ones)
        db.query(TeacherAssignment).filter(
            TeacherAssignment.subject_id == subject_id,
            TeacherAssignment.section_id == None
        ).delete()
        
        # Create new assignments
        for idx, teacher_id in enumerate(teacher_ids):
            teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
            if not teacher:
                continue
            
            assignment = TeacherAssignment(
                teacher_id=teacher_id,
                subject_id=subject_id,
                section_id=None,  # Global assignment
                is_primary=(idx == 0),  # First teacher is primary
                is_eligible=True,
                user_id=user.id,
                semester=int(subject.semester) if subject.semester else None
            )
            db.add(assignment)
        
        # Update legacy teacher_id to first teacher for backward compatibility
        if teacher_ids:
            subject.teacher_id = teacher_ids[0]
        
        db.commit()
        db.close()
        
        return jsonify({'message': 'Teachers assigned successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/subjects/<int:subject_id>/teachers/<int:assignment_id>', methods=['DELETE'])
def remove_teacher_assignment(subject_id, assignment_id):
    """Remove a teacher assignment from a subject"""
    try:
        db = SessionLocal()
        
        assignment = db.query(TeacherAssignment).filter(
            TeacherAssignment.id == assignment_id,
            TeacherAssignment.subject_id == subject_id
        ).first()
        
        if not assignment:
            db.close()
            return jsonify({'error': 'Assignment not found'}), 404
        
        db.delete(assignment)
        db.commit()
        db.close()
        
        return jsonify({'message': 'Teacher assignment removed successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

## Rooms API removed: lecture halls are used directly

# Section management endpoints
@app.route('/api/sections', methods=['GET'])
def get_sections():
    """Get all sections, optionally filtered by semester"""
    try:
        db = SessionLocal()
        semester = request.args.get('semester')
        
        query = db.query(Section)
        if semester:
            query = query.filter(Section.semester == semester)
        sections = query.all()
        
        db.close()
        
        return jsonify([{
            'id': s.id,
            'name': s.name,
            'semester': s.semester,
            'programme': s.programme,
            'class_strength': s.class_strength,
            'classStrength': s.class_strength,  # alias
            'lecture_hall': s.lecture_hall,
            'lectureHall': s.lecture_hall,  # alias
            'class_teacher_id': s.class_teacher_id,
            'classTeacherId': s.class_teacher_id,  # alias
            'created_at': s.created_at.isoformat() if getattr(s, 'created_at', None) else None
        } for s in sections])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sections', methods=['POST'])
def create_section():
    """Create a new section"""
    try:
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({'error': 'Section name is required'}), 400
        
        db = SessionLocal()
        user = get_or_create_default_user(db)
        
        section = Section(
            name=data['name'],
            semester=data.get('semester'),
            programme=data.get('programme'),
            class_strength=data.get('class_strength') or data.get('classStrength', 30),
            lecture_hall=data.get('lecture_hall') or data.get('lectureHall'),
            class_teacher_id=data.get('class_teacher_id') or data.get('classTeacherId'),
            user_id=user.id
        )
        
        db.add(section)
        db.commit()
        section_id = section.id
        db.close()
        
        return jsonify({
            'message': 'Section created successfully',
            'section_id': section_id
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sections/<int:section_id>', methods=['PUT'])
def update_section(section_id):
    """Update a section"""
    try:
        data = request.get_json()
        
        db = SessionLocal()
        section = db.query(Section).filter(Section.id == section_id).first()
        
        if not section:
            db.close()
            return jsonify({'error': 'Section not found'}), 404
        
        # Update fields
        if 'name' in data:
            section.name = data['name']
        if 'semester' in data:
            section.semester = data['semester']
        if 'programme' in data:
            section.programme = data['programme']
        if 'class_strength' in data or 'classStrength' in data:
            section.class_strength = data.get('class_strength') or data.get('classStrength')
        if 'lecture_hall' in data or 'lectureHall' in data:
            section.lecture_hall = data.get('lecture_hall') or data.get('lectureHall')
        if 'class_teacher_id' in data or 'classTeacherId' in data:
            section.class_teacher_id = data.get('class_teacher_id') or data.get('classTeacherId')
        
        db.commit()
        db.close()
        
        return jsonify({'message': 'Section updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sections/<int:section_id>', methods=['DELETE'])
def delete_section(section_id):
    """Delete a section"""
    try:
        db = SessionLocal()
        section = db.query(Section).filter(Section.id == section_id).first()
        
        if not section:
            db.close()
            return jsonify({'error': 'Section not found'}), 404
        
        db.delete(section)
        db.commit()
        db.close()
        
        return jsonify({'message': 'Section deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Timetable generation endpoints
@app.route('/api/timetables', methods=['GET'])
def get_timetables():
    """Get all timetables"""
    try:
        db = SessionLocal()
        timetables = db.query(Timetable).all()
        db.close()
        
        response = []
        for t in timetables:
            created = t.created_at.isoformat() if hasattr(t, 'created_at') and t.created_at else None
            updated = t.updated_at.isoformat() if hasattr(t, 'updated_at') and t.updated_at else None
            response.append({
                'id': t.id,
                'name': t.name if hasattr(t, 'name') else 'Untitled',
                'status': 'completed' if t.is_active else 'archived',
                'conflicts': t.conflicts_detected if hasattr(t, 'conflicts_detected') else 0,
                'created_at': created,
                'updated_at': updated,
                # aliases for frontend compatibility
                'createdAt': created,
                'updatedAt': updated
            })
        return jsonify(response)
        
    except Exception as e:
        import traceback
        print(f"Error in get_timetables: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/timetables', methods=['POST'])
def generate_timetable():
    """Generate new timetable(s) - single or multi-section
    
    Returns detailed error responses with separate errors and warnings.
    
    Success Response (201):
    {
        "message": "Timetable generated successfully",
        "timetable_id": 123,
        "warnings": [...]  // Optional warnings even on success
    }
    
    Error Response (400):
    {
        "success": false,
        "errors": [
            {
                "type": "error",
                "code": "INSUFFICIENT_HOURS",
                "message": "...",
                "details": {...},
                "suggestions": [...]
            }
        ],
        "warnings": [
            {
                "type": "warning",
                "code": "POOR_DISTRIBUTION",
                "message": "...",
                "details": {...},
                "suggestions": [...]
            }
        ]
    }
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({
                'success': False,
                'errors': [{
                    'type': 'error',
                    'code': 'INVALID_INPUT',
                    'message': 'Timetable name is required',
                    'details': {},
                    'suggestions': ['Provide a name for the timetable']
                }]
            }), 400
        
        # Build generator
        db = SessionLocal()
        user = get_or_create_default_user(db)
        
        # Extract workload configuration if provided
        config = WorkloadConfig()
        if 'workloadConfig' in data or 'config' in data:
            cfg_data = data.get('workloadConfig') or data.get('config', {})
            if 'multi_timetable_min_hours' in cfg_data:
                config.multi_timetable_min_hours = int(cfg_data['multi_timetable_min_hours'])
            if 'multi_timetable_max_hours' in cfg_data:
                config.multi_timetable_max_hours = int(cfg_data['multi_timetable_max_hours'])
            if 'single_timetable_target_hours' in cfg_data:
                config.single_timetable_target_hours = int(cfg_data['single_timetable_target_hours'])
            if 'max_theory_subjects' in cfg_data:
                config.max_theory_subjects = int(cfg_data['max_theory_subjects'])
            if 'max_lab_subjects' in cfg_data:
                config.max_lab_subjects = int(cfg_data['max_lab_subjects'])
            if 'require_rest_between_classes' in cfg_data:
                config.require_rest_between_classes = bool(cfg_data['require_rest_between_classes'])
        
        gen = TimetableGenerator(db_session=db, user=user, config=config)

        # Optional runtime tuning
        try:
            opts = data.get('options') if isinstance(data, dict) else None
            def get_opt(key, default=None):
                if opts and key in opts:
                    return opts.get(key)
                return data.get(key, default) if isinstance(data, dict) else default
            timeout_val = get_opt('timeout')
            if isinstance(timeout_val, int):
                gen.timeout_seconds = timeout_val
            fm = get_opt('find_multiple')
            if fm is not None:
                gen.find_multiple_solutions = bool(fm)
            sc = get_opt('solutions_count')
            if sc is not None:
                try:
                    gen.solutions_count = max(1, int(sc))
                except Exception:
                    pass
        except Exception:
            pass

        # Fetch data
        user_id = user.id
        teachers = db.query(Teacher).filter(Teacher.user_id == user_id).all()
        subjects_query = db.query(Subject).filter(Subject.user_id == user_id)
        
        # Filter subjects if specified
        try:
            meta_payload = data.get('meta') or {}
            subj_list = meta_payload.get('subjects')
            if isinstance(subj_list, list) and len(subj_list) > 0:
                ids = []
                for item in subj_list:
                    try:
                        if isinstance(item, dict) and 'id' in item:
                            ids.append(int(item['id']))
                        elif isinstance(item, (int, str)):
                            ids.append(int(item))
                    except Exception:
                        continue
                if ids:
                    subjects_query = subjects_query.filter(Subject.id.in_(ids))
        except Exception:
            pass
        subjects = subjects_query.all()

        # Determine generation mode
        generation_mode = data.get('generation_mode', 'single')  # 'single' or 'multi'
        meta = data.get('meta') or {}
        
        # Extract time and period configuration
        time_config = data.get('time_config', {})
        if time_config:
            meta['time_config'] = time_config
        
        # Get sections if multi-timetable mode
        sections = None
        if generation_mode == 'multi':
            section_names = data.get('section_ids', [])  # Actually section names, not IDs
            
            if not section_names:
                db.close()
                return jsonify({
                    'success': False,
                    'errors': [{
                        'type': 'error',
                        'code': 'INVALID_INPUT',
                        'message': 'No sections provided for multi-timetable generation',
                        'details': {'generation_mode': 'multi'},
                        'suggestions': ['Provide section names in section_ids array']
                    }]
                }), 400
            
            # Section names provided - create or get sections from metadata
            sections_meta = meta.get('sections', [])
            sections = []
            
            for section_name in section_names:
                # Find metadata for this section
                section_meta = next((s for s in sections_meta if s.get('name') == section_name), None)
                
                # Check if section already exists
                existing_section = db.query(Section).filter(
                    Section.name == section_name,
                    Section.user_id == user_id
                ).first()
                
                if existing_section:
                    sections.append(existing_section)
                elif section_meta:
                    # Create new section
                    new_section = Section(
                        name=section_name,
                        semester=meta.get('semester'),
                        programme=meta.get('programme_name') or meta.get('programmeName'),
                        class_strength=section_meta.get('classStrength') or section_meta.get('class_strength'),
                        lecture_hall=section_meta.get('lectureHall') or section_meta.get('lecture_hall') or section_meta.get('hall'),
                        class_teacher_id=section_meta.get('class_teacher_id'),
                        user_id=user_id
                    )
                    db.add(new_section)
                    db.flush()  # Get the ID
                    sections.append(new_section)
            
            if not sections:
                db.close()
                return jsonify({
                    'success': False,
                    'errors': [{
                        'type': 'error',
                        'code': 'INVALID_INPUT',
                        'message': 'No valid sections found for multi-timetable generation',
                        'details': {'section_names': section_names},
                        'suggestions': ['Verify section names and metadata are correct']
                    }]
                }), 400

        # Generate timetable(s)
        success, result, errors = gen.generate_timetable(
            teachers=teachers,
            subjects=subjects,
            timetable_name=data['name'],
            extra_info=meta,
            sections=sections,
            generation_mode=generation_mode
        )

        # Process errors - convert to structured format if needed
        structured_errors = []
        structured_warnings = []
        
        if errors:
            # Check if errors are already TimetableError objects
            from timetable_generator.error_reporter import TimetableError
            
            for error in errors:
                if isinstance(error, TimetableError):
                    # Already structured
                    if error.type == 'error':
                        structured_errors.append(error.to_dict())
                    else:
                        structured_warnings.append(error.to_dict())
                elif isinstance(error, dict):
                    # Already a dict, check type
                    if error.get('type') == 'error':
                        structured_errors.append(error)
                    else:
                        structured_warnings.append(error)
                else:
                    # Legacy string error - convert to structured format
                    structured_errors.append({
                        'type': 'error',
                        'code': 'GENERATION_FAILED',
                        'message': str(error),
                        'details': {},
                        'suggestions': ['Review input data and try again']
                    })
        
        # Cache result data before closing session
        result_data = None
        if success:
            if isinstance(result, list):  # Multiple timetables
                result_data = {
                    'success': True,
                    'message': f'{len(result)} timetables generated successfully',
                    'timetable_ids': [tt.id for tt in result],
                    'count': len(result)
                }
            else:  # Single timetable
                result_data = {
                    'success': True,
                    'message': 'Timetable generated successfully',
                    'timetable_id': result.id if result else None,
                    'conflicts': getattr(result, 'conflicts_detected', 0)
                }
            
            # Include warnings even on success
            if structured_warnings:
                result_data['warnings'] = structured_warnings
        
        db.close()

        if success:
            return jsonify(result_data), 201
        else:
            # Return structured error response
            error_response = {
                'success': False,
                'errors': structured_errors if structured_errors else [{
                    'type': 'error',
                    'code': 'GENERATION_FAILED',
                    'message': 'No valid timetable solution found',
                    'details': {},
                    'suggestions': [
                        'Review subject and teacher assignments',
                        'Check for scheduling conflicts',
                        'Verify workload configuration'
                    ]
                }]
            }
            
            # Include warnings if any
            if structured_warnings:
                error_response['warnings'] = structured_warnings
            
            return jsonify(error_response), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'errors': [{
                'type': 'error',
                'code': 'INTERNAL_ERROR',
                'message': str(e),
                'details': {'exception_type': type(e).__name__},
                'suggestions': ['Contact system administrator if problem persists']
            }]
        }), 500

@app.route('/api/timetables/<int:timetable_id>', methods=['GET'])
def get_timetable(timetable_id):
    """Get a specific timetable"""
    try:
        db = SessionLocal()
        timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
        
        if not timetable:
            db.close()
            return jsonify({'error': 'Timetable not found'}), 404
        
        # Minimal serialization only
        payload = {
            'id': timetable.id,
            'name': getattr(timetable, 'name', None),
            'created_at': timetable.created_at.isoformat() if getattr(timetable, 'created_at', None) else None,
            'updated_at': timetable.updated_at.isoformat() if getattr(timetable, 'updated_at', None) else None
        }
        db.close()
        return jsonify(payload)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/api/timetables/<int:timetable_id>', methods=['DELETE'])
def delete_timetable(timetable_id):
    """Delete a timetable"""
    db = SessionLocal()
    try:
        # Get the timetable
        timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
        if not timetable:
            return jsonify({'error': 'Timetable not found'}), 404

        # Delete the timetable
        db.delete(timetable)
        db.commit()

        return jsonify({'message': 'Timetable deleted successfully'})
        
    except Exception as e:
        db.rollback()
        print(f"Error deleting timetable {timetable_id}: {str(e)}")
        return jsonify({'error': f'Failed to delete timetable: {str(e)}'}), 500
    finally:
        db.close()

@app.route('/api/timetables/delete-all', methods=['DELETE', 'POST'])
def delete_all_timetables():
    """Delete all timetables"""
    db = SessionLocal()
    try:
        # Count timetables before deletion
        count = db.query(Timetable).count()
        
        if count == 0:
            return jsonify({'message': 'No timetables to delete', 'count': 0}), 200
        
        # Delete all timetables
        db.query(Timetable).delete()
        db.commit()

        return jsonify({
            'message': f'Successfully deleted {count} timetable(s)',
            'count': count
        }), 200
        
    except Exception as e:
        db.rollback()
        print(f"Error deleting all timetables: {str(e)}")
        return jsonify({'error': f'Failed to delete timetables: {str(e)}'}), 500
    finally:
        db.close()

# Data import/export endpoints
@app.route('/api/import/teachers', methods=['POST'])
def import_teachers():
    """Import teachers from file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if not file.filename or file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file temporarily
        file_ext = os.path.splitext(file.filename)[1] if file.filename else '.xlsx'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            file.save(tmp_file.name)
            
            # Import data
            data_importer = get_data_importer()
            success, errors, teachers = data_importer.import_teachers_from_excel(tmp_file.name)
            
            # Clean up
            os.unlink(tmp_file.name)
            
            if success:
                return jsonify({
                    'message': f"Successfully imported {len(teachers)} teachers",
                    'count': len(teachers)
                }), 200
            else:
                error_msg = errors[0] if errors else 'Import failed'
                return jsonify({'error': error_msg}), 400
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import/subjects', methods=['POST'])
def import_subjects():
    """Import subjects from file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if not file.filename or file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file temporarily
        file_ext = os.path.splitext(file.filename)[1] if file.filename else '.xlsx'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            file.save(tmp_file.name)
            
            # Import data
            data_importer = get_data_importer()
            success, errors, subjects = data_importer.import_subjects_from_excel(tmp_file.name)
            
            # Clean up
            os.unlink(tmp_file.name)
            
            if success:
                return jsonify({
                    'message': f"Successfully imported {len(subjects)} subjects",
                    'count': len(subjects)
                }), 200
            else:
                error_msg = errors[0] if errors else 'Import failed'
                return jsonify({'error': error_msg}), 400
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Room imports removed - rooms table deleted

@app.route('/api/export/timetable/<int:timetable_id>', methods=['GET'])
def export_timetable(timetable_id):
    """Export timetable in specified format - sends file directly to browser for download"""
    db = None
    try:
        format_type = request.args.get('format', 'pdf').lower()
        
        if format_type not in ['pdf', 'excel', 'png', 'svg']:
            return jsonify({'error': 'Invalid format. Supported formats: pdf, excel, png, svg'}), 400
        
        # Get timetable
        db = SessionLocal()
        timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
        
        if not timetable:
            db.close()
            return jsonify({'error': 'Timetable not found'}), 404
        
        # Cache timetable name before closing session
        tt_name = str(timetable.name)
        
        # Export timetable using in-memory methods
        try:
            timetable_exporter = get_timetable_exporter()
            
            if format_type == 'pdf':
                file_bytes = timetable_exporter.export_to_pdf_bytes(timetable)
                mimetype = 'application/pdf'
                ext = 'pdf'
            elif format_type == 'excel':
                file_bytes = timetable_exporter.export_to_excel_bytes(timetable)
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                ext = 'xlsx'
            elif format_type in ('png', 'jpg'):
                file_bytes = timetable_exporter.export_to_image_bytes(timetable, format=format_type)
                mimetype = f'image/{format_type}'
                ext = format_type
            elif format_type == 'svg':
                file_bytes = timetable_exporter.export_to_svg_bytes(timetable)
                mimetype = 'image/svg+xml'
                ext = 'svg'
            else:
                db.close()
                return jsonify({'error': 'Unsupported format'}), 400
                
        except Exception as e:
            if db:
                db.close()
            import traceback
            print("=" * 80)
            print(f"EXPORT ERROR for format {format_type}:")
            traceback.print_exc()
            print("=" * 80)
            return jsonify({'error': f'Export failed: {str(e)}'}), 500
            
        # Safe to close the session after exporter produced output
        if db:
            db.close()
        
        # Ensure BytesIO is at the beginning
        file_bytes.seek(0)
        
        # Create a sanitized filename
        safe_name = ''.join(c if c.isalnum() or c in ('-', '_', ' ') else '_' for c in tt_name)
        download_name = f"SmartSched_{safe_name}.{ext}"
        
        return send_file(
            file_bytes,
            mimetype=mimetype,
            as_attachment=True,
            download_name=download_name
        )
            
    except Exception as e:
        if db:
            db.close()
        import traceback
        print("=" * 80)
        print("EXPORT ENDPOINT ERROR:")
        traceback.print_exc()
        print("=" * 80)
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/timetable/studio', methods=['POST'])
def export_timetable_from_studio():
    """
    Export timetable from Design Studio HTML - pixel-perfect export.
    Accepts HTML content from the frontend and exports to PDF/Excel/PNG.
    
    Request body:
    {
        "html": "full HTML of timetable",
        "css": "optional CSS styles",
        "format": "pdf|excel|png",
        "name": "timetable name for filename"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'html' not in data or 'format' not in data:
            return jsonify({'error': 'Missing required fields: html, format'}), 400
        
        html_content = data['html']
        css_content = data.get('css', '')
        format_type = data['format'].lower()
        timetable_name = data.get('name', 'timetable')
        
        if format_type not in ['pdf', 'excel', 'png']:
            return jsonify({'error': 'Invalid format. Supported: pdf, excel, png'}), 400
        
        # Export using HTML-based exporter
        timetable_exporter = get_timetable_exporter()
        file_bytes = timetable_exporter.export_from_html(html_content, format_type, css_content)
        
        # Determine mimetype and extension
        if format_type == 'pdf':
            mimetype = 'application/pdf'
            ext = 'pdf'
        elif format_type == 'excel':
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ext = 'xlsx'
        elif format_type == 'png':
            mimetype = 'image/png'
            ext = 'png'
        else:
            return jsonify({'error': 'Unsupported format'}), 400
        
        # Ensure BytesIO is at the beginning
        file_bytes.seek(0)
        
        # Create sanitized filename
        safe_name = ''.join(c if c.isalnum() or c in ('-', '_', ' ') else '_' for c in timetable_name)
        download_name = f"SmartSched_{safe_name}.{ext}"
        
        return send_file(
            file_bytes,
            mimetype=mimetype,
            as_attachment=True,
            download_name=download_name
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Statistics endpoint
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        db = SessionLocal()
        
        teacher_count = db.query(Teacher).count()
        subject_count = db.query(Subject).count()
        timetable_count = db.query(Timetable).count()
        section_count = db.query(Section).count()
        
        db.close()
        
        return jsonify({
            'teachers': teacher_count,
            'subjects': subject_count,
            'rooms': 0,  # Rooms removed, kept for compatibility
            'timetables': timetable_count,
            'sections': section_count
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Configuration endpoints
@app.route('/api/config/workload', methods=['GET'])
def get_workload_config():
    """Get current workload configuration"""
    try:
        config = WorkloadConfig()
        return jsonify({
            'multi_timetable_min_hours': config.multi_timetable_min_hours,
            'multi_timetable_max_hours': config.multi_timetable_max_hours,
            'single_timetable_target_hours': config.single_timetable_target_hours,
            'max_theory_subjects': config.max_theory_subjects,
            'max_lab_subjects': config.max_lab_subjects,
            'require_rest_between_classes': config.require_rest_between_classes
        })
    except Exception as e:
        print(f"Error in get_workload_config: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/workload', methods=['POST'])
def update_workload_config():
    """Update workload configuration (returns updated config for client to use)"""
    try:
        data = request.get_json()
        config = WorkloadConfig()
        
        # Update configuration based on provided data
        if 'multi_timetable_min_hours' in data:
            config.multi_timetable_min_hours = int(data['multi_timetable_min_hours'])
        if 'multi_timetable_max_hours' in data:
            config.multi_timetable_max_hours = int(data['multi_timetable_max_hours'])
        if 'single_timetable_target_hours' in data:
            config.single_timetable_target_hours = int(data['single_timetable_target_hours'])
        if 'max_theory_subjects' in data:
            config.max_theory_subjects = int(data['max_theory_subjects'])
        if 'max_lab_subjects' in data:
            config.max_lab_subjects = int(data['max_lab_subjects'])
        if 'require_rest_between_classes' in data:
            config.require_rest_between_classes = bool(data['require_rest_between_classes'])
        
        return jsonify({
            'message': 'Configuration updated (client-side only)',
            'config': {
                'multi_timetable_min_hours': config.multi_timetable_min_hours,
                'multi_timetable_max_hours': config.multi_timetable_max_hours,
                'single_timetable_target_hours': config.single_timetable_target_hours,
                'max_theory_subjects': config.max_theory_subjects,
                'max_lab_subjects': config.max_lab_subjects,
                'require_rest_between_classes': config.require_rest_between_classes
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Data validation endpoint
@app.route('/api/validate', methods=['GET'])
def validate_data():
    """Validate system data"""
    try:
        db = SessionLocal()
        
        issues = []
        
        # Check for basic data
        if db.query(Teacher).count() == 0:
            issues.append('No teachers found')
        
        if db.query(Subject).count() == 0:
            issues.append('No subjects found')
        # rooms removed: no validation required
        
        # Subjects without a teacher are allowed (e.g., free periods), so do not flag them
        
        db.close()
        
        return jsonify({
            'valid': len(issues) == 0,
            'issues': issues,
            'message': 'Data validation passed' if len(issues) == 0 else 'Data validation issues found'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# AI Scheduler endpoints
try:
    from ai.scheduler import AIScheduler
    ai_scheduler = AIScheduler()
    AI_ENABLED = True
except Exception as e:
    print(f"Warning: AI Scheduler not available: {e}")
    AI_ENABLED = False
    ai_scheduler = None

@app.route('/api/ai/status', methods=['GET'])
def ai_status():
    """Get AI/ML status"""
    try:
        if not AI_ENABLED or not ai_scheduler:
            return jsonify({
                'ai_enabled': False,
                'ml_models_loaded': False,
                'status': 'AI components not available',
                'features': []
            })
        
        return jsonify({
            'ai_enabled': True,
            'ml_models_loaded': ai_scheduler.ml_optimizer.is_fitted if ai_scheduler and ai_scheduler.ml_optimizer else False,
            'status': 'AI-Powered Scheduling Active' if AI_ENABLED else 'Standard Mode',
            'features': [
                'Smart Slot Ordering',
                'AI Explanations',
                'Feature Engineering',
                'Workload Optimization'
            ] if AI_ENABLED else []
        })
    except Exception as e:
        return jsonify({
            'ai_enabled': False,
            'ml_models_loaded': False,
            'status': f'Error: {str(e)}',
            'features': []
        })

@app.route('/api/ai/schedule/generate', methods=['POST'])
def ai_generate_schedule():
    """Generate timetable using AI scheduler"""
    if not AI_ENABLED:
        return jsonify({'error': 'AI Scheduler not available. Install dependencies: pip install scikit-learn numpy scipy'}), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Generate timetable using AI
        result = ai_scheduler.generate_timetable(
            courses=data.get('courses', []),
            rooms=data.get('rooms', []),
            faculty=data.get('faculty', []),
            constraints=data.get('constraints')
        ) if ai_scheduler else None
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/explanation/<assignment_id>', methods=['GET'])
def ai_get_explanation(assignment_id):
    """Get explanation for a specific assignment"""
    if not AI_ENABLED:
        return jsonify({'error': 'AI Scheduler not available'}), 503
    
    try:
        explanation = ai_scheduler.get_explanation(assignment_id) if ai_scheduler else None
        return jsonify(explanation), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/feedback', methods=['POST'])
def ai_collect_feedback():
    """Collect feedback for continuous learning"""
    if not AI_ENABLED:
        return jsonify({'error': 'AI Scheduler not available'}), 503
    
    try:
        data = request.get_json()
        result = ai_scheduler.collect_feedback(
            timetable_id=data.get('timetable_id'),
            feedback=data
        ) if ai_scheduler else None
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/health', methods=['GET'])
def ai_health_check():
    """Check AI scheduler health"""
    return jsonify({
        'status': 'healthy' if AI_ENABLED else 'unavailable',
        'ai_enabled': AI_ENABLED,
        'ml_models_loaded': ai_scheduler.ml_optimizer.is_fitted if ai_scheduler and ai_scheduler.ml_optimizer else False,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/')
def serve_frontend():
    """Serve the main frontend page"""
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files from frontend directory"""
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
    return send_from_directory(frontend_dir, filename)

# AI Scheduler endpoints
try:
    from ai.scheduler import AIScheduler
    ai_scheduler = AIScheduler()
    AI_ENABLED = True
except Exception as e:
    print(f"Warning: AI Scheduler not available: {e}")
    AI_ENABLED = False
    ai_scheduler = None

@app.route('/api/export', methods=['POST'])
def export_timetable_from_html():
    """Export timetable to PDF, PNG, or Excel"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ('html', 'format')):
            return jsonify({'error': 'HTML content and format are required'}), 400
            
        html_content = data['html']
        format_type = data['format'].lower()
        css_content = data.get('css', '')
        
        if format_type not in ['pdf', 'png', 'excel']:
            return jsonify({'error': 'Invalid format. Supported: pdf, png, excel'}), 400
            
        exporter = get_timetable_exporter()
        output = exporter.export_from_html(html_content, format_type, css_content)
        
        # Set appropriate content type and filename
        if format_type == 'pdf':
            mimetype = 'application/pdf'
            filename = 'timetable.pdf'
        elif format_type == 'png':
            mimetype = 'image/png'
            filename = 'timetable.png'
        elif format_type == 'excel':
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = 'timetable.xlsx'
            
        return send_file(
            output,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Ensure database and tables exist before starting the API
    setup_database()
    print("Starting API server on http://localhost:5000")
    if AI_ENABLED:
        print("[OK] AI Scheduler enabled - endpoints available at /api/ai/*")
    else:
        print("[!]  AI Scheduler disabled - install dependencies to enable")
    app.run(debug=True, host='0.0.0.0', port=5000)
