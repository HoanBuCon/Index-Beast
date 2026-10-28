"""Migration và repository với PostgreSQL thật. Mỗi lần chạy tạo một database tạm rồi xóa, không đụng DB dev.

Chạy: make up && pytest -m integration

Phụ trách: TV1 · [S2] Schema PostgreSQL & migrations
"""

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import asyncpg
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import Settings
from core.db import repositories as repo
from core.db.models import Base

pytestmark = pytest.mark.integration

TABLES = {"documents", "chunks", "entities", "conversations", "messages", "feedback", "ingestion_jobs", "eval_runs"}


def _admin_dsn(url) -> str:
    return url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)


async def _admin(url, sql: str) -> None:
    conn = await asyncpg.connect(_admin_dsn(url))
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


def _alembic(url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    base = make_url(Settings().database_url)
    name = f"ib_test_{uuid.uuid4().hex[:8]}"
    asyncio.run(_admin(base, f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    try:
        command.upgrade(_alembic(url), "head")
        yield url
    finally:
        asyncio.run(_admin(base, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


@pytest.fixture
async def session(db_url: str) -> AsyncSession:
    engine = create_async_engine(db_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as s:
            yield s
            await s.rollback()  # mỗi test tự dọn: không commit dữ liệu
    finally:
        await engine.dispose()


async def test_migration_creates_every_table_and_matches_models(db_url: str):
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
            diff = await conn.run_sync(lambda c: compare_metadata(MigrationContext.configure(c), Base.metadata))
    finally:
        await engine.dispose()

    assert tables >= TABLES
    assert diff == [], f"models lệch migration, chạy alembic revision --autogenerate: {diff}"


def test_downgrade_then_upgrade_is_clean(db_url: str):
    config = _alembic(db_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")


async def test_conversation_history_and_recent_messages(session: AsyncSession):
    conversation = await repo.create_conversation(session, channel="discord", external_ref="discord:thread:1")
    for i in range(8):
        await repo.add_message(session, conversation.id, role="user" if i % 2 == 0 else "assistant", content=f"m{i}")

    loaded = await repo.get_conversation(session, conversation.id)
    recent = await repo.recent_messages(session, conversation.id, limit=6)

    assert loaded is not None and len(loaded.messages) == 8
    assert [m.content for m in recent] == [f"m{i}" for i in range(2, 8)]


async def test_message_jsonb_sources_round_trip(session: AsyncSession):
    conversation = await repo.create_conversation(session, channel="web")
    sources = [{"index": 1, "title": "Ranni the Witch", "url": "https://example.test"}]

    message = await repo.add_message(session, conversation.id, role="assistant", content="a", sources=sources)
    await session.refresh(message)

    assert message.sources == sources


async def test_feedback_checks_rating_and_message(session: AsyncSession):
    conversation = await repo.create_conversation(session, channel="web")
    message = await repo.add_message(session, conversation.id, role="assistant", content="a")

    assert await repo.message_exists(session, message.id)
    assert not await repo.message_exists(session, uuid.uuid4())
    await repo.add_feedback(session, message.id, 1, "đúng")
    with pytest.raises(IntegrityError):
        await repo.add_feedback(session, message.id, 5, None)


async def test_upsert_document_is_idempotent_and_replace_chunks(session: AsyncSession):
    fields = {
        "source": "wikigg",
        "source_id": "123",
        "url": "https://eldenring.wiki.gg/wiki/Ranni",
        "title": "Ranni the Witch",
        "revision_id": 1,
        "raw_hash": "h1",
        "fetched_at": datetime.now(UTC),
    }
    first = await repo.upsert_document(session, **fields)
    second = await repo.upsert_document(session, **{**fields, "revision_id": 2, "raw_hash": "h2"})

    assert first == second

    def chunk(ordinal: int) -> dict:
        return {"id": uuid.uuid4(), "ordinal": ordinal, "text": f"t{ordinal}", "token_count": 3, "game_scope": "base"}

    assert await repo.replace_chunks(session, first, [chunk(0), chunk(1)]) == 2
    assert await repo.replace_chunks(session, first, [chunk(0)]) == 1  # chunk cũ bị thay, không dồn lại


async def test_chunk_rejects_unknown_source_type(session: AsyncSession):
    doc = await repo.upsert_document(
        session, source="wikigg", source_id="9", url="u", title="t", raw_hash="h", fetched_at=datetime.now(UTC)
    )
    bad = {"id": uuid.uuid4(), "ordinal": 0, "text": "x", "token_count": 1, "source_type": "made_up"}

    with pytest.raises(IntegrityError):
        await repo.replace_chunks(session, doc, [bad])


@pytest.mark.parametrize(("ok", "failed", "expected"), [(10, 0, "succeeded"), (8, 2, "partial"), (0, 3, "failed")])
async def test_job_status_from_counts(session: AsyncSession, ok: int, failed: int, expected: str):
    job = await repo.start_job(session, kind="crawl", source="wikigg", external_id=f"crawl-{uuid.uuid4().hex[:6]}")

    await repo.finish_job(session, job, pages_ok=ok, pages_failed=failed, log={"errors": []})

    assert job.status == expected
    assert job.finished_at is not None
