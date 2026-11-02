"""Read-only corpus census and deterministic evidence samples; no model loading or client construction.

Run from backend: python -m scripts.audit_corpus_capabilities --output ../docs/testing/corpus-capabilities.json
Signals are literal text occurrences, NOT verified capability coverage or retrieval results.
"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from core.corpus import CorpusPolicy

FOCUS = (
    "Bloodhound's Fang",
    "Rivers of Blood",
    "Uchigatana",
    "Moonveil",
    "Arsenal Charm",
    "Radagon's Soreseal",
    "Flame, Cleanse Me",
    "Ash of War: Golden Vow",
    "Malenia, Blade of Miquella",
    "Ranni the Witch",
    "Blaidd the Half-Wolf",
    "Great-Jar's Arsenal",
)
SIGNALS = {
    "scaling_or_requirements": r"\b(scaling|requirements?|requires?|strength|dexterity|arcane)\b",
    "status_or_effect": r"\b(blood loss|poison|scarlet rot|frostbite|equipment load)\b",
    "location_or_acquisition": r"\b(found|dropped|obtained|located|acquired|starting equipment)\b",
    "quest": r"\b(quest|questline|progression|prerequisite)\b",
    "combat": r"\b(parry|dodge|invincibility|weakness|resistance|strategy)\b",
    "version_mention": r"\b(?:patch|version)\s*\d+(?:\.\d+)*",
}


def jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as stream:
        for line, text in enumerate(stream, 1):
            try:
                row = json.loads(text)
                if not isinstance(row, dict):
                    raise ValueError("Expected object")
            except ValueError as exc:
                raise ValueError(f"{path}:{line}: invalid JSON object") from exc
            yield line, row


def sample(line: int, row: dict) -> dict:
    return {
        "line_or_record": line,
        **{k: row[k] for k in ("chunk_id", "record_id", "title", "section", "reason", "decision", "url") if k in row},
        "excerpt": row.get("text", "")[:450],
    }


def audit(chunk_dir: Path, clean_dir: Path) -> dict:
    policy = CorpusPolicy("pilot", ("en",))
    path = chunk_dir / "chunks.jsonl"
    counts, languages, selected_releases, reasons, sections, kinds, signals = (Counter() for _ in range(7))
    fields = Counter()
    focus = {name: {"selected_chunks": 0, "sections": Counter(), "samples": [], "review_samples": []} for name in FOCUS}
    chunk_ids = set()
    for line, row in jsonl(path):
        counts["total_chunks"] += 1
        if row["chunk_id"] in chunk_ids:
            raise ValueError(f"{path}:{line}: duplicate chunk_id")
        chunk_ids.add(row["chunk_id"])
        languages[row.get("lang", "<missing>")] += 1
        reason = policy.exclusion_reason(row)
        if reason:
            reasons[reason] += 1
            continue
        counts["selected_chunks"] += 1
        selected_releases[row.get("release_scope", "<missing>")] += 1
        sections[row.get("section", "<missing>")] += 1
        kinds[row.get("unit_kind", "<missing>")] += 1
        fields.update(k for k, v in row.items() if v is not None and v != "")
        for label, pattern in SIGNALS.items():
            if re.search(pattern, row["text"], re.I):
                signals[label] += 1
        item = focus.get(row.get("title"))
        if item is not None:
            item["selected_chunks"] += 1
            item["sections"][row.get("section", "<missing>")] += 1
            # First occurrence in artifact order for each distinct section, bounded to eight.
            if len(item["samples"]) < 8 and not any(s["section"] == row["section"] for s in item["samples"]):
                item["samples"].append(sample(line, row))
    clean_review = clean_dir / "review.csv"
    review_reasons = Counter()
    with clean_review.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for record, row in enumerate(reader, 1):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"{clean_review}:record {record}: column count mismatch")
            review_reasons[row["reason"]] += 1
            item = focus.get(row.get("title"))
            if (
                item is not None
                and row["reason"]
                in {
                    "gameplay_section",
                    "gameplay_infobox_field",
                    "numeric_stats_table",
                    "combat_section_may_contain_lore",
                    "combat_loadout_table",
                    "unclassified_structure",
                }
                and len(item["review_samples"]) < 6
            ):
                item["review_samples"].append(sample(record, row))
    auxiliary = {}
    for name in ("documents.jsonl", "review.jsonl", "coverage.jsonl"):
        records = list(jsonl(chunk_dir / name))
        auxiliary[name] = {"records": len(records), "first_record_fields": sorted(records[0][1]) if records else []}
    return {
        "method": "Full read-only census, pilot/en; fixed 12-title sample, first distinct sections in input order. "
        "Text signals are NOT semantic coverage, source verification, model evaluation or retrieval recall.",
        "input": path.as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "counts": dict(counts),
        "languages": dict(languages),
        "not_selected_reasons": dict(reasons),
        "selected_releases": dict(selected_releases),
        "selected_nonempty_fields": dict(fields),
        "selected_sections": dict(sections.most_common()),
        "selected_unit_kinds": dict(kinds),
        "selected_literal_signals": dict(signals),
        "clean_review_reasons": dict(review_reasons.most_common()),
        "auxiliary": auxiliary,
        "focus": focus,
        "limitations": "Reviewed sample has no statistical representativeness. Absence in a sampled title does "
        "not prove absence corpus-wide. Review rows are inspected only, never admitted into the index.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=Path("data/chunk_runs/s2-full-v1"))
    parser.add_argument("--clean", type=Path, default=Path("data/clean_runs/s2-full-v2"))
    parser.add_argument("--output", type=Path, help="Optional UTF-8 report path; omitted prints only")
    args = parser.parse_args()
    result = json.dumps(audit(args.chunks, args.clean), ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(result, end="")
    else:
        destination = args.output.resolve()
        for protected in (args.chunks.resolve(), args.clean.resolve()):
            if destination.is_relative_to(protected):
                parser.error("Report must be outside the input artifact directories")
        destination.write_text(result, encoding="utf-8")
        print(f"Wrote read-only audit report: {args.output}")


if __name__ == "__main__":
    main()
