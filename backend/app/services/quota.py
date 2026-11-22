"""Hạn mức hỏi đáp theo ngày (giờ Việt Nam) đếm trong Redis: số câu hỏi và token LLM của từng khách/tài khoản,
cộng một trần token chung cho cả hệ thống.

Kiểm tra (`reserve`) trước khi gọi LLM, ghi token (`charge`) sau khi có câu trả lời, nên ngân sách token có thể vượt
tối đa một câu trả lời. Câu hỏi được tính khi nhận, kể cả khi trả lời lỗi sau đó (chặn được kẻ cố tình gây lỗi).
Admin không đi qua lớp này (xem app.api.guard). Redis lỗi thì từ chối (503): mỗi câu hỏi tốn tiền LLM.

Phụ trách: TV1 · [S5] Hạn mức hỏi đáp (sau sự cố bị dội câu hỏi thật 22/11/2026)
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Literal

from core.config import Settings
from core.errors import QuotaExceededError, UnavailableError

log = logging.getLogger(__name__)

VIETNAM = timezone(timedelta(hours=7))  # Việt Nam không đổi giờ theo mùa
_TTL_SECONDS = 2 * 86400  # giữ bộ đếm qua hết ngày ở mọi múi giờ của client
GLOBAL_KEY = "global"

Kind = Literal["guest", "user", "bot"]


def day_stamp(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(VIETNAM).strftime("%Y%m%d")


def seconds_until_reset(now: datetime | None = None) -> int:
    local = (now or datetime.now(UTC)).astimezone(VIETNAM)
    midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((midnight - local).total_seconds()))


@dataclass(frozen=True)
class Limits:
    questions: int  # 0 = không giới hạn
    tokens: int


class ChatQuota:
    def __init__(self, redis, settings: Settings) -> None:
        self.redis, self.settings = redis, settings

    def limits(self, kind: Kind) -> Limits:
        s = self.settings
        if kind == "guest":
            return Limits(s.chat_guest_daily_questions, s.chat_guest_daily_tokens)
        if kind == "user":
            return Limits(s.chat_user_daily_questions, s.chat_user_daily_tokens)
        return Limits(0, 0)  # bot: giới hạn mỗi phút theo thread/guild ở guard, cộng trần token chung

    async def reserve(self, key: str, kind: Kind) -> None:
        """429 quota_exceeded nếu hết trần chung, token hoặc câu hỏi của `key` hôm nay; không thì tính một câu."""
        limits, day = self.limits(kind), day_stamp()
        budget = self.settings.chat_daily_token_budget
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                used_global, used_tokens = await pipe.get(_tokens(GLOBAL_KEY, day)).get(_tokens(key, day)).execute()
            if budget and int(used_global or 0) >= budget:
                raise QuotaExceededError(_GLOBAL_MESSAGE, retry_after=seconds_until_reset())
            if limits.tokens and int(used_tokens or 0) >= limits.tokens:
                raise QuotaExceededError(_message(kind, self.settings), retry_after=seconds_until_reset())
            if limits.questions:
                questions = _questions(key, day)
                async with self.redis.pipeline(transaction=True) as pipe:
                    count, _ = await pipe.incr(questions).expire(questions, _TTL_SECONDS).execute()
                if count > limits.questions:
                    raise QuotaExceededError(_message(kind, self.settings), retry_after=seconds_until_reset())
        except QuotaExceededError:
            raise
        except Exception:
            log.warning("chat quota unavailable", exc_info=True)
            raise UnavailableError("Không kiểm tra được hạn mức hỏi đáp.") from None

    async def charge(self, key: str, tokens: int) -> None:
        """Cộng token của một câu trả lời vào `key` và trần chung của ngày hiện tại."""
        if tokens <= 0:
            return
        day = day_stamp()
        own, shared = _tokens(key, day), _tokens(GLOBAL_KEY, day)
        async with self.redis.pipeline(transaction=True) as pipe:
            await (
                pipe.incrby(own, tokens)
                .expire(own, _TTL_SECONDS)
                .incrby(shared, tokens)
                .expire(shared, _TTL_SECONDS)
                .execute()
            )


def _tokens(key: str, day: str) -> str:
    return f"quota:tokens:{key}:{day}"


def _questions(key: str, day: str) -> str:
    return f"quota:questions:{key}:{day}"


_GLOBAL_MESSAGE = "Hệ thống đã dùng hết ngân sách trả lời hôm nay. Vui lòng quay lại sau 0 giờ (giờ Việt Nam)."


def _message(kind: Kind, settings: Settings) -> str:
    if kind == "guest":
        more = (
            f" để hỏi {settings.chat_user_daily_questions} câu mỗi ngày" if settings.chat_user_daily_questions else ""
        )
        return (
            f"Đã hết lượt hỏi của khách hôm nay. Đăng nhập bằng Discord{more}, hoặc quay lại sau 0 giờ (giờ Việt Nam)."
        )
    return "Bạn đã dùng hết lượt hỏi hôm nay. Lượt hỏi được làm mới lúc 0 giờ (giờ Việt Nam)."
