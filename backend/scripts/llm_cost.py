"""Báo cáo chi phí LLM theo ngày từ PostgreSQL (NFR-COST-01), chỉ đọc, không gọi API nào.

  python -m scripts.llm_cost --days 7
  python -m scripts.llm_cost --since 2026-11-10 --until 2026-11-17 --input-price 0.28 --output-price 0.42 --json

Nguồn số liệu: bảng `messages` (tin nhắn assistant): `tokens_in`/`tokens_out` là tổng token mọi lượt gọi LLM của
câu trả lời (sinh câu, agent, viết lại truy vấn: xem app/rag/trace.py::token_usage). Số lần tìm web đếm từ
`rag_trace`: số bước `agent.steps` có tool = search_web (vòng lặp Agent, từ 22/11); trace cũ: số bước `tool_actions`
có action = web_search; nếu không có thì 1 khi `web_search.status` là ok/error.
Câu trả lời không gọi LLM (trả lời có sẵn, ngoài phạm vi) có token NULL, tính 0 token nhưng vẫn tính là một câu hỏi.
Ngày tính theo UTC. Tiền = token * giá / 1.000.000 (+ số lần tìm web * giá mỗi lần).

Giá mặc định chỉ là điểm xuất phát: PHẢI đối chiếu lại bảng giá hiện hành của nhà cung cấp trước khi báo cáo số liệu.

Phụ trách: TV3 (do TV1 dựng hộ) · [S5] Chi phí LLM
"""

import argparse
import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

# TODO(verify): giá DeepSeek (USD / 1 triệu token, cache miss) và Tavily (USD / lượt tìm basic) ghi theo bảng giá
# lúc viết, chưa đối chiếu được trong môi trường này. Kiểm tra https://api-docs.deepseek.com/quick_start/pricing và
# https://docs.tavily.com/documentation/api-credits rồi truyền --input-price/--output-price/--search-price.
DEFAULT_INPUT_PRICE = 0.28
DEFAULT_OUTPUT_PRICE = 0.42
DEFAULT_SEARCH_PRICE = 0.008
TARGET_QUESTIONS_PER_DAY = 1000
TARGET_MONTHLY_USD = 30.0
DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class Prices:
    input_per_m: float = DEFAULT_INPUT_PRICE
    output_per_m: float = DEFAULT_OUTPUT_PRICE
    search_each: float = DEFAULT_SEARCH_PRICE


def cost_of(tokens_in: int, tokens_out: int, searches: int, prices: Prices) -> float:
    return (
        tokens_in * prices.input_per_m + tokens_out * prices.output_per_m
    ) / 1_000_000 + searches * prices.search_each


def web_search_calls(rag_trace: dict[str, Any] | None) -> int:
    """Số lần gọi Tavily ước tính từ trace (xem docstring đầu file)."""
    if not isinstance(rag_trace, dict):
        return 0
    agent = rag_trace.get("agent")
    steps = agent.get("steps") if isinstance(agent, dict) else None
    if isinstance(steps, list):
        # Mỗi lời gọi đều tới Tavily, kể cả khi lỗi ở đó; bước bị từ chối trước khi chạy ("error" mà không có lời gọi)
        # không phân biệt được trong trace, nên mọi bước search_web đều được đếm (cận trên).
        from_loop = sum(1 for s in steps if isinstance(s, dict) and s.get("tool") == "search_web")
        if from_loop:
            return from_loop
    actions = rag_trace.get("tool_actions")
    if isinstance(actions, list):
        from_agent = sum(1 for a in actions if isinstance(a, dict) and a.get("action") == "web_search")
        if from_agent:
            return from_agent
    web = rag_trace.get("web_search")
    return 1 if isinstance(web, dict) and web.get("status") in ("ok", "error") else 0


def _int(value: Any) -> int:
    return value if type(value) is int and value > 0 else 0


