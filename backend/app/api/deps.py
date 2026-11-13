"""Dependency FastAPI: lấy AppContext, xác định caller (service token / IP), kiểm tra admin token, rate-limit.

get_ctx, get_session; xác thực và rate-limit thêm ở S4.

Phụ trách: TV1 · [S1] Skeleton FastAPI · [S4] Xác thực client, CORS, bảo vệ admin
"""

import hmac
import logging
from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.discord_oauth import DiscordOAuth
from app.api.guard import ensure_admin_not_blocked, record_admin_failure
from app.context import AppContext
from app.services import auth
from app.services.auth import SESSION_COOKIE, AuthUser
from app.services.chat import ChatService
from core.errors import ForbiddenError, NotFoundError, UnauthorizedError

log = logging.getLogger(__name__)


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


async def optional_user(request: Request) -> AuthUser | None:
    """Người dùng của cookie phiên (ADR-005), hoặc None cho khách. Lỗi DB coi như khách để chat vẫn chạy."""
    ctx = request.app.state.ctx
    token = request.cookies.get(SESSION_COOKIE)
    if not token or ctx.sessionmaker is None or not ctx.settings.auth_enabled:
        return None
    try:
        return await auth.user_for_token(ctx.sessionmaker, ctx.settings, token)
    except SQLAlchemyError:
        log.warning("session lookup failed", exc_info=True)
        return None


async def require_user(user: AuthUser | None = Depends(optional_user)) -> AuthUser:
    if user is None:
        raise UnauthorizedError("Cần đăng nhập.")
    return user


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def require_same_origin(request: Request) -> None:
    """Lệnh ghi dùng cookie chỉ nhận từ trang web của mình. Không có Origin (curl, bot, cùng origin) thì cho qua:
    cookie SameSite=Lax đã chặn gửi chéo trang."""
    origin = request.headers.get("origin")
    if origin is None:
        return
    settings = request.app.state.ctx.settings
    allowed = {o.rstrip("/") for o in settings.cors_origins} | {origin_of(settings.web_url)}
    if origin.rstrip("/") not in allowed:
        raise ForbiddenError()


def get_discord_oauth(request: Request) -> DiscordOAuth:
    return DiscordOAuth(request.app.state.ctx.settings)


async def require_admin(request: Request) -> None:
    """Quản trị viên đăng nhập (AUTH_ADMIN_DISCORD_IDS) vào thẳng; không thì cần X-Admin-Token. Chưa đặt ADMIN_TOKEN
    thì /admin/* trả 404 như chưa tồn tại; sai token trả 401 và bị đếm theo IP, quá `rate_limit_per_minute` lần sai
    trong một phút thì trả 429 (chống dò token)."""
    settings = request.app.state.ctx.settings
    user = await optional_user(request)
    if user is not None and user.is_admin:
        return
    if not settings.admin_enabled:
        raise NotFoundError("Không tìm thấy tài nguyên.")
    await ensure_admin_not_blocked(request)
    sent = request.headers.get(ADMIN_TOKEN_HEADER, "")
    if not hmac.compare_digest(sent.encode(), settings.admin_token.get_secret_value().strip().encode()):
        await record_admin_failure(request)
        raise UnauthorizedError("Token quản trị không hợp lệ.")
