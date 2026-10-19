"""Tạo async engine + sessionmaker cho PostgreSQL.

Phụ trách: TV1 · [S1] Skeleton FastAPI · [S2] Schema PostgreSQL & migrations
"""

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        # asyncpg mặc định chờ kết nối 60 s: request sẽ treo khi DB chết
        connect_args={"timeout": settings.client_timeout_seconds},
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
