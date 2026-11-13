"""Ghi và xem kết quả đo trong bảng `eval_runs` (FR-EVAL-04), để so sánh các lần đo giữa các sprint.

Ghi một lần đo (cần PostgreSQL đang chạy và đã migrate):
  python -m scripts.eval_runs add --name golden-baseline --metric recall@5=0.78 --metric accuracy=0.64
  python -m scripts.eval_runs add --name golden-baseline --from-json report.json   # {"config": {...}, "metrics": {...}}
Xem các lần đo gần nhất (cũng hiện trên trang admin):
  python -m scripts.eval_runs list --limit 10

Chỉ nhận số hữu hạn làm số đo (không chuỗi, không bool, không NaN). `config.name` là tên hiện trên trang admin.
`--git-sha` mặc định lấy commit hiện tại.

Phụ trách: TV1 · [S4] Lưu kết quả đo cho TV3
"""

import argparse
import asyncio
import json
import math
import subprocess
from pathlib import Path
from typing import Any


def parse_pairs(items: list[str], flag: str) -> dict[str, str]:
    pairs = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise SystemExit(f"{flag} cần dạng ten=gia-tri, nhận được: {item!r}")
        pairs[key.strip()] = value.strip()
    return pairs


def to_metrics(raw: dict[str, Any]) -> dict[str, float]:
    metrics = {}
    for key, value in raw.items():
        if isinstance(value, bool):
            raise SystemExit(f"Số đo {key!r} không được là true/false.")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise SystemExit(f"Số đo {key!r} phải là số, nhận được {value!r}.") from None
        if not math.isfinite(number):
            raise SystemExit(f"Số đo {key!r} phải là số hữu hạn.")
        metrics[key] = number
    if not metrics:
        raise SystemExit("Cần ít nhất một số đo (--metric ten=so hoặc --from-json).")
    return metrics


def git_sha(choice: str) -> str | None:
    if choice == "none":
        return None
    if choice != "auto":
        return choice
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build(args) -> tuple[dict[str, Any], dict[str, float]]:
    config: dict[str, Any] = {}
    raw_metrics: dict[str, Any] = {}
    if args.from_json:
        try:
            data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SystemExit(f"Không đọc được {args.from_json}: {exc}") from None
        if not isinstance(data, dict):
            raise SystemExit('File JSON phải là một object có khóa "metrics" và "config".')
        config.update(data.get("config") or {})
        raw_metrics.update(data.get("metrics") or {})
    config.update(parse_pairs(args.config or [], "--config"))
    raw_metrics.update(parse_pairs(args.metric or [], "--metric"))
    if args.name:
        config["name"] = args.name
    return config, to_metrics(raw_metrics)


async def record(sessionmaker, *, git_sha: str | None, config: dict[str, Any], metrics: dict[str, float]):
    from core.db import repositories as repo

    async with sessionmaker() as session, session.begin():
        return await repo.add_eval_run(session, git_sha=git_sha, config=config, metrics=metrics)


async def recent(sessionmaker, limit: int):
    from core.db import repositories as repo

    async with sessionmaker() as session:
        return await repo.recent_eval_runs(session, limit)


async def run(args) -> int:
    from core.config import Settings
    from core.db.session import create_engine, create_sessionmaker

    engine = create_engine(Settings())
    sessionmaker = create_sessionmaker(engine)
    try:
        if args.command == "add":
            config, metrics = build(args)
            row = await record(sessionmaker, git_sha=git_sha(args.git_sha), config=config, metrics=metrics)
            print(f"Đã ghi lượt đo {row.id}: {metrics}")
        else:
            for row in await recent(sessionmaker, args.limit):
                name = (row.config or {}).get("name", "-")
                sha = (row.git_sha or "-")[:8]
                print(f"{row.created_at:%Y-%m-%d %H:%M}  {name:24} {sha}  {row.metrics}")
    finally:
        await engine.dispose()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="ghi một lần đo")
    add.add_argument("--name", help="tên lượt đo, hiện trên trang admin")
    add.add_argument("--metric", action="append", help="ten=so, lặp lại cho nhiều số đo")
    add.add_argument("--config", action="append", help="ten=gia-tri mô tả cấu hình, lặp lại được")
    add.add_argument("--from-json", help="file JSON có khóa metrics và config")
    add.add_argument("--git-sha", default="auto", help="auto (mặc định), none hoặc một commit")
    show = sub.add_parser("list", help="xem các lần đo gần nhất")
    show.add_argument("--limit", type=int, default=10)
    return asyncio.run(run(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
