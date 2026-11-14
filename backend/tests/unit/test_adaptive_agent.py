import asyncio
import json
import time
from dataclasses import replace
from uuid import uuid4

import pytest

from app.rag.agent import AgentDecision, check_decision
from app.rag.entity_spelling import close_spelling, correct_name
from app.rag.pipeline import ChatPipeline
from app.rag.rewrite import contains_name
from app.services.chat import LiveChatService
from core.errors import BadRequestError
from tests.unit.test_agent_durable import AgentLLM, plan, req, settings
from tests.unit.test_live_chat import FakeRetriever, hit
from tests.unit.test_tool_agent import ToolsLLM, step
from tests.unit.test_vi_en import RankedRetriever


@pytest.mark.parametrize("query", ["Leyndell Ashen Capital", "Leyndell,  Ashen Capital"])
def test_active_rewrite_accepts_name_punctuation_and_spaces(query):
    question = "How to unlock Leyndell, Ashen Capital?"
    decision = AgentDecision.model_validate(
        plan(resolved_question=question, search_query=query, entities=["Leyndell, Ashen Capital"])
    )
    check_decision(decision, question, [], {})
    assert not contains_name("Leyndell, Royal Capital", "Leyndell, Ashen Capital")
    assert not contains_name("patch 1,10", "patch 1.10")


@pytest.mark.parametrize("typed", ["Mooonveil", "Moonvveeeeil", "Moon veil", "Moonviel"])
def test_spelling_tolerates_common_keyboard_errors(typed):
    assert close_spelling(typed, "Moonveil")
    assert not close_spelling("NG+10", "NG+1")


async def test_name_mismatch_can_fall_back_to_original_self_contained_query():
    question = "Who is Ranni?"
    llm = AgentLLM([plan(search_query="Who is Rennala?")])
    pipe = ChatPipeline(settings(), llm, FakeRetriever())
    prepared = await pipe.prepare(req(question), [])
    assert prepared.trace["rewrite_fallback"]
    assert pipe.retriever.calls == [(question, True)]


def spelling_decision():
    return plan(
        intent="acquisition",
        name_to_check="Mooonveil",
        entities=["Mooonveil"],
        resolved_question="Where to get Mooonveil?",
        search_query="Mooonveil location",
    )


async def test_unique_corpus_name_replaces_typo_but_preserves_original_message():
    llm = ToolsLLM([step("check_name"), step("finish", evidence_ids=["1"])], [spelling_decision()])
    retriever = FakeRetriever([hit(title="Moonveil"), hit(2, title="Ranni")])
    pipe = ChatPipeline(settings(chat_tool_agent_enabled=True), llm, retriever)
    p = await pipe.prepare(req("Mooonveil lấy ở đâu?"), [])
    payload = json.loads(p.values["payload"])
    assert retriever.calls == [("Mooonveil", True)]
    assert llm.observations[1]["name_lookup"]["status"] == "verified"
    assert payload["question"] == "Where to get Moonveil?"
    assert payload["original_user_message"] == "Mooonveil lấy ở đâu?"
    assert [h.id for h in p.hits] == ["1"]
    assert "task_plan" not in payload


@pytest.mark.parametrize(
    ("typed", "canonical"),
    [
        ("Fire Knight Shortsword", "Fire Knight's Shortsword"),
        ("Talisman Blessed Dew", "Blessed Dew Talisman"),
        ("Guranq", "Gurranq, Beast Clergyman"),
        ("St Trinna", "St. Trina"),
        ("Greate Sword", "Greatsword"),
    ],
)
async def test_name_lookup_accepts_a_reordered_full_title_or_omitted_possessive(typed, canonical):
    question = f"Where can I get {typed}?"
    decision = plan(
        intent="acquisition", resolved_question=question, search_query=question, name_to_check=typed, entities=[typed]
    )
    llm = ToolsLLM([step("check_name"), step("finish", evidence_ids=["1"])], [decision])
    retriever = RankedRetriever(rankings={typed: [hit(title=canonical)]})
    prepared = await ChatPipeline(settings(chat_tool_agent_enabled=True), llm, retriever).prepare(req(question), [])
    assert prepared.trace["verified_name"]["canonical"] == canonical
    assert [h.payload["title"] for h in prepared.hits] == [canonical]


