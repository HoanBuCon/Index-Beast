"""Đăng ký exception handler: mọi lỗi trả JSON {code, message, request_id}.

Phụ trách: TV1 · [S2] Xử lý lỗi & logging chuẩn
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.errors import AppError, BadRequestError, NotFoundError, RateLimitedError, UnauthorizedError
from core.logging import request_id_var

log = logging.getLogger("app.errors")

_HTTP_ERRORS: dict[int, type[AppError]] = {
    400: BadRequestError,
    401: UnauthorizedError,
    404: NotFoundError,
    429: RateLimitedError,
}


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


def error_response(status_code: int, code: str, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
    body = ErrorBody(code=code, message=message, request_id=request_id_var.get())
    return JSONResponse(body.model_dump(), status_code=status_code, headers=headers)


async def _app_error(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        log.error("app error", extra={"data": {"code": exc.code, "path": request.url.path}}, exc_info=exc)
    return error_response(exc.status_code, exc.code, exc.message, exc.headers)


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Chỉ trả vị trí + loại lỗi, không echo giá trị người dùng gửi lên
    fields = [".".join(str(p) for p in e["loc"] if p != "body") for e in exc.errors()]
    log.info("validation error", extra={"data": {"path": request.url.path, "fields": fields}})
    return error_response(422, "validation_error", "Dữ liệu gửi lên không hợp lệ: " + ", ".join(fields or ["body"]))


async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    known = _HTTP_ERRORS.get(exc.status_code)
    code = known.code if known else f"http_{exc.status_code}"
    message = known.message if known else "Yêu cầu không thể xử lý."
    return error_response(exc.status_code, code, message, dict(exc.headers or {}))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
