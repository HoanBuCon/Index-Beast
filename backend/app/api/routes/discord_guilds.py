"""API cho bot Discord theo từng server: kênh `/setup` và xóa ký ức `/clear`. Chỉ nhận X-Service-Token.

Backend không kiểm tra quyền admin Discord: bot phải kiểm tra trước khi gọi (backend chỉ tin service token).
Hợp đồng cho TV4: docs/api/discord-guild-tv4.md.

Phụ trách: TV1 · [S5] API server Discord cho bot
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from app.api.deps import get_chat_service
from app.api.errors import ErrorBody
from app.api.guard import is_trusted_service
from app.api.schemas.discord_guild import (
    ChannelsRemoved,
    ClearMemoryRequest,
    ClearMemoryResult,
    GuildChannelOut,
    GuildChannelsOut,
)
from app.services.chat import ChatService
from app.services.discord_guild import GuildChannelStore, GuildMemoryCleaner
from core.errors import UnauthorizedError, UnavailableError

GuildId = Annotated[str, Path(pattern=r"^\d{1,32}$")]
ChannelId = Annotated[str, Path(pattern=r"^\d{1,32}$")]


def require_service(request: Request) -> None:
    if not is_trusted_service(request):
        raise UnauthorizedError("Chỉ dịch vụ bot được gọi API server Discord.")


def get_channel_store(request: Request) -> GuildChannelStore:
    sessionmaker = request.app.state.ctx.sessionmaker
    if sessionmaker is None:
        raise UnavailableError()
    return GuildChannelStore(sessionmaker)


def get_memory_cleaner(request: Request, service: ChatService = Depends(get_chat_service)) -> GuildMemoryCleaner:
    sessionmaker = request.app.state.ctx.sessionmaker
    if sessionmaker is None:
        raise UnavailableError()
    memory = getattr(getattr(service, "pipeline", None), "memory", None)
    return GuildMemoryCleaner(sessionmaker, getattr(memory, "vectors", None), getattr(service, "forget", None))


_ERRORS = {code: {"model": ErrorBody} for code in (401, 422, 503)}

router = APIRouter(prefix="/discord/guilds/{guild_id}", tags=["discord-guild"], dependencies=[Depends(require_service)])


@router.get(
    "/channels", response_model=GuildChannelsOut, responses=_ERRORS, summary="Kênh bot tự trả lời của một server"
)
async def list_channels(guild_id: GuildId, store: GuildChannelStore = Depends(get_channel_store)) -> GuildChannelsOut:
    rows = await store.list(guild_id)
    return GuildChannelsOut(
        guild_id=guild_id, channels=[GuildChannelOut(channel_id=r.channel_id, enabled_at=r.created_at) for r in rows]
    )


@router.put(
    "/channels/{channel_id}",
    response_model=GuildChannelOut,
    responses={409: {"model": ErrorBody}, **_ERRORS},
    summary="Bật một kênh (idempotent)",
)
async def enable_channel(
    guild_id: GuildId, channel_id: ChannelId, store: GuildChannelStore = Depends(get_channel_store)
) -> GuildChannelOut:
    row = await store.enable(guild_id, channel_id)
    return GuildChannelOut(channel_id=row.channel_id, enabled_at=row.created_at)


@router.delete(
    "/channels/{channel_id}", response_model=ChannelsRemoved, responses=_ERRORS, summary="Tắt một kênh (idempotent)"
)
async def disable_channel(
    guild_id: GuildId, channel_id: ChannelId, store: GuildChannelStore = Depends(get_channel_store)
) -> ChannelsRemoved:
    return ChannelsRemoved(deleted=await store.disable(guild_id, channel_id))


@router.delete("/channels", response_model=ChannelsRemoved, responses=_ERRORS, summary="Tắt mọi kênh của server")
async def disable_all_channels(
    guild_id: GuildId, store: GuildChannelStore = Depends(get_channel_store)
) -> ChannelsRemoved:
    return ChannelsRemoved(deleted=await store.disable(guild_id))


@router.post(
    "/memory/clear",
    response_model=ClearMemoryResult,
    responses=_ERRORS,
    summary="Xóa ký ức hội thoại của một người hoặc cả server (idempotent)",
)
async def clear_memory(
    guild_id: GuildId, body: ClearMemoryRequest, cleaner: GuildMemoryCleaner = Depends(get_memory_cleaner)
) -> ClearMemoryResult:
    counts = await cleaner.clear(guild_id, user_hash=body.user_hash if body.scope == "user" else None)
    return ClearMemoryResult(guild_id=guild_id, scope=body.scope, **counts)
