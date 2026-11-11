"""
Admin registration with email domain setup
"""
from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session
from typing import List, Tuple
from models import User, AllowedDomain
from .password_utils import PasswordUtils
from .token_manager import TokenManager
import re

admin_registration_bp = Blueprint('admin_registration', __name__, url_prefix='/api/admin')

def validate_email_format(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def parse_domains(domains_input: str) -> List[str]:
    """
    Parse comma-separated domains input
    
    Args:
        domains_input: Comma-separated domains (e.g., "@college.ac.in, @university.edu")
    
    Returns:
        List of normalized domains
    """
    if not domains_input:
        return []
    
    # Split by comma and clean up
    domains = [d.strip() for d in domains_input.split(',')]
    
    # Normalize each domain
    normalized = []
    for domain in domains:
        if domain:
            normalized_domain = AllowedDomain.normalize_domain(domain)
            if normalized_domain not in normalized:  # Avoid duplicates
                normalized.append(normalized_domain)
    
    return normalized

def validate_domains(domains: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate list of domains
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    if not domains:
        errors.append("At least one email domain is required")
        return False, errors
    
    for domain in domains:
        is_valid, error_msg = AllowedDomain.validate_domain_format(domain)
        if not is_valid:
            errors.append(f"Invalid domain '{domain}': {error_msg}")
    
    return len(errors) == 0, errors

@admin_registration_bp.route('/register', methods=['POST'])
def register_admin():
    """
    Register a new admin user with email domain setup
    
    Request body:
    {
        "username": "admin",
        "email": "admin@example.com",
        "password": "SecurePass123!",
        "full_name": "Admin User",
        "allowed_domains": "@college.ac.in, @university.edu"
    }
    
    Response:
    {
        "message": "Admin registered successfully",
        "user": {...},
        "domains_added": ["@college.ac.in", "@university.edu"]
    }
    """
    from api.app import SessionLocal
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'allowed_domains']
        missing_fields = [f for f in required_fields if f not in data or not data[f]]
        
        if missing_fields:
            return jsonify({
                'error': f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
        
        username = data['username'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        full_name = data.get('full_name', '').strip()
        domains_input = data['allowed_domains']
        
        # Validate email format
        if not validate_email_format(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate username length
        if len(username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters long'}), 400
        
        # Parse and validate domains
        domains = parse_domains(domains_input)
        is_valid, domain_errors = validate_domains(domains)
        
        if not is_valid:
            return jsonify({
                'error': 'Invalid email domains',
                'details': domain_errors
            }), 400
        
        # Create database session
        db = SessionLocal()
        
        try:
            # Check if username or email already exists
            existing_user = db.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                if existing_user.username == username:
                    return jsonify({'error': 'Username already exists'}), 400
                if existing_user.email == email:
                    return jsonify({'error': 'Email already exists'}), 400
            
            # Validate password strength
            password_utils = PasswordUtils()
            is_strong, password_errors = password_utils.is_strong_password(password)
            
            if not is_strong:
                return jsonify({
                    'error': 'Password does not meet requirements',
                    'details': password_errors
                }), 400
            
            # Create admin user
            hashed_password = password_utils.hash_password(password)
            admin_user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                full_name=full_name,
                is_active=True,
                is_admin=True,
                role='admin'
            )
            
            db.add(admin_user)
            db.flush()  # Get user ID
            
            # Add allowed domains
            added_domains = []
            duplicate_domains = []
            
            for domain in domains:
                # Check if domain already exists
                existing_domain = db.query(AllowedDomain).filter(
                    AllowedDomain.domain == domain
                ).first()
                
                if existing_domain:
                    # Link to this new admin so they can use it
                    existing_domain.created_by_user_id = admin_user.id
                    
                    # Reactivate if it was deactivated
                    if not existing_domain.is_active:
                        existing_domain.is_active = True
                        
                    # Treat as added for this user
                    added_domains.append(domain)
                else:
                    # Create new domain
                    new_domain = AllowedDomain(
                        domain=domain,
                        is_active=True,
                        created_by_user_id=admin_user.id,
                        notes=f"Added during admin registration by {username}"
                    )
                    db.add(new_domain)
                    added_domains.append(domain)
            
            # Commit transaction
            db.commit()
            
            # Prepare response
            response = {
                'message': 'Admin registered successfully',
                'user': {
                    'id': admin_user.id,
                    'username': admin_user.username,
                    'email': admin_user.email,
                    'role': admin_user.role,
                    'is_admin': admin_user.is_admin
                },
                'domains_added': added_domains
            }
            
            if duplicate_domains:
                response['warning'] = f"Some domains already existed: {', '.join(duplicate_domains)}"
            
            return jsonify(response), 201
            
        except Exception as e:
            db.rollback()
            return jsonify({'error': f'Registration failed: {str(e)}'}), 500
        finally:
            db.close()
            
    except Exception as e:
        return jsonify({'error': f'Invalid request: {str(e)}'}), 400

@admin_registration_bp.route('/domains', methods=['GET'])
def get_allowed_domains():
    """
    Get all allowed email domains
    
    Response:
    {
        "domains": [
            {
                "id": 1,
                "domain": "@college.ac.in",
                "is_active": true,
                "created_at": "2026-02-06T10:00:00"
            }
        ]
    }
    """
    from api.app import SessionLocal
    from auth.decorators import get_current_user
    
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1].strip()
        
        db = SessionLocal()
        
        try:
            user, error = get_current_user(db, token)
            
            if error or not user:
                return jsonify({'error': 'Unauthorized'}), 401
            
            # Only admins can view domains
            if not user.is_admin:
                return jsonify({'error': 'Admin access required'}), 403
            
            # Get all domains
            domains = db.query(AllowedDomain).order_by(AllowedDomain.created_at.desc()).all()
            
            return jsonify({
                'domains': [d.to_dict() for d in domains]
            }), 200
            
        finally:
            db.close()
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_registration_bp.route('/domains', methods=['POST'])
def add_allowed_domain():
    """
    Add a new allowed email domain (admin only)
    
    Request body:
    {
        "domain": "@newcollege.edu",
        "notes": "Optional notes"
    }
    """
    from api.app import SessionLocal
    from auth.decorators import get_current_user
    
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1].strip()
        
        data = request.get_json()
        
        if not data or 'domain' not in data:
            return jsonify({'error': 'Domain is required'}), 400
        
        domain_input = data['domain'].strip()
        notes = data.get('notes', '').strip()
        
        # Normalize domain
        domain = AllowedDomain.normalize_domain(domain_input)
        
        # Validate domain
        is_valid, error_msg = AllowedDomain.validate_domain_format(domain)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        db = SessionLocal()
        
        try:
            user, error = get_current_user(db, token)
            
            if error or not user:
                return jsonify({'error': 'Unauthorized'}), 401
            
            # Only admins can add domains
            if not user.is_admin:
                return jsonify({'error': 'Admin access required'}), 403
            
            # Check if domain already exists
            existing_domain = db.query(AllowedDomain).filter(
                AllowedDomain.domain == domain
            ).first()
            
            if existing_domain:
                if existing_domain.is_active:
                    return jsonify({'error': 'Domain already exists'}), 400
                else:
                    # Reactivate
                    existing_domain.is_active = True
                    existing_domain.notes = notes if notes else existing_domain.notes
                    db.commit()
                    return jsonify({
                        'message': 'Domain reactivated',
                        'domain': existing_domain.to_dict()
                    }), 200
            
            # Create new domain
            new_domain = AllowedDomain(
                domain=domain,
                is_active=True,
                created_by_user_id=user.id,
                notes=notes
            )
            
            db.add(new_domain)
            db.commit()
            db.refresh(new_domain)
            
            return jsonify({
                'message': 'Domain added successfully',
                'domain': new_domain.to_dict()
            }), 201
            
        finally:
            db.close()
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_registration_bp.route('/domains/<int:domain_id>', methods=['PUT'])
def update_allowed_domain(domain_id):
    """
    Update an allowed email domain (admin only)
    
    Request body:
    {
        "is_active": false,
        "notes": "Updated notes"
    }
    """
    from api.app import SessionLocal
    from auth.decorators import get_current_user
    
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1].strip()
        
        data = request.get_json()
        
        db = SessionLocal()
        
        try:
            user, error = get_current_user(db, token)
            
            if error or not user:
                return jsonify({'error': 'Unauthorized'}), 401
            
            # Only admins can update domains
            if not user.is_admin:
                return jsonify({'error': 'Admin access required'}), 403
            
            # Get domain
            domain = db.query(AllowedDomain).filter(AllowedDomain.id == domain_id).first()
            
            if not domain:
                return jsonify({'error': 'Domain not found'}), 404
            
            # Update fields
            if 'is_active' in data:
                domain.is_active = bool(data['is_active'])
            
            if 'notes' in data:
                domain.notes = data['notes'].strip()
            
            db.commit()
            db.refresh(domain)
            
            return jsonify({
                'message': 'Domain updated successfully',
                'domain': domain.to_dict()
            }), 200
            
        finally:
            db.close()
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_registration_bp.route('/domains/<int:domain_id>', methods=['DELETE'])
def delete_allowed_domain(domain_id):
    """
    Delete (deactivate) an allowed email domain (admin only)
    """
    from api.app import SessionLocal
    from auth.decorators import get_current_user
    
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1].strip()
        
        db = SessionLocal()
        
        try:
            user, error = get_current_user(db, token)
            
            if error or not user:
                return jsonify({'error': 'Unauthorized'}), 401
            
            # Only admins can delete domains
            if not user.is_admin:
                return jsonify({'error': 'Admin access required'}), 403
            
            # Get domain
            domain = db.query(AllowedDomain).filter(AllowedDomain.id == domain_id).first()
            
            if not domain:
                return jsonify({'error': 'Domain not found'}), 404
            
            # Soft delete (deactivate)
            domain.is_active = False
            db.commit()
            
            return jsonify({
                'message': 'Domain deactivated successfully'
            }), 200
            
        finally:
            db.close()
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
