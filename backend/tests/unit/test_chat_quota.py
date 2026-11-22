"""Hạn mức câu hỏi và ngân sách token theo ngày (giờ Việt Nam), sau sự cố bị dội câu hỏi thật 22/11/2026.

Khách: 5 câu/ngày theo IP. Tài khoản đăng nhập: 30 câu/ngày. Admin (AUTH_ADMIN_DISCORD_IDS): không giới hạn.
Mỗi nhóm có ngân sách token riêng; thêm một trần token chung cho cả hệ thống (bot cũng tính).

Phụ trách: TV1 · [S5] Hạn mức hỏi đáp
"""

from collections.abc import Iterator
from contextlib import aclosing
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import optional_user
from app.api.schemas.chat import ChatRequest
from app.main import create_app
from app.services.auth import AuthUser
from app.services.mock_chat import MockChatService
from app.services.quota import ChatQuota, seconds_until_reset
from core.config import Settings
from tests.conftest import FakeRedis
from tests.unit.test_live_chat import FakeLLM, FakeRetriever, rag_tokens, service

TOKEN = "bot-secret-for-tests"
WEB = {"message": "Ranni là ai?", "channel": "web"}
BOT = {"message": "Ranni là ai?", "channel": "discord", "external_ref": "discord:thread:1"}
USER = AuthUser(id=uuid4(), display_name="Tarnished", is_admin=False)
ADMIN = AuthUser(id=uuid4(), display_name="Admin", is_admin=True)


def quota_settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "chat_mode": "rag",
        "api_service_token": TOKEN,
        "rate_limit_per_minute": 1000,  # chỉ kiểm hạn mức ngày
        "chat_guest_daily_questions": 2,
        "chat_user_daily_questions": 3,
        **overrides,
    }
    return Settings(_env_file=None, **values)


@pytest.fixture
def app_client(ctx, fakes) -> Iterator[tuple[TestClient, FakeRedis]]:
    ctx.settings = quota_settings()
    with TestClient(create_app(ctx.settings, context=ctx)) as client:
        client.app.state.chat_service = MockChatService()  # chỉ kiểm hạn mức, không gọi LLM
        yield client, fakes["redis"]


def as_user(client: TestClient, user: AuthUser | None) -> None:
    client.app.dependency_overrides[optional_user] = lambda: user


def ask(client: TestClient, body=WEB, **kwargs) -> int:
    return client.post("/api/v1/chat", json=body, **kwargs).status_code


def test_guest_gets_a_few_questions_a_day_then_a_login_hint(app_client):
    client, _ = app_client

    codes = [ask(client) for _ in range(2)]
    blocked = client.post("/api/v1/chat/stream", json=WEB)

    assert codes == [200, 200]
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "quota_exceeded"
    assert "Đăng nhập" in blocked.json()["message"]
    assert 0 < int(blocked.headers["Retry-After"]) <= 86400


def test_signed_in_user_has_a_larger_daily_quota(app_client):
    client, _ = app_client
    as_user(client, USER)

    codes = [ask(client) for _ in range(4)]

    assert codes == [200, 200, 200, 429]


def test_admin_is_never_limited(app_client):
    client, _ = app_client
    client.app.state.ctx.settings.rate_limit_per_minute = 1
    as_user(client, ADMIN)

    assert {ask(client) for _ in range(6)} == {200}  # cả giới hạn mỗi phút lẫn hạn mức ngày


def test_users_and_guests_are_counted_separately(app_client):
    client, _ = app_client
    as_user(client, USER)
    assert [ask(client) for _ in range(3)] == [200, 200, 200]

    as_user(client, None)
    assert ask(client) == 200  # khách cùng IP vẫn còn lượt của khách


async def test_token_budget_blocks_before_the_question_cap(app_client):
    client, redis = app_client
    settings = client.app.state.ctx.settings
    settings.chat_user_daily_tokens = 1000
    as_user(client, USER)
    quota = ChatQuota(redis, settings)

    assert ask(client) == 200
    await quota.charge(f"user:{USER.id}", 1000)
    res = client.post("/api/v1/chat", json=WEB)

    assert res.status_code == 429
    assert res.json()["code"] == "quota_exceeded"


async def test_global_budget_stops_everyone_but_admins(app_client):
    client, redis = app_client
    settings = client.app.state.ctx.settings
    settings.chat_daily_token_budget = 500
    await ChatQuota(redis, settings).charge("guest:203.0.113.7", 500)

    as_user(client, USER)
    user = client.post("/api/v1/chat", json=WEB)
    bot = ask(client, BOT, headers={"X-Service-Token": TOKEN})
    as_user(client, ADMIN)
    admin = ask(client)

    assert (user.status_code, user.json()["code"]) == (429, "quota_exceeded")
    assert bot == 429
    assert admin == 200


def test_bot_has_no_daily_question_cap(app_client):
    client, _ = app_client
    headers = {"X-Service-Token": TOKEN}

    codes = {ask(client, {**BOT, "external_ref": f"discord:thread:{n}"}, headers=headers) for n in range(4)}

    assert codes == {200}  # bot vẫn có giới hạn mỗi phút theo thread/guild và trần token chung


def test_zero_turns_a_limit_off(ctx):
    ctx.settings = quota_settings(chat_guest_daily_questions=0)
    with TestClient(create_app(ctx.settings, context=ctx)) as client:
        client.app.state.chat_service = MockChatService()
        assert {ask(client) for _ in range(5)} == {200}


def test_redis_down_refuses_paid_questions(app_client):
    client, redis = app_client
    redis.fail = True

    assert ask(client) == 503


def test_mock_mode_has_no_quota(client):
    assert {ask(client) for _ in range(8)} == {200}


def test_reset_is_midnight_in_vietnam():
    from datetime import UTC, datetime

    assert seconds_until_reset(datetime(2026, 11, 22, 16, 59, 0, tzinfo=UTC)) == 60  # 23:59 giờ VN
    assert seconds_until_reset(datetime(2026, 11, 22, 17, 0, 0, tzinfo=UTC)) == 86400


async def test_live_service_reports_token_usage_for_the_attached_quota_key():
    charged: list[tuple[str, int]] = []

    async def sink(key: str, tokens: int) -> None:
        charged.append((key, tokens))

    chat = service(llm=FakeLLM(), retriever=FakeRetriever())
    chat.usage_sink = sink

    await chat.answer(ChatRequest(**WEB).attach_quota("guest:203.0.113.7"))
    await chat.answer(ChatRequest(**WEB))  # admin: không có khóa, không tính

    assert len(charged) == 1
    assert charged[0][0] == "guest:203.0.113.7" and charged[0][1] > 0


async def test_stream_path_charges_usage_too():
    charged: list[tuple[str, int]] = []

    async def sink(key: str, tokens: int) -> None:
        charged.append((key, tokens))

    chat = service(llm=FakeLLM(tokens=rag_tokens()), retriever=FakeRetriever())
    chat.usage_sink = sink

    events = await chat.open_stream(ChatRequest(**WEB).attach_quota("user:42"))
    async with aclosing(events) as stream:
        names = [name async for name, _ in stream]

    assert "done" in names
    assert len(charged) == 1 and charged[0][0] == "user:42" and charged[0][1] > 0


async def test_failing_usage_sink_never_fails_the_answer():
    async def sink(key: str, tokens: int) -> None:
        raise RuntimeError("redis down")

    chat = service(llm=FakeLLM(), retriever=FakeRetriever())
    chat.usage_sink = sink

    response = await chat.answer(ChatRequest(**WEB).attach_quota("guest:203.0.113.7"))

    assert response.answer
