"""Answer Guard và câu trả lời được giữ lại: tên trường nội bộ được viết lại, không bao giờ hiện ra; pack rule level."""

from contextlib import aclosing

import pytest

from app.rag.gameplay_knowledge import LEVEL_RULE_ID, level_rule
from app.rag.generator import Prepared, validate_answer
from tests.unit.test_live_chat import hit


def answer_with(p, text):
    return validate_answer(p, {"answer": text, "evidence": [{"index": 1, "quote_id": "q0"}], "insufficient": False})


def test_the_level_rule_the_agent_can_cite_keeps_its_id_and_is_a_fresh_copy():
    rule = level_rule()
    assert rule.id == LEVEL_RULE_ID and "minus 79" in rule.payload["text"]
    rule.payload["text"] = "changed"
    assert "minus 79" in level_rule().payload["text"]


@pytest.mark.parametrize(
    ("answer", "fields"),
    [
        ("Theo `player_profile`, ưu tiên Intelligence [1].", ["player_profile"]),
        ("Mình dùng agent_results để chia điểm [1].", ["agent_results"]),
    ],
)
def test_internal_field_names_go_to_the_guard_and_are_never_shown(answer, fields):
    p = Prepared("rag", "vi", [], hits=[hit()])
    out = answer_with(p, answer)
    # Không bị bỏ: Answer Guard được yêu cầu viết lại, và câu trả lời dự phòng đã đọc tự nhiên.
    assert p.trace["guard_request"]["issues"] == [{"kind": "internal_field_name", "fields": fields}]
    assert not any(f in out.answer for f in fields) and "`" not in out.answer
    clean = Prepared("rag", "vi", [], hits=[hit()])
    answer_with(clean, "Ưu tiên Intelligence [1].")
    assert "guard_request" not in clean.trace


async def test_every_answer_is_held_and_the_guard_rewrites_an_internal_field_name():
    from app.api.schemas.chat import ChatRequest
    from tests.unit.test_live_chat import BODY, FakeLLM, FakeRetriever, service

    evidence = '"evidence": [{"index": 1, "quote": "Ranni is an Empyrean"}], "insufficient": false}'
    leak = '{"answer": "Ranni là Empyrean [1].\nTheo player_profile thì chưa chia điểm [1]. ", ' + evidence
    llm = FakeLLM(tokens=[leak[:30], leak[30:]])
    llm.data = {"answer": "Ranni là Empyrean [1].\nTheo thông tin bạn đưa ra thì chưa chia điểm [1]."}
    live = service(llm=llm, retriever=FakeRetriever(), rag_format_retries=0)
    async with aclosing(await live.open_stream(ChatRequest(**BODY))) as events:
        frames = [frame async for frame in events]
    tokens = [p.token for n, p in frames if n == "token"]
    # Hiện một lần, sau khi kiểm: không có gì đã hiện bị cắt hay bị thay bằng lỗi về sau.
    assert frames[-1][0] == "done" and len(tokens) == 1
    assert "player_profile" not in tokens[0] and tokens[0].startswith(llm.data["answer"])
