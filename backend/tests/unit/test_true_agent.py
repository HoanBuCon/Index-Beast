"""Vòng lặp Agent chuẩn bị mọi lượt RAG: tool và guard thật, model tool calling soạn sẵn."""

import json
from uuid import UUID

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from app.api.schemas.chat import ChatRequest
from app.rag.pipeline import ChatPipeline
from app.rag.true_agent import tool_specs
from core.errors import BadRequestError
from tests.unit.test_agent_durable import settings
from tests.unit.test_live_chat import FakeLLM, FakeRetriever, hit


class RecordingLLM(FakeLLM):
    """FakeLLM có các lượt Agent soạn sẵn; giữ mọi danh sách message Agent đã thấy."""

    def __init__(self, script):
        super().__init__()
        self.agent_script, self.agent_seen, self.offered = list(script), [], []

    async def agent_turn(self, messages, tools):
        self.agent_seen.append(list(messages))
        self.offered.append({t["function"]["name"] for t in tools})
        return await super().agent_turn(messages, tools)

    def tool_result(self, turn):
        """Kết quả tool cuối cùng hiển thị cho Agent ở lượt gọi model `turn` (tính từ 0)."""
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
    assert "calculator" not in names(tool_specs(web=False))  # 22/11: Agent tính bằng run_python.


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
    assert "word for word" in llm.tool_result(1)["error"] and "assumption" not in llm.tool_result(1)["error"]
    assert p.player_state["constraints"] == [{"key": "level", "value": "60", "source_id": "current"}]
    # Lượt sau: điều kiện được hiện lại và giữ nguyên trừ khi Agent bỏ hoặc thay nó.
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
    # Các số Agent tự tính tới bước viết nguyên như vậy; server không kiểm lại.
    assert json.loads(p.values["payload"])["agent_results"] == results
    # Quy tắc level dựng sẵn được đưa cho Agent nhưng không thêm vào câu trả lời trừ khi được chọn.
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


async def test_check_name_returns_the_titles_found_and_leaves_the_choice_to_the_agent():
    # 24/11: không còn heuristic chính tả phía server; tiêu đề nào tìm được cũng tới Agent, theo thứ tự retrieval.
    found = [hit(1, title="Ranni the Witch"), hit(2, title="Rennala"), hit(3, title="Ranni the Witch"), hit(4)]
    llm = RecordingLLM([("check_name", {"name": "Rani"}), finish(evidence_ids=["1"])])
    await ChatPipeline(settings(), llm, FakeRetriever(found)).prepare(req("Rani là ai?"), [])
    result = llm.tool_result(1)
    assert result["candidates"] == ["Ranni the Witch", "Rennala", "Ranni"]
    assert "single_close_match" not in result and [r["id"] for r in result["results"]] == ["1", "2", "3", "4"]


@pytest.mark.parametrize("tool", ["reply", "ask_user"])
async def test_texts_shown_directly_never_name_internal_fields(tool):
    text = "Mình chưa có `player_profile` của bạn, cho mình biết level nhé."
    args = (
        {"text": text, "answer_language": "vi"}
        if tool == "reply"
        else {"question": text, "missing": [{"key": "level", "label": "Level"}], "answer_language": "vi"}
    )
    p = await ChatPipeline(settings(), RecordingLLM([(tool, args)]), FakeRetriever()).prepare(req("chia điểm"), [])
    assert "player_profile" not in p.static_answer and "thông tin bạn đưa ra" in p.static_answer
    assert p.trace["internal_field_replaced"] == ["player_profile"]
    if tool == "ask_user":
        assert p.clarification.question == p.static_answer


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
    page = llm.tool_result(2)["pages"][0]  # Khối web nhóm theo trang, theo thứ tự trang, kèm bản xem trước ngắn.
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
    # Cả câu hỏi của người chơi lẫn câu trả lời của trợ lý đều hiện ra, cũ nhất trước; không tìm kiếm gì.
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
    assert [t["text"][:9] for t in turns] == ["message 3", "message 4"]  # Lượt mới thứ ba vượt ngân sách ký tự.


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
    # Dùng cho câu trả lời này (calculator, bước viết), đánh dấu là giả định; không giữ làm điều kiện của người chơi.
    assert json.loads(p.values["payload"])["player_profile"] == {"level": "150", "assumed": "level"}
    assert p.player_state["constraints"] == []
    # Giả định không được thay lời người chơi đã nói.
    llm2 = RecordingLLM(
        [
            ("set_conditions", {"set": [{"key": "level", "value": "60", "source_id": "current"}]}),
            ("set_conditions", {"set": [{"key": "level", "value": "150", "source_id": "assumption"}]}),
            finish(intent="build"),
        ]
    )
    p2 = await ChatPipeline(settings(), llm2, FakeRetriever()).prepare(req("Build Strength level 60"), [])
    assert llm2.tool_result(2)["status"] == "error" and p2.player_state["constraints"][0]["value"] == "60"
    assert "cannot replace" in llm2.tool_result(2)["error"] and "word for word" not in llm2.tool_result(2)["error"]


