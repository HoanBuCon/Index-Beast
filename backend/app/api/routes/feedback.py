"""POST /feedback: 👍/👎 cho một câu trả lời.

Phụ trách: TV1 · [S2] API contract v1
"""

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_chat_service
from app.api.errors import ErrorBody
from app.api.schemas.feedback import FeedbackRequest
from app.services.mock_chat import MockChatService
from core.errors import NotFoundError

router = APIRouter(tags=["feedback"])


@router.post(
    "/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorBody}, 422: {"model": ErrorBody}},
    summary="Gửi 👍/👎 cho message_id",
)
async def feedback(body: FeedbackRequest, service: MockChatService = Depends(get_chat_service)) -> Response:
    if not service.has_message(body.message_id):
        raise NotFoundError("Không tìm thấy câu trả lời để đánh giá.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
