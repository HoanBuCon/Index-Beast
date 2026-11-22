"""Admin: id hội thoại dán vào ô tra cứu trace vẫn ra trace của câu trả lời cuối; /admin/stats kèm last_message_id.

SQLite biên dịch SQL repository production (xem test_agent_durable), KHÔNG phải test tích hợp Postgres.

Phụ trách: TV1 · [S5] Trang admin (API)
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.api.schemas.conversation import ConversationOut, MessageOut
from app.services.memory_repository import Snapshot, owner_hash
from core.db import repositories as repo_queries
from core.errors import NotFoundError
from tests.unit.test_agent_durable import repo  # noqa: F401  (fixture dùng chung)
from tests.unit.test_live_chat import FakeLLM, FakeRetriever  # noqa: F401
from tests.unit.test_trace import admin_client, stats_client  # noqa: F401

BASE = datetime(2026, 11, 8, 3, 0, tzinfo=UTC)


async def save_turn(repository, conv, revision, offset, question, answer, trace):
    """Lưu một lượt hỏi-đáp; trả (id tin user, id tin assistant)."""
    at = BASE + timedelta(minutes=offset)
    pair = [
        MessageOut(id=uuid4(), role="user", content=question, created_at=at),
        MessageOut(id=uuid4(), role="assistant", content=answer, created_at=at + timedelta(seconds=1)),
    ]
    snapshot = Snapshot(conv, None, owner_hash("secret"), revision, {})
    await repository.save(snapshot, pair, {}, {"intent": "smalltalk"}, {"trace": trace, "latency_ms": 5.0})
    return pair[0].id, pair[1].id


async def two_turn_conversation(repository):
    conv = ConversationOut(id=uuid4(), channel="web", created_at=BASE, messages=[])
    await save_turn(repository, conv, 0, 0, "Ranni là ai?", "câu 1", {"turn": 1})
    _, last = await save_turn(repository, conv, 1, 5, "Còn Radahn?", "câu 2", {"turn": 2})
    return conv, last


async def test_trace_accepts_a_conversation_id_and_returns_its_latest_assistant_message(repo):  # noqa: F811
    conv, last = await two_turn_conversation(repo)
    found = await repo.trace(conv.id)
    assert found["message_id"] == last and found["trace"] == {"turn": 2}
    assert (await repo.trace(last))["message_id"] == last  # id tin nhắn vẫn chạy như cũ


async def test_trace_of_unknown_id_or_conversation_without_answer_is_none(repo):  # noqa: F811
    assert await repo.trace(uuid4()) is None
    conv = ConversationOut(id=uuid4(), channel="web", created_at=BASE, messages=[])
    only_user = [MessageOut(id=uuid4(), role="user", content="xin chào", created_at=BASE)]
    await repo.save(Snapshot(conv, None, owner_hash("secret"), 0, {}), only_user, {}, {"intent": "smalltalk"})
    assert await repo.trace(conv.id) is None


async def test_recent_conversations_carry_the_latest_assistant_message_id(repo):  # noqa: F811
    conv, last = await two_turn_conversation(repo)
    empty = ConversationOut(id=uuid4(), channel="web", created_at=BASE + timedelta(hours=1), messages=[])
    await repo.save(
        Snapshot(empty, None, owner_hash("secret"), 0, {}),
        [MessageOut(id=uuid4(), role="user", content="chỉ có câu hỏi", created_at=BASE)],
        {},
        {"intent": "smalltalk"},
    )
    async with repo.sessions() as session:
        rows = await repo_queries.recent_conversations(session)
    by_id = {row[0]: row for row in rows}
    assert by_id[conv.id][1] == "Ranni là ai?" and by_id[conv.id][3] == last
    assert by_id[empty.id][3] is None


async def test_live_service_falls_back_from_conversation_id_for_in_memory_traces(settings):
    from app.rag.pipeline import ChatPipeline
    from app.services.chat import LiveChatService

    service = LiveChatService(ChatPipeline(settings, FakeLLM(), FakeRetriever()))
    conversation_id, message_id = uuid4(), uuid4()
    conversation = ConversationOut(
        id=conversation_id,
        channel="web",
        created_at=BASE,
        messages=[
            MessageOut(id=uuid4(), role="user", content="hỏi", created_at=BASE),
            MessageOut(id=message_id, role="assistant", content="đáp", created_at=BASE),
        ],
    )
    from app.services.chat import ConversationState

    service._conversations[conversation_id] = ConversationState(conversation, None)
    service.traces[message_id] = {"selected_ids": ["a"]}
    assert (await service.trace(conversation_id))["message_id"] == message_id
    assert (await service.trace(message_id))["message_id"] == message_id
    with pytest.raises(NotFoundError):
        await service.trace(uuid4())


def test_admin_stats_exposes_last_message_id_nullable(admin_client, monkeypatch):  # noqa: F811
    with_answer, without = uuid4(), uuid4()
    msg = uuid4()
    client, auth = stats_client(
        admin_client,
        monkeypatch,
        recent_conversations=[(with_answer, "Hỏi", BASE, msg), (without, "Chưa đáp", BASE, None)],
    )
    first, second = client.get("/api/v1/admin/stats", headers=auth.headers).json()["conversations"]
    assert first["id"] == str(with_answer) and first["last_message_id"] == str(msg)
    assert "last_message_id" not in second  # client web từ chối null ở trường tùy chọn
