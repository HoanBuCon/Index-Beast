import asyncio
import json
import logging
from time import monotonic

import httpx
import pytest

from app.rag.reranker import JinaReranker
from core.types import Hit


async def test_reorders_candidate_head_and_preserves_original_hits():
    hits = [Hit(str(i), 1.0 - i / 10, {"title": f"title {i}", "text": f"text {i}"}) for i in range(4)]

    def handle(request):
        assert str(request.url) == "https://api.jina.ai/v1/rerank"
        assert request.headers["Authorization"] == "Bearer secret"
        body = json.loads(request.content)
        assert body == {
            "model": "jina-reranker-v2-base-multilingual",
            "query": "question",
            "documents": ["title 0\ntext 0", "title 1\ntext 1", "title 2\ntext 2"],
            "top_n": 3,
            "return_documents": False,
        }
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 0, "relevance_score": 0.2},
                    {"index": 2, "relevance_score": 0.9},
                    {"index": 1, "relevance_score": 0.5},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await JinaReranker("secret", max_candidates=3, client=client).rank("question", hits)
    assert result == [hits[2], hits[1], hits[0], hits[3]]
    assert all(result[i] is hits[j] for i, j in enumerate([2, 1, 0, 3]))


async def test_success_emits_sanitized_structured_outcome(caplog):
    hits = [Hit("a", 0.8, {"text": "private document"}), Hit("b", 0.7)]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json={"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]}
            )
        )
    ) as client:
        with caplog.at_level(logging.INFO):
            result = await JinaReranker("secret", model="test-model", client=client).rank("private query", hits)

    assert result == [hits[1], hits[0]]
    outcome = next(record for record in caplog.records if getattr(record, "event", None) == "reranker_outcome")
    assert {
        "provider": outcome.provider,
        "model": outcome.model,
        "candidate_count": outcome.candidate_count,
        "ranked_count": outcome.ranked_count,
        "status": outcome.status,
        "reason_category": outcome.reason_category,
    } == {
        "provider": "jina",
        "model": "test-model",
        "candidate_count": 2,
        "ranked_count": 2,
        "status": "ok",
        "reason_category": None,
    }
    assert isinstance(outcome.elapsed_ms, float) and outcome.elapsed_ms >= 0
    assert "secret" not in caplog.text and "private" not in caplog.text


