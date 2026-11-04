"""Offline diagnostic runner guards, checkpoints and no golden-answer leakage."""

import json
from copy import deepcopy

import pytest

from app.rag.pipeline import ChatPipeline
from core.config import Settings
from scripts import diagnose_golden as diagnostic
from tests.unit.test_live_chat import FakeLLM, FakeRetriever, SequenceLLM


def case(key="IB-GS-001"):
    return {
        "id": key,
        "question": "Ranni là ai?",
        "lang": "vi",
        "expected_answer": "PRIVATE_REFERENCE_ONLY",
        "source_urls": ["https://example.test/ranni"],
        "category": "character",
        "difficulty": "easy",
    }


def test_plan_uses_exact_25_distinct_golden_cases_without_settings_or_clients(capsys, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("execution must not start")

    monkeypatch.setattr(diagnostic, "live", forbidden)
    assert diagnostic.main([]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["cases"] == 25 and result["max_logical_model_calls"] == 100
    # Selection remains 25; the source dataset has been extended to 100 separately.
    assert result["review_status"] == {"pending": 100}
    assert result["languages"]["vi"] >= 13


@pytest.mark.parametrize("args", [["--execute"], ["--execute", "--allow-llm"]])
def test_explicit_execution_permissions_are_required(args, monkeypatch):
    monkeypatch.setattr(diagnostic, "live", lambda *a: pytest.fail("must not execute"))
    with pytest.raises(SystemExit) as exc:
        diagnostic.main(args)
    assert exc.value.code == 2


async def test_answer_reference_never_reaches_model_and_final_text_only_is_recorded(tmp_path):
    fake = FakeLLM()
    llm = diagnostic.CapturedLLM(fake)
    pipeline = ChatPipeline(Settings(_env_file=None, chat_mode="rag"), llm, FakeRetriever())
    checkpoints = []
    rows = await diagnostic.diagnose([case()], pipeline, llm, checkpoint=lambda r: checkpoints.append(deepcopy(r)))
    assert rows[0]["status"] == "ok" and rows[0]["answer"] == fake.data["answer"]
    assert "PRIVATE_REFERENCE_ONLY" not in str(fake.seen)
    assert rows[0]["context"] and rows[0]["sources"] and rows[0]["model_outputs"]
    assert "reasoning_content" not in str(rows)
    assert len(checkpoints) == 1
    report = {"rows": rows}
    diagnostic.save_checkpoint(tmp_path, report)
    diagnostic.write_review(tmp_path, report)
    assert not (tmp_path / "report.tmp").exists()
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["rows"][0]["status"] == "ok"
    review = json.loads((tmp_path / "manual_review.jsonl").read_text(encoding="utf-8"))
    assert review["correctness"] is None and review["reviewer"] is None
    assert (tmp_path / "review.md").exists()


async def test_failed_case_remains_in_report_and_next_case_still_runs():
    valid = json.dumps(FakeLLM().data)
    fake = SequenceLLM(["invalid JSON", valid])
    llm = diagnostic.CapturedLLM(fake)
    pipeline = ChatPipeline(Settings(_env_file=None, chat_mode="rag", rag_format_retries=0), llm, FakeRetriever())
    rows = await diagnostic.diagnose([case(), case("IB-GS-002")], pipeline, llm)
    assert [row["status"] for row in rows] == ["error", "ok"]
    result = diagnostic.summary(rows)
    assert result["cases_attempted"] == 2 and result["errors"] == 1
    assert result["source_page_hit_at5"]["denominator"] == 2
    assert result["correctness"] is None and result["recall_at5"] is None


def test_output_cannot_overwrite_existing_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostic, "live", lambda *a: pytest.fail("must not execute"))
    with pytest.raises(SystemExit):
        diagnostic.main(["--execute", "--allow-llm", "--allow-web", "--output-dir", str(tmp_path)])


def test_unknown_or_duplicate_selection_id_is_rejected(tmp_path):
    selection = tmp_path / "selection.json"
    selection.write_text('{"ids":["IB-GS-001","IB-GS-001"]}', encoding="utf-8")
    with pytest.raises(ValueError):
        diagnostic.load_cases(
            diagnostic.ROOT / "golden_set.jsonl", diagnostic.ROOT / "reviews/s2-golden-set-review.jsonl", selection
        )


async def test_capture_never_serializes_private_reasoning_and_call_budget_is_enforced():
    from app.adapters.llm import LLMResponse

    class Delegate:
        async def invoke_chain(self, chain, inputs):
            return LLMResponse("{}", "fake", 2, 3, "stop", reasoning_content="PRIVATE_REASONING")

    capture = diagnostic.CapturedLLM(Delegate(), max_calls=1)
    await capture.invoke_chain(None, {"policy": "Rewrite"})
    assert "PRIVATE_REASONING" not in str(capture.outputs)
    with pytest.raises(RuntimeError, match="budget exhausted"):
        await capture.invoke_chain(None, {"policy": "Rewrite"})
