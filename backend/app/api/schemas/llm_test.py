"""Schema cho API thử DeepSeek tại môi trường dev/test.

Phụ trách: TV3 (MinhMuc) · [S1] Xác nhận DeepSeek
"""

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.llm import ReasoningEffort


class LLMTestIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(
        default="Godrick the Grafted là ai? Trả lời ngắn bằng tiếng Việt.", min_length=1, max_length=8000
    )
    thinking: bool = False
    reasoning_effort: ReasoningEffort = "low"
    max_tokens: int = Field(default=2048, ge=1, le=8192)
    temperature: float = Field(default=0.2, ge=0, le=2)


class LLMTestUsage(BaseModel):
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    reasoning_tokens: int | None


class LLMTestOut(BaseModel):
    model: str
    thinking: bool
    reasoning_effort: ReasoningEffort | None
    answer: str
    reasoning_content: str | None
    finish_reason: str
    latency_ms: float
    usage: LLMTestUsage
