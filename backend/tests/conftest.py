"""Fixture dùng chung: Settings cho test và AppContext với tài nguyên giả (không cần service thật).

S2–S3 thêm encoder/LLM giả ở đây.

Phụ trách: Cả team
"""

import asyncio
from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.context import AppContext, register_infra
from app.main import create_app
from core.config import Settings


@pytest.fixture
def settings() -> Settings:
    # _env_file=None: bỏ qua .env của máy dev để test cho cùng kết quả ở mọi nơi
    return Settings(_env_file=None, environment="test", health_timeout_seconds=0.2)


@pytest.fixture(autouse=True)
def disable_remote_tracing(monkeypatch):
    """Offline tests must not export traces because a developer enabled tracing in their shell."""
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


@dataclass
class FakeResource:
    """Tài nguyên giả: hoạt động bình thường, ném lỗi (fail) hoặc treo (hang) để test timeout."""

    fail: bool = False
    hang: bool = False

    async def _respond(self) -> bool:
        if self.hang:
            await asyncio.sleep(10)
        if self.fail:
            raise ConnectionError("resource down")
        return True

    async def close(self) -> None:
        return None


class FakeEngine(FakeResource):
    @asynccontextmanager
    async def connect(self):
        await self._respond()
        yield self

    async def execute(self, _statement) -> None:
        return None

    async def dispose(self) -> None:
        return None


class FakeRedis(FakeResource):
    async def ping(self) -> bool:
        return await self._respond()

    async def aclose(self) -> None:
        return None


class FakeQdrant(FakeResource):
    async def get_collections(self) -> None:
        await self._respond()


@pytest.fixture
def fakes() -> dict[str, FakeResource]:
    return {"engine": FakeEngine(), "redis": FakeRedis(), "qdrant": FakeQdrant()}


@pytest.fixture
def ctx(settings: Settings, fakes: dict[str, FakeResource]) -> AppContext:
    """Đăng ký bằng chính register_infra() của production để test đúng logic thật."""
    context = AppContext(settings=settings, sessionmaker=None, **fakes)  # type: ignore[arg-type]
    register_infra(context)
    return context


@pytest.fixture
def client(settings: Settings, ctx: AppContext) -> Iterator[TestClient]:
    with TestClient(create_app(settings, context=ctx)) as test_client:
        yield test_client