@pytest.mark.parametrize(
    "failure,reason",
    [("status", "http_status"), ("timeout", "timeout"), ("invalid", "invalid_response")],
)
async def test_fallback_outcome_has_safe_reason_category(failure, reason, caplog):
    hits = [Hit("a", 0.8), Hit("b", 0.7)]

    def handle(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("secret private query", request=request)
        if failure == "invalid":
            return httpx.Response(200, json={"results": [{"index": 0}]})
        return httpx.Response(429, text="secret private provider body")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with caplog.at_level(logging.WARNING):
            result = await JinaReranker("secret", client=client).rank("private query", hits)

    assert result == hits
    outcome = next(record for record in caplog.records if getattr(record, "event", None) == "reranker_outcome")
    assert outcome.status == "fallback"
    assert outcome.reason_category == reason
    assert outcome.ranked_count == 0
    if failure == "status":
        assert outcome.provider_status_code == 429
    assert "secret" not in caplog.text and "private" not in caplog.text


async def test_cancellation_propagates_and_logs_without_call_state_leaking(caplog):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def handle(_):
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        reranker = JinaReranker("secret", client=client)
        with caplog.at_level(logging.INFO):
            task = asyncio.create_task(reranker.rank("private query", [Hit("a", 1), Hit("b", 0)]))
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    outcome = next(record for record in caplog.records if getattr(record, "event", None) == "reranker_outcome")
    assert outcome.status == "fallback" and outcome.reason_category == "cancelled"
    assert "secret" not in caplog.text and "private" not in caplog.text


async def test_concurrent_calls_keep_outcomes_per_call(caplog):
    async def handle(request):
        body = json.loads(request.content)
        if body["query"] == "slow":
            await asyncio.sleep(0.01)
            return httpx.Response(
                200,
                json={"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.1}]},
            )
        return httpx.Response(429, text="secret provider detail")

    hits = [Hit("a", 0.8), Hit("b", 0.7)]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        reranker = JinaReranker("secret", client=client)
        with caplog.at_level(logging.INFO):
            results = await asyncio.gather(reranker.rank("slow", hits), reranker.rank("fast", hits))

    assert results == [[hits[1], hits[0]], hits]
    outcomes = [record for record in caplog.records if getattr(record, "event", None) == "reranker_outcome"]
    assert len(outcomes) == 2
    observed = {
        (record.status, record.reason_category, record.candidate_count, record.ranked_count) for record in outcomes
    }
    assert observed == {
        ("ok", None, 2, 2),
        ("fallback", "http_status", 2, 0),
    }


@pytest.mark.parametrize(
    "results",
    [
        [{"index": True, "relevance_score": 0.5}, {"index": 1, "relevance_score": 0.4}],
        [{"index": 0, "relevance_score": 0.5}, {"index": 0, "relevance_score": 0.4}],
        [{"index": 0, "relevance_score": 0.5}],
        [{"index": 0, "relevance_score": float("nan")}, {"index": 1, "relevance_score": 0.4}],
        [{"index": 0, "relevance_score": 1.1}, {"index": 1, "relevance_score": 0.4}],
        [{"index": 2, "relevance_score": 0.5}, {"index": 1, "relevance_score": 0.4}],
    ],
)
async def test_invalid_results_fall_back_without_leaking_data(results, caplog):
    hits = [Hit("a", 0.8, {"text": "private document"}), Hit("b", 0.7)]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": results}))
    ) as client:
        with caplog.at_level(logging.WARNING):
            result = await JinaReranker("secret", client=client).rank("private query", hits)
    assert result == hits
    assert "secret" not in caplog.text and "private" not in caplog.text
    assert caplog.records


@pytest.mark.parametrize("failure", ["status", "timeout", "redirect"])
async def test_request_failure_returns_original_order(failure):
    hits = [Hit("a", 0.8), Hit("b", 0.7)]

    def handle(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("secret private query", request=request)
        return httpx.Response(302 if failure == "redirect" else 500, headers={"Location": "https://other.example"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle), follow_redirects=True) as client:
        assert await JinaReranker("secret", client=client).rank("private query", hits) == hits


async def test_zero_or_one_hit_does_not_call_api():
    def handle(_):
        pytest.fail("API must not be called")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        reranker = JinaReranker("secret", client=client)
        assert await reranker.rank("q", []) == []
        hits = [Hit("a", 1.0)]
        assert await reranker.rank("q", hits) == hits


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.waits = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


async def test_token_budget_waits_for_the_window_then_refuses_long_waits():
    from app.rag.reranker import TokenBudget

    clock = FakeClock()
    budget = TokenBudget(100, clock=clock, sleep=clock.sleep)
    first = await budget.acquire(60, max_wait_seconds=5)
    clock.now += 50
    budget.settle(first, 80)  # Jina's real count replaces the estimate
    assert await budget.acquire(30, max_wait_seconds=5) is None  # 80 + 30 > 100 for another 10 s
    assert await budget.acquire(30, max_wait_seconds=15) is not None and clock.waits == [10]
    budget.block(20)
    assert await budget.acquire(1, max_wait_seconds=5) is None


async def test_reranker_keeps_rrf_order_without_calling_when_the_budget_is_spent(caplog):
    hits = [Hit("a", 0.8, {"text": "x" * 300}), Hit("b", 0.7, {"text": "y" * 300})]
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "usage": {"total_tokens": 900},
                "results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        reranker = JinaReranker("secret", client=client, tokens_per_minute=1000, max_wait_seconds=0)
        assert await reranker.rank("q", hits) == [hits[1], hits[0]]
        with caplog.at_level(logging.INFO):
            assert await reranker.rank("q", hits) == hits
    assert len(calls) == 1
    outcome = [r for r in caplog.records if getattr(r, "event", None) == "reranker_outcome"][-1]
    assert (outcome.status, outcome.reason_category) == ("fallback", "rate_budget")


async def test_rate_limited_response_blocks_the_budget_for_retry_after():
    hits = [Hit("a", 0.8, {"text": "a"}), Hit("b", 0.7, {"text": "b"})]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(429, headers={"retry-after": "30"}))
    ) as client:
        reranker = JinaReranker("secret", client=client, tokens_per_minute=100_000, max_wait_seconds=5)
        assert await reranker.rank("q", hits) == hits
    assert reranker.budget.blocked_until - monotonic() > 25


