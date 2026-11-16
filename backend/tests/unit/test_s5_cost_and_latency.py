"""scripts/llm_cost, scripts/trace_latency và loadtest/helpers: tính tiền, p50/p95 từng bước, golden set, khung SSE.
Không cần PostgreSQL hay locust: phần truy vấn DB dùng sessionmaker giả.

Phụ trách: TV3 (do TV1 dựng hộ) · [S5] Load test, chi phí LLM
"""

import asyncio
import json
from argparse import Namespace
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from loadtest import helpers
from scripts import llm_cost, trace_latency

PRICES = llm_cost.Prices(input_per_m=1.0, output_per_m=2.0, search_each=0.01)


def at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 11, day, hour, tzinfo=UTC)


def test_cost_of_applies_price_per_million_tokens_and_per_search():
    assert llm_cost.cost_of(2_000_000, 500_000, 3, PRICES) == pytest.approx(2.0 + 1.0 + 0.03)


def test_web_search_calls_prefers_agent_actions_then_pipeline_status():
    agent = {"tool_actions": [{"action": "web_search"}, {"action": "search"}, {"action": "web_search"}]}
    assert llm_cost.web_search_calls(agent) == 2
    assert llm_cost.web_search_calls({"tool_actions": [], "web_search": {"status": "ok"}}) == 1
    assert llm_cost.web_search_calls({"web_search": {"status": "not_run"}}) == 0
    assert llm_cost.web_search_calls(None) == 0


def test_aggregate_groups_by_utc_day_and_ignores_missing_tokens():
    utc_plus7 = datetime(2026, 11, 2, 8, tzinfo=timezone(timedelta(hours=7)))  # = 01:00 ngày 2 theo UTC
    rows = [
        (at(1), 1_000_000, 100_000, 1),
        (at(1, 23), None, None, 0),  # câu trả lời có sẵn: không gọi LLM
        (at(2), 500_000, 50_000, 0),
        (utc_plus7, True, -5, 0),  # giá trị bẩn bị bỏ qua
    ]
    report = llm_cost.aggregate(rows, PRICES)
    assert [d["date"] for d in report] == ["2026-11-01", "2026-11-02"]
    first, second = report
    assert (first["questions"], first["tokens_in"], first["tokens_out"], first["searches"]) == (
        2,
        1_000_000,
        100_000,
        1,
    )
    assert first["usd"] == pytest.approx(1.0 + 0.2 + 0.01)
    assert second["questions"] == 2 and second["tokens_in"] == 500_000
    assert second["tokens_in"] == 500_000


def test_projection_uses_average_cost_per_question():
    report = [{"date": "2026-11-01", "questions": 100, "tokens_in": 0, "tokens_out": 0, "searches": 0, "usd": 0.5}]
    summary = llm_cost.project(report, questions_per_day=1000)
    assert summary["usd_per_question"] == pytest.approx(0.005)
    assert summary["projected_monthly_usd"] == pytest.approx(150.0)
    assert summary["within_target"] is False
    cheap = [{**report[0], "usd": 0.05}]
    assert llm_cost.project(cheap)["within_target"] is True  # 0,0005 x 1000 x 30 = $15
    assert llm_cost.project([])["within_target"] is False  # chưa có dữ liệu thì không được báo đạt


def test_render_reports_verdict_and_empty_window():
    report = llm_cost.aggregate([(at(1), 100, 100, 0)], PRICES)  # 0,0003 USD/câu: dưới mục tiêu
    text = llm_cost.render(report, llm_cost.project(report), PRICES)
    assert "2026-11-01" in text and "ĐẠT" in text
    assert "không có tin nhắn" in llm_cost.render([], llm_cost.project([]), PRICES)


def test_parse_window_days_and_explicit_dates():
    now = datetime(2026, 11, 16, 8, tzinfo=UTC)
    since, until = llm_cost.parse_window(Namespace(days=7, since=None, until=None), now)
    assert until == datetime(2026, 11, 17, tzinfo=UTC) and until - since == timedelta(days=7)
    since, until = llm_cost.parse_window(Namespace(days=7, since="2026-11-10", until="2026-11-12"), now)
    assert (since.day, until.day) == (10, 12)
    for bad in (Namespace(days=7, since="x", until=None), Namespace(days=7, since="2026-11-12", until="2026-11-10")):
        with pytest.raises(SystemExit):
            llm_cost.parse_window(bad, now)


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt):
        self.statement = stmt
        return SimpleNamespace(all=lambda: self.rows)

    async def scalars(self, stmt):
        self.statement = stmt
        return SimpleNamespace(all=lambda: self.rows)


