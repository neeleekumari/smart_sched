"""
Database migration to add allowed_domains table

This migration creates the allowed_domains table for managing
teacher email domains that are automatically verified.

Run this migration after add_teacher_verification_fields.py
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from config import Config

def run_migration():
    """Run the migration to create allowed_domains table"""
    
    engine = create_engine(Config.DATABASE_URL, echo=True)
    
    print("=" * 80)
    print("ALLOWED DOMAINS TABLE MIGRATION")
    print("=" * 80)
    print("\nThis migration will create the allowed_domains table for managing")
    print("teacher email domains that are automatically verified.")
    print("\n" + "=" * 80)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                print("\n[1/2] Creating allowed_domains table...")
                
                # Create allowed_domains table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS allowed_domains (
                        id SERIAL PRIMARY KEY,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        domain VARCHAR(100) NOT NULL UNIQUE,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_by_user_id INTEGER,
                        notes VARCHAR(500)
                    );
                """))
                
                print("✓ Successfully created allowed_domains table")
                
                print("\n[2/2] Creating indexes...")
                
                # Create index on domain
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_allowed_domains_domain 
                    ON allowed_domains(domain);
                """))
                
                # Create index on is_active
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_allowed_domains_is_active 
                    ON allowed_domains(is_active);
                """))
                
                print("✓ Successfully created indexes")
                
                # Add default domain from config if it exists
                print("\n[3/3] Adding default domain from config...")
                
                default_domain = Config.TEACHER_EMAIL_DOMAIN
                if default_domain:
                    # Check if domain already exists
                    result = conn.execute(text("""
                        SELECT id FROM allowed_domains WHERE domain = :domain
                    """), {"domain": default_domain.lower()})
                    
                    if not result.fetchone():
                        conn.execute(text("""
                            INSERT INTO allowed_domains (domain, is_active, notes)
                            VALUES (:domain, TRUE, 'Default domain from configuration')
                        """), {"domain": default_domain.lower()})
                        print(f"✓ Added default domain: {default_domain}")
                    else:
                        print(f"✓ Default domain already exists: {default_domain}")
                else:
                    print("⚠ No default domain in config (TEACHER_EMAIL_DOMAIN)")
                
                # Commit transaction
                trans.commit()
                
                print("\n" + "=" * 80)
                print("MIGRATION COMPLETED SUCCESSFULLY!")
                print("=" * 80)
                print("\nThe allowed_domains table has been created.")
                print("\nNext steps:")
                print("1. Restart your Flask application")
                print("2. Register an admin user with email domains")
                print("3. Teachers with matching email domains will be auto-verified")
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
    print("\nStarting allowed_domains table migration...")
    success = run_migration()
    
    if success:
        print("\n✓ Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Migration failed!")
        sys.exit(1)
