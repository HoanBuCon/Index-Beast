"""Quyền riêng tư (FR-AUTH-08, NFR-PRIV-01): xóa tài khoản và xóa dữ liệu quá hạn lưu giữ.

Hai việc dùng chung các hàm xóa hội thoại: điểm ngữ nghĩa trong Qdrant xóa TRƯỚC, PostgreSQL xóa SAU. Qdrant lỗi thì
phần còn lại chưa bị xóa và người dùng thử lại được; ngược lại sẽ để lại vector mồ côi mà không còn cách tìm ra chúng.

Lưu ý hợp nhất: PR #110 thêm `MemoryVectors.delete_conversations(ids)` làm cùng việc với `VectorPurger` ở đây (cùng
tên, cùng đối số); khi merge, thay `VectorPurger(client, collection)` bằng `MemoryVectors(...)` rồi xóa lớp này.

Phụ trách: TV1 · [S5] Quyền riêng tư và xóa tài khoản
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import datetime
from uuid import UUID

import httpx
from qdrant_client import models as qm
from qdrant_client.http.exceptions import ApiException, ResponseHandlingException
from sqlalchemy import delete, func, null, select, update
from sqlalchemy.exc import SQLAlchemyError

from core.db.models import AuthSession, Conversation, Feedback, IngestionJob, Message, User
from core.errors import UnavailableError

log = logging.getLogger(__name__)

BATCH_SIZE = 500  # số hội thoại mỗi lần xóa: giữ transaction và bộ lọc Qdrant nhỏ
_VECTOR_FILTER_CHUNK = 200
_QDRANT_ERRORS = (ApiException, ResponseHandlingException, httpx.HTTPError, OSError)


@dataclass
class Counts:
    conversations: int = 0
    messages: int = 0
    feedback: int = 0
    sessions: int = 0
    users: int = 0
    traces: int = 0
    ingestion_logs: int = 0

    def add(self, other: "Counts") -> None:
        for f in fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(other, f.name))


class VectorPurger:
    """Cùng dáng với `MemoryVectors.delete_conversations(ids)` của PR #110: lọc theo payload `conversation_id`, không
    đếm. `client` None (chế độ mock/test) hoặc chưa có collection thì không có gì để xóa."""

    def __init__(self, client, collection: str):
        self.client, self.collection = client, collection

    async def delete_conversations(self, conversation_ids: Sequence[UUID]) -> None:
        if self.client is None or not conversation_ids:
            return
        try:
            if not await self.client.collection_exists(self.collection):
                return
            for start in range(0, len(conversation_ids), _VECTOR_FILTER_CHUNK):
                ids = [str(i) for i in conversation_ids[start : start + _VECTOR_FILTER_CHUNK]]
                selector = qm.FilterSelector(
                    filter=qm.Filter(must=[qm.FieldCondition(key="conversation_id", match=qm.MatchAny(any=ids))])
                )
                await self.client.delete(self.collection, points_selector=selector, wait=True)
        except _QDRANT_ERRORS:
            log.warning("memory vector purge failed", exc_info=True)
            raise UnavailableError("Không xóa được ký ức hội thoại. Chưa có dữ liệu nào bị xóa, hãy thử lại.") from None


async def _delete_conversations(session, ids: Sequence[UUID], *, count: bool) -> Counts:
    """Xóa; tin nhắn, feedback, ký ức, runtime đi theo khóa ngoại ON DELETE CASCADE. `count` bật thì đếm thêm."""
    counts = Counts()
    if count:
        messages = select(Message.id).where(Message.conversation_id.in_(ids))
        counts.messages = (
            await session.execute(select(func.count()).select_from(Message).where(Message.conversation_id.in_(ids)))
        ).scalar_one()
        counts.feedback = (
            await session.execute(select(func.count()).select_from(Feedback).where(Feedback.message_id.in_(messages)))
        ).scalar_one()
    counts.conversations = (await session.execute(delete(Conversation).where(Conversation.id.in_(ids)))).rowcount
    return counts


async def delete_account(sessionmaker, qdrant, memory_collection: str, user_id: UUID) -> Counts:
    """Xóa người dùng, mọi phiên, mọi hội thoại gắn `user_id` (gồm cả hội thoại khách đã nhận) kèm tin nhắn, feedback,
    ký ức và điểm Qdrant. Idempotent: người dùng đã mất thì trả 0, không lỗi.

    Phiên đăng nhập được GIỮ tới bước cuối cùng: mọi lỗi giữa chừng (Qdrant hoặc PostgreSQL) để phiên còn hiệu lực nên
    `DELETE /me` gọi lại được, và vòng sau nhặt đúng phần còn sót (hội thoại còn trong PostgreSQL). Mỗi lô: xóa vector
    TRƯỚC, hàng PostgreSQL SAU. Bước cuối: xóa vector của hội thoại còn sót, rồi trong MỘT transaction xóa nốt hội thoại
    (gồm hội thoại mới tạo xen vào), mọi phiên và dòng người dùng (nếu không, khóa ngoại SET NULL sẽ biến hội thoại sót
    thành hội thoại khách mà vẫn còn dữ liệu). Vector của hội thoại tạo sát bước cuối được `SemanticMemory.sync` dọn qua
    `conversation_exists` (rag/semantic_memory.py) vì dòng hội thoại đã mất."""
    purger, total = VectorPurger(qdrant, memory_collection), Counts()
    try:
        while True:
            async with sessionmaker() as session:
                found = select(Conversation.id).where(Conversation.user_id == user_id).limit(BATCH_SIZE)
                ids = list((await session.execute(found)).scalars())
            if not ids:
                break
            await purger.delete_conversations(ids)
            async with sessionmaker() as session, session.begin():
                total.add(await _delete_conversations(session, ids, count=False))
        async with sessionmaker() as session:
            remaining = list(
                (await session.execute(select(Conversation.id).where(Conversation.user_id == user_id))).scalars()
            )
        await purger.delete_conversations(remaining)
        async with sessionmaker() as session, session.begin():
            leftover = delete(Conversation).where(Conversation.user_id == user_id).returning(Conversation.id)
            stragglers = list((await session.execute(leftover)).scalars())
            total.conversations += len(stragglers)
            total.sessions = (await session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))).rowcount
            total.users = (await session.execute(delete(User).where(User.id == user_id))).rowcount
    except SQLAlchemyError:
        raise UnavailableError("Không xóa được tài khoản. Hãy thử lại.") from None
    late = [i for i in stragglers if i not in set(remaining)]
    if late:  # hiếm: tạo giữa lần chọn cuối và transaction cuối; người dùng đã mất nên chỉ dọn best-effort
        try:
            await purger.delete_conversations(late)
        except UnavailableError:
            log.warning("late memory vectors left for the indexer cleanup", extra={"conversations": len(late)})
    return total


def _stale_ids(cutoff: datetime):
    """Đọc tin mới nhất theo index (conversation_id, created_at); nếu chưa có tin thì dùng lúc tạo."""
    newest = (
        select(Message.created_at)
        .where(Message.conversation_id == Conversation.id)
        .order_by(Message.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    return (
        select(Conversation.id)
        .where(Conversation.channel == "web", Conversation.user_id.is_(None))
        .where(func.coalesce(newest, Conversation.created_at) < cutoff)
    )


def _still_stale(cutoff: datetime, ids: Sequence[UUID]):
    return _stale_ids(cutoff).where(Conversation.id.in_(ids))


def _guest_batch(cutoff: datetime, after=None):
    query = _stale_ids(cutoff)
    if after is not None:
        query = query.where(Conversation.id > after)
    return query.order_by(Conversation.id).limit(BATCH_SIZE).with_for_update(of=Conversation)


def _old_traces(cutoff: datetime):
    return select(Message.id).where(
        Message.created_at < cutoff, Message.rag_trace.is_not(None), func.jsonb_typeof(Message.rag_trace) != "null"
    )


def _old_ingestion_logs(cutoff: datetime):
    return select(IngestionJob.id).where(
        IngestionJob.finished_at < cutoff, IngestionJob.log.is_not(None), func.jsonb_typeof(IngestionJob.log) != "null"
    )


def _clear_old_traces(cutoff: datetime):
    return update(Message).where(Message.id.in_(_old_traces(cutoff).limit(BATCH_SIZE))).values(rag_trace=null())


def _clear_old_ingestion_logs(cutoff: datetime):
    return (
        update(IngestionJob)
        .where(IngestionJob.id.in_(_old_ingestion_logs(cutoff).limit(BATCH_SIZE)))
        .values(log=null())
    )


async def _count_retention(session, cutoff: datetime, now: datetime) -> Counts:
    stale = _stale_ids(cutoff).subquery()
    stale_ids = select(stale.c.id)
    traces_to_clear = _old_traces(cutoff).where(Message.conversation_id.not_in(stale_ids))
    return Counts(
        conversations=(await session.execute(select(func.count()).select_from(stale))).scalar_one(),
        messages=(
            await session.execute(
                select(func.count()).select_from(Message).where(Message.conversation_id.in_(stale_ids))
            )
        ).scalar_one(),
        feedback=(
            await session.execute(
                select(func.count())
                .select_from(Feedback)
                .join(Message, Message.id == Feedback.message_id)
                .where(Message.conversation_id.in_(stale_ids))
            )
        ).scalar_one(),
        traces=(await session.execute(select(func.count()).select_from(traces_to_clear.subquery()))).scalar_one(),
        ingestion_logs=(
            await session.execute(select(func.count()).select_from(_old_ingestion_logs(cutoff).subquery()))
        ).scalar_one(),
        sessions=(
            await session.execute(select(func.count()).select_from(AuthSession).where(AuthSession.expires_at < now))
        ).scalar_one(),
    )


async def apply_retention(
    sessionmaker, qdrant, memory_collection: str, *, cutoff: datetime, now: datetime, dry_run: bool = False
) -> Counts:
    """Xóa khách web quá hạn, trace cũ của mọi kênh và phiên hết hạn; `dry_run` chỉ đếm.

    Khóa từng lô hội thoại trước khi kiểm lại và xóa; giữ khóa tới khi giao dịch xong.
    """
    purger = VectorPurger(qdrant, memory_collection)
    try:
        if dry_run:
            async with sessionmaker() as session:
                return await _count_retention(session, cutoff, now)
        total = Counts()
        after = None
        while True:
            async with sessionmaker() as session, session.begin():
                candidates = list((await session.execute(_guest_batch(cutoff, after))).scalars())
                if not candidates:
                    break
                after = candidates[-1]
                ids = list((await session.execute(_still_stale(cutoff, candidates))).scalars())
                if ids:
                    await purger.delete_conversations(ids)
                    total.add(await _delete_conversations(session, ids, count=True))
        while True:
            async with sessionmaker() as session, session.begin():
                result = await session.execute(_clear_old_traces(cutoff))
                removed = result.rowcount
            total.traces += removed
            if removed < BATCH_SIZE:
                break
        while True:
            async with sessionmaker() as session, session.begin():
                removed = (await session.execute(_clear_old_ingestion_logs(cutoff))).rowcount
            total.ingestion_logs += removed
            if removed < BATCH_SIZE:
                break
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
