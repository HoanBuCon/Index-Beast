"""Xóa tài khoản và chính sách lưu giữ 90 ngày trên PostgreSQL thật (FR-AUTH-08, NFR-PRIV-01). DB tạm do fixture.

Chạy: make up && pytest -m integration

Phụ trách: TV1 · [S5] Quyền riêng tư và xóa tài khoản
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services import auth, privacy
from core.config import Settings
from core.db import repositories as repo
from core.db.models import AuthSession, Conversation, ConversationMemory, Feedback, Message, User
from tests.integration.test_db_schema import db_url  # noqa: F401  (fixture dùng chung)

pytestmark = pytest.mark.integration

SETTINGS = Settings(
    _env_file=None, environment="test", discord_client_id="1", discord_client_secret="s", auth_secret="k" * 32
)
COLLECTION = "conversation_memories"


class RecordingQdrant:
    def __init__(self):
        self.deleted: list[list[str]] = []

    async def collection_exists(self, name):
        return True

    async def delete(self, collection, points_selector, wait):
        self.deleted.append(points_selector.filter.must[0].match.any)


@pytest.fixture
async def sessionmaker(db_url: str):  # noqa: F811
    engine = create_async_engine(db_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def make_conversation(sessionmaker, *, user_id=None, age_days=0, empty=False, with_memory=True):
    """Hội thoại có tin nhắn (cũ `age_days` ngày), feedback và một ký ức. Trả (conversation_id, answer_id)."""
    at = datetime.now(UTC) - timedelta(days=age_days)
    async with sessionmaker() as session, session.begin():
        conv = await repo.create_conversation(session, channel="web")
        conv.user_id, conv.created_at = user_id, at
        if empty:
            return conv.id, None
        question = await repo.add_message(session, conv.id, role="user", content="Marika là ai?", created_at=at)
        answer = await repo.add_message(session, conv.id, role="assistant", content="OK", created_at=at)
        await repo.add_feedback(session, answer.id, 1, None)
        if with_memory:
            session.add(
                ConversationMemory(
                    id=uuid4(),
                    conversation_id=conv.id,
                    source_message_id=question.id,
                    kind="fact",
                    content="x",
                    embedding_text="x",
                    created_at=at,
                )
            )
        return conv.id, answer.id


async def count(sessionmaker, model, *where):
    async with sessionmaker() as session:
        return (await session.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


async def test_delete_account_removes_the_user_and_only_their_data(sessionmaker):
    leaving = await auth.upsert_user(sessionmaker, SETTINGS, "9001", "Leaving")
    staying = await auth.upsert_user(sessionmaker, SETTINGS, "9002", "Staying")
    await auth.create_session(sessionmaker, leaving.id, 7)
    await auth.create_session(sessionmaker, leaving.id, 7)
    keep_session = await auth.create_session(sessionmaker, staying.id, 7)
    mine = [(await make_conversation(sessionmaker, user_id=leaving.id))[0] for _ in range(2)]
    theirs, _ = await make_conversation(sessionmaker, user_id=staying.id)
    guest, _ = await make_conversation(sessionmaker, user_id=None)
    qdrant = RecordingQdrant()

    counts = await privacy.delete_account(sessionmaker, qdrant, COLLECTION, leaving.id)

    assert (counts.conversations, counts.messages, counts.feedback, counts.sessions, counts.users) == (2, 4, 2, 2, 1)
    assert sorted(i for batch in qdrant.deleted for i in batch) == sorted(str(i) for i in mine)
    assert await count(sessionmaker, User, User.id == leaving.id) == 0
    assert await count(sessionmaker, AuthSession, AuthSession.user_id == leaving.id) == 0
    assert await count(sessionmaker, Conversation, Conversation.id.in_(mine)) == 0
    assert await count(sessionmaker, Message, Message.conversation_id.in_(mine)) == 0
    assert await count(sessionmaker, ConversationMemory, ConversationMemory.conversation_id.in_(mine)) == 0
    # người khác và khách còn nguyên
    assert await count(sessionmaker, Conversation, Conversation.id.in_([theirs, guest])) == 2
    assert await count(sessionmaker, ConversationMemory, ConversationMemory.conversation_id == theirs) == 1
    assert (await auth.user_for_token(sessionmaker, SETTINGS, keep_session)).id == staying.id


async def test_delete_account_is_idempotent(sessionmaker):
    user = await auth.upsert_user(sessionmaker, SETTINGS, "9100", "Twice")
    await make_conversation(sessionmaker, user_id=user.id)
    await privacy.delete_account(sessionmaker, None, COLLECTION, user.id)
    again = await privacy.delete_account(sessionmaker, None, COLLECTION, user.id)
    assert again == privacy.Counts()


async def test_a_failed_vector_purge_deletes_nothing_and_a_retry_completes(sessionmaker):
    user = await auth.upsert_user(sessionmaker, SETTINGS, "9200", "Retry")
    conv, _ = await make_conversation(sessionmaker, user_id=user.id)

    class Down(RecordingQdrant):
        async def delete(self, *args, **kwargs):
            raise ConnectionError("down")

    with pytest.raises(privacy.UnavailableError):
        await privacy.delete_account(sessionmaker, Down(), COLLECTION, user.id)
    assert await count(sessionmaker, User, User.id == user.id) == 1
    assert await count(sessionmaker, Conversation, Conversation.id == conv) == 1
    await privacy.delete_account(sessionmaker, RecordingQdrant(), COLLECTION, user.id)
    assert await count(sessionmaker, User, User.id == user.id) == 0


async def test_retention_deletes_only_conversations_idle_longer_than_the_window(sessionmaker, monkeypatch):
    monkeypatch.setattr(privacy, "BATCH_SIZE", 2)  # ép nhiều lượt xóa
    now = datetime.now(UTC)
    old = [(await make_conversation(sessionmaker, age_days=120))[0] for _ in range(3)]
    old_empty, _ = await make_conversation(sessionmaker, age_days=100, empty=True)
    fresh, _ = await make_conversation(sessionmaker, age_days=10)
    edge, _ = await make_conversation(sessionmaker, age_days=89)
    # tạo từ lâu nhưng mới có tin nhắn: hoạt động cuối là tin nhắn nên được giữ
    revived, _ = await make_conversation(sessionmaker, age_days=200, with_memory=False)
    async with sessionmaker() as session, session.begin():
        await session.execute(update(Message).where(Message.conversation_id == revived).values(created_at=now))

    qdrant = RecordingQdrant()
    cutoff = now - timedelta(days=90)
    dry = await privacy.apply_retention(sessionmaker, qdrant, COLLECTION, cutoff=cutoff, now=now, dry_run=True)
    assert (dry.conversations, dry.messages, dry.feedback) == (4, 6, 3) and qdrant.deleted == []
    assert await count(sessionmaker, Conversation, Conversation.id.in_([*old, old_empty])) == 4  # dry-run không xóa

    done = await privacy.apply_retention(sessionmaker, qdrant, COLLECTION, cutoff=cutoff, now=now)
    assert (done.conversations, done.messages, done.feedback) == (4, 6, 3)
    assert sorted(i for batch in qdrant.deleted for i in batch) == sorted(str(i) for i in [*old, old_empty])
    assert await count(sessionmaker, Conversation, Conversation.id.in_([*old, old_empty])) == 0
    assert await count(sessionmaker, Conversation, Conversation.id.in_([fresh, edge, revived])) == 3
    assert (
        await count(
            sessionmaker, Feedback, Feedback.message_id.in_(select(Message.id).where(Message.conversation_id == fresh))
        )
        == 1
    )
    again = await privacy.apply_retention(sessionmaker, qdrant, COLLECTION, cutoff=cutoff, now=now)
    assert again == privacy.Counts()


async def test_retention_removes_expired_sessions_in_batches_and_keeps_live_ones(sessionmaker, monkeypatch):
    monkeypatch.setattr(privacy, "BATCH_SIZE", 2)
    now = datetime.now(UTC)
    user = await auth.upsert_user(sessionmaker, SETTINGS, "9300", "Sessions")
    expired = [await auth.create_session(sessionmaker, user.id, 7) for _ in range(5)]
    async with sessionmaker() as session, session.begin():
        await session.execute(update(AuthSession).values(expires_at=now - timedelta(seconds=1)))
    live = await auth.create_session(
        sessionmaker, user.id, 7
    )  # create_session tự dọn phiên hết hạn: tạo xong mới đặt hạn
    async with sessionmaker() as session, session.begin():  # đưa lại 5 phiên hết hạn (create_session đã dọn chúng)
        for index in range(5):
            session.add(AuthSession(user_id=user.id, token_hash=f"expired-{index}", expires_at=now - timedelta(days=1)))

    result = await privacy.apply_retention(
        sessionmaker, None, COLLECTION, cutoff=now - timedelta(days=90), now=now, dry_run=True
    )
    assert result.sessions == 5
    done = await privacy.apply_retention(sessionmaker, None, COLLECTION, cutoff=now - timedelta(days=90), now=now)
    assert done.sessions == 5 and expired
    assert (await auth.user_for_token(sessionmaker, SETTINGS, live)).id == user.id
    assert await count(sessionmaker, AuthSession, AuthSession.user_id == user.id) == 1
