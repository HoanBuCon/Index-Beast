"""The Agent loop that prepares every RAG turn: real tools and guards, a scripted tool-calling model."""

import json
from uuid import UUID

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from app.api.schemas.chat import ChatRequest
from app.rag.pipeline import ChatPipeline
from app.rag.true_agent import tool_specs
from core.errors import BadRequestError
from tests.unit.test_agent_durable import settings
from tests.unit.test_live_chat import FakeLLM, FakeRetriever


class RecordingLLM(FakeLLM):
    """FakeLLM whose Agent turns are scripted; keeps every message list the Agent saw."""

    def __init__(self, script):
        super().__init__()
        self.agent_script, self.agent_seen = list(script), []

    async def agent_turn(self, messages, tools):
        self.agent_seen.append(list(messages))
        return await super().agent_turn(messages, tools)

    def tool_result(self, turn):
        """The last tool result shown to the Agent at model call `turn` (0-based)."""
        return json.loads([m for m in self.agent_seen[turn] if isinstance(m, ToolMessage)][-1].content)

    def payload(self, turn=0):
        return json.loads(next(m.content for m in self.agent_seen[turn] if isinstance(m, HumanMessage)))


def req(message="Ranni là ai?", **kw):
    return ChatRequest(message=message, channel="web", options={"web_search": "off", **kw.pop("options", {})}, **kw)


def finish(**kw):
    return ("finish", {"request": "Who is Ranni?", "intent": "lore", "answer_language": "en", **kw})


def test_tool_specs_follow_web_policy_and_clarification_budget():
    names = lambda specs: {s["function"]["name"] for s in specs}  # noqa: E731
    assert "search_web" not in names(tool_specs(web=False)) and "search_web" in names(tool_specs(web=True))
    assert "ask_user" not in names(tool_specs(web=False, ask=False))
    assert {"set_conditions", "run_python", "finish", "reply"} <= names(tool_specs(web=False))
    assert "calculator" not in names(tool_specs(web=False))  # 22/11: the Agent computes with run_python.


async def test_the_agent_searches_and_chooses_evidence_for_the_generator():
    llm = RecordingLLM([("search_corpus", {"query": "Ranni identity"}), finish(evidence_ids=["1"])])
    p = await ChatPipeline(settings(), llm, FakeRetriever()).prepare(req(), [])
    assert p.trace["evidence_selection"] == {"method": "model", "ids": ["1"]} and [h.id for h in p.hits] == ["1"]
    assert p.agent_decision == {"action": "retrieve", "intent": "lore", "resolved_question": "Who is Ranni?"}
    assert p.lang == "en" and p.static_answer is None
    assert [s["tool"] for s in p.trace["agent"]["steps"]] == ["search_corpus", "finish"]
    assert p.trace["model_calls"] == [{"phase": "agent"}, {"phase": "agent"}]
    result = await ChatPipeline(settings(), llm, FakeRetriever()).generator.generate(p)
    assert result.grounded


async def test_conditions_need_the_players_words_and_persist_in_working_state():
    llm = RecordingLLM(
        [
            ("set_conditions", {"set": [{"key": "level", "value": "150", "source_id": "current"}]}),
            ("set_conditions", {"set": [{"key": "level", "value": "60", "source_id": "current"}]}),
            finish(),
        ]
    )
    p = await ChatPipeline(settings(), llm, FakeRetriever()).prepare(req("Build Strength level 60 giúp mình"), [])
    assert llm.tool_result(1)["status"] == "error" and llm.tool_result(1)["keys"] == ["level"]
    assert p.player_state["constraints"] == [{"key": "level", "value": "60", "source_id": "current"}]
    # Next turn: the condition is shown again and kept unless the Agent retires or replaces it.
    llm2 = RecordingLLM([("set_conditions", {"retire": ["level"]}), finish()])
    p2 = await ChatPipeline(settings(), llm2, FakeRetriever()).prepare(req("bỏ level đi"), [], player=p.player_state)
    assert llm2.payload()["conditions"] == [{"key": "level", "value": "60", "source_id": "current"}]
    assert p2.player_state["constraints"] == [] and p2.player_state["retired_condition_keys"] == ["level"]


