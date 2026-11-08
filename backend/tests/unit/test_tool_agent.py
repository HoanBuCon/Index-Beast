"""Scripted decisions exercise orchestration, not live semantic accuracy."""

import json

import pytest

from app.adapters.llm import LLMResponse
from app.rag.generator import Prepared, RAGValidationError, validate_answer
from app.rag.pipeline import ChatPipeline
from core.errors import UnavailableError
from tests.unit.test_agent_durable import AgentLLM, plan, req, settings
from tests.unit.test_live_chat import FakeRetriever


class ToolsLLM(AgentLLM):
    def __init__(self, actions):
        super().__init__()
        self.actions = iter(actions)
        self.observations = []

    async def invoke_chain(self, chain, inputs):
        if inputs.get("policy", "").startswith("You are IndexBeast's bounded tool"):
            self.observations.append(json.loads(inputs["question"]))
            return LLMResponse(json.dumps(next(self.actions)), "fake", 10, 5, "stop")
        return await super().invoke_chain(chain, inputs)


def step(action, query="", **kw):
    return {"action": action, "query": query, "reason": "missing_evidence", **kw}


def pipeline(llm, **kw):
    return ChatPipeline(settings(chat_tool_agent_enabled=True, **kw), llm, FakeRetriever())


async def test_model_can_change_query_after_observations_without_legacy_routing(monkeypatch):
    import app.rag.gameplay_knowledge as snapshots
    import app.services.gameplay as legacy

    def forbidden(*args, **kwargs):
        raise AssertionError("legacy rule path used")

    monkeypatch.setattr(legacy, "advance", forbidden)
    monkeypatch.setattr(snapshots, "supplements", forbidden)
    llm = ToolsLLM([step("local_search", "Ranni identity"), step("local_search", "Ranni parents"), step("finish")])
    pipe = pipeline(llm)
    p = await pipe.prepare(req(), [])
    assert [c[0] for c in pipe.retriever.calls] == ["Ranni identity", "Ranni parents"]
    assert llm.observations[1]["observations"][0]["returned"] > 0
    assert p.hits and p.trace["tool_stop"] == "finish"


async def test_duplicate_queries_are_not_executed_again():
    llm = ToolsLLM([step("local_search", "Ranni identity"), step("local_search", " RANNI  identity "), step("finish")])
    pipe = pipeline(llm)
    p = await pipe.prepare(req(), [])
    assert len(pipe.retriever.calls) == 1
    assert p.trace["tool_actions"][1]["status"] == "denied"


async def test_off_forbids_web_and_preserves_local_answer():
    llm = ToolsLLM([step("web_search", "Ranni"), step("local_search", "Ranni"), step("finish")])
    p = await pipeline(llm).prepare(req(options={"web_search": "off"}), [])
    assert "web_search" not in llm.observations[0]["available_actions"]
    assert p.trace["tool_actions"][0]["status"] == "denied"
    assert p.hits


async def test_clarification_is_model_generated_and_resumable():
    llm = ToolsLLM(
        [
            step(
                "clarify",
                reason="player_detail",
                question="Bạn muốn biết khía cạnh nào?",
                missing=[{"key": "aspect", "label": "Khía cạnh"}],
            )
        ]
    )
    p = await pipeline(llm).prepare(req(), [])
    assert p.clarification.question == "Bạn muốn biết khía cạnh nào?"
    assert p.player_state["pending"]["id"] == str(p.clarification.id)


async def test_missing_game_evidence_does_not_create_clarification_or_generate_without_sources():
    llm = ToolsLLM(
        [
            step("local_search", "Ranni identity"),
            step("clarify", question="Bạn có thông tin nào không?", missing=[{"key": "evidence", "label": "Nguồn"}]),
            step("stop"),
        ]
    )
    pipe = pipeline(llm)
    p = await pipe.prepare(req(), [])
    result = await pipe.generator.generate(p)
    assert p.trace["tool_actions"][1]["status"] == "denied"
    assert p.trace["evidence_selection"] == {"method": "model", "ids": []}
    assert p.clarification is None and p.player_state["pending"] is None
    assert result.answer == "Mình chưa có đủ thông tin để trả lời câu này."
    assert not result.sources and not result.grounded and llm.calls == 0


