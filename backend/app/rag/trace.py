"""Ghi trace mỗi request: query gốc/viết lại, chunk ids + điểm từng bước, độ trễ, token. Lưu vào messages.trace để
debug câu trả lời sai. `public_trace` là cửa duy nhất đi vào DB hoặc API: bỏ khóa nội bộ, che secret, giới hạn cỡ.

Phụ trách: TV1 · [S3] Trace từng bước RAG
"""

import json
import re
from typing import Any

MAX_TRACE_BYTES = 64 * 1024
MAX_TEXT_CHARS = 1000
MAX_LIST_ITEMS = 50
MAX_DEPTH = 8
REDACTED = "[redacted]"

# Khóa kiểu api_key, secret, authorization, token, *_token; không bắt prompt_tokens/completion_tokens.
_SECRET_KEY = re.compile(r"(api_?key|secret|password|authorization|cookie|bearer)|(^|_)token$", re.I)
_SECRET_VALUE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}|\bBearer\s+\S+|\btvly-[A-Za-z0-9_-]{8,}", re.I)


def _clean(value: Any, depth: int = 0) -> Any:
    if depth > MAX_DEPTH:
        return "…"
    if isinstance(value, dict):
        return {
            str(key): REDACTED if _SECRET_KEY.search(str(key)) else _clean(item, depth + 1)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, (list, tuple, set)):
        return [_clean(item, depth + 1) for item in list(value)[:MAX_LIST_ITEMS]]
    if isinstance(value, str):
        text = _SECRET_VALUE.sub(REDACTED, value)
        return text if len(text) <= MAX_TEXT_CHARS else text[:MAX_TEXT_CHARS] + "…"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:MAX_TEXT_CHARS]


def public_trace(raw: dict, *, latency_ms: float | None = None) -> dict:
    """Bản trace an toàn để lưu và trả cho admin. `result` giữ nội dung câu trả lời, đã có ở bảng messages."""
    data = {key: value for key, value in raw.items() if key != "result"}
    if latency_ms is not None:
        data["latency_ms"] = latency_ms
    cleaned = _clean(data)
    size = len(json.dumps(cleaned, ensure_ascii=False).encode())
    if size > MAX_TRACE_BYTES:
        keep = {key: cleaned[key] for key in ("latency_ms", "usage", "rewrite", "rewritten_query") if key in cleaned}
        return {**keep, "truncated": True, "bytes": size, "keys": sorted(cleaned)}
    return cleaned


def _count(*values: Any) -> int | None:
    numbers = [v for v in values if type(v) is int]
    return sum(numbers) if numbers else None


def token_usage(trace: dict) -> tuple[int | None, int | None]:
    """Token vào/ra của các lượt gọi LLM trong trace (sinh câu trả lời + viết lại truy vấn)."""
    generation = trace.get("usage") or {}
    rewrite = (trace.get("rewrite") or {}).get("usage") or {}
    return (
        _count(generation.get("prompt_tokens"), rewrite.get("prompt_tokens")),
        _count(generation.get("completion_tokens"), rewrite.get("completion_tokens")),
    )
