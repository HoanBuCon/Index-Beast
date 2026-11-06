"""Offline source-reference and language propagation regressions; no live model quality claim."""

import json

import pytest

from app.rag.agent import AgentDecision, check_decision, normalize_sources
from app.rag.generator import Generator, Prepared
from tests.unit.test_agent_durable import plan
from tests.unit.test_live_chat import FakeLLM, hit


def resume(source="memory-1", value="Moonveil"):
    return AgentDecision.model_validate(
        plan(
            intent="build",
            turn_type="clarification_reply",
            entities=["Moonveil", "Samurai"],
            resolved_question="Moonveil level 100 Samurai PvE",
            search_query="Moonveil level 100 Samurai PvE",
            selected_memory_ids=["memory-1"],
            constraints=[{"key": "weapon", "value": value, "source_id": source}],
        )
    )


MEMORY = {"id": "memory-1", "source_id": "user-message-1", "text": "Chia chỉ số Moonveil", "kind": "topic"}
QUESTION = "Samurai level 100, chủ yếu PvE."


def test_captured_memory_id_shape_maps_to_message_without_changing_value_or_original():
    original = resume()
    fixed, count = normalize_sources(original, [MEMORY], {})
    check_decision(fixed, QUESTION, [MEMORY], {})
    assert count == 1 and fixed.constraints[0].source_id == "user-message-1"
    assert fixed.constraints[0].value == "Moonveil" and original.constraints[0].source_id == "memory-1"
    assert normalize_sources(fixed, [MEMORY], {})[1] == 0


@pytest.mark.parametrize("source,value", [("unknown", "Moonveil"), ("memory-1", "Rivers of Blood")])
def test_alias_normalization_does_not_authorize_unknown_sources_or_values(source, value):
    with pytest.raises(ValueError):
        fixed, _ = normalize_sources(resume(source, value), [MEMORY], {})
        check_decision(fixed, QUESTION, [MEMORY], {})


def test_unselected_memory_is_not_an_alias_and_collisions_fail_closed():
    decision = resume().model_copy(update={"selected_memory_ids": []})
    fixed, count = normalize_sources(decision, [MEMORY], {})
    assert count == 0
    with pytest.raises(ValueError):
        check_decision(fixed, QUESTION, [MEMORY], {})
    with pytest.raises(ValueError, match="Ambiguous"):
        normalize_sources(
            resume(), [MEMORY], {"constraints": [{"source_id": "memory-1", "key": "other", "value": "x"}]}
        )


def test_normalization_keeps_superseded_constraint_guard():
    old = {**MEMORY, "text": "Moonveil", "kind": "topic"}
    working = {"constraints": [{"key": "weapon", "value": "Uchigatana", "source_id": "new-message"}]}
    fixed, _ = normalize_sources(resume(), [old], working)
    with pytest.raises(ValueError, match="Superseded"):
        check_decision(fixed, QUESTION, [old], working)


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
    # Recovery must keep the same authoritative target and evidence, not translate/retrieve again.
    recovery = generator._inputs(p, 1)
    assert recovery["lang"] == lang and target in recovery["policy"]
    assert recovery["payload"] == p.values["payload"] and p.values["lang"] != lang
