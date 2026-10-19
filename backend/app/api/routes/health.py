"""GET /health: chạy song song mọi health check đã đăng ký trong AppContext (có timeout).

200 khi tất cả đều ổn, 503 khi có service lỗi — Docker healthcheck dựa vào mã này.
Thêm service cần kiểm tra: đăng ký trong app/context.py, không sửa file này.

Phụ trách: TV1 · [S1] Skeleton FastAPI
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_ctx
from app.api.schemas.health import HealthOut
from app.context import AppContext, HealthCheck

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)


async def _run(name: str, check: HealthCheck, limit_seconds: float) -> bool:
    try:
        async with asyncio.timeout(limit_seconds):
            await check()
        return True
    except Exception as exc:
        log.warning("health check failed", extra={"data": {"service": name, "error": repr(exc)}})
        return False


@router.get("/health", response_model=HealthOut, responses={503: {"model": HealthOut}})
async def health(response: Response, ctx: AppContext = Depends(get_ctx)) -> HealthOut:
    names = list(ctx.health_checks)
    timeout = ctx.settings.health_timeout_seconds
    results = await asyncio.gather(*(_run(n, ctx.health_checks[n], timeout) for n in names))
    healthy = all(results)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(status="ok" if healthy else "degraded", checks=dict(zip(names, results, strict=True)))
