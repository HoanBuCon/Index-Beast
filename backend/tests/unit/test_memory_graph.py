"""Offline behavioral regressions; no real model/server or semantic-quality claims."""

import asyncio
import json
from contextlib import aclosing
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.api.schemas.chat import ChatRequest
from app.api.schemas.conversation import MessageOut
from app.rag.history import dependent, select_history
from app.rag.pipeline import ChatPipeline
from app.rag.prompts import prompt
from app.rag.rewrite import rewrite_problem
from app.services.chat import LiveChatService
from app.services.gameplay import PlayerState, advance
from core.config import Settings
from core.errors import NotFoundError, TimeoutAppError, UpstreamError
from tests.unit.test_live_chat import BODY, FakeLLM, FakeRetriever, SequenceLLM
from tests.unit.test_vi_en import RankedRetriever, ScriptedLLM, rewritten
from tests.unit.test_web_search import CoverageLLM, FakeSearch


def request(text, **kwargs):
    return ChatRequest(message=text, channel="web", **kwargs)


def user(text, **metadata):
    return {"role": "user", "content": text, **metadata}


def recall(text, rows, **kwargs):
    return select_history(text, rows, max_messages=kwargs.get("messages", 8), max_chars=kwargs.get("chars", 8000))


@pytest.mark.parametrize("question", ["Ranni là ai?", "Where is Moonveil?", "How does Marika relate to her children?"])
def test_standalone_requests_ignore_old_user_and_assistant_claims(question):
    selected = recall(question, [user("Gia phả Marika"), {"role": "assistant", "content": "Invented fact"}])
    assert selected.rows == [] and not selected.ambiguous


@pytest.mark.parametrize(
    "question",
    [
        "nói tiếp về gia phả",
        "tell me more about the family tree",
        "giải thích thêm về gia phả",
    ],
)
def test_topic_search_finds_older_user_turn_before_input_budget(question):
    # Same-language lexical search is intentional; this test supplies both VI/EN labels in the user's topic.
    rows = [user("Gia phả Marika / Marika family tree", message_id="topic", created_at="2026-11-06")]
    rows += [user("Ranni là ai?"), {"role": "assistant", "content": "assistant claims"}] * 10
    selection = recall(question, rows, messages=1)
    assert selection.rows == [{"role": "user", "content": rows[0]["content"]}]
    assert selection.provenance == [{"message_id": "topic", "created_at": "2026-11-06"}]


def test_competing_topics_and_comparison_require_clarification():
    rows = [user("Gia phả Marika"), user("Gia phả Radagon")]
    assert recall("nói tiếp về gia phả", rows).ambiguous
    assert recall("Where can I find it?", [user("Compare Moonveil and Uchigatana")]).ambiguous


def test_latest_referent_not_old_equipment_and_compound_name_is_one_subject():
    selected = recall("Lấy nó ở đâu?", [user("Tôi dùng Moonveil"), user("Ranni là ai?")])
    assert selected.rows == [user("Ranni là ai?")]
    selected = recall("Lấy nó ở đâu?", [user("Tôi muốn tìm Bloodhound's Fang")])
    assert selected.rows == [user("Tôi muốn tìm Bloodhound's Fang")]
    # Shared generic wording is not a reason to jump away from the nearest referent.
    selected = recall("What happened to her?", [user("What happened to Ranni?"), user("Marika là ai?")])
    assert selected.rows == [user("Marika là ai?")]


def test_dedup_correction_provenance_budgets_and_reset():
    rows = [user("Moonveil build level 100 Samurai PvE"), user("level 110"), user("level 110"), user("level 120")]
    selected = recall("PvP", rows)
    assert selected.rows == [rows[0], rows[-2], rows[-1]]
    assert len(recall("PvP", rows, messages=1).rows) == 1
    assert recall("PvP", rows, chars=4).ambiguous
    assert recall("PvP", rows, messages=0).ambiguous
    assert recall("continue", [user("Marika family tree"), user("new topic")]).ambiguous
    assert recall("new topic: Ranni", rows).rows == []


