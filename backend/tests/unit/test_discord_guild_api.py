"""API server Discord cho bot (/setup, /clear): xác thực service token, kiểm tra ID, mã lỗi và dạng phản hồi.
Kho dữ liệu giả; truy vấn thật chạy ở tests/integration/test_discord_guild.py (cần PostgreSQL).

Phụ trách: TV1 · [S5] API server Discord cho bot
"""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes.discord_guilds import get_channel_store, get_memory_cleaner
from app.api.schemas.conversation import ConversationOut, MessageOut
from app.api.schemas.discord_guild import MAX_CHANNELS_PER_GUILD
from app.main import create_app
from app.rag.semantic_memory import MemoryVectors
from app.services.chat import ConversationState, LiveChatService
from core.config import Settings
from core.errors import ConflictError, UnavailableError

TOKEN = "bot-secret-for-tests"
AUTH = {"X-Service-Token": TOKEN}
GUILD, CHANNEL = "111222333444555666", "777888999000111222"
USER_HASH = "a" * 64
BASE = f"/api/v1/discord/guilds/{GUILD}"


class FakeStore:
    def __init__(self):
        self.rows: dict[str, datetime] = {}
        self.fail = False

    async def list(self, guild_id):
        self._check()
        return [SimpleNamespace(channel_id=c, created_at=t) for c, t in self.rows.items()]

    async def enable(self, guild_id, channel_id):
        self._check()
        if channel_id not in self.rows and len(self.rows) >= MAX_CHANNELS_PER_GUILD:
            raise ConflictError("full")
        self.rows.setdefault(channel_id, datetime(2026, 11, 16, tzinfo=UTC))
        return SimpleNamespace(channel_id=channel_id, created_at=self.rows[channel_id])

    async def disable(self, guild_id, channel_id=None):
        self._check()
        gone = list(self.rows) if channel_id is None else [c for c in self.rows if c == channel_id]
        for c in gone:
            del self.rows[c]
        return len(gone)

    def _check(self):
        if self.fail:
            raise UnavailableError()


class FakeCleaner:
    def __init__(self):
        self.calls = []

    async def clear(self, guild_id, *, user_hash=None):
        self.calls.append((guild_id, user_hash))
        return {"conversations": 2, "threads_kept": 1, "vector_conversations": 2}


@pytest.fixture
def api(ctx):
    ctx.settings = Settings(_env_file=None, environment="test", api_service_token=TOKEN)
    store, cleaner = FakeStore(), FakeCleaner()
    app = create_app(ctx.settings, context=ctx)
    app.dependency_overrides[get_channel_store] = lambda: store
    app.dependency_overrides[get_memory_cleaner] = lambda: cleaner
    with TestClient(app) as client:
        yield client, store, cleaner


