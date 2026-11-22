import json
import logging

from core.logging import JsonFormatter, request_id_var


def _format(record_msg: str, **extra) -> dict:
    record = logging.LogRecord("app", logging.INFO, __file__, 1, record_msg, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return json.loads(JsonFormatter().format(record))


def test_log_line_is_json_with_request_id_and_data():
    token = request_id_var.set("req-1")
    try:
        line = _format("hello", data={"n": 1, "text": "Radahn"})
    finally:
        request_id_var.reset(token)

    assert line["msg"] == "hello"
    assert line["level"] == "INFO"
    assert line["request_id"] == "req-1"
    assert line["data"] == {"n": 1, "text": "Radahn"}


def test_log_without_request_context_uses_dash():
    assert _format("x")["request_id"] == "-"


def test_extra_fields_are_kept_in_data():
    # reranker ghi extra={"event": ..., "status": ...}: production phải thấy được kết quả rerank
    line = _format("Reranker outcome", event="reranker_outcome", status="ok", ranked_count=5)
    assert line["data"] == {"event": "reranker_outcome", "status": "ok", "ranked_count": 5}


def test_extra_fields_merge_with_data_and_skip_uvicorn_color_message():
    line = _format("x", data={"n": 1}, event="e", color_message="\x1b[32mx\x1b[0m")
    assert line["data"] == {"event": "e", "n": 1}


def test_uvicorn_access_log_stays_off_after_setup(monkeypatch):
    # uvicorn bật access log (có IP người dùng) khi logger "uvicorn.access" có handler, kể cả kế thừa từ root
    from core.logging import setup_logging

    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", list(root.handlers))
    setup_logging("INFO")
    assert not logging.getLogger("uvicorn.access").hasHandlers()
    assert logging.getLogger("uvicorn.error").hasHandlers()
