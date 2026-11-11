# Teacher Email Domain Verification System

## Overview

This system automatically verifies and assigns teacher roles to users based on their email domain. When a user registers or logs in with an email from a configured university domain (e.g., `@college.ac.in`), they are automatically assigned the `teacher` role and a teacher profile is created.

## Features

- ✅ **Automatic Role Detection**: Users with university email domains are automatically assigned `teacher` role
- ✅ **Auto-Create Teacher Profile**: Teacher profiles are automatically created on first login
- ✅ **Verification Status**: Teachers start with `pending_verification` status
- ✅ **Protected Routes**: Decorators for teacher-only and verified-teacher-only endpoints
- ✅ **Secure Authentication**: Uses bcrypt password hashing and JWT tokens
- ✅ **Admin Verification**: Admins can verify or reject teacher accounts

## Configuration

### 1. Environment Variables

Add to your `.env` file:

```env
# Teacher Email Domain Verification
TEACHER_EMAIL_DOMAIN=@college.ac.in
```

You can change `@college.ac.in` to your institution's email domain.

### 2. Database Migration

The system adds two new fields:

**User Model:**
- `role` (String): User role - 'user', 'teacher', or 'admin'

**Teacher Model:**
- `verification_status` (String): Verification status - 'pending_verification', 'verified', or 'rejected'
- `email` (String): Now has unique constraint and index

Run database migration:

```bash
# Using Alembic (recommended)
alembic revision --autogenerate -m "Add teacher verification fields"
alembic upgrade head

# Or drop and recreate (development only)
python -c "from models import Base; from sqlalchemy import create_engine; from config import Config; engine = create_engine(Config.DATABASE_URL); Base.metadata.drop_all(engine); Base.metadata.create_all(engine)"
```

## How It Works

### Registration Flow

1. User registers with email `john.doe@college.ac.in`
2. System detects email ends with configured domain
3. User is created with `role='teacher'`
4. Teacher profile is auto-created with `verification_status='pending_verification'`
5. User receives confirmation

### Login Flow

1. User logs in with credentials
2. System checks if email matches teacher domain
3. If user has `role='user'` but email matches domain:
   - Role is updated to `teacher`
   - Teacher profile is auto-created
4. JWT token includes role and teacher information
5. User can access teacher-specific features

### Verification Flow

1. Teacher logs in and sees "pending verification" status
2. Admin reviews pending teachers via `/api/admin/teachers/pending`
3. Admin verifies or rejects teacher via `/api/admin/teachers/{id}/verify`
4. Verified teachers can access all teacher features

## API Endpoints

### Authentication Endpoints

#### Register User
```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "johndoe",
  "email": "john.doe@college.ac.in",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

**Response:**
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john.doe@college.ac.in",
    "role": "teacher"
  }
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "john.doe@college.ac.in",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "message": "Login successful",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john.doe@college.ac.in",
    "role": "teacher"
  }
}
```

### Teacher Endpoints

#### Get Teacher Profile
```http
GET /api/teacher/profile
Authorization: Bearer <token>
```

**Response:**
```json
{
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john.doe@college.ac.in",
    "role": "teacher"
  },
  "teacher": {
    "id": 1,
    "name": "John Doe",
    "initials": "JDO",
    "email": "john.doe@college.ac.in",
    "verification_status": "pending_verification",
    "can_teach_labs": false,
    "max_hours_per_day": 6,
    "max_hours_per_week": 30
  }
}
```

#### Teacher Dashboard (Verified Only)
```http
GET /api/teacher/dashboard
Authorization: Bearer <token>
```

**Response:**
```json
{
  "teacher": {
    "id": 1,
    "name": "John Doe",
    "verification_status": "verified"
  },
  "stats": {
    "total_subjects": 3,
    "total_timetables": 5,
    "max_hours_per_week": 30
  },
  "subjects": [...],
  "recent_timetables": [...]
}
```

#### Manage Availability (Verified Only)
```http
PUT /api/teacher/availability
Authorization: Bearer <token>
Content-Type: application/json

{
  "availability": {
    "monday": [1, 2, 3, 4, 5],
    "tuesday": [1, 2, 3, 4, 5],
    "wednesday": [1, 2, 3, 4, 5],
    "thursday": [1, 2, 3, 4, 5],
    "friday": [1, 2, 3, 4, 5]
  }
}
```

### Admin Endpoints

#### Get Pending Teachers
```http
GET /api/admin/teachers/pending
Authorization: Bearer <admin-token>
```

