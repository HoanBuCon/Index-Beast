"""Dependency FastAPI: lấy AppContext, xác định caller (service token / IP), kiểm tra admin token, rate-limit.

S1 chỉ có get_ctx; xác thực và rate-limit thêm ở S4.

Phụ trách: TV1 · [S1] Skeleton FastAPI · [S4] Xác thực client, CORS, bảo vệ admin
"""

from fastapi import Request

from app.context import AppContext
from app.services.mock_chat import MockChatService


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def get_chat_service(request: Request) -> MockChatService:
    return request.app.state.chat_service