def test_cost_fetch_rows_maps_database_rows():
    row = SimpleNamespace(
        created_at=at(1), tokens_in=10, tokens_out=5, tool_actions=[{"action": "web_search"}], web_search=None
    )
    session = FakeSession([row])
    rows = asyncio.run(llm_cost.fetch_rows(lambda: session, at(1), at(2)))
    assert rows == [(at(1), 10, 5, 1)]
    sql = str(session.statement)
    assert "messages.role" in sql and "messages.created_at" in sql


def test_percentile_interpolates():
    assert trace_latency.percentile([10], 95) == 10
    assert trace_latency.percentile([1, 2, 3, 4], 50) == 2.5
    assert trace_latency.percentile(list(range(1, 101)), 95) == pytest.approx(95.05)


def full_trace(**over):
    base = {
        "prepare_ms": 400.0,
        "rewrite": {"elapsed_ms": 120.0},
        "agent": {"elapsed_ms": 200.0},
        "retrieval_queries": [{"elapsed_ms": 30.0}, {"elapsed_ms": 50.0}],
        "tool_actions": [{"action": "web_search", "elapsed_ms": 700.0}, {"action": "web_search", "elapsed_ms": 300.0}],
    }
    return {**base, **over}


def test_step_timings_extracts_every_step():
    steps = trace_latency.step_timings(5000.0, full_trace())
    assert steps == {
        "total": 5000.0,
        "prepare": 400.0,
        "generate_rest": 4600.0,
        "rewrite": 120.0,
        "agent_decision": 200.0,
        "retrieval": 80.0,
        "tool:web_search": 1000.0,
    }


def test_step_timings_tolerates_missing_truncated_or_dirty_traces():
    assert trace_latency.step_timings(None, None) == {}
    assert trace_latency.step_timings(900.0, {"truncated": True, "bytes": 99999}) == {"total": 900.0}
    dirty = {
        "prepare_ms": "x",
        "rewrite": "oops",
        "retrieval_queries": [None, {"elapsed_ms": True}, {"elapsed_ms": -1}],
    }
    assert trace_latency.step_timings(10.0, dirty) == {"total": 10.0}
    assert "generate_rest" not in trace_latency.step_timings(100.0, {"prepare_ms": 400.0})  # prepare > total: bỏ


def test_summarize_orders_by_p95_and_counts_per_step():
    rows = [(1000.0 * i, full_trace() if i % 2 else None) for i in range(1, 11)]
    table = trace_latency.summarize(rows)
    assert list(table)[0] == "total"
    assert table["total"]["n"] == 10 and table["prepare"]["n"] == 5
    assert table["total"]["p50"] == pytest.approx(5500.0)
    assert table["retrieval"] == {"n": 5, "p50": 80.0, "p95": 80.0, "max": 80.0}
    assert "total" in trace_latency.render(table, 10, 0)
    assert "không có trace" in trace_latency.render({}, 0, 0)


def test_latency_fetch_rows_selects_only_latency_and_trace_columns():
    row = SimpleNamespace(latency_ms=12.5, rag_trace={"prepare_ms": 1.0})
    session = FakeSession([row])
    rows = asyncio.run(trace_latency.fetch_rows(lambda: session, at(1), at(2), 10))
    assert rows == [(12.5, {"prepare_ms": 1.0})]
    columns = [c.name for c in session.statement.selected_columns]
    assert columns == ["latency_ms", "rag_trace"]
    assert "messages.latency_ms IS NOT NULL" in str(session.statement)


def sql_of(session):
    return str(session.statement.compile(compile_kwargs={"literal_binds": True}))


