"""create_app(): FastAPI + lifespan (tạo/đóng AppContext) + middleware + router.

Chạy: uvicorn --factory app.main:create_app
File này hiếm khi cần sửa. Điểm mở rộng: tài nguyên → app/context.py · endpoint → app/api/routes/ và
app/api/router.py · middleware → app/middleware.py · cấu hình → core/config.py.

Phụ trách: TV1 · [S1] Skeleton FastAPI
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import HEALTH_PATH, api_router
from app.context import AppContext, build_context
from app.middleware import install_middleware
from core.config import Settings, ensure_safe_for_environment, get_settings
from core.logging import setup_logging

log = logging.getLogger("app")


def create_app(settings: Settings | None = None, context: AppContext | None = None) -> FastAPI:
    """`context`: test truyền tài nguyên giả vào; khi đó app không tự đóng chúng."""
    settings = settings or get_settings()
    ensure_safe_for_environment(settings)
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ctx = context or build_context(settings)
        app.state.ctx = ctx
        started = {"environment": settings.environment, "resources": list(ctx.health_checks)}
        log.info("api started", extra={"data": started})
        try:
            yield
        finally:
            if context is None:
                await ctx.aclose()
            log.info("api stopped")

    public_docs = not settings.is_prod  # không công khai Swagger/OpenAPI trên production
    app = FastAPI(
        title="Index Beast API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if public_docs else None,
        openapi_url="/api/openapi.json" if public_docs else None,
        redoc_url=None,
    )
    install_middleware(app, settings, quiet_paths=[HEALTH_PATH])
    app.include_router(api_router)
    return app
