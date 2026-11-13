"""Trace RAG: che secret, giới hạn cỡ, đếm token; endpoint admin và việc trace chỉ còn trong RAM khi không có DB.

Phụ trách: TV1 · [S3] Trace từng bước RAG
"""

import json
from contextlib import ExitStack
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.deps import get_chat_service
from app.context import AppContext, register_infra
from app.main import create_app
from app.rag.trace import MAX_TRACE_BYTES, public_trace, token_usage
from core.config import REPO_ROOT
from core.errors import NotFoundError


def test_public_trace_drops_internal_keys_and_the_answer_text():
    raw = {"result": object(), "_format_retry": True, "selected_ids": ["a"], "nested": {"_private": 1, "ok": 2}}
    assert public_trace(raw, latency_ms=3.5) == {"selected_ids": ["a"], "nested": {"ok": 2}, "latency_ms": 3.5}


def test_public_trace_redacts_secrets_by_key_and_by_value():
    raw = {
        "api_key": "abc",
        "web_search": {"authorization": "Bearer zzz", "query": "Ranni"},
        "note": "sent sk-abcdefghijklmnop1234 and Bearer top-secret-value",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    cleaned = public_trace(raw)
    assert cleaned["api_key"] == "[redacted]" and cleaned["web_search"]["authorization"] == "[redacted]"
    assert cleaned["web_search"]["query"] == "Ranni"
    assert "sk-abcdefghijklmnop1234" not in cleaned["note"] and "top-secret-value" not in cleaned["note"]
    assert cleaned["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}  # *_tokens không phải secret


def test_public_trace_is_json_safe_and_bounded():
    cleaned = public_trace({"when": datetime.now(UTC), "id": uuid4(), "rows": list(range(500)), "text": "x" * 5000})
    json.dumps(cleaned)
    assert len(cleaned["rows"]) == 50 and len(cleaned["text"]) < 1100
    huge = public_trace({"latency_ms": 1.0, **{f"k{i}": ["y" * 900] * 50 for i in range(3)}})
    assert huge["truncated"] is True and huge["latency_ms"] == 1.0 and len(json.dumps(huge)) < MAX_TRACE_BYTES


def test_token_usage_sums_generation_and_rewrite_and_tolerates_missing_values():
    trace = {"usage": {"prompt_tokens": 100, "completion_tokens": 20}, "rewrite": {"usage": {"prompt_tokens": 7}}}
    assert token_usage(trace) == (107, 20)
    agent = {"usage": {"prompt_tokens": 5, "completion_tokens": 2}}
    assert token_usage({**trace, "agent": agent}) == (112, 22)  # quyết định của agent cũng tốn token
    assert token_usage({}) == (None, None)
    assert token_usage({"usage": {"prompt_tokens": None, "completion_tokens": None}}) == (None, None)


class FakeTraceService:
    def __init__(self):
        self.known = uuid4()

    async def trace(self, message_id):
        if message_id != self.known:
            raise NotFoundError("Không tìm thấy trace của câu trả lời này.")
        return {"message_id": message_id, "trace": {"retrieved": []}, "source": "memory"}


@pytest.fixture
def admin_client(settings, fakes):
    stack = ExitStack()  # lifespan phải chạy để app.state.ctx tồn tại

    def make(token: str | None) -> tuple[TestClient, FakeTraceService]:
        configured = settings.model_copy(update={"admin_token": SecretStr(token) if token is not None else None})
        ctx = AppContext(settings=configured, sessionmaker=None, **fakes)  # type: ignore[arg-type]
        register_infra(ctx)
        client = stack.enter_context(TestClient(create_app(configured, context=ctx)))
        service = FakeTraceService()
        client.app.dependency_overrides[get_chat_service] = lambda: service
        return client, service

    with stack:
        yield make


@pytest.mark.parametrize("token", [None, "", "change-me"])
def test_admin_is_disabled_until_a_real_token_is_configured(admin_client, token):
    client, service = admin_client(token)
    response = client.get(f"/api/v1/admin/trace/{service.known}", headers={"X-Admin-Token": token or "x"})
    assert response.status_code == 404


def test_admin_trace_requires_the_right_token(admin_client):
    client, service = admin_client("s3cret-token")
    url = f"/api/v1/admin/trace/{service.known}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"X-Admin-Token": "wrong"}).status_code == 401
    ok = client.get(url, headers={"X-Admin-Token": "s3cret-token"})
    assert ok.status_code == 200 and ok.json()["source"] == "memory"
    assert "s3cret-token" not in ok.text


def test_admin_trace_unknown_message_and_bad_id(admin_client):
    client, _ = admin_client("s3cret-token")
    headers = {"X-Admin-Token": "s3cret-token"}
    assert client.get(f"/api/v1/admin/trace/{uuid4()}", headers=headers).status_code == 404
    assert client.get("/api/v1/admin/trace/not-a-uuid", headers=headers).status_code == 422


def test_rag_trace_column_is_deferred_so_history_loads_do_not_read_it():
    from core.db.models import Message

    assert Message.__mapper__.column_attrs["rag_trace"].deferred is True
    assert Message.__mapper__.column_attrs["trace"].deferred is False  # ảnh và câu hỏi lại vẫn nạp cùng lịch sử


async def test_repository_trace_maps_database_errors_to_unavailable():
    from sqlalchemy.exc import OperationalError

    from app.services.memory_repository import MemoryRepository
    from core.errors import UnavailableError

    class Down:
        async def __aenter__(self):
            raise OperationalError("select", {}, ConnectionError("db down"))

        async def __aexit__(self, *args):
            return False

    with pytest.raises(UnavailableError):
        await MemoryRepository(lambda: Down()).trace(uuid4())


class FakeAsyncSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def stats_client(admin_client, monkeypatch, **repo_results):
    from core.db import repositories as repo

    client, _ = admin_client("s3cret-token")
    client.app.state.ctx.sessionmaker = lambda: FakeAsyncSession()
    defaults = {"recent_conversations": [], "recent_feedback": [], "list_jobs": [], "recent_eval_runs": []}
    for name, value in {**defaults, **repo_results}.items():

        async def fake(_session, *_args, _value=value, **_kwargs):
            if isinstance(_value, Exception):
                raise _value
            return _value

        monkeypatch.setattr(repo, name, fake)
    return client, SimpleNamespace(headers={"X-Admin-Token": "s3cret-token"})


def test_admin_stats_matches_the_shape_the_web_client_validates(admin_client, monkeypatch):
    when = datetime(2026, 11, 8, 3, 0, tzinfo=UTC)
    client, auth = stats_client(
        admin_client,
        monkeypatch,
        recent_conversations=[(uuid4(), "  Marika   là ai? " + "x" * 100, when), (uuid4(), None, when)],
        recent_feedback=[
            SimpleNamespace(message_id=uuid4(), rating=-1, reason="sai"),
            SimpleNamespace(message_id=uuid4(), rating=1, reason=None),
        ],
        list_jobs=[
            SimpleNamespace(external_id="crawl-abc", id=uuid4(), status="succeeded", pages_ok=7),
            SimpleNamespace(external_id=None, id=uuid4(), status="running", pages_ok=0),
        ],
        recent_eval_runs=[
            SimpleNamespace(
                id=uuid4(),
                config={"name": "baseline"},
                created_at=when,
                metrics={"recall@5": 0.8, "n": 3, "ok": True, "note": "x"},
            ),
            SimpleNamespace(id=uuid4(), config={}, created_at=when, metrics={"mrr": 0.4}),
        ],
    )
    response = client.get("/api/v1/admin/stats", headers=auth.headers)
    assert response.status_code == 200
    body = response.json()
    first, second = body["conversations"]
    assert first["title"].startswith("Marika là ai? xxx") and len(first["title"]) == 60
    assert second["title"] == "(chưa có câu hỏi)" and isinstance(first["created_at"], str)
    withreason, without = body["feedback"]
    assert withreason["reason"] == "sai" and "reason" not in without  # client web từ chối reason=null
    assert [j["id"] for j in body["ingestion_jobs"]][0] == "crawl-abc" and len(body["ingestion_jobs"][1]["id"]) == 36
    named, unnamed = body["eval_runs"]
    assert named["metrics"] == {"recall@5": 0.8, "n": 3}  # chỉ giữ số, bỏ bool và chuỗi
    assert named["id"] == "baseline · 08/11 03:00" and len(unnamed["id"]) == 36  # có tên thì hiện tên, không thì UUID


def test_admin_stats_is_empty_not_an_error_without_data(admin_client, monkeypatch):
    client, auth = stats_client(admin_client, monkeypatch)
    assert client.get("/api/v1/admin/stats", headers=auth.headers).json() == {
        "conversations": [],
        "feedback": [],
        "ingestion_jobs": [],
        "eval_runs": [],
    }


def test_admin_stats_requires_the_token_and_maps_database_errors(admin_client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    client, auth = stats_client(
        admin_client, monkeypatch, recent_feedback=OperationalError("select", {}, ConnectionError("db down"))
    )
    assert client.get("/api/v1/admin/stats").status_code == 401
    assert client.get("/api/v1/admin/stats", headers={"X-Admin-Token": "wrong"}).status_code == 401
    down = client.get("/api/v1/admin/stats", headers=auth.headers)
    assert down.status_code == 503 and down.json()["code"] == "unavailable"


@pytest.mark.parametrize("token,enabled", [(None, False), ("", False), ("change-me", False), ("s3cret-token", True)])
def test_admin_enabled_and_trace_capability_follow_the_token(admin_client, token, enabled):
    client, _ = admin_client(token)
    assert client.app.state.ctx.settings.admin_enabled is enabled
    assert client.get("/api/v1/chat/capabilities").json()["trace_available"] is enabled


def test_wrong_admin_tokens_are_throttled_per_ip_even_for_the_right_token_afterwards(admin_client):
    client, service = admin_client("s3cret-token")
    url = f"/api/v1/admin/trace/{service.known}"
    limit = client.app.state.ctx.settings.rate_limit_per_minute
    codes = [client.get(url, headers={"X-Admin-Token": f"guess-{i}"}).status_code for i in range(limit)]
    assert codes == [401] * limit
    blocked = client.get(url, headers={"X-Admin-Token": "s3cret-token"})
    assert blocked.status_code == 429 and blocked.json()["code"] == "rate_limited"
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60
    assert client.get(url, headers={"X-Admin-Token": "guess-again"}).status_code == 429


def test_correct_admin_requests_are_never_counted_as_failures(admin_client):
    client, service = admin_client("s3cret-token")
    headers = {"X-Admin-Token": "s3cret-token"}
    limit = client.app.state.ctx.settings.rate_limit_per_minute
    codes = {client.get(f"/api/v1/admin/trace/{service.known}", headers=headers).status_code for _ in range(limit * 3)}
    assert codes == {200}


def test_admin_throttle_fails_closed_when_redis_is_down(admin_client, fakes):
    client, service = admin_client("s3cret-token")
    fakes["redis"].fail = True
    response = client.get(f"/api/v1/admin/trace/{service.known}", headers={"X-Admin-Token": "s3cret-token"})
    assert response.status_code == 503


def test_disabled_admin_does_not_touch_redis_and_stays_404(admin_client, fakes):
    client, service = admin_client(None)
    fakes["redis"].fail = True  # nếu có đụng tới Redis thì sẽ ra 503
    assert client.get(f"/api/v1/admin/trace/{service.known}", headers={"X-Admin-Token": "x"}).status_code == 404


def test_staging_caddyfile_denies_through_a_handle_block_that_runs_first():
    """`respond` rời xếp sau `handle` trong thứ tự directive của Caddy: allowlist IP sẽ không bao giờ có tác dụng."""
    text = (REPO_ROOT / "infra" / "Caddyfile.staging").read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
    deny = code.index("handle @denied {")
    assert deny < code.index("handle /api/*") and deny < code.rindex("handle {")
    assert "respond @denied" not in code
    assert "basic_auth {" in code  # mật khẩu vẫn bắt buộc; Caddy xếp basic_auth trước mọi handle, bất kể thứ tự viết
