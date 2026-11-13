"""TV4 · API chia sẻ giới hạn được người dùng duyệt; không mở quyền đọc cả hội thoại Discord."""

from fastapi import APIRouter, Depends, Header, Request, Response

from app.api.deps import get_chat_service
from app.api.errors import ErrorBody
from app.api.guard import is_trusted_service
from app.api.schemas.answer_share import AnswerShareCreated, AnswerShareRequest, SharedAnswer
from app.services.answer_shares import AnswerShareStore
from core.errors import BadRequestError, NotFoundError, UnauthorizedError

router = APIRouter(tags=["answer-shares"])


def private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"


@router.post(
    "/answer-shares",
    response_model=AnswerShareCreated,
    status_code=201,
    responses={code: {"model": ErrorBody} for code in (400, 401, 404, 503)},
)
async def create_answer_share(
    body: AnswerShareRequest, request: Request, response: Response, service=Depends(get_chat_service)
) -> AnswerShareCreated:
    if not is_trusted_service(request):
        raise UnauthorizedError("Chỉ dịch vụ bot được tạo link chia sẻ.")
    if hasattr(service, "stored_history"):
        history = await service.stored_history(body.conversation_id, trusted_service=True)
    else:
        history = service.history(body.conversation_id)
    if history.channel != "discord":
        raise BadRequestError("Chỉ chia sẻ câu trả lời Discord qua chức năng này.")
    index = next((i for i, message in enumerate(history.messages) if message.id == body.message_id), None)
    if index is None or history.messages[index].role != "assistant":
        raise NotFoundError("Không tìm thấy câu trả lời để chia sẻ.")
    message = history.messages[index]
    question = next((m.content for m in reversed(history.messages[:index]) if m.role == "user"), "")
    result = await AnswerShareStore(request.app.state.ctx.redis).create(
        question=question, answer=message.content, sources=message.sources, grounded=message.grounded is True
    )
    private_response(response)
    return result


@router.get(
    "/answer-shares", response_model=SharedAnswer, responses={code: {"model": ErrorBody} for code in (404, 503)}
)
async def read_answer_share(
    request: Request, response: Response, token: str | None = Header(default=None, alias="X-Answer-Share-Token")
) -> SharedAnswer:
    # Capability nhận qua header; token trong fragment của link web không đi vào access log.
    result = await AnswerShareStore(request.app.state.ctx.redis).read(token)
    private_response(response)
    return result
