"""Read-only local chunk-readiness study; no encoder/model/API execution."""

import argparse
import csv
import math
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup
from tokenizers import Tokenizer

from ingest.artifacts import now, read, save, sha256


def distribution(values):
    values = sorted(values)
    if not values:
        return {}

    def percentile(p):
        return values[max(0, math.ceil(len(values) * p) - 1)]

    return {
        "n": len(values),
        "min": values[0],
        "p50": percentile(0.5),
        "p90": percentile(0.9),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
        "max": values[-1],
        "total": sum(values),
    }


def study(input_dir, tokenizer_path, output_dir):
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Use a new or empty study output directory")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    source = read(input_dir / "report.json")
    for name, info in source["csv_validation"].items():
        if sha256((input_dir / name).read_bytes()) != info["sha256"]:
            raise ValueError("Input CSV no longer matches clean report")
    with (input_dir / "lore_clean.csv").open(encoding="utf-8-sig", newline="") as stream:
        clean_rows = {row["record_id"]: row for row in csv.DictReader(stream)}
    pages = source["input_pages"]
    records = []
    block_records = []
    page_stats = []
    inputs = {}
    repeated = []
    metadata = Counter()
    source_dom = {}
    dialogue_tables = []
    for page in pages:
        path = input_dir / "processed/wikigg" / (page["id"] + ".json")
        raw = read(path)
        inputs[str(path.resolve())] = sha256(path.read_bytes())
        if raw["revision_id"] != page["revision_id"]:
            raise ValueError("Processed revision mismatch")
        paths = Counter(s["section"] for s in raw["sections"])
        repeated.extend(
            {"title": page["title"], "section": name, "occurrences": n} for name, n in paths.items() if n > 1
        )
        counts = Counter()
        if not raw.get("updated_at"):
            metadata["documents_without_updated_at"] += 1
        for section in raw["sections"]:
            prefix = f"passage: {raw['title']}\n{section['section']}\n"
            body = len(tokenizer.encode(section["text"], add_special_tokens=False).ids)
            serialized = len(tokenizer.encode(prefix + section["text"], add_special_tokens=True).ids)
            kinds = Counter(b["kind"] for b in section["blocks"])
            row = {
                "source_id": page["id"],
                "title": raw["title"],
                "revision_id": raw["revision_id"],
                "record_id": section["record_id"],
                "section": section["section"],
                "status": section["scope_status"],
                "body_tokens": body,
                "serialized_tokens": serialized,
                "prefix_tokens": len(tokenizer.encode(prefix, add_special_tokens=False).ids),
                "heading_depth": len(section["section"].split(" > ")),
                "block_kinds": dict(kinds),
                "source_type": section["source_type"],
                "lang": section["lang"],
                "image_count": len(section.get("image_ids", [])),
                "lines": len(section["text"].splitlines()),
            }
            if section["scope_status"] == "base":
                csv_row = clean_rows.get(section["record_id"])
                if not csv_row or sha256(section["text"].encode()) != csv_row["content_hash"]:
                    raise ValueError("Processed section differs from exported CSV")
                metadata["base_with_dom_location"] += bool(section.get("location"))
                if section["section"] not in ("Introduction", "Infobox"):
                    metadata["base_headed_sections"] += 1
                    metadata["base_headed_sections_without_anchor"] += not section.get("anchor")
            records.append(row)
            counts[section["scope_status"]] += 1
            for block in section["blocks"]:
                if section["scope_status"] == "base" and block["kind"] == "dialogue":
                    if page["id"] not in source_dom:
                        snapshot = read(Path(raw["source_snapshot"]))
                        soup = BeautifulSoup(snapshot["content"], "html.parser")
                        body_node = soup.select_one(".mw-parser-output, #page-content, main")
                        source_dom[page["id"]] = list(body_node.find_all(True))
                    node = source_dom[page["id"]][int(block["location"].split(":")[1])]
                    if node.name != "table":
                        raise ValueError("DOM locator mismatch")
                    headers = [h.get_text(" ", strip=True) for h in node.select("th")]
                    dialogue_tables.append(
                        {
                            "title": raw["title"],
                            "section": section["section"],
                            "source_th_cells": len(headers),
                            "header_examples": headers[:3],
                            "processed_has_typed_turns": "turns" in block,
                        }
                    )
                block_records.append(
                    {
                        "title": raw["title"],
                        "section": section["section"],
                        "status": section["scope_status"],
                        "kind": block["kind"],
                        "tokens": len(tokenizer.encode(block["text"], add_special_tokens=False).ids),
                        "location": block["location"],
                    }
                )
            for key in ("record_id", "section", "text", "scope_status", "source_type", "lang"):
                if not section.get(key):
                    metadata["missing_" + key] += 1
        page_stats.append(
            {
                "source_id": page["id"],
                "title": raw["title"],
                "sections_by_status": dict(counts),
                "url_present": bool(raw.get("url")),
                "revision_present": bool(raw.get("revision_id")),
            }
        )
    base = [r for r in records if r["status"] == "base"]
    groups = {}
    for status in ("base", "review", "excluded"):
        items = [r for r in records if r["status"] == status]
        groups[status] = {
            "body_tokens": distribution([r["body_tokens"] for r in items]),
            "serialized_tokens": distribution([r["serialized_tokens"] for r in items]),
        }
    scenarios = {}
    for cap in (350, 400, 450, 500):
        for overlap in (0, 50):
            lengths = []
            prefix_too_long = 0
            for row in base:
                # Count-only estimate. Final semantic chunks must be re-encoded as whole strings.
                capacity = cap - row["prefix_tokens"] - 2
                if capacity <= overlap:
                    prefix_too_long += 1
                    continue
                remaining = row["body_tokens"]
                while remaining > 0:
                    take = min(capacity, remaining)
                    lengths.append(take)
                    if remaining <= capacity:
                        break
                    remaining -= capacity - overlap
            scenarios[f"{cap}/{overlap}"] = {
                "estimated_chunks": len(lengths),
                "body_under_100": sum(x < 100 for x in lengths),
                "prefix_budget_failures": prefix_too_long,
            }
    by_kind = {}
    for kind in sorted({r["kind"] for r in block_records}):
        selected = [r for r in block_records if r["kind"] == kind and r["status"] == "base"]
        by_kind[kind] = {
            "count": len(selected),
            "tokens": distribution([r["tokens"] for r in selected]),
            "over_450": sum(r["tokens"] > 450 for r in selected),
        }
    report = {
        "created_at": now(),
        "input_dir": str(input_dir.resolve()),
        "source_job": source["source_job"],
        "tokenizer_path": str(tokenizer_path.resolve()),
        "tokenizer_sha256": sha256(tokenizer_path.read_bytes()),
        "network_calls": 0,
        "embeddings_run": False,
        "page_count": len(pages),
        "section_counts": dict(Counter(r["status"] for r in records)),
        "distributions": groups,
        "base_body_bins": {f"under_{n}": sum(r["body_tokens"] < n for r in base) for n in (50, 100, 150, 300)},
        "base_serialized_over": {
            str(n): sum(r["serialized_tokens"] > n for r in base) for n in (350, 400, 450, 512, 1000, 2000)
        },
        "base_source_types": dict(Counter(r["source_type"] for r in base)),
        "base_languages": dict(Counter(r["lang"] for r in base)),
        "base_block_kinds": by_kind,
        "scenarios": scenarios,
        "scenario_method": (
            "count-only token windows with estimated prefix budget; not emitted or semantically validated chunks"
        ),
        "pages_without_base": sum(not p["sections_by_status"].get("base") for p in page_stats),
        "base_sections_with_images": sum(r["image_count"] > 0 for r in base),
        "repeated_heading_paths": repeated,
        "metadata_audit": dict(metadata),
        "dialogue_source_structure": {
            "tables": len(dialogue_tables),
            "source_th_cells": sum(t["source_th_cells"] for t in dialogue_tables),
            "typed_turn_blocks": sum(t["processed_has_typed_turns"] for t in dialogue_tables),
            "examples": dialogue_tables[:8],
        },
        "longest_base_sections": sorted(base, key=lambda r: r["serialized_tokens"], reverse=True)[:15],
        "sections": records,
        "blocks": block_records,
        "pages": page_stats,
    }
    for path, digest in inputs.items():
        if sha256(Path(path).read_bytes()) != digest:
            raise ValueError("Study changed source artifact")
    report["input_artifacts_unchanged"] = True
    output_dir.mkdir(parents=True, exist_ok=True)
    save(output_dir / "chunk-readiness.json", report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    r = study(args.input, args.tokenizer, args.output)
    print(
        {
            k: r[k]
            for k in (
                "page_count",
                "section_counts",
                "distributions",
                "base_body_bins",
                "base_serialized_over",
                "base_block_kinds",
                "scenarios",
                "metadata_audit",
            )
        }
    )


if __name__ == "__main__":
    main()
