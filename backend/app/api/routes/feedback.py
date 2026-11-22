"""POST /feedback: 👍/👎 cho một câu trả lời; lưu vào bảng feedback khi bật lưu hội thoại bằng PostgreSQL.

Phụ trách: TV1 · [S2] API contract v1
"""

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import get_chat_service, optional_user
from app.api.errors import ErrorBody
from app.api.guard import is_trusted_service
from app.api.schemas.feedback import FeedbackRequest
from app.services.auth import AuthUser
from app.services.chat import ChatService
from core.errors import NotFoundError

router = APIRouter(tags=["feedback"])


@router.post(
    "/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorBody},
        404: {"model": ErrorBody},
        422: {"model": ErrorBody},
        503: {"model": ErrorBody},
    },
    summary="Gửi 👍/👎 cho message_id",
)
async def feedback(
    body: FeedbackRequest,
    request: Request,
    service: ChatService = Depends(get_chat_service),
    user: AuthUser | None = Depends(optional_user),
) -> Response:
    exists = (
        await service.stored_has_message(
            body.message_id,
            token=request.headers.get("X-Conversation-Token"),
            trusted_service=is_trusted_service(request),
            user_id=user.id if user else None,
        )
        if hasattr(service, "stored_has_message")
        else service.has_message(body.message_id)
    )
    if not exists:
        raise NotFoundError("Không tìm thấy câu trả lời để đánh giá.")
    # Chỉ lưu khi hội thoại nằm trong PostgreSQL (CHAT_PERSISTENCE=postgres); chế độ RAM chỉ xác nhận yêu cầu
    if (repository := getattr(service, "repository", None)) is not None:
        await repository.save_feedback(body.message_id, body.rating, body.reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
