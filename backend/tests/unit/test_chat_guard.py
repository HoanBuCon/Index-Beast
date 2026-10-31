"""Bảo vệ /chat khi gọi LLM thật: service token, rate-limit Redis, hạn thời gian; hội thoại bot theo external_ref.

Phụ trách: TV1 · [S2] Sửa phát hiện code review #1–#3
"""

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.schemas.chat import ChatRequest
from app.main import create_app
from app.services.mock_chat import MockChatService
from core.config import Settings
from core.errors import TimeoutAppError
from tests.conftest import FakeRedis
from tests.unit.test_live_chat import FakeLLM, service

TOKEN = "bot-secret-for-tests"
BODY = {"message": "Ranni là ai?", "channel": "web"}
BOT = {"message": "Ranni là ai?", "channel": "discord", "external_ref": "discord:thread:1"}


@pytest.fixture
def guarded(ctx, fakes) -> Iterator[tuple[TestClient, FakeRedis]]:
    redis = fakes["redis"]
    ctx.settings = Settings(
        _env_file=None, environment="test", chat_mode="llm_only", api_service_token=TOKEN, rate_limit_per_minute=2
    )
    with TestClient(create_app(ctx.settings, context=ctx)) as client:
        client.app.state.chat_service = MockChatService()  # chỉ kiểm guard, không gọi LLM
        yield client, redis


def test_web_requests_are_limited_per_ip(guarded):
    client, _ = guarded

    codes = [client.post("/api/v1/chat", json=BODY).status_code for _ in range(3)]
    limited = client.post("/api/v1/chat/stream", json=BODY)

    assert codes == [200, 200, 429]
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) in range(1, 61)


def test_discord_channel_requires_service_token(guarded):
    client, _ = guarded

    missing = client.post("/api/v1/chat", json=BOT)
    wrong = client.post("/api/v1/chat", json=BOT, headers={"X-Service-Token": "guess"})

    assert missing.status_code == wrong.status_code == 401
    assert missing.json()["code"] == "unauthorized"


def test_bot_is_limited_per_external_ref_not_shared_ip(guarded):
    client, _ = guarded
    headers = {"X-Service-Token": TOKEN}

    first_thread = [client.post("/api/v1/chat", json=BOT, headers=headers).status_code for _ in range(3)]
    other_thread = client.post("/api/v1/chat", json={**BOT, "external_ref": "discord:thread:2"}, headers=headers)

    assert first_thread == [200, 200, 429]
    assert other_thread.status_code == 200  # cùng IP của bot nhưng thread khác: không bị chặn chung


def test_redis_down_rejects_instead_of_unlimited(guarded):
    client, redis = guarded
    redis.fail = True

    res = client.post("/api/v1/chat", json=BODY)

    assert res.status_code == 503


def test_mock_mode_skips_guard(client):
    codes = {client.post("/api/v1/chat", json=BOT).status_code for _ in range(15)}

    assert codes == {200}  # mock không tốn tiền: không cần token, không giới hạn


async def test_same_external_ref_reuses_conversation_and_history():
    llm = FakeLLM()
    chat = service(llm=llm)
    ask = ChatRequest(**BOT)

    first = await chat.answer(ask)
    second = await chat.answer(ChatRequest(**{**BOT, "message": "Cô ấy ở đâu?"}))
    other = await chat.answer(ChatRequest(**{**BOT, "external_ref": "discord:thread:2"}))

    assert second.conversation_id == first.conversation_id
    assert other.conversation_id != first.conversation_id
    assert any("Ranni is an Empyrean" in str(m.get("content", "")) for m in llm.seen[1])  # có lịch sử lượt trước


async def test_mock_service_also_reuses_by_external_ref():
    chat = MockChatService()

    first = await chat.answer(ChatRequest(**BOT))
    second = await chat.answer(ChatRequest(**BOT))

    assert first.conversation_id == second.conversation_id


async def test_slow_llm_hits_deadline_and_releases_conversation():
    llm = FakeLLM()

    async def slow(messages, **kwargs):
        await asyncio.sleep(5)

    llm.complete = slow
    chat = service(llm=llm, chat_timeout_seconds=0.05)

    with pytest.raises(TimeoutAppError):
        await chat.answer(ChatRequest(**BODY))
    assert all(not s.lock.locked() for s in chat._conversations.values())