@pytest.mark.parametrize("streaming", [False, True])
async def test_comparison_passes_selected_options_and_keeps_recommendation(streaming):
    from tests.unit.test_live_chat import hit

    query = "Elden Ring starting classes starting gear and playstyle comparison"
    llm = ToolsLLM([step("local_search", query), step("finish", evidence_ids=["1", "2"])])
    llm.decisions = [plan(intent="gameplay_comparison", entities=[], resolved_question=query, search_query=query)]
    llm.data = {
        "answer": "A có khiên từ đầu [1]. B có gậy dùng phép [2].",
        "evidence": [{"index": 1, "quote_id": "q0"}, {"index": 2, "quote_id": "q0"}],
        "insufficient": False,
        "recommendation": "Nếu muốn tập cận chiến và đỡ đòn, mình chọn A. Nếu thích phép, chọn B.",
    }
    llm.tokens = list(json.dumps(llm.data))
    pipe = pipeline(llm)
    pipe.retriever = FakeRetriever(
        [
            hit(1, title="Class A", text="Class A starts with a shield for melee.", url="https://example.test/a"),
            hit(2, title="Class B", text="Class B starts with a staff for spells.", url="https://example.test/b"),
        ]
    )
    p = await pipe.prepare(req("class tốt nhất đầu game"), [])
    expected = llm.data["answer"] + "\n\n" + llm.data["recommendation"]
    if streaming:
        assert "".join([token async for token in pipe.generator.stream(p)]) == expected
        result = p.trace["result"]
    else:
        result = await pipe.generator.generate(p)
    assert llm.observations[0]["intent"] == "gameplay_comparison"
    assert p.clarification is None and result.grounded
    assert result.answer == expected
    assert p.trace["answer_basis"] == "evidence_with_recommendation"
    assert [source.url for source in result.sources] == ["https://example.test/a", "https://example.test/b"]


@pytest.mark.parametrize("streaming", [False, True])
async def test_gameplay_advice_can_answer_with_empty_retrieval_without_claiming_sources(streaming):
    query = "Elden Ring beginner dodge or block trade-offs"
    llm = ToolsLLM([step("local_search", query), step("stop")])
    llm.decisions = [plan(intent="mechanics", entities=[], resolved_question=query, search_query=query)]
    llm.data = {
        "answer": "Nếu khó canh thời điểm né, hãy tập đỡ những đòn dễ đọc rồi xen kẽ né khi đã quen.",
        "evidence": [],
        "insufficient": False,
        "advisory": True,
    }
    llm.tokens = list(json.dumps(llm.data))
    pipe = pipeline(llm)
    pipe.retriever = FakeRetriever([])
    p = await pipe.prepare(req("Mới chơi nên tập né hay đỡ đòn?", options={"web_search": "off"}), [])
    assert p.static_answer is None and p.clarification is None
    if streaming:
        assert "".join([token async for token in pipe.generator.stream(p)]) == llm.data["answer"]
        result = p.trace["result"]
    else:
        result = await pipe.generator.generate(p)
    assert result.answer == llm.data["answer"] and not result.grounded and not result.sources
    assert p.trace["answer_basis"] == "gameplay_advice"


@pytest.mark.parametrize("intent", ["lore", "comparison", "mechanics"])
async def test_unverified_advice_is_blocked_for_lore_and_no_spoilers(intent):
    query = "Elden Ring Marika"
    llm = ToolsLLM([step("local_search", query), step("stop")])
    llm.decisions = [plan(intent=intent)]
    pipe = pipeline(llm)
    p = await pipe.prepare(req(options={"spoilers": intent != "mechanics"}), [])
    assert not p.gameplay_advice and p.static_answer is not None
    with pytest.raises(RAGValidationError, match="trích dẫn"):
        validate_answer(p, {"answer": "A claim.", "evidence": [], "insufficient": False, "advisory": True})


@pytest.mark.parametrize("extra", [{"answer": "Advice [1]"}, {"insufficient": True}, {"limitation": "Unverified"}])
def test_gameplay_advice_keeps_citation_and_status_contract(extra):
    p = Prepared("rag", "en", [], gameplay_advice=True)
    with pytest.raises(RAGValidationError) as error:
        validate_answer(p, {"answer": "Advice.", "evidence": [], "insufficient": False, "advisory": True, **extra})
    assert error.value.reason == "invalid_gameplay_advice"


