"""GET /conversations/{id}: lịch sử hội thoại.

Phụ trách: TV1 · [S2] API contract v1
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_chat_service
from app.api.errors import ErrorBody
from app.api.schemas.conversation import ConversationOut
from app.services.chat import ChatService

router = APIRouter(tags=["conversations"])


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationOut,
    responses={404: {"model": ErrorBody}, 422: {"model": ErrorBody}},
    summary="Lịch sử hội thoại",
)
async def get_conversation(conversation_id: UUID, service: ChatService = Depends(get_chat_service)) -> ConversationOut:
    return service.history(conversation_id)
