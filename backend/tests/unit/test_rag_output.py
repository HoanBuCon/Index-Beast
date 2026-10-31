"""Strict whole-output parsing; all cases are local strings, never model calls."""

import json

import pytest

from app.rag.generator import answer_prefix
from app.rag.output import MAX_OUTPUT_CHARS, OutputFormatError, decode_output

DATA = {"answer": 'Tiếng Việt: "Ranni"\nCô ấy.', "evidence": [], "insufficient": True}
RAW = json.dumps(DATA, ensure_ascii=False)


@pytest.mark.parametrize(
    "wrapper", ["{}", " \n{}\t", "\ufeff{}", "```json\n{}\n```", "```\r\n{}\r\n```", "\ufeff```JSON\n{}\n```"]
)
def test_complete_output_envelopes_preserve_all_values(wrapper):
    decoded, _ = decode_output(wrapper.format(RAW))
    assert decoded == DATA


@pytest.mark.parametrize(
    "raw",
    [
        "Answer first. " + RAW,
        RAW + " trailing prose",
        RAW + RAW,
        "```json\n" + RAW,
        "```json\n" + RAW + "\n``` trailing",
        "```python\n" + RAW + "\n```",
        '{"answer":"private answer",}',
        '{"answer":"private answer"',
        '{"answer":"unescaped\nline"}',
        '{"answer":"private", "answer":"overridden"}',
        '{"evidence":[{"index":1,"index":2}]}',
        '{"answer":NaN}',
        '{"answer":Infinity}',
    ],
)
def test_invalid_output_is_not_repaired_or_partially_extracted(raw):
    with pytest.raises(OutputFormatError) as caught:
        decode_output(raw)
    assert "private" not in str(caught.value.diagnostics)
    assert "private" not in str(caught.value)


def test_invalid_json_coordinates_are_numeric_without_document_or_provider_error_text():
    with pytest.raises(OutputFormatError) as caught:
        decode_output('{\n"answer": "private body",\n}')
    data = caught.value.diagnostics
    assert data["reason"] == "invalid_json" and data["json_error"] == "syntax"
    assert (data["json_line"], data["json_column"]) == (3, 1)
    assert isinstance(data["json_offset"], int) and "private" not in str(data)


@pytest.mark.parametrize("raw", ["x" * (MAX_OUTPUT_CHARS + 1), "[" * 3000 + "]" * 3000], ids=["oversized", "deep"])
def test_oversized_or_deeply_nested_output_is_rejected(raw):
    with pytest.raises(OutputFormatError):
        decode_output(raw)


@pytest.mark.parametrize("envelope", ["{}", "\ufeff{}", "```json\n{}\n```", "\ufeff```\r\n{}\r\n```"])
def test_streamed_envelopes_and_unicode_escape_fragments_remain_monotonic(envelope):
    raw = envelope.format(json.dumps(DATA, ensure_ascii=True))
    prefixes = [answer_prefix(raw[:i]) for i in range(1, len(raw) + 1)]
    assert prefixes[-1] == DATA["answer"]
    assert all(current.startswith(previous) for previous, current in zip(prefixes, prefixes[1:], strict=False))
