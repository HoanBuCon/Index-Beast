"""Check the clean-only export and quantify tables quarantined from chunk input."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


def lines(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def catalog_header(text):
    return bool(re.search(r"(?im)^\s*(?:Icon|Image)\s*\|\s*(?:Item(?: Name)?|Name)\s*\|", text))


def run(clean, chunks, previous_chunks, protocol, output):
    with (clean / "content_clean.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        accepted = list(reader)
        assert all(None not in r and all(v is not None for v in r.values()) for r in accepted)
    assert all(r["decision"] == "keep" and r["chunk_eligible"] == "True" for r in accepted)
    assert not any(catalog_header(r["text"]) for r in accepted)
    current = lines(chunks / "chunks.jsonl")
    assert not any(catalog_header(r["text"]) for r in current)
    sections = {
        (d["source_id"], s["section"], b["location"]): b
        for f in (clean / "filtered").glob("*.json")
        for d in [json.loads(f.read_text(encoding="utf-8"))]
        for s in d["sections"]
        for b in s["blocks"]
    }
    removed = []
    for c in lines(previous_chunks):
        reasons = {
            sections[(c["source_id"], c["section"], loc)]["reason"]
            for loc in c["source_locations"]
            if (c["source_id"], c["section"], loc) in sections
            and sections[(c["source_id"], c["section"], loc)]["decision"] != "keep"
        }
        if reasons:
            removed.append(dict(c, table_filter_reasons=sorted(reasons)))
    assertions = json.loads(protocol.read_text(encoding="utf-8"))["cases"]
    facts = sum(
        any(
            c["source_id"] == q["source_id"] and re.search(q["evidence_pattern"], c["embedding_text"], re.I)
            for c in current
        )
        for q in assertions
    )
    assert facts == len(assertions), "A previously preserved equipment fact disappeared"
    # The example in the screenshot must remain available for review, never in clean-only.
    with (clean / "review.csv").open(encoding="utf-8-sig", newline="") as stream:
        review = list(csv.DictReader(stream))
    assert any(r["source_id"] == "52" and catalog_header(r["text"]) for r in review)
    output.mkdir(parents=True, exist_ok=True)
    (output / "removed-chunks.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in removed), encoding="utf-8"
    )
    with (clean / "content_clean_all.csv").open(encoding="utf-8-sig", newline="") as stream:
        catalog_rows = sum(1 for _ in csv.DictReader(stream))
    report = {
        "clean_rows": len(accepted),
        "catalog_rows": catalog_rows,
        "chunks": len(current),
        "previous_chunks_quarantined": len(removed),
        "removed_reasons": dict(Counter(reason for c in removed for reason in c["table_filter_reasons"])),
        "labelled_stats_chunks_retained": sum(c["unit_kind"] == "infobox_stats" for c in current),
        "equipment_facts_present": facts,
        "equipment_cases": len(assertions),
        "catalog_header_in_clean_or_chunks": 0,
        "screenshot_source_52_retained_in_review": True,
        "chunk_sha256": hashlib.sha256((chunks / "chunks.jsonl").read_bytes()).hexdigest(),
        "api_calls": 0,
        "encoder_calls": 0,
        "database_writes": 0,
        "note": "Fact presence and table structure only; no new vector or LLM benchmark.",
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", type=Path, required=True)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--previous-chunks", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.clean, args.chunks, args.previous_chunks, args.protocol, args.output)
