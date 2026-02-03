"""
Database Configuration
======================
SQLAlchemy async setup for PostgreSQL.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Database URL from environment or default to local PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/bentonville_gas"
)

# For sync operations (Alembic migrations)
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set True for SQL logging
    pool_size=5,
    max_overflow=10,
)

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency for FastAPI routes to get a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables (for development). Use Alembic in production."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()
