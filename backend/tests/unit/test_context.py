import pytest


async def test_new_resource_check_shows_up_in_health(ctx, client):
    async def check_llm() -> None:
        raise TimeoutError("deepseek unreachable")

    ctx.register("llm", check=check_llm)

    res = client.get("/api/v1/health")

    assert res.status_code == 503
    assert res.json()["checks"] == {"postgres": True, "redis": True, "qdrant": True, "llm": False}


async def test_aclose_runs_in_reverse_order_and_survives_errors(ctx):
    order: list[str] = []

    async def ok(name: str) -> None:
        order.append(name)

    async def boom() -> None:
        order.append("boom")
        raise RuntimeError("close failed")

    ctx._closers.clear()
    ctx.register("a", close=lambda: ok("a"))
    ctx.register("b", close=boom)
    ctx.register("c", close=lambda: ok("c"))

    with pytest.raises(ExceptionGroup):
        await ctx.aclose()

    assert order == ["c", "boom", "a"]
