import json
from contextlib import aclosing

import pytest

from app.adapters.llm import LLMResponse
from app.rag.agent import AgentDecision, DecisionError, check_decision, decide
from tests.unit.test_agent_durable import AgentLLM, plan, req, service, settings
from tests.unit.test_live_chat import FakeRetriever, hit
from tests.unit.test_tool_agent import ToolsLLM, step

ROOT = "giờ đi đâu tiếp"
REPLY = "vừa xong tutorial"


def route_decision(**changes):
    return plan(
        **{
            "intent": "route",
            "turn_type": "clarification_reply",
            "entities": [],
            "resolved_question": "Where should I go after finishing the tutorial in Elden Ring?",
            "search_query": "Elden Ring after tutorial Cave of Knowledge and The First Step route",
            "search_hypotheses": ["Cave of Knowledge", "The First Step"],
            "constraints": [{"key": "progress", "value": REPLY, "source_id": "current"}],
            **changes,
        }
    )


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("tool_agent", [False, True])
async def test_tutorial_clarification_resumes_route_without_entity(stream, tool_agent):
    ask = plan(
        intent="route",
        action="clarify",
        entities=[],
        reply="Bạn vừa tới đoạn nào?",
        missing=[{"key": "progress", "label": "Tiến độ", "input_type": "text"}],
        reason="missing_player_details",
    )

    def resume(payload):
        assert payload["question"] == REPLY
        assert payload["working_state"]["request_text"] == ROOT
        assert payload["working_state"]["pending"]["question"] == ask["reply"]
        assert payload["memories"] == []
        return route_decision()

    search = route_decision()["search_query"]
    llm = (
        ToolsLLM([step("local_search", search), step("finish", evidence_ids=["1"])], [ask, resume])
        if tool_agent
        else AgentLLM([ask, resume])
    )
    llm.data = {
        "answer": "Nếu bạn đã ra tới The First Step, hãy đi về phía Church of Elleh [1].",
        "evidence": [{"index": 1, "quote_id": "q0"}],
        "insufficient": False,
    }
    llm.tokens = list(json.dumps(llm.data, ensure_ascii=False))
    live = service(llm=llm, chat_history_messages=0, chat_tool_agent_enabled=tool_agent)
    live.pipeline.retriever = FakeRetriever(
        [hit(title="Early route", text="From The First Step, travel to the Church of Elleh.")]
    )
    first = await live.answer(req(ROOT, options={"web_search": "off"}))
    assert first.clarification is not None and not live.pipeline.retriever.calls
    request = req(
        REPLY,
        conversation_id=first.conversation_id,
        clarification_id=first.clarification.id,
        options={"web_search": "off"},
    )
    if stream:
        async with aclosing(await live.open_stream(request)) as events:
            frames = [frame async for frame in events]
        assert frames[-1][0] == "done"
        assert any(kind == "token" for kind, _ in frames)
    else:
        result = await live.answer(request)
        assert result.clarification is None and result.grounded
    assert live.pipeline.retriever.calls == [(search, True)]
    if tool_agent:
        assert llm.observations[0]["search_hypotheses"] == ["Cave of Knowledge", "The First Step"]
    stored = live.history(first.conversation_id)
    assert [m.content for m in stored.messages if m.role == "user"] == [ROOT, REPLY]
    assert "Nếu bạn đã ra tới" in stored.messages[-1].content
    assert len(stored.messages[-1].sources) == 1
    state = live._conversations[first.conversation_id].player
    assert state["pending"] is None
    assert [(c["key"], c["value"]) for c in state["constraints"]] == [("progress", REPLY)]
    prompt = llm.seen[-1][-1]["content"]
    assert route_decision()["resolved_question"] in prompt and "Cave of Knowledge" not in prompt


@pytest.mark.parametrize("reply", ["nói tiếp về nó", "rồi", "xong rồi"])
def test_followup_without_agent_confirmed_context_cannot_search(reply):
    decision = route_decision(constraints=[])
    with pytest.raises(DecisionError) as error:
        check_decision(
            AgentDecision.model_validate(decision), reply, [], {"request_text": ROOT, "pending": {"id": "1"}}
        )
    assert error.value.reason == "missing_followup_context"