def test_loadtest_conversations_are_excluded_by_default_in_both_reports():
    cost = FakeSession([])
    asyncio.run(llm_cost.fetch_rows(lambda: cost, at(1), at(2)))
    latency = FakeSession([])
    asyncio.run(trace_latency.fetch_rows(lambda: latency, at(1), at(2), 10))
    for session in (cost, latency):
        sql = sql_of(session)
        assert "JOIN conversations" in sql
        assert "conversations.external_ref IS NULL" in sql and "conversations.external_ref NOT LIKE" in sql
        assert "loadtest:" in sql


def test_include_loadtest_removes_the_filter_and_the_join():
    cost = FakeSession([])
    asyncio.run(llm_cost.fetch_rows(lambda: cost, at(1), at(2), include_loadtest=True))
    latency = FakeSession([])
    asyncio.run(trace_latency.fetch_rows(lambda: latency, at(1), at(2), 10, include_loadtest=True))
    for session in (cost, latency):
        assert "conversations" not in sql_of(session)


def test_include_loadtest_flag_is_shared_by_both_clis():
    import argparse

    parser = argparse.ArgumentParser()
    llm_cost.add_window_args(parser)
    assert parser.parse_args([]).include_loadtest is False
    assert parser.parse_args(["--include-loadtest"]).include_loadtest is True


def test_parse_window_rejects_until_without_since():
    with pytest.raises(SystemExit, match="--since"):
        llm_cost.parse_window(Namespace(days=7, since=None, until="2026-11-12"))


def test_parse_window_converts_aware_values_to_utc_and_treats_naive_as_utc():
    since, until = llm_cost.parse_window(
        Namespace(days=7, since="2026-11-10T02:00:00+07:00", until="2026-11-11T00:00:00"),
        datetime(2026, 11, 16, tzinfo=UTC),
    )
    assert since == datetime(2026, 11, 9, 19, tzinfo=UTC) and since.utcoffset() == timedelta(0)
    assert until == datetime(2026, 11, 11, tzinfo=UTC)


def test_failure_label_separates_rate_limiting():
    assert helpers.failure_label(429) == "rate_limited"
    assert helpers.failure_label(502) == "HTTP 502"


def test_load_questions_reads_jsonl_and_skips_bad_rows(tmp_path):
    path = tmp_path / "g.jsonl"
    lines = [
        json.dumps({"question": " Blaidd là ai? ", "lang": "vi"}),
        json.dumps({"question": "Blaidd là ai?", "lang": "vi"}),  # trùng sau khi cắt khoảng trắng
        "{hỏng",
        json.dumps({"question": "x" * 2001}),
        json.dumps({"id": 1}),
        json.dumps({"question": "Who is Ranni?", "lang": "en"}),
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    pool = helpers.load_questions([path, tmp_path / "missing.jsonl"])
    assert pool == [{"question": "Blaidd là ai?", "lang": "vi"}, {"question": "Who is Ranni?", "lang": "en"}]
    with pytest.raises(SystemExit):
        helpers.load_questions([tmp_path / "missing.jsonl"])


def test_default_golden_files_exist_and_load():
    pool = helpers.load_questions()
    assert len(pool) >= 100
    assert all(0 < len(item["question"]) <= helpers.MAX_MESSAGE_CHARS for item in pool)


def test_parse_sse_yields_events_and_ignores_comments():
    stream = [
        ": keep-alive",
        "event: status",
        'data: {"status": "searching"}',
        "",
        "event: token",
        'data: {"token": "Xin"}',
        "",
        "event: done",
        'data: {"conversation_id": "c"}',
    ]  # khung cuối thiếu dòng trống vẫn được đọc
    assert list(helpers.parse_sse(stream)) == [
        ("status", '{"status": "searching"}'),
        ("token", '{"token": "Xin"}'),
        ("done", '{"conversation_id": "c"}'),
    ]


def test_env_helpers_fall_back_on_bad_values(monkeypatch):
    monkeypatch.setenv("LT_X", "abc")
    assert helpers.env_float("LT_X", 1.5) == 1.5 and helpers.env_int("LT_X", 4) == 4
    monkeypatch.setenv("LT_X", "7")
    assert helpers.env_int("LT_X", 4) == 7
    assert helpers.ok_codes("200, 503") == {200, 503} and helpers.ok_codes("") == {200}
    assert helpers.golden_paths_from_env(" a.jsonl, b.jsonl ") is not None and helpers.golden_paths_from_env("") is None
