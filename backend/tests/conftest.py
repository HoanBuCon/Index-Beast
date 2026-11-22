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
    """Test offline không được xuất trace chỉ vì lập trình viên bật tracing trong shell của họ."""
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
    """Đủ cho health check và rate-limit (get, pipeline().incr().expire().execute())."""

    async def ping(self) -> bool:
        return await self._respond()

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        await self._respond()
        self.__dict__.setdefault("store", {})[key] = value
        return True

    async def getdel(self, key: str):
        await self._respond()
        return self.__dict__.setdefault("store", {}).pop(key, None)

    async def get(self, key: str):
        await self._respond()
        return self.__dict__.setdefault("counts", {}).get(key)

    def pipeline(self, transaction: bool = True) -> "_FakePipeline":
        self.__dict__.setdefault("counts", {})  # dataclass cha không gọi __post_init__ của lớp con
        return _FakePipeline(self)

    async def aclose(self) -> None:
        return None


class _FakePipeline:
    """Ghi lại lệnh rồi chạy khi execute(), trả kết quả từng lệnh như redis-py (incr/incrby: giá trị mới)."""

    def __init__(self, redis: FakeRedis) -> None:
        self.redis, self.ops = redis, []

    async def __aenter__(self) -> "_FakePipeline":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    def incr(self, key: str) -> "_FakePipeline":
        return self.incrby(key, 1)

    def incrby(self, key: str, amount: int) -> "_FakePipeline":
        self.ops.append(("incrby", key, amount))
        return self

    def get(self, key: str) -> "_FakePipeline":
        self.ops.append(("get", key, None))
        return self

    def expire(self, key: str, seconds: int) -> "_FakePipeline":
        self.ops.append(("expire", key, seconds))
        return self

    async def execute(self) -> list:
        await self.redis._respond()
        counts, results = self.redis.counts, []
        for op, key, value in self.ops:
            if op == "incrby":
                counts[key] = counts.get(key, 0) + value
                results.append(counts[key])
            elif op == "get":
                results.append(counts.get(key))
            else:
                results.append(True)
        self.ops = []
        return results


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
