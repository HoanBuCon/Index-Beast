"""POST /chat (JSON, cho bot) và POST /chat/stream (SSE: status, token, sources, done, error; cho web).

S2: dùng MockChatService. S3 thay service bằng pipeline RAG thật, giữ nguyên route và schema.

Phụ trách: TV1 · [S2] API contract v1 · [S3] Endpoint /chat & /chat/stream thật
"""

import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_chat_service
from app.api.errors import ErrorBody
from app.api.schemas.chat import (
    SSE_EVENT_MODELS,
    ChatRequest,
    ChatResponse,
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    StatusEvent,
    TokenEvent,
)
from app.services.mock_chat import MockChatService
from core.errors import AppError
from core.logging import request_id_var

router = APIRouter(tags=["chat"])
log = logging.getLogger(__name__)

_ERROR_RESPONSES = {code: {"model": ErrorBody} for code in (404, 422, 429, 502)}


def _sse(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {SSE_EVENT_MODELS[event].model_validate(payload).model_dump_json()}\n\n"


@router.post("/chat", response_model=ChatResponse, responses=_ERROR_RESPONSES, summary="Hỏi đáp, trả một lần (bot)")
async def chat(body: ChatRequest, service: MockChatService = Depends(get_chat_service)) -> ChatResponse:
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
async def chat_stream(body: ChatRequest, service: MockChatService = Depends(get_chat_service)) -> StreamingResponse:
    # Lỗi trước khi bắt đầu stream (hội thoại không tồn tại, quá tốc độ…) vẫn trả JSON + mã HTTP đúng
    result = await service.answer(body)

    async def events() -> AsyncIterator[str]:
        try:
            yield _sse("status", StatusEvent(status="searching"))
            for word in result.answer.split(" "):
                yield _sse("token", TokenEvent(token=word + " "))
            yield _sse("sources", SourcesEvent(sources=result.sources))
            yield _sse("done", DoneEvent.model_validate(result, from_attributes=True))
        except Exception as exc:
            code = exc.code if isinstance(exc, AppError) else AppError.code
            log.exception("stream failed", extra={"data": {"code": code}})
            error = ErrorEvent(code=code, message=AppError.message, request_id=request_id_var.get())
            yield _sse("error", error)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # tắt buffer của Caddy/nginx
    )
