"""TV4 · S3: chia sẻ một câu trả lời; người dùng cho phép bổ sung API giới hạn này."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas.chat import Source


class AnswerShareRequest(BaseModel):
    conversation_id: UUID
    message_id: UUID


class AnswerShareCreated(BaseModel):
    token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    expires_at: datetime


class SharedAnswer(BaseModel):
    question: str = Field(max_length=2000)
    answer: str = Field(min_length=1, max_length=100_000)
    sources: list[Source] = Field(max_length=100)
    grounded: bool
    expires_at: datetime
