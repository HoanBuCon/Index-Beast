"""Ngân sách lượt gọi model mỗi lượt chat, dùng chung cho vòng lặp Agent, generator, Answer Guard và bước chọn ảnh."""

from core.errors import UnavailableError


def spend(trace: dict, phase: str, maximum: int | None):
    calls = trace.setdefault("model_calls", [])
    if maximum is not None and len(calls) >= maximum:
        raise UnavailableError("Lượt hỏi đã đạt giới hạn xử lý. Hãy gửi yêu cầu cụ thể hơn.")
    calls.append({"phase": phase})
