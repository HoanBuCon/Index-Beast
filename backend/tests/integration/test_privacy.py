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
from core.db.models import AuthSession, Conversation, ConversationMemory, Feedback, IngestionJob, Message, User
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

    assert (counts.conversations, counts.users) == (2, 1)
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
    token = await auth.create_session(sessionmaker, user.id, 7)
    conv, _ = await make_conversation(sessionmaker, user_id=user.id)

    class Down(RecordingQdrant):
        async def delete(self, *args, **kwargs):
            raise ConnectionError("down")

    with pytest.raises(privacy.UnavailableError):
        await privacy.delete_account(sessionmaker, Down(), COLLECTION, user.id)
    assert await count(sessionmaker, User, User.id == user.id) == 1
    assert await count(sessionmaker, Conversation, Conversation.id == conv) == 1
    assert (
        await auth.user_for_token(sessionmaker, SETTINGS, token)
    ).id == user.id  # phiên còn: DELETE /me thử lại được
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
        await session.execute(
            update(Message).where(Message.conversation_id.in_(old)).values(rag_trace={"stage": "retrieve"})
        )

    qdrant = RecordingQdrant()
    cutoff = now - timedelta(days=90)
    dry = await privacy.apply_retention(sessionmaker, qdrant, COLLECTION, cutoff=cutoff, now=now, dry_run=True)
    assert (dry.conversations, dry.messages, dry.feedback) == (4, 6, 3) and qdrant.deleted == []
    assert dry.traces == 0  # Trace của khách này đi cùng hội thoại khi xóa.
    assert await count(sessionmaker, Conversation, Conversation.id.in_([*old, old_empty])) == 4  # dry-run không xóa

    done = await privacy.apply_retention(sessionmaker, qdrant, COLLECTION, cutoff=cutoff, now=now)
    assert (done.conversations, done.messages, done.feedback) == (4, 6, 3)
    assert done.traces == dry.traces
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


async def test_delete_account_removes_a_conversation_created_after_the_batch_loop(sessionmaker):
    """Đua: hội thoại xuất hiện sau khi vòng lặp thấy "hết" vẫn bị xóa cùng người dùng (không thành hội thoại khách
    mồ côi), điểm Qdrant của nó cũng bị xóa, và phiên mất cùng transaction cuối."""
    user = await auth.upsert_user(sessionmaker, SETTINGS, "9400", "Racer")
    token = await auth.create_session(sessionmaker, user.id, 7)
    late: list = []
    real, opens = sessionmaker, []

    # Lần mở thứ 3 là giao dịch cuối (sau lần quét rỗng và lần chọn "còn sót"): chèn một hội thoại mới ngay trước nó.
    class Gate:
        def __call__(self):
            opens.append(1)
            if len(opens) == 3:
                return _InjectThenOpen()
            return real()

    class _InjectThenOpen:
        async def __aenter__(self):
            late.append((await make_conversation(real, user_id=user.id))[0])
            self.inner = real()
            return await self.inner.__aenter__()

        async def __aexit__(self, *exc):
            return await self.inner.__aexit__(*exc)

    qdrant = RecordingQdrant()
    await privacy.delete_account(Gate(), qdrant, COLLECTION, user.id)

    assert len(late) == 1
    assert await auth.user_for_token(real, SETTINGS, token) is None
    assert await count(real, Conversation, Conversation.id.in_(late)) == 0
    assert await count(real, User, User.id == user.id) == 0
    assert [i for batch in qdrant.deleted for i in batch] == [str(late[0])]


async def test_delete_account_also_removes_a_claimed_guest_conversation_but_not_an_unclaimed_one(sessionmaker):
    user = await auth.upsert_user(sessionmaker, SETTINGS, "9500", "Claimer")
    claimed, _ = await make_conversation(sessionmaker, user_id=None)
    async with sessionmaker() as session, session.begin():
        await session.execute(update(Conversation).where(Conversation.id == claimed).values(user_id=user.id))
    unclaimed, _ = await make_conversation(sessionmaker, user_id=None)
    await privacy.delete_account(sessionmaker, None, COLLECTION, user.id)
    assert await count(sessionmaker, Conversation, Conversation.id == claimed) == 0
    assert await count(sessionmaker, Conversation, Conversation.id == unclaimed) == 1  # chỉ retention hoặc /clear xóa