async def test_failed_local_search_without_evidence_is_a_service_error():
    pipe = pipeline(ToolsLLM([step("local_search", "Ranni identity"), step("stop")]))
    pipe.retriever = FakeRetriever(missing=True)
    with pytest.raises(UnavailableError, match="Không thể truy vấn"):
        await pipe.prepare(req(), [])


async def test_retrieving_after_a_clarification_does_not_reset_the_tool_question_budget():
    llm = ToolsLLM(
        [step("clarify", reason="player_detail", question="Còn điều gì?", missing=[{"key": "goal", "label": "Goal"}])]
    )
    llm.decisions = [
        plan(
            action="clarify",
            reason="ambiguous_subject",
            reply="Bạn đang nói về ai?",
            missing=[{"key": "subject", "label": "Nhân vật"}],
        ),
        plan(turn_type="clarification_reply"),
    ]
    pipe = pipeline(llm, chat_tool_steps=1)
    first = await pipe.prepare(req(), [])
    first.player_state["clarification_rounds"] = 3
    resumed = await pipe.prepare(req("Ranni", clarification_id=first.clarification.id), [], player=first.player_state)
    assert "clarify" not in llm.observations[0]["available_actions"]
    assert resumed.clarification is None
    assert resumed.trace["tool_actions"][0]["status"] == "denied"


async def test_budget_reserves_generation_and_does_not_loop():
    llm = ToolsLLM([step("local_search", "Ranni")])
    p = await pipeline(llm, chat_agent_max_calls=3).prepare(req(), [])
    assert len(llm.observations) == 1 and p.trace["tool_stop"] == "model_budget"


async def test_always_cannot_finish_without_search():
    # No web provider/key: existing requested-always availability contract still applies.
    llm = ToolsLLM([step("finish")])
    pipe = pipeline(llm)
    with pytest.raises(UnavailableError):
        await pipe.prepare(req(options={"web_search": "always"}), [])


async def test_unknown_calculator_is_not_exposed_without_sources():
    llm = ToolsLLM([step("calculator", allocation={"vigor": 50}), step("stop")])
    p = await pipeline(llm).prepare(req(), [])
    assert "calculator" not in llm.observations[0]["available_actions"]
    assert p.trace["tool_actions"][0]["status"] == "denied"


def test_benchmark_plan_has_no_client_or_model(monkeypatch, capsys):
    from scripts.benchmark_agent import main

    main(["--manifest", "eval/agent_tools_10.json", "--max-turns", "3"])
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "PLAN ONLY" and output["turns"] == 3


@pytest.mark.parametrize("mode", ["auto", "always"])
async def test_model_can_search_web_preserving_unknown_metadata_and_origin(mode):
    from tests.unit.test_web_search import FakeSearch, web_hit

    llm = ToolsLLM([step("web_search", "Moonveil requirements Elden Ring"), step("finish")])
    pipe = pipeline(llm, tavily_api_key="offline-test-key")
    pipe.web_search = FakeSearch(rows=[web_hit()])
    p = await pipe.prepare(req(options={"web_search": mode}), [])
    assert p.hits[0].payload["game_scope"] == "unknown"
    assert p.hits[0].payload["review_status"] == "unreviewed"
    assert p.values["payload"].find('"origin": "web"') >= 0


def test_live_four_snapshot_selection_is_valid_but_not_unbounded():
    from pydantic import ValidationError

    from app.rag.tool_agent import ToolStep

    decision = step("source_snapshot", snapshot_ids=["a", "b", "c", "d"])
    assert len(ToolStep.model_validate(decision).snapshot_ids) == 4
    with pytest.raises(ValidationError):
        ToolStep.model_validate({**decision, "snapshot_ids": [str(i) for i in range(6)]})


def test_resume_does_not_replay_even_uncertain_in_flight_turns():
    from scripts.diagnose_agent_memory import remaining_cases

    cases = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    report = {"attempted_turns": 2, "rows": [{"id": "a", "status": "ok"}, {"id": "b", "status": "running"}]}
    assert remaining_cases(report, cases) == [{"id": "c"}]
    with pytest.raises(ValueError):
        remaining_cases({**report, "attempted_turns": 1}, cases)