async def test_the_agent_computes_with_python_and_the_writer_gets_its_results():
    code = "plan = {'vigor': 60, 'strength': 80}\nprint(sum(plan.values()))"
    results = "Allocation (assumed level 150): Vigor 60, Strength 80 ... total 229"
    llm = RecordingLLM(
        [
            ("set_conditions", {"set": [{"key": "level", "value": "150", "source_id": "assumption"}]}),
            ("run_python", {"code": code}),
            ("run_python", {"code": "import os"}),
            finish(intent="build", results=results),
        ]
    )
    p = await ChatPipeline(settings(), llm, FakeRetriever()).prepare(req("Cho mình một build Strength"), [])
    assert llm.tool_result(2) == {"status": "ok", "output": "140\n"}
    assert llm.tool_result(3)["status"] == "error" and "not allowed" in llm.tool_result(3)["error"]
    # The Agent's own computed numbers reach the writer as they are; the server does not re-check them.
    assert json.loads(p.values["payload"])["agent_results"] == results
    # The built-in level rule is offered to the Agent but not added to the answer unless chosen.
    assert llm.payload()["built_in_sources"][0]["id"] and all(h.id == "1" for h in p.hits)


async def test_ask_user_creates_a_clarification_and_the_reply_continues_the_request():
    ask = (
        "ask_user",
        {
            "question": "Bạn đang level bao nhiêu?",
            "missing": [{"key": "level", "label": "Level"}],
            "answer_language": "vi",
        },
    )
    llm = RecordingLLM([ask])
    p = await ChatPipeline(settings(), llm, FakeRetriever()).prepare(req("Chia điểm thế nào?"), [])
    assert p.static_answer == "Bạn đang level bao nhiêu?" and p.clarification.fields[0].key == "level"
    assert p.player_state["pending"]["id"] == str(p.clarification.id) and p.agent_decision["action"] == "clarify"
    reply = RecordingLLM(
        [("set_conditions", {"set": [{"key": "level", "value": "90", "source_id": "current"}]}), finish()]
    )
    later = req("level 90", clarification_id=p.clarification.id)
    p2 = await ChatPipeline(settings(), reply, FakeRetriever()).prepare(later, [], player=p.player_state)
    shown = reply.payload()["replying_to"]
    assert shown == {
        "id": str(p.clarification.id),
        "question": "Bạn đang level bao nhiêu?",
        "original_request": "Chia điểm thế nào?",
    }
    assert p2.player_state["request_text"] == "Chia điểm thế nào?" and p2.player_state["clarification_rounds"] == 1
    with pytest.raises(BadRequestError):
        await ChatPipeline(settings(), RecordingLLM([]), FakeRetriever()).prepare(
            req("level 90", clarification_id=UUID(int=1)), [], player=p.player_state
        )


async def test_reply_cancel_clears_the_working_state():
    llm = RecordingLLM([("reply", {"text": "Đã hủy.", "answer_language": "vi", "end_task": True})])
    working = {"constraints": [{"key": "level", "value": "60", "source_id": "current"}], "updated": 9e12}
    p = await ChatPipeline(settings(), llm, FakeRetriever()).prepare(req("thôi hủy"), [], player=working)
    assert p.static_answer == "Đã hủy." and p.player_state["constraints"] == []
    assert p.agent_decision["intent"] == "cancel"


async def test_a_call_with_broken_json_arguments_is_answered_so_the_loop_continues():
    llm = RecordingLLM([("__invalid__", None), finish()])
    p = await ChatPipeline(settings(), llm, FakeRetriever()).prepare(req(), [])
    answered = [m for m in llm.agent_seen[1] if isinstance(m, ToolMessage)]
    assert answered[-1].tool_call_id == "call_1" and "not valid JSON" in answered[-1].content
    assert p.trace["agent"]["steps"][0]["status"] == "invalid_arguments"


async def test_always_web_policy_requires_a_web_search_before_finish():
    from tests.unit.test_web_search import FakeSearch, web_hit

    llm = RecordingLLM([finish(), ("search_web", {"query": "Ranni"}), finish()])
    pipe = ChatPipeline(settings(tavily_api_key="offline-test-key"), llm, FakeRetriever())
    pipe.web_search = FakeSearch(rows=[web_hit()])
    p = await pipe.prepare(req(options={"web_search": "always"}), [])
    assert "search_web" in llm.tool_result(1)["error"] and pipe.web_search.calls
    page = llm.tool_result(2)["pages"][0]  # Web blocks grouped by page, in page order, with short previews.
    assert page["url"] and page["blocks"][0]["id"] and len(page["blocks"][0]["text"]) <= 200
    assert p.trace["web_search"]["status"] == "ok"


