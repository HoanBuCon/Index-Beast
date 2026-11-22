"""Middleware HTTP dùng chung. Thêm middleware mới: viết ở đây rồi gắn trong install_middleware().

Viết dạng ASGI thuần (không dùng BaseHTTPMiddleware) để request id còn hiệu lực trong suốt lúc stream
body — cần cho SSE /chat/stream ở S3.

Phụ trách: TV1 · [S1] Skeleton FastAPI
"""

import logging
import re
import time
import uuid
from collections.abc import Iterable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api import guard
from app.api.errors import error_response
from core.config import Settings
from core.errors import AppError, RateLimitedError
from core.logging import request_id_var

log = logging.getLogger("app.http")

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")  # id từ client chỉ được nhận khi an toàn để ghi log


def _request_id(scope: Scope) -> str:
    incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
    return incoming if incoming and _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex[:16]


class RequestContextMiddleware:
    """Gắn request id (nhận từ web/bot hoặc tự sinh) vào log và header trả về; log mỗi request khi kết thúc."""

    def __init__(self, app: ASGIApp, quiet_paths: Iterable[str] = ()) -> None:
        self.app = app
        self.quiet_paths = frozenset(quiet_paths)  # chỉ log khi không trả 200, vd. healthcheck mỗi 15 giây

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = _request_id(scope)
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status = 500
        started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status, started
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, rid)
            await send(message)

        data: dict[str, object] = {"method": scope["method"], "path": scope["path"]}
        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            log.exception("unhandled error", extra={"data": data})
            if started:  # đã trả một phần body (vd. SSE giữa chừng): chỉ còn cách ngắt kết nối
                raise
            # Tự trả JSON 500 tại đây vì ServerErrorMiddleware nằm ngoài, lúc đó request id đã bị reset
            await error_response(500, AppError.code, AppError.message)(scope, receive, send_with_request_id)
            status = 500
            data |= {"status": status, "ms": round((time.perf_counter() - start) * 1000, 1)}
            log.info("request", extra={"data": data})
        else:
            if not (scope["path"] in self.quiet_paths and status == 200):
                data |= {"status": status, "ms": round((time.perf_counter() - start) * 1000, 1)}
                log.info("request", extra={"data": data})
        finally:
            request_id_var.reset(token)


class ApiRateLimitMiddleware:
    """Trần chung `rate_limit_api_per_minute` cho mọi request /api/* theo IP, đếm trong Redis (đúng cho nhiều worker).

    Chặn trước router nên request dội vào đường dẫn không tồn tại hay tài nguyên giả cũng bị tính, và 429 trả ngay
    không chạm PostgreSQL/Qdrant. Bỏ qua: `exempt_paths` (healthcheck) và bot có service token hợp lệ (bot gom request
    của mọi người dùng Discord về một IP; /chat của bot đã có giới hạn riêng theo external_ref và guild).
    Redis lỗi thì cho qua: lớp này chỉ chống dội request, còn /chat tốn tiền LLM vẫn đóng (503) ở app.api.guard.
    """

    def __init__(self, app: ASGIApp, exempt_paths: Iterable[str] = ()) -> None:
        self.app = app
        self.exempt_paths = frozenset(exempt_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/") or scope["path"] in self.exempt_paths:
            await self.app(scope, receive, send)
            return
        ctx = scope["app"].state.ctx
        limit = ctx.settings.rate_limit_api_per_minute
        if limit and not guard.is_trusted_service(Request(scope)):
            client = scope.get("client")
            window = int(time.time()) // guard.WINDOW_SECONDS
            key = f"ratelimit:api:ip:{guard.ip_key(client[0] if client else '-')}:{window}"
            try:
                async with ctx.redis.pipeline(transaction=True) as pipe:
                    count, _ = await pipe.incr(key).expire(key, guard.WINDOW_SECONDS * 2).execute()
            except Exception:  # noqa: BLE001 - Redis lỗi không được làm sập toàn bộ API
                log.warning("api rate limit unavailable")
                count = 0
            if count > limit:
                error = RateLimitedError(retry_after=guard.retry_after())
                await error_response(error.status_code, error.code, error.message, error.headers)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def install_middleware(
    app: FastAPI, settings: Settings, *, quiet_paths: Iterable[str] = (), exempt_paths: Iterable[str] = ()
) -> None:
    # Middleware thêm sau nằm ngoài cùng: RequestContext > CORS > ApiRateLimit. 429 vì thế vẫn có request id, được
    # log, và có header CORS để web đọc được.
    app.add_middleware(ApiRateLimitMiddleware, exempt_paths=exempt_paths)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", REQUEST_ID_HEADER, "X-Conversation-Token"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware, quiet_paths=quiet_paths)