async def test_finish_without_evidence_is_reminded_once_and_never_filled_in_by_the_server():
    llm = RecordingLLM([("search_corpus", {"query": "Ranni"}), finish(), finish()])
    p = await ChatPipeline(settings(), llm, FakeRetriever()).prepare(req(), [])
    assert "evidence_ids is empty" in llm.tool_result(2)["error"]
    # Agent lại finish mà không chọn gì: không có evidence, bước viết nói rõ còn thiếu gì.
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
    with pytest.raises(RAGValidationError):  # Cờ này là quyết định của Agent.
        validate_answer(Prepared("rag", "vi", []), data)


async def test_budget_counts_model_calls_not_tools():
    # 23/11: bốn tool trong một lượt không còn ăn vào ngân sách lượt gọi model (trước đây trần 12 bước cắt sớm).
    searches = [("search_corpus", {"query": f"q{i}"}) for i in range(4)]
    llm = RecordingLLM([("__multi__", searches), finish(evidence_ids="seen")])
    p = await ChatPipeline(settings(chat_agent_max_calls=3), llm, FakeRetriever()).prepare(req(), [])
    agent = p.trace["agent"]
    assert agent["status"] == "ok" and agent["model_calls"] == 2 and len(agent["steps"]) == 5
    assert "forced_finish" not in agent and p.hits


async def test_the_last_call_only_allows_finish_so_found_evidence_is_kept():
    llm = RecordingLLM([("search_corpus", {"query": "Ranni"}), ("search_corpus", {"query": "Ranni quest"})] * 3)
    p = await ChatPipeline(settings(chat_agent_max_calls=3), llm, FakeRetriever()).prepare(req(), [])
    agent = p.trace["agent"]
    assert agent["model_calls"] == 3 and agent["forced_finish"] and p.trace["tool_stop"] == "finish"
    # Agent biết ngân sách từ đầu, được nhắc khi gần hết, và lượt cuối chỉ có finish.
    assert llm.payload()["model_calls"] == 3
    assert any("model calls left" in m.content for m in llm.agent_seen[1] if isinstance(m, HumanMessage))
    assert llm.offered[-1] == {"finish"} and "search_corpus" in llm.offered[0]
    assert p.hits  # Evidence Agent đã tìm vẫn tới bước viết, do chính Agent chọn ở lượt finish.


async def test_the_agent_decides_when_the_writer_needs_reasoning():
    llm = RecordingLLM([finish(intent="comparison", needs_reasoning=True)])
    p = await ChatPipeline(settings(), llm, FakeRetriever()).prepare(req(), [])
    assert p.reasoning and p.trace["agent"]["needs_reasoning"] is True
    llm = RecordingLLM([finish()])
    p = await ChatPipeline(settings(), llm, FakeRetriever()).prepare(req(), [])
    assert not p.reasoning and p.trace["agent"]["needs_reasoning"] is False


@pytest.mark.parametrize("thinking", [False, True])
async def test_agent_thinking_is_an_opt_in_and_the_forced_finish_never_thinks(thinking, monkeypatch):
    from tests.unit.test_live_chat import FakeChatModel

    bound = []
    original = FakeChatModel.bind_tools

    def spy(self, tools, **kwargs):
        bound.append(kwargs)
        return original(self, tools, **kwargs)

    monkeypatch.setattr(FakeChatModel, "bind_tools", spy)
    llm = RecordingLLM([("search_corpus", {"query": "Ranni"})] * 3)
    p = await ChatPipeline(
        settings(chat_agent_max_calls=2, chat_agent_thinking=thinking), llm, FakeRetriever()
    ).prepare(req(), [])
    assert p.trace["agent"]["thinking"] is thinking and p.trace["agent"]["forced_finish"]
    loop, final = bound[0], bound[-1]
    assert loop["extra_body"]["thinking"]["type"] == ("enabled" if thinking else "disabled")
    # DeepSeek bỏ qua temperature khi thinking; không gửi để khỏi hiểu nhầm.
    assert ("temperature" in loop) is not thinking
    assert final["tool_choice"] == "finish" and final["extra_body"]["thinking"]["type"] == "disabled"
