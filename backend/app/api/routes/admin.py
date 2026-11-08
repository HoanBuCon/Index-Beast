"""/admin/*: trace theo message_id và thống kê cho trang admin (hội thoại, feedback, job ingestion, eval).
Cần X-Admin-Token; chưa đặt ADMIN_TOKEN thì cả nhóm trả 404.

Phụ trách: TV1 · [S3] Trace từng bước RAG · [S5] Trang admin (API)
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_chat_service, get_ctx, require_admin
from app.api.errors import ErrorBody
from app.api.schemas.admin import AdminConversation, AdminEvalRun, AdminFeedback, AdminJob, AdminStats
from app.api.schemas.trace import TraceOut
from app.context import AppContext
from app.services.chat import ChatService
from core.db import repositories as repo
from core.errors import UnavailableError

TITLE_CHARS = 60

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


@router.get(
    "/admin/trace/{message_id}",
    response_model=TraceOut,
    responses={401: {"model": ErrorBody}, 404: {"model": ErrorBody}, 422: {"model": ErrorBody}},
    summary="Trace RAG của một câu trả lời",
)
async def get_trace(message_id: UUID, service: ChatService = Depends(get_chat_service)) -> TraceOut:
    return TraceOut.model_validate(await service.trace(message_id))


def _title(question: str | None) -> str:
    text = " ".join((question or "").split())
    return text[:TITLE_CHARS] if text else "(chưa có câu hỏi)"


@router.get(
    "/admin/stats",
    response_model=AdminStats,
    responses={401: {"model": ErrorBody}, 404: {"model": ErrorBody}, 503: {"model": ErrorBody}},
    summary="Hội thoại gần đây, feedback, job ingestion và kết quả eval",
)
async def get_stats(ctx: AppContext = Depends(get_ctx)) -> AdminStats:
    """Đọc PostgreSQL. Hội thoại chỉ có ở đó khi CHAT_PERSISTENCE=postgres; chế độ memory trả danh sách rỗng."""
    try:
        async with ctx.sessionmaker() as session:
            conversations = await repo.recent_conversations(session)
            feedback = await repo.recent_feedback(session)
            jobs = await repo.list_jobs(session, limit=10)
            runs = await repo.recent_eval_runs(session)
    except SQLAlchemyError:
        raise UnavailableError("Không đọc được thống kê từ PostgreSQL.") from None
    return AdminStats(
        conversations=[AdminConversation(id=str(i), title=_title(q), created_at=at) for i, q, at in conversations],
        feedback=[AdminFeedback(message_id=str(f.message_id), rating=f.rating, reason=f.reason) for f in feedback],
        ingestion_jobs=[AdminJob(id=j.external_id or str(j.id), status=j.status, pages_ok=j.pages_ok) for j in jobs],
        eval_runs=[
            AdminEvalRun(
                id=str(r.id),
                # Client web chỉ nhận số; bỏ giá trị khác (và bool, vì bool cũng là int)
                metrics={k: v for k, v in (r.metrics or {}).items() if type(v) in (int, float)},
            )
            for r in runs
        ],
    )
