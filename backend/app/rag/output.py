"""Bounded, whole-response JSON decoding; never repair facts or extract a partial object."""

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
            # Never include a provider-controlled key in logs/errors.
            raise OutputFormatError({"json_error": "duplicate_key"})
        result[key] = value
    return result


def _reject_constant(_value):
    raise OutputFormatError({"json_error": "nonfinite_number"})


def char_class(text: str, position: int) -> str:
    """Category of the character at a decode failure. Never the character or surrounding text."""
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
    """Accept JSON or ONE complete BOM/fenced envelope; reject everything outside it."""
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
        # strict=False accepts raw line breaks/tabs inside strings, a benign model formatting slip.
        # Schema, citation and quote validation are unchanged.
        return json.loads(
            body, object_pairs_hook=_unique_object, parse_constant=_reject_constant, strict=False
        ), wrapper
    except json.JSONDecodeError as exc:
        # Coordinates and fixed labels only. str(exc) or exc.doc could leak the answer.
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
