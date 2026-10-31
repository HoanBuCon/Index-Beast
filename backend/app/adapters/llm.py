"""DeepSeek adapter backed by ChatDeepSeek; one model per lifespan, no paid calls on construction.

Phụ trách: TV3 · [S2–S3] LangChain migration
"""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import aclosing, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.runnables import Runnable
from langchain_deepseek import ChatDeepSeek
from langsmith import tracing_context
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from core.config import Settings, get_settings

ReasoningEffort = Literal["low", "high", "max"]
_PROVIDER_STREAMS: ContextVar[list | None] = ContextVar("indexbeast_provider_streams", default=None)


def track_provider_stream(stream):
    """Register the real provider iterator for deterministic close through nested LCEL streams."""
    streams = _PROVIDER_STREAMS.get()
    if streams is not None:
        streams.append(stream)
    return stream


class ManagedChatDeepSeek(ChatDeepSeek):
    async def _astream(self, *args, **kwargs):
        stream = track_provider_stream(super()._astream(*args, **kwargs))
        async with aclosing(stream):
            async for chunk in stream:
                yield chunk


class LLMError(RuntimeError):
    """Provider/output error without request bodies, credentials or private reasoning."""

    def __init__(self, message, *, reason="llm_error", finish_reason=None, prompt_tokens=None, completion_tokens=None):
        super().__init__(message)
        reasons = {
            "llm_error",
            "incomplete_output",
            "empty_output",
            "missing_finish_reason",
            "unsupported_content_type",
            "provider_request_failed",
            "provider_stream_failed",
            "invalid_json",
        }
        known = {"stop", "length", "content_filter", "tool_calls", "function_call"}
        self.diagnostics = {
            "reason": reason if isinstance(reason, str) and reason in reasons else "llm_error",
            "finish_reason": finish_reason
            if finish_reason is None or (isinstance(finish_reason, str) and finish_reason in known)
            else "unknown",
        }
        for key, value in (("prompt_tokens", prompt_tokens), ("completion_tokens", completion_tokens)):
            if type(value) is int and value >= 0:
                self.diagnostics[key] = value


class LLMConfigurationError(LLMError):
    """Missing or invalid model configuration."""


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    finish_reason: str
    reasoning_content: str | None = None
    reasoning_tokens: int | None = None


