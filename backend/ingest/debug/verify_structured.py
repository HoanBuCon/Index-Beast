"""Offline delivery checks: facts against source cells, CSV, stats, media and hashes."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def lines(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def verify(clean, chunks, output, baseline, sample=None):
    output.mkdir(parents=True, exist_ok=True)
    tables = lines(clean / "tables/tables_inventory.jsonl")
    facts = lines(clean / "tables/table_facts.jsonl")
    data = lines(chunks / "chunks.jsonl")
    cells = {t["table_id"]: {c["cell_id"]: c for c in t["cells"]} for t in tables}
    table_map = {t["table_id"]: t for t in tables}
    fact_map = {f["fact_id"]: f for f in facts}
    errors = []
    assert len(fact_map) == len(facts), "Duplicate fact ID"
    assert len(cells) == len(tables), "Duplicate table ID"
    for fact in facts:
        cell = cells[fact["table_id"]][fact["cell_id"]]
        assert fact["raw_cell_text"] == cell["text"], "Fact differs from source cell"
        assert fact["column_index"] == cell["column"], "Fact moved to wrong source column"
        assert fact["decision"] in {"keep", "review"}
        if fact["decision"] == "keep" and table_map[fact["table_id"]]["headers"].count(fact["stat_name"]) > 1:
            errors.append({"check": "unresolved_repeated_header", "fact_id": fact["fact_id"]})
        if fact["decision"] == "keep" and re.search(
            r"Nightreign|Tarnished Edition|Cut dialogue|Cut content|Unused|Behind the scenes",
            fact["title"] + " " + fact["section"],
            re.I,
        ):
            errors.append({"check": "outside_scope_fact", "fact_id": fact["fact_id"], "title": fact["title"]})
    used = set()
    for chunk in data:
        for fid in chunk.get("fact_ids", []):
            f = fact_map[fid]
            assert f["decision"] == "keep" and f["source_id"] == chunk["source_id"]
            assert f["revision_id"] == chunk["revision_id"] and f["table_id"] == chunk["table_id"]
            used.add(fid)
        # Exclude U+30FB middle dot used as a bullet in English item descriptions.
        if chunk["lang"] == "en" and re.search(
            r"[\u3041-\u3096\u309d-\u309f\u30a1-\u30fa\u30fd-\u30ff]", chunk["text"]
        ):
            errors.append({"check": "japanese_in_en", "chunk_id": chunk["chunk_id"]})
    for table in tables:
        assert all(c["decision"] in {"keep", "review", "excluded"} and c.get("reason") for c in table["cells"])
    checks = {}
    for root, names in [
        (
            clean,
            [
                "content_clean.csv",
                "content_clean_all.csv",
                "review.csv",
                "images.csv",
                "tables/table_facts.csv",
                "tables/facts_clean.csv",
                "tables/tables_review.csv",
            ],
        ),
        (chunks, ["chunks.csv"]),
    ]:
        for name in names:
            path = root / name
            assert path.read_bytes().startswith(b"\xef\xbb\xbf"), "CSV lacks BOM"
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                count = 0
                for row in reader:
                    assert None not in row and all(v is not None for v in row.values()), "Malformed CSV columns"
                    if name == "content_clean.csv":
                        assert row["decision"] == "keep" and row["chunk_eligible"] == "True"
                    if name == "tables/facts_clean.csv":
                        assert row["decision"] == "keep"
                    if name == "images.csv" and row.get("local_path"):
                        assert Path(row["local_path"]).is_file() or (Path("data") / row["local_path"]).is_file()
                    count += 1
            checks[str(path)] = {"rows": count, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    expected = read(baseline)
    facts_present = []
    for q in expected["facts"]:
        hit = any(
            c["source_id"] == q["source_id"] and re.search(q["evidence_pattern"], c["embedding_text"], re.I)
            for c in data
        )
        facts_present.append({"id": q["id"], "present": hit})
    assert all(x["present"] for x in facts_present), "Previously preserved equipment fact lost"
    stats = sum(c["unit_kind"] == "infobox_stats" for c in data)
    assert stats >= expected["prior_stats_chunks"], "Previously preserved stat contexts lost"
    fingerprints = read(Path("data/raw/final-input-fingerprints.json"))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in fingerprints.items())
    upgrades = [t for t in tables if t["table_type"] == "upgrade_stats"]
    longsword = [t for t in upgrades if t["title"] == "Longsword"]
    assert len(longsword) == 13 and len({t["variant"] for t in longsword}) == 13
    crystal = [f for f in facts if f["title"] == "Crystal Sword" and f["table_type"] == "upgrade_stats"]
    assert all(f["stat_name"] == "Atk" and f["decision"] == "review" for f in crystal if f["value"] in {"68", "166"})
    assert {f["value"] for f in crystal if f["stat_name"] == "Grd Boost" and f["decision"] == "keep"} >= {"33", "36.3"}
    stable_sample = None
    if sample:
        small = lines(sample / "chunks.jsonl")
        ids = {c["source_id"] for c in small}

        def logical(rows):
            return {c["chunk_id"]: {k: v for k, v in c.items() if k != "updated_at"} for c in rows}

        stable_sample = logical(small) == logical([c for c in data if c["source_id"] in ids])
        assert stable_sample, "Sample and full run differ"
    report = {
        "clean_dir": str(clean.resolve()),
        "chunk_dir": str(chunks.resolve()),
        "clean_report_sha256": hashlib.sha256((clean / "report.json").read_bytes()).hexdigest(),
        "chunk_artifact_sha256": hashlib.sha256((chunks / "chunks.jsonl").read_bytes()).hexdigest(),
        "tables": len(tables),
        "source_cells": sum(len(t["cells"]) for t in tables),
        "table_decisions": dict(Counter(t["decision"] for t in tables)),
        "facts": len(facts),
        "facts_kept": sum(f["decision"] == "keep" for f in facts),
        "facts_linked_from_chunks": len(used),
        "stats_chunks": stats,
        "chunks": len(data),
        "upgrade_tables": len(upgrades),
        "longsword_variants": len(longsword),
        "facts_presence": facts_present,
        "raw_manifest_fingerprints_verified": len(fingerprints),
        "csv": checks,
        "sample_stable": stable_sample,
        "errors": errors,
        "api_calls": 0,
        "encoder_calls": 0,
        "database_writes": 0,
        "limitations": "Structural/fact-presence audit; not retrieval/LLM or human semantic certification.",
    }
    (output / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"csv", "facts_presence"}}))
    if errors:
        raise ValueError("Verification flags require review/fix before delivery")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", type=Path, required=True)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--sample", type=Path)
    args = parser.parse_args()
    verify(args.clean, args.chunks, args.output, args.baseline, args.sample)
