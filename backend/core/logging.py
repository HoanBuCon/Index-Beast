"""Log JSON một dòng mỗi sự kiện, kèm request_id (API) hoặc job_id (ingest) để lọc khi debug.

Dùng: `log.info("msg", extra={"data": {...}})` — trường `data` được đưa nguyên vào JSON.

Phụ trách: TV1 · [S1] Skeleton FastAPI
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

NO_ID = "-"
request_id_var: ContextVar[str] = ContextVar("request_id", default=NO_ID)
job_id_var: ContextVar[str] = ContextVar("job_id", default=NO_ID)
# Thuộc tính sẵn có của LogRecord; còn lại là extra do code truyền vào. color_message: bản có mã màu uvicorn tự thêm
_RECORD_FIELDS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "data",
    "color_message",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if (job_id := job_id_var.get()) != NO_ID:
            payload["job_id"] = job_id
        # extra={"data": {...}} và extra={"event": ..., ...} (reranker) đều vào "data"; data ghi đè khi trùng khóa
        extras = {k: v for k, v in vars(record).items() if k not in _RECORD_FIELDS}
        if data := {**extras, **(getattr(record, "data", None) or {})}:
            payload["data"] = data
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # uvicorn gắn handler riêng; bỏ đi để log của nó cũng ra JSON qua root
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    # Access log của uvicorn chứa IP người dùng (docs/privacy.md: không lưu IP). uvicorn chỉ ghi khi logger này có
    # handler, kể cả kế thừa từ root, nên --no-access-log không đủ: cắt hẳn.
    # Middleware app.http đã log request không kèm IP.
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
    logging.getLogger("httpx").setLevel(logging.WARNING)
