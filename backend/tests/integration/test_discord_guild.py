"""Kênh `/setup` và xóa ký ức `/clear` trên PostgreSQL thật (migration 0005). DB tạm do fixture dùng chung tạo.

Chạy: make up && pytest -m integration

Phụ trách: TV1 · [S5] API server Discord cho bot
"""

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.schemas.conversation import ConversationOut, MessageOut
from app.api.schemas.discord_guild import MAX_CHANNELS_PER_GUILD
from app.services.discord_guild import GuildChannelStore, GuildMemoryCleaner
from app.services.memory_repository import MemoryRepository, Snapshot, owner_hash
from core.db.models import Conversation, ConversationMemory, DiscordGuildChannel, Feedback, Message
from core.errors import ConflictError
from tests.integration.test_db_schema import db_url  # noqa: F401  (fixture dùng chung)

pytestmark = pytest.mark.integration

GUILD, OTHER_GUILD = "1000000000000000001", "1000000000000000002"
ALICE, BOB = (hashlib.sha256(name.encode()).hexdigest() for name in ("alice-discord-id", "bob-discord-id"))


@pytest.fixture
async def sessionmaker(db_url: str):  # noqa: F811
    engine = create_async_engine(db_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
async def _empty_guild_channels(sessionmaker):
    """DB là của cả module (scope=module): dọn kênh /setup trước mỗi test để các test không thấy dữ liệu của nhau."""
    async with sessionmaker() as session, session.begin():
        await session.execute(DiscordGuildChannel.__table__.delete())


class FakeVectors:
    def __init__(self):
        self.calls = []

    async def available(self):
        return True

    async def delete_conversations(self, ids):
        self.calls.append(set(ids))


async def talk(sessionmaker, external_ref, *, guild_id, channel="discord", revision=0, conv_id=None, question="Ranni?"):
    """Một lượt hỏi đáp qua đúng đường lưu của chat: tạo hội thoại, 2 tin nhắn, 1 dòng ký ức `topic`."""
    now = datetime.now(UTC)
    conv = ConversationOut(id=conv_id or uuid4(), channel=channel, created_at=now, messages=[])
    pair = [
        MessageOut(id=uuid4(), role="user", content=question, created_at=now),
        MessageOut(id=uuid4(), role="assistant", content="Ranni là phù thủy.", created_at=now),
    ]
    snapshot = Snapshot(conv, external_ref, owner_hash(external_ref or "x"), revision, {}, guild_id=guild_id)
    decision = {"intent": "lore", "action": "retrieve", "resolved_question": question}
    await MemoryRepository(sessionmaker).save(snapshot, pair, {}, decision)
    return conv.id, pair[1].id


async def count(sessionmaker, model) -> int:
    async with sessionmaker() as session:
        return await session.scalar(select(func.count()).select_from(model))


# --- kênh /setup ---


async def test_enable_is_idempotent_and_listing_is_per_guild(sessionmaker):
    store = GuildChannelStore(sessionmaker)

    first = await store.enable(GUILD, "11")
    again = await store.enable(GUILD, "11")
    await store.enable(GUILD, "22")
    await store.enable(OTHER_GUILD, "33")

    assert first.created_at == again.created_at
    assert [r.channel_id for r in await store.list(GUILD)] == ["11", "22"]
    assert [r.channel_id for r in await store.list(OTHER_GUILD)] == ["33"]


async def test_disable_one_then_all_only_touches_that_guild(sessionmaker):
    store = GuildChannelStore(sessionmaker)
    for channel in ("11", "22", "33"):
        await store.enable("2000000000000000001", channel)
    await store.enable("2000000000000000002", "44")

    assert await store.disable("2000000000000000001", "11") == 1
    assert await store.disable("2000000000000000001", "11") == 0  # idempotent
    assert await store.disable("2000000000000000001") == 2
    assert await store.disable("2000000000000000001") == 0
    assert [r.channel_id for r in await store.list("2000000000000000002")] == ["44"]


async def test_cap_holds_even_when_enables_race(sessionmaker):
    store = GuildChannelStore(sessionmaker)
    guild = "3000000000000000001"

    results = await asyncio.gather(
        *(store.enable(guild, str(n)) for n in range(MAX_CHANNELS_PER_GUILD + 10)), return_exceptions=True
    )

    assert sum(isinstance(r, ConflictError) for r in results) == 10
    assert len(await store.list(guild)) == MAX_CHANNELS_PER_GUILD
    assert (await store.enable(guild, "0")).channel_id == "0"  # kênh đã bật vẫn gọi lại được khi đầy


# --- guild_id được lưu cùng hội thoại ---


async def test_save_records_guild_id_and_backfills_conversations_that_predate_it(sessionmaker):
    ref = f"discord:channel:5:{ALICE}"
    conv_id, _ = await talk(sessionmaker, ref, guild_id=None)
    async with sessionmaker() as session:
        assert (await session.get(Conversation, conv_id)).guild_id is None

    await _second_turn(sessionmaker, conv_id, ref, guild_id=GUILD)

    async with sessionmaker() as session:
        assert (await session.get(Conversation, conv_id)).guild_id == GUILD
    await _second_turn(sessionmaker, conv_id, ref, guild_id=OTHER_GUILD)  # không ghi đè guild đã có
    async with sessionmaker() as session:
        assert (await session.get(Conversation, conv_id)).guild_id == GUILD


async def _second_turn(sessionmaker, conv_id: UUID, ref: str, *, guild_id):
    repo = MemoryRepository(sessionmaker)
    snapshot = await repo.load(conv_id, channel="discord", external_ref=ref)
    now = datetime.now(UTC)
    pair = [
        MessageOut(id=uuid4(), role="user", content="Còn Radahn?", created_at=now),
        MessageOut(id=uuid4(), role="assistant", content="Radahn là tướng quân.", created_at=now),
    ]
    snapshot.guild_id = guild_id
    await repo.save(snapshot, pair, {}, {"intent": "smalltalk"})


# --- /clear ---


async def seed(sessionmaker):
    """Alice 2 kênh + Bob 1 kênh + 1 thread trong GUILD; Alice 1 kênh trong OTHER_GUILD; 1 hội thoại web."""
    ids = {
        "alice_1": await talk(sessionmaker, f"discord:channel:5:{ALICE}", guild_id=GUILD),
        "alice_2": await talk(sessionmaker, f"discord:channel:6:{ALICE}", guild_id=GUILD),
        "bob": await talk(sessionmaker, f"discord:channel:5:{BOB}", guild_id=GUILD),
        "thread": await talk(sessionmaker, "discord:thread:77", guild_id=GUILD),
        "alice_other": await talk(sessionmaker, f"discord:channel:9:{ALICE}", guild_id=OTHER_GUILD),
        "alice_no_guild": await talk(sessionmaker, f"discord:channel:8:{ALICE}", guild_id=None),
        "web": await talk(sessionmaker, None, guild_id=None, channel="web"),
    }
    await MemoryRepository(sessionmaker).save_feedback(ids["alice_1"][1], 1, None)
    return {name: conv for name, (conv, _) in ids.items()}


async def survivors(sessionmaker, ids) -> set[str]:
    async with sessionmaker() as session:
        alive = set((await session.scalars(select(Conversation.id))).all())
    return {name for name, conv in ids.items() if conv in alive}


@pytest.fixture
async def clean(sessionmaker):
    async with sessionmaker() as session, session.begin():
        for model in (Feedback, ConversationMemory, Message, Conversation):
            await session.execute(model.__table__.delete())
    yield


async def test_clear_user_removes_only_that_users_conversations_in_that_guild(sessionmaker, clean):
    ids = await seed(sessionmaker)
    vectors, forgotten = FakeVectors(), []
    cleaner = GuildMemoryCleaner(sessionmaker, vectors, forgotten.extend)

    result = await cleaner.clear(GUILD, user_hash=ALICE)

    assert result == {"conversations": 2, "threads_kept": 1, "vector_conversations": 2}
    assert await survivors(sessionmaker, ids) == {"bob", "thread", "alice_other", "alice_no_guild", "web"}
    alice = {ids["alice_1"], ids["alice_2"]}
    assert vectors.calls == [alice, alice] and set(forgotten) == alice  # xóa vector trước và sau khi xóa PostgreSQL
    assert await count(sessionmaker, Feedback) == 0  # feedback của Alice đã xóa theo tin nhắn (cascade)
    assert await count(sessionmaker, Message) == 10 and await count(sessionmaker, ConversationMemory) == 5


async def test_clear_is_idempotent(sessionmaker, clean):
    await seed(sessionmaker)
    cleaner = GuildMemoryCleaner(sessionmaker, FakeVectors())

    await cleaner.clear(GUILD, user_hash=ALICE)
    again = await cleaner.clear(GUILD, user_hash=ALICE)

    assert again == {"conversations": 0, "threads_kept": 1, "vector_conversations": 0}  # thread vẫn còn


async def test_clear_all_removes_threads_and_every_member_but_not_other_guilds_or_web(sessionmaker, clean):
    ids = await seed(sessionmaker)

    result = await GuildMemoryCleaner(sessionmaker, FakeVectors()).clear(GUILD)

    assert result == {"conversations": 4, "threads_kept": 0, "vector_conversations": 4}
    assert await survivors(sessionmaker, ids) == {"alice_other", "alice_no_guild", "web"}
    assert await count(sessionmaker, ConversationMemory) == 3  # ký ức của 3 hội thoại còn lại


async def test_user_hash_is_matched_exactly_not_as_a_substring_or_wildcard(sessionmaker, clean):
    ids = await seed(sessionmaker)

    result = await GuildMemoryCleaner(sessionmaker).clear(GUILD, user_hash="%" * 64)

    assert result["conversations"] == 0 and len(await survivors(sessionmaker, ids)) == 7


async def test_vector_failure_leaves_postgres_untouched_so_a_retry_finishes_the_job(sessionmaker, clean):
    ids = await seed(sessionmaker)

    class Broken:
        async def available(self):
            return True

        async def delete_conversations(self, ids):
            raise ConnectionError("qdrant down")

    from core.errors import UnavailableError

    with pytest.raises(UnavailableError):
        await GuildMemoryCleaner(sessionmaker, Broken()).clear(GUILD)
    assert len(await survivors(sessionmaker, ids)) == 7

    result = await GuildMemoryCleaner(sessionmaker, FakeVectors()).clear(GUILD)
    assert result["conversations"] == 4


async def test_channel_config_survives_clear(sessionmaker, clean):
    await seed(sessionmaker)
    store = GuildChannelStore(sessionmaker)
    await store.enable(GUILD, "5")

    await GuildMemoryCleaner(sessionmaker).clear(GUILD)

    assert [r.channel_id for r in await store.list(GUILD)] == ["5"]
    assert await count(sessionmaker, DiscordGuildChannel) >= 1
