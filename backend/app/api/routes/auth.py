"""Đăng nhập Discord OAuth2 (ADR-005): /auth/discord/login, /auth/discord/callback, /auth/logout, /auth/me,
và hội thoại của người dùng: /me/conversations, /me/conversations/claim.

Phiên là cookie httpOnly; DB chỉ giữ SHA-256 của token. Chưa cấu hình đăng nhập thì login/callback trả 404.

Phụ trách: TV1 · [S4] Auth service
"""

import json
import secrets

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse

from app.adapters.discord_oauth import DiscordOAuth
from app.api.deps import get_ctx, get_discord_oauth, optional_user, require_same_origin, require_user
from app.api.errors import ErrorBody
from app.api.guard import enforce_login_limit
from app.api.schemas.auth import AuthMe, AuthUserOut, ClaimRequest, MyConversation
from app.context import AppContext
from app.services import auth
from app.services.auth import OAUTH_COOKIE, OAUTH_STATE_TTL_SECONDS, SESSION_COOKIE, AuthUser
from app.services.memory_repository import owner_hash
from core.errors import BadRequestError, NotFoundError, UnavailableError


def no_store(response: Response) -> None:
    """Mọi phản hồi ở đây gắn với một người dùng hoặc đặt cookie: không để proxy hay trình duyệt lưu lại.
    Dependency chỉ phủ phản hồi JSON; route tự trả Response (chuyển hướng, 204) phải qua `_private`."""
    response.headers["Cache-Control"] = "no-store"


def _private(response: Response) -> Response:
    no_store(response)
    return response


router = APIRouter(tags=["auth"], dependencies=[Depends(no_store)])
OAUTH_COOKIE_PATH = "/api/v1/auth"
_ERRORS = {401: {"model": ErrorBody}, 404: {"model": ErrorBody}, 503: {"model": ErrorBody}}


def _state_key(state: str) -> str:
    return f"oauth:state:{auth.hash_token(state)}"


def _require_enabled(ctx: AppContext) -> None:
    if not ctx.settings.auth_enabled:
        raise NotFoundError("Không tìm thấy tài nguyên.")


def _web_url(ctx: AppContext, path: str) -> str:
    return ctx.settings.web_url.rstrip("/") + path


def _me(user: AuthUser | None) -> AuthMe:
    if user is None:
        return AuthMe(authenticated=False)
    return AuthMe(
        authenticated=True, user=AuthUserOut(id=user.id, display_name=user.display_name, is_admin=user.is_admin)
    )


@router.get(
    "/auth/discord/login",
    status_code=status.HTTP_302_FOUND,
    responses={302: {"description": "Chuyển sang Discord để cấp quyền."}, **_ERRORS},
    summary="Bắt đầu đăng nhập bằng Discord",
)
async def discord_login(
    request: Request,
    next: str = "/",
    ctx: AppContext = Depends(get_ctx),
    oauth: DiscordOAuth = Depends(get_discord_oauth),
) -> RedirectResponse:
    _require_enabled(ctx)
    await enforce_login_limit(request)
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    payload = json.dumps({"verifier": verifier, "next": auth.safe_next(next)})
    try:
        await ctx.redis.set(_state_key(state), payload, ex=OAUTH_STATE_TTL_SECONDS)
    except Exception:
        raise UnavailableError("Không bắt đầu được đăng nhập.") from None
    response = _private(
        RedirectResponse(oauth.authorize_url(state, auth.pkce_challenge(verifier)), status.HTTP_302_FOUND)
    )
    response.set_cookie(
        OAUTH_COOKIE,
        state,
        max_age=OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        secure=ctx.settings.auth_cookie_is_secure,
        samesite="lax",
        path=OAUTH_COOKIE_PATH,
    )
    return response


@router.get(
    "/auth/discord/callback",
    status_code=status.HTTP_302_FOUND,
    responses={302: {"description": "Về trang web sau khi đăng nhập."}, 400: {"model": ErrorBody}, **_ERRORS},
    summary="Discord gọi lại sau khi người dùng cấp quyền",
)
async def discord_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    ctx: AppContext = Depends(get_ctx),
    oauth: DiscordOAuth = Depends(get_discord_oauth),
) -> RedirectResponse:
    _require_enabled(ctx)
    cookie_state = request.cookies.get(OAUTH_COOKIE)
    if error:  # người dùng từ chối trên Discord
        response = _private(RedirectResponse(_web_url(ctx, "/?login=denied"), status.HTTP_302_FOUND))
        response.delete_cookie(OAUTH_COOKIE, path=OAUTH_COOKIE_PATH)
        return response
    auth.require_state(cookie_state, state)
    if not code or len(code) > 512:
        raise BadRequestError("Thiếu mã đăng nhập.")
    try:
        stored = await ctx.redis.getdel(_state_key(state))  # dùng một lần: gọi lại cùng state sẽ bị từ chối
    except Exception:
        raise UnavailableError("Không hoàn tất được đăng nhập.") from None
    if not stored:
        raise BadRequestError("Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng thử lại.")
    saved = json.loads(stored)

    access_token = await oauth.exchange(code, saved["verifier"])
    discord_id, display_name = await oauth.fetch_user(access_token)
    user = await auth.upsert_user(ctx.sessionmaker, ctx.settings, discord_id, display_name)
    session_token = await auth.create_session(ctx.sessionmaker, user.id, ctx.settings.auth_session_days)

    response = _private(RedirectResponse(_web_url(ctx, auth.safe_next(saved.get("next"))), status.HTTP_302_FOUND))
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=ctx.settings.auth_session_days * 86400,
        httponly=True,
        secure=ctx.settings.auth_cookie_is_secure,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(OAUTH_COOKIE, path=OAUTH_COOKIE_PATH)
    return response


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_same_origin)],
    responses={403: {"model": ErrorBody}, 503: {"model": ErrorBody}},
    summary="Đăng xuất: xóa phiên",
)
async def logout(request: Request, ctx: AppContext = Depends(get_ctx)) -> Response:
    if ctx.sessionmaker is not None:
        await auth.end_session(ctx.sessionmaker, request.cookies.get(SESSION_COOKIE))
    response = _private(Response(status_code=status.HTTP_204_NO_CONTENT))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get(
    "/auth/me",
    response_model=AuthMe,
    summary="Trạng thái đăng nhập hiện tại; luôn 200, chưa đăng nhập thì authenticated=false",
)
async def me(user: AuthUser | None = Depends(optional_user)) -> AuthMe:
    return _me(user)


@router.get(
    "/me/conversations",
    response_model=list[MyConversation],
    responses={401: {"model": ErrorBody}, 503: {"model": ErrorBody}},
    summary="Hội thoại của tôi, mới nhất trước (tối đa 50)",
)
async def my_conversations(user: AuthUser = Depends(require_user), ctx: AppContext = Depends(get_ctx)):
    rows = await auth.list_conversations(ctx.sessionmaker, user.id)
    return [MyConversation(id=i, title=title, created_at=at) for i, title, at in rows]


@router.post(
    "/me/conversations/claim",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_same_origin)],
    responses={**_ERRORS, 403: {"model": ErrorBody}},
    summary="Nhận hội thoại khách đang có conversation_token về tài khoản của tôi",
)
async def claim_conversation(
    body: ClaimRequest, user: AuthUser = Depends(require_user), ctx: AppContext = Depends(get_ctx)
) -> Response:
    await auth.claim_conversation(ctx.sessionmaker, user.id, body.conversation_id, owner_hash(body.conversation_token))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