ENDPOINTS = [
    ("GET", "/channels", None),
    ("PUT", f"/channels/{CHANNEL}", None),
    ("DELETE", f"/channels/{CHANNEL}", None),
    ("DELETE", "/channels", None),
    ("POST", "/memory/clear", {"scope": "all"}),
]


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
@pytest.mark.parametrize("headers", [{}, {"X-Service-Token": "guess"}, {"X-Admin-Token": TOKEN}])
def test_every_endpoint_requires_the_service_token(api, method, path, body, headers):
    client, store, cleaner = api

    response = client.request(method, BASE + path, json=body, headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized" and response.json()["request_id"]
    assert not store.rows and not cleaner.calls


def test_unset_service_token_never_authenticates(ctx):
    ctx.settings = Settings(_env_file=None, environment="test")  # không đặt API_SERVICE_TOKEN
    with TestClient(create_app(ctx.settings, context=ctx)) as client:
        assert client.get(BASE + "/channels", headers={"X-Service-Token": ""}).status_code == 401


def test_bad_ids_fail_auth_first_then_validation(api):
    client, *_ = api

    assert client.get("/api/v1/discord/guilds/abc/channels").status_code == 401
    for path in ("/api/v1/discord/guilds/abc/channels", f"/api/v1/discord/guilds/{'1' * 33}/channels"):
        assert client.get(path, headers=AUTH).status_code == 422
    for bad in ("abc", "12-3", "1" * 33):
        assert client.put(f"{BASE}/channels/{bad}", headers=AUTH).status_code == 422


def test_enable_list_disable_roundtrip_is_idempotent(api):
    client, *_ = api

    first = client.put(f"{BASE}/channels/{CHANNEL}", headers=AUTH)
    again = client.put(f"{BASE}/channels/{CHANNEL}", headers=AUTH)
    listed = client.get(BASE + "/channels", headers=AUTH).json()
    removed = client.delete(f"{BASE}/channels/{CHANNEL}", headers=AUTH)
    removed_again = client.delete(f"{BASE}/channels/{CHANNEL}", headers=AUTH)

    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    assert listed["guild_id"] == GUILD and listed["limit"] == MAX_CHANNELS_PER_GUILD
    assert [c["channel_id"] for c in listed["channels"]] == [CHANNEL]
    assert removed.json() == {"deleted": 1} and removed_again.json() == {"deleted": 0}
    assert removed_again.status_code == 200


def test_disable_all_reports_how_many_channels_were_removed(api):
    client, *_ = api
    for n in range(3):
        client.put(f"{BASE}/channels/{n + 1}", headers=AUTH)

    assert client.delete(BASE + "/channels", headers=AUTH).json() == {"deleted": 3}
    assert client.delete(BASE + "/channels", headers=AUTH).json() == {"deleted": 0}


def test_channel_cap_is_409_with_the_standard_error_shape(api):
    client, store, _ = api
    for n in range(MAX_CHANNELS_PER_GUILD):
        assert client.put(f"{BASE}/channels/{n + 1}", headers=AUTH).status_code == 200

    full = client.put(f"{BASE}/channels/999", headers=AUTH)

    assert full.status_code == 409 and full.json()["code"] == "conflict"
    assert client.put(f"{BASE}/channels/1", headers=AUTH).status_code == 200  # kênh đã bật vẫn gọi lại được


def test_store_outage_is_503_not_a_stack_trace(api):
    client, store, _ = api
    store.fail = True

    response = client.get(BASE + "/channels", headers=AUTH)

    assert response.status_code == 503 and response.json()["code"] == "unavailable"


def test_clear_user_passes_only_the_hash_and_reports_counts(api):
    client, _, cleaner = api

    response = client.post(BASE + "/memory/clear", headers=AUTH, json={"scope": "user", "user_hash": USER_HASH})

    assert response.status_code == 200
    assert response.json() == {
        "guild_id": GUILD,
        "scope": "user",
        "conversations": 2,
        "threads_kept": 1,
        "vector_conversations": 2,
    }
    assert cleaner.calls == [(GUILD, USER_HASH)]


def test_clear_all_has_no_user(api):
    client, _, cleaner = api

    response = client.post(BASE + "/memory/clear", headers=AUTH, json={"scope": "all"})

    assert response.status_code == 200 and response.json()["scope"] == "all"
    assert cleaner.calls == [(GUILD, None)]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"scope": "everything"},
        {"scope": "user"},
        {"scope": "user", "user_hash": "123456789012345678"},  # ID Discord thô bị từ chối: chỉ nhận bản băm
        {"scope": "user", "user_hash": "A" * 64},
        {"scope": "user", "user_hash": "a" * 63},
    ],
)
def test_clear_rejects_missing_scope_and_raw_discord_ids(api, body):
    client, _, cleaner = api

    response = client.post(BASE + "/memory/clear", headers=AUTH, json=body)

    assert response.status_code == 422 and not cleaner.calls
    assert "123456789012345678" not in response.text  # không echo giá trị gửi lên


# --- Qdrant: xóa theo payload conversation_id (client local in-memory, lọc thật) ---


async def _memory_vectors(*conversations):
    from qdrant_client import AsyncQdrantClient
    from qdrant_client import models as qm

    client = AsyncQdrantClient(":memory:")
    vectors = MemoryVectors(client, "mem", "corpus")
    await vectors.setup()
    points = [
        qm.PointStruct(id=str(uuid4()), vector={"dense": [1.0] + [0.0] * 383}, payload={"conversation_id": str(c)})
        for c in conversations
    ]
    if points:
        await client.upsert("mem", points=points, wait=True)
    return client, vectors


async def _remaining(client) -> set[str]:
    points, _ = await client.scroll("mem", limit=100, with_payload=True)
    return {p.payload["conversation_id"] for p in points}


def test_vector_delete_removes_only_the_given_conversations():
    kept, gone_a, gone_b = uuid4(), uuid4(), uuid4()

    async def scenario():
        client, vectors = await _memory_vectors(kept, gone_a, gone_a, gone_b)
        result = await vectors.delete_conversations([gone_a, gone_b])
        return result, await _remaining(client)

    result, remaining = asyncio.run(scenario())

    assert result is None and remaining == {str(kept)}