async def test_retention_preserves_account_and_discord_history_but_prunes_old_rag_trace(sessionmaker):
    now = datetime.now(UTC)
    user = await auth.upsert_user(sessionmaker, SETTINGS, "9600", "Owner")
    guest, _ = await make_conversation(sessionmaker, age_days=120)
    owned, _ = await make_conversation(sessionmaker, user_id=user.id, age_days=120)
    discord, _ = await make_conversation(sessionmaker, age_days=120)
    conversations = [guest, owned, discord]
    retained_messages = Message.conversation_id.in_([owned, discord])
    async with sessionmaker() as session, session.begin():
        await session.execute(update(Conversation).where(Conversation.id == discord).values(channel="discord"))
        await session.execute(
            update(Message).where(Message.conversation_id.in_(conversations)).values(rag_trace={"debug": True})
        )
    dry = await privacy.apply_retention(
        sessionmaker, None, COLLECTION, cutoff=now - timedelta(days=90), now=now, dry_run=True
    )
    assert dry.conversations == 1 and dry.traces == 4
    done = await privacy.apply_retention(sessionmaker, None, COLLECTION, cutoff=now - timedelta(days=90), now=now)
    assert done.conversations == 1 and done.traces == dry.traces
    assert await count(sessionmaker, Conversation, Conversation.id == guest) == 0
    assert await count(sessionmaker, Conversation, Conversation.id.in_([owned, discord])) == 2
    assert await count(sessionmaker, Message, retained_messages) == 4
    assert (
        await count(sessionmaker, Feedback, Feedback.message_id.in_(select(Message.id).where(retained_messages))) == 2
    )
    assert await count(sessionmaker, Message, retained_messages, Message.rag_trace.is_not(None)) == 0


async def test_retention_clears_completed_job_logs_in_batches_without_recounting_json_null(sessionmaker, monkeypatch):
    from sqlalchemy import JSON, null

    monkeypatch.setattr(privacy, "BATCH_SIZE", 2)
    now = datetime.now(UTC)
    old = now - timedelta(days=100)
    async with sessionmaker() as session, session.begin():
        jobs = [
            IngestionJob(kind="update", status="succeeded", finished_at=old, pages_ok=3, log={"x": 1}) for _ in range(3)
        ]
        empty = IngestionJob(kind="update", status="succeeded", finished_at=old, log=JSON.NULL)
        fresh = IngestionJob(kind="update", status="succeeded", finished_at=now, log={"x": 1})
        running = IngestionJob(kind="update", status="running", log={"x": 1})
        session.add_all([*jobs, empty, fresh, running])
        await session.flush()
        ids, fresh_id, running_id = [j.id for j in jobs], fresh.id, running.id
    dry = await privacy.apply_retention(
        sessionmaker, None, COLLECTION, cutoff=now - timedelta(days=90), now=now, dry_run=True
    )
    assert dry.ingestion_logs == 3
    done = await privacy.apply_retention(sessionmaker, None, COLLECTION, cutoff=now - timedelta(days=90), now=now)
    assert done.ingestion_logs == 3
    async with sessionmaker() as session:
        rows = (await session.execute(select(IngestionJob).where(IngestionJob.id.in_(ids)))).scalars().all()
        assert all(row.log is None and row.pages_ok == 3 and row.status == "succeeded" for row in rows)
        assert (await session.get(IngestionJob, fresh_id)).log == {"x": 1}
        assert (await session.get(IngestionJob, running_id)).log == {"x": 1}
        assert (
            await session.execute(
                select(func.count())
                .select_from(IngestionJob)
                .where(IngestionJob.id.in_(ids), IngestionJob.log.is_(null()))
            )
        ).scalar_one() == 3
    again = await privacy.apply_retention(sessionmaker, None, COLLECTION, cutoff=now - timedelta(days=90), now=now)
    assert again.ingestion_logs == 0
