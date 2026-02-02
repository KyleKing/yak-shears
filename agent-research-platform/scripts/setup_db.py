#!/usr/bin/env python
"""Setup database with pgvector extension and run migrations."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncpg
from alembic import command
from alembic.config import Config

from research_platform.config import settings


async def create_database_if_not_exists():
    """Create database if it doesn't exist."""
    # Parse database URL to get connection info
    url = settings.database_url.replace("postgresql+asyncpg://", "")
    parts = url.split("@")
    creds = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    username = creds[0]
    password = creds[1]
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 5432
    database = host_db[1].split("?")[0]

    print(f"Connecting to PostgreSQL at {host}:{port}")

    # Connect to default postgres database
    try:
        conn = await asyncpg.connect(
            user=username, password=password, host=host, port=port, database="postgres"
        )

        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", database
        )

        if not exists:
            print(f"Creating database: {database}")
            await conn.execute(f'CREATE DATABASE "{database}"')
            print(f"✓ Database {database} created")
        else:
            print(f"✓ Database {database} already exists")

        await conn.close()

    except Exception as e:
        print(f"Error creating database: {e}")
        raise


async def enable_pgvector():
    """Enable pgvector extension."""
    url = settings.database_url.replace("postgresql+asyncpg://", "")
    parts = url.split("@")
    creds = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    username = creds[0]
    password = creds[1]
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 5432
    database = host_db[1].split("?")[0]

    print(f"Enabling pgvector extension in {database}")

    try:
        conn = await asyncpg.connect(
            user=username, password=password, host=host, port=port, database=database
        )

        # Check if extension exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        )

        if not exists:
            await conn.execute("CREATE EXTENSION vector")
            print("✓ pgvector extension enabled")
        else:
            print("✓ pgvector extension already enabled")

        await conn.close()

    except Exception as e:
        print(f"Error enabling pgvector: {e}")
        print("Make sure pgvector is installed: https://github.com/pgvector/pgvector")
        raise


def run_migrations():
    """Run Alembic migrations."""
    print("Running database migrations")

    # Get alembic config
    alembic_cfg = Config("alembic.ini")

    # Run upgrade to head
    command.upgrade(alembic_cfg, "head")

    print("✓ Migrations completed")


async def main():
    """Setup database."""
    print("=== Database Setup ===\n")

    try:
        # Step 1: Create database
        await create_database_if_not_exists()

        # Step 2: Enable pgvector
        await enable_pgvector()

        # Step 3: Run migrations
        run_migrations()

        print("\n✓ Database setup complete!")
        print(f"\nDatabase URL: {settings.database_url}")

    except Exception as e:
        print(f"\n✗ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
