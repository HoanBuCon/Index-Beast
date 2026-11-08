"""Thống kê cho trang admin: hội thoại gần đây, feedback, job ingestion, kết quả eval.

Hình dạng khớp `AdminStats` của web (`web/src/api/types.ts`); client kiểm nghiêm từng trường nên không được trả null
ở trường tùy chọn (dùng exclude_if) và số đo eval chỉ gồm giá trị số.

Phụ trách: TV1 · [S3] Trace từng bước RAG · [S5] Trang admin (API)
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AdminConversation(BaseModel):
    id: str
    title: str = Field(description="Câu hỏi đầu tiên của hội thoại, cắt còn 60 ký tự.")
    created_at: datetime


class AdminFeedback(BaseModel):
    message_id: str
    rating: int
    reason: str | None = Field(default=None, exclude_if=lambda value: value is None)


class AdminJob(BaseModel):
    id: str = Field(description="Mã job của CLI (external_id) nếu có, không thì UUID.")
    status: str
    pages_ok: int


class AdminEvalRun(BaseModel):
    id: str
    metrics: dict[str, float]


class AdminStats(BaseModel):
    conversations: list[AdminConversation]
    feedback: list[AdminFeedback]
    ingestion_jobs: list[AdminJob]
    eval_runs: list[AdminEvalRun]
