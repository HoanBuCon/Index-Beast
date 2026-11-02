"""Audit fixtures stay local; counters and samples must not imply semantic coverage."""

import csv
import json

from scripts.audit_corpus_capabilities import audit


def test_capability_audit_keeps_unknown_labels_and_excluded_data_separate(tmp_path):
    chunks, clean = tmp_path / "chunks", tmp_path / "clean"
    chunks.mkdir()
    clean.mkdir()
    row = {
        "chunk_id": "a",
        "game_scope": "elden_ring",
        "lang": "en",
        "source_type": "wiki_prose",
        "release_scope": "unknown",
        "title": "Arsenal Charm",
        "section": "Description",
        "text": "Boosts maximum equipment load.",
        "unit_kind": "prose",
        "source_updated_at": None,
    }
    (chunks / "chunks.jsonl").write_text(
        json.dumps(row) + "\n" + json.dumps({**row, "chunk_id": "b", "lang": "unknown"}) + "\n",
        encoding="utf-8",
    )
    for name in ("documents.jsonl", "review.jsonl", "coverage.jsonl"):
        (chunks / name).write_text("{}\n", encoding="utf-8")
    with (clean / "review.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["title", "reason", "decision", "text"])
        writer.writeheader()
        writer.writerow(
            {
                "title": "Arsenal Charm",
                "reason": "gameplay_section",
                "decision": "excluded",
                "text": "Acquisition information deliberately not indexed.",
            }
        )
    before = (chunks / "chunks.jsonl").read_bytes()
    result = audit(chunks, clean)
    assert result["counts"] == {"total_chunks": 2, "selected_chunks": 1}
    assert result["not_selected_reasons"] == {"language_not_selected": 1}
    assert result["selected_releases"] == {"unknown": 1}
    assert result["selected_literal_signals"]["status_or_effect"] == 1
    focus = result["focus"]["Arsenal Charm"]
    assert focus["selected_chunks"] == 1 and len(focus["review_samples"]) == 1
    assert focus["samples"][0]["chunk_id"] == "a"
    assert "source_updated_at" not in result["selected_nonempty_fields"]
    assert "NOT semantic coverage" in result["method"]
    assert (chunks / "chunks.jsonl").read_bytes() == before
