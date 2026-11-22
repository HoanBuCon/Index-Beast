"""Trace RAG lưu và đọc lại trên PostgreSQL thật (JSONB, cột số đo). DB tạm do fixture của test_db_schema tạo.

Chạy: make up && pytest -m integration

Phụ trách: TV1 · [S3] Trace từng bước RAG
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.schemas.conversation import ConversationOut, MessageOut
from app.services.memory_repository import MemoryRepository, Snapshot, owner_hash
from tests.integration.test_db_schema import db_url  # noqa: F401  (fixture dùng chung)

pytestmark = pytest.mark.integration


async def test_assistant_message_keeps_trace_and_measures(db_url: str):  # noqa: F811
    engine = create_async_engine(db_url)
    try:
        repo = MemoryRepository(async_sessionmaker(engine, expire_on_commit=False))
        conv = ConversationOut(id=uuid4(), channel="web", created_at=datetime.now(UTC), messages=[])
        now = datetime.now(UTC)
        pair = [
            MessageOut(id=uuid4(), role="user", content="Ranni là ai?", created_at=now),
            MessageOut(id=uuid4(), role="assistant", content="OK", created_at=now),
        ]
        record = {
            "trace": {"retrieved": [{"id": "p1", "score": 0.9}], "web_search": {"status": "not_run"}},
            "rewritten_query": "Who is Ranni?",
            "latency_ms": 1234.5,
            "tokens_in": 900,
            "tokens_out": 120,
        }
        decision = {"intent": "smalltalk"}  # không tạo bộ nhớ ngữ nghĩa: chỉ kiểm tra bản ghi tin nhắn
        await repo.save(Snapshot(conv, None, owner_hash("secret"), 0, {}), pair, {}, decision, record)
        stored = await repo.trace(pair[1].id)
        assert stored["rewritten_query"] == "Who is Ranni?" and stored["latency_ms"] == 1234.5
        assert (stored["tokens_in"], stored["tokens_out"]) == (900, 120)
        assert stored["trace"]["retrieved"][0]["score"] == 0.9
        assert await repo.trace(pair[0].id) is None
    finally:
        await engine.dispose()
