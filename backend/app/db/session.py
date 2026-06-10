"""
Async database session factory using SQLAlchemy 2.x + asyncpg driver.
Provides both a FastAPI dependency (get_db) and a context manager (get_db_session)
for use in MCP tool handlers that run outside the request/response cycle.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Convert sync DSN → async DSN for asyncpg
DATABASE_URL: str = (
    settings.DATABASE_URL
    .replace("postgresql://", "postgresql+asyncpg://")
    .replace("postgres://", "postgresql+asyncpg://")
)

engine = create_async_engine(
    DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    # asyncpg requires json_serializer for JSONB columns
    json_serializer=lambda obj: __import__("json").dumps(obj, ensure_ascii=False),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a DB session scoped to one HTTP request.
    Always rolls back on exception; always closes on exit.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for DB access outside the FastAPI request cycle.
    Used by MCP tool handlers and background tasks.

    Usage:
        async with get_db_session() as db:
            result = await db.execute(...)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Create all ORM-mapped tables if they don't exist.
    Idempotent — safe to call on every startup (after SQL migrations run).
    """
    import app.models  # noqa: F401 — import models to register with Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
