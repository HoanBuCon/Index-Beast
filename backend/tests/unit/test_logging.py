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
