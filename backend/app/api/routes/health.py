"""GET /health: chạy song song mọi health check đã đăng ký trong AppContext, mỗi check có timeout.

200 khi tất cả ổn, 503 khi có tài nguyên lỗi — Docker healthcheck dựa vào mã này.
Thêm tài nguyên cần kiểm tra: đăng ký trong app/context.py, không sửa file này.

Phụ trách: TV1 · [S1] Skeleton FastAPI
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_ctx
from app.api.schemas.health import HealthOut
from app.context import AppContext, HealthCheck

PATH = "/health"

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)


async def _passes(name: str, check: HealthCheck, limit_seconds: float) -> bool:
    try:
        async with asyncio.timeout(limit_seconds):
            await check()
    except Exception as exc:
        log.warning("health check failed", extra={"data": {"resource": name, "error": repr(exc)}})
        return False
    return True


@router.get(PATH, response_model=HealthOut, responses={503: {"model": HealthOut}})
async def health(response: Response, ctx: AppContext = Depends(get_ctx)) -> HealthOut:
    names = list(ctx.health_checks)
    limit = ctx.settings.health_timeout_seconds
    results = await asyncio.gather(*(_passes(name, ctx.health_checks[name], limit) for name in names))
    healthy = all(results)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(status="ok" if healthy else "degraded", checks=dict(zip(names, results, strict=True)))
