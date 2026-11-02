"""Alembic env (async): lấy DATABASE_URL từ core.config, metadata từ core.db.models.

Test truyền URL riêng qua Config.set_main_option("sqlalchemy.url", ...) để không đụng DB dev.

Phụ trách: TV1 · [S2] Schema PostgreSQL & migrations
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import get_settings
from core.db.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def _configure(connection: Connection | None, **kwargs) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, **kwargs)


def run_migrations_offline() -> None:
    _configure(None, url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
