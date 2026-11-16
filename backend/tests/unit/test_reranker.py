import asyncio
import json
import logging

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
    outcome = next(record for record in caplog.records if getattr(record, "event", None) == "jina_reranker_outcome")
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
    outcome = next(record for record in caplog.records if getattr(record, "event", None) == "jina_reranker_outcome")
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

    outcome = next(record for record in caplog.records if getattr(record, "event", None) == "jina_reranker_outcome")
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
    outcomes = [record for record in caplog.records if getattr(record, "event", None) == "jina_reranker_outcome"]
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
