"""TV2 loader transactions against an isolated PostgreSQL database."""

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from core.db.models import Chunk, IngestionJob
from core.db.session import create_sessionmaker
from core.ids import chunk_id, document_id
from ingest.artifacts import save, sha256
from ingest.chunk import postgres
from tests.integration.test_db_schema import db_url as db_url

pytestmark = pytest.mark.integration


def bundle(directory, text="Original lore", source_type="wiki_prose"):
    identity = document_id("wikigg", "1")
    raw_path = directory / "raw.json"
    save(
        raw_path,
        {
            "source": "wikigg",
            "source_id": "1",
            "revision_id": 1,
            "content": text,
            "content_hash": sha256(text.encode()),
            "url": "https://example.org/wiki/1",
        },
    )
    row = {
        "doc_id": str(identity),
        "chunk_id": str(chunk_id(identity, 0)),
        "ordinal": 0,
        "source": "wikigg",
        "source_id": "1",
        "revision_id": 1,
        "source_snapshot": str(raw_path),
        "title": "Fixture",
        "section": "Lore",
        "text": text,
        "text_hash": sha256(text.encode()),
        "embedding_text": "passage: Fixture\n" + text,
        "token_count": 12,
        "source_type": source_type,
        "game_scope": "base",
        "lang": "en",
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    payload = (json.dumps(row) + "\n").encode()
    (directory / "chunks.jsonl").write_bytes(payload)
    save(directory / "report.json", {"artifact_sha256": {"chunks.jsonl": sha256(payload)}})


async def test_loader_rerun_quarantine_and_rollback(db_url, tmp_path, monkeypatch):
    monkeypatch.setattr(postgres, "create_engine", lambda _: create_async_engine(db_url))
    bundle(tmp_path)
    first = await postgres.load(tmp_path)
    assert first["pages_ok"] == 1 and first["pages_failed"] == 0
    engine = create_async_engine(db_url)
    sessions = create_sessionmaker(engine)

    async def state():
        async with sessions() as session:
            rows = (await session.execute(select(Chunk))).scalars().all()
            return [(r.id, r.text, r.updated_at) for r in rows]

    try:
        original = await state()
        await postgres.load(tmp_path)
        assert await state() == original
        bundle(tmp_path, source_type="unknown")
        review = await postgres.load(tmp_path)
        assert review["pages_failed"] == 1
        assert await state() == original
        bundle(tmp_path, text="Changed lore")
        replace = postgres.replace_chunks

        async def failing_replace(*args, **kwargs):
            await replace(*args, **kwargs)
            raise RuntimeError("Injected failure after replacement")

        monkeypatch.setattr(postgres, "replace_chunks", failing_replace)
        failed = await postgres.load(tmp_path)
        assert failed["pages_failed"] == 1
        assert await state() == original
        async with sessions() as session:
            jobs = (await session.execute(select(IngestionJob))).scalars().all()
            assert len(jobs) == 4
            assert all(job.status != "running" for job in jobs)
    finally:
        await engine.dispose()
