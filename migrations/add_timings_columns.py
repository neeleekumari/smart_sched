"""
Migration: Add timings and time_config columns to timetables table
"""
import os
import sys

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, inspect, text
from config import Config

def migrate():
    """Add timings and time_config columns to timetables table"""
    
    try:
        # Get database URL from config
        database_url = Config.DATABASE_URL
        print(f"Connecting to database: {database_url.split('@')[1] if '@' in database_url else database_url}")
        
        # Create engine
        engine = create_engine(database_url)
        
        # Check if table exists
        inspector = inspect(engine)
        if 'timetables' not in inspector.get_table_names():
            print("⚠️  'timetables' table doesn't exist yet.")
            print("   The columns will be created automatically when you start the server.")
            return True
        
        # Get existing columns
        columns = [col['name'] for col in inspector.get_columns('timetables')]
        
        with engine.connect() as conn:
            # Add timings column if it doesn't exist
            if 'timings' not in columns:
                print("Adding 'timings' column...")
                conn.execute(text("ALTER TABLE timetables ADD COLUMN timings JSON"))
                conn.commit()
                print("✅ Added 'timings' column")
            else:
                print("ℹ️  'timings' column already exists")
            
            # Add time_config column if it doesn't exist
            if 'time_config' not in columns:
                print("Adding 'time_config' column...")
                conn.execute(text("ALTER TABLE timetables ADD COLUMN time_config JSON"))
                conn.commit()
                print("✅ Added 'time_config' column")
            else:
                print("ℹ️  'time_config' column already exists")
        
        print("\n✅ Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print(f"   Error details: {type(e).__name__}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRATION: Add timings and time_config columns")
    print("=" * 60)
    print()
    
    success = migrate()
    
    if success:
        print("\nNext steps:")
        print("1. Restart the API server: python run_app.py")
        print("2. Generate a new timetable to test the changes")
        print("3. Timings will now be accurate based on your configuration!")
    else:
        print("\nPlease fix the errors above and try again.")
