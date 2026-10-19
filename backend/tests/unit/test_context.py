import logging

import pytest


def test_registered_resource_appears_in_health(ctx, client):
    async def check_llm() -> None:
        raise TimeoutError("deepseek unreachable")

    ctx.register("llm", check=check_llm)

    res = client.get("/api/v1/health")

    assert res.status_code == 503
    assert res.json()["checks"] == {"postgres": True, "redis": True, "qdrant": True, "llm": False}


def test_register_rejects_duplicate_name(ctx):
    with pytest.raises(ValueError, match="redis"):
        ctx.register("redis", close=ctx.redis.aclose)


async def test_aclose_closes_in_reverse_order_and_logs_failures(ctx, caplog):
    order: list[str] = []

    def closer(name: str, fail: bool = False):
        async def close() -> None:
            order.append(name)
            if fail:
                raise RuntimeError("close failed")

        return close

    ctx._closers.clear()
    ctx.register("a", close=closer("a"))
    ctx.register("b", close=closer("b", fail=True))
    ctx.register("c", close=closer("c"))

    with caplog.at_level(logging.ERROR):
        await ctx.aclose()  # không ném lỗi: tắt app phải tiếp tục đóng các tài nguyên còn lại

    assert order == ["c", "b", "a"]
    assert [r.data["resource"] for r in caplog.records] == ["b"]
