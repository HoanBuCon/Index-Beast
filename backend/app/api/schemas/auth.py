"""Hợp đồng đăng nhập cho web (TV4): trạng thái phiên, danh sách hội thoại của tôi, nhận hội thoại khách.

Phụ trách: TV1 · [S4] Auth service (ADR-005)
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AuthUserOut(BaseModel):
    id: UUID
    display_name: str | None = None
    is_admin: bool


class AuthMe(BaseModel):
    authenticated: bool
    user: AuthUserOut | None = None


class MyConversation(BaseModel):
    id: UUID
    title: str = Field(description="Câu hỏi đầu tiên của hội thoại, cắt còn 60 ký tự.")
    created_at: datetime


class ClaimRequest(BaseModel):
    conversation_id: UUID
    conversation_token: str = Field(min_length=32, max_length=128, repr=False)
