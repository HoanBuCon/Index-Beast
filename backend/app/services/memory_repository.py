"""PostgreSQL is chat/memory source of truth; vector indexes are rebuildable derivatives."""

import hashlib
import hmac
from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import undefer

from app.api.schemas.conversation import ConversationOut, MessageOut
from core.db.models import Conversation, ConversationMemory, ConversationRuntime, Feedback, Message
from core.errors import BadRequestError, NotFoundError, UnauthorizedError, UnavailableError


def owner_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class Snapshot:
    conversation: ConversationOut
    external_ref: str | None
    owner: str
    revision: int
    working: dict
    user_id: UUID | None = None  # chủ sở hữu đã đăng nhập, gắn vào hội thoại mới


class MemoryRepository:
    def __init__(self, sessionmaker):
        self.sessions = sessionmaker

    async def load(self, conversation_id=None, *, channel, external_ref, token=None, user_id=None) -> Snapshot | None:
        try:
            async with self.sessions() as session:
                query = select(Conversation, ConversationRuntime).join(ConversationRuntime)
                if conversation_id is not None:
                    query = query.where(Conversation.id == conversation_id)
                elif channel == "discord" and external_ref:
                    query = query.where(Conversation.channel == channel, Conversation.external_ref == external_ref)
                else:
                    return None
                row = (await session.execute(query)).first()
                if row is None:
                    if conversation_id:
                        raise NotFoundError("Không tìm thấy hội thoại đã lưu.")
                    return None
                conv, runtime = row
                if conv.channel != channel or conv.external_ref != external_ref:
                    raise NotFoundError("Không tìm thấy hội thoại.")
                owned_by_user = user_id is not None and conv.user_id == user_id  # ADR-005
                if (
                    channel == "web"
                    and not owned_by_user
                    and (not token or not hmac.compare_digest(owner_hash(token), conv.client_user_ref or ""))
                ):
                    raise UnauthorizedError("Cần token của hội thoại này.")
                messages = (
                    await session.scalars(
                        select(Message)
                        .where(Message.conversation_id == conv.id)
                        .order_by(Message.created_at.desc(), Message.id.desc())
                        .limit(64)
                    )
                ).all()
                output = ConversationOut(
                    id=conv.id,
                    channel=conv.channel,
                    created_at=conv.created_at,
                    messages=[
                        MessageOut(
                            id=m.id,
                            role=m.role,
                            content=m.content,
                            sources=m.sources,
                            grounded=m.grounded,
                            images=(m.trace or {}).get("images", []),
                            clarification=(m.trace or {}).get("clarification"),
                            created_at=m.created_at,
                        )
                        for m in reversed(messages)
                    ],
                )
                return Snapshot(output, conv.external_ref, conv.client_user_ref or "", runtime.revision, runtime.state)
        except SQLAlchemyError:
            raise UnavailableError("Không đọc được hội thoại đã lưu.") from None

    async def save_feedback(self, message_id: UUID, rating: int, reason: str | None) -> None:
        """Mỗi câu trả lời giữ một đánh giá: gửi lại thì thay thế đánh giá cũ (người dùng đổi ý 👍 sang 👎)."""
        try:
            async with self.sessions() as session, session.begin():
                await session.execute(delete(Feedback).where(Feedback.message_id == message_id))
                session.add(Feedback(message_id=message_id, rating=rating, reason=reason))
                await session.flush()
        except SQLAlchemyError:
            raise UnavailableError("Không lưu được đánh giá.") from None

    async def trace(self, message_id: UUID) -> dict | None:
        """Số đo và trace RAG của một câu trả lời; None nếu không phải tin nhắn assistant đã lưu."""
        try:
            async with self.sessions() as session:
                stmt = select(Message).options(undefer(Message.rag_trace)).where(Message.id == message_id)
                row = (await session.scalars(stmt)).first()
        except SQLAlchemyError:
            raise UnavailableError("Không đọc được trace đã lưu.") from None
        if row is None or row.role != "assistant":
            return None
        return {
            "message_id": row.id,
            "conversation_id": row.conversation_id,
            "created_at": row.created_at,
            "grounded": row.grounded,
            "rewritten_query": row.rewritten_query,
            "latency_ms": row.latency_ms,
            "tokens_in": row.tokens_in,
            "tokens_out": row.tokens_out,
            "trace": row.rag_trace,
            "source": "postgres",
        }

    async def save(
        self, snapshot: Snapshot, pair: list[MessageOut], working: dict, decision: dict, record: dict | None = None
    ):
        """`record` (trace + số đo) chỉ gắn vào tin nhắn assistant, tin cuối của `pair`."""
        record = record or {}
        try:
            async with self.sessions() as session, session.begin():
                existing = await session.get(Message, pair[0].id)
                if existing:
                    if existing.conversation_id != snapshot.conversation.id or existing.content != pair[0].content:
                        raise BadRequestError("Mã lượt hỏi đã dùng cho nội dung khác.")
                    return False
                conv = snapshot.conversation
                if snapshot.revision == 0:
                    session.add(
                        Conversation(
                            id=conv.id,
                            channel=conv.channel,
                            external_ref=snapshot.external_ref,
                            client_user_ref=snapshot.owner,
                            user_id=snapshot.user_id,
                            created_at=conv.created_at,
                        )
                    )
                    await session.flush()
                    session.add(ConversationRuntime(conversation_id=conv.id, revision=1, state=working))
                else:
                    changed = await session.execute(
                        update(ConversationRuntime)
                        .where(
                            ConversationRuntime.conversation_id == conv.id,
                            ConversationRuntime.revision == snapshot.revision,
                        )
                        .values(revision=snapshot.revision + 1, state=working)
                    )
                    if changed.rowcount != 1:
                        raise UnavailableError("Hội thoại vừa được cập nhật ở lượt khác. Vui lòng thử lại.")
                for m in pair:
                    extra = record if m.role == "assistant" else {}
                    session.add(
                        Message(
                            id=m.id,
                            conversation_id=conv.id,
                            role=m.role,
                            content=m.content,
                            rewritten_query=extra.get("rewritten_query"),
                            sources=[s.model_dump() for s in m.sources],
                            grounded=m.grounded,
                            latency_ms=extra.get("latency_ms"),
                            tokens_in=extra.get("tokens_in"),
                            tokens_out=extra.get("tokens_out"),
                            created_at=m.created_at,
                            trace={
                                "images": [i.model_dump() for i in m.images],
                                "clarification": m.clarification.model_dump(mode="json") if m.clarification else None,
                            },
                            rag_trace=extra.get("trace"),
                        )
                    )
                await session.flush()
                if decision and decision.get("intent") not in {"smalltalk", "cancel", "out_of_scope"}:
                    user = pair[0]
                    topic = decision["resolved_question"] if decision.get("action") == "retrieve" else user.content
                    session.add(
                        ConversationMemory(
                            id=uuid5(conv.id, f"topic:{user.id}"),
                            conversation_id=conv.id,
                            source_message_id=user.id,
                            kind="topic",
                            content=topic,
                            embedding_text=topic,
                            status="active",
                            revision=1,
                            indexed_revision=0,
                            created_at=user.created_at,
                        )
                    )
                    for c in working.get("constraints", []):
                        if c["source_id"] != str(user.id):
                            continue
                        await session.execute(
                            update(ConversationMemory)
                            .where(
                                ConversationMemory.conversation_id == conv.id,
                                ConversationMemory.kind == "fact",
                                ConversationMemory.key == c["key"],
                                ConversationMemory.status == "active",
                            )
                            .values(status="superseded", revision=ConversationMemory.revision + 1)
                        )
                        session.add(
                            ConversationMemory(
                                id=uuid5(conv.id, f"fact:{user.id}:{c['key']}"),
                                conversation_id=conv.id,
                                source_message_id=user.id,
                                kind="fact",
                                key=c["key"],
                                content=c["value"],
                                embedding_text=f"User {c['key']}: {c['value']}. Request: {topic}",
                                status="active",
                                revision=1,
                                indexed_revision=0,
                                created_at=user.created_at,
                            )
                        )
            return True
        except SQLAlchemyError:
            raise UnavailableError("Không lưu được hội thoại; lượt hỏi chưa được xác nhận thành công.") from None

    @staticmethod
    def item(row):
        return {
            "id": str(row.id),
            "source_id": str(row.source_message_id),
            "kind": row.kind,
            "key": row.key,
            "text": row.content,
            "created_at": row.created_at.isoformat(),
            "revision": row.revision,
        }

    async def memories(self, conversation_id: UUID, *, ids=None, recent=False, owner=None):
        try:
            async with self.sessions() as session:
                q = select(ConversationMemory).where(
                    ConversationMemory.conversation_id == conversation_id, ConversationMemory.status == "active"
                )
                if owner is not None:
                    q = q.join(Conversation, Conversation.id == ConversationMemory.conversation_id).where(
                        Conversation.client_user_ref == owner
                    )
                if ids is not None:
                    if not ids:
                        return []
                    q = q.where(ConversationMemory.id.in_([UUID(i) for i in ids]))
                if recent:
                    q = q.where(ConversationMemory.kind == "topic")
                rows = (await session.scalars(q.order_by(ConversationMemory.created_at.desc()).limit(12))).all()
                return [self.item(row) for row in rows[:2] if recent] if recent else [self.item(row) for row in rows]
        except SQLAlchemyError:
            raise UnavailableError("Không đọc được ký ức hội thoại.") from None

    async def pending(self, conversation_id: UUID, limit=16, *, owner=None):
        try:
            async with self.sessions() as session:
                query = select(ConversationMemory).where(
                    ConversationMemory.conversation_id == conversation_id,
                    ConversationMemory.indexed_revision != ConversationMemory.revision,
                    ConversationMemory.index_error.is_(None),
                )
                if owner is not None:
                    query = query.join(Conversation, Conversation.id == ConversationMemory.conversation_id).where(
                        Conversation.client_user_ref == owner
                    )
                return list((await session.scalars(query.order_by(ConversationMemory.created_at).limit(limit))).all())
        except SQLAlchemyError:
            raise UnavailableError("Không đọc được trạng thái chỉ mục ký ức.") from None

    async def mark_indexed(self, memory_id, revision, *, error=None):
        try:
            async with self.sessions() as session, session.begin():
                await session.execute(
                    update(ConversationMemory)
                    .where(ConversationMemory.id == memory_id, ConversationMemory.revision == revision)
                    .values(indexed_revision=revision, index_error=error)
                )
        except SQLAlchemyError:
            raise UnavailableError("Không cập nhật được trạng thái chỉ mục ký ức.") from None

    async def message(self, conversation_id, message_id):
        try:
            async with self.sessions() as session:
                row = await session.get(Message, message_id)
                return row if row and row.conversation_id == conversation_id else None
        except SQLAlchemyError:
            raise UnavailableError("Không đọc được lượt hỏi đã lưu.") from None

    async def rebuild(self, conversation_id):
        try:
            async with self.sessions() as session, session.begin():
                await session.execute(
                    update(ConversationMemory)
                    .where(ConversationMemory.conversation_id == conversation_id)
                    .values(indexed_revision=0, index_error=None)
                )
        except SQLAlchemyError:
            raise UnavailableError("Không chuẩn bị được việc dựng lại ký ức.") from None
