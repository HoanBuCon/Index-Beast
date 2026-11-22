"""Công cụ đo golden 200 (24/11): manifest, judge, tổng hợp và reranker chờ khi 429. Offline, không gọi API."""

import pytest

from eval.golden_manifest import build
from eval.judge_answers import judge_input, valid
from eval.measure_retrieval import OutcomeLog, ThrottledReranker
from eval.summarize_ablation import aggregate, case_row


def test_manifest_has_every_approved_case_with_labels_and_the_clarification_reply():
    cases = build()
    assert len(cases) == 200 and {c["difficulty"] for c in cases} == {"easy", "medium", "hard"}
    diallos = next(c for c in cases if c["id"] == "IB-GS-279")
    assert diallos["replies"] and "lần đầu" in diallos["replies"][0] and diallos["followup_expected_answer"]
    assert sum(bool({"typo", "vi_no_diacritics", "telex", "abbreviation"} & set(c["case_tags"])) for c in cases) >= 40


def test_judge_scores_are_validated_and_the_input_carries_both_turns():
    assert valid({"correctness": 2, "faithfulness": None, "behavior": None, "followup": None})["correctness"] == 2
    with pytest.raises(ValueError):
        valid({"correctness": 3})
    case = {"category": "quest", "question": "q", "expected_answer": "a", "followup_expected_answer": "b"}
    result = {
        "turns": [
            {"answer": "", "clarification": {"question": "Ai?"}, "sources": []},
            {"message": "Diallos", "answer": "Liurnia [1]", "sources": [{"title": "Knight Diallos", "text": "x"}]},
        ]
    }
    payload = judge_input(case, result)
    assert payload["first_turn"]["clarification_question"] == "Ai?"
    assert payload["followup"]["reference_answer"] == "b" and payload["followup"]["sources"][0]["excerpt"] == "x"


def test_summary_counts_gold_pages_jina_outcomes_and_the_discord_limit():
    case = {
        "id": "IB-GS-1",
        "difficulty": "easy",
        "lang": "vi",
        "category": "mechanics",
        "case_tags": ["typo"],
        "source_urls": ["https://eldenring.wiki.gg/wiki/Golden_Seed"],
    }
    turn = {
        "http_status": 200,
        "last_event": "done",
        "grounded": True,
        "client_ms": 46000,
        "sources": [{"url": "https://eldenring.wiki.gg/wiki/Golden_Seed/"}],
        "trace": {"agent": {"steps": [{"tool": "search_corpus"}, {"tool": "search_web"}], "usage": {}}},
    }
    row = case_row(case, {"turns": [turn], "rerank": {"ok": 1, "fallback:http_status:429": 3}}, {"correctness": 2})
    assert row["gold_cited"] and row["noisy"] and row["over_45s"] and row["search_web"] == 1
    summary = aggregate([row])
    assert summary["accuracy_pct"] == 100.0 and summary["reranker_ok_pct"] == 25.0 and summary["over_45s"] == 1


async def test_throttled_reranker_retries_only_on_rate_limit(monkeypatch):
    log = OutcomeLog()

    class Flaky:
        calls = 0

        async def rank(self, query, hits):
            self.calls += 1
            log.rows.append({"status": "ok" if self.calls == 3 else "fallback", "reason": "http_status"})
            return ["ranked"] if self.calls == 3 else hits

    async def no_wait(_):
        return None

    monkeypatch.setattr("eval.measure_retrieval.asyncio.sleep", no_wait)
    flaky = Flaky()
    assert await ThrottledReranker(flaky, log).rank("q", ["rrf"]) == ["ranked"] and flaky.calls == 3
