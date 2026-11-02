"""Full base+SotE loading on a disposable PostgreSQL database, never dev data."""

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from core.db.models import Chunk
from core.db.session import create_sessionmaker
from core.ids import chunk_id, document_id
from ingest.artifacts import save, sha256
from ingest.chunk import load_full
from tests.integration.test_db_schema import db_url as db_url

pytestmark = pytest.mark.integration


def make_bundle(root, text="SotE lore"):
    identity = document_id("wikigg", "1")
    (root / "wikigg").mkdir(exist_ok=True)
    raw = {
        "source": "wikigg",
        "source_id": "1",
        "revision_id": 1,
        "content": text,
        "content_hash": sha256(text.encode()),
    }
    save(root / "raw.json", raw)
    doc = {
        "doc_id": str(identity),
        "source": "wikigg",
        "source_id": "1",
        "revision_id": 1,
        "title": "SotE fixture",
        "url": "https://example.org/1",
        "source_snapshot": str(root / "raw.json"),
        "raw_content_hash": raw["content_hash"],
        "game_scope": "elden_ring",
        "release_scope": "sote_candidate",
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    row = {k: doc[k] for k in ["doc_id", "source", "source_id", "revision_id", "source_snapshot", "game_scope"]}
    row.update(
        ordinal=0,
        chunk_id=str(chunk_id(identity, 0)),
        section="Lore",
        text=text,
        text_hash=sha256(text.encode()),
        embedding_text="passage: SotE fixture\nLore\n" + text,
        token_count=12,
        source_type="wiki_prose",
        lang="unknown",
    )
    payload = (json.dumps(row) + "\n").encode()
    (root / "chunks.jsonl").write_bytes(payload)
    (root / "wikigg/1.jsonl").write_bytes(payload)
    (root / "documents.jsonl").write_text(json.dumps(doc) + "\n", encoding="utf-8")
    save(
        root / "report.json",
        {
            "chunking_version": "s2-full-chunk-1.0",
            "max_tokens": 450,
            "counts": {"pages": 1, "chunks": 1},
            "artifact_sha256": {n: sha256((root / n).read_bytes()) for n in ["chunks.jsonl", "documents.jsonl"]},
        },
    )


async def test_full_load_rerun_unknown_language_and_rollback(db_url, tmp_path, monkeypatch):
    monkeypatch.setattr(load_full, "create_engine", lambda _: create_async_engine(db_url))
    make_bundle(tmp_path)
    assert (await load_full.load(tmp_path))["documents_ok"] == 1
    assert (await load_full.load(tmp_path))["unchanged_documents"] == 1
    engine = create_async_engine(db_url)
    sessions = create_sessionmaker(engine)

    async def snapshot():
        async with sessions() as session:
            rows = (await session.execute(select(Chunk))).scalars().all()
            return [(c.id, c.text, c.game_scope, c.lang, c.updated_at) for c in rows]

    try:
        original = await snapshot()
        assert original[0][2:4] == ("elden_ring", "unknown")
        make_bundle(tmp_path, "Changed lore")
        replace = load_full.replace_chunks

        async def broken(*args, **kwargs):
            await replace(*args, **kwargs)
            raise RuntimeError("Injected failure")

        monkeypatch.setattr(load_full, "replace_chunks", broken)
        result = await load_full.load(tmp_path)
        assert result["documents_failed"] == 1
        assert await snapshot() == original
    finally:
        await engine.dispose()
