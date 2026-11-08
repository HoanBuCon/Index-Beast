"""Dependency FastAPI: lấy AppContext, xác định caller (service token / IP), kiểm tra admin token, rate-limit.

get_ctx, get_session; xác thực và rate-limit thêm ở S4.

Phụ trách: TV1 · [S1] Skeleton FastAPI · [S4] Xác thực client, CORS, bảo vệ admin
"""

import hmac
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import AppContext
from app.services.chat import ChatService
from core.errors import NotFoundError, UnauthorizedError


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


async def get_session(ctx: AppContext = Depends(get_ctx)) -> AsyncIterator[AsyncSession]:
    """Một transaction cho mỗi request: commit khi handler xong, rollback khi có exception. Dùng qua SessionDep."""
    async with ctx.sessionmaker() as session, session.begin():
        yield session


# scope="function": commit chạy TRƯỚC khi gửi response. Mặc định của FastAPI (scope="request") chạy sau, nên
# commit lỗi vẫn trả 200 cho client trong khi dữ liệu không được lưu. Route stream (SSE) cần session riêng
# trong generator vì session này đã đóng khi stream bắt đầu.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


ADMIN_TOKEN_HEADER = "X-Admin-Token"


def require_admin(request: Request) -> None:
    """Chưa cấu hình ADMIN_TOKEN thì /admin/* trả 404 như chưa tồn tại; sai token trả 401."""
    settings = request.app.state.ctx.settings
    if not settings.admin_enabled:
        raise NotFoundError("Không tìm thấy tài nguyên.")
    sent = request.headers.get(ADMIN_TOKEN_HEADER, "")
    if not hmac.compare_digest(sent.encode(), settings.admin_token.get_secret_value().strip().encode()):
        raise UnauthorizedError("Token quản trị không hợp lệ.")
