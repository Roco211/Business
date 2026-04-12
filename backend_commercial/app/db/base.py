"""
Database base class and session management
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models"""
    pass


# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,  # Enable connection health checks
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session as context manager
    
    Usage:
        async with get_db_context() as db:
            result = await db.execute(query)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize database
    
    Creates all tables defined in models
    """
    async with engine.begin() as conn:
        # Import all models here to ensure they are registered
        from app.models import user  # noqa
        
        # Create tables
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    """
    Drop all database tables
    
    WARNING: Use with caution!
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def check_db_connection() -> bool:
    """
    Check database connection health
    
    Returns:
        bool: True if connection is healthy
    """
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False


# Redis connection (optional)
try:
    import redis.asyncio as redis
    
    redis_client = redis.from_url(
        settings.REDIS_URL,
        password=settings.REDIS_PASSWORD,
        decode_responses=True,
    )
except ImportError:
    redis_client = None


async def get_redis():
    """
    Get Redis client
    
    Returns:
        Redis client if available, None otherwise
    """
    return redis_client


# Database utilities
class PaginationParams:
    """Pagination parameters"""
    def __init__(
        self,
        page: int = 1,
        page_size: int = 20,
        max_page_size: int = 100,
    ):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), max_page_size)
        self.offset = (self.page - 1) * self.page_size
        self.limit = self.page_size


class SortParams:
    """Sorting parameters"""
    def __init__(
        self,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        allowed_fields: list = None,
    ):
        self.sort_by = sort_by
        self.sort_order = sort_order.lower()
        
        # Validate sort order
        if self.sort_order not in ["asc", "desc"]:
            self.sort_order = "desc"
        
        # Validate sort field if allowed_fields provided
        if allowed_fields and sort_by not in allowed_fields:
            self.sort_by = "created_at"


# Query helpers
def apply_pagination(query, pagination: PaginationParams):
    """Apply pagination to query"""
    return query.offset(pagination.offset).limit(pagination.limit)


def apply_sorting(query, model, sort_params: SortParams):
    """Apply sorting to query"""
    column = getattr(model, sort_params.sort_by, None)
    if column is None:
        column = getattr(model, "created_at")
    
    if sort_params.sort_order == "asc":
        return query.order_by(column.asc())
    else:
        return query.order_by(column.desc())