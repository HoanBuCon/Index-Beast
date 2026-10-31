"""Lịch sử một hội thoại (GET /conversations/{id}).

Phụ trách: TV1 · [S2] API contract v1
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas.chat import ChatImage, Source


class MessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    sources: list[Source] = []
    images: list[ChatImage] = Field(default_factory=list, max_length=3)
    grounded: bool | None = None
    created_at: datetime


class ConversationOut(BaseModel):
    id: UUID
    channel: Literal["web", "discord"]
    created_at: datetime
    messages: list[MessageOut]
