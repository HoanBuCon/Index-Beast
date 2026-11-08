"""Sourced calculation tests use synthetic fixtures, not a claim of live factual correctness."""

import copy
import json

import pytest

from app.rag.build_data import BuildCache, bound_value, check
from app.rag.build_math import ATTRIBUTES
from app.rag.generator import Prepared, RAGValidationError, validate_answer
from tests.unit.test_live_chat import hit


@pytest.fixture(params=[("Vagabond", "Zweihander", 9), ("Hero", "Great Stars", 7), ("Bandit", "Reduvia", 5)])
def build(request):
    cls, weapon, start = request.param
    base = {k: 10 for k in ATTRIBUTES}
    text = f"{cls} starting class; {weapon} one-handed requirements. Starting level: {start}.\n"
    text += "\n".join(f"{k.title()}: {v}" for k, v in base.items())
    text += "\nRequired Strength: 12. Points per level: 1. Attribute cap: 99.\n"
    text += "Respec cannot reduce an attribute below its starting class base value."
    h = hit(1, title=f"{cls} and {weapon}", text=text, release_scope="unknown")

    def n(value, label):
        return {"value": value, "label": label, "source_id": "1", "quote_id": "q0"}

    data = dict(
        starting_class=cls,
        weapon=weapon,
        usage="one_handed_no_bonuses",
        starting_level=n(start, "Starting level"),
        base={k: n(v, k.title()) for k, v in base.items()},
        requirements={"strength": n(12, "Required Strength")},
        points_per_level=n(1, "Points per level"),
        attribute_cap=n(99, "Attribute cap"),
        class_floor_rule={
            "source_id": "1",
            "quote_id": "q0",
            "quote": "Respec cannot reduce an attribute below its starting class base value.",
        },
    )
    allocation = {**base, "strength": 12, "vigor": 10 + 30 - start - 2}
    profile = {"starting_class": cls, "weapon": weapon, "level": "30"}
    return data, allocation, profile, [h]


def test_arbitrary_classes_weapons_and_artifact(build):
    data, allocation, profile, hits = build
    result = check(*build)
    assert result["allocation"] == allocation and result["attribute_total"] == sum(allocation.values())
    assert result["provenance"]["1"]["release_scope"] == "unknown"
    assert not result["optimality_verified"] and result["review_status"] != "approved"
    cache = BuildCache()
    cache.put(data, hits)
    cached, original = cache.get(profile)
    cached["weapon"] = "mutated"
    assert cache.get(profile)[0]["weapon"] == data["weapon"]
    assert "level" not in cache.get(profile)[0] and original[0].id == "1"
    assert cache.get({**profile, "weapon": "Other"}) is None


@pytest.mark.parametrize(
    "error", ["total", "floor", "cap", "requirements", "label", "source", "profile", "usage", "release", "floor_rule"]
)
def test_reject_bad_data_or_math(build, error):
    data, allocation, profile, hits = copy.deepcopy(build)
    if error == "total":
        allocation["vigor"] += 1
    elif error == "floor":
        allocation["mind"] -= 1
        allocation["vigor"] += 1
    elif error == "cap":
        data["attribute_cap"]["value"] = 12
    elif error == "requirements":
        allocation["strength"] = 11
        allocation["vigor"] += 1
    elif error == "label":
        data["base"]["mind"]["label"] = "Missing Header"
    elif error == "source":
        data["base"]["mind"]["source_id"] = "invented"
    elif error == "profile":
        profile["weapon"] = "Other weapon"
    elif error == "usage":
        data["usage"] = "two_handed"
    elif error == "floor_rule":
        data["class_floor_rule"]["quote"] = "An invented respec rule"
    else:
        hits.append(hit(2, text=hits[0].payload["text"], patch_version="2.0"))
        hits[0].payload["patch_version"] = "1.0"
        data["attribute_cap"]["source_id"] = "2"
    with pytest.raises(ValueError):
        check(data, allocation, profile, hits)


def test_headers_are_bound_to_values_and_correct_row():
    q = "| Class | Level | Vigor | Mind |\n| --- | --- | --- | --- |\n| Hero | 7 | 14 | 9 |\n| Vagabond | 9 | 15 | 10 |"
    assert bound_value(q, "Vigor", 15, entity="Vagabond")
    assert not bound_value(q, "Vigor", 10, entity="Vagabond")
    assert not bound_value(q, "Vigor", 14, entity="Vagabond")
    assert not bound_value("Vigor: 15, Mind: 10", "Vigor", 10)


def test_generator_receives_and_renders_checked_allocation(build):
    data, allocation, profile, hits = build
    artifact = check(*build)
    p = Prepared("rag", "vi", [], hits=hits, checked_build=artifact, values={"player_profile": profile})
    raw = {"answer": "Một phương án khả thi [1].", "evidence": [{"index": 1, "quote_id": "q0"}], "insufficient": False}
    out = validate_answer(p, raw)
    for key, value in allocation.items():
        assert f"{key.title()} {value}" in out.answer
    assert json.loads(json.dumps(artifact))["allocation"] == allocation
    with pytest.raises(RAGValidationError):
        validate_answer(p, {**raw, "build_allocation": {**allocation, "vigor": 99}})
    with pytest.raises(RAGValidationError):
        validate_answer(p, {"answer": "Thiếu dữ liệu.", "evidence": [], "insufficient": True})
    artifact["allocation"]["vigor"] += 1
    with pytest.raises(RAGValidationError):
        validate_answer(p, raw)


