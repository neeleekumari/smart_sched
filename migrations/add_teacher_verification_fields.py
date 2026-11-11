"""
Database migration to add teacher verification fields

This migration adds:
1. role field to users table (String: 'user', 'teacher', 'admin')
2. verification_status field to teachers table (String: 'pending_verification', 'verified', 'rejected')
3. Makes email field in teachers table unique and indexed

Run this migration to enable the teacher verification system.
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from config import Config

def run_migration():
    """Run the migration to add teacher verification fields"""
    
    engine = create_engine(Config.DATABASE_URL, echo=True)
    
    print("=" * 80)
    print("TEACHER VERIFICATION MIGRATION")
    print("=" * 80)
    print("\nThis migration will add the following fields:")
    print("1. users.role (String) - User role: 'user', 'teacher', or 'admin'")
    print("2. teachers.verification_status (String) - Verification status")
    print("3. Make teachers.email unique and indexed")
    print("\n" + "=" * 80)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                print("\n[1/3] Adding 'role' column to users table...")
                # Add role column to users table if it doesn't exist
                conn.execute(text("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='users' AND column_name='role'
                        ) THEN
                            ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user' NOT NULL;
                            COMMENT ON COLUMN users.role IS 'User role: user, teacher, or admin';
                        END IF;
                    END $$;
                """))
                print("✓ Successfully added 'role' column to users table")
                
                print("\n[2/3] Adding 'verification_status' column to teachers table...")
                # Add verification_status column to teachers table if it doesn't exist
                conn.execute(text("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='teachers' AND column_name='verification_status'
                        ) THEN
                            ALTER TABLE teachers ADD COLUMN verification_status VARCHAR(20) DEFAULT 'pending_verification' NOT NULL;
                            COMMENT ON COLUMN teachers.verification_status IS 'Verification status: pending_verification, verified, or rejected';
                        END IF;
                    END $$;
                """))
                print("✓ Successfully added 'verification_status' column to teachers table")
                
                print("\n[3/3] Making teachers.email unique and indexed...")
                # Make email unique and indexed if not already
                # First, check if constraint exists
                result = conn.execute(text("""
                    SELECT constraint_name 
                    FROM information_schema.table_constraints 
                    WHERE table_name='teachers' 
                    AND constraint_type='UNIQUE' 
                    AND constraint_name LIKE '%email%'
                """))
                
                if not result.fetchone():
                    # Remove any duplicate emails first (keep the first occurrence)
                    conn.execute(text("""
                        DELETE FROM teachers a USING teachers b
                        WHERE a.id > b.id 
                        AND a.email = b.email 
                        AND a.email IS NOT NULL 
                        AND a.email != '';
                    """))
                    
                    # Create a partial unique index (only for non-null, non-empty emails)
                    conn.execute(text("""
                        CREATE UNIQUE INDEX teachers_email_unique 
                        ON teachers(email) 
                        WHERE email IS NOT NULL AND email != '';
                    """))
                    print("✓ Successfully added unique constraint to teachers.email")
                else:
                    print("✓ Unique constraint already exists on teachers.email")
                
                # Check if index exists
                result = conn.execute(text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename='teachers' 
                    AND indexname LIKE '%email%'
                """))
                
                if not result.fetchone():
                    # Create index
                    conn.execute(text("""
                        CREATE INDEX idx_teachers_email ON teachers(email);
                    """))
                    print("✓ Successfully created index on teachers.email")
                else:
                    print("✓ Index already exists on teachers.email")
                
                # Commit transaction
                trans.commit()
                
                print("\n" + "=" * 80)
                print("MIGRATION COMPLETED SUCCESSFULLY!")
                print("=" * 80)
                print("\nNext steps:")
                print("1. Restart your Flask application")
                print("2. Test registration with a teacher email (e.g., teacher@college.ac.in)")
                print("3. Check that teacher role is automatically assigned")
                print("4. Verify teacher profile is auto-created with 'pending_verification' status")
                print("\n" + "=" * 80)
                
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"\n✗ Migration failed: {e}")
                print("\nRolling back changes...")
                return False
                
    except Exception as e:
        print(f"\n✗ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    print("\nStarting teacher verification migration...")
    success = run_migration()
    
    if success:
        print("\n✓ Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Migration failed!")
        sys.exit(1)
