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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.config import Settings
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

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, rid)
            await send(message)

        data: dict[str, object] = {"method": scope["method"], "path": scope["path"]}
        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            log.exception("unhandled error", extra={"data": data})
            raise
        else:
            if not (scope["path"] in self.quiet_paths and status == 200):
                data |= {"status": status, "ms": round((time.perf_counter() - start) * 1000, 1)}
                log.info("request", extra={"data": data})
        finally:
            request_id_var.reset(token)


def install_middleware(app: FastAPI, settings: Settings, *, quiet_paths: Iterable[str] = ()) -> None:
    # Middleware thêm sau nằm ngoài cùng → RequestContext bọc cả CORS, nên mọi response đều có request id
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware, quiet_paths=quiet_paths)
