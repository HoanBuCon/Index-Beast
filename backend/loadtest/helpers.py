"""Phần thuần của kịch bản tải (không import locust nên test đơn vị được): bộ câu hỏi từ golden set, đọc khung SSE,
đọc cấu hình từ biến môi trường.

Phụ trách: TV3 (do TV1 dựng hộ) · [S5] Load test
"""

import json
import os
import random
from collections.abc import Iterable, Iterator
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN = (BACKEND_DIR / "eval" / "golden_set.jsonl", BACKEND_DIR / "eval" / "golden_set_s3.jsonl")
MAX_MESSAGE_CHARS = 2000  # khớp app/api/schemas/chat.py


def load_questions(paths: Iterable[Path] | None = None) -> list[dict[str, str]]:
    """Đọc mỗi dòng JSONL có `question`; bỏ dòng hỏng/trống/quá dài và câu trùng. Trả [{question, lang}]."""
    seen, pool = set(), []
    for path in paths or DEFAULT_GOLDEN:
        if not Path(path).is_file():
            continue
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            question = row.get("question") if isinstance(row, dict) else None
            if not isinstance(question, str):
                continue
            question = question.strip()
            if not question or len(question) > MAX_MESSAGE_CHARS or question in seen:
                continue
            seen.add(question)
            pool.append({"question": question, "lang": str(row.get("lang") or "vi")})
    if not pool:
        raise SystemExit("Không có câu hỏi nào trong golden set (kiểm tra LOADTEST_GOLDEN).")
    return pool


def golden_paths_from_env(value: str | None) -> list[Path] | None:
    """LOADTEST_GOLDEN: các đường dẫn cách nhau bằng dấu phẩy; trống = golden_set.jsonl + golden_set_s3.jsonl."""
    items = [Path(p.strip()) for p in (value or "").split(",") if p.strip()]
    return items or None


def pick(pool: list[dict[str, str]], rng: random.Random | None = None) -> str:
    return (rng or random).choice(pool)["question"]


def parse_sse(lines: Iterable[str]) -> Iterator[tuple[str, str]]:
    """Gom dòng của luồng SSE thành (event, data). Khung kết thúc bằng dòng trống; dòng bắt đầu bằng ':' là comment."""
    event, data = "message", []
    for line in lines:
        if line == "":
            if data:
                yield event, "\n".join(data)
            event, data = "message", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        yield event, "\n".join(data)


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def ok_codes(value: str | None, default: tuple[int, ...] = (200,)) -> set[int]:
    codes = {int(p) for p in (value or "").replace(" ", "").split(",") if p.isdigit()}
    return codes or set(default)
