"""POST /chat (JSON, cho bot) và POST /chat/stream (SSE: status, token, sources, done, error; cho web).

CHAT_MODE chọn mock/llm_only/rag qua cùng service contract, giữ nguyên schema/event v1.

Phụ trách: TV1 · [S2] API contract v1 · [S3] Endpoint /chat & /chat/stream thật
"""

import logging
from collections.abc import AsyncIterator
from contextlib import aclosing

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.api.deps import get_chat_service
from app.api.errors import ErrorBody
from app.api.guard import enforce_chat_limits
from app.api.schemas.chat import (
    SSE_EVENT_MODELS,
    ChatRequest,
    ChatResponse,
    ErrorEvent,
)
from app.services.chat import ChatService
from core.errors import AppError
from core.logging import request_id_var

router = APIRouter(tags=["chat"])
log = logging.getLogger(__name__)

_ERROR_RESPONSES = {code: {"model": ErrorBody} for code in (401, 404, 422, 429, 502, 503, 504)}


def _sse(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {SSE_EVENT_MODELS[event].model_validate(payload).model_dump_json()}\n\n"


@router.post("/chat", response_model=ChatResponse, responses=_ERROR_RESPONSES, summary="Hỏi đáp, trả một lần (bot)")
async def chat(body: ChatRequest, request: Request, service: ChatService = Depends(get_chat_service)) -> ChatResponse:
    await enforce_chat_limits(request, body)
    return await service.answer(body)


@router.post(
    "/chat/stream",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Luồng SSE. Mỗi frame: `event: <tên>` + `data: <JSON>`. Thứ tự: status, token (nhiều lần), "
            "sources, done; lỗi giữa chừng gửi `error` rồi đóng. Schema từng event: StatusEvent, TokenEvent, "
            "SourcesEvent, DoneEvent, ErrorEvent.",
        },
        **_ERROR_RESPONSES,
    },
    summary="Hỏi đáp, stream SSE (web)",
)
async def chat_stream(
    body: ChatRequest, request: Request, service: ChatService = Depends(get_chat_service)
) -> StreamingResponse:
    await enforce_chat_limits(request, body)
    # Lỗi trước khi bắt đầu stream (hội thoại không tồn tại, quá tốc độ…) vẫn trả JSON + mã HTTP đúng
    stream = await service.open_stream(body)

    async def events() -> AsyncIterator[str]:
        try:
            async with aclosing(stream):
                async for event, payload in stream:
                    yield _sse(event, payload)
        except Exception as exc:
            code = exc.code if isinstance(exc, AppError) else AppError.code
            log.error("stream failed", extra={"data": {"code": code}})
            message = exc.message if isinstance(exc, AppError) else AppError.message
            error = ErrorEvent(code=code, message=message, request_id=request_id_var.get())
            yield _sse("error", error)

    return StreamingResponse(
        events(),
        background=BackgroundTask(stream.aclose),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # tắt buffer của Caddy/nginx
    )
