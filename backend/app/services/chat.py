"""Chat service contract and bounded in-memory live conversations; no DB migration changes.

Phụ trách: TV3 · [S3] Chat integration
"""

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel

from app.api.schemas.chat import ChatImage, ChatRequest, ChatResponse, DoneEvent, SourcesEvent, StatusEvent, TokenEvent
from app.api.schemas.conversation import ConversationOut, MessageOut
from app.rag.generator import Generated, Prepared
from app.rag.pipeline import ChatPipeline
from core.errors import NotFoundError

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


def notice(lang: str) -> str:
    return (
        "Chế độ LLM: câu trả lời chưa được đối chiếu kho tri thức.\n\n"
        if lang == "vi"
        else "LLM mode: this answer has not been checked against the knowledge base.\n\n"
    )


class LiveChatService:
    def __init__(self, pipeline: ChatPipeline, *, image_catalog=None):
        self.pipeline = pipeline
        self.image_catalog = image_catalog
        self._conversations: OrderedDict[UUID, ConversationState] = OrderedDict()
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
            return state
        # Evict only inactive conversations. This remains a dev memory store, not durable storage.
        if len(self._conversations) >= 500:
            victim = next((k for k, v in self._conversations.items() if not v.lock.locked()), None)
            if victim is None:
                from core.errors import UnavailableError

                raise UnavailableError("Có quá nhiều hội thoại đang hoạt động.")
            del self._conversations[victim]
        conv = ConversationOut(id=uuid4(), channel=req.channel, created_at=datetime.now(UTC), messages=[])
        state = ConversationState(conv, req.external_ref)
        self._conversations[conv.id] = state
        return state

    def _history_for(self, state: ConversationState) -> list[dict]:
        settings = self.pipeline.settings
        rows, size = [], 0
        candidates = (
            state.conversation.messages[-settings.chat_history_messages :] if settings.chat_history_messages else []
        )
        for msg in reversed(candidates):
            if size + len(msg.content) > settings.chat_history_chars:
                break
            rows.append({"role": msg.role, "content": msg.content})
            size += len(msg.content)
        return list(reversed(rows))

    async def _images(self, req, prepared, result) -> list[ChatImage]:
        if self.image_catalog is None or prepared.mode != "rag" or not result.grounded or not result.sources:
            return []
        try:
            resolved = await self.image_catalog.resolve(
                prepared.hits, [s.index for s in result.sources], spoilers=req.options.spoilers
            )
            prepared.trace["images"] = {"returned": len(resolved.images), "excluded": resolved.reasons}
            return resolved.images
        except Exception:
            # Images are optional. Never swallow task cancellation or leak paths/data through errors.
            prepared.trace["images"] = {"returned": 0, "excluded": {"resolver_unavailable": 1}}
            logging.getLogger(__name__).warning("Image resolver unavailable; returning text only")
            return []

    def _save(self, req, state, prepared: Prepared, result: Generated, started: float, images=None) -> ChatResponse:
        answer = (notice(prepared.lang) if prepared.mode == "llm_only" else "") + result.answer
        now = datetime.now(UTC)
        message_id = uuid4()
        state.conversation.messages.extend(
            [
                MessageOut(id=uuid4(), role="user", content=req.message, created_at=now),
                MessageOut(
                    id=message_id,
                    role="assistant",
                    content=answer,
                    sources=result.sources,
                    images=images or [],
                    grounded=result.grounded,
                    created_at=now,
                ),
            ]
        )
        state.conversation.messages[:] = state.conversation.messages[-64:]
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
        )

    async def answer(self, req: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        state = self._state(req)
        async with state.lock:
            prepared = await self.pipeline.prepare(req, self._history_for(state))
            result = await self.pipeline.generator.generate(prepared)
            images = await self._images(req, prepared, result)
            return self._save(req, state, prepared, result, started, images)

    async def open_stream(self, req: ChatRequest) -> ChatEvents:
        """Prepare and prime provider BEFORE sending HTTP headers, then stream actual deltas."""
        started = time.perf_counter()
        state = self._state(req)
        await state.lock.acquire()
        tokens = None
        try:
            prepared = await self.pipeline.prepare(req, self._history_for(state))
            tokens = self.pipeline.generator.stream(prepared)
            first = await anext(tokens)
        except BaseException:
            try:
                if tokens is not None:
                    await tokens.aclose()
            finally:
                state.lock.release()
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
                async with aclosing(tokens):
                    yield "status", StatusEvent(status="generating")
                    if prepared.mode == "llm_only":
                        yield "token", TokenEvent(token=notice(prepared.lang))
                    yield "token", TokenEvent(token=first)
                    async for token in tokens:
                        yield "token", TokenEvent(token=token)
                    result = prepared.trace["result"]
                    images = await self._images(req, prepared, result)
                    response = self._save(req, state, prepared, result, started, images)
                    yield "sources", SourcesEvent(sources=response.sources, images=response.images)
                    yield "done", DoneEvent.model_validate(response, from_attributes=True)
            finally:
                await cleanup()

        return ManagedEvents(events(), cleanup)
