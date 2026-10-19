"""Fixture dùng chung: Settings test, AppContext giả (không cần service thật). Encoder/LLM giả thêm ở S2–S3.

Phụ trách: Cả team
"""

import asyncio
from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from app.context import AppContext, register_infra
from app.main import create_app
from core.config import Settings


@pytest.fixture
def settings() -> Settings:
    # _env_file=None: không đọc .env của máy dev để test luôn cho cùng kết quả
    return Settings(_env_file=None, environment="test", health_timeout_seconds=0.2)


@dataclass
class FakeService:
    """Giả lập một dependency: chạy bình thường, ném lỗi, hoặc treo (để test timeout)."""

    fail: bool = False
    hang: bool = False
    calls: list[str] = field(default_factory=list)

    async def _act(self, name: str) -> bool:
        self.calls.append(name)
        if self.hang:
            await asyncio.sleep(10)
        if self.fail:
            raise ConnectionError(f"{name} down")
        return True


class FakeEngine(FakeService):
    @asynccontextmanager
    async def connect(self):
        await self._act("connect")
        yield self

    async def execute(self, _stmt) -> None:
        return None

    async def dispose(self) -> None:
        return None


class FakeRedis(FakeService):
    async def ping(self) -> bool:
        return await self._act("ping")

    async def aclose(self) -> None:
        return None


class FakeQdrant(FakeService):
    async def get_collections(self) -> None:
        await self._act("get_collections")

    async def close(self) -> None:
        return None


@pytest.fixture
def fakes() -> dict[str, FakeService]:
    return {"engine": FakeEngine(), "redis": FakeRedis(), "qdrant": FakeQdrant()}


@pytest.fixture
def ctx(settings: Settings, fakes: dict[str, FakeService]) -> AppContext:
    """AppContext với bản giả, đăng ký health check bằng đúng hàm production (register_infra)."""
    context = AppContext(settings=settings, sessionmaker=None, **fakes)  # type: ignore[arg-type]
    register_infra(context)
    return context


@pytest.fixture
def client(settings: Settings, ctx: AppContext) -> Iterator[TestClient]:
    with TestClient(create_app(settings, context=ctx)) as c:
        yield c
