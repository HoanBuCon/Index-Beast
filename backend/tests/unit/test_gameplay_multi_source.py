import json

import httpx
import pytest

from scripts.benchmark_agent import main
from scripts.diagnose_agent_memory import continuation_case, run_case


async def test_auto_can_give_general_advice_when_web_is_unavailable():
    from app.adapters.tavily import WebSearchError
    from app.rag.pipeline import ChatPipeline
    from tests.unit.test_agent_durable import settings
    from tests.unit.test_live_chat import FakeRetriever
    from tests.unit.test_true_agent import RecordingLLM, req
    from tests.unit.test_web_search import FakeSearch

    query = "Elden Ring general dodge and block practice"
    llm = RecordingLLM(
        [
            ("search_corpus", {"query": query}),
            ("search_web", {"query": query}),
            ("finish", {"request": query, "intent": "mechanics", "answer_language": "vi", "gameplay_advice": True}),
        ]
    )
    llm.data = {
        "answer": "Tập né từng đòn trước khi ghép đòn phản công.",
        "evidence": [],
        "insufficient": False,
        "advisory": True,
    }
    pipe = ChatPipeline(settings(tavily_api_key="test-key"), llm, FakeRetriever([]))
    pipe.web_search = FakeSearch(error=WebSearchError("network"))
    p = await pipe.prepare(req("Tập né hay đỡ đòn thế nào?", options={"web_search": "auto"}), [])
    # Tìm web lỗi là một quan sát cho Agent, và Agent vẫn chọn lời khuyên chung.
    assert llm.tool_result(2)["status"] == "error" and p.trace["web_search"]["status"] == "error"
    answer = await pipe.generator.generate(p)
    assert p.trace["answer_basis"] == "gameplay_advice"
    assert answer.answer == llm.data["answer"] and not answer.grounded and not answer.sources


def test_case_budget_keeps_all_clarification_answers(tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    main_case = {"id": "main", "question": "Where next?", "lang": "en", "clarification_answers": ["A", "B"]}
    manifest.write_text(json.dumps([main_case, {**main_case, "id": "other"}]), encoding="utf-8")
    main(["--manifest", str(manifest), "--max-cases", "1"])
    plan = json.loads(capsys.readouterr().out)
    assert plan["cases"] == 1
    assert plan["manifest"]["cases"][0]["clarification_answers"] == ["A", "B"]


@pytest.mark.parametrize("http_status", [502, 200])
def test_continue_case_retries_failed_clarification_in_the_same_conversation(http_status):
    case = {"question": "Original question", "clarification_answers": ["First detail", "Second detail"]}
    row = {
        "http_turns": [
            {"http_status": 200, "response": {"clarification": {"id": "pending"}}},
            {"http_status": http_status, "message": "First detail"},
        ]
    }
    group = {"conversation_id": "conversation", "conversation_token": "token"}
    continued, credentials = continuation_case(case, row, group)
    assert continued == {"question": "First detail", "clarification_answers": ["Second detail"]}
    assert credentials == {**group, "clarification_id": "pending"}
    assert continuation_case(case, row, {}) == (case, {})
    assert row["restart_offset"] == 2


@pytest.mark.parametrize("endpoint", ["chat", "chat/stream"])
@pytest.mark.parametrize("has_answers", [True, False])
async def test_case_reuses_conversation_and_clarification_through_final_answer(tmp_path, endpoint, has_answers):
    questions = ["Principal request", "First detail", "Second detail"]
    bodies = []

    def reply(request):
        body = json.loads(request.content)
        i = len(bodies)
        bodies.append(body)
        assert body["message"] == questions[i]
        if i:
            assert body["conversation_id"] == "conversation"
            assert body["conversation_token"] == "test-token"
            assert body["clarification_id"] == f"pending-{i}"
        data = {"conversation_id": "conversation", "conversation_token": "test-token"}
        clarification = {"id": f"pending-{i + 1}"} if i < 2 else None
        answer = "Clarify" if clarification else "Final answer"
        if endpoint == "chat":
            return httpx.Response(200, json={**data, "answer": answer, "clarification": clarification})
        frames = [("token", {"token": answer}), ("sources", {"clarification": clarification}), ("done", data)]
        return httpx.Response(200, text="".join(f"event: {event}\ndata: {json.dumps(d)}\n\n" for event, d in frames))

    case = {
        "id": "main",
        "question": questions[0],
        "lang": "en",
        "group": None,
        "endpoint": endpoint,
        "clarification_answers": questions[1:] if has_answers else [],
    }
    row, checkpoints = {}, []
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply), base_url="http://test") as client:
        data = await run_case(
            client,
            case,
            {},
            row,
            {},
            tmp_path / "state.json",
            case_budget=True,
            checkpoint=lambda: checkpoints.append(len(bodies)),
        )
    if has_answers:
        assert row["status"] == "ok" and data["answer"] == "Final answer"
        assert len(row["http_turns"]) == 3 and checkpoints == [1, 2]
        assert len({b["turn_id"] for b in bodies}) == 3
    else:
        assert row["status"] == "incomplete" and data is None and len(bodies) == 1
    assert "test-token" not in json.dumps(row)
