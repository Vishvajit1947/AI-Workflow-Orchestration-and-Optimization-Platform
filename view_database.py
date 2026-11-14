"""
Database viewer script - connects to the actual PostgreSQL database
and displays all records from all tables.
"""
import asyncio
import sys
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine
from backend.app.config import settings

async def view_all_tables():
    """Connect to database and show all records from all tables."""
    
    print(f"\n{'='*80}")
    print(f"DATABASE VIEWER - {settings.DATABASE_URL.split('@')[1]}")
    print(f"{'='*80}\n")
    
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    
    try:
        async with engine.begin() as conn:
            # Get all table names
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result]
            
            if not tables:
                print("⚠️  No tables found in the database!")
                return
            
            print(f"Found {len(tables)} tables: {', '.join(tables)}\n")
            
            # For each table, show its structure and all records
            for table_name in tables:
                print(f"\n{'─'*80}")
                print(f"TABLE: {table_name}")
                print(f"{'─'*80}")
                
                # Get column info
                col_result = await conn.execute(text(f"""
                    SELECT column_name, data_type, character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position;
                """))
                columns = [(row[0], row[1]) for row in col_result]
                
                print("\nColumns:")
                for col_name, col_type in columns:
                    print(f"  • {col_name} ({col_type})")
                
                # Get record count
                count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = count_result.scalar()
                print(f"\nTotal records: {count}")
                
                if count > 0:
                    # Get all records
                    records_result = await conn.execute(text(f"SELECT * FROM {table_name} LIMIT 100"))
                    records = records_result.fetchall()
                    
                    print(f"\nRecords (showing up to 100):")
                    print("-" * 80)
                    
                    # Print header
                    col_names = [col[0] for col in columns]
                    header = " | ".join(f"{name[:20]:20}" for name in col_names)
                    print(header)
                    print("-" * 80)
                    
                    # Print rows
                    for record in records:
                        row_str = " | ".join(f"{str(val)[:20]:20}" for val in record)
                        print(row_str)
                else:
                    print("  (No records)")
                
                print()
    
    except Exception as e:
        print(f"\n❌ Error connecting to database: {e}")
        print(f"\nConnection string used: {settings.DATABASE_URL}")
        sys.exit(1)
    
    finally:
        await engine.dispose()
    
    print(f"\n{'='*80}")
    print("END OF DATABASE VIEW")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    asyncio.run(view_all_tables())
