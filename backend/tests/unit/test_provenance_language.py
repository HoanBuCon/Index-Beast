"""Generator viết bằng ngôn ngữ server chọn trong khi retrieval vẫn bằng tiếng Anh."""

import json

import pytest

from app.rag.generator import Generator, Prepared
from tests.unit.test_live_chat import FakeLLM, hit


@pytest.mark.parametrize("lang,target", [("vi", "Vietnamese (tiếng Việt)"), ("en", "English")])
@pytest.mark.parametrize("streaming", [False, True])
async def test_json_and_sse_use_server_language_with_english_retrieval(lang, target, streaming):
    llm = FakeLLM()
    llm.data = {
        "answer": "Ranni là một Empyrean [1]." if lang == "vi" else "Ranni is an Empyrean [1].",
        "evidence": [{"index": 1, "quote_id": "q0"}],
        "insufficient": False,
    }
    llm.tokens = [json.dumps(llm.data, ensure_ascii=False)]
    p = Prepared(
        "rag",
        lang,
        [],
        hits=[hit()],
        values={
            "persona": "IndexBeast",
            "lang": "en" if lang == "vi" else "vi",
            "spoilers": True,
            "policy": "Return valid JSON with evidence.",
            "history": [],
            "payload": json.dumps({"question": "Who is Ranni?", "text": hit().payload["text"]}),
        },
    )
    generator = Generator(llm)
    if streaming:
        answer = "".join([token async for token in generator.stream(p)])
    else:
        answer = (await generator.generate(p)).answer
    assert answer == llm.data["answer"]
    system = llm.seen[0][0]["content"]
    assert f"Language: {lang}" in system and f"Write all explanatory prose in {target}" in system
    assert "Who is Ranni?" in llm.seen[0][-1]["content"]
    # Phục hồi phải giữ cùng ngôn ngữ đích và evidence có thẩm quyền, không dịch/retrieve lại.
    recovery = generator._inputs(p, 1)
    assert recovery["lang"] == lang and target in recovery["policy"]
    assert recovery["payload"] == p.values["payload"] and p.values["lang"] != lang