class DeepSeekLLM:
    def __init__(
        self, settings: Settings | None = None, *, client: AsyncOpenAI | None = None, model: BaseChatModel | None = None
    ):
        self.settings = settings or get_settings()
        self._owns_client = client is None and model is None
        self._sync_http = None
        if model is not None:
            self.model = model
            self._client = None
            return
        secret = self.settings.deepseek_api_key
        key = secret.get_secret_value().strip() if secret else ""
        # Injected SDK transport is retained for offline wire-contract tests. ChatDeepSeek
        # still owns the inference path; the adapter never calls SDK completions directly.
        if client is not None:
            key = client.api_key
        if not key:
            raise LLMConfigurationError("Set DEEPSEEK_API_KEY in the repository .env or environment.")
        self._sync_http = httpx.Client()
        params = dict(
            model=self.settings.llm_model,
            api_key=key,
            api_base=self.settings.deepseek_base_url,
            timeout=self.settings.llm_timeout_seconds,
            max_retries=self.settings.llm_max_retries,
            temperature=None,
            http_client=self._sync_http,
            use_responses_api=False,
            stream_usage=True,
            verbose=False,
        )
        if client is not None:
            params.update(root_async_client=client, async_client=client.chat.completions)
        try:
            self.model = ManagedChatDeepSeek(**params)
        except Exception:
            self._sync_http.close()
            raise LLMConfigurationError("Invalid DeepSeek configuration.") from None
        self._client = self.model.root_async_client

    def bind_model(
        self,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        thinking: bool = False,
        reasoning_effort: ReasoningEffort = "low",
        json_output: bool = False,
    ) -> Runnable:
        limit = self.settings.llm_max_tokens if max_tokens is None else max_tokens
        sampling = self.settings.llm_temperature if temperature is None else temperature
        if not 1 <= limit <= 8192 or not 0 <= sampling <= 2:
            raise ValueError("Invalid max_tokens or temperature")
        if reasoning_effort not in ("low", "high", "max"):
            raise ValueError("reasoning_effort must be low, high or max")
        params: dict[str, Any] = {
            "max_tokens": limit,
            "extra_body": {"thinking": {"type": "enabled" if thinking else "disabled"}},
        }
        if thinking:
            params["reasoning_effort"] = reasoning_effort
        else:
            params["temperature"] = sampling
        if json_output:
            # JSON mode, NOT tool calling/JSON schema: preserve provider compatibility.
            params["response_format"] = {"type": "json_object"}
        return self.model.bind(**params)

    def response(self, message: AIMessage) -> LLMResponse:
        metadata = message.response_metadata
        reason = metadata.get("finish_reason")
        raw = metadata.get("token_usage")
        if isinstance(raw, dict) and raw:
            prompt_tokens, completion_tokens = raw.get("prompt_tokens"), raw.get("completion_tokens")
            reasoning = (raw.get("completion_tokens_details") or {}).get("reasoning_tokens")
        else:
            usage = message.usage_metadata or {}
            prompt_tokens, completion_tokens = usage.get("input_tokens"), usage.get("output_tokens")
            reasoning = (usage.get("output_token_details") or {}).get("reasoning")
        if reason != "stop" or not isinstance(message.content, str) or not message.content.strip():
            failure = "incomplete_output" if reason != "stop" else "empty_output"
            if reason is None:
                failure = "missing_finish_reason"
            elif not isinstance(message.content, str):
                failure = "unsupported_content_type"
            raise LLMError(
                "DeepSeek returned empty or incomplete output.",
                reason=failure,
                finish_reason=reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        return LLMResponse(
            content=message.content,
            model=metadata.get("model_name") or self.settings.llm_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=reason,
            reasoning_content=message.additional_kwargs.get("reasoning_content"),
            reasoning_tokens=reasoning,
        )

    async def invoke_chain(self, chain: Runnable, inputs: Any) -> LLMResponse:
        try:
            # Tracing is deliberately disabled; a server env var must not silently export
            # prompts/corpus to LangSmith. An explicit tracing feature is a separate task.
            with tracing_context(enabled=False):
                message = await chain.ainvoke(inputs)
            return self.response(message)
        except LLMError:
            raise
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            raise LLMError(
                f"DeepSeek request failed ({type(exc).__name__}, status={status}).", reason="provider_request_failed"
            ) from None

    async def stream_chain(self, chain: Runnable, inputs: Any) -> AsyncIterator[str]:
        # One producer owns every LCEL context and provider iterator for the whole run.
        # Consumers can prime in a route task and resume in an SSE task safely.
        queue = asyncio.Queue(maxsize=1)
        stopping = asyncio.Event()

        async def produce():
            streams = []
            token = _PROVIDER_STREAMS.set(streams)
            error = None
            try:
                with tracing_context(enabled=False):
                    try:
                        async with aclosing(chain.astream(inputs)) as stream:
                            async for message in stream:
                                if stopping.is_set():
                                    break
                                await queue.put(message)
                    finally:
                        for provider in reversed(streams):
                            await provider.aclose()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = exc
            finally:
                _PROVIDER_STREAMS.reset(token)
            if not stopping.is_set():
                await queue.put(error)

        producer = asyncio.create_task(produce())
        has_content, finished = False, False
        try:
            while True:
                message = await queue.get()
                if message is None:
                    break
                if isinstance(message, Exception):
                    raise message
                if not isinstance(message, AIMessageChunk):
                    raise LLMError("Unexpected model stream output.")
                reason = message.response_metadata.get("finish_reason")
                if reason is not None:
                    if reason != "stop":
                        raise LLMError("DeepSeek stream incomplete.", reason="incomplete_output", finish_reason=reason)
                    finished = True
                if isinstance(message.content, str) and message.content:
                    has_content = has_content or bool(message.content.strip())
                    yield message.content
            if not has_content or not finished:
                raise LLMError(
                    "DeepSeek stream ended without a complete answer.",
                    reason="empty_output" if not has_content else "missing_finish_reason",
                )
        except LLMError:
            raise
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            raise LLMError(
                f"DeepSeek stream failed ({type(exc).__name__}, status={status}).", reason="provider_stream_failed"
            ) from None
        finally:
            stopping.set()
            # A nested provider may consume cancellation while unwinding. Unblock the
            # bounded queue too, so its next iteration sees the explicit stop signal.
            with suppress(asyncio.QueueEmpty):
                queue.get_nowait()
            producer.cancel()
            with suppress(asyncio.CancelledError):
                await producer

    async def complete(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        thinking: bool = False,
        reasoning_effort: ReasoningEffort = "low",
    ) -> LLMResponse:
        if not messages:
            raise ValueError("messages must not be empty")
        chain = self.bind_model(
            max_tokens=max_tokens, temperature=temperature, thinking=thinking, reasoning_effort=reasoning_effort
        )
        return await self.invoke_chain(chain, list(messages))

    async def complete_json(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        chain = self.bind_model(max_tokens=max_tokens, temperature=temperature, json_output=True)
        result = await self.invoke_chain(
            chain,
            [
                {"role": "system", "content": 'Return only a valid JSON object, for example {"answer":"text"}.'},
                *messages,
            ],
        )
        return self.json_object(result.content)

    @staticmethod
    def json_object(content: str) -> dict:
        try:
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (ValueError, RecursionError):
            raise LLMError("DeepSeek returned invalid JSON.", reason="invalid_json") from None

    async def stream(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        json_output: bool = False,
    ) -> AsyncIterator[str]:
        chain = self.bind_model(max_tokens=max_tokens, temperature=temperature, json_output=json_output)
        async with aclosing(self.stream_chain(chain, list(messages))) as stream:
            async for token in stream:
                yield token

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.close()
        if self._sync_http is not None:
            self._sync_http.close()

    async def __aenter__(self) -> "DeepSeekLLM":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
