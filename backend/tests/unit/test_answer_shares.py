"""TV4 · API share: tài nguyên giả, không mạng/LLM; không mở cả hội thoại cho share token."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.answer_shares import SHARE_TTL_SECONDS, share_key
from core.config import Settings

TOKEN = "test-share-service-only"
AUTH = {"X-Service-Token": TOKEN}


class ShareRedis:
    def __init__(self):
        self.values = {}
        self.writes = []
        self.fail = False

    async def set(self, key, value, *, ex, nx):
        if self.fail:
            raise ConnectionError("PRIVATE_REDIS_DETAILS")
        self.writes.append((key, ex, nx))
        self.values[key] = value
        return True

    async def get(self, key):
        if self.fail:
            raise ConnectionError("PRIVATE_REDIS_DETAILS")
        return self.values.get(key)


@pytest.fixture
def share_client(ctx):
    ctx.settings = Settings(_env_file=None, environment="test", api_service_token=TOKEN)
    redis = ShareRedis()
    ctx.redis = redis
    with TestClient(create_app(ctx.settings, context=ctx)) as client:
        yield client, redis


def answer(client, question="First question", channel="discord"):
    return client.post(
        "/api/v1/chat", json={"message": question, "channel": channel, "external_ref": "discord:thread:test-share"}
    ).json()


def create(client, reply, headers=AUTH):
    return client.post(
        "/api/v1/answer-shares",
        headers=headers,
        json={"conversation_id": reply["conversation_id"], "message_id": reply["message_id"]},
    )


def test_only_service_can_create_even_in_mock(share_client):
    client, redis = share_client
    reply = answer(client)
    for headers in ({}, {"X-Service-Token": "wrong"}, {"X-Admin-Token": TOKEN}):
        assert create(client, reply, headers).status_code == 401
    assert not redis.writes
    assert create(client, reply).status_code == 201


def test_snapshot_is_one_answer_without_history_ids_or_credentials(share_client):
    client, redis = share_client
    first = answer(client)
    second = answer(client, "PRIVATE OTHER QUESTION")
    made = create(client, first)
    token = made.json()["token"]
    assert len(token) == 43
    assert made.headers["Cache-Control"] == "no-store"
    shared = client.get("/api/v1/answer-shares", headers={"X-Answer-Share-Token": token})
    assert shared.status_code == 200
    assert set(shared.json()) == {"question", "answer", "sources", "grounded", "expires_at"}
    assert shared.json()["question"] == "First question"
    assert shared.json()["answer"] == first["answer"]
    assert shared.json()["sources"] == first["sources"]
    assert "PRIVATE OTHER QUESTION" not in shared.text
    assert TOKEN not in shared.text and token not in str(redis.values)
    assert redis.writes[0] == (share_key(token), SHARE_TTL_SECONDS, True)
    assert shared.headers["Cache-Control"] == "no-store"
    assert shared.headers["Referrer-Policy"] == "no-referrer"
    client.get("/api/v1/answer-shares", headers={"X-Answer-Share-Token": token})
    assert len(redis.writes) == 1  # đọc không gia hạn TTL
    assert create(client, second).json()["token"] != token


def test_missing_wrong_and_expired_capabilities_fail_closed(share_client):
    client, redis = share_client
    token = create(client, answer(client)).json()["token"]
    for headers in ({}, {"X-Answer-Share-Token": "bad"}, {"X-Answer-Share-Token": "z" * 43}):
        assert client.get("/api/v1/answer-shares", headers=headers).status_code == 404
    # Query token không được chấp nhận/không dùng làm cơ chế chia sẻ.
    assert client.get("/api/v1/answer-shares", params={"token": token}).status_code == 404
    key = share_key(token)
    saved = json.loads(redis.values[key])
    saved["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    redis.values[key] = json.dumps(saved)
    assert client.get("/api/v1/answer-shares", headers={"X-Answer-Share-Token": token}).status_code == 404
    redis.values.clear()
    assert client.get("/api/v1/answer-shares", headers={"X-Answer-Share-Token": token}).status_code == 404


def test_targets_must_be_assistant_messages_in_the_selected_discord_conversation(share_client):
    client, _ = share_client
    reply = answer(client)
    unknown = {**reply, "message_id": str(uuid4())}
    assert create(client, unknown).status_code == 404
    history = client.get(f"/api/v1/conversations/{reply['conversation_id']}").json()
    user = {**reply, "message_id": history["messages"][0]["id"]}
    assert create(client, user).status_code == 404
    assert create(client, {**reply, "conversation_id": str(uuid4())}).status_code == 404
    assert create(client, answer(client, channel="web")).status_code == 400


def test_redis_failure_and_corrupt_snapshot_do_not_expose_internal_data(share_client):
    client, redis = share_client
    reply = answer(client)
    token = create(client, reply).json()["token"]
    redis.values[share_key(token)] = "bad JSON"
    assert client.get("/api/v1/answer-shares", headers={"X-Answer-Share-Token": token}).status_code == 503
    redis.fail = True
    for response in [
        create(client, reply),
        client.get("/api/v1/answer-shares", headers={"X-Answer-Share-Token": token}),
    ]:
        assert response.status_code == 503
        assert "PRIVATE_REDIS_DETAILS" not in response.text


def test_hanging_redis_has_a_bounded_read_and_write(share_client, monkeypatch):
    client, redis = share_client
    monkeypatch.setattr("app.services.answer_shares.SHARE_IO_TIMEOUT_SECONDS", 0.01)
    reply = answer(client)
    token = create(client, reply).json()["token"]

    async def hang(*args, **kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(redis, "get", hang)
    monkeypatch.setattr(redis, "set", hang)
    assert create(client, reply).status_code == 503
    assert client.get("/api/v1/answer-shares", headers={"X-Answer-Share-Token": token}).status_code == 503
