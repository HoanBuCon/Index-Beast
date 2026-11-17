"""Stream/final JSON tolerance for raw line breaks, and content-free failure categories."""

import pytest

from app.rag.generator import StreamPrefixError, answer_prefix
from app.rag.output import OutputFormatError, char_class, decode_output


def test_raw_line_break_inside_answer_is_accepted_while_streaming_and_at_eof():
    raw = '{"answer":"Route A [1].\n\nRoute B [2].","evidence":[],"insufficient":true}'
    assert answer_prefix(raw[: raw.index("[2]")]) == "Route A [1].\n\nRoute B "
    data, _ = decode_output(raw)
    assert data["answer"] == "Route A [1].\n\nRoute B [2]."


def test_invalid_escape_is_classified_without_content():
    with pytest.raises(StreamPrefixError) as error:
        answer_prefix('{"answer":"Hạ boss \\q bắt buộc"')
    assert error.value.char_class == "invalid_escape"
    with pytest.raises(OutputFormatError) as decoded:
        decode_output('{"answer":"a \\q b"}')
    assert decoded.value.diagnostics["json_char"] == "invalid_escape"
    assert "boss" not in str(decoded.value.diagnostics)


def test_metadata_before_answer_is_still_reported_as_a_category():
    with pytest.raises(StreamPrefixError) as error:
        answer_prefix(
            '{"evidence":[{"index":1,"quote_id":"q0"}],"insufficient":false,"limitation":null,"x":"' + "y" * 40
        )
    assert error.value.char_class == "answer_not_first"


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
