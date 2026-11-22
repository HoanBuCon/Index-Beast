"""Attach provenance and export table inventory/facts/review with CSV round-trip checks."""

import csv
import json
import re
from collections import Counter

from core.text.structured_tables import row_metadata
from ingest.artifacts import save, sha256
from ingest.transform.document import stable_id


def attach(parsed, raw, snapshot, policy_version):
    tables, facts = [], []
    mapping, ids = {}, {}
    affinity = {
        b["table_id"]: (b.get("variant_context") or {}).get("label")
        for s in parsed["sections"]
        for b in s["blocks"]
        if b.get("table_type") == "upgrade_stats"
    }
    context = {k: raw[k] for k in ["source_id", "source", "title", "revision_id", "fetched_at"]}
    context.update(
        source_id=str(raw["source_id"]),
        source_snapshot=str(snapshot),
        url=raw["url"],
        raw_content_hash=raw["content_hash"],
        parser_version=policy_version,
        game_scope="elden_ring",
    )
    for table in parsed.get("table_inventory", []):
        table_id = stable_id(raw["source_id"], raw["revision_id"], table["table_id"], policy_version)
        ids[table["table_id"]] = table_id
        for fact in table["facts"]:
            fid = stable_id(table_id, fact["fact_id"])
            mapping[fact["fact_id"]] = fid
            language = fact["lang"]
            if language == "unknown" and not re.search(r"[\u3040-\u30ff\u3400-\u9fff]", fact["raw_cell_text"]):
                language = parsed["html_lang"] if parsed["html_lang"] in {"en", "vi", "ja"} else "unknown"
            facts.append(
                dict(
                    fact,
                    **context,
                    fact_id=fid,
                    table_id=table_id,
                    section=table["section"],
                    table_type=table["table_type"],
                    variant=table["variant"],
                    lang=language,
                    location=table["location"] + "/" + fact["cell_id"],
                    source_type="in_game_text" if table["table_type"] == "dialogue_table" else "wiki_prose",
                )
            )
        tables.append(
            dict({k: v for k, v in table.items() if k not in {"facts", "blocks"}}, **context, table_id=table_id)
        )
        tables[-1]["affinity"] = affinity.get(table["table_id"])
    for section in parsed["sections"]:
        for block in section["blocks"]:
            if block.get("table_id"):
                block["table_id"] = ids[block["table_id"]]
                block["fact_ids"] = [mapping[f] for f in block["fact_ids"]]
    affinity_by_id = {t["table_id"]: t.get("affinity") for t in tables}
    for fact in facts:
        fact.update(**row_metadata(fact["row_key"]), affinity=affinity_by_id[fact["table_id"]])
    return tables, facts


def export(output, tables, facts, *, replace=False):
    output.mkdir(parents=True, exist_ok=replace)
    reviews = []
    for t in tables:
        for cell in t["cells"]:
            if cell["decision"] != "keep":
                reviews.append(
                    {
                        "record_id": stable_id(t["table_id"], cell["cell_id"]),
                        "table_id": t["table_id"],
                        "source_id": t["source_id"],
                        "title": t["title"],
                        "revision_id": t["revision_id"],
                        "section": t["section"],
                        "location": t["location"] + "/" + cell["cell_id"],
                        "source_snapshot": t["source_snapshot"],
                        "decision": cell["decision"],
                        "reason": cell["reason"],
                        "raw_cell_text": cell["text"],
                    }
                )
    checks = {}
    for name, rows in [
        ("tables_inventory", tables),
        ("table_facts", facts),
        ("facts_clean", [f for f in facts if f["decision"] == "keep"]),
        ("tables_review", reviews),
    ]:
        path = output / (name + ".jsonl")
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        checks[path.name] = {"rows": len(rows), "sha256": sha256(path.read_bytes())}
        if name == "tables_inventory":
            continue
        headers = (
            list(rows[0])
            if rows
            else (["fact_id", "decision"] if name in {"table_facts", "facts_clean"} else ["record_id", "decision"])
        )
        csv_path = output / (name + ".csv")
        expected = [
            {
                k: json.dumps(r[k], ensure_ascii=False)
                if isinstance(r.get(k), (list, dict))
                else ""
                if r.get(k) is None
                else str(r.get(k, ""))
                for k in headers
            }
            for r in rows
        ]
        with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(expected)
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            if list(csv.DictReader(stream)) != expected:
                raise ValueError("Structured table CSV round-trip mismatch")
        checks[csv_path.name] = {"rows": len(rows), "sha256": sha256(csv_path.read_bytes())}
    report = {
        "tables": len(tables),
        "facts": len(facts),
        "review_or_excluded_cells": len(reviews),
        "table_types": dict(Counter(t["table_type"] for t in tables)),
        "table_decisions": dict(Counter(t["decision"] for t in tables)),
        "cell_decisions": dict(Counter(c["decision"] for t in tables for c in t["cells"])),
        "fact_decisions": dict(Counter(f["decision"] for f in facts)),
        "review_reasons": dict(Counter(r["reason"] for r in reviews)),
        "csv_roundtrip_verified": True,
        "files": checks,
    }
    save(output / "report.json", report)
    return report


def finalize(clean):
    """Regenerate table exports from verified inventory without changing source values."""
    report_path = clean / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for name, info in report["structured_tables"]["files"].items():
        if sha256((clean / "tables" / name).read_bytes()) != info["sha256"]:
            raise ValueError("Table artifact changed before finalizing")

    def read_lines(path):
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    report["structured_tables"] = export(
        clean / "tables",
        read_lines(clean / "tables/tables_inventory.jsonl"),
        read_lines(clean / "tables/table_facts.jsonl"),
        replace=True,
    )
    save(report_path, report)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean", type=Path)
    finalize(parser.parse_args().clean)
