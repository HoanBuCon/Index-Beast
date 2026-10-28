"""Chat giả cho Sprint 2: trả câu trả lời cố định có nguồn để web/bot làm song song. S3 thay bằng pipeline RAG thật
(cùng giao diện: answer(), history(), has_message()).

Lệnh thử lỗi cho FE/bot (gõ làm nội dung câu hỏi):
  /mock-ungrounded  → grounded=false, không nguồn
  /mock-error       → 502 upstream_error
  /mock-429         → 429 rate_limited kèm Retry-After
  /mock-slow        → trả sau 5 giây (thử loading/timeout)

Phụ trách: TV1 · [S2] API contract v1
"""

import asyncio
import time
from collections import OrderedDict
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.api.schemas.chat import ChatRequest, ChatResponse, Source
from app.api.schemas.conversation import ConversationOut, MessageOut
from core.errors import NotFoundError, RateLimitedError, UpstreamError

MAX_CONVERSATIONS = 500  # mock giữ trong RAM; quá ngưỡng thì bỏ hội thoại cũ nhất

_SOURCES = [
    Source(
        index=1,
        title="Ranni the Witch",
        section="Lore",
        url="https://eldenring.wiki.gg/wiki/Ranni_the_Witch",
        text="Dữ liệu giả để thử giao diện.",
    ),
    Source(
        index=2,
        title="Night of the Black Knives",
        section="Lore",
        url="https://eldenring.wiki.gg/wiki/Night_of_the_Black_Knives",
        text="Dữ liệu giả để thử giao diện.",
    ),
]
_ANSWER = {
    "vi": "Đây là câu trả lời giả từ máy chủ mock [1]. Nội dung thật sẽ có ở Sprint 3 cùng trích dẫn từ wiki [2].",
    "en": "This is a mock answer from the server [1]. Real content arrives in Sprint 3 with wiki citations [2].",
}
_NO_EVIDENCE = "Mình chưa tìm thấy thông tin này trong dữ liệu lore."


class MockChatService:
    def __init__(self) -> None:
        self._conversations: OrderedDict[UUID, ConversationOut] = OrderedDict()

    async def answer(self, req: ChatRequest) -> ChatResponse:
        start = time.perf_counter()
        command = req.message.strip()
        if command == "/mock-error":
            raise UpstreamError()
        if command == "/mock-429":
            raise RateLimitedError(retry_after=5)
        if command == "/mock-slow":
            await asyncio.sleep(5)

        conversation = self._conversation_for(req)
        grounded = command != "/mock-ungrounded"
        text = _ANSWER["en" if req.options.lang == "en" else "vi"] if grounded else _NO_EVIDENCE
        sources = _SOURCES if grounded else []
        now = datetime.now(UTC)
        conversation.messages.append(MessageOut(id=uuid4(), role="user", content=req.message, created_at=now))
        reply = MessageOut(
            id=uuid4(), role="assistant", content=text, sources=sources, grounded=grounded, created_at=now
        )
        conversation.messages.append(reply)
        return ChatResponse(
            conversation_id=conversation.id,
            message_id=reply.id,
            answer=text,
            sources=sources,
            grounded=grounded,
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
        )

    def history(self, conversation_id: UUID) -> ConversationOut:
        try:
            return self._conversations[conversation_id]
        except KeyError:
            raise NotFoundError("Không tìm thấy hội thoại.") from None

    def has_message(self, message_id: UUID) -> bool:
        return any(m.id == message_id for c in self._conversations.values() for m in c.messages)

    def _conversation_for(self, req: ChatRequest) -> ConversationOut:
        if req.conversation_id is not None:
            return self.history(req.conversation_id)
        conversation = ConversationOut(id=uuid4(), channel=req.channel, created_at=datetime.now(UTC), messages=[])
        self._conversations[conversation.id] = conversation
        while len(self._conversations) > MAX_CONVERSATIONS:
            self._conversations.popitem(last=False)
        return conversation