def aggregate(rows: list[tuple[datetime, int | None, int | None, int]], prices: Prices) -> list[dict[str, Any]]:
    """rows: (created_at, tokens_in, tokens_out, số lần tìm web). Trả danh sách theo ngày UTC tăng dần."""
    days: dict[date, dict[str, Any]] = defaultdict(
        lambda: {"questions": 0, "tokens_in": 0, "tokens_out": 0, "searches": 0}
    )
    for created_at, tokens_in, tokens_out, searches in rows:
        if created_at.tzinfo is not None:
            created_at = created_at.astimezone(UTC)
        day = days[created_at.date()]
        day["questions"] += 1
        day["tokens_in"] += _int(tokens_in)
        day["tokens_out"] += _int(tokens_out)
        day["searches"] += _int(searches)
    report = []
    for day, data in sorted(days.items()):
        usd = cost_of(data["tokens_in"], data["tokens_out"], data["searches"], prices)
        report.append({"date": day.isoformat(), **data, "usd": usd})
    return report


def project(report: list[dict[str, Any]], questions_per_day: int = TARGET_QUESTIONS_PER_DAY) -> dict[str, Any]:
    """Chi phí trung bình mỗi câu của cả cửa sổ, nhân lên `questions_per_day` x 30 ngày, so với mục tiêu $30/tháng."""
    questions = sum(d["questions"] for d in report)
    total = sum(d["usd"] for d in report)
    per_question = total / questions if questions else 0.0
    monthly = per_question * questions_per_day * DAYS_PER_MONTH
    return {
        "questions": questions,
        "total_usd": total,
        "usd_per_question": per_question,
        "projected_monthly_usd": monthly,
        "target_monthly_usd": TARGET_MONTHLY_USD,
        "within_target": questions > 0 and monthly <= TARGET_MONTHLY_USD,
        "questions_per_day": questions_per_day,
    }


LOADTEST_REF_PREFIX = "loadtest:"  # external_ref của lưu lượng load test (locustfile, chế độ service token)


