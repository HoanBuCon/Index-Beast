"""Hợp đồng API v1: /chat, /chat/stream, /feedback, /conversations và định dạng lỗi chuẩn.

Phụ trách: TV1 · [S2] API contract v1
"""

import json
from uuid import uuid4

BODY = {"message": "Ranni là ai?", "channel": "web"}


def parse_sse(text: str) -> list[tuple[str, dict]]:
    frames = []
    for block in text.strip().split("\n\n"):
        event, data = block.split("\n")
        frames.append((event.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return frames


def test_chat_returns_answer_with_sources(client):
    res = client.post("/api/v1/chat", json=BODY)

    assert res.status_code == 200
    data = res.json()
    assert data["grounded"] is True
    assert [s["index"] for s in data["sources"]] == [1, 2]
    assert data["answer"]


def test_chat_continues_conversation_and_history_lists_messages(client):
    first = client.post("/api/v1/chat", json=BODY).json()
    client.post("/api/v1/chat", json={**BODY, "conversation_id": first["conversation_id"]})

    history = client.get(f"/api/v1/conversations/{first['conversation_id']}").json()

    assert [m["role"] for m in history["messages"]] == ["user", "assistant", "user", "assistant"]
    assert history["channel"] == "web"


def test_stream_event_order_and_payloads(client):
    res = client.post("/api/v1/chat/stream", json=BODY)

    assert res.headers["content-type"].startswith("text/event-stream")
    frames = parse_sse(res.text)
    names = [name for name, _ in frames]
    assert names[0] == "status"
    assert names[-2:] == ["sources", "done"]
    assert set(names[1:-2]) == {"token"}
    done = frames[-1][1]
    assert set(done) == {"conversation_id", "message_id", "grounded", "latency_ms"}
    assert "".join(d["token"] for n, d in frames if n == "token").strip().startswith("Đây là")


def test_ungrounded_has_no_sources(client):
    data = client.post("/api/v1/chat", json={**BODY, "message": "/mock-ungrounded"}).json()

    assert data["grounded"] is False
    assert data["sources"] == []


def test_feedback_accepts_known_message_and_rejects_unknown(client):
    message_id = client.post("/api/v1/chat", json=BODY).json()["message_id"]

    ok = client.post("/api/v1/feedback", json={"message_id": message_id, "rating": 1, "reason": "đúng"})
    unknown = client.post("/api/v1/feedback", json={"message_id": str(uuid4()), "rating": -1})

    assert ok.status_code == 204
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "not_found"


def test_errors_use_standard_body_with_request_id(client):
    res = client.get(f"/api/v1/conversations/{uuid4()}", headers={"X-Request-ID": "web-123"})

    assert res.status_code == 404
    assert res.json() == {"code": "not_found", "message": "Không tìm thấy hội thoại.", "request_id": "web-123"}
    assert res.headers["X-Request-ID"] == "web-123"


def test_validation_error_does_not_echo_input(client):
    res = client.post("/api/v1/chat", json={"message": "x" * 5000, "channel": "web"})

    body = res.json()
    assert res.status_code == 422
    assert body["code"] == "validation_error"
    assert "xxxx" not in res.text
    assert body["request_id"] == res.headers["X-Request-ID"]


def test_rate_limited_sets_retry_after(client):
    res = client.post("/api/v1/chat", json={**BODY, "message": "/mock-429"})

    assert res.status_code == 429
    assert res.headers["Retry-After"] == "5"
    assert res.json()["code"] == "rate_limited"


def test_unknown_route_uses_standard_404(client):
    res = client.get("/api/v1/nope")

    assert res.status_code == 404
    assert set(res.json()) == {"code", "message", "request_id"}


def test_unhandled_exception_returns_json_500_with_request_id(settings, ctx):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(settings, context=ctx)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret detail")

    with TestClient(app, raise_server_exceptions=False) as c:
        res = c.get("/boom", headers={"X-Request-ID": "abc"})

    assert res.status_code == 500
    assert res.json() == {
        "code": "internal_error",
        "message": "Đã xảy ra lỗi. Vui lòng thử lại sau.",
        "request_id": "abc",
    }
    assert "secret detail" not in res.text
