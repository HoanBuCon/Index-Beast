"""Chặn lạm dụng /chat khi mỗi request tốn tiền LLM: xác thực bot bằng service token và giới hạn tần suất bằng Redis.

Khóa giới hạn: bot đã xác thực → theo external_ref (mọi request của bot cùng một IP); còn lại → theo IP client.
Chế độ mock không tốn tiền nên bỏ qua. Redis lỗi thì từ chối (503) thay vì mở cửa cho request không giới hạn.

Phụ trách: TV1 · [S4] Xác thực client, rate-limit (làm sớm ở S2 vì chế độ LLM thật đã chạy)
"""

import hmac
import logging
import time

from fastapi import Request

from app.api.schemas.chat import ChatRequest
from core.config import PLACEHOLDER
from core.errors import RateLimitedError, UnauthorizedError, UnavailableError

SERVICE_TOKEN_HEADER = "X-Service-Token"
WINDOW_SECONDS = 60

log = logging.getLogger(__name__)


def _trusted_service(request: Request) -> bool:
    expected = request.app.state.ctx.settings.api_service_token
    secret = expected.get_secret_value().strip() if expected else ""
    sent = request.headers.get(SERVICE_TOKEN_HEADER, "")
    return bool(secret) and secret != PLACEHOLDER and hmac.compare_digest(sent.encode(), secret.encode())


async def enforce_chat_limits(request: Request, body: ChatRequest) -> None:
    ctx = request.app.state.ctx
    settings = ctx.settings
    if settings.chat_mode == "mock":
        return
    trusted = _trusted_service(request)
    if body.channel == "discord" and not trusted:
        # Không cho giả làm bot để né giới hạn theo IP
        raise UnauthorizedError("Kênh discord cần X-Service-Token hợp lệ.")
    who = f"ref:{body.external_ref or '-'}" if trusted else f"ip:{request.client.host if request.client else '-'}"
    window = int(time.time()) // WINDOW_SECONDS
    key = f"ratelimit:chat:{who}:{window}"
    try:
        async with ctx.redis.pipeline(transaction=True) as pipe:
            count, _ = await pipe.incr(key).expire(key, WINDOW_SECONDS * 2).execute()
    except Exception:
        log.warning("rate limit unavailable", exc_info=True)
        raise UnavailableError("Không kiểm tra được giới hạn tần suất.") from None
    if count > settings.rate_limit_per_minute:
        raise RateLimitedError(retry_after=WINDOW_SECONDS - int(time.time()) % WINDOW_SECONDS)