def test_expanding_a_shortened_title_does_not_duplicate_a_translated_full_title():
    assert correct_name("Where is the Beast-Repellent Torch?", "Beast-Repellent", "Beast-Repellent Torch") == (
        "Where is the Beast-Repellent Torch?"
    )


async def test_agent_can_verify_a_full_title_on_contextual_search():
    name, title = "Beast-Repellent", "Beast-Repellent Torch"
    question = f"Where is the {title} sold?"
    decision = plan(
        intent="acquisition", resolved_question=question, search_query=question, name_to_check=name, entities=[name]
    )
    llm = ToolsLLM([step("check_name"), step("local_search", question), step("finish", evidence_ids=["1"])], [decision])
    retriever = RankedRetriever(rankings={question: [hit(title=title)]})
    prepared = await ChatPipeline(settings(chat_tool_agent_enabled=True), llm, retriever).prepare(req(question), [])
    assert prepared.trace["verified_name"]["canonical"] == title
    assert json.loads(prepared.values["payload"])["question"] == question


@pytest.mark.parametrize("with_competitor", [False, True])
@pytest.mark.parametrize("search_name", ["Dialloz", "Diallos"])
async def test_agent_can_retry_a_name_miss_with_context_and_asks_when_candidates_conflict(with_competitor, search_name):
    typed = "Dialloz"
    question = f"Who was {typed} looking for at Roundtable Hold?"
    query = f"{search_name} looking for person Roundtable Hold"
    canonical = "Knight Diallos"
    decision = plan(
        intent="quest", resolved_question=question, search_query=question, name_to_check=typed, entities=[typed]
    )
    evidence = [hit(title=canonical, text="At Roundtable Hold, Diallos asks about his missing servant Lanya.")]
    if with_competitor:
        evidence.append(hit(2, title="Captain Diallos", text="A different candidate."))
    last = (
        step(
            "clarify",
            reason="ambiguous_name",
            question="Do you mean Knight Diallos or Captain Diallos?",
            missing=[{"key": "character", "label": "Character"}],
        )
        if with_competitor
        else step("finish", evidence_ids=["1"])
    )
    llm = ToolsLLM([step("check_name"), step("local_search", query), last], [decision])
    retriever = RankedRetriever(rankings={typed: [hit(title="Diallos's Mask")], query: evidence})
    prepared = await ChatPipeline(settings(chat_tool_agent_enabled=True), llm, retriever).prepare(req(question), [])
    assert retriever.calls == [typed, query]
    assert llm.observations[1]["name_lookup"]["status"] == "not_found"
    if with_competitor:
        assert prepared.clarification and not prepared.hits
        assert "verified_name" not in prepared.trace
    else:
        assert prepared.trace["verified_name"]["canonical"] == canonical
        assert [h.payload["title"] for h in prepared.hits] == [canonical]


async def test_ambiguous_corpus_name_asks_and_does_not_choose_a_candidate():
    llm = ToolsLLM(
        [
            step("check_name"),
            step(
                "clarify",
                reason="ambiguous_name",
                question="Bạn muốn hỏi Moonveil hay Moonveil A?",
                missing=[{"key": "weapon", "label": "Vũ khí"}],
            ),
        ],
        [spelling_decision()],
    )
    retriever = FakeRetriever([hit(title="Moonveil"), hit(2, title="Moonveil A", aliases=["Moonveil"])])
    p = await ChatPipeline(settings(chat_tool_agent_enabled=True), llm, retriever).prepare(
        req("Mooonveil lấy ở đâu?"), []
    )
    assert llm.observations[1]["name_lookup"]["status"] == "ambiguous"
    assert p.clarification is not None and not p.hits
    assert "verified_name" not in p.trace