def test_scan_window_is_bounded_and_assistant_cannot_create_subject():
    assert recall("nói tiếp về gia phả", [user("Gia phả Marika")] + [user("hello")] * 65).ambiguous
    assert recall("Who is she?", [{"role": "assistant", "content": "Ranni is a witch."}]).ambiguous
    assert dependent("It requires how much Intelligence?")


@pytest.mark.parametrize("lang,query", [("vi", "Marika family tree"), ("en", "Marika family tree")])
async def test_memory_only_reaches_rewrite_not_evidence_assessor_or_rag_generator(lang, query):
    llm = ScriptedLLM(rewritten(query, entities=["Marika"]))
    pipe = ChatPipeline(Settings(_env_file=None, chat_mode="rag"), llm, FakeRetriever())
    rows = [user("Gia phả Marika"), {"role": "assistant", "content": "Invented child is Alice."}]
    prepared = await pipe.prepare(request("nói tiếp về gia phả", options={"lang": lang}), rows)
    assert llm.inputs[0]["history"] == [rows[0]]
    assert prepared.values["history"] == [] and "Alice" not in str(prepared.messages)
    assert json.loads(prepared.values["payload"])["question"] == query
    assert prepared.lang == lang and len(prepared.hits) == 1
    assert prepared.trace["graph_nodes"] == [
        "scope",
        "gameplay",
        "memory",
        "rewrite",
        "retrieve",
        "rerank",
        "assess",
        "context",
        "prompt",
    ]


async def test_missing_subject_clarifies_without_model_search_or_retriever():
    llm, retriever, search = ScriptedLLM(), RankedRetriever(), FakeSearch()
    pipe = ChatPipeline(
        Settings(_env_file=None, chat_mode="rag", tavily_api_key="offline", web_search_mode="always"),
        llm,
        retriever,
        web_search=search,
    )
    p = await pipe.prepare(request("nói tiếp về gia phả"), [])
    assert p.static_answer and not llm.inputs and not retriever.calls and not search.calls


async def test_clarification_does_not_require_disabled_web_even_when_client_requested_always():
    llm, retriever = FakeLLM(), FakeRetriever()
    service = LiveChatService(
        ChatPipeline(
            Settings(_env_file=None, chat_mode="rag", web_search_enabled=False),
            llm,
            retriever,
        ),
        gameplay_enabled=True,
    )
    result = await service.answer(request("Chia chỉ số Moonveil", options={"web_search": "always"}))
    assert result.clarification and not llm.calls and not retriever.calls


def test_graph_compilation_creates_no_model_or_network_client(monkeypatch):
    import httpx

    from core.encoders.onnx import FastEmbedEncoder

    llm = FakeLLM()

    def forbidden(*args, **kwargs):
        raise AssertionError("Graph construction must not instantiate clients or encoders")

    monkeypatch.setattr(httpx.AsyncClient, "__init__", forbidden)
    monkeypatch.setattr(FastEmbedEncoder, "__init__", forbidden)
    pipe = ChatPipeline(Settings(_env_file=None, chat_mode="rag"), llm, FakeRetriever())
    assert pipe.prepare_graph and pipe.generator.graph


async def test_rewrite_failure_with_valid_memory_does_not_search_dangling_question():
    llm, retriever = ScriptedLLM("broken"), RankedRetriever()
    pipe = ChatPipeline(Settings(_env_file=None, chat_mode="rag"), llm, retriever)
    p = await pipe.prepare(request("nói tiếp về gia phả"), [user("Gia phả Marika")])
    assert p.static_answer and p.trace["rewrite_fallback"] and not retriever.calls


async def test_lowercase_family_subject_and_rewrite_without_resolved_entity_are_safe():
    selected = recall("nói tiếp về gia phả", [user("gia phả marika")])
    assert selected.rows == [user("gia phả marika")] and not selected.ambiguous
    llm, retriever = ScriptedLLM(rewritten("Marika family tree", entities=["Marika"])), RankedRetriever()
    pipe = ChatPipeline(Settings(_env_file=None, chat_mode="rag"), llm, retriever)
    await pipe.prepare(request("nói tiếp về gia phả"), selected.rows)
    assert retriever.calls == ["Marika family tree"]
    llm.output = rewritten("Where is it?", entities=[])
    retriever.calls.clear()
    result = await pipe.prepare(request("Lấy nó ở đâu?"), [user("gia phả marika")])
    assert result.static_answer and not retriever.calls


