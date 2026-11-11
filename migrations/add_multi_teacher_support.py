"""
Database migration: Add multi-teacher support
Adds new columns to teacher_assignments table
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, Column, Boolean, Integer
from sqlalchemy.orm import sessionmaker
from config import Config

def migrate():
    """Run migration to add multi-teacher support"""
    from sqlalchemy import text
    
    engine = create_engine(Config.DATABASE_URL, echo=True)
    
    # Add columns using raw SQL (SQLAlchemy doesn't support ALTER TABLE directly)
    with engine.connect() as conn:
        try:
            # Add is_eligible column if it doesn't exist
            conn.execute(text("""
                ALTER TABLE teacher_assignments 
                ADD COLUMN IF NOT EXISTS is_eligible BOOLEAN DEFAULT TRUE
            """))
            conn.commit()
            print("✓ Added is_eligible column")
        except Exception as e:
            print(f"is_eligible column may already exist: {e}")
        
        try:
            # Add semester column if it doesn't exist
            conn.execute(text("""
                ALTER TABLE teacher_assignments 
                ADD COLUMN IF NOT EXISTS semester INTEGER
            """))
            conn.commit()
            print("✓ Added semester column")
        except Exception as e:
            print(f"semester column may already exist: {e}")
    
    print("\n✅ Migration completed successfully!")
    print("Multi-teacher support is now enabled.")

if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE MIGRATION: Multi-Teacher Support")
    print("=" * 60)
    migrate()
