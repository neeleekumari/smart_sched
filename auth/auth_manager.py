"""
Authentication manager for user operations with automatic teacher verification
"""
from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import User, Teacher, AllowedDomain
from .password_utils import PasswordUtils
from .token_manager import TokenManager
from config import Config

class AuthManager:
    """Manages user authentication and authorization with automatic teacher verification"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.password_utils = PasswordUtils()
        self.token_manager = TokenManager()
        self.teacher_email_domain = Config.TEACHER_EMAIL_DOMAIN  # Fallback for backward compatibility
    
    def _get_allowed_domains(self) -> List[str]:
        """Get all active allowed domains from database"""
        try:
            domains = self.db.query(AllowedDomain).filter(
                AllowedDomain.is_active == True
            ).all()
            
            domain_list = [d.domain.lower() for d in domains]
            
            # Fallback to config if no domains in database
            if not domain_list and self.teacher_email_domain:
                domain_list = [self.teacher_email_domain.lower()]
            
            return domain_list
        except Exception as e:
            print(f"Error fetching allowed domains: {e}")
            # Fallback to config
            return [self.teacher_email_domain.lower()] if self.teacher_email_domain else []
    
    def _is_teacher_email(self, email: str) -> bool:
        """Check if email belongs to any allowed teacher domain"""
        allowed_domains = self._get_allowed_domains()
        print(f"DEBUG: Checking email '{email}' against allowed domains: {allowed_domains}")
        for domain in allowed_domains:
            if email.lower().endswith(domain.lower()):
                print(f"DEBUG: Match found for domain '{domain}'")
                return True
        print(f"DEBUG: No match found for email '{email}'")
        return False
    

    
    def _generate_initials(self, name: str) -> str:
        """Generate 3-letter initials from name"""
        if not name:
            return 'TCH'
        
        parts = [p for p in name.replace('-', ' ').split() if p]
        if not parts:
            return 'TCH'
        
        if len(parts) == 1:
            # Single name: take first 3 letters
            return parts[0][:3].upper()
        
        elif len(parts) == 2:
            # Two names: first letter + stressed consonant + last initial
            first = parts[0]
            last = parts[1]
            
            if len(last) == 1:
                vowels = 'aeiouAEIOU'
                stressed_letter = ''
                for i in range(1, len(first)):
                    if first[i] not in vowels:
                        stressed_letter = first[i]
                        break
                if not stressed_letter and len(first) > 1:
                    stressed_letter = first[1]
                initials = first[0] + stressed_letter + last[0]
            else:
                initials = first[0] + last[0] + (last[1] if len(last) > 1 else first[1] if len(first) > 1 else '')
            
            return initials[:3].upper()
        
        else:
            # Three or more names: take first letter of each
            initials = ''.join(p[0] for p in parts[:3])
            return initials[:3].upper()
    
    def generate_teacher_code(self, institute_code: str) -> str:
        """Generate unique teacher code (e.g. BIT001)"""
        # Get count of teachers with this institute code
        from sqlalchemy import func
        pattern = f"{institute_code}%"
        
        # We need to find the max number used. Just counting isn't safe if deletions happen.
        # But for simplicity, let's query all codes, extract number, find max.
        # Or just use count + 1 loop until unique.
        
        # Helper to get numeric part
        def get_next_code():
            existing_codes = self.db.query(Teacher.teacher_code).filter(
                Teacher.teacher_code.like(pattern)
            ).all()
            
            max_num = 0
            for (code,) in existing_codes:
                if code and len(code) > len(institute_code):
                    try:
                        num_part = int(code[len(institute_code):])
                        if num_part > max_num:
                            max_num = num_part
                    except ValueError:
                        pass
            
            return f"{institute_code}{max_num + 1:03d}"

        new_code = get_next_code()
        # Verify uniqueness just in case (though loop above covers max)
        while self.db.query(Teacher).filter(Teacher.teacher_code == new_code).first():
             # Fallback if race condition or manual entry
             # Just increment
             num_part = int(new_code[len(institute_code):])
             new_code = f"{institute_code}{num_part + 1:03d}"
             
        return new_code

    def register_user(self, username: str, email: str, password: str, 
                     full_name: Optional[str] = None, role: Optional[str] = None,
                     institute_name: Optional[str] = None, institute_code: Optional[str] = None,
                     salutation: Optional[str] = None) -> Tuple[bool, Optional[User], list]:
        """Register a new user with automatic teacher role detection or explicit role assignment"""
        errors = []
        
        # Normalize inputs
        try:
            username = (username or '').strip()
            email = (email or '').strip()
        except Exception:
            pass
        # Use lowercase for uniqueness consistency
        normalized_username = username.lower()
        normalized_email = email.lower()

        # Validate input
        # Note: If teacher, username might be auto-generated later as teacher_code
        if role != 'teacher' and (not normalized_username or len(normalized_username) < 3):
            errors.append("Username must be at least 3 characters long")
        
        if not normalized_email or "@" not in normalized_email:
            errors.append("Invalid email address")
        
        # Check password strength
        is_strong, password_errors = self.password_utils.is_strong_password(password)
        if not is_strong:
            errors.extend(password_errors)
        
        if errors:
            return False, None, errors
        
        try:
            # Check if username already exists (unless we are auto-generating it for Teacher)
            if role != 'teacher':
                existing_user = self.db.query(User).filter(User.username == normalized_username).first()
                if existing_user:
                     errors.append("Username already exists")
                     return False, None, errors
            
            # Check if email already exists
            existing_email = self.db.query(User).filter(User.email == normalized_email).first()
            if existing_email:
                return False, None, ["Email already exists"]

            # Determine role: prioritize explicit request, then fallback to email domain
            final_role = 'user'
            generated_teacher_code = None
            
            if role and role.lower() == 'teacher':
                 final_role = 'teacher'
            elif self._is_teacher_email(normalized_email):
                 final_role = 'teacher'

            if final_role == 'teacher':
                # IF requesting teacher role, MUST match allowed domain
                if not self._is_teacher_email(normalized_email):
                    errors.append("Registration restricted to allowed teacher domains only")
                    return False, None, errors
                if not full_name:
                    errors.append("Full name is required for teacher registration")
                    return False, None, errors
                
                # --- Teacher Logic: Find Institute Code ---
                # Find Admin who owns this domain
                domain_part = normalized_email.split('@')[1]
                # We need to find which admin allowed this domain.
                # Assuming AllowedDomain is linked to User (which it isn't explicitly yet, but let's check).
                # Actually, AllowedDomain table doesn't have user_id in the view I saw.
                # BUT, I can query All Admins and check their 'institute_code' if they have one.
                # Since we don't have a direct link, let's assume valid domains belong to the *configured* institute.
                # Ideally, we should find the Admin User who has `institute_code` set.
                
                # Search via AllowedDomain table for owner
                
                # 1. Try to find the specific admin who registered this domain
                domain_part = normalized_email.split('@')[1]
                search_domain = '@' + domain_part if not domain_part.startswith('@') else domain_part
                
                allowed_domain_entry = self.db.query(AllowedDomain).filter(AllowedDomain.domain == search_domain).first()
                admin_user = None
                
                if allowed_domain_entry and allowed_domain_entry.created_by_user_id:
                     admin_user = self.db.query(User).filter(User.id == allowed_domain_entry.created_by_user_id).first()
                     if admin_user:
                         print(f"DEBUG: Found Admin via AllowedDomain: {admin_user.username} (Inst: {admin_user.institute_code})")

                # 2. Fallback: If no owner found (legacy domains), find first valid Admin with institute code
                if not admin_user:
                     print("DEBUG: No specific domain owner found. Falling back to first Admin with code.")
                     # Only consider admins who actually have a code set
                     admin_user = self.db.query(User).filter(User.is_admin == True, User.institute_code != None).first()
                
                # Use Admin's Institute Code
                inst_code = admin_user.institute_code if (admin_user and admin_user.institute_code) else "INST"
                
                # Generate Teacher Code
                generated_teacher_code = self.generate_teacher_code(inst_code)
                
                # Set Username = Teacher Code
                normalized_username = generated_teacher_code
                print(f"DEBUG: Generated Teacher Code / Username: {normalized_username}")

            # Create new user
            hashed_password = self.password_utils.hash_password(password)
            user = User(
                username=normalized_username,
                email=normalized_email,
                hashed_password=hashed_password,
                full_name=full_name,
                is_active=True,
                role=final_role,
                institute_name=institute_name, # For Admin registration
                institute_code=institute_code  # For Admin registration
            )
            
            if final_role == 'admin':
                user.is_admin = True
            
            self.db.add(user)
            self.db.flush() # Get ID without committing transaction
            
            # --- Create Teacher Profile ---
            if final_role == 'teacher':
                # Check for existing profile (unlikely given unique email check above, but safe)
                existing_teacher = self.db.query(Teacher).filter(
                    Teacher.email == normalized_email
                ).first()
                
                if existing_teacher:
                    # Link existing teacher to new user
                    existing_teacher.user_id = user.id
                    existing_teacher.verification_status = 'verified'
                    if full_name: existing_teacher.name = full_name
                    if generated_teacher_code: existing_teacher.teacher_code = generated_teacher_code
                    if salutation: existing_teacher.salutation = salutation
                else:
                    # Create new verified teacher profile
                    new_teacher = Teacher(
                        name=full_name,
                        email=normalized_email,
                        initials=self._generate_initials(full_name),
                        user_id=user.id,
                        verification_status='verified',
                        can_teach_labs=False, # Default
                        teacher_code=generated_teacher_code,
                        salutation=salutation
                    )
                    self.db.add(new_teacher)
            
            self.db.commit()
            self.db.refresh(user)
            
            # Log Code for "Email"
            if generated_teacher_code:
                print(f"\n[EMAIL MOCK] To: {email}\nSubject: Welcome to SmartSched!\nBody: Your Teacher Code is: {generated_teacher_code}. Please use this code to login.\n")
            
            return True, user, []
            
        except IntegrityError as e:
            self.db.rollback()
            return False, None, ["Username or email already exists"]
        except Exception as e:
            self.db.rollback()
            import traceback
            traceback.print_exc()
            return False, None, [f"Registration failed: {str(e)}"]
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, Optional[User], Optional[str]]:
        """Authenticate a user and return access token with automatic teacher role detection"""
        # Find user by username or email
        user = self.db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user:
            return False, None, None
        
        if not user.is_active:
            return False, None, None
        
        # Verify password
        if not self.password_utils.verify_password(password, user.hashed_password):
            return False, None, None
        
        # Auto-assign teacher role if email matches domain and role is not set
        if user.role == 'user' and self._is_teacher_email(user.email):
            try:
                user.role = 'teacher'
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                print(f"Error updating user role: {e}")
        
        # Get teacher profile if exists
        teacher_profile = None
        if user.role == 'teacher':
            teacher_profile = self.db.query(Teacher).filter(
                Teacher.email == user.email
            ).first()
            
            # If teacher profile exists but not linked to user, link it now
            if teacher_profile and not teacher_profile.user_id:
                try:
                    teacher_profile.user_id = user.id
                    teacher_profile.verification_status = 'verified'
                    self.db.commit()
                except Exception as e:
                    self.db.rollback()
                    print(f"Error linking teacher profile on login: {e}")
        
        # Create access token with role and teacher info
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
            "role": user.role,
            "teacher_id": teacher_profile.id if teacher_profile else None,
            "teacher_verified": teacher_profile.verification_status == 'verified' if teacher_profile else False
        }
        
        access_token = self.token_manager.create_access_token(token_data)
        
        return True, user, access_token
    
    def verify_token(self, token: str):
        """Verify token and return user"""
        payload = self.token_manager.verify_token(token)
        if not payload:
            return False, None
        
        user_id = payload.get("sub")
        if not user_id:
            return False, None
        
        user = self.db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            return False, None
        
        return True, user
    
    def change_password(self, user: User, old_password: str, new_password: str):
        """Change user password"""
        errors = []
        
        # Verify old password
        if not self.password_utils.verify_password(old_password, user.hashed_password):
            errors.append("Current password is incorrect")
        
        # Check new password strength
        is_strong, password_errors = self.password_utils.is_strong_password(new_password)
        if not is_strong:
            errors.extend(password_errors)
        
        if errors:
            return False, errors
        
        try:
            # Update password
            user.hashed_password = self.password_utils.hash_password(new_password)
            self.db.commit()
            return True, []
            
        except Exception as e:
            self.db.rollback()
            return False, [f"Password change failed: {str(e)}"]
    
    def update_user_profile(self, user: User, **kwargs):
        """Update user profile information"""
        errors = []
        
        try:
            # Update allowed fields
            if 'full_name' in kwargs:
                user.full_name = kwargs['full_name']
            
            if 'email' in kwargs:
                new_email = kwargs['email']
                if not new_email or "@" not in new_email:
                    errors.append("Invalid email address")
                else:
                    # Check if email is already taken by another user
                    existing_user = self.db.query(User).filter(
                        User.email == new_email,
                        User.id != user.id
                    ).first()
                    if existing_user:
                        errors.append("Email already exists")
                    else:
                        user.email = new_email
            
            if errors:
                return False, errors
            
            self.db.commit()
            return True, []
            
        except Exception as e:
            self.db.rollback()
            return False, [f"Profile update failed: {str(e)}"]
    
    def deactivate_user(self, user: User):
        """Deactivate a user account"""
        try:
            user.is_active = False
            self.db.commit()
            return True, []
        except Exception as e:
            self.db.rollback()
            return False, [f"Account deactivation failed: {str(e)}"]
    
    def activate_user(self, user: User):
        """Activate a user account"""
        try:
            user.is_active = True
            self.db.commit()
            return True, []
        except Exception as e:
            self.db.rollback()
            return False, [f"Account activation failed: {str(e)}"]
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.db.query(User).filter(User.username == username).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()
    
    def list_users(self, limit: int = 100, offset: int = 0):
        """List all users (admin function)"""
        return self.db.query(User).offset(offset).limit(limit).all()
    
    def is_admin(self, user: User) -> bool:
        """Check if user is admin"""
        return user.is_admin
    
    def make_admin(self, user: User):
        """Make user an admin"""
        try:
            user.is_admin = True
            self.db.commit()
            return True, []
        except Exception as e:
            self.db.rollback()
            return False, [f"Failed to make user admin: {str(e)}"]
    
    def remove_admin(self, user: User):
        """Remove admin privileges from user"""
        try:
            user.is_admin = False
            self.db.commit()
            return True, []
        except Exception as e:
            self.db.rollback()
            return False, [f"Failed to remove admin privileges: {str(e)}"]
