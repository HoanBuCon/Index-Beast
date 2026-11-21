"""Giải mã JSON nguyên câu trả lời, có giới hạn; không bao giờ sửa dữ kiện hay lấy một object dở dang."""

import json
import re

MAX_OUTPUT_CHARS = 100000
_FENCE = re.compile(r"\A```(?:json)?[ \t]*\r?\n(.*)\r?\n```\Z", re.DOTALL | re.IGNORECASE)


class OutputFormatError(ValueError):
    def __init__(self, diagnostics: dict):
        super().__init__("Invalid RAG JSON output")
        self.diagnostics = {"reason": "invalid_json", **diagnostics}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            # Không bao giờ đưa khóa do provider kiểm soát vào log/lỗi.
            raise OutputFormatError({"json_error": "duplicate_key"})
        result[key] = value
    return result


def _reject_constant(_value):
    raise OutputFormatError({"json_error": "nonfinite_number"})


def char_class(text: str, position: int) -> str:
    """Nhóm của ký tự tại chỗ giải mã lỗi. Không bao giờ là chính ký tự hay text xung quanh."""
    if position >= len(text):
        return "end_of_text"
    char = text[position]
    if ord(char) < 0x20:
        return "control_char"
    if char == "\\":
        return "invalid_escape"
    if char == '"':
        return "quote"
    if char in "{}[],:":
        return "structural"
    return "other"


def decode_output(raw: str) -> tuple[object, str]:
    """Nhận JSON hoặc MỘT lớp bọc hoàn chỉnh (BOM/code fence); từ chối mọi thứ nằm ngoài nó."""
    shape = {"output_chars": len(raw)}
    if len(raw) > MAX_OUTPUT_CHARS:
        raise OutputFormatError({**shape, "json_error": "output_too_large"})
    body = raw.strip(" \t\r\n")
    bom = body.startswith("\ufeff")
    if bom:
        body = body[1:].strip(" \t\r\n")
    match = _FENCE.fullmatch(body)
    if match:
        body = match[1]
    wrapper = "bom_fence" if bom and match else "bom" if bom else "fence" if match else "none"
    shape["output_wrapper"] = wrapper
    try:
        # strict=False chấp nhận xuống dòng/tab thô trong chuỗi, một lỗi định dạng vô hại của model.
        # Kiểm tra schema, trích dẫn và trích dẫn nguyên văn không đổi.
        return json.loads(
            body, object_pairs_hook=_unique_object, parse_constant=_reject_constant, strict=False
        ), wrapper
    except json.JSONDecodeError as exc:
        # Chỉ tọa độ và nhãn cố định. str(exc) hay exc.doc có thể làm lộ câu trả lời.
        raise OutputFormatError(
            {
                **shape,
                "json_error": "syntax",
                "json_offset": exc.pos,
                "json_line": exc.lineno,
                "json_column": exc.colno,
                "json_char": char_class(body, exc.pos),
            }
        ) from None
    except RecursionError:
        raise OutputFormatError({**shape, "json_error": "nesting_too_deep"}) from None
    except OutputFormatError as exc:
        raise OutputFormatError({**shape, **exc.diagnostics}) from None