async def test_failed_web_is_observed_and_cancelled_tool_propagates():
    import asyncio

    from tests.unit.test_web_search import FakeSearch

    llm = ToolsLLM([step("web_search", "Ranni"), step("stop")])
    pipe = pipeline(llm, tavily_api_key="offline-test-key")
    from app.adapters.tavily import WebSearchError

    pipe.web_search = FakeSearch(error=WebSearchError("network"))
    with pytest.raises(UnavailableError):
        await pipe.prepare(req(), [])
    assert llm.observations[1]["observations"][0]["status"] == "error"

    started = asyncio.Event()

    async def cancelled(*args):
        started.set()
        await asyncio.Future()

    pipe = pipeline(ToolsLLM([step("web_search", "Ranni")]), tavily_api_key="offline-test-key")
    pipe.web_search = type("Search", (), {"search": cancelled})()
    task = asyncio.create_task(pipe.prepare(req(), []))
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_final_evidence_is_model_selected_without_keyword_order(monkeypatch):
    import app.rag.pipeline as module

    def forbidden(*args, **kw):
        raise AssertionError("Keyword coverage routing was used")

    monkeypatch.setattr(module, "coverage_order", forbidden)
    llm = ToolsLLM([step("local_search", "Ranni"), step("finish", evidence_ids=["3", "1"])])
    from tests.unit.test_live_chat import hit

    pipe = pipeline(llm)
    pipe.retriever = FakeRetriever(
        [hit(1), hit(2, text="Ranni additional fact two."), hit(3, text="Ranni additional fact three.")]
    )
    p = await pipe.prepare(req(), [])
    assert [h.id for h in p.hits] == ["3", "1"]
    assert p.trace["evidence_selection"]["method"] == "model"
    assert len(llm.observations[1]["candidates"]) >= 3


async def test_evidence_rank_fallback_is_explicit_not_keyword(monkeypatch):
    import app.rag.pipeline as module

    monkeypatch.setattr(module, "coverage_order", lambda *a, **kw: pytest.fail("keyword fallback"))
    p = await pipeline(ToolsLLM([step("local_search", "Ranni"), step("finish")])).prepare(req(), [])
    assert p.trace["evidence_selection"] == {"method": "rank_fallback", "ids": []}
    assert p.hits


@pytest.mark.parametrize("ids", [["fake"], ["1", "1"]])
async def test_evidence_selector_rejects_invented_or_duplicate_ids(ids):
    p = await pipeline(ToolsLLM([step("local_search", "Ranni"), step("finish", evidence_ids=ids)])).prepare(req(), [])
    assert p.trace["evidence_selection"] == {"method": "rank_fallback", "ids": [], "reason": "invalid_or_duplicate_id"}
    assert p.hits and all(h.id != "fake" for h in p.hits)


@pytest.mark.parametrize("mode", ["off", "auto", "always"])
def test_media_benchmark_plan_honors_modes_and_never_calls_clients(tmp_path, capsys, mode):
    from scripts.benchmark_agent import main

    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps([{"id": "one", "question": "Ranni?", "lang": "vi", "web_search": mode}]), encoding="utf-8"
    )
    main(["--manifest", str(path), "--probe-images"])
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "PLAN ONLY" and result["manifest"]["cases"][0]["web_search"] == mode


async def test_selected_original_web_id_is_not_lost_by_duplicate_merging():
    from app.adapters.tavily import WebHit
    from tests.unit.test_web_search import FakeSearch, web_hit

    first = web_hit()
    second = WebHit("second-web-id", first.score, {**first.payload, "url": "https://eldenring.wiki.gg/wiki/Equivalent"})
    llm = ToolsLLM([step("web_search", "Ranni"), step("finish", evidence_ids=[second.id])])
    pipe = pipeline(llm, tavily_api_key="offline-test-key")
    pipe.web_search = FakeSearch(rows=[first, second])
    p = await pipe.prepare(req(options={"web_search": "always"}), [])
    assert [h.id for h in p.hits] == [second.id]
    assert p.hits[0].payload == second.payload
