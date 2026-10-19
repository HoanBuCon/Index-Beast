"""AppContext: tài nguyên dùng chung (DB, Qdrant, Redis; S3 thêm encoders, LLM, web search), tạo một lần lúc
khởi động. Test truyền bản giả thay cho tài nguyên thật.

Thêm một tài nguyên mới — chỉ sửa file này:
  1. thêm thuộc tính vào AppContext,
  2. tạo nó trong build_context(),
  3. gọi ctx.register(name, close=..., check=...) để có trong /health và được đóng khi tắt app.

Phụ trách: TV1 · [S1] Skeleton FastAPI · [S3] Endpoint /chat & /chat/stream thật
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from core.config import Settings
from core.db.session import create_engine, create_sessionmaker

log = logging.getLogger(__name__)

HealthCheck = Callable[[], Awaitable[None]]  # ném exception khi tài nguyên không dùng được
Closer = Callable[[], Awaitable[None]]


@dataclass
class AppContext:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    qdrant: AsyncQdrantClient
    redis: Redis
    health_checks: dict[str, HealthCheck] = field(default_factory=dict)
    _closers: list[tuple[str, Closer]] = field(default_factory=list, repr=False)

    def register(self, name: str, *, close: Closer | None = None, check: HealthCheck | None = None) -> None:
        if name in self.health_checks or any(n == name for n, _ in self._closers):
            raise ValueError(f"tài nguyên '{name}' đã được đăng ký")
        if check is not None:
            self.health_checks[name] = check
        if close is not None:
            self._closers.append((name, close))

    async def aclose(self) -> None:
        """Đóng ngược thứ tự đăng ký. Một tài nguyên lỗi chỉ được ghi log, không chặn các tài nguyên còn lại."""
        while self._closers:
            name, close = self._closers.pop()
            try:
                await close()
            except Exception:
                log.exception("failed to close resource", extra={"data": {"resource": name}})


def register_infra(ctx: AppContext) -> None:
    """Đăng ký PostgreSQL, Redis, Qdrant. Test gọi lại hàm này với bản giả để kiểm tra đúng logic production."""

    async def check_postgres() -> None:
        async with ctx.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def check_redis() -> None:
        if not await ctx.redis.ping():
            raise ConnectionError("redis ping returned false")

    async def check_qdrant() -> None:
        await ctx.qdrant.get_collections()

    ctx.register("postgres", close=ctx.engine.dispose, check=check_postgres)
    ctx.register("redis", close=ctx.redis.aclose, check=check_redis)
    ctx.register("qdrant", close=ctx.qdrant.close, check=check_qdrant)


def build_context(settings: Settings) -> AppContext:
    """Chỉ tạo client, chưa mở kết nối: API vẫn khởi động khi một service tạm chết (/health sẽ báo)."""
    timeout = settings.client_timeout_seconds
    engine = create_engine(settings)
    ctx = AppContext(
        settings=settings,
        engine=engine,
        sessionmaker=create_sessionmaker(engine),
        qdrant=AsyncQdrantClient(url=settings.qdrant_url, timeout=max(1, round(timeout))),  # client chỉ nhận số nguyên
        redis=Redis.from_url(
            settings.redis_url, decode_responses=True, socket_timeout=timeout, socket_connect_timeout=timeout
        ),
    )
    register_infra(ctx)
    return ctx
