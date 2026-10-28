"""ChatRequest, ChatResponse, Source và các event SSE của /chat/stream.

Hợp đồng v1: web và bot (TV4) viết type tay theo file này / openapi.json. Chỉ thêm trường tùy chọn;
đổi tên hay xóa trường là thay đổi phá vỡ, cần CHANGE-REQ.

Phụ trách: TV1 · [S2] API contract v1
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

MAX_MESSAGE_CHARS = 2000


class ChatOptions(BaseModel):
    spoilers: bool = True
    lang: Literal["auto", "vi", "en"] = "auto"


class ChatRequest(BaseModel):
    conversation_id: UUID | None = Field(None, description="Bỏ trống để tạo hội thoại mới.")
    # strip trước khi kiểm tra độ dài: câu hỏi toàn khoảng trắng bị từ chối, không tới LLM
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)]
    channel: Literal["web", "discord"]
    external_ref: Annotated[str, Field(max_length=128)] | None = Field(
        None, description="Khóa kênh của client, vd. discord:thread:<id>. Không chứa thông tin định danh thô."
    )
    options: ChatOptions = ChatOptions()


class Source(BaseModel):
    index: Annotated[int, Field(ge=1, description="Số trích dẫn [n] trong câu trả lời.")]
    title: str
    section: str | None = None
    url: str
    text: str | None = Field(None, description="Đoạn trích ngắn từ nguồn.")
    origin: Literal["corpus", "web"] = "corpus"


class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    answer: str
    sources: list[Source]
    grounded: bool = Field(description="False khi không đủ bằng chứng; khi đó sources rỗng.")
    latency_ms: float


class DoneEvent(BaseModel):
    conversation_id: UUID
    message_id: UUID
    grounded: bool
    latency_ms: float


class StatusEvent(BaseModel):
    status: str


class TokenEvent(BaseModel):
    token: str


class SourcesEvent(BaseModel):
    sources: list[Source]


class ErrorEvent(BaseModel):
    code: str
    message: str
    request_id: str


SSE_EVENT_MODELS: dict[str, type[BaseModel]] = {
    "status": StatusEvent,
    "token": TokenEvent,
    "sources": SourcesEvent,
    "done": DoneEvent,
    "error": ErrorEvent,
}
