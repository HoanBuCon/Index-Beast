"""Kiểm tra API thử LLM bằng client giả, không tiêu hao credits.

Phụ trách: TV3 (MinhMuc) · [S1] Xác nhận DeepSeek
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.adapters.llm import LLMError, LLMResponse
from app.main import create_app
from core.config import Settings

PATH = "/api/v1/dev/llm/test"


@pytest.mark.parametrize("thinking", [False, True])
def test_api_returns_answer_usage_and_passes_thinking_mode(client, ctx, thinking):
    ctx.llm = AsyncMock()
    ctx.llm.complete.return_value = LLMResponse(
        content="Xin chào",
        model="deepseek-flash",
        prompt_tokens=10,
        completion_tokens=20,
        finish_reason="stop",
        reasoning_content="Provider reasoning" if thinking else None,
        reasoning_tokens=12 if thinking else 0,
    )
    response = client.post(PATH, json={"message": "Hello", "thinking": thinking, "reasoning_effort": "high"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Xin chào"
    assert body["thinking"] is thinking
    assert body["reasoning_effort"] == ("high" if thinking else None)
    assert body["usage"]["total_tokens"] == 30
    assert body["usage"]["reasoning_tokens"] == (12 if thinking else 0)
    assert body["latency_ms"] >= 0
    assert ctx.llm.complete.call_args.kwargs["thinking"] is thinking
    assert ctx.llm.complete.call_args.kwargs["reasoning_effort"] == "high"


def test_no_configured_key_returns_503(client):
    response = client.post(PATH, json={"message": "Hello"})
    assert response.status_code == 503
    assert "DEEPSEEK_API_KEY" in response.json()["message"]


def test_provider_error_returns_502(client, ctx):
    ctx.llm = AsyncMock()
    ctx.llm.complete.side_effect = LLMError("DeepSeek request failed (AuthenticationError, status=401).")
    response = client.post(PATH, json={"message": "Hello"})
    assert response.status_code == 502
    assert "401" in response.json()["message"]


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "  "},
        {"message": "x" * 8001},
        {"message": "Hello", "max_tokens": 0},
        {"message": "Hello", "max_tokens": 8193},
        {"message": "Hello", "reasoning_effort": "unsupported"},
        {"message": "Hello", "api_key": "should-not-be-accepted"},
    ],
)
def test_invalid_inputs_do_not_call_provider(client, ctx, payload):
    ctx.llm = AsyncMock()
    assert client.post(PATH, json=payload).status_code == 422
    ctx.llm.complete.assert_not_called()


def test_debug_endpoint_is_visible_in_dev_swagger(client):
    schema = client.get("/api/openapi.json").json()
    assert PATH in schema["paths"]


def test_debug_endpoint_is_absent_in_production(ctx):
    settings = Settings(_env_file=None, environment="prod", postgres_password="safe-test-value")
    app = create_app(settings, context=ctx)
    with TestClient(app) as client:
        assert client.post(PATH, json={"message": "Hello"}).status_code == 404
    assert PATH not in app.openapi()["paths"]
