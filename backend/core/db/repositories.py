"""Truy vấn hay dùng: hội thoại và tin nhắn, feedback, upsert document/chunk, ghi job ingest.

Mỗi hàm nhận AsyncSession và chỉ flush, không commit: nơi gọi (dependency get_session, CLI ingest) quyết định
ranh giới transaction. Tách file khi quá ~300 dòng.

Phụ trách: TV1 · [S2] Schema PostgreSQL & migrations
"""

import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.db.models import Chunk, Conversation, Document, Feedback, IngestionJob, Message


async def create_conversation(
    session: AsyncSession,
    *,
    channel: str,
    external_ref: str | None = None,
    client_user_ref: str | None = None,
    guild_id: str | None = None,
) -> Conversation:
    conversation = Conversation(
        channel=channel, external_ref=external_ref, client_user_ref=client_user_ref, guild_id=guild_id
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def get_conversation(session: AsyncSession, conversation_id: uuid.UUID) -> Conversation | None:
    """Kèm toàn bộ tin nhắn theo thứ tự thời gian."""
    query = select(Conversation).where(Conversation.id == conversation_id).options(selectinload(Conversation.messages))
    return (await session.execute(query)).scalar_one_or_none()


async def add_message(
    session: AsyncSession, conversation_id: uuid.UUID, *, role: str, content: str, **fields: Any
) -> Message:
    """`fields`: rewritten_query, sources, grounded, latency_ms, tokens_in, tokens_out, trace."""
    message = Message(conversation_id=conversation_id, role=role, content=content, **fields)
    session.add(message)
    await session.flush()
    return message


async def recent_messages(session: AsyncSession, conversation_id: uuid.UUID, limit: int = 6) -> list[Message]:
    """N tin gần nhất (FR-CHAT-02), trả theo thứ tự cũ → mới."""
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id)
        .limit(limit)
    )
    return list(reversed((await session.execute(query)).scalars().all()))


async def message_exists(session: AsyncSession, message_id: uuid.UUID) -> bool:
    return (await session.execute(select(Message.id).where(Message.id == message_id))).first() is not None


async def add_feedback(session: AsyncSession, message_id: uuid.UUID, rating: int, reason: str | None) -> Feedback:
    feedback = Feedback(message_id=message_id, rating=rating, reason=reason)
    session.add(feedback)
    await session.flush()
    return feedback


async def upsert_document(session: AsyncSession, **fields: Any) -> uuid.UUID:
    """Theo (source, source_id); trả id. Trang đã có thì cập nhật revision, hash, trạng thái…"""
    values = {"id": uuid.uuid4(), **fields}
    update = {k: v for k, v in fields.items() if k not in ("source", "source_id")}
    update["updated_at"] = datetime.now(UTC)
    statement = (
        insert(Document)
        .values(**values)
        .on_conflict_do_update(constraint="uq_documents_source_source_id", set_=update)
        .returning(Document.id)
    )
    return (await session.execute(statement)).scalar_one()


async def replace_chunks(session: AsyncSession, document_id: uuid.UUID, chunks: Iterable[dict[str, Any]]) -> int:
    """Thay toàn bộ chunk của một document trong cùng transaction (chia đoạn lại không để chunk mồ côi)."""
    rows = [{**chunk, "document_id": document_id} for chunk in chunks]
    await session.execute(delete(Chunk).where(Chunk.document_id == document_id))
    if rows:
        await session.execute(insert(Chunk), rows)
    return len(rows)


async def start_job(
    session: AsyncSession, *, kind: str, source: str | None = None, external_id: str | None = None
) -> IngestionJob:
    job = IngestionJob(kind=kind, source=source, external_id=external_id)
    session.add(job)
    await session.flush()
    return job


async def finish_job(
    session: AsyncSession,
    job: IngestionJob,
    *,
    pages_ok: int,
    pages_failed: int,
    log: dict[str, Any] | None = None,
) -> IngestionJob:
    """succeeded khi không có lỗi, partial khi lẫn lỗi và thành công, failed khi không trang nào thành công."""
    job.pages_ok, job.pages_failed, job.log = pages_ok, pages_failed, log
    job.status = "succeeded" if not pages_failed else ("partial" if pages_ok else "failed")
    job.finished_at = datetime.now(UTC)
    await session.flush()
    return job


async def list_jobs(session: AsyncSession, limit: int = 20) -> Sequence[IngestionJob]:
    query = select(IngestionJob).order_by(IngestionJob.started_at.desc()).limit(limit)
    return (await session.execute(query)).scalars().all()
