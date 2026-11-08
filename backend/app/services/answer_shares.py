"""TV4 · Bản chia sẻ Redis: chỉ một câu trả lời, mã ngẫu nhiên, TTL cố định; không đổi quyền lịch sử."""

import asyncio
import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from app.api.schemas.answer_share import AnswerShareCreated, SharedAnswer
from core.errors import NotFoundError, UnavailableError

SHARE_TTL_SECONDS = 24 * 60 * 60
SHARE_IO_TIMEOUT_SECONDS = 3
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
MAX_SNAPSHOT_BYTES = 1_000_000


def share_key(token: str) -> str:
    # Redis không giữ token thô; URL/API log không chứa token trong path hoặc query.
    return "answer-share:v1:" + hashlib.sha256(token.encode()).hexdigest()


class AnswerShareStore:
    def __init__(self, redis):
        self.redis = redis

    async def create(self, *, question, answer, sources, grounded) -> AnswerShareCreated:
        try:
            snapshot = SharedAnswer(
                question=question,
                answer=answer,
                sources=sources,
                grounded=grounded,
                expires_at=datetime.now(UTC) + timedelta(seconds=SHARE_TTL_SECONDS),
            )
        except ValidationError:
            raise UnavailableError("Câu trả lời chưa thể chia sẻ.") from None
        payload = snapshot.model_dump_json()
        if len(payload.encode()) > MAX_SNAPSHOT_BYTES:
            raise UnavailableError("Câu trả lời quá lớn để tạo bản chia sẻ.")
        token = secrets.token_urlsafe(32)
        try:
            async with asyncio.timeout(SHARE_IO_TIMEOUT_SECONDS):
                saved = await self.redis.set(share_key(token), payload, ex=SHARE_TTL_SECONDS, nx=True)
        except Exception:
            raise UnavailableError("Chưa tạo được link chia sẻ. Vui lòng thử lại sau.") from None
        if not saved:
            raise UnavailableError("Chưa tạo được link chia sẻ. Vui lòng thử lại sau.")
        return AnswerShareCreated(token=token, expires_at=snapshot.expires_at)

    async def read(self, token: str | None) -> SharedAnswer:
        if not token or not TOKEN_PATTERN.fullmatch(token):
            raise NotFoundError("Link chia sẻ không hợp lệ hoặc đã hết hạn.")
        try:
            async with asyncio.timeout(SHARE_IO_TIMEOUT_SECONDS):
                raw = await self.redis.get(share_key(token))
        except Exception:
            raise UnavailableError("Chưa đọc được bản chia sẻ. Vui lòng thử lại sau.") from None
        if not raw:
            raise NotFoundError("Link chia sẻ không hợp lệ hoặc đã hết hạn.")
        try:
            snapshot = SharedAnswer.model_validate_json(raw)
        except Exception:
            raise UnavailableError("Bản chia sẻ không còn đọc được.") from None
        if snapshot.expires_at.tzinfo is None or snapshot.expires_at <= datetime.now(UTC):
            raise NotFoundError("Link chia sẻ không hợp lệ hoặc đã hết hạn.")
        return snapshot
