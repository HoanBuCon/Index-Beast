"""Offline tests for the True Agent spike: a scripted tool-calling model, the real tools and guards."""

import json

from langchain_core.messages import AIMessage, ToolMessage

from app.api.schemas.chat import ChatRequest
from app.rag.pipeline import ChatPipeline
from app.rag.true_agent import run_true_agent, tool_specs
from tests.unit.test_agent_durable import settings
from tests.unit.test_live_chat import FakeLLM, FakeRetriever


class ScriptedToolModel:
    """Returns one scripted AIMessage per call; records what the Agent saw."""

    def __init__(self, steps):
        self.steps, self.seen, self.bound = list(steps), [], None

    def bind_tools(self, tools, **kwargs):
        self.bound = {"tools": [t["function"]["name"] for t in tools], **kwargs}
        return self

    async def ainvoke(self, messages):
        self.seen.append(list(messages))
        name, args = self.steps.pop(0)
        if name == "__invalid__":
            bad = {"name": "calculator", "args": "{broken", "id": f"call_{len(self.seen)}", "error": "bad json"}
            return AIMessage(content="", invalid_tool_calls=[bad])
        return AIMessage(
            content="",
            tool_calls=[{"name": name, "args": args, "id": f"call_{len(self.seen)}"}],
            usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
        )

    def last_tool_result(self):
        return json.loads(next(m for m in reversed(self.seen[-1]) if isinstance(m, ToolMessage)).content)


def req(message="Ranni là ai?"):
    return ChatRequest(message=message, channel="web", options={"web_search": "off"})


def test_tool_specs_follow_the_variant_and_web_policy():
    names = lambda specs: {s["function"]["name"] for s in specs}  # noqa: E731
    assert "finish" in names(tool_specs("generator", web=False)) and "final_answer" not in names(
        tool_specs("generator", web=False)
    )
    assert "final_answer" in names(tool_specs("final_answer", web=True))
    assert "search_web" not in names(tool_specs("generator", web=False))


async def test_generator_variant_searches_then_the_existing_writer_answers():
    model = ScriptedToolModel(
        [
            ("search_corpus", {"query": "Ranni identity"}),
            ("finish", {"request": "Who is Ranni?", "answer_language": "en", "evidence_ids": ["1"]}),
        ]
    )
    pipe = ChatPipeline(settings(), FakeLLM(), FakeRetriever())
    run = await run_true_agent(pipe, req(), variant="generator", model=model)
    assert run.stop == "finish" and run.result.grounded and run.result.answer.startswith("Ranni is an Empyrean")
    assert run.model_calls == 2 and [t["name"] for t in run.tool_calls] == ["search_corpus", "finish"]
    assert run.prepared.trace["evidence_selection"] == {"method": "model", "ids": ["1"]}
    assert model.bound["tool_choice"] == "auto" and "finish" in model.bound["tools"]
    assert run.usage == {"input_tokens": 200, "output_tokens": 20}


async def test_final_answer_variant_is_checked_and_a_rejection_goes_back_to_the_agent():
    model = ScriptedToolModel(
        [
            ("search_corpus", {"query": "Ranni identity"}),
            ("open_evidence", {"ids": ["1"]}),
            (
                "final_answer",
                {"answer": "Ranni [1].", "answer_language": "en", "evidence": [{"id": "9", "quote_ids": ["q0"]}]},
            ),
            (
                "final_answer",
                {
                    "answer": "Ranni is an Empyrean [1].",
                    "answer_language": "en",
                    "evidence": [{"id": "1", "quote_ids": ["q0"]}],
                },
            ),
        ]
    )
    pipe = ChatPipeline(settings(), FakeLLM(), FakeRetriever())
    run = await run_true_agent(pipe, req(), variant="final_answer", model=model)
    # The unknown evidence ID was returned to the Agent as a tool error, then fixed.
    assert [t["status"] for t in run.tool_calls] == ["ok", "ok", "error", "ok"]
    assert run.stop == "final_answer" and run.result.grounded and run.result.sources[0].index == 1
    assert run.prepared.trace["model_calls"] == [{"phase": "true_agent"}] * 4  # No separate generation call.


async def test_calculator_only_accepts_player_facts_and_reports_errors_to_the_agent():
    model = ScriptedToolModel(
        [
            ("calculator", {"level": "150", "allocation": {"vigor": 40}, "fill": "strength"}),
            ("calculator", {"level": "60", "allocation": {"vigor": 40}}),
            ("reply", {"text": "ok"}),
        ]
    )
    pipe = ChatPipeline(settings(), FakeLLM(), FakeRetriever())
    run = await run_true_agent(pipe, req("Build Strength level 60 giúp mình"), variant="generator", model=model)
    first = json.loads(next(m for m in model.seen[1] if isinstance(m, ToolMessage)).content)
    assert first["status"] == "error" and first["fields"] == ["level"]  # 150 is not in the player's message.
    second = model.last_tool_result()
    assert second["status"] == "error" and "eight attributes" in second["error"]
    assert run.prepared.checked_build is None and run.stop == "reply"


async def test_a_call_with_broken_json_arguments_is_answered_so_the_loop_can_continue():
    # Live spike 22/11: an unanswered invalid tool call made DeepSeek reject the next request (HTTP 400).
    model = ScriptedToolModel([("__invalid__", None), ("reply", {"text": "ok"})])
    pipe = ChatPipeline(settings(), FakeLLM(), FakeRetriever())
    run = await run_true_agent(pipe, req(), variant="generator", model=model)
    answered = [m for m in model.seen[1] if isinstance(m, ToolMessage)]
    assert answered and answered[-1].tool_call_id == "call_1" and "not valid JSON" in answered[-1].content
    assert run.stop == "reply" and run.tool_calls[0]["status"] == "invalid_arguments"
