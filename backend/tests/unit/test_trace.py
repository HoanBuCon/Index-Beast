"""Trace RAG: che secret, giới hạn cỡ, đếm token; endpoint admin và việc trace chỉ còn trong RAM khi không có DB.

Phụ trách: TV1 · [S3] Trace từng bước RAG
"""

import json
from contextlib import ExitStack
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.deps import get_chat_service
from app.context import AppContext, register_infra
from app.main import create_app
from app.rag.trace import MAX_TRACE_BYTES, public_trace, token_usage
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