def _as_utc(value: datetime) -> datetime:
    """Có múi giờ thì đổi sang UTC; không có (chỉ ngày) thì coi là UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def exclude_loadtest(stmt, include_loadtest: bool):
    """Mặc định loại hội thoại có external_ref bắt đầu bằng `loadtest:` (cần join conversations). Hội thoại không có
    external_ref (web thường) được giữ."""
    if include_loadtest:
        return stmt
    from sqlalchemy import or_

    from core.db.models import Conversation, Message

    return stmt.join(Conversation, Conversation.id == Message.conversation_id).where(
        or_(
            Conversation.external_ref.is_(None),
            ~Conversation.external_ref.startswith(LOADTEST_REF_PREFIX, autoescape=True),
        )
    )


def parse_window(args, now: datetime | None = None) -> tuple[datetime, datetime]:
    """[since, until) theo UTC: --since/--until (YYYY-MM-DD) hoặc --days (mặc định) tính tới hết hôm nay."""
    now = now or datetime.now(UTC)
    if args.until and not args.since:
        raise SystemExit("--until cần đi kèm --since (hoặc bỏ --until và dùng --days).")
    try:
        if args.since:
            since = _as_utc(datetime.fromisoformat(args.since))
            until = _as_utc(datetime.fromisoformat(args.until)) if args.until else now
        else:
            until = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            since = until - timedelta(days=args.days)
    except ValueError:
        raise SystemExit("Ngày phải có dạng YYYY-MM-DD.") from None
    if since >= until:
        raise SystemExit("--since phải trước --until.")
    return since, until


def render(report: list[dict[str, Any]], summary: dict[str, Any], prices: Prices) -> str:
    lines = [
        f"Giá: vào ${prices.input_per_m}/1M, ra ${prices.output_per_m}/1M, "
        f"tìm web ${prices.search_each}/lượt (cần đối chiếu)",
        f"{'ngày (UTC)':12} {'câu':>6} {'token vào':>12} {'token ra':>11} {'tìm web':>8} {'USD':>9}",
    ]
    for d in report:
        lines.append(
            f"{d['date']:12} {d['questions']:>6} {d['tokens_in']:>12,} {d['tokens_out']:>11,} {d['searches']:>8} "
            f"{d['usd']:>9.4f}"
        )
    if not report:
        lines.append("(không có tin nhắn assistant trong cửa sổ này)")
        return "\n".join(lines)
    verdict = "ĐẠT" if summary["within_target"] else "VƯỢT"
    lines += [
        f"Tổng: {summary['questions']} câu, ${summary['total_usd']:.4f}, ${summary['usd_per_question']:.5f}/câu",
        f"Dự phóng {summary['questions_per_day']} câu/ngày x {DAYS_PER_MONTH} ngày = "
        f"${summary['projected_monthly_usd']:.2f}/tháng so với mục tiêu "
        f"${summary['target_monthly_usd']:.0f}: {verdict}",
    ]
    return "\n".join(lines)


async def fetch_rows(
    sessionmaker, since: datetime, until: datetime, include_loadtest: bool = False
) -> list[tuple[datetime, int | None, int | None, int]]:
    from sqlalchemy import select

    from core.db.models import Message

    stmt = (
        select(
            Message.created_at,
            Message.tokens_in,
            Message.tokens_out,
            Message.rag_trace["agent"].label("agent"),
            Message.rag_trace["tool_actions"].label("tool_actions"),
            Message.rag_trace["web_search"].label("web_search"),
        )
        .where(Message.role == "assistant", Message.created_at >= since, Message.created_at < until)
        .order_by(Message.created_at)
    )
    stmt = exclude_loadtest(stmt, include_loadtest)
    async with sessionmaker() as session:
        result = (await session.execute(stmt)).all()
    return [
        (
            r.created_at,
            r.tokens_in,
            r.tokens_out,
            web_search_calls({"agent": r.agent, "tool_actions": r.tool_actions, "web_search": r.web_search}),
        )
        for r in result
    ]


async def run(args) -> int:
    from core.config import Settings
    from core.db.session import create_engine, create_sessionmaker

    prices = Prices(args.input_price, args.output_price, args.search_price)
    since, until = parse_window(args)
    engine = create_engine(Settings())
    try:
        rows = await fetch_rows(create_sessionmaker(engine), since, until, args.include_loadtest)
    finally:
        await engine.dispose()
    report = aggregate(rows, prices)
    summary = project(report, args.questions_per_day)
    if args.json:
        print(json.dumps({"days": report, "summary": summary}, ensure_ascii=False, indent=2))
    else:
        print(render(report, summary, prices))
    return 0


def add_window_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--days", type=int, default=7, help="số ngày gần nhất (mặc định 7)")
    parser.add_argument("--since", help="YYYY-MM-DD (UTC), thay cho --days")
    parser.add_argument("--until", help="YYYY-MM-DD (UTC), không gồm ngày này; mặc định là bây giờ; cần --since")
    parser.add_argument(
        "--include-loadtest",
        action="store_true",
        help="tính cả lưu lượng load test (hội thoại có external_ref bắt đầu bằng 'loadtest:'); mặc định loại ra",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_window_args(parser)
    parser.add_argument("--input-price", type=float, default=DEFAULT_INPUT_PRICE, help="USD / 1M token vào")
    parser.add_argument("--output-price", type=float, default=DEFAULT_OUTPUT_PRICE, help="USD / 1M token ra")
    parser.add_argument("--search-price", type=float, default=DEFAULT_SEARCH_PRICE, help="USD / lượt tìm web (Tavily)")
    parser.add_argument("--questions-per-day", type=int, default=TARGET_QUESTIONS_PER_DAY, help="quy mô dự phóng")
    parser.add_argument("--json", action="store_true", help="in JSON thay vì bảng")
    return asyncio.run(run(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
