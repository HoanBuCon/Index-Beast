"""Middleware HTTP dùng chung. Thêm middleware mới: viết ở đây rồi gắn trong install_middleware().

Phụ trách: TV1 · [S1] Skeleton FastAPI
"""

import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from core.config import Settings
from core.logging import request_id_var

log = logging.getLogger("app.http")
REQUEST_ID_HEADER = "X-Request-ID"
QUIET_PATHS = ("/api/v1/health",)  # Docker gọi mỗi 15 giây: chỉ log khi không trả 200


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Gắn request id (nhận từ web/bot hoặc tự sinh) vào log và header trả về; log thời gian xử lý."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        start = time.perf_counter()
        data: dict[str, object] = {"method": request.method, "path": request.url.path}
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = rid
            data |= {"status": response.status_code, "ms": round((time.perf_counter() - start) * 1000, 1)}
            if not (request.url.path in QUIET_PATHS and response.status_code == 200):
                log.info("request", extra={"data": data})
            return response
        except Exception:
            log.exception("unhandled error", extra={"data": data})
            raise
        finally:
            request_id_var.reset(token)


def install_middleware(app: FastAPI, settings: Settings) -> None:
    # Thứ tự: middleware thêm sau bọc ngoài cùng → RequestContext chạy trước CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)
