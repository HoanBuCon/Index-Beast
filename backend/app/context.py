"""AppContext: gom tài nguyên dùng chung (DB, Qdrant, Redis, encoders, LLM, web search) tạo một lần lúc khởi động.
Test thay từng phần bằng bản giả.

Thêm một tài nguyên mới (vd. LLM ở S3) — chỉ sửa file này:
  1. thêm thuộc tính vào AppContext,
  2. tạo nó trong build_context(),
  3. gọi ctx.register(name, close=..., check=...) để có health check và được đóng khi tắt app.
Route /health và lifespan tự dùng danh sách đã đăng ký, không cần sửa.

Phụ trách: TV1 · [S1] Skeleton FastAPI · [S3] Endpoint /chat & /chat/stream thật
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from core.config import Settings
from core.db.session import create_engine, create_sessionmaker

HealthCheck = Callable[[], Awaitable[None]]  # ném exception nếu không khoẻ
Closer = Callable[[], Awaitable[None]]


@dataclass
class AppContext:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    qdrant: AsyncQdrantClient
    redis: Redis
    health_checks: dict[str, HealthCheck] = field(default_factory=dict)
    _closers: list[Closer] = field(default_factory=list, repr=False)

    def register(self, name: str, *, close: Closer | None = None, check: HealthCheck | None = None) -> None:
        if check is not None:
            self.health_checks[name] = check
        if close is not None:
            self._closers.append(close)

    async def aclose(self) -> None:
        # Đóng ngược thứ tự tạo; một tài nguyên lỗi không chặn việc đóng các tài nguyên còn lại
        errors: list[BaseException] = []
        for close in reversed(self._closers):
            try:
                await close()
            except Exception as exc:
                errors.append(exc)
        self._closers.clear()
        if errors:
            raise ExceptionGroup("errors while closing AppContext", errors)


def register_infra(ctx: AppContext) -> None:
    """Đăng ký health check + hàm đóng cho PostgreSQL, Redis, Qdrant. Test dùng lại hàm này với bản giả."""

    async def check_postgres() -> None:
        async with ctx.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def check_redis() -> None:
        if not await ctx.redis.ping():
            raise RuntimeError("redis ping returned false")

    async def check_qdrant() -> None:
        await ctx.qdrant.get_collections()

    ctx.register("postgres", close=ctx.engine.dispose, check=check_postgres)
    ctx.register("redis", close=ctx.redis.aclose, check=check_redis)
    ctx.register("qdrant", close=ctx.qdrant.close, check=check_qdrant)


def build_context(settings: Settings) -> AppContext:
    """Chỉ tạo client, chưa mở kết nối: API vẫn khởi động khi một service tạm chết, /health sẽ báo lỗi."""
    engine = create_engine(settings.database_url)
    timeout = settings.health_timeout_seconds
    ctx = AppContext(
        settings=settings,
        engine=engine,
        sessionmaker=create_sessionmaker(engine),
        qdrant=AsyncQdrantClient(url=settings.qdrant_url, timeout=max(1, int(timeout))),
        redis=Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=timeout),
    )
    register_infra(ctx)
    return ctx
