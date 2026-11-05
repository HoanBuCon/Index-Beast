"""Chat service contract and bounded in-memory live conversations; no DB migration changes.

Phụ trách: TV3 · [S3] Chat integration
"""

import asyncio
import logging
import secrets
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import BaseModel

from app.api.schemas.chat import ChatImage, ChatRequest, ChatResponse, DoneEvent, SourcesEvent, StatusEvent, TokenEvent
from app.api.schemas.conversation import ConversationOut, MessageOut
from app.rag.generator import Generated, Prepared
from app.rag.pipeline import ChatPipeline
from app.rag.semantic_memory import MemoryScope
from app.services.memory_repository import MemoryRepository, Snapshot, owner_hash
from core.errors import BadRequestError, NotFoundError, TimeoutAppError, UnauthorizedError, UnavailableError

ChatEvents = AsyncIterator[tuple[str, BaseModel]]


class ManagedEvents:
    """Can close a primed provider even if the SSE consumer never starts iterating."""

    def __init__(self, events: ChatEvents, cleanup: Callable[[], Awaitable[None]]):
        self.events, self.cleanup = events, cleanup

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await anext(self.events)

    async def aclose(self):
        try:
            await self.events.aclose()
        finally:
            await self.cleanup()


class ChatService(Protocol):
    async def answer(self, req: ChatRequest) -> ChatResponse: ...
    async def open_stream(self, req: ChatRequest) -> ChatEvents: ...
    def history(self, conversation_id: UUID) -> ConversationOut: ...
    def has_message(self, message_id: UUID) -> bool: ...


@dataclass
class ConversationState:
    conversation: ConversationOut
    external_ref: str | None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    player: object = None
    owner: str = ""
    revision: int = 0
    token: str | None = field(default=None, repr=False)


def notice(lang: str) -> str:
    return (
        "Chế độ LLM: câu trả lời chưa được đối chiếu kho tri thức.\n\n"
        if lang == "vi"
        else "LLM mode: this answer has not been checked against the knowledge base.\n\n"
    )


