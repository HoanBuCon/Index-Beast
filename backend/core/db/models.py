"""Bảng ORM theo SRS §6: documents, chunks, entities, conversations, messages, feedback, ingestion_jobs, eval_runs.
Đổi schema → sửa file này rồi `alembic revision --autogenerate -m "..."`, đọc lại file sinh ra trước khi commit.

Quy ước: khóa chính UUID (documents/chunks dùng id ổn định do ingest sinh để upsert idempotent); thời gian là
timestamptz (UTC); enum dạng text + CheckConstraint (đổi giá trị chỉ cần migration, không phải ALTER TYPE).

Phụ trách: TV1 · [S2] Schema PostgreSQL & migrations
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Tên constraint/index cố định để Alembic đổi/xóa được về sau
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

CHANNELS = ("web", "discord")
DOCUMENT_STATUSES = ("active", "excluded", "deleted")
SOURCE_TYPES = ("in_game_text", "wiki_prose", "speculation")
JOB_STATUSES = ("running", "succeeded", "partial", "failed")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _now() -> Any:
    return func.now()


class Document(Base):
    """Một trang nguồn (bản raw đã chọn lọc). Khóa tự nhiên: (source, source_id)."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source", "source_id"),
        CheckConstraint(_in("status", DOCUMENT_STATUSES), name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(Text)  # wikigg, ...
    source_id: Mapped[str] = mapped_column(Text)  # pageid ở nguồn
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    revision_id: Mapped[int | None] = mapped_column(BigInteger)
    game_scope: Mapped[str | None] = mapped_column(Text)  # base; NULL = chưa rà soát (ADR-004)
    raw_hash: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now(), onupdate=_now())

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """Một đoạn đã chia. Metadata theo FR-ING-05 (doc_id, title, url, source nằm ở documents)."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal"),
        CheckConstraint(_in("source_type", SOURCE_TYPES), name="source_type"),
        Index("ix_chunks_game_scope", "game_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)  # uuid5(document_id, ordinal) do ingest sinh
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)  # đường dẫn heading "Cha > Con"
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    game_scope: Mapped[str | None] = mapped_column(Text)  # sao chép từ document để lọc không cần join
    source_type: Mapped[str] = mapped_column(Text, default="wiki_prose", server_default="wiki_prose")
    spoiler_level: Mapped[int | None] = mapped_column(SmallInteger)
    lang: Mapped[str] = mapped_column(Text, default="en", server_default="en")
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now(), onupdate=_now())

    document: Mapped[Document] = relationship(back_populates="chunks")


class Entity(Base):
    """Thực thể chuẩn (boss, npc, location, item…) cho alias và lọc."""

    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("source", "type", "source_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(Text, index=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    type: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(_in("channel", CHANNELS), name="channel"),
        Index("ix_conversations_channel_external_ref", "channel", "external_ref"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    channel: Mapped[str] = mapped_column(Text)
    external_ref: Mapped[str | None] = mapped_column(Text)  # vd. discord:thread:<id>
    client_user_ref: Mapped[str | None] = mapped_column(Text)  # chỉ lưu bản băm (NFR-PRIV-01)
    guild_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(_in("role", ("user", "assistant")), name="role"),
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    rewritten_query: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    grounded: Mapped[bool | None] = mapped_column(Boolean)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    trace: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # dấu vết RAG cho trang admin (S5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )  # không dùng now(): trong một transaction mọi tin sẽ trùng giờ, mất thứ tự

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("rating IN (1, -1)", name="rating"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(SmallInteger)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (CheckConstraint(_in("status", JOB_STATUSES), name="status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(Text, unique=True)  # mã job của CLI, vd. crawl-2301a25ddbc1
    kind: Mapped[str] = mapped_column(Text)  # crawl, clean, chunk, index
    source: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="running", server_default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pages_ok: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pages_failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    log: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # tóm tắt và danh sách lỗi


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    git_sha: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
