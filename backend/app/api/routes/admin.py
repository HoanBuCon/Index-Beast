"""/admin/*: xem trace theo message_id (S3); thống kê, trạng thái ingestion job, kết quả eval (S5). Cần X-Admin-Token.

Phụ trách: TV1 · [S3] Trace từng bước RAG · [S5] Trang admin (API)
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_chat_service, require_admin
from app.api.errors import ErrorBody
from app.api.schemas.trace import TraceOut
from app.services.chat import ChatService

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


@router.get(
    "/admin/trace/{message_id}",
    response_model=TraceOut,
    responses={401: {"model": ErrorBody}, 404: {"model": ErrorBody}, 422: {"model": ErrorBody}},
    summary="Trace RAG của một câu trả lời",
)
async def get_trace(message_id: UUID, service: ChatService = Depends(get_chat_service)) -> TraceOut:
    return TraceOut.model_validate(await service.trace(message_id))