def test_corrections_cannot_reintroduce_old_level_goal_or_assistant_entity():
    rows = [user("Moonveil build level 100 PvE")]
    assert (
        rewrite_problem("level 120", "Moonveil build level 120 and level 100", ["Moonveil"], rows)
        == "superseded_constraint"
    )
    assert rewrite_problem("PvP", "Moonveil build for PvP and PvE", ["Moonveil"], rows) == "superseded_constraint"
    assert rewrite_problem("PvP", "Moonveil build for PvP", ["Moonveil"], rows) is None
    assert (
        rewrite_problem("Who is she?", "Who is Ranni?", ["Ranni"], [{"role": "assistant", "content": "Ranni"}])
        == "unverified_entity"
    )


@pytest.mark.parametrize(
    "mode,status,expected_web",
    [
        ("off", "insufficient", False),
        ("auto", "sufficient", False),
        ("auto", "insufficient", True),
        ("always", "sufficient", True),
    ],
)
async def test_graph_policy_branches_and_assessor_never_receives_memory(mode, status, expected_web):
    llm, search = CoverageLLM(status), FakeSearch()
    pipe = ChatPipeline(
        Settings(_env_file=None, chat_mode="rag", tavily_api_key="offline", web_search_mode=mode),
        llm,
        FakeRetriever(),
        web_search=search,
    )
    p = await pipe.prepare(request("Ranni là ai?"), [user("Moonveil build")])
    assert bool(search.calls) is expected_web
    assert ("web" in p.trace["graph_nodes"]) is expected_web
    assert all(inputs["history"] == [] for inputs in llm.inputs)
    assert len(p.hits) <= 5


async def test_service_searches_before_budget_and_never_reads_other_conversation():
    llm = ScriptedLLM(rewritten("Marika family tree", entities=["Marika"]))
    service = LiveChatService(
        ChatPipeline(Settings(_env_file=None, chat_mode="rag", chat_history_messages=1), llm, FakeRetriever([]))
    )
    a, b = service._state(request("first")), service._state(request("other"))
    a.conversation.messages = [
        MessageOut(id=uuid4(), role="user", content=text, created_at=datetime.now(UTC))
        for text in ["Gia phả Marika", *["Ranni là ai?"] * 10]
    ]
    p, _ = await service._prepare(request("nói tiếp về gia phả", conversation_id=a.conversation.id), a)
    assert p.trace["memory"]["selected"] == 1 and llm.inputs[0]["history"] == [user("Gia phả Marika")]
    assert p.trace["memory"]["provenance"][0]["conversation_id"] == str(a.conversation.id)
    p, _ = await service._prepare(request("nói tiếp về gia phả", conversation_id=b.conversation.id), b)
    assert p.static_answer and p.trace["memory"]["selected"] == 0
    with pytest.raises(NotFoundError):
        service._state(ChatRequest(message="x", channel="discord", conversation_id=a.conversation.id))


def test_new_gameplay_task_does_not_inherit_old_weapon_or_location():
    prior = advance(PlayerState(), request("Chia chỉ số Moonveil level 100 Samurai PvE"), "vi", now=100)
    route = advance(prior.state, request("Tôi nên đi đâu tiếp?"), "vi", now=101)
    assert route.clarification and route.state.slots == {}
    assert "Moonveil" not in route.query
    topic = advance(route.state, request("Gia phả Marika"), "vi", now=102)
    assert not topic.clarification and topic.state.slots == {} and topic.query == "Gia phả Marika"


