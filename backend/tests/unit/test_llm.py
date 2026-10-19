"""Kiểm tra adapter qua HTTP transport giả, không gọi provider hay đọc .env thật.

Phụ trách: TV3 · [S1] Xác nhận DeepSeek
"""

import json
from contextlib import aclosing, asynccontextmanager

import httpx
import pytest
from openai import AsyncOpenAI

from app.adapters.llm import DeepSeekLLM, LLMConfigurationError, LLMError
from app.context import build_context
from core.config import Settings

MESSAGES = [{"role": "user", "content": "Who is Godrick?"}]


def completion(content="Hello", reason="stop"):
    return {
        "id": "test",
        "object": "chat.completion",
        "created": 0,
        "model": "deepseek-flash",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": reason}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


@asynccontextmanager
async def fake_llm(handler):
    settings = Settings(_env_file=None, llm_model="test-model")
    async with AsyncOpenAI(
        api_key="fake-key",
        base_url="https://api.deepseek.com",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    ) as client:
        yield DeepSeekLLM(settings, client=client)


async def test_complete_sends_deepseek_parameters_and_exposes_usage():
    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/chat/completions"
        assert request.headers["authorization"] == "Bearer fake-key"
        assert body["model"] == "test-model"
        assert body["thinking"] == {"type": "disabled"}
        assert body["max_tokens"] == 128
        assert body["temperature"] == 0
        assert body["messages"] == MESSAGES
        assert body["stream"] is False
        return httpx.Response(200, json=completion())

    async with fake_llm(handler) as llm:
        result = await llm.complete(MESSAGES, max_tokens=128, temperature=0)
    assert result.content == "Hello"
    assert (result.prompt_tokens, result.completion_tokens) == (10, 5)


async def test_json_mode_adds_instruction_without_mutating_messages():
    messages = list(MESSAGES)

    def handler(request):
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert "JSON" in body["messages"][0]["content"]
        return httpx.Response(200, json=completion('{"query_en":"Godrick"}'))

    async with fake_llm(handler) as llm:
        assert await llm.complete_json(messages) == {"query_en": "Godrick"}
    assert messages == MESSAGES


async def test_thinking_mode_omits_temperature_and_preserves_provider_reasoning():
    def handler(request):
        body = json.loads(request.content)
        assert body["thinking"] == {"type": "enabled"}
        assert body["reasoning_effort"] == "low"
        assert "temperature" not in body
        result = completion("Final answer")
        result["choices"][0]["message"]["reasoning_content"] = "Provider reasoning"
        result["usage"]["completion_tokens_details"] = {"reasoning_tokens": 3}
        return httpx.Response(200, json=result)

    async with fake_llm(handler) as llm:
        result = await llm.complete(MESSAGES, thinking=True, reasoning_effort="low")
    assert result.content == "Final answer"
    assert result.reasoning_content == "Provider reasoning"
    assert result.reasoning_tokens == 3


@pytest.mark.parametrize("content", ["not-json", "[]", '"string"', "null"])
async def test_invalid_json_is_rejected(content):
    async with fake_llm(lambda _: httpx.Response(200, json=completion(content))) as llm:
        with pytest.raises(LLMError, match="JSON"):
            await llm.complete_json(MESSAGES)


@pytest.mark.parametrize("content,reason", [("", "stop"), (None, "stop"), ("half", "length")])
async def test_empty_or_truncated_completion_is_not_success(content, reason):
    async with fake_llm(lambda _: httpx.Response(200, json=completion(content, reason))) as llm:
        with pytest.raises(LLMError):
            await llm.complete(MESSAGES)


@pytest.mark.parametrize("status", [401, 402, 429, 500])
async def test_provider_errors_are_sanitized(status):
    def handler(_):
        return httpx.Response(status, json={"error": {"message": "fake-key private-prompt"}})

    async with fake_llm(handler) as llm:
        with pytest.raises(LLMError) as caught:
            await llm.complete(MESSAGES)
    assert str(status) in str(caught.value)
    assert "fake-key" not in str(caught.value)
    assert "private-prompt" not in str(caught.value)


class SSEBody(httpx.AsyncByteStream):
    def __init__(self, *, reason="stop", fail=False):
        self.reason = reason
        self.fail = fail
        self.closed = False

    async def __aiter__(self):
        for delta, reason in [
            ({"role": "assistant", "reasoning_content": "private reasoning"}, None),
            ({"content": "Xin "}, None),
            ({"content": "chào"}, None),
            ({}, self.reason),
        ]:
            yield (
                "data: "
                + json.dumps(
                    {
                        "id": "test",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": "deepseek-flash",
                        "choices": [{"index": 0, "delta": delta, "finish_reason": reason}],
                    }
                )
                + "\n\n"
            ).encode()
            if self.fail and "content" in delta:
                raise httpx.ReadError("sensitive provider payload")
        yield b"data: [DONE]\n\n"

    async def aclose(self):
        self.closed = True


async def test_stream_yields_only_answer_and_closes_http_response():
    body = SSEBody()

    def handler(request):
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)

    async with fake_llm(handler) as llm:
        assert "".join([part async for part in llm.stream(MESSAGES)]) == "Xin chào"
    assert body.closed


async def test_stream_can_be_closed_when_consumer_stops_early():
    body = SSEBody()
    async with fake_llm(lambda _: httpx.Response(200, stream=body)) as llm:
        async with aclosing(llm.stream(MESSAGES)) as stream:
            assert await anext(stream) == "Xin "
        assert body.closed


@pytest.mark.parametrize("reason", [None, "length"])
async def test_incomplete_stream_raises_after_partial_text(reason):
    body = SSEBody(reason=reason)
    parts = []
    async with fake_llm(lambda _: httpx.Response(200, stream=body)) as llm:
        with pytest.raises(LLMError):
            async for part in llm.stream(MESSAGES):
                parts.append(part)
    assert parts == ["Xin ", "chào"]
    assert body.closed


async def test_midstream_network_failure_is_sanitized_and_closed():
    body = SSEBody(fail=True)
    parts = []
    async with fake_llm(
        lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)
    ) as llm:
        with pytest.raises(LLMError, match="stream failed") as caught:
            async for _ in llm.stream(MESSAGES):
                parts.append(_)
    assert parts == ["Xin "]
    assert "sensitive" not in str(caught.value)
    assert body.closed


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key_fails_before_any_network_call(key):
    with pytest.raises(LLMConfigurationError, match="DEEPSEEK_API_KEY"):
        DeepSeekLLM(Settings(_env_file=None, deepseek_api_key=key))


async def test_settings_load_key_from_env_file_and_hide_it(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=secret-from-file\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.deepseek_api_key.get_secret_value() == "secret-from-file"
    assert "secret-from-file" not in repr(settings)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-from-env")
    assert Settings(_env_file=env_file).deepseek_api_key.get_secret_value() == "secret-from-env"


async def test_owned_client_closes_on_exit_and_injected_client_stays_open():
    async with DeepSeekLLM(Settings(_env_file=None, deepseek_api_key="fake")) as llm:
        client = llm._client
    assert client.is_closed()
    async with fake_llm(lambda _: httpx.Response(200, json=completion())) as llm:
        await llm.aclose()
        assert not llm._client.is_closed()


async def test_context_registers_llm_for_shutdown_but_not_paid_health_probes():
    ctx = build_context(Settings(_env_file=None, deepseek_api_key="fake"))
    assert ctx.llm is not None
    assert "llm" not in ctx.health_checks
    client = ctx.llm._client
    await ctx.aclose()
    assert client.is_closed()