async def test_the_agent_sees_recent_turns_and_answers_about_the_conversation():
    history = [
        {"role": "user", "content": "Ranni là ai?", "message_id": "m1"},
        {"role": "assistant", "content": "Ranni là một Empyrean [1].", "message_id": "m2"},
    ]
    reply = {
        "text": "Câu trước bạn hỏi: Ranni là ai?",
        "answer_language": "vi",
        "about_conversation": True,
    }
    llm = RecordingLLM([("reply", reply)])
    pipe = ChatPipeline(settings(), llm, FakeRetriever())
    p = await pipe.prepare(req("Câu hỏi trước của tôi là gì?"), history)
    # Both the player's question and the assistant's answer are shown, oldest first; nothing was searched.
    assert llm.payload()["recent_turns"] == [
        {"role": "user", "text": "Ranni là ai?"},
        {"role": "assistant", "text": "Ranni là một Empyrean [1]."},
    ]
    assert p.static_answer == reply["text"] and p.agent_decision["intent"] == "conversation"
    assert not pipe.retriever.calls and not p.hits


def test_recent_turns_keep_the_newest_within_the_history_budget():
    pipe = ChatPipeline(settings(chat_history_messages=3, chat_history_chars=30), FakeLLM(), FakeRetriever())
    history = [{"role": "user", "content": f"message {i} " + "x" * 5} for i in range(5)]
    turns = pipe._recent_turns(history)
    assert [t["text"][:9] for t in turns] == ["message 3", "message 4"]  # Third-newest is over the char budget.


async def test_an_assumed_level_serves_this_turn_but_is_never_stored_as_a_player_fact():
    llm = RecordingLLM(
        [
            ("set_conditions", {"set": [{"key": "level", "value": "150", "source_id": "assumption"}]}),
            finish(intent="build"),
        ]
    )
    pipe = ChatPipeline(settings(), llm, FakeRetriever())
    p = await pipe.prepare(req("Cho mình một build Strength"), [])
    assert llm.tool_result(1)["status"] == "ok"
    # Used for this answer (calculator, writer), marked as assumed; not kept as a player condition.
    assert json.loads(p.values["payload"])["player_profile"] == {"level": "150", "assumed": "level"}
    assert p.player_state["constraints"] == []
    # An assumption may not replace what the player said.
    llm2 = RecordingLLM(
        [
            ("set_conditions", {"set": [{"key": "level", "value": "60", "source_id": "current"}]}),
            ("set_conditions", {"set": [{"key": "level", "value": "150", "source_id": "assumption"}]}),
            finish(intent="build"),
        ]
    )
    p2 = await ChatPipeline(settings(), llm2, FakeRetriever()).prepare(req("Build Strength level 60"), [])
    assert llm2.tool_result(2)["status"] == "error" and p2.player_state["constraints"][0]["value"] == "60"


async def test_finish_without_evidence_is_reminded_once_and_never_filled_in_by_the_server():
    llm = RecordingLLM([("search_corpus", {"query": "Ranni"}), finish(), finish()])
    p = await ChatPipeline(settings(), llm, FakeRetriever()).prepare(req(), [])
    assert "evidence_ids is empty" in llm.tool_result(2)["error"]
    # The Agent finished again without choosing: no evidence, the writer says what is missing.
    assert p.trace["evidence_selection"] == {"method": "model", "ids": []} and p.hits == []
    assert p.static_answer is None


async def test_discord_uses_the_same_web_default_as_other_channels():
    discord = ChatRequest(message="Ranni là ai?", channel="discord", external_ref="discord:channel:1")
    llm = RecordingLLM([finish()])
    p = await ChatPipeline(settings(web_search_mode="off"), llm, FakeRetriever()).prepare(discord, [])
    assert p.trace["web_search"]["requested"] == "off"


def test_gameplay_advice_may_carry_a_recommendation_but_never_a_citation_or_url():
    from app.rag.generator import Prepared, RAGValidationError, validate_answer

    advice = Prepared("rag", "vi", [], gameplay_advice=True)
    data = {"answer": "Ưu tiên Vigor trước.", "evidence": [], "insufficient": False, "advisory": True}
    result = validate_answer(advice, {**data, "recommendation": "Sau đó tăng chỉ số chính."})
    assert result.answer == "Ưu tiên Vigor trước.\n\nSau đó tăng chỉ số chính." and not result.grounded
    for bad in ("Xem https://example.com", "Theo nguồn [1]"):
        with pytest.raises(RAGValidationError):
            validate_answer(advice, {**data, "recommendation": bad})
    with pytest.raises(RAGValidationError):  # The flag is the Agent's decision.
        validate_answer(Prepared("rag", "vi", []), data)
