"""Offline verification of measurement boundaries, percentile math and explicit inference guard."""

from types import SimpleNamespace

import pytest

from scripts import benchmark_retrieval as benchmark


def test_retrieval_benchmark_needs_explicit_inference_permission(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["benchmark", "--report", str(tmp_path / "report.json")])
    monkeypatch.setattr(benchmark, "get_settings", lambda: pytest.fail("settings/client/model path reached"))
    with pytest.raises(SystemExit) as error:
        benchmark.main()
    assert error.value.code == 2 and not list(tmp_path.iterdir())


def test_nearest_rank_percentile_and_median_exclude_failures_and_handle_no_success():
    rows = [
        {"success": True, "hit_count": 0 if n == 1 else 30, **{m: float(n) for m in benchmark.METRICS}}
        for n in range(1, 31)
    ]
    rows.append({"success": False, "total_retrieve_ms": 0.0})
    result = benchmark.summarize(rows)
    assert result["successful"] == 30 and result["errors"] == 1 and result["empty_successful_results"] == 1
    assert result["total_retrieve_ms"] == {"samples": 30, "min": 1, "median": 15.5, "p95": 29, "max": 30}
    empty = benchmark.summarize([rows[-1]])
    assert empty["total_retrieve_ms"]["median"] is None and empty["total_retrieve_ms"]["samples"] == 0


@pytest.mark.parametrize("fail", [False, True])
async def test_measurement_rows_reset_and_failures_are_not_fast_successes(fail):
    probe = benchmark.Probe()
    probe.metrics["old_metric"] = 123
    probe.query_calls = 99

    class Retriever:
        async def retrieve(self, query, *, spoilers):
            assert query == "synthetic" and spoilers
            with probe.stage("ready_ms"), probe.stage("embedding_ms"), probe.stage("qdrant_ms"):
                if fail:
                    raise RuntimeError("private exception body must not enter report")
                probe.query_calls += 1
            return [SimpleNamespace(id="point", score=0.5, payload={"title": "synthetic"})]

    row = await benchmark.measure_one(
        Retriever(), probe, ("T01", "en", "synthetic"), phase="warm", round_number=1, spoilers=True
    )
    assert row["success"] is not fail and "old_metric" not in row
    assert all(row[m] >= 0 for m in benchmark.METRICS)
    assert "private exception" not in str(row)
    if fail:
        assert row["error_type"] == "RuntimeError"
    else:
        assert row["query_api_calls"] == 1 and row["hit_count"] == 1


async def test_missing_instrumentation_is_failure_not_zero_latency():
    class Retriever:
        async def retrieve(self, query, *, spoilers):
            return []

    row = await benchmark.measure_one(
        Retriever(), benchmark.Probe(), ("T01", "en", "synthetic"), phase="warm", round_number=1, spoilers=True
    )
    assert not row["success"] and row["error_type"] == "ValueError"


async def test_query_timer_wraps_real_client_query_method_only(monkeypatch):
    from qdrant_client import AsyncQdrantClient

    async def query(self, collection, **kwargs):
        assert collection == "synthetic" and kwargs == {"limit": 30}
        return "result"

    monkeypatch.setattr(AsyncQdrantClient, "query_points", query)
    probe = benchmark.Probe()
    client = benchmark.MeasuredClient(location=":memory:", probe=probe)
    try:
        assert await client.query_points("synthetic", limit=30) == "result"
        assert probe.query_calls == 1 and set(probe.metrics) == {"qdrant_ms"}
    finally:
        await client.close()
