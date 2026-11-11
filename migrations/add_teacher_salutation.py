"""
Migration: Add title column to teachers table
"""
import os
import sys

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, inspect, text
from config import Config

def migrate():
    """Add title column to teachers table"""
    
    try:
        # Get database URL from config
        database_url = Config.DATABASE_URL
        print(f"Connecting to database: {database_url.split('@')[1] if '@' in database_url else database_url}")
        
        # Create engine
        engine = create_engine(database_url)
        
        # Check if table exists
        inspector = inspect(engine)
        if 'teachers' not in inspector.get_table_names():
            print("⚠️  'teachers' table doesn't exist yet.")
            print("   The column will be created automatically when you start the server.")
            return True
        
        # Get existing columns
        columns = [col['name'] for col in inspector.get_columns('teachers')]
        
        with engine.connect() as conn:
            # Add title column if it doesn't exist
            if 'title' not in columns:
                print("Adding 'title' column...")
                conn.execute(text("ALTER TABLE teachers ADD COLUMN title VARCHAR(10)"))
                conn.commit()
                print("✅ Added 'title' column")
            else:
                print("ℹ️  'title' column already exists")
        
        print("\n✅ Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print(f"   Error details: {type(e).__name__}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRATION: Add title column to teachers")
    print("=" * 60)
    print()
    
    success = migrate()
    
    if success:
        print("\nNext steps:")
        print("1. Restart the API server: python run_app.py")
        print("2. Add teachers with titles (Mr., Mrs., Dr., Prof., etc.)")
        print("3. Titles will be displayed professionally in the UI!")
    else:
        print("\nPlease fix the errors above and try again.")
