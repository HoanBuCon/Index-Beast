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
from app.rag.pipeline import ChatPipeline, select_context
from app.rag.prompts import prompt
from app.rag.retriever import document_to_hit, hit_to_document
from app.rag.rewrite import RewriteResult, rewrite_problem
from app.rag.web_search import Assessment, assess, merge_evidence
from core.corpus import CorpusPolicy
from core.types import Hit
from tests.unit.test_live_chat import BODY, FakeLLM, FakeRetriever, SequenceLLM, hit, service
from tests.unit.test_vi_en import ScriptedLLM
from tests.unit.test_web_search import FakeSearch, RankedRetriever, settings, web_hit

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures/golden_guard_replays.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("row", FIXTURE["assessments"], ids=lambda r: r["id"])
async def test_observed_assessor_outputs_have_lossless_evidence_contract(row):
    data = json.loads(row["output"])
    result, trace = await assess(ScriptedLLM(row["output"]), row["question"], [], row["context"], 1)
    assert result == data["status"] and trace["reason"] == "assessed"
    assert trace["decision"] == "local_" + data["status"]
    assert Assessment.model_validate(data).evidence == data["evidence"]


@pytest.mark.parametrize("row", FIXTURE["rewrites"], ids=lambda r: r["id"])
def test_observed_correct_rewrites_are_not_rejected_as_missing_names(row):
    output = RewriteResult.model_validate(row["output"])
    assert rewrite_problem(row["question"], output.standalone_query_en, output.entities, []) is None


@pytest.mark.parametrize("evidence", [{"1": "q0"}, {"1": ["q0"]}, {"1": ["q1", "q2"]}])
async def test_legacy_and_multiple_assessment_references_are_preserved(evidence):
    data = {"status": "sufficient", "covered": ["effect"], "missing": [], "evidence": evidence}
    context = [{"index": 1, "evidence_units": {"q0": "whole", "q1": "first", "q2": "second"}}]
    result, _ = await assess(ScriptedLLM(data), "effect?", [], context, 1)
    assert result == "sufficient"
    expected = [evidence["1"]] if isinstance(evidence["1"], str) else evidence["1"]
    assert Assessment.model_validate(data).evidence["1"] == expected


@pytest.mark.parametrize(
    "changes",
    [
        {"evidence": {"1": []}},
        {"evidence": {"1": ["q0", "q0"]}},
        {"evidence": {"1": ["q99"]}},
        {"evidence": {"2": ["q0"]}},
        {"evidence": {"1": True}},
        {"evidence": {"1": [0]}},
        {"evidence": {"1": ["q0", "q1", "q2", "q3"]}},
        {"evidence": {}},
        {"covered": []},
        {"covered": [" "]},
        {"missing": ["requested amount"]},
    ],
)
async def test_bad_coverage_never_becomes_sufficient(changes):
    data = {"status": "sufficient", "covered": ["effect"], "missing": [], "evidence": {"1": ["q0"]}, **changes}
    result, trace = await assess(ScriptedLLM(data), "effect?", [], [{"index": 1, "evidence_units": {"q0": "text"}}], 1)
    assert result == "error" and trace["decision"] == "assessment_error"


async def test_actual_list_output_skips_web_when_sufficient_and_error_reason_stays_distinct():
    row = FIXTURE["assessments"][0]
    llm = ScriptedLLM(row["output"])
    pipe = ChatPipeline(settings(), llm, RankedRetriever(), web_search=FakeSearch())
    from app.rag.retriever import hit_to_document

    context_hits = [hit(i, text="Fixture source content") for i in range(1, 6)]
    state = {
        "prepared": Prepared("rag", "vi", [], trace={"web_search": {}}),
        "search_mode": "auto",
        "query": row["question"],
        "history": [],
        "req": ChatRequest(**BODY),
        "documents": [hit_to_document(h) for h in context_hits],
    }
    await pipe._web(state)
    assert not pipe.web_search.calls and state["prepared"].trace["web_search"]["status"] == "local_sufficient"
    pipe.llm = ScriptedLLM("bad JSON")
    await pipe._web(state)
    assert pipe.web_search.calls and state["prepared"].trace["web_search"]["trigger"] == "assessment_error"


@pytest.mark.parametrize(
    "question,query,entities",
    [
        ("Ranni là ai?", "Who is Rannith?", ["Ranni"]),
        ("Moonveil build level 80", "Moonveil build level 150", ["Moonveil"]),
        ("Moonveil build không dùng khiên", "Moonveil build with a shield", ["Moonveil"]),
        ("Moonveil build PvP", "Moonveil build PvE", ["Moonveil"]),
        ("Lấy Moonveil ở đâu?", "Moonveil lore", ["Moonveil"]),
        ("Revered Spirit Ash", "Revered Spirit ashes of war", ["Revered Spirit Ash"]),
    ],
)
def test_entity_number_negation_and_intent_guards_remain(question, query, entities):
    assert rewrite_problem(question, query, entities, []) is not None


def replay_context(key):
    case = FIXTURE["context_cases"][key]
    output = json.loads(case["query"])
    local = [Hit(h["id"], h["score"], h["payload"]) for h in case["local"]]
    web = [WebHit(h["id"], h["score"], h["payload"]) for h in case["web"]]
    chosen = select_context(
        merge_evidence(local, web),
        5,
        12000,
        policy=CorpusPolicy("pilot", ("en",)),
        entities=output["entities"],
        query=output["standalone_query_en"],
    )
    return chosen


def test_real_stone_comparison_reserves_both_targets_with_description_evidence():
    chosen = replay_context("IB-GS-044")
    assert len(chosen) <= 5
    normal = [h for h in chosen if h.payload["title"] == "Ancient Dragon Smithing Stone"]
    special = [h for h in chosen if h.payload["title"] == "Somber Ancient Dragon Smithing Stone"]
    assert any("+25" in h.payload["text"] for h in normal)
    assert any("+10" in h.payload["text"] for h in special)


def test_real_quest_case_keeps_negative_requirement_and_dedups_aliases():
    chosen = replay_context("IB-GS-050")
    assert len(chosen) <= 5
    assert any("not necessary to complete Ranni" in h.payload["text"] for h in chosen)
    # Local quest evidence may legitimately fill the selected context. Inspect dedup at merge,
    # without forcing unrelated web material into a now-sufficient local answer.
    web = dedup_web([WebHit(h["id"], h["score"], h["payload"]) for h in FIXTURE["context_cases"]["IB-GS-050"]["web"]])
    assert len(web) == 1 and len(web[0].payload["provenance"]) == 3
    roundtrip = document_to_hit(hit_to_document(web[0]))
    assert roundtrip.payload == web[0].payload  # No metadata is lost by LangChain conversion.


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
    selected = select_context([source], 5, 12000, entities=["Ranni", "Moonveil"], query="equipment requirements")
    assert selected == [source]
    assert select_context([hit(game_scope=None)], 5, 12000, entities=["Ranni"], query="quest") == []
    assert select_context([source], 5, 1, entities=["Moonveil"], query="requirements") == []


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


def test_duplicate_evidence_source_is_rejected_instead_of_silent_overwrite():
    with pytest.raises(RAGValidationError) as failure:
        validate_answer(
            Prepared("rag", "en", [], hits=[hit()]),
            {
                "answer": "Ranni is an Empyrean [1].",
                "evidence": [{"index": 1, "quote_id": "q0"}, {"index": 1, "quote_id": "q0"}],
                "insufficient": False,
            },
        )
    assert failure.value.reason == "duplicate_evidence_index"
