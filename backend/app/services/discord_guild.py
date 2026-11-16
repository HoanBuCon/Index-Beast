"""Cấu hình theo server Discord cho bot (stateless): kênh `/setup` và xóa ký ức `/clear`.

PostgreSQL là nguồn sự thật; điểm ký ức trong Qdrant chỉ là chỉ mục dẫn xuất nên xóa trước, rồi mới xóa dòng PostgreSQL:
lỗi giữa chừng thì gọi lại được (idempotent), không để lại điểm vector mồ côi mà PostgreSQL đã quên.

Phụ trách: TV1 · [S5] API server Discord cho bot
"""

import logging
from collections.abc import Callable, Iterable, Sequence
from typing import Any
from uuid import UUID

import httpx
from qdrant_client.http.exceptions import ApiException, ResponseHandlingException
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.api.schemas.discord_guild import MAX_CHANNELS_PER_GUILD
from core.db.models import Conversation, DiscordGuildChannel
from core.errors import ConflictError, UnavailableError

log = logging.getLogger(__name__)

# Lỗi client Qdrant (HTTP 4xx/5xx, truyền tải) và mạng; lỗi lập trình thì không bị nuốt thành 503
VECTOR_ERRORS = (ApiException, ResponseHandlingException, httpx.HTTPError, OSError)

BATCH = 500  # số hội thoại mỗi lượt xóa: giữ tham số truy vấn và bộ lọc Qdrant nhỏ


class GuildChannelStore:
    def __init__(self, sessionmaker):
        self.sessions = sessionmaker

    async def list(self, guild_id: str) -> list[DiscordGuildChannel]:
        try:
            async with self.sessions() as session:
                query = select(DiscordGuildChannel).where(DiscordGuildChannel.guild_id == guild_id)
                query = query.order_by(DiscordGuildChannel.created_at, DiscordGuildChannel.channel_id)
                return list(await session.scalars(query))
        except SQLAlchemyError:
            raise UnavailableError("Không đọc được cấu hình kênh của server.") from None

    async def enable(self, guild_id: str, channel_id: str) -> DiscordGuildChannel:
        """Bật một kênh; bật lại kênh đã bật là no-op. Quá MAX_CHANNELS_PER_GUILD kênh thì 409."""
        try:
            async with self.sessions() as session, session.begin():
                # Khóa theo server để hai /setup đồng thời không cùng vượt trần
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": f"discord_guild_channels:{guild_id}"},
                )
                row = await session.get(DiscordGuildChannel, (guild_id, channel_id))
                if row is not None:
                    return row
                total = await session.scalar(
                    select(func.count())
                    .select_from(DiscordGuildChannel)
                    .where(DiscordGuildChannel.guild_id == guild_id)
                )
                if (total or 0) >= MAX_CHANNELS_PER_GUILD:
                    raise ConflictError(f"Mỗi server chỉ bật tối đa {MAX_CHANNELS_PER_GUILD} kênh.")
                row = DiscordGuildChannel(guild_id=guild_id, channel_id=channel_id)
                session.add(row)
                await session.flush()
                await session.refresh(row)  # created_at do DB sinh
                return row
        except SQLAlchemyError:
            raise UnavailableError("Không lưu được cấu hình kênh của server.") from None

    async def disable(self, guild_id: str, channel_id: str | None = None) -> int:
        """Tắt một kênh (hoặc mọi kênh khi `channel_id` là None); trả số kênh vừa tắt, 0 nếu chưa bật."""
        try:
            async with self.sessions() as session, session.begin():
                stmt = delete(DiscordGuildChannel).where(DiscordGuildChannel.guild_id == guild_id)
                if channel_id is not None:
                    stmt = stmt.where(DiscordGuildChannel.channel_id == channel_id)
                return (await session.execute(stmt)).rowcount or 0
        except SQLAlchemyError:
            raise UnavailableError("Không cập nhật được cấu hình kênh của server.") from None


def _batches(ids: Sequence[UUID]) -> Iterable[Sequence[UUID]]:
    for start in range(0, len(ids), BATCH):
        yield ids[start : start + BATCH]


class GuildMemoryCleaner:
    """Xóa hội thoại Discord của một server (hoặc của một người trong server) cùng ký ức ngữ nghĩa của chúng."""

    def __init__(self, sessionmaker, vectors=None, forget: Callable[[Iterable[UUID]], Any] | None = None):
        self.sessions, self.vectors, self.forget = sessionmaker, vectors, forget

    async def clear(self, guild_id: str, *, user_hash: str | None = None) -> dict[str, int]:
        """`user_hash` None = cả server. Hội thoại của người dùng có external_ref `discord:channel:<kênh>:<user_hash>`;
        hội thoại thread (`discord:thread:<id>`) dùng chung nhiều người nên chỉ bị xóa khi xóa cả server.

        Mỗi lô: xóa điểm vector, xóa dòng PostgreSQL (messages, feedback, runtime, memories theo ON DELETE CASCADE),
        rồi xóa điểm vector lần nữa: indexer có thể đã đọc dòng `pending` trước khi xóa và upsert sau lần xóa đầu."""
        where = [Conversation.channel == "discord", Conversation.guild_id == guild_id]
        threads = Conversation.external_ref.startswith("discord:thread:", autoescape=True)
        if user_hash is not None:
            where.append(Conversation.external_ref.startswith("discord:channel:", autoescape=True))
            where.append(Conversation.external_ref.endswith(f":{user_hash}", autoescape=True))
        deleted = threads_kept = 0
        try:
            async with self.sessions() as session:
                ids = list((await session.scalars(select(Conversation.id).where(*where))).all())
                if user_hash is not None:
                    threads_kept = await session.scalar(
                        select(func.count())
                        .select_from(Conversation)
                        .where(Conversation.channel == "discord", Conversation.guild_id == guild_id, threads)
                    )
            vectors = self.vectors if ids and self.vectors is not None and await self.vectors.available() else None
            for batch in _batches(ids):
                if vectors is not None:
                    await vectors.delete_conversations(batch)
                async with self.sessions() as session, session.begin():
                    result = await session.execute(delete(Conversation).where(Conversation.id.in_(batch)))
                    deleted += result.rowcount or 0
                if vectors is not None:
                    await vectors.delete_conversations(batch)
                if self.forget is not None:
                    self.forget(batch)
        except SQLAlchemyError:
            raise UnavailableError("Không xóa được ký ức của server. Có thể gọi lại để hoàn tất.") from None
        except VECTOR_ERRORS:
            # Lỗi Qdrant/mạng. Lần xóa đầu lỗi: dòng PostgreSQL của lô chưa bị xóa, gọi lại là xong. Lần hai lỗi:
            # dòng PostgreSQL đã mất nên chỉ còn điểm mồ côi (payload chỉ có ID, không có nội dung chat; recall bỏ qua
            # điểm không có dòng PostgreSQL tương ứng); log này để vận hành biết.
            log.warning(
                "guild memory clear: vector store failed", extra={"data": {"guild_id": guild_id}}, exc_info=True
            )
            raise UnavailableError("Không xóa được ký ức ngữ nghĩa. Có thể gọi lại để hoàn tất.") from None
        return {
            "conversations": deleted,
            "threads_kept": threads_kept or 0,
            "vector_conversations": len(ids) if vectors is not None else 0,
        }