class LiveChatService:
    def __init__(self, pipeline: ChatPipeline, *, image_catalog=None, gameplay_enabled=False, repository=None):
        self.pipeline = pipeline
        self.image_catalog = image_catalog
        self.gameplay_enabled = gameplay_enabled
        self.repository: MemoryRepository | None = repository
        self._registry_lock = asyncio.Lock()
        self._conversations: OrderedDict[UUID, ConversationState] = OrderedDict()
        # (channel, external_ref) → hội thoại: bot không giữ conversation_id, nên mỗi thread hoặc user Discord
        # dùng lại một hội thoại
        self._by_ref: dict[tuple[str, str], UUID] = {}
        self.traces: OrderedDict[UUID, dict] = OrderedDict()

    def history(self, conversation_id: UUID) -> ConversationOut:
        if conversation_id not in self._conversations:
            raise NotFoundError("Không tìm thấy hội thoại.")
        return self._conversations[conversation_id].conversation.model_copy(deep=True)

    def has_message(self, message_id: UUID) -> bool:
        return any(
            m.id == message_id and m.role == "assistant"
            for s in self._conversations.values()
            for m in s.conversation.messages
        )

    def _state(self, req: ChatRequest) -> ConversationState:
        if req.conversation_id is not None:
            state = self._conversations.get(req.conversation_id)
            if state is None or state.conversation.channel != req.channel or state.external_ref != req.external_ref:
                raise NotFoundError("Không tìm thấy hội thoại.")
            self._conversations.move_to_end(req.conversation_id)
            return state
        ref = (req.channel, req.external_ref) if req.external_ref else None
        if ref is not None and (existing := self._by_ref.get(ref)) in self._conversations:
            self._conversations.move_to_end(existing)
            return self._conversations[existing]
        # Evict only inactive conversations, ít dùng gần đây nhất trước. Kho RAM cho dev; S3 chuyển sang PostgreSQL.
        if len(self._conversations) >= 500:
            victim = next((k for k, v in self._conversations.items() if not v.lock.locked()), None)
            if victim is None:
                raise UnavailableError("Có quá nhiều hội thoại đang hoạt động.")
            evicted = self._conversations.pop(victim)
            if evicted.external_ref:
                self._by_ref.pop((evicted.conversation.channel, evicted.external_ref), None)
        conv = ConversationOut(id=uuid4(), channel=req.channel, created_at=datetime.now(UTC), messages=[])
        state = ConversationState(conv, req.external_ref)
        self._conversations[conv.id] = state
        if ref is not None:
            self._by_ref[ref] = conv.id
        return state

    async def _load_state(self, req):
        if self.repository is None:
            return self._state(req)
        if req.channel == "web" and req.external_ref is not None:
            raise BadRequestError("Web dùng conversation token, không dùng external_ref làm danh tính.")
        async with self._registry_lock:
            stored = await self.repository.load(
                req.conversation_id, channel=req.channel, external_ref=req.external_ref, token=req.conversation_token
            )
            if stored:
                if stored.conversation.id not in self._conversations:
                    if len(self._conversations) >= 500:
                        victim = next(
                            (key for key, value in self._conversations.items() if not value.lock.locked()), None
                        )
                        if victim is None:
                            raise UnavailableError("Có quá nhiều hội thoại đang hoạt động.")
                        evicted = self._conversations.pop(victim)
                        if evicted.external_ref:
                            self._by_ref.pop((evicted.conversation.channel, evicted.external_ref), None)
                    self._conversations[stored.conversation.id] = ConversationState(
                        stored.conversation,
                        stored.external_ref,
                        player=stored.working,
                        owner=stored.owner,
                        revision=stored.revision,
                    )
                state = self._conversations[stored.conversation.id]
                state.token = req.conversation_token
                return state
            # A new durable conversation receives a random capability. Only its hash enters PostgreSQL.
            state = self._state(req)
            if not state.owner:
                if req.channel == "web":
                    state.token = secrets.token_urlsafe(32)
                    state.owner = owner_hash(state.token)
                else:
                    if not req.external_ref:
                        raise BadRequestError("Discord cần external_ref cho hội thoại lưu bền.")
                    state.owner = owner_hash(req.external_ref)
                    old_id = state.conversation.id
                    state.conversation.id = uuid5(NAMESPACE_URL, "indexbeast:" + state.owner)
                    self._conversations.pop(old_id, None)
                    self._conversations[state.conversation.id] = state
                    self._by_ref[(req.channel, req.external_ref)] = state.conversation.id
            return state

    async def _refresh(self, state, req):
        if self.repository is None or state.revision == 0:
            return
        stored = await self.repository.load(
            state.conversation.id, channel=req.channel, external_ref=req.external_ref, token=req.conversation_token
        )
        state.conversation, state.player, state.revision = stored.conversation, stored.working, stored.revision

    async def stored_history(self, conversation_id, *, token=None, trusted_service=False):
        if self.repository is None:
            return self.history(conversation_id)
        # Read the channel/ref by ID internally, but never return messages before capability/service auth.
        from core.db.models import Conversation

        try:
            async with self.repository.sessions() as session:
                conv = await session.get(Conversation, conversation_id)
                if conv is None:
                    raise NotFoundError("Không tìm thấy hội thoại.")
                channel, external_ref = conv.channel, conv.external_ref
        except NotFoundError:
            raise
        except Exception:
            raise UnavailableError("Không đọc được hội thoại.") from None
        if channel == "discord" and not trusted_service:
            raise UnauthorizedError("Cần service token để đọc hội thoại Discord.")
        stored = await self.repository.load(conversation_id, channel=channel, external_ref=external_ref, token=token)
        return stored.conversation

    async def stored_has_message(self, message_id, *, token=None, trusted_service=False):
        if self.repository is None:
            return self.has_message(message_id)
        from core.db.models import Message

        try:
            async with self.repository.sessions() as session:
                row = await session.get(Message, message_id)
                if row is None or row.role != "assistant":
                    return False
                conversation_id = row.conversation_id
        except Exception:
            raise UnavailableError("Không kiểm tra được câu trả lời đã lưu.") from None
        await self.stored_history(conversation_id, token=token, trusted_service=trusted_service)
        return True

    def _history_for(self, state: ConversationState) -> list[dict]:
        # Search the bounded conversation BEFORE applying model-input budgets.
        # Existing channel/external_ref routing checks remain in _state. No global or
        # cross-conversation lookup; a web conversation UUID is NOT verified account ownership.
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "message_id": str(msg.id),
                "created_at": msg.created_at.isoformat(),
                "conversation_id": str(state.conversation.id),
            }
            for msg in state.conversation.messages[-64:]
        ]

    async def _images(self, req, prepared, result) -> list[ChatImage]:
        if self.image_catalog is None or prepared.mode != "rag" or not result.grounded or not result.sources:
            return []
        try:
            resolved = await self.image_catalog.resolve(
                prepared.hits, [s.index for s in result.sources if s.origin != "web"], spoilers=req.options.spoilers
            )
            prepared.trace["images"] = {"returned": len(resolved.images), "excluded": resolved.reasons}
            return resolved.images
        except Exception:
            # Images are optional. Never swallow task cancellation or leak paths/data through errors.
            prepared.trace["images"] = {"returned": 0, "excluded": {"resolver_unavailable": 1}}
            logging.getLogger(__name__).warning("Image resolver unavailable; returning text only")
            return []

    async def _prepare(self, req, state):
        kwargs = {"gameplay": True, "handle_gameplay": True, "player": state.player} if self.gameplay_enabled else {}
        if self.repository is not None:
            kwargs["memory_scope"] = MemoryScope(state.conversation.id, state.owner)
            kwargs["player"] = state.player
        prepared = await self.pipeline.prepare(req, self._history_for(state), **kwargs)
        return prepared, prepared.player_state

    async def _save(
        self, req, state, prepared: Prepared, result: Generated, started: float, images=None, player=None
    ) -> ChatResponse:
        answer = (notice(prepared.lang) if prepared.mode == "llm_only" else "") + result.answer
        now = datetime.now(UTC)
        user_id = uuid5(state.conversation.id, f"user:{req.turn_id}") if req.turn_id else uuid4()
        message_id = uuid5(state.conversation.id, f"assistant:{req.turn_id}") if req.turn_id else uuid4()
        pair = [
            MessageOut(id=user_id, role="user", content=req.message, created_at=now),
            MessageOut(
                id=message_id,
                role="assistant",
                content=answer,
                sources=result.sources,
                images=images or [],
                grounded=result.grounded,
                clarification=prepared.clarification,
                created_at=now + timedelta(microseconds=1),
            ),
        ]
        if self.repository is not None:
            working = dict(player) if isinstance(player, dict) else {}
            working["constraints"] = [
                {**c, "source_id": str(user_id) if c["source_id"] == "current" else c["source_id"]}
                for c in working.get("constraints", [])
            ]
            snapshot = Snapshot(state.conversation, state.external_ref, state.owner, state.revision, working)
            created = await self.repository.save(snapshot, pair, working, prepared.agent_decision)
            if not created:
                replay = await self._replay(req, state, started)
                if replay is None:
                    raise UnavailableError("Không khôi phục được lượt hỏi trùng.")
                return replay
            state.revision += 1
            player = working
        state.conversation.messages.extend(pair)
        state.conversation.messages[:] = state.conversation.messages[-64:]
        if player is not None:
            state.player = player
        if self.repository is not None and self.pipeline.memory is not None:
            try:
                async with asyncio.timeout(self.pipeline.settings.chat_memory_timeout_seconds):
                    prepared.trace["memory_sync"] = await self.pipeline.memory.sync(
                        MemoryScope(state.conversation.id, state.owner)
                    )
            except TimeoutError:
                prepared.trace["memory_sync"] = {"status": "pending"}
        trace = {k: v for k, v in prepared.trace.items() if k != "result"}
        trace["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        self.traces[message_id] = trace
        if len(self.traces) > 1000:
            self.traces.popitem(last=False)
        return ChatResponse(
            conversation_id=state.conversation.id,
            message_id=message_id,
            answer=answer,
            sources=result.sources,
            grounded=result.grounded,
            latency_ms=trace["latency_ms"],
            images=images or [],
            clarification=prepared.clarification,
            conversation_token=state.token if self.repository is not None and req.channel == "web" else None,
        )

    async def answer(self, req: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        try:
            # Hạn tổng cho cả chờ khóa, LLM (kể cả retry) và ảnh: bot bỏ cuộc ở 60 s, backend phải dừng trước
            async with asyncio.timeout(self.pipeline.settings.chat_timeout_seconds):
                state = await self._load_state(req)
                async with state.lock:
                    await self._refresh(state, req)
                    if replay := await self._replay(req, state, started):
                        return replay
                    prepared, player = await self._prepare(req, state)
                    result = await self.pipeline.generator.generate(prepared)
                    images = await self._images(req, prepared, result)
                    return await self._save(req, state, prepared, result, started, images, player)
        except TimeoutError:
            raise TimeoutAppError() from None

    async def open_stream(self, req: ChatRequest) -> ChatEvents:
        """Prepare and prime provider BEFORE sending HTTP headers, then stream actual deltas."""
        started = time.perf_counter()
        deadline = asyncio.get_running_loop().time() + self.pipeline.settings.chat_timeout_seconds
        owns_lock = False
        tokens = None
        try:
            async with asyncio.timeout_at(deadline):
                state = await self._load_state(req)
                await state.lock.acquire()
                owns_lock = True
                await self._refresh(state, req)
                replay = await self._replay(req, state, started)
                if replay is not None:

                    async def replay_tokens():
                        yield replay.answer

                    prepared = Prepared(self.pipeline.settings.chat_mode, "vi", [], static_answer=replay.answer)
                    prepared.trace["result"] = Generated(replay.answer, replay.sources, replay.grounded)
                    player = state.player
                    tokens = replay_tokens()
                    first = await anext(tokens)
                else:
                    prepared, player = await self._prepare(req, state)
                    tokens = self.pipeline.generator.stream(prepared)
                    first = await anext(tokens)
        except BaseException as exc:
            try:
                if tokens is not None:
                    await tokens.aclose()
            finally:
                if owns_lock:
                    state.lock.release()
            if isinstance(exc, TimeoutError):
                raise TimeoutAppError() from None
            raise

        closed = False

        async def cleanup():
            nonlocal closed
            if not closed:
                closed = True
                try:
                    await tokens.aclose()
                finally:
                    state.lock.release()

        async def events():
            try:
                async with asyncio.timeout_at(deadline), aclosing(tokens):
                    yield "status", StatusEvent(status="generating")
                    if prepared.mode == "llm_only":
                        yield "token", TokenEvent(token=notice(prepared.lang))
                    yield "token", TokenEvent(token=first)
                    async for token in tokens:
                        yield "token", TokenEvent(token=token)
                    result = prepared.trace["result"]
                    images = await self._images(req, prepared, result)
                    response = replay or await self._save(req, state, prepared, result, started, images, player)
                    yield (
                        "sources",
                        SourcesEvent(
                            sources=response.sources, images=response.images, clarification=response.clarification
                        ),
                    )
                    yield "done", DoneEvent.model_validate(response, from_attributes=True)
            except TimeoutError:
                raise TimeoutAppError() from None
            finally:
                await cleanup()

        return ManagedEvents(events(), cleanup)

    async def _replay(self, req, state, started):
        if self.repository is None or req.turn_id is None:
            return None
        user_id = uuid5(state.conversation.id, f"user:{req.turn_id}")
        user = await self.repository.message(state.conversation.id, user_id)
        if user is None:
            return None
        if user.content != req.message:
            raise BadRequestError("Mã lượt hỏi đã dùng cho nội dung khác.")
        row = await self.repository.message(
            state.conversation.id, uuid5(state.conversation.id, f"assistant:{req.turn_id}")
        )
        if row is None:
            raise UnavailableError("Lượt hỏi đã lưu chưa hoàn chỉnh.")
        return ChatResponse(
            conversation_id=state.conversation.id,
            message_id=row.id,
            answer=row.content,
            sources=row.sources,
            grounded=bool(row.grounded),
            latency_ms=(time.perf_counter() - started) * 1000,
            images=(row.trace or {}).get("images", []),
            clarification=(row.trace or {}).get("clarification"),
            conversation_token=state.token if req.channel == "web" else None,
        )
