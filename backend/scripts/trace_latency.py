"""p50/p95 độ trễ từng bước của pipeline từ trace đã lưu trong PostgreSQL (FR-EVAL-05, NFR-PERF-01), chỉ đọc.

  python -m scripts.trace_latency --days 1
  python -m scripts.trace_latency --since 2026-11-16 --until 2026-11-17 --limit 2000 --json

Các bước (đều là mili giây, lấy từ `messages.rag_trace` và cột `latency_ms`):
  total            cột latency_ms: cả câu trả lời
  prepare          trace.prepare_ms: mọi thứ trước khi sinh câu trả lời
  agent_decision   trace.agent.elapsed_ms: quyết định của agent
  tool:<action>    tổng trace.tool_actions[].elapsed_ms theo action (local_search, web_search, calculator…)
  rewrite, retrieval  chỉ có ở trace cũ trước khi bỏ nhánh legacy (trace.rewrite.elapsed_ms, trace.retrieval_queries)
  generate_rest    total - prepare: sinh câu trả lời + hậu xử lý (suy ra, không đo trực tiếp)
Các bước có thể chồng lên nhau (rewrite nằm trong prepare), nên không cộng được. Trace bị cắt (`truncated`) mất chi
tiết bước và chỉ góp cho `total`. Mỗi bước chỉ tính trên các câu có bước đó (cột n).

Phụ trách: TV3 (do TV1 dựng hộ) · [S5] Đo p95 từng bước từ trace
"""

import argparse
import asyncio
import json
import math
from collections import defaultdict
from datetime import datetime
from typing import Any

from scripts.llm_cost import add_window_args, exclude_loadtest, parse_window


def percentile(values: list[float], q: float) -> float:
    """Phân vị q (0-100) nội suy tuyến tính; danh sách phải khác rỗng."""
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q / 100
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def _ms(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None


def _sum_ms(items: Any, only: str | None = None) -> dict[str, float]:
    """Cộng elapsed_ms của danh sách bước, theo `action` (hoặc một khóa duy nhất nếu `only`)."""
    totals: dict[str, float] = defaultdict(float)
    for item in items if isinstance(items, list) else []:
        elapsed = _ms(item.get("elapsed_ms")) if isinstance(item, dict) else None
        if elapsed is not None:
            totals[only or str(item.get("action") or "unknown")] += elapsed
    return dict(totals)


def step_timings(latency_ms: float | None, trace: dict[str, Any] | None) -> dict[str, float]:
    steps: dict[str, float] = {}
    total = _ms(latency_ms)
    if total is not None:
        steps["total"] = total
    if not isinstance(trace, dict):
        return steps
    prepare = _ms(trace.get("prepare_ms"))
    if prepare is not None:
        steps["prepare"] = prepare
        if total is not None and total >= prepare:
            steps["generate_rest"] = total - prepare
    for name, section in (("rewrite", "rewrite"), ("agent_decision", "agent")):
        data = trace.get(section)
        elapsed = _ms(data.get("elapsed_ms")) if isinstance(data, dict) else None
        if elapsed is not None:
            steps[name] = elapsed
    retrieval = _sum_ms(trace.get("retrieval_queries"), only="retrieval")
    steps.update(retrieval)
    for action, elapsed in _sum_ms(trace.get("tool_actions")).items():
        steps[f"tool:{action}"] = elapsed
    return steps


def summarize(rows: list[tuple[float | None, dict[str, Any] | None]]) -> dict[str, dict[str, float]]:
    """rows: (latency_ms, rag_trace). Trả {bước: {n, p50, p95, max}} sắp theo p95 giảm dần."""
    samples: dict[str, list[float]] = defaultdict(list)
    for latency_ms, trace in rows:
        for step, value in step_timings(latency_ms, trace).items():
            samples[step].append(value)
    table = {
        step: {
            "n": len(values),
            "p50": round(percentile(values, 50), 1),
            "p95": round(percentile(values, 95), 1),
            "max": round(max(values), 1),
        }
        for step, values in samples.items()
    }
    return dict(sorted(table.items(), key=lambda item: -item[1]["p95"]))


def render(table: dict[str, dict[str, float]], total_rows: int, truncated: int) -> str:
    if not table:
        return "(không có trace nào trong cửa sổ này)"
    lines = [f"{'bước':22} {'n':>6} {'p50 ms':>10} {'p95 ms':>10} {'max ms':>10}"]
    for step, s in table.items():
        lines.append(f"{step:22} {s['n']:>6} {s['p50']:>10.1f} {s['p95']:>10.1f} {s['max']:>10.1f}")
    lines.append(f"{total_rows} câu trả lời, {truncated} trace bị cắt (không có chi tiết bước)")
    return "\n".join(lines)


async def fetch_rows(sessionmaker, since: datetime, until: datetime, limit: int, include_loadtest: bool = False):
    from sqlalchemy import select

    from core.db.models import Message

    stmt = (
        select(Message.latency_ms, Message.rag_trace)
        .where(
            Message.role == "assistant",
            Message.latency_ms.is_not(None),
            Message.created_at >= since,
            Message.created_at < until,
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    stmt = exclude_loadtest(stmt, include_loadtest)
    async with sessionmaker() as session:
        result = (await session.execute(stmt)).all()
    return [(r.latency_ms, r.rag_trace) for r in result]


async def run(args) -> int:
    from core.config import Settings
    from core.db.session import create_engine, create_sessionmaker

    since, until = parse_window(args)
    engine = create_engine(Settings())
    try:
        rows = await fetch_rows(create_sessionmaker(engine), since, until, args.limit, args.include_loadtest)
    finally:
        await engine.dispose()
    table = summarize(rows)
    truncated = sum(1 for _, trace in rows if isinstance(trace, dict) and trace.get("truncated"))
    if args.json:
        print(json.dumps({"steps": table, "answers": len(rows), "truncated": truncated}, ensure_ascii=False, indent=2))
    else:
        print(render(table, len(rows), truncated))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_window_args(parser)
    parser.add_argument("--limit", type=int, default=5000, help="số câu trả lời mới nhất tối đa (mặc định 5000)")
    parser.add_argument("--json", action="store_true", help="in JSON thay vì bảng")
    return asyncio.run(run(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
