"""Dung sai JSON cuối và các nhóm lỗi không chứa nội dung."""

import pytest

from app.rag.output import OutputFormatError, char_class, decode_output


def test_invalid_escape_is_classified_without_content():
    with pytest.raises(OutputFormatError) as decoded:
        decode_output('{"answer":"Hạ boss \\q bắt buộc"}')
    assert decoded.value.diagnostics["json_char"] == "invalid_escape"
    assert "boss" not in str(decoded.value.diagnostics)


@pytest.mark.parametrize(
    ("text", "position", "expected"), [("a\nb", 1, "control_char"), ('a"b', 1, "quote"), ("ab", 5, "end_of_text")]
)
def test_char_class_labels(text, position, expected):
    assert char_class(text, position) == expected


def test_retry_and_language_policies_come_from_prompt_files():
    from app.rag.generator import Generator, Prepared

    prepared = Prepared("rag", "vi", [], values={"policy": "BASE"}, gameplay_advice=True)
    first = Generator._inputs(prepared, 0)["policy"]
    retry = Generator._inputs(prepared, 1)["policy"]
    assert first.startswith("BASE") and "AUTHORITATIVE RESPONSE LANGUAGE" in first and "Vietnamese" in first
    assert "{target}" not in first and "FORMAT RETRY" not in first
    assert "FORMAT RETRY" in retry and '"advisory":true' in retry and "Smithing Stone" not in retry
