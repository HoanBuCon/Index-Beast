"""Trace RAG của một câu trả lời, cho trang admin và CLI.

Phụ trách: TV1 · [S3] Trace từng bước RAG
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TraceOut(BaseModel):
    message_id: UUID
    conversation_id: UUID | None = None
    created_at: datetime | None = None
    grounded: bool | None = None
    rewritten_query: str | None = None
    latency_ms: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    trace: dict[str, Any] | None = Field(default=None, description="Dấu vết từng bước RAG, đã che secret.")
    source: str = Field(description="postgres (đã lưu) hoặc memory (chỉ còn trong RAM, mất khi khởi động lại).")
