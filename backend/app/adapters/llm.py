"""Async DeepSeek Platform adapter: text, JSON và streaming, mặc định tắt thinking cho RAG.

Phụ trách: TV3 · [S1] Xác nhận DeepSeek · [S3] Generation và query rewriting
"""

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from openai import APIError, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam

from core.config import Settings, get_settings

ReasoningEffort = Literal["low", "high", "max"]


class LLMError(RuntimeError):
    """Lỗi provider/output đã bỏ thông tin nhạy cảm, để service/API xử lý."""


class LLMConfigurationError(LLMError):
    """Chưa cấu hình API key."""


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str
    reasoning_content: str | None = None
    reasoning_tokens: int | None = None


class DeepSeekLLM:
    """Một instance mỗi application lifespan. Client truyền vào do caller sở hữu.

    Không kết nối mạng lúc khởi tạo; SDK retry có giới hạn. Không retry lại stream
    khi đã trả một phần nội dung để tránh ghép trùng câu trả lời.
    """

    def __init__(self, settings: Settings | None = None, *, client: AsyncOpenAI | None = None) -> None:
        self.settings = settings or get_settings()
        self._owns_client = client is None
        if client is None:
            secret = self.settings.deepseek_api_key
            key = secret.get_secret_value().strip() if secret else ""
            if not key:
                raise LLMConfigurationError("Set DEEPSEEK_API_KEY in the repository .env or environment.")
            client = AsyncOpenAI(
                api_key=key,
                base_url=self.settings.deepseek_base_url,
                timeout=self.settings.llm_timeout_seconds,
                max_retries=self.settings.llm_max_retries,
            )
        self._client = client

    def _parameters(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        max_tokens: int | None,
        temperature: float | None,
        thinking: bool = False,
        reasoning_effort: ReasoningEffort = "low",
    ) -> dict[str, Any]:
        if not messages:
            raise ValueError("messages must not be empty")
        token_limit = self.settings.llm_max_tokens if max_tokens is None else max_tokens
        sampling = self.settings.llm_temperature if temperature is None else temperature
        if not 1 <= token_limit <= 8192:
            raise ValueError("max_tokens must be between 1 and 8192")
        if not 0 <= sampling <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if reasoning_effort not in ("low", "high", "max"):
            raise ValueError("reasoning_effort must be low, high or max")
        parameters = {
            "model": self.settings.llm_model,
            "messages": list(messages),
            "max_tokens": token_limit,
            "extra_body": {"thinking": {"type": "enabled" if thinking else "disabled"}},
        }
        if thinking:
            parameters["reasoning_effort"] = reasoning_effort
        else:
            # Thinking mode không hỗ trợ temperature theo tài liệu DeepSeek.
            parameters["temperature"] = sampling
        return parameters

    @staticmethod
    def _response(completion: ChatCompletion) -> LLMResponse:
        if not completion.choices:
            raise LLMError("DeepSeek returned no choices.")
        choice = completion.choices[0]
        if choice.finish_reason != "stop":
            raise LLMError(f"DeepSeek did not finish the answer (finish_reason={choice.finish_reason}).")
        content = choice.message.content
        if not content or not content.strip():
            raise LLMError("DeepSeek returned empty content.")
        usage = completion.usage
        token_details = usage.completion_tokens_details if usage else None
        return LLMResponse(
            content=content,
            model=completion.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            finish_reason=choice.finish_reason,
            reasoning_content=getattr(choice.message, "reasoning_content", None) or None,
            reasoning_tokens=token_details.reasoning_tokens if token_details else None,
        )

    async def _complete(self, parameters: dict[str, Any]) -> LLMResponse:
        try:
            response = await self._client.chat.completions.create(**parameters, stream=False)
        except (APIError, httpx.HTTPError) as exc:
            # Không lộ provider body, headers hoặc nội dung người dùng vào log/API.
            status = getattr(exc, "status_code", None)
            raise LLMError(f"DeepSeek request failed ({type(exc).__name__}, status={status}).") from None
        return self._response(response)

    async def complete(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        thinking: bool = False,
        reasoning_effort: ReasoningEffort = "low",
    ) -> LLMResponse:
        """Trả lời đầy đủ, kèm token usage để service ghi trace/chi phí."""
        return await self._complete(self._parameters(messages, max_tokens, temperature, thinking, reasoning_effort))

    async def complete_json(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """JSON object cho query rewrite. Caller kiểm tra schema nghiệp vụ."""
        parameters = self._parameters(messages, max_tokens, temperature)
        parameters["messages"] = [
            {"role": "system", "content": 'Return only a valid JSON object, for example {"answer": "text"}.'},
            *parameters["messages"],
        ]
        parameters["response_format"] = {"type": "json_object"}
        response = await self._complete(parameters)
        try:
            result = json.loads(response.content)
        except (ValueError, RecursionError):
            raise LLMError("DeepSeek returned invalid JSON.") from None
        if not isinstance(result, dict):
            raise LLMError("DeepSeek JSON output must be an object.")
        return result

    async def stream(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Yield text, không forward reasoning. Caller dùng contextlib.aclosing.

        LLMError sau một phần output nghĩa là câu trả lời chưa hoàn tất. Khi dừng
        giữa chừng, caller phải đóng iterator để giải phóng kết nối HTTP.
        """
        parameters = self._parameters(messages, max_tokens, temperature)
        stream = None
        has_content = False
        finished = False
        try:
            stream = await self._client.chat.completions.create(**parameters, stream=True)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.delta.content:
                    has_content = has_content or bool(choice.delta.content.strip())
                    yield choice.delta.content
                if choice.finish_reason is not None:
                    if choice.finish_reason != "stop":
                        raise LLMError(f"DeepSeek stream incomplete (finish_reason={choice.finish_reason}).")
                    finished = True
            if not finished or not has_content:
                raise LLMError("DeepSeek stream ended without a complete answer.")
        except (APIError, httpx.HTTPError) as exc:
            status = getattr(exc, "status_code", None)
            raise LLMError(f"DeepSeek stream failed ({type(exc).__name__}, status={status}).") from None
        finally:
            if stream is not None:
                await stream.close()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.close()

    async def __aenter__(self) -> "DeepSeekLLM":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