def test_vector_delete_is_idempotent_and_ignores_an_empty_batch():
    gone = uuid4()

    async def scenario():
        client, vectors = await _memory_vectors(gone)
        await vectors.delete_conversations([gone])
        await vectors.delete_conversations([gone])
        await vectors.delete_conversations([])
        return await _remaining(client)

    assert asyncio.run(scenario()) == set()


def test_delete_does_not_probe_the_collection_each_time():
    async def scenario():
        client, vectors = await _memory_vectors()
        calls = []
        original = client.collection_exists

        async def spy(name):
            calls.append(name)
            return await original(name)

        client.collection_exists = spy
        await vectors.delete_conversations([uuid4()])
        await vectors.delete_conversations([uuid4()])
        return calls, await vectors.available()

    calls, available = asyncio.run(scenario())
    assert calls == ["mem"] and available is True  # chỉ lần gọi `available()` hỏi


def test_absent_collection_is_not_available():
    from qdrant_client import AsyncQdrantClient

    assert asyncio.run(MemoryVectors(AsyncQdrantClient(":memory:"), "absent", "corpus").available()) is False


# --- Bộ nhớ RAM của LiveChatService ---


def test_forget_drops_cached_conversation_and_its_external_ref_index():
    from tests.unit.test_live_chat import service

    live: LiveChatService = service()
    conv = ConversationOut(id=uuid4(), channel="discord", created_at=datetime.now(UTC), messages=[])
    live._conversations[conv.id] = ConversationState(conv, "discord:thread:1")
    live._by_ref[("discord", "discord:thread:1")] = conv.id

    live.forget([conv.id, uuid4()])  # id lạ bị bỏ qua

    assert conv.id not in live._conversations and ("discord", "discord:thread:1") not in live._by_ref


def test_stale_ram_copy_of_a_cleared_discord_conversation_restarts_as_a_new_one_transparently():
    from app.api.schemas.chat import ChatRequest
    from core.errors import NotFoundError
    from tests.unit.test_live_chat import service

    class GoneRepository:
        async def load(self, *args, **kwargs):
            raise NotFoundError()

    live = service()
    live.repository = GoneRepository()
    old = MessageOut(id=uuid4(), role="user", content="cũ", created_at=datetime.now(UTC))
    conv = ConversationOut(id=uuid4(), channel="discord", created_at=datetime.now(UTC), messages=[old])
    state = ConversationState(conv, "discord:thread:1", revision=3, player={"old": 1}, owner="owner-hash")
    live._conversations[conv.id] = state
    req = ChatRequest(message="Ranni?", channel="discord", external_ref="discord:thread:1")

    asyncio.run(live._refresh(state, req))  # không ném lỗi

    assert state.revision == 0 and state.conversation.messages == [] and state.player is None
    assert state.conversation.id == conv.id and state.owner == "owner-hash"  # cùng khóa, như cache miss
    assert live._conversations[conv.id] is state


def test_stale_web_conversation_still_reports_not_found():
    from app.api.schemas.chat import ChatRequest
    from core.errors import NotFoundError
    from tests.unit.test_live_chat import service

    class GoneRepository:
        async def load(self, *args, **kwargs):
            raise NotFoundError()

    live = service()
    live.repository = GoneRepository()
    conv = ConversationOut(id=uuid4(), channel="web", created_at=datetime.now(UTC), messages=[])
    state = ConversationState(conv, None, revision=3)
    req = ChatRequest(message="Ranni?", channel="web", conversation_id=conv.id)

    with pytest.raises(NotFoundError):
        asyncio.run(live._refresh(state, req))


# --- guild_id chỉ được tin khi có service token ---


class CapturingService:
    def __init__(self):
        self.seen = []

    async def answer(self, req):
        from app.api.schemas.chat import ChatResponse

        self.seen.append(req.guild_id)
        return ChatResponse(
            conversation_id=uuid4(), message_id=uuid4(), answer="ok", sources=[], grounded=False, latency_ms=1
        )


def test_guild_id_reaches_the_service_only_with_a_valid_service_token(ctx):
    ctx.settings = Settings(_env_file=None, environment="test", chat_mode="llm_only", api_service_token=TOKEN)
    with TestClient(create_app(ctx.settings, context=ctx)) as client:
        service = client.app.state.chat_service = CapturingService()
        body = {"message": "Ranni là ai?", "guild_id": GUILD}

        client.post("/api/v1/chat", json={**body, "channel": "web"})
        client.post(
            "/api/v1/chat", json={**body, "channel": "discord", "external_ref": "discord:thread:1"}, headers=AUTH
        )

    assert service.seen == [None, GUILD]
