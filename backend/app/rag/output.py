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
        return json.loads(body, object_pairs_hook=_unique_object, parse_constant=_reject_constant), wrapper
    except json.JSONDecodeError as exc:
        # Coordinates and fixed labels only. str(exc) or exc.doc could leak the answer.
        raise OutputFormatError(
            {**shape, "json_error": "syntax", "json_offset": exc.pos, "json_line": exc.lineno, "json_column": exc.colno}
        ) from None
    except RecursionError:
        raise OutputFormatError({**shape, "json_error": "nesting_too_deep"}) from None
    except OutputFormatError as exc:
        raise OutputFormatError({**shape, **exc.diagnostics}) from None


def stream_body_prefix(raw: str) -> str:
    """Remove only the allowed opening envelope while receiving fragmented tokens.

    Closing fence/trailing data are checked by decode_output when the stream ends.
    """
    body = raw.lstrip(" \t\r\n")
    if body.startswith("\ufeff"):
        body = body[1:].lstrip(" \t\r\n")
    if body.startswith("`"):
        if any(opening.startswith(body.lower()) for opening in ("```json\n", "```json\r\n", "```\n", "```\r\n")):
            return ""
        opening = re.match(r"\A```(?:json)?[ \t]*\r?\n", body, re.IGNORECASE)
        if opening:
            return body[opening.end() :]
    return body
