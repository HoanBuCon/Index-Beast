"""Giới hạn tần suất chung cho /api/* theo IP (chống một máy dội request, sự cố production 22/11/2026).

Phụ trách: TV1 · [S5] Chống DoS
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from core.config import Settings
from tests.conftest import FakeRedis

TOKEN = "bot-secret-for-tests"


@pytest.fixture
def limited(ctx, fakes) -> Iterator[tuple[TestClient, FakeRedis]]:
    ctx.settings = Settings(_env_file=None, environment="test", api_service_token=TOKEN, rate_limit_api_per_minute=3)
    with TestClient(create_app(ctx.settings, context=ctx)) as client:
        yield client, fakes["redis"]


def test_api_requests_over_the_limit_get_429_with_retry_after(limited):
    client, _ = limited

    codes = [client.get("/api/v1/chat/capabilities").status_code for _ in range(3)]
    blocked = client.get("/api/v1/answer-shares", params={"id": "x"})

    assert codes == [200, 200, 200]
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"
    assert int(blocked.headers["Retry-After"]) in range(1, 61)
    assert blocked.headers["X-Request-ID"]  # vẫn qua RequestContext: có request id và được log


def test_unknown_paths_count_too(limited):
    client, _ = limited

    codes = [client.get("/api/v1/images/" + "a" * 64).status_code for _ in range(4)]

    assert codes[-1] == 429


def test_health_and_bot_are_not_limited(limited):
    client, _ = limited
    bot = {"X-Service-Token": TOKEN}

    health = [client.get("/api/v1/health").status_code for _ in range(5)]
    bot_codes = [client.get("/api/v1/chat/capabilities", headers=bot).status_code for _ in range(5)]

    assert 429 not in health
    assert bot_codes == [200] * 5


def test_wrong_service_token_is_limited_like_anyone(limited):
    client, _ = limited
    guess = {"X-Service-Token": "guess"}

    codes = [client.get("/api/v1/chat/capabilities", headers=guess).status_code for _ in range(4)]

    assert codes[-1] == 429


def test_redis_down_lets_requests_through(limited):
    # Giới hạn chung chỉ chống dội request: Redis lỗi thì mở (giới hạn /chat tốn tiền LLM vẫn đóng, trả 503)
    client, redis = limited
    redis.fail = True

    assert client.get("/api/v1/chat/capabilities").status_code == 200


def test_zero_disables_the_limit(ctx):
    ctx.settings = Settings(_env_file=None, environment="test", rate_limit_api_per_minute=0)
    with TestClient(create_app(ctx.settings, context=ctx)) as client:
        codes = {client.get("/api/v1/chat/capabilities").status_code for _ in range(5)}

    assert codes == {200}
