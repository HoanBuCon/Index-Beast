"""Replays actual failing decisions offline; corrected responses are scripted, not live retests."""

import json
from pathlib import Path

import pytest

from app.rag.agent import decide
from tests.unit.test_agent_durable import AgentLLM, settings

CASES = json.loads((Path(__file__).parents[1] / "fixtures/agent_media_decisions.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
async def test_live_invalid_decision_gets_one_bounded_model_repair(case):
    llm = AgentLLM([case["bad"], case["fixed"]])
    trace = {}
    result = await decide(llm, case["question"], [], {}, "vi", settings(), trace, requested_lang="vi")
    assert result is not None
    assert len(llm.plans) == 2 and llm.plans[1]["repair"]["previous_decision"] == case["bad"]
    assert [c["phase"] for c in trace["model_calls"]] == ["decision", "decision_repair"]
    assert trace["agent"]["repair_attempts"] == 1


async def test_repair_never_loops_or_bypasses_provenance():
    case = CASES[0]
    llm = AgentLLM([case["bad"]])
    trace = {}
    assert await decide(llm, case["question"], [], {}, "vi", settings(), trace) is None
    assert len(llm.plans) == 2
    # Generation reserve disallows an additional attempt when only one call remains.
    trace = {}
    assert await decide(llm, case["question"], [], {}, "vi", settings(chat_agent_max_calls=2), trace) is None
    assert len(trace["model_calls"]) == 1
