"""Golden-set draft integrity and review gate; no corpus download, inference or HTTP requests."""

import json
from pathlib import Path

import pytest

from eval.validate_golden import validate

ROOT = Path(__file__).resolve().parents[2] / "eval"


def test_sprint2_adds_thirty_cases_with_vi_sote_negatives_and_honest_review_gate():
    result = validate(ROOT / "golden_set.jsonl", ROOT / "reviews/s2-golden-set-review.jsonl", require_reviewed=True)
    rows = [json.loads(s) for s in (ROOT / "golden_set.jsonl").read_text(encoding="utf-8").splitlines()]
    new = [r for r in rows if 31 <= int(r["id"].rsplit("-", 1)[1]) <= 60]
    assert len(new) == 30 and sum(r["lang"] == "vi" for r in new) >= 15
    assert sum(r["category"] == "out_of_scope" for r in new) == 6
    assert result["total"] >= 60 and result["vi_ratio"] >= 0.5 and result["sote_cases"] >= 10
    assert result["author_evidence_cases"] >= 24
    # Gate follows actual review records; later human approval must not break this test.
    reviews = [
        json.loads(s) for s in (ROOT / "reviews/s2-golden-set-review.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    approved = all(r["status"] == "approved" for r in reviews)
    assert result["accepted"] is approved and result["review_gate_passed"] is approved
    pvp = next(r for r in rows if r["id"] == "IB-GS-027")
    assert pvp["category"] == "insufficient_evidence" and pvp["source_urls"] == []


def draft():
    row = {
        "id": "IB-GS-001",
        "question": "Nhân vật là ai?",
        "lang": "vi",
        "expected_answer": "Đáp án tham chiếu.",
        "source_urls": ["https://example.test/source"],
        "category": "character",
        "difficulty": "easy",
    }
    review = {
        "id": row["id"],
        "status": "pending",
        "reviewer": None,
        "reviewed_at": None,
        "checks": {k: "pending" for k in ("source_urls", "expected_answer", "difficulty", "scope")},
    }
    return row, review


def files(tmp_path, rows, reviews):
    a, b = tmp_path / "golden.jsonl", tmp_path / "review.jsonl"
    for path, data in ((a, rows), (b, reviews)):
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in data), encoding="utf-8")
    return a, b


@pytest.mark.parametrize("problem", ["duplicate", "source_missing", "extra_field", "language_ratio", "bad_url"])
def test_rejects_invalid_golden_records(tmp_path, problem):
    row, review = draft()
    rows, reviews = [row], [review]
    if problem == "duplicate":
        rows.append(dict(row))
    elif problem == "source_missing":
        row["source_urls"] = []
    elif problem == "extra_field":
        row["review_status"] = "approved"
    elif problem == "language_ratio":
        row["lang"] = "en"
    else:
        row["source_urls"] = ["file:///source"]
    with pytest.raises(ValueError):
        validate(*files(tmp_path, rows, reviews))


def test_pending_is_draft_valid_but_not_review_approved(tmp_path):
    row, review = draft()
    paths = files(tmp_path, [row], [review])
    assert validate(*paths)["accepted"]
    assert not validate(*paths, require_reviewed=True)["accepted"]
    review.update(status="approved", reviewer="UncleThing", reviewed_at="2026-10-31T12:00:00+07:00")
    review["checks"] = {k: "pass" for k in review["checks"]}
    assert validate(*files(tmp_path, [row], [review]), require_reviewed=True)["accepted"]
    review["reviewer"] = "TV3 - MinhMuc"
    with pytest.raises(ValueError, match="TV2"):
        validate(*files(tmp_path, [row], [review]), require_reviewed=True)


def test_artifact_quote_checks_do_not_accept_fabricated_provenance(tmp_path):
    import hashlib

    row, review = draft()
    text = "Exact source text."
    review["author_evidence"] = [
        {
            "chunk_id": "chunk",
            "source_url": row["source_urls"][0],
            "quote_start": 0,
            "quote": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
    ]
    corpus = tmp_path / "chunks.jsonl"
    corpus.write_text(
        json.dumps({"chunk_id": "chunk", "url": row["source_urls"][0], "text": text}) + "\n", encoding="utf-8"
    )
    assert validate(*files(tmp_path, [row], [review]), corpus=corpus)["author_evidence_cases_verified"] == 1
    review["author_evidence"][0]["quote"] = "Invented source text."
    with pytest.raises(ValueError, match="exact artifact"):
        validate(*files(tmp_path, [row], [review]), corpus=corpus)