def test_cache_expires(build, monkeypatch):
    import app.rag.build_data as module

    cache = BuildCache()
    cache.put(build[0], build[3])
    monkeypatch.setattr(module.time, "monotonic", lambda: 10**12)
    assert cache.get(build[2]) is None


async def test_tool_calculator_artifact_survives_context_and_generation(build):

    from app.api.schemas.chat import ChatRequest
    from app.rag.pipeline import ChatPipeline
    from app.rag.tool_agent import run_tools
    from tests.unit.test_agent_durable import settings
    from tests.unit.test_live_chat import FakeRetriever
    from tests.unit.test_tool_agent import ToolsLLM, step

    data, allocation, profile, hits = build
    llm = ToolsLLM(
        [
            step("local_search", "source numerical data"),
            step("calculator", build_data=data, allocation=allocation),
            step("finish", evidence_ids=["1"]),
        ]
    )
    pipe = ChatPipeline(settings(chat_tool_agent_enabled=True), llm, FakeRetriever(hits))
    req = ChatRequest(message="Chia chỉ số cho tôi.", channel="web", options={"web_search": "off"})
    player = {"constraints": [{"key": k, "value": v} for k, v in profile.items()]}
    p = Prepared("rag", "vi", [], player_state=player, max_calls=6, trace={"web_search": {"requested": "off"}})
    state = {
        "prepared": p,
        "req": req,
        "search_mode": "off",
        "resolved_question": req.message,
        "query": "build",
        "history": [],
        "started": 0,
        "next_player": player,
    }
    state = await run_tools(pipe, state)
    assert p.checked_build["allocation"] == allocation
    # No finish IDs / exhausted step budget must still retain every accounting source.
    p.trace.pop("evidence_selection")
    pipe._context(state)
    assert [h.id for h in p.hits] == ["1"]
    result = pipe._prompt(state)
    assert json.loads(result.values["payload"])["checked_build"]["allocation"] == allocation
    assert pipe.build_cache.get(profile)[0] == data
    assert result.values["player_profile"] == profile


def test_attribute_header_cannot_be_swapped_even_if_same_integer(build):
    data, allocation, profile, hits = copy.deepcopy(build)
    data["base"]["vigor"]["label"] = "Mind"
    with pytest.raises(ValueError, match="header"):
        check(data, allocation, profile, hits)


async def test_calculator_validation_feedback_reports_unknown_source_without_accepting(build):
    from app.api.schemas.chat import ChatRequest
    from app.rag.pipeline import ChatPipeline
    from app.rag.tool_agent import run_tools
    from tests.unit.test_agent_durable import settings
    from tests.unit.test_live_chat import FakeRetriever
    from tests.unit.test_tool_agent import ToolsLLM, step

    data, allocation, profile, hits = copy.deepcopy(build)
    data["starting_level"]["source_id"] = "unfetched-snapshot"
    llm = ToolsLLM(
        [step("local_search", "sources"), step("calculator", build_data=data, allocation=allocation), step("finish")]
    )
    pipe = ChatPipeline(settings(chat_tool_agent_enabled=True), llm, FakeRetriever(hits))
    p = Prepared(
        "rag",
        "vi",
        [],
        max_calls=6,
        trace={"web_search": {"requested": "off"}},
        player_state={"constraints": [{"key": k, "value": v} for k, v in profile.items()]},
    )
    req = ChatRequest(message="Build", channel="web")
    await run_tools(
        pipe, {"prepared": p, "req": req, "search_mode": "off", "resolved_question": "Build", "query": "Build"}
    )
    assert p.checked_build is None
    assert llm.observations[2]["observations"][-1]["validation"] == "Unknown numeric source"


@pytest.mark.parametrize("prose", ["Vigor 99 [1].", "| Vigor | Mind |\n| 99 | 99 | [1]"])
def test_generator_cannot_smuggle_different_stats_in_prose(build, prose):
    p = Prepared("rag", "vi", [], hits=build[3], checked_build=check(*build), values={"player_profile": build[2]})
    with pytest.raises(RAGValidationError):
        validate_answer(p, {"answer": prose, "evidence": [{"index": 1, "quote_id": "q0"}], "insufficient": False})


def test_tavily_rendered_attribute_cell_keeps_header_value_binding():
    quote = (
        "| Attribute | Required | Scaling |\n| Image 20: ER Custom Stat Icon Strength (Color).pngStrength: | 5 | E |"
    )
    assert bound_value(quote, "Strength", 5)
    assert not bound_value(quote, "Strength", 20)
    assert not bound_value(quote, "Strength", 13)


@pytest.mark.parametrize("field", ["variant_context", "affinity", "upgrade_level"])
def test_numerical_sources_cannot_mix_explicit_variants(build, field):
    data, allocation, profile, hits = copy.deepcopy(build)
    hits.append(hit(2, text=hits[0].payload["text"]))
    hits[0].payload[field] = {"value": "first"}
    hits[1].payload[field] = {"value": "second"}
    data["attribute_cap"]["source_id"] = "2"
    with pytest.raises(ValueError, match="Conflicting"):
        check(data, allocation, profile, hits)
