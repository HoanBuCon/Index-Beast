"""Offline replays of observed failures. Parser/selection improvements are not a live quality score."""

import json
from contextlib import aclosing
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.adapters.tavily import WebHit
from app.api.schemas.chat import ChatRequest
from app.rag.context_policy import dedup_web
from app.rag.evidence import evidence_units
from app.rag.generator import Prepared, RAGValidationError, validate_answer
from app.rag.pipeline import select_context
from app.rag.prompts import prompt
from tests.unit.test_live_chat import FakeLLM, FakeRetriever, SequenceLLM, hit, service
from tests.unit.test_web_search import web_hit

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures/golden_guard_replays.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("release_scope", "base"),
        ("patch_version", "1.16"),
        ("speaker", "Another"),
        ("variant_context", "alternate"),
        ("affinity", "Cold"),
        ("future_condition", "only at night"),
        ("release_scope", None),
    ],
)
def test_dedup_never_merges_different_conditions(field, value):
    a = web_hit()
    b = replace(a, id="b", payload={**a.payload, "url": a.payload["url"] + "?oldid=1", field: value})
    original = deepcopy(a.payload)
    assert len(dedup_web([a, b])) == 2
    assert a.payload == original


def test_alias_dedup_is_idempotent_and_does_not_merge_titles_or_changed_text():
    rows = [WebHit(h["id"], h["score"], h["payload"]) for h in FIXTURE["context_cases"]["IB-GS-050"]["web"]]
    first = dedup_web(rows[:2])
    combined = dedup_web([*first, rows[2]])
    assert len(combined) == 1 and len(combined[0].payload["provenance"]) == 3
    assert dedup_web(combined) == combined
    assert len(first[0].payload["provenance"]) == 2
    assert len(dedup_web([rows[0], replace(rows[1], payload={**rows[1].payload, "text": "Different body"})])) == 2
    assert len(dedup_web([rows[0], replace(rows[1], payload={**rows[1].payload, "title": "Fia"})])) == 2


def test_no_missing_target_is_fabricated_and_policy_budget_still_apply():
    source = hit(title="Moonveil", text="Some mechanics")
    assert select_context([source], 5, 12000) == [source]
    assert select_context([hit(game_scope=None)], 5, 12000) == []
    assert select_context([source], 5, 1) == []


def test_multiple_quote_ids_resolve_exact_pieces_not_whole_page():
    text = "Useful numeric requirement 23. " * 80 + "\nGallery unrelated notes. " * 40
    units = evidence_units(text)
    ids = list(units)[:2]
    prepared = Prepared("rag", "en", [], hits=[hit(text=text)])
    data = {"answer": "Supported detail [1].", "evidence": [{"index": 1, "quote_ids": ids}], "insufficient": False}
    result = validate_answer(prepared, data)
    assert result.sources[0].text == "\n[…]\n".join(units[q] for q in ids)
    assert all(units[q] in text for q in ids)
    for bad in [["q99"], [ids[0], ids[0]]]:
        with pytest.raises(RAGValidationError):
            validate_answer(prepared, {**data, "evidence": [{"index": 1, "quote_ids": bad}]})
    with pytest.raises(RAGValidationError):
        validate_answer(prepared, {**data, "evidence": [{"index": 1, "quote_id": ids[0], "quote_ids": ids}]})


async def test_observed_build_schema_failure_gets_bounded_clarification_not_a_fake_grounded_answer():
    clarification = {"answer": "Bạn muốn dùng vũ khí nào và chơi PvE hay PvP?", "evidence": [], "insufficient": True}
    llm = SequenceLLM([FIXTURE["build"]["outputs"][0], json.dumps(clarification)])
    live = service("rag", llm, FakeRetriever())
    response = await live.answer(ChatRequest(message="Hướng dẫn build Elden Ring", channel="web"))
    assert llm.attempts == 2 and not response.grounded and not response.sources
    assert response.answer == clarification["answer"]
    assert "Do not include type" in llm.seen[-1]["policy"]
    assert "required" in prompt("answer") and "does NOT establish" in prompt("answer")


def test_observed_invalid_build_outputs_still_cannot_pass_validation():
    for output in FIXTURE["build"]["outputs"]:
        with pytest.raises(RAGValidationError):
            validate_answer(Prepared("rag", "vi", [], hits=[hit(i) for i in range(1, 6)]), json.loads(output))


@pytest.mark.parametrize("streaming", [False, True])
async def test_multiple_quotes_and_partial_answer_keep_json_sse_contract(streaming):
    text = "Requirement value 23 with its stated condition. " * 60 + "\nGallery of unrelated pictures. " * 50
    units = evidence_units(text)
    ids = list(units)[:2]
    llm = FakeLLM()
    llm.data = {
        "answer": "Supported mechanics under the stated condition [1].",
        "evidence": [{"index": 1, "quote_ids": ids}],
        "insufficient": False,
        "limitation": "What level and playstyle do you prefer?",
    }
    llm.tokens = list(json.dumps(llm.data))
    live = service("rag", llm, FakeRetriever([hit(text=text)]))
    request = ChatRequest(message="Help me choose a build", channel="web")
    if streaming:
        async with aclosing(await live.open_stream(request)) as events:
            frames = [frame async for frame in events]
        assert frames[-1][0] == "done" and all(name != "error" for name, _ in frames)
        sources = next(payload for name, payload in frames if name == "sources").sources
        assert llm.closed
    else:
        response = await live.answer(request)
        assert response.grounded and llm.data["limitation"] in response.answer
        sources = response.sources
    assert len(sources) == 1 and sources[0].text == "\n[…]\n".join(units[q] for q in ids)


def test_two_evidence_items_for_one_source_are_merged_not_rejected():
    result = validate_answer(
        Prepared("rag", "en", [], hits=[hit()]),
        {
            "answer": "Ranni is an Empyrean [1].",
            "evidence": [{"index": 1, "quote_id": "q0"}, {"index": 1, "quote_id": "q0"}],
            "insufficient": False,
        },
    )
    assert result.grounded and len(result.sources) == 1 and "[…]" not in result.sources[0].text