@pytest.mark.parametrize(
    "original,reply,entity,mistranslated,corrected",
    [
        (
            "Chia tám chỉ số để dùng Reduvia một tay giúp tôi.",
            "Bandit level 70, chủ yếu PvE và không dùng đồ cộng chỉ số.",
            "Reduvia",
            "Reduvia level 70 Bandit PvE allocation of 8 points without stat bonuses",
            "Reduvia level 70 Bandit PvE spread across eight attributes without stat bonuses",
        ),
        (
            "Nêu hai cách vào Leyndell.",
            "Bản gốc, tôi muốn tránh boss tùy chọn.",
            "Leyndell",
            "2 routes to Leyndell in the base game avoiding optional bosses",
            "Two routes to Leyndell in the base game avoiding optional bosses",
        ),
    ],
)
@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_model_repairs_numeric_meaning_or_searches_verbatim(
    original, reply, entity, mistranslated, corrected, repair_succeeds
):
    bad = plan(
        turn_type="clarification_reply",
        intent="build" if entity == "Reduvia" else "route",
        entities=[entity],
        resolved_question=mistranslated,
        search_query=mistranslated,
    )

    def repair(payload):
        assert payload["repair"]["reason"] == "changed_numeric_constraints"
        assert payload["working_state"]["request_text"] == original
        return {**bad, "resolved_question": corrected, "search_query": corrected} if repair_succeeds else bad

    trace = {}
    result = await decide(
        AgentLLM([bad, repair]), reply, [], {"request_text": original, "pending": {"id": "1"}}, "vi", settings(), trace
    )
    assert result is not None
    assert result.search_query == (corrected if repair_succeeds else f"{original}\n{reply}")
    assert result.turn_type == "clarification_reply"
    assert trace["agent"]["reason"] == ("ready" if repair_succeeds else "original_query_fallback")


async def test_vague_reply_can_repair_to_a_specific_clarification():
    def repair(payload):
        assert "lacks a resolved subject or progression milestone" in payload["repair"]["validation_error"]
        return route_decision(
            action="clarify",
            search_hypotheses=[],
            constraints=[],
            missing=[{"key": "progress", "label": "Tiến độ"}],
            reply="Bạn vừa hoàn thành đoạn nào?",
            reason="missing_player_details",
        )

    llm = AgentLLM([route_decision(constraints=[]), repair])
    result = await decide(
        llm, "nói tiếp về nó", [], {"request_text": ROOT, "pending": {"id": "1"}}, "vi", settings(), {}
    )
    assert result is not None and result.action == "clarify"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        (
            {"constraints": [{"key": "progress", "value": "beat Margit", "source_id": "current"}]},
            "unverified_constraint",
        ),
        ({"entities": ["Cave of Knowledge"]}, "unverified_entity"),
        ({"resolved_question": "Where should I go from Cave of Knowledge?"}, "invalid_search_hypothesis"),
        (
            {"search_query": "Elden Ring tutorial route Cave of Knowledge at level 100 The First Step"},
            "changed_numeric_constraints",
        ),
    ],
)
def test_progress_and_search_hypotheses_do_not_authorize_invented_facts(changes, reason):
    with pytest.raises(DecisionError) as error:
        check_decision(
            AgentDecision.model_validate(route_decision(**changes)),
            REPLY,
            [],
            {"request_text": ROOT, "pending": {"id": "1"}},
        )
    assert error.value.reason == reason


@pytest.mark.parametrize("reason", ["missing_followup_context", "invalid_decision_schema", "invalid_json"])
async def test_failed_decision_logs_only_classification_and_retry_count(caplog, reason):
    class BrokenJSON(AgentLLM):
        async def invoke_chain(self, *args, **kwargs):
            return LLMResponse("invalid JSON marker", "fake", 10, 5, "stop")

    llm = {
        "missing_followup_context": AgentLLM([route_decision(constraints=[])]),
        "invalid_decision_schema": AgentLLM([{"unexpected": "model output marker"}]),
        "invalid_json": BrokenJSON(),
    }[reason]
    trace = {}
    result = await decide(llm, REPLY, [], {"request_text": ROOT, "pending": {"id": "1"}}, "vi", settings(), trace)
    assert result is None and trace["agent"]["validation_reason"] == reason
    record = next(r for r in caplog.records if r.message == "Agent decision rejected")
    assert record.data == {"reason": reason, "repair_attempts": int(reason == "missing_followup_context")}
    assert REPLY not in caplog.text and "marker" not in caplog.text