async def test_partial_title_surfaces_two_capitals_for_clarification():
    short = "Leyndell Capital"
    decision = plan(name_to_check=short, entities=[short], resolved_question=short, search_query=short)
    llm = ToolsLLM(
        [
            step("check_name"),
            step(
                "clarify",
                reason="ambiguous_name",
                question="Royal hay Ashen?",
                missing=[{"key": "location", "label": "Địa điểm"}],
            ),
        ],
        [decision],
    )
    retriever = FakeRetriever([hit(title="Leyndell, Royal Capital"), hit(2, title="Leyndell, Ashen Capital")])
    p = await ChatPipeline(settings(chat_tool_agent_enabled=True), llm, retriever).prepare(req(short), [])
    assert p.clarification is not None and not p.hits
    assert llm.observations[1]["name_lookup"]["candidates"] == ["Leyndell, Royal Capital", "Leyndell, Ashen Capital"]


async def test_ram_retry_replays_same_turn_after_concurrent_submissions():
    llm = AgentLLM()
    service = LiveChatService(ChatPipeline(settings(chat_persistence="memory"), llm, FakeRetriever()))
    opened = await service.answer(req())
    request = req(conversation_id=opened.conversation_id, turn_id=uuid4())
    first, second = await asyncio.gather(service.answer(request), service.answer(request))
    assert first.message_id == second.message_id
    assert llm.calls == 2
    assert len(service.history(opened.conversation_id).messages) == 4
    with pytest.raises(BadRequestError):
        await service.answer(request.model_copy(update={"message": "Marika là ai?"}))


@pytest.mark.parametrize("spoilers", [True, False])
async def test_plan_resumes_completed_goal_for_both_legacy_spoiler_values(spoilers):
    question = "Lấy Moonveil ở đâu và chia điểm để dùng Moonveil?"
    resolved = "Where to get Moonveil and how to allocate stats for Moonveil?"
    first = plan(
        intent="build",
        resolved_question=resolved,
        search_query=resolved,
        entities=["Moonveil"],
        subgoals=["Find Moonveil", "Allocate stats"],
    )
    resume = plan(
        intent="build",
        turn_type="clarification_reply",
        resolved_question=resolved + " At level 100.",
        search_query="Moonveil level 100 stats",
        entities=["Moonveil"],
        constraints=[{"key": "level", "value": "100", "source_id": "current"}],
    )
    llm = ToolsLLM(
        [
            step("local_search", "Moonveil location"),
            step(
                "clarify",
                reason="player_detail",
                question="Bạn đang ở level bao nhiêu?",
                missing=[{"key": "level", "label": "Level"}],
                completed_goals={"g1": ["1"]},
            ),
            step("local_search", "Moonveil level 100 stats"),
            step("finish", evidence_ids=["2"], completed_goals={"g2": ["2"]}),
        ],
        [first, resume],
    )
    pipe = ChatPipeline(
        settings(chat_tool_agent_enabled=True), llm, FakeRetriever([hit(title="Moonveil", spoiler_level=2)])
    )
    p = await pipe.prepare(req(question), [])
    saved = json.loads(json.dumps(p.player_state))
    assert saved["plan"][0]["evidence_ids"] == ["1"]
    pipe.retriever = FakeRetriever([hit(2, title="Moonveil", text="Moonveil stat requirements", spoiler_level=0)])
    result = await pipe.prepare(req("Level 100", options={"spoilers": spoilers}), [], player=saved)
    assert llm.observations[2]["task_plan"][0]["evidence_ids"] == ["1"]
    assert [h.id for h in result.hits] == ["1", "2"]
    assert pipe.retriever.calls == [("Moonveil level 100 stats", True)]
    assert "plan" not in result.player_state and "plan_evidence" not in result.player_state


async def test_plan_rejects_invented_source_and_reopens_a_goal():
    llm = ToolsLLM(
        [
            step("local_search", "Ranni"),
            step("finish", completed_goals={"g1": ["fake"]}),
            step("finish", evidence_ids=["1"], reopen_goals=["g1"], completed_goals={"g2": ["1"]}),
        ],
        [plan(subgoals=["Ranni identity", "Ranni role"])],
    )
    pipe = ChatPipeline(settings(chat_tool_agent_enabled=True), llm, FakeRetriever())
    p = await pipe.prepare(req(), [], player={"updated": time.time()})
    assert p.trace["tool_actions"][1]["status"] == "denied"
    assert p.trace["task_plan"][0]["evidence_ids"] == []
    assert p.trace["task_plan"][1]["evidence_ids"] == ["1"]


