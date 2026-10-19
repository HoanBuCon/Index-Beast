"""Log JSON một dòng/sự kiện, gắn request_id (contextvar) và job_id cho ingest để lọc log khi debug.

Dùng: `log.info("msg", extra={"data": {...}})` — trường `data` được đưa nguyên vào JSON.

Phụ trách: TV1 · [S2] Xử lý lỗi & logging chuẩn
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
job_id_var: ContextVar[str] = ContextVar("job_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if (job_id := job_id_var.get()) != "-":
            payload["job_id"] = job_id
        if data := getattr(record, "data", None):
            payload["data"] = data
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # uvicorn tự cấu hình handler riêng; cho log của nó đi qua root để cũng thành JSON
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
