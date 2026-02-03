#!/usr/bin/env python3
"""
Database Setup Script
=====================
Sets up the PostgreSQL database for the Bentonville Gas Simulator.

Usage:
    python scripts/setup_db.py

Prerequisites:
    1. PostgreSQL must be running locally
    2. Set DATABASE_URL environment variable (optional, defaults to localhost)
"""

import os
import sys
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def create_database():
    """Create the database if it doesn't exist."""
    import asyncpg
    
    # Get connection details from DATABASE_URL or use defaults
    db_url = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/bentonville_gas"
    )
    
    # Parse URL to extract database name
    # Format: postgresql://user:pass@host:port/dbname
    parts = db_url.replace("postgresql://", "").replace("postgresql+asyncpg://", "")
    
    if "@" in parts:
        credentials, host_part = parts.split("@")
        user, password = credentials.split(":") if ":" in credentials else (credentials, "")
    else:
        user, password = "postgres", ""
        host_part = parts
    
    if "/" in host_part:
        host_port, db_name = host_part.rsplit("/", 1)
    else:
        host_port, db_name = host_part, "bentonville_gas"
    
    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host, port = host_port, 5432
    
    print(f"📦 Setting up database: {db_name}")
    print(f"   Host: {host}:{port}")
    print(f"   User: {user}")
    
    try:
        # Connect to default postgres database to create our database
        conn = await asyncpg.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database="postgres"  # Connect to default db first
        )
        
        # Check if database exists
        result = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            db_name
        )
        
        if result:
            print(f"✅ Database '{db_name}' already exists")
        else:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"✅ Created database '{db_name}'")
        
        await conn.close()
        return True
        
    except asyncpg.InvalidCatalogNameError:
        print(f"❌ Database '{db_name}' does not exist and cannot be created")
        return False
    except asyncpg.InvalidPasswordError:
        print(f"❌ Invalid password for user '{user}'")
        return False
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\nMake sure PostgreSQL is running:")
        print("  macOS:   brew services start postgresql")
        print("  Linux:   sudo systemctl start postgresql")
        print("  Docker:  docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres")
        return False


async def run_migrations():
    """Run Alembic migrations."""
    import subprocess
    
    print("\n🔄 Running database migrations...")
    
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Migrations complete")
        if result.stdout:
            print(result.stdout)
        return True
    else:
        print(f"❌ Migration failed:")
        print(result.stderr)
        return False


async def verify_tables():
    """Verify that all tables were created."""
    import asyncpg
    
    db_url = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/bentonville_gas"
    ).replace("postgresql+asyncpg://", "postgresql://")
    
    print("\n🔍 Verifying tables...")
    
    try:
        conn = await asyncpg.connect(db_url)
        
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        expected_tables = {'nodes', 'pipes', 'leaks', 'simulation_snapshots', 'alembic_version'}
        found_tables = {row['table_name'] for row in tables}
        
        print(f"   Found tables: {', '.join(found_tables)}")
        
        missing = expected_tables - found_tables
        if missing:
            print(f"   ⚠️ Missing tables: {', '.join(missing)}")
        else:
            print("   ✅ All expected tables present")
        
        await conn.close()
        return not missing
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


async def main():
    """Main setup function."""
    print("=" * 50)
    print("Bentonville Gas Simulator - Database Setup")
    print("=" * 50)
    
    # Step 1: Create database
    if not await create_database():
        sys.exit(1)
    
    # Step 2: Run migrations
    if not await run_migrations():
        sys.exit(1)
    
    # Step 3: Verify
    await verify_tables()
    
    print("\n" + "=" * 50)
    print("✅ Database setup complete!")
    print("=" * 50)
    print("\nTo enable database persistence, start the API with:")
    print("  USE_DATABASE=true uvicorn api.main:app --reload")


if __name__ == "__main__":
    asyncio.run(main())
