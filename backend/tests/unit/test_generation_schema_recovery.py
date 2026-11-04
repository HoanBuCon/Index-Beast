"""Provider schema failures: bounded regeneration without weakening evidence validation."""

import json
from contextlib import aclosing

import pytest

from app.api.schemas.chat import ChatRequest
from app.rag.prompts import prompt
from core.errors import UpstreamError
from tests.unit.test_live_chat import BODY, FakeLLM, FakeRetriever, SequenceLLM, service


@pytest.mark.parametrize(
    "invalid",
    [
        {"answer": "Missing fields"},
        {"answer": "Ranni [1].", "evidence": [], "insufficient": "false"},
        {"answer": "Ranni [1].", "evidence": [{"index": "1", "quote_id": "q0"}], "insufficient": False},
        {"answer": "", "evidence": [], "insufficient": True},
    ],
)
async def test_schema_regeneration_keeps_context_and_validates_fresh_answer(invalid):
    valid = FakeLLM().data
    llm = SequenceLLM([json.dumps(invalid), json.dumps(valid)])
    live = service("rag", llm, FakeRetriever())
    result = await live.answer(ChatRequest(**BODY))
    assert llm.attempts == 2 and result.grounded and result.answer == valid["answer"]
    assert llm.seen[0]["payload"] == llm.seen[1]["payload"]
    assert live.traces[result.message_id]["generation_retry_reason"] == "schema_invalid"


@pytest.mark.parametrize("retries,attempts", [(0, 1), (1, 2)])
async def test_repeated_schema_failure_still_fails_and_is_not_saved(retries, attempts, caplog):
    llm = SequenceLLM([json.dumps({"answer": "private invalid answer"})])
    live = service("rag", llm, FakeRetriever(), rag_format_retries=retries)
    with pytest.raises(UpstreamError):
        await live.answer(ChatRequest(**BODY))
    assert llm.attempts == attempts and not live.traces
    assert all(not state.conversation.messages for state in live._conversations.values())
    assert "private invalid answer" not in caplog.text
    assert any(r.msg == "Generation failed" and r.data["reason"] == "schema_invalid" for r in caplog.records)


async def test_schema_recovery_cannot_accept_fabricated_quote():
    bad_quote = {
        "answer": "Ranni [1].",
        "evidence": [{"index": 1, "quote": "Invented source quote"}],
        "insufficient": False,
    }
    llm = SequenceLLM([json.dumps({"answer": "Missing schema"}), json.dumps(bad_quote)])
    live = service("rag", llm, FakeRetriever())
    with pytest.raises(UpstreamError):
        await live.answer(ChatRequest(**BODY))
    assert llm.attempts == 2 and not live.traces


async def test_stream_can_recover_schema_only_before_visible_tokens():
    class Recovering(FakeLLM):
        attempts = 0
        closed_attempts = 0

        async def stream(self, messages, **kwargs):
            self.attempts += 1
            raw = json.dumps({"answer": "Incomplete schema"} if self.attempts == 1 else self.data)
            try:
                for char in raw:
                    yield char
            finally:
                self.closed_attempts += 1

    llm = Recovering()
    live = service("rag", llm, FakeRetriever())
    async with aclosing(await live.open_stream(ChatRequest(**BODY))) as events:
        frames = [frame async for frame in events]
    assert llm.attempts == llm.closed_attempts == 2
    assert frames[-1][0] == "done"
    assert "".join(p.token for n, p in frames if n == "token") == llm.data["answer"]


def test_direct_style_keeps_evidence_contract():
    policy = prompt("answer")
    assert "Do not narrate searching" in policy
    assert "Keep the required [n] citations" in policy
    assert "Use only the numbered evidence" in policy
    assert "I can't confirm that relationship" in policy


async def test_empty_context_is_normal_response_without_retrieval_narration():
    llm = FakeLLM()
    result = await service("rag", llm, FakeRetriever([])).answer(ChatRequest(**BODY))
    assert not result.grounded and not result.sources and llm.calls == 0
    assert "nguồn" not in result.answer and "tìm được" not in result.answer


@pytest.mark.parametrize("streaming", [False, True])
async def test_katana_question_with_unrelated_context_is_insufficient_not_502(streaming):
    llm = FakeLLM()
    llm.data = {
        "answer": "Bạn muốn chơi katana nào và thiên về PvE hay PvP?",
        "evidence": [],
        "insufficient": True,
    }
    llm.tokens = list(json.dumps(llm.data))
    # Ranni context intentionally does not establish a katana build.
    live = service("rag", llm, FakeRetriever())
    request = ChatRequest(message="huong dan build katana", channel="web")
    if streaming:
        async with aclosing(await live.open_stream(request)) as events:
            frames = [frame async for frame in events]
        assert frames[-1][0] == "done" and not frames[-1][1].grounded
        assert "".join(p.token for n, p in frames if n == "token") == llm.data["answer"]
    else:
        result = await live.answer(request)
        assert not result.grounded and not result.sources and result.answer == llm.data["answer"]
