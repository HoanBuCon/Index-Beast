"""Cấu hình theo server Discord cho bot (stateless): kênh `/setup` và xóa ký ức `/clear`.

PostgreSQL là nguồn sự thật; điểm ký ức trong Qdrant chỉ là chỉ mục dẫn xuất nên xóa trước, rồi mới xóa dòng PostgreSQL:
lỗi giữa chừng thì gọi lại được (idempotent), không để lại điểm vector mồ côi mà PostgreSQL đã quên.

Phụ trách: TV1 · [S5] API server Discord cho bot
"""

from collections.abc import Callable, Iterable, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.api.schemas.discord_guild import MAX_CHANNELS_PER_GUILD
from core.db.models import Conversation, ConversationMemory, DiscordGuildChannel, Feedback, Message
from core.errors import ConflictError, UnavailableError

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
        hội thoại thread (`discord:thread:<id>`) dùng chung nhiều người nên chỉ bị xóa khi xóa cả server."""
        where = [Conversation.channel == "discord", Conversation.guild_id == guild_id]
        if user_hash is not None:
            where.append(Conversation.external_ref.startswith("discord:channel:", autoescape=True))
            where.append(Conversation.external_ref.endswith(f":{user_hash}", autoescape=True))
        totals = {"conversations": 0, "messages": 0, "feedback": 0, "memories": 0, "vector_points": 0}
        try:
            async with self.sessions() as session:
                ids = list((await session.scalars(select(Conversation.id).where(*where))).all())
            for batch in _batches(ids):
                if self.vectors is not None:
                    totals["vector_points"] += await self.vectors.delete_conversations(batch)
                async with self.sessions() as session, session.begin():
                    totals["messages"] += await session.scalar(
                        select(func.count()).select_from(Message).where(Message.conversation_id.in_(batch))
                    )
                    totals["feedback"] += await session.scalar(
                        select(func.count())
                        .select_from(Feedback)
                        .join(Message, Message.id == Feedback.message_id)
                        .where(Message.conversation_id.in_(batch))
                    )
                    totals["memories"] += await session.scalar(
                        select(func.count())
                        .select_from(ConversationMemory)
                        .where(ConversationMemory.conversation_id.in_(batch))
                    )
                    # messages, feedback, conversation_runtime, conversation_memories xóa theo ON DELETE CASCADE
                    result = await session.execute(delete(Conversation).where(Conversation.id.in_(batch)))
                    totals["conversations"] += result.rowcount or 0
                if self.forget is not None:
                    self.forget(batch)
        except SQLAlchemyError:
            raise UnavailableError("Không xóa được ký ức của server. Có thể gọi lại để hoàn tất.") from None
        except UnavailableError:
            raise
        except Exception:
            # Qdrant lỗi: dòng PostgreSQL của lượt này chưa bị xóa nên gọi lại là an toàn
            raise UnavailableError("Không xóa được ký ức ngữ nghĩa. Có thể gọi lại để hoàn tất.") from None
        return totals
