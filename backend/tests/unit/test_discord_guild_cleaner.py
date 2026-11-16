"""GuildMemoryCleaner với session giả (thứ tự xóa, lỗi Qdrant, log), cuộc đua indexer, dựng MemoryVectors từ ctx,
và khóa rate limit IPv6 theo /64. Truy vấn SQL thật chạy ở tests/integration/test_discord_guild.py.

Phụ trách: TV1 · [S5] API server Discord cho bot
"""

import logging
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.api.guard import _client_ip
from app.api.routes.discord_guilds import get_memory_cleaner
from app.rag.semantic_memory import MemoryScope, MemoryVectors, SemanticMemory
from app.services.discord_guild import GuildMemoryCleaner
from core.config import Settings
from core.errors import UnavailableError


class FakeSession:
    """Đủ cho clear(): scalars → danh sách id, scalar → số thread, execute(delete) → rowcount."""

    def __init__(self, ids, threads, log):
        self.ids, self.threads, self.log = ids, threads, log

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def begin(self):
        return self

    async def scalars(self, _query):
        return SimpleNamespace(all=lambda: list(self.ids))

    async def scalar(self, _query):
        return self.threads

    async def execute(self, _query):
        self.log.append("pg_delete")
        return SimpleNamespace(rowcount=len(self.ids))


class RecordingVectors:
    def __init__(self, log, *, available=True, error=None):
        self.log, self._available, self.error = log, available, error
        self.probes = 0

    async def available(self):
        self.probes += 1
        return self._available

    async def delete_conversations(self, ids):
        self.log.append("vectors_delete")
        if self.error:
            raise self.error


def cleaner(ids, vectors, *, threads=0, log=None, forget=None):
    log = [] if log is None else log
    return GuildMemoryCleaner(lambda: FakeSession(ids, threads, log), vectors, forget), log


async def test_vectors_are_deleted_before_and_again_after_postgres_so_a_racing_indexer_cannot_leave_points():
    log = []
    ids = [uuid4(), uuid4()]
    forgotten = []
    c, _ = cleaner(ids, RecordingVectors(log), log=log, forget=forgotten.extend)

    result = await c.clear("1")

    assert log == ["vectors_delete", "pg_delete", "vectors_delete"]
    assert result == {"conversations": 2, "threads_kept": 0, "vector_conversations": 2}
    assert forgotten == ids


async def test_collection_availability_is_probed_once_per_clear_not_per_batch(monkeypatch):
    monkeypatch.setattr("app.services.discord_guild.BATCH", 2)
    vectors = RecordingVectors([])
    c, log = cleaner([uuid4() for _ in range(5)], vectors)

    await c.clear("1")

    assert vectors.probes == 1 and log.count("pg_delete") == 3  # 5 hội thoại, lô 2 → 3 lô


async def test_missing_collection_or_no_vector_store_still_clears_postgres():
    ids = [uuid4()]
    for vectors in (RecordingVectors([], available=False), None):
        c, log = cleaner(ids, vectors)
        result = await c.clear("1")
        assert result["conversations"] == 1 and result["vector_conversations"] == 0
        assert log == ["pg_delete"]


async def test_threads_are_reported_as_kept_for_one_user_only():
    c, _ = cleaner([uuid4()], None, threads=4)

    assert (await c.clear("1", user_hash="a" * 64))["threads_kept"] == 4
    assert (await c.clear("1"))["threads_kept"] == 0  # xóa cả server thì không còn thread nào bị giữ


@pytest.mark.parametrize(
    "error",
    [
        UnexpectedResponse(500, "boom", b"", {}),
        ResponseHandlingException(httpx.ConnectError("down")),
        httpx.ReadTimeout("slow"),
        ConnectionError("refused"),
        TimeoutError(),
    ],
)
async def test_qdrant_and_transport_errors_become_503_and_are_logged(error, caplog):
    log = []
    c, _ = cleaner([uuid4()], RecordingVectors(log, error=error), log=log)

    with caplog.at_level(logging.WARNING), pytest.raises(UnavailableError):
        await c.clear("1")

    assert log == ["vectors_delete"]  # lỗi ở lần xóa đầu: PostgreSQL chưa bị đụng tới
    assert any(r.exc_info for r in caplog.records)