def test_completed_build_can_be_corrected_without_carrying_old_values():
    prior = advance(PlayerState(), request("Chia chỉ số Moonveil level 100 Samurai PvE"), "vi", now=100)
    level = advance(prior.state, request("level 120"), "vi", now=101)
    goal = advance(level.state, request("PvP"), "vi", now=102)
    assert goal.status == "resumed" and not goal.clarification
    assert goal.state.slots["level"] == "120" and goal.state.slots["goal"] == "PvP"
    assert "100" not in goal.query and "PvE" not in goal.query
    assert "120" in goal.query and "PvP" in goal.query and "Moonveil" in goal.query


async def test_json_graph_retry_does_not_repeat_retrieval_and_commits_one_pair():
    llm, retriever = SequenceLLM(["broken", json.dumps(FakeLLM().data)]), FakeRetriever()
    service = LiveChatService(ChatPipeline(Settings(_env_file=None, chat_mode="rag"), llm, retriever))
    result = await service.answer(ChatRequest(**BODY))
    assert llm.attempts == 2 and len(retriever.calls) == 1
    assert len(service.history(result.conversation_id).messages) == 2
    assert service.traces[result.message_id]["generation_graph_nodes"] == [
        "generate",
        "validate",
        "repair",
        "generate",
        "validate",
        "finish",
    ]


async def test_invalid_after_visible_stream_does_not_retry_save_or_send_done():
    llm = FakeLLM(tokens=['{"answer":"Ranni [1]. ', "Unfinished"])
    service = LiveChatService(ChatPipeline(Settings(_env_file=None, chat_mode="rag"), llm, FakeRetriever()))
    events = await service.open_stream(ChatRequest(**BODY))
    frames = []
    with pytest.raises(UpstreamError):
        async with aclosing(events):
            async for frame in events:
                frames.append(frame)
    assert not any(name == "done" for name, _ in frames)
    assert not service.traces and llm.closed
    assert all(not state.conversation.messages and not state.lock.locked() for state in service._conversations.values())


async def test_graph_invocations_do_not_share_state_or_checkpoint():
    pipe = ChatPipeline(Settings(_env_file=None, chat_mode="rag"), FakeLLM(), FakeRetriever([]))
    a, b = await asyncio.gather(pipe.prepare(request("Ranni là ai?"), []), pipe.prepare(request("Moonveil là gì?"), []))
    assert a.trace is not b.trace and a.values is not b.values
    assert pipe.prepare_graph.checkpointer is None and pipe.generator.graph.checkpointer is None
    assert "Ranni" in a.values["payload"] and "Moonveil" in b.values["payload"]


async def test_stream_lock_wait_is_bounded_without_releasing_another_turns_lock():
    service = LiveChatService(
        ChatPipeline(
            Settings(_env_file=None, chat_mode="llm_only", chat_timeout_seconds=0.02),
            FakeLLM(),
        )
    )
    state = service._state(request("first"))
    await state.lock.acquire()
    try:
        with pytest.raises(TimeoutAppError):
            await service.open_stream(request("Ranni là ai?", conversation_id=state.conversation.id))
        assert state.lock.locked() and not state.conversation.messages
    finally:
        state.lock.release()


async def test_midstream_deadline_closes_provider_and_no_success_done():
    class Slow(FakeLLM):
        async def stream(self, messages, **kwargs):
            try:
                yield "First clause. "
                await asyncio.Event().wait()
            finally:
                self.closed = True

    llm = Slow()
    service = LiveChatService(
        ChatPipeline(
            Settings(_env_file=None, chat_mode="llm_only", chat_timeout_seconds=0.05),
            llm,
        )
    )
    frames = []
    async with aclosing(await service.open_stream(request("Who is Ranni?"))) as events:
        with pytest.raises(TimeoutAppError):
            async for frame in events:
                frames.append(frame)
    assert llm.closed and not service.traces and not any(name == "done" for name, _ in frames)
    assert all(not state.lock.locked() for state in service._conversations.values())


def test_prompt_direct_voice_preserves_truth_and_citation_rules():
    persona, answer = prompt("persona"), prompt("answer")
    assert 'Do not add "perhaps"' in persona and "own judgment" in persona
    assert "Omit limitation when the requested answer is supported" in answer
    assert "Do not fill gaps with your own knowledge" in answer
    assert "MUST equal the set of evidence.index" in answer