class FakeCrossEncoder:
    def __init__(self, scores=None, error=None, gate=None):
        self.scores, self.error, self.gate, self.calls = scores, error, gate, []

    def rerank(self, query, documents, batch_size):
        self.calls.append((query, list(documents), batch_size))
        if self.gate is not None:
            self.gate.wait(5)
        if self.error:
            raise self.error
        return iter(self.scores[: len(documents)])


async def test_local_reranker_orders_by_score_in_small_batches_and_truncates(caplog):
    from app.rag.reranker import LocalReranker

    hits = [Hit(str(i), 0.5, {"title": f"t{i}", "text": "x" * 500}) for i in range(4)]
    reranker = LocalReranker("m", "cache", max_candidates=3, max_chars=120, batch_size=2)
    reranker._encoder = FakeCrossEncoder([0.1, 2.0, -1.0])
    with caplog.at_level(logging.INFO):
        assert await reranker.rank("q", hits) == [hits[1], hits[0], hits[2], hits[3]]
    _, documents, batch = reranker._encoder.calls[0]
    assert batch == 2 and all(len(doc) == 120 for doc in documents)
    outcome = [r for r in caplog.records if getattr(r, "event", None) == "reranker_outcome"][-1]
    assert (outcome.provider, outcome.status) == ("local", "ok")


async def test_local_reranker_keeps_rrf_order_on_model_error_or_bad_scores():
    from app.rag.reranker import LocalReranker

    hits = [Hit("a", 0.9, {"text": "a"}), Hit("b", 0.8, {"text": "b"})]
    reranker = LocalReranker("m", "cache")
    reranker._encoder = FakeCrossEncoder(error=RuntimeError("onnx"))
    assert await reranker.rank("q", hits) == hits
    reranker._encoder = FakeCrossEncoder([float("nan"), 1.0])
    assert await reranker.rank("q", hits) == hits and not reranker._busy


async def test_timed_out_inference_blocks_new_runs_until_the_worker_really_ends(caplog):
    """Regression 24/11: lượt quá giờ vẫn chạy ngầm; không được cho lượt mới chạy chồng (từng ăn ~18 GB RAM)."""
    import threading

    from app.rag.reranker import LocalReranker

    hits = [Hit("a", 0.9, {"text": "a"}), Hit("b", 0.8, {"text": "b"})]
    gate = threading.Event()
    reranker = LocalReranker("m", "cache", timeout_seconds=0.05)
    reranker._encoder = FakeCrossEncoder([0.1, 0.9], gate=gate)
    with caplog.at_level(logging.INFO):
        assert await reranker.rank("q", hits) == hits  # quá giờ -> RRF
        assert await reranker.rank("q", hits) == hits  # worker cũ còn chạy -> bận, không gọi model lần hai
    assert len(reranker._encoder.calls) == 1
    reasons = [r.reason_category for r in caplog.records if getattr(r, "event", None) == "reranker_outcome"]
    assert reasons[-2:] == ["timeout", "busy"]
    gate.set()
    for _ in range(100):
        if not reranker._busy:
            break
        await asyncio.sleep(0.01)
    assert await reranker.rank("q", hits) == [hits[1], hits[0]]


def test_local_provider_needs_no_jina_key():
    from core.config import Settings

    assert Settings(rag_reranker_enabled=True, rag_reranker_provider="local", jina_api_key=None).reranker_available
    assert not Settings(rag_reranker_enabled=False, rag_reranker_provider="local").reranker_available