async def test_a_programming_error_is_not_masked_as_unavailable():
    c, _ = cleaner([uuid4()], RecordingVectors([], error=KeyError("bug")))

    with pytest.raises(KeyError):
        await c.clear("1")


# --- indexer: không để điểm vector mồ côi của hội thoại đã bị xóa ---


class IndexRepository:
    def __init__(self, exists):
        self.exists = exists
        self.marked = []

    async def pending(self, conversation_id, owner=None):
        return [SimpleNamespace(id=uuid4(), status="active", embedding_text="Ranni", revision=1)]

    async def mark_indexed(self, memory_id, revision, *, error=None):
        self.marked.append(memory_id)

    async def conversation_exists(self, conversation_id):
        return self.exists


class IndexVectors:
    def __init__(self):
        self.upserts, self.cleared = [], []

    async def validate(self):
        return None

    async def upsert(self, scope, row, vector):
        self.upserts.append(row.id)

    async def delete_conversations(self, ids):
        self.cleared.append(list(ids))


class FixedEncoder:
    async def encode_dense(self, texts, *, query=False):
        return [[0.0] * 384 for _ in texts]


@pytest.mark.parametrize("exists", [True, False])
async def test_sync_removes_points_it_just_wrote_for_a_conversation_deleted_meanwhile(exists):
    scope = MemoryScope(uuid4(), "owner")
    vectors = IndexVectors()
    memory = SemanticMemory(
        IndexRepository(exists), vectors, FixedEncoder(), Settings(_env_file=None, environment="test")
    )

    counts = await memory.sync(scope)

    assert len(vectors.upserts) == 1 and not counts["failed"]
    assert vectors.cleared == ([] if exists else [[scope.conversation_id]])


# --- get_memory_cleaner dựng MemoryVectors từ ctx, không phụ thuộc pipeline chat ---


def _request(qdrant, settings=None, sessionmaker=object()):
    settings = settings or Settings(_env_file=None, environment="test")
    ctx = SimpleNamespace(settings=settings, qdrant=qdrant, sessionmaker=sessionmaker)
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(ctx=ctx)))


def test_cleaner_uses_the_configured_memory_collection_even_when_chat_memory_is_off():
    settings = Settings(_env_file=None, environment="test", chat_memory_collection="mem_x", rag_collection="lore_y")
    service = SimpleNamespace(pipeline=SimpleNamespace(memory=None))  # chat không bật ký ức ngữ nghĩa
    qdrant = object()

    built = get_memory_cleaner(_request(qdrant, settings), service)

    assert isinstance(built.vectors, MemoryVectors)
    assert built.vectors.client is qdrant and built.vectors.collection == "mem_x"


def test_cleaner_has_no_vector_store_without_a_qdrant_client():
    assert get_memory_cleaner(_request(None), SimpleNamespace()).vectors is None


def test_cleaner_needs_a_database():
    with pytest.raises(UnavailableError):
        get_memory_cleaner(_request(None, sessionmaker=None), SimpleNamespace())


# --- rate limit IPv6 theo /64 ---


def _ip(host):
    return _client_ip(SimpleNamespace(client=SimpleNamespace(host=host)))


def test_ipv4_is_unchanged_and_unparseable_hosts_pass_through():
    assert _ip("203.0.113.7") == "203.0.113.7"
    assert _ip("testclient") == "testclient"
    assert _client_ip(SimpleNamespace(client=None)) == "-"


def test_ipv6_addresses_in_the_same_64_share_one_rate_limit_key():
    a, b = _ip("2001:db8:1:2:aaaa:bbbb:cccc:dddd"), _ip("2001:db8:1:2:1::1")

    assert a == b == "2001:db8:1:2::/64"
    assert _ip("2001:db8:1:3::1") != a  # /64 khác thì khóa khác


def test_ipv4_mapped_ipv6_uses_the_ipv4_key():
    assert _ip("::ffff:203.0.113.7") == "203.0.113.7"
