"""
Apply Supabase migration for Que Bella database schema
"""
import os
import asyncio
from supabase_client import get_supabase

async def apply_migration():
    """Apply the database migration to Supabase"""
    
    # Read the migration file
    migration_path = "/app/supabase_migration.sql"
    
    try:
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        
        # Get Supabase client
        supabase = get_supabase()
        
        print("🚀 Applying Supabase migration...")
        
        # Execute the migration
        result = supabase.rpc('exec_sql', {'sql': migration_sql})
        
        if result.data:
            print("✅ Migration applied successfully!")
            print(f"Result: {result.data}")
        else:
            print("❌ Migration failed!")
            print(f"Error: {result}")
            
    except Exception as e:
        print(f"❌ Error applying migration: {e}")
        
        # Alternative approach - apply migration in chunks
        print("\n🔄 Trying alternative approach - applying migration via direct SQL execution...")
        
        try:
            # For now, let's just print the migration and apply it manually
            print("\n📝 Please apply this migration manually in Supabase SQL Editor:")
            print("=" * 80)
            with open(migration_path, 'r') as f:
                print(f.read())
            print("=" * 80)
            
        except Exception as e2:
            print(f"❌ Error reading migration file: {e2}")

if __name__ == "__main__":
    asyncio.run(apply_migration())