async def test_invalid_tool_output_gets_retried_within_existing_step_budget():
    llm = ToolsLLM([{"invalid": True}, step("local_search", "Ranni"), step("finish", evidence_ids=["1"])])
    pipe = ChatPipeline(settings(chat_tool_agent_enabled=True), llm, FakeRetriever())
    p = await pipe.prepare(req(), [])
    assert llm.observations[1]["observations"] == [{"status": "invalid_tool_output"}]
    assert len(llm.observations) == 3 and [h.id for h in p.hits] == ["1"]


async def test_question_only_benchmark_can_search_again_and_select_later_web_evidence():
    from app.adapters.tavily import WebHit

    class Web:
        async def search(self, query):
            return [WebHit(query, 0.1, hit(title=query).payload)], {}

    llm = ToolsLLM(
        [
            step("local_search", "Ranni identity"),
            step("local_search", "Ranni parents"),
            step("web_search", "Ranni background"),
            step("web_search", "Ranni quest evidence"),
            step("local_search", "Ranni ending"),
            step("finish", evidence_ids=["Ranni quest evidence"]),
        ]
    )
    config = settings(
        chat_tool_agent_enabled=True,
        chat_tool_steps=None,
        chat_tool_queries=None,
        chat_agent_max_calls=None,
        tavily_api_key="test-key",
    )
    pipe = ChatPipeline(config, llm, FakeRetriever([hit(i) for i in range(30)]), web_search=Web())
    p = await pipe.prepare(req(options={"web_search": "auto"}), [])
    assert len(pipe.retriever.calls) == 3
    assert [h.id for h in p.hits] == ["Ranni quest evidence"]
    assert llm.observations[-1]["remaining_steps"] is None
    assert len(p.trace["model_calls"]) == 8 and p.trace["tool_stop"] == "finish"


@pytest.mark.parametrize("complete_local", [False, True])
async def test_auto_checks_coverage_and_keeps_local_evidence_when_web_fills_a_gap(complete_local):
    from app.adapters.llm import LLMResponse
    from app.adapters.tavily import WebHit
    from tests.unit.test_web_search import FakeSearch, web_hit

    class AssessedAgent(ToolsLLM):
        checks = []

        async def invoke_chain(self, chain, inputs):
            if not inputs.get("policy", "").startswith("Evaluate whether"):
                return await super().invoke_chain(chain, inputs)
            payload = json.loads(inputs["question"])
            self.checks.append(payload)
            context = payload["context"]
            has_web = any(c["origin"] == "web" for c in context)
            enough = complete_local or has_web
            result = {
                "status": "sufficient" if enough else "partial",
                "covered": ["class facts"],
                "missing": [] if enough else ["complete class list"],
                "evidence": {str(c["index"]): ["q0"] for c in context},
                "followup_query": "" if enough else "Elden Ring official all ten starting classes",
            }
            return LLMResponse(json.dumps(result), "fake", 10, 5, "stop")

    question = "Which starting classes are in Elden Ring?"
    llm = AssessedAgent(
        [
            step("local_search", question),
            step("finish", evidence_ids=["1"]),
            step("finish", evidence_ids=["web:classes"]),
        ],
        [plan(resolved_question=question, search_query=question, entities=[])],
    )
    search = FakeSearch(rows=[WebHit("web:classes", 0, {**web_hit().payload, "text": "All ten starting classes."})])
    pipe = ChatPipeline(
        settings(chat_tool_agent_enabled=True, chat_tool_steps=1, chat_agent_max_calls=1, tavily_api_key="test-key"),
        llm,
        FakeRetriever(),
        web_search=search,
    )
    p = await pipe.prepare(req(question, options={"web_search": "auto"}), [])
    assert p.trace["tool_stop"] == "finish"
    assert p.trace["coverage_checks"][-1]["status"] == "sufficient"
    if complete_local:
        assert not search.calls and [h.id for h in p.hits] == ["1"]
    else:
        assert len(search.calls) == 1
        assert search.calls[0].splitlines()[0] == "Elden Ring official all ten starting classes"
        assert p.trace["tool_actions"][1]["status"] == "needs_evidence"
        assert [h.id for h in p.hits] == ["1", "web:classes"]


