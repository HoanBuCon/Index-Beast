"""GET /conversations/{id}: lịch sử hội thoại.

Phụ trách: TV1 · [S2] API contract v1
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_chat_service, optional_user
from app.api.errors import ErrorBody
from app.api.guard import _trusted_service
from app.api.schemas.conversation import ConversationOut
from app.services.auth import AuthUser
from app.services.chat import ChatService

router = APIRouter(tags=["conversations"])


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationOut,
    responses={
        401: {"model": ErrorBody},
        404: {"model": ErrorBody},
        422: {"model": ErrorBody},
        503: {"model": ErrorBody},
    },
    summary="Lịch sử hội thoại",
)
async def get_conversation(
    conversation_id: UUID,
    request: Request,
    service: ChatService = Depends(get_chat_service),
    user: AuthUser | None = Depends(optional_user),
) -> ConversationOut:
    if hasattr(service, "stored_history"):
        return await service.stored_history(
            conversation_id,
            token=request.headers.get("X-Conversation-Token"),
            trusted_service=_trusted_service(request),
            user_id=user.id if user else None,
        )
    return service.history(conversation_id)
