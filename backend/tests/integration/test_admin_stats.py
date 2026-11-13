"""Truy vấn thống kê admin trên PostgreSQL thật: tiêu đề lấy từ câu hỏi đầu, thứ tự mới nhất trước, giới hạn.

Chạy: make up && pytest -m integration

Phụ trách: TV1 · [S3] Trace từng bước RAG · [S5] Trang admin (API)
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.db import repositories as repo
from core.db.models import EvalRun
from tests.integration.test_db_schema import db_url  # noqa: F401  (fixture dùng chung)

pytestmark = pytest.mark.integration


async def test_admin_queries_order_titles_and_limits(db_url: str):  # noqa: F811
    engine = create_async_engine(db_url)
    try:
        now = datetime.now(UTC)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session, session.begin():
            old = await repo.create_conversation(session, channel="web")
            new = await repo.create_conversation(session, channel="discord")
            empty = await repo.create_conversation(session, channel="web")
            old.created_at, new.created_at, empty.created_at = now - timedelta(hours=2), now - timedelta(hours=1), now
            await repo.add_message(session, old.id, role="user", content="Marika là ai?", created_at=now)
            await repo.add_message(session, old.id, role="assistant", content="Trả lời", created_at=now)
            await repo.add_message(session, old.id, role="user", content="Câu hỏi thứ hai", created_at=now)
            await repo.add_message(session, new.id, role="user", content="Ranni ở đâu?", created_at=now)
            answer = await repo.add_message(session, new.id, role="assistant", content="Ở Nokron", created_at=now)
            await repo.add_feedback(session, answer.id, -1, "sai")
            await repo.add_feedback(session, answer.id, 1, None)
            await repo.start_job(session, kind="crawl", external_id="crawl-test")
            session.add_all([EvalRun(metrics={"recall@5": 0.8}), EvalRun(metrics={})])

        async with async_sessionmaker(engine)() as session:
            rows = await repo.recent_conversations(session, limit=2)
            assert [(title, at.tzinfo is not None) for _, title, at in rows] == [(None, True), ("Ranni ở đâu?", True)]
            assert (await repo.recent_conversations(session))[2][1] == "Marika là ai?"  # câu hỏi ĐẦU, không phải cuối
            feedback = await repo.recent_feedback(session)
            assert sorted((f.rating, f.reason) for f in feedback) == [(-1, "sai"), (1, None)]
            assert [j.external_id for j in await repo.list_jobs(session, limit=10)] == ["crawl-test"]
            assert {tuple(r.metrics) for r in await repo.recent_eval_runs(session)} == {("recall@5",), ()}
            assert len(await repo.recent_feedback(session, limit=1)) == 1
    finally:
        await engine.dispose()


async def test_feedback_is_replaced_not_duplicated_and_eval_runs_round_trip(db_url: str):  # noqa: F811
    from app.services.memory_repository import MemoryRepository
    from scripts import eval_runs

    engine = create_async_engine(db_url)
    try:
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        async with sessionmaker() as session, session.begin():
            conversation = await repo.create_conversation(session, channel="web")
            answer = await repo.add_message(session, conversation.id, role="assistant", content="OK")
        memory = MemoryRepository(sessionmaker)
        await memory.save_feedback(answer.id, 1, None)
        await memory.save_feedback(answer.id, -1, "thiếu nguồn")
        async with sessionmaker() as session:
            rows = await repo.recent_feedback(session)
            assert [(f.rating, f.reason) for f in rows if f.message_id == answer.id] == [(-1, "thiếu nguồn")]

        await eval_runs.record(sessionmaker, git_sha="abc", config={"name": "baseline"}, metrics={"recall@5": 0.8})
        listed = await eval_runs.recent(sessionmaker, 5)
        mine = [
            (r.git_sha, r.metrics) for r in listed if r.config.get("name") == "baseline"
        ]  # DB dùng chung trong module
        assert mine == [("abc", {"recall@5": 0.8})]
    finally:
        await engine.dispose()