@pytest.mark.parametrize("scenario", ["one_source", "missing_requirement", "conflicting_requirement"])
async def test_auto_web_coverage_guides_generator_without_requiring_more_sources(scenario):
    from app.adapters.llm import LLMResponse
    from tests.unit.test_web_search import FakeSearch, web_hit

    question = "Moonveil cần bao nhiêu Intelligence?"
    answer = "Moonveil cần 23 Intelligence [1]."
    limitation = None
    lookup = "Moonveil Intelligence requirement and location"
    followup = "Elden Ring Moonveil Intelligence minimum requirements"
    excerpts = [web_hit()]
    gap = []
    if scenario == "missing_requirement":
        excerpts = []
        gap = ["minimum Intelligence requirement"]
    elif scenario == "conflicting_requirement":
        other = web_hit()
        excerpts.append(
            replace(
                other,
                id="web:other",
                payload={
                    **other.payload,
                    "url": "https://eldenring.fandom.com/wiki/Moonveil",
                    "text": "Moonveil requires Intelligence 25.",
                },
            )
        )
        gap = ["minimum Intelligence requirement"]

    if gap:
        question = "Moonveil lấy ở đâu và cần bao nhiêu Intelligence?"
        other = web_hit()
        excerpts.insert(
            0,
            replace(other, id="web:pickup", payload={**other.payload, "text": "Moonveil drops in Gael Tunnel."}),
        )
        answer = "Bạn lấy Moonveil ở Gael Tunnel [1]."
        limitation = (
            "Chưa xác định được mức Intelligence tối thiểu."
            if scenario == "missing_requirement"
            else "Mức Intelligence tối thiểu còn mâu thuẫn."
        )
    evidence_ids = [h.id for h in excerpts]
    checked_fact = ["acquisition location" if gap else "minimum Intelligence requirement"]
    verdict = {
        "status": "partial" if gap else "sufficient",
        "covered": checked_fact,
        "missing": gap,
    }

    class AssessedAgent(ToolsLLM):
        async def invoke_chain(self, chain, inputs):
            if not inputs.get("policy", "").startswith("Evaluate whether"):
                return await super().invoke_chain(chain, inputs)
            assessment = json.loads(inputs["question"])
            assert [row["point_id"] for row in assessment["context"]] == evidence_ids
            assert assessment["context"][0]["source_domain"] == "eldenring.wiki.gg"
            return LLMResponse(
                json.dumps(
                    {
                        **verdict,
                        "evidence": {"1": ["q0"]},
                        "followup_query": followup if gap else "",
                    }
                ),
                "fake",
                10,
                5,
                "stop",
            )

    class Search(FakeSearch):
        async def search(self, query):
            rows, diagnostics = await super().search(query)
            return (rows, diagnostics) if len(self.calls) == 1 else ([], {"selected_urls": 0})

    finish = step("finish", evidence_ids=evidence_ids)
    llm = AssessedAgent(
        [step("web_search", lookup), finish, finish, finish],
        [plan(intent="acquisition", resolved_question=question, search_query=lookup, entities=["Moonveil"])],
    )
    llm.data = {
        "answer": answer,
        "evidence": [{"index": 1, "quote_id": "q0"}],
        "insufficient": False,
        **({"limitation": limitation} if limitation else {}),
    }
    search = Search(rows=excerpts)
    pipe = ChatPipeline(
        settings(chat_tool_agent_enabled=True, tavily_api_key="test-key"),
        llm,
        FakeRetriever([]),
        web_search=search,
    )
    prepared = await pipe.prepare(req(question, options={"web_search": "auto"}), [])
    assert json.loads(prepared.values["payload"])["evidence_coverage"] == verdict
    assert len(search.calls) == (2 if gap else 1)
    if gap:
        assert followup in search.calls[1]
    result = await pipe.generator.generate(prepared)
    assert result.answer == (f"{answer}\n\n{limitation}" if limitation else answer)
    assert result.grounded and len(result.sources) == 1 and result.sources[0].origin == "web"
