"""Người dùng và phiên đăng nhập (ADR-005): băm Discord ID, tạo và tra phiên, nhận hội thoại, kiểm đường dẫn `next`.

Không đọc cookie hay gọi Discord ở đây (việc của routes và adapter) để dễ kiểm thử.

Phụ trách: TV1 · [S4] Auth service
"""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from core.config import Settings
from core.db import repositories as repo
from core.db.models import AuthSession, Conversation, User
from core.errors import BadRequestError, NotFoundError, UnauthorizedError, UnavailableError

SESSION_COOKIE = "ib_session"
OAUTH_COOKIE = "ib_oauth"
OAUTH_STATE_TTL_SECONDS = 600
TITLE_CHARS = 60


@dataclass(frozen=True)
class AuthUser:
    id: UUID
    display_name: str | None
    is_admin: bool


def provider_hash(settings: Settings, discord_id: str) -> str:
    """HMAC-SHA256 theo AUTH_SECRET: nhận ra người dùng quay lại mà không lưu Discord ID thô."""
    secret = settings.auth_secret.get_secret_value().strip().encode()
    return hmac.new(secret, f"discord:{discord_id}".encode(), hashlib.sha256).hexdigest()


def admin_hashes(settings: Settings) -> frozenset[str]:
    if not settings.auth_enabled:
        return frozenset()
    return frozenset(provider_hash(settings, i) for i in settings.auth_admin_discord_ids)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def safe_next(value: str | None) -> str:
    """Chỉ nhận đường dẫn tương đối trong cùng trang; mọi thứ khác về "/" (chống chuyển hướng mở)."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or any(ord(c) < 32 for c in value):
        return "/"
    return value[:200]


def title_of(question: str | None) -> str:
    text = " ".join((question or "").split())
    return text[:TITLE_CHARS] if text else "(chưa có câu hỏi)"


async def upsert_user(sessionmaker, settings: Settings, discord_id: str, display_name: str | None) -> AuthUser:
    digest = provider_hash(settings, discord_id)
    now = datetime.now(UTC)
    statement = (
        insert(User)
        .values(provider="discord", provider_user_hash=digest, display_name=display_name, last_login_at=now)
        .on_conflict_do_update(
            constraint="uq_users_provider_provider_user_hash",
            set_={"display_name": display_name, "last_login_at": now},
        )
        .returning(User.id)
    )
    try:
        async with sessionmaker() as session, session.begin():
            user_id = (await session.execute(statement)).scalar_one()
    except SQLAlchemyError:
        raise UnavailableError("Không lưu được tài khoản.") from None
    return AuthUser(user_id, display_name, digest in admin_hashes(settings))


async def create_session(sessionmaker, user_id: UUID, days: int) -> str:
    """Trả token thô cho cookie; DB chỉ giữ SHA-256. Dọn luôn mọi phiên đã hết hạn (dùng chỉ mục expires_at)."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    try:
        async with sessionmaker() as session, session.begin():
            await session.execute(delete(AuthSession).where(AuthSession.expires_at < now))
            session.add(
                AuthSession(user_id=user_id, token_hash=hash_token(token), expires_at=now + timedelta(days=days))
            )
    except SQLAlchemyError:
        raise UnavailableError("Không tạo được phiên đăng nhập.") from None
    return token


async def user_for_token(sessionmaker, settings: Settings, token: str | None) -> AuthUser | None:
    """Người dùng của phiên còn hạn; None nếu không có cookie, sai token hoặc hết hạn."""
    if not token or len(token) > 200:
        return None
    query = (
        select(User.id, User.display_name, User.provider_user_hash)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(AuthSession.token_hash == hash_token(token), AuthSession.expires_at > datetime.now(UTC))
    )
    async with sessionmaker() as session:
        row = (await session.execute(query)).first()
    if row is None:
        return None
    return AuthUser(row.id, row.display_name, row.provider_user_hash in admin_hashes(settings))


async def end_session(sessionmaker, token: str | None) -> None:
    if not token:
        return
    try:
        async with sessionmaker() as session, session.begin():
            await session.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    except SQLAlchemyError:
        raise UnavailableError("Không đăng xuất được.") from None


async def list_conversations(sessionmaker, user_id: UUID, limit: int = 50) -> list[tuple[UUID, str, datetime]]:
    """Hội thoại của người dùng, mới nhất trước: (id, câu hỏi đầu, giờ tạo)."""
    try:
        async with sessionmaker() as session:
            rows = await repo.conversations_of_user(session, user_id, limit)
    except SQLAlchemyError:
        raise UnavailableError("Không đọc được danh sách hội thoại.") from None
    return [(i, title_of(q), at) for i, q, at in rows]


async def claim_conversation(sessionmaker, user_id: UUID, conversation_id: UUID, token_hash: str) -> None:
    """Gắn hội thoại khách cho người dùng. Cần token của hội thoại (`token_hash` = băm của conversation_token).

    Chỉ nhận hội thoại web chưa có chủ hoặc đã là của chính người này; của người khác trả 404 như không tồn tại.
    """
    try:
        async with sessionmaker() as session, session.begin():
            conv = await session.get(Conversation, conversation_id, with_for_update=True)
            if conv is None or conv.channel != "web":
                raise NotFoundError("Không tìm thấy hội thoại.")
            if not hmac.compare_digest(token_hash, conv.client_user_ref or ""):
                raise UnauthorizedError("Cần token của hội thoại này.")
            if conv.user_id is not None and conv.user_id != user_id:
                raise NotFoundError("Không tìm thấy hội thoại.")
            await session.execute(update(Conversation).where(Conversation.id == conv.id).values(user_id=user_id))
    except SQLAlchemyError:
        raise UnavailableError("Không nhận được hội thoại.") from None


def require_state(cookie_state: str | None, query_state: str | None) -> str:
    """`state` trong query phải trùng cookie đã đặt lúc bắt đầu đăng nhập (chống đăng nhập giả mạo)."""
    if not cookie_state or not query_state or not hmac.compare_digest(cookie_state, query_state):
        raise BadRequestError("Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng thử lại.")
    return query_state
