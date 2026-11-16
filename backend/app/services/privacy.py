"""Quyền riêng tư (FR-AUTH-08, NFR-PRIV-01): xóa tài khoản và xóa dữ liệu quá hạn lưu giữ.

Hai việc dùng chung các hàm xóa hội thoại: điểm ngữ nghĩa trong Qdrant xóa TRƯỚC, PostgreSQL xóa SAU. Qdrant lỗi thì
không xóa gì và người dùng thử lại được; ngược lại sẽ để lại vector mồ côi mà không còn cách tìm ra chúng.

Lưu ý hợp nhất: PR #110 thêm `MemoryVectors.delete_conversations` làm cùng việc với `purge_memory_vectors` ở đây;
khi merge, giữ một bản (nên giữ phương thức của #110 và để `purge_memory_vectors` gọi nó).

Phụ trách: TV1 · [S5] Quyền riêng tư và xóa tài khoản
"""

from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import datetime
from uuid import UUID

from qdrant_client import models as qm
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError

from core.db.models import AuthSession, Conversation, Feedback, Message, User
from core.errors import UnavailableError

BATCH_SIZE = 500  # số hội thoại mỗi lần xóa: giữ transaction và bộ lọc Qdrant nhỏ
_VECTOR_FILTER_CHUNK = 200


@dataclass
class Counts:
    conversations: int = 0
    messages: int = 0
    feedback: int = 0
    sessions: int = 0
    users: int = 0

    def add(self, other: "Counts") -> None:
        for f in fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(other, f.name))


async def purge_memory_vectors(client, collection: str, conversation_ids: Sequence[UUID]) -> None:
    """Xóa mọi điểm ký ức của các hội thoại này khỏi Qdrant (lọc theo payload `conversation_id`).
    `client` None (chế độ llm_only) hoặc chưa có collection thì không có gì để xóa."""
    if client is None or not conversation_ids:
        return
    try:
        if not await client.collection_exists(collection):
            return
        for start in range(0, len(conversation_ids), _VECTOR_FILTER_CHUNK):
            ids = [str(i) for i in conversation_ids[start : start + _VECTOR_FILTER_CHUNK]]
            selector = qm.FilterSelector(
                filter=qm.Filter(must=[qm.FieldCondition(key="conversation_id", match=qm.MatchAny(any=ids))])
            )
            await client.delete(collection, points_selector=selector, wait=True)
    except Exception:
        raise UnavailableError("Không xóa được ký ức hội thoại. Chưa có dữ liệu nào bị xóa, hãy thử lại.") from None


async def _delete_conversations(session, ids: Sequence[UUID]) -> Counts:
    """Đếm rồi xóa; tin nhắn, feedback, ký ức, runtime đi theo khóa ngoại ON DELETE CASCADE."""
    messages = select(Message.id).where(Message.conversation_id.in_(ids))
    counts = Counts(
        messages=(await session.execute(select(func.count()).where(Message.conversation_id.in_(ids)))).scalar_one(),
        feedback=(
            await session.execute(select(func.count()).select_from(Feedback).where(Feedback.message_id.in_(messages)))
        ).scalar_one(),
    )
    counts.conversations = (await session.execute(delete(Conversation).where(Conversation.id.in_(ids)))).rowcount
    return counts


async def delete_account(sessionmaker, qdrant, memory_collection: str, user_id: UUID) -> Counts:
    """Xóa người dùng, mọi phiên, mọi hội thoại gắn với họ (kèm tin nhắn, feedback, ký ức) và điểm Qdrant tương ứng.
    Idempotent: người dùng đã mất thì trả số đếm 0, không lỗi."""
    total = Counts()
    try:
        while True:
            async with sessionmaker() as session:
                ids = list(
                    (
                        await session.execute(
                            select(Conversation.id).where(Conversation.user_id == user_id).limit(BATCH_SIZE)
                        )
                    ).scalars()
                )
            if not ids:
                break
            await purge_memory_vectors(qdrant, memory_collection, ids)
            async with sessionmaker() as session, session.begin():
                total.add(await _delete_conversations(session, ids))
        async with sessionmaker() as session, session.begin():
            total.sessions = (
                await session.execute(
                    select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user_id)
                )
            ).scalar_one()
            total.users = (await session.execute(delete(User).where(User.id == user_id))).rowcount  # phiên: CASCADE
    except SQLAlchemyError:
        raise UnavailableError("Không xóa được tài khoản. Hãy thử lại.") from None
    return total


def _stale(cutoff: datetime):
    """Hoạt động cuối = tin nhắn mới nhất, hoặc lúc tạo nếu hội thoại chưa có tin."""
    newest = select(func.max(Message.created_at)).where(Message.conversation_id == Conversation.id).scalar_subquery()
    return func.coalesce(newest, Conversation.created_at) < cutoff


async def _count_retention(session, cutoff: datetime, now: datetime) -> Counts:
    stale_ids = select(Conversation.id).where(_stale(cutoff))
    messages = select(Message.id).where(Message.conversation_id.in_(stale_ids))
    return Counts(
        conversations=(await session.execute(select(func.count()).select_from(stale_ids.subquery()))).scalar_one(),
        messages=(await session.execute(select(func.count()).select_from(messages.subquery()))).scalar_one(),
        feedback=(
            await session.execute(select(func.count()).select_from(Feedback).where(Feedback.message_id.in_(messages)))
        ).scalar_one(),
        sessions=(
            await session.execute(select(func.count()).select_from(AuthSession).where(AuthSession.expires_at < now))
        ).scalar_one(),
    )


async def apply_retention(
    sessionmaker, qdrant, memory_collection: str, *, cutoff: datetime, now: datetime, dry_run: bool = False
) -> Counts:
    """NFR-PRIV-01: xóa hội thoại có hoạt động cuối trước `cutoff` và phiên đăng nhập hết hạn trước `now`.
    Trace RAG nằm trong `messages.rag_trace` nên đi cùng hội thoại. `dry_run` chỉ đếm."""
    try:
        if dry_run:
            async with sessionmaker() as session:
                return await _count_retention(session, cutoff, now)
        total = Counts()
        while True:
            async with sessionmaker() as session:
                ids = list(
                    (await session.execute(select(Conversation.id).where(_stale(cutoff)).limit(BATCH_SIZE))).scalars()
                )
            if not ids:
                break
            await purge_memory_vectors(qdrant, memory_collection, ids)
            async with sessionmaker() as session, session.begin():
                total.add(await _delete_conversations(session, ids))
        while True:
            async with sessionmaker() as session, session.begin():
                batch = select(AuthSession.id).where(AuthSession.expires_at < now).limit(BATCH_SIZE)
                removed = (await session.execute(delete(AuthSession).where(AuthSession.id.in_(batch)))).rowcount
            total.sessions += removed
            if removed < BATCH_SIZE:
                break
        return total
    except SQLAlchemyError:
        raise UnavailableError("Không áp dụng được chính sách lưu giữ dữ liệu.") from None
