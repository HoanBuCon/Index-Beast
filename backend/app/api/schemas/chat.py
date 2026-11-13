"""ChatRequest, ChatResponse, Source và các event SSE của /chat/stream.

Hợp đồng v1: web và bot (TV4) viết type tay theo file này / openapi.json. Chỉ thêm trường tùy chọn;
đổi tên hay xóa trường là thay đổi phá vỡ, cần CHANGE-REQ.

Phụ trách: TV1 · [S2] API contract v1
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, PrivateAttr, StringConstraints

MAX_MESSAGE_CHARS = 2000


class ChatOptions(BaseModel):
    spoilers: bool = True
    lang: Literal["auto", "vi", "en"] = "auto"
    web_search: Literal["off", "auto", "always"] | None = None


class ChatRequest(BaseModel):
    conversation_id: UUID | None = Field(None, description="Bỏ trống để tạo hội thoại mới.")
    conversation_token: str | None = Field(default=None, min_length=32, max_length=128, repr=False)
    turn_id: UUID | None = None
    # strip trước khi kiểm tra độ dài: câu hỏi toàn khoảng trắng bị từ chối, không tới LLM
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)]
    channel: Literal["web", "discord"]
    external_ref: Annotated[str, Field(max_length=128)] | None = Field(
        None, description="Khóa kênh của client, vd. discord:thread:<id>. Không chứa thông tin định danh thô."
    )
    options: ChatOptions = ChatOptions()
    clarification_id: UUID | None = Field(None, description="ID câu hỏi đang chờ; client cũ có thể trả lời bằng text.")
    # Người dùng đăng nhập do server gắn từ cookie phiên (ADR-005); không có trong JSON/OpenAPI, client không giả được
    _user_id: UUID | None = PrivateAttr(default=None)

    @property
    def user_id(self) -> UUID | None:
        return self._user_id

    def attach_user(self, user_id: UUID | None) -> "ChatRequest":
        self._user_id = user_id
        return self


class ClarificationField(BaseModel):
    key: str
    label: str
    input_type: Literal["text", "number", "choice"] = "text"
    options: list[str] = Field(default_factory=list, max_length=10)


class Clarification(BaseModel):
    id: UUID
    status: Literal["pending"] = "pending"
    question: str
    fields: list[ClarificationField] = Field(min_length=1, max_length=2)
    expires_at: str


class ChatImage(BaseModel):
    association: Literal["exact_section", "entity_page", "web_result"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    id: str = Field(pattern=r"^[0-9a-f]{64}$")
    url: str
    caption: str | None = None
    alt: str | None = None
    source_url: str
    source_indices: list[int] = Field(min_length=1, max_length=5)
    attribution: str | None = None
    license: str | None = None
    license_status: str | None = None
    file_page_url: str | None = None
    game_scope: str | None = None
    release_scope: str | None = None


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
    images: list[ChatImage] = Field(default_factory=list, max_length=3)
    clarification: Clarification | None = None
    conversation_token: str | None = Field(default=None, repr=False, exclude_if=lambda value: value is None)


class DoneEvent(BaseModel):
    conversation_id: UUID
    message_id: UUID
    grounded: bool
    latency_ms: float
    conversation_token: str | None = Field(default=None, repr=False, exclude_if=lambda value: value is None)


class StatusEvent(BaseModel):
    status: str


class TokenEvent(BaseModel):
    token: str


class SourcesEvent(BaseModel):
    sources: list[Source]
    images: list[ChatImage] = Field(default_factory=list, max_length=3)
    clarification: Clarification | None = None


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
