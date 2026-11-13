"""Người dùng, phiên và quyền sở hữu hội thoại trên PostgreSQL thật (migration 0004). DB tạm do fixture dùng chung tạo.

Chạy: make up && pytest -m integration

Phụ trách: TV1 · [S4] Auth service
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.schemas.conversation import ConversationOut, MessageOut
from app.services import auth
from app.services.memory_repository import MemoryRepository, Snapshot, owner_hash
from core.config import Settings
from core.db.models import AuthSession, Conversation, User
from core.errors import NotFoundError, UnauthorizedError
from tests.integration.test_db_schema import db_url  # noqa: F401  (fixture dùng chung)

pytestmark = pytest.mark.integration

SETTINGS = Settings(
    _env_file=None,
    environment="test",
    discord_client_id="1",
    discord_client_secret="secret",
    auth_secret="k" * 32,
    auth_admin_discord_ids="777",
)


@pytest.fixture
async def sessionmaker(db_url: str):  # noqa: F811
    engine = create_async_engine(db_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def save_conversation(sessionmaker, *, token: str, user_id=None, question="Marika là ai?"):
    now = datetime.now(UTC)
    conv = ConversationOut(id=uuid4(), channel="web", created_at=now, messages=[])
    pair = [
        MessageOut(id=uuid4(), role="user", content=question, created_at=now),
        MessageOut(id=uuid4(), role="assistant", content="OK", created_at=now),
    ]
    snapshot = Snapshot(conv, None, owner_hash(token), 0, {}, user_id=user_id)
    await MemoryRepository(sessionmaker).save(snapshot, pair, {}, {"intent": "smalltalk"})
    return conv.id


async def test_user_is_upserted_by_hash_and_the_raw_discord_id_is_never_stored(sessionmaker):
    first = await auth.upsert_user(sessionmaker, SETTINGS, "424242", "Tarnished")
    again = await auth.upsert_user(sessionmaker, SETTINGS, "424242", "Renamed")
    other = await auth.upsert_user(sessionmaker, SETTINGS, "515151", None)
    assert first.id == again.id != other.id and not first.is_admin
    async with sessionmaker() as session:
        row = (await session.execute(select(User).where(User.id == first.id))).scalar_one()
        assert row.display_name == "Renamed" and row.last_login_at is not None
        assert "424242" not in row.provider_user_hash and len(row.provider_user_hash) == 64
        assert "424242" not in " ".join(str(v) for v in (await session.execute(text("select * from users"))).scalars())


async def test_admin_comes_from_the_configured_ids_at_request_time(sessionmaker):
    admin = await auth.upsert_user(sessionmaker, SETTINGS, "777", "Melina")
    token = await auth.create_session(sessionmaker, admin.id, 7)
    assert (await auth.user_for_token(sessionmaker, SETTINGS, token)).is_admin
    revoked = Settings(**{**SETTINGS.model_dump(), "auth_admin_discord_ids": []})
    assert not (await auth.user_for_token(sessionmaker, revoked, token)).is_admin  # thu hồi có hiệu lực ngay


async def test_sessions_are_hashed_expire_and_can_be_ended(sessionmaker):
    user = await auth.upsert_user(sessionmaker, SETTINGS, "100", "A")
    token = await auth.create_session(sessionmaker, user.id, 7)
    async with sessionmaker() as session:
        stored = (await session.execute(select(AuthSession).where(AuthSession.user_id == user.id))).scalars().all()
        assert [s.token_hash for s in stored] == [auth.hash_token(token)] and token not in stored[0].token_hash
    assert (await auth.user_for_token(sessionmaker, SETTINGS, token)).id == user.id
    assert await auth.user_for_token(sessionmaker, SETTINGS, "forged") is None
    assert await auth.user_for_token(sessionmaker, SETTINGS, None) is None

    async with sessionmaker() as session, session.begin():
        await session.execute(update(AuthSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert await auth.user_for_token(sessionmaker, SETTINGS, token) is None  # hết hạn

    fresh = await auth.create_session(sessionmaker, user.id, 7)  # phiên mới dọn phiên hết hạn của người này
    async with sessionmaker() as session:
        count = len((await session.execute(select(AuthSession).where(AuthSession.user_id == user.id))).scalars().all())
    assert count == 1
    await auth.end_session(sessionmaker, fresh)
    assert await auth.user_for_token(sessionmaker, SETTINGS, fresh) is None


async def test_conversation_owner_reads_and_continues_without_the_token(sessionmaker):
    owner = await auth.upsert_user(sessionmaker, SETTINGS, "200", "Owner")
    stranger = await auth.upsert_user(sessionmaker, SETTINGS, "201", "Stranger")
    conversation_id = await save_conversation(sessionmaker, token="guest-token", user_id=owner.id)
    repo = MemoryRepository(sessionmaker)

    mine = await repo.load(conversation_id, channel="web", external_ref=None, user_id=owner.id)
    assert mine.conversation.id == conversation_id
    for kwargs in ({}, {"user_id": stranger.id}, {"token": "wrong-token"}):  # khách, người khác, sai token
        with pytest.raises(UnauthorizedError):
            await repo.load(conversation_id, channel="web", external_ref=None, **kwargs)
    held = await repo.load(conversation_id, channel="web", external_ref=None, token="guest-token")
    assert held.conversation.id == conversation_id  # người giữ token vẫn đọc được như trước


async def test_claim_adopts_a_guest_conversation_only_with_its_token(sessionmaker):
    user = await auth.upsert_user(sessionmaker, SETTINGS, "300", "Claimer")
    rival = await auth.upsert_user(sessionmaker, SETTINGS, "301", "Rival")
    conversation_id = await save_conversation(sessionmaker, token="claim-token", question="Ranni ở đâu?")

    with pytest.raises(UnauthorizedError):
        await auth.claim_conversation(sessionmaker, user.id, conversation_id, owner_hash("not-the-token"))
    with pytest.raises(NotFoundError):
        await auth.claim_conversation(sessionmaker, user.id, uuid4(), owner_hash("claim-token"))
    assert await auth.list_conversations(sessionmaker, user.id) == []

    await auth.claim_conversation(sessionmaker, user.id, conversation_id, owner_hash("claim-token"))
    await auth.claim_conversation(sessionmaker, user.id, conversation_id, owner_hash("claim-token"))  # nhận lại: vẫn ổn
    listed = await auth.list_conversations(sessionmaker, user.id)
    assert [(i, title) for i, title, _ in listed] == [(conversation_id, "Ranni ở đâu?")]

    with pytest.raises(NotFoundError):  # đã có chủ: kẻ có token cũng không giành được
        await auth.claim_conversation(sessionmaker, rival.id, conversation_id, owner_hash("claim-token"))
    assert await auth.list_conversations(sessionmaker, rival.id) == []


async def test_deleting_a_user_keeps_the_conversation_as_a_guest_one(sessionmaker):
    user = await auth.upsert_user(sessionmaker, SETTINGS, "400", "Leaving")
    conversation_id = await save_conversation(sessionmaker, token="stay-token", user_id=user.id)
    async with sessionmaker() as session, session.begin():
        await session.execute(text("delete from users where id = :id"), {"id": user.id})
    async with sessionmaker() as session:
        conv = await session.get(Conversation, conversation_id)
    assert conv is not None and conv.user_id is None