**Response:**
```json
{
  "count": 2,
  "teachers": [
    {
      "id": 1,
      "name": "John Doe",
      "email": "john.doe@college.ac.in",
      "verification_status": "pending_verification",
      "created_at": "2026-02-06T10:00:00"
    }
  ]
}
```

#### Verify Teacher
```http
POST /api/admin/teachers/1/verify
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "action": "verify"
}
```

**Response:**
```json
{
  "message": "Teacher John Doe has been verified",
  "teacher": {
    "id": 1,
    "name": "John Doe",
    "email": "john.doe@college.ac.in",
    "verification_status": "verified"
  }
}
```

## Using Decorators

### Available Decorators

1. **`@require_auth`**: Requires valid JWT token
2. **`@require_teacher`**: Requires teacher role
3. **`@require_verified_teacher`**: Requires verified teacher status
4. **`@require_admin`**: Requires admin role

### Example Usage

```python
from flask import Blueprint, jsonify
from auth.decorators import require_verified_teacher

teacher_bp = Blueprint('teacher', __name__)

@teacher_bp.route('/my-subjects', methods=['GET'])
@require_verified_teacher
def get_my_subjects(current_user, current_teacher, db, **kwargs):
    """Get subjects assigned to current teacher"""
    # current_user: User object
    # current_teacher: Teacher object (verified)
    # db: Database session
    
    subjects = db.query(Subject).filter(
        Subject.teacher_id == current_teacher.id
    ).all()
    
    return jsonify({
        'subjects': [s.to_dict() for s in subjects]
    }), 200
```

## Security Features

### Password Security
- **Bcrypt Hashing**: All passwords are hashed using bcrypt with salt
- **Password Strength Validation**: Enforces strong password requirements
- **No Plain Text Storage**: Passwords are never stored in plain text

### JWT Token Security
- **HS256 Algorithm**: Secure token signing
- **Expiration**: Tokens expire after configured time (default: 30 minutes)
- **Payload Validation**: All token claims are validated
- **Role-Based Access**: Tokens include role information

### Email Validation
- **Domain Verification**: Only configured domains are accepted
- **Case-Insensitive**: Email comparison is case-insensitive
- **Unique Constraint**: Email addresses must be unique

## Integration with Existing Code

### 1. Register Blueprints

Add to `api/app.py`:

```python
from auth.example_protected_routes import teacher_bp, admin_bp

# Register blueprints
app.register_blueprint(teacher_bp)
app.register_blueprint(admin_bp)
```

### 2. Update Login Response

The login endpoint already returns the updated token with role information. No changes needed.

### 3. Frontend Integration

Update your frontend to handle teacher role:

```javascript
// After login
const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
});

const data = await response.json();

if (data.token) {
    localStorage.setItem('authToken', data.token);
    
    // Check user role
    if (data.user.role === 'teacher') {
        // Redirect to teacher dashboard
        window.location.href = '/teacher/dashboard';
    } else {
        // Redirect to regular dashboard
        window.location.href = '/dashboard';
    }
}
```

## Testing

### Test Teacher Registration

```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "teacher1",
    "email": "teacher1@college.ac.in",
    "password": "SecurePass123!",
    "full_name": "Teacher One"
  }'
```

### Test Teacher Login

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "teacher1@college.ac.in",
    "password": "SecurePass123!"
  }'
```

### Test Protected Route

```bash
TOKEN="your-jwt-token-here"

curl -X GET http://localhost:5000/api/teacher/profile \
  -H "Authorization: Bearer $TOKEN"
```

## Troubleshooting

### Issue: Teacher profile not created

**Solution**: Check that:
1. Email domain matches `TEACHER_EMAIL_DOMAIN` in `.env`
2. Database has Teacher table with all required fields
3. User has `role='teacher'`

### Issue: "Teacher verification required" error

**Solution**: Teacher needs to be verified by admin:
1. Admin logs in
2. Admin calls `/api/admin/teachers/pending`
3. Admin calls `/api/admin/teachers/{id}/verify` with `action: "verify"`

### Issue: Token doesn't include role information

**Solution**: User needs to log in again after role assignment. Old tokens don't have role information.

## Production Considerations

1. **Change SECRET_KEY**: Use a strong, random secret key in production
2. **HTTPS Only**: Always use HTTPS in production
3. **Token Expiration**: Consider shorter token expiration times
4. **Rate Limiting**: Implement rate limiting on auth endpoints
5. **Email Verification**: Consider adding email verification step
6. **Audit Logging**: Log all teacher verification actions
7. **Backup Domain**: Configure multiple email domains if needed

## Support

For issues or questions, contact the development team or refer to the main project documentation.
