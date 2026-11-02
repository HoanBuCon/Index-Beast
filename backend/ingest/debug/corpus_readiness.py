"""Read-only audit of the delivered corpus; writes findings to a new directory."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup
from tokenizers import Tokenizer

from core.ids import chunk_id, document_id
from core.text.chunking import prepare_units
from ingest.chunk.load_full import preflight


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


def metadata_audit(data, output):
    """Count missing structured metadata, without inferring absence from prose."""
    fields = [
        "patch_version",
        "game_version",
        "upgrade_level",
        "affinity",
        "ng_cycle",
        "source_updated_at",
        "spoiler_level",
        "content_type",
        "review_status",
    ]
    result = {
        "chunk_nonempty_metadata": dict.fromkeys(fields, 0),
        "csv_schema": {},
        "semantic_review_candidates": [],
        "language_label_mismatches": [],
        "short_body_chunks_at_most_20_chars": 0,
    }
    with (data / "chunk_runs/s2-full-v1/chunks.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            chunk = json.loads(line)
            label = (chunk.get("variant_context") or {}).get("label")
            explicit_language = {
                "🇧🇷": "pt",
                "🇵🇹": "pt",
                "🇹🇼": "zh",
                "🇯🇵": "ja",
                "🇨🇳": "zh",
                "🇩🇪": "de",
                "🇫🇷": "fr",
                "🇮🇹": "it",
                "🇰🇷": "ko",
                "🇷🇺": "ru",
                "🇵🇱": "pl",
                "🇪🇸": "es",
                "🇹🇭": "th",
            }.get(label)
            if explicit_language and explicit_language != chunk["lang"]:
                result["language_label_mismatches"].append(
                    {
                        "source_id": chunk["source_id"],
                        "title": chunk["title"],
                        "chunk_id": chunk["chunk_id"],
                        "label": label,
                        "lang": chunk["lang"],
                        "expected_from_source_tab": explicit_language,
                        "text_sample": chunk["text"][:180],
                    }
                )
            result["short_body_chunks_at_most_20_chars"] += len(chunk["text"].strip()) <= 20
            if re.search(r"\btemplate\b", chunk["title"], re.I) or re.search(
                r"\{\{|\[\[|<tabber>|English line [123]|日本語[一二三]|lorem ipsum", chunk["text"], re.I
            ):
                result["semantic_review_candidates"].append(
                    {
                        "source_id": chunk["source_id"],
                        "title": chunk["title"],
                        "chunk_id": chunk["chunk_id"],
                        "lang": chunk["lang"],
                        "text_sample": chunk["text"][:350],
                        "reason": "template_title_or_markup_or_placeholder_candidate_not_automatic_exclusion",
                    }
                )
            for key in fields:
                result["chunk_nonempty_metadata"][key] += chunk.get(key) is not None and chunk.get(key) != ""
    for name in ["content_clean_all.csv", "review.csv", "images.csv"]:
        seen, labels, empty = set(), Counter(), Counter()
        n = malformed = duplicates = 0
        path = data / "clean_runs/s2-full-v2" / name
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                n += 1
                malformed += None in row or any(v is None for v in row.values())
                identity = row.get("record_id") or row.get("occurrence_id")
                duplicates += identity in seen
                seen.add(identity)
                if name == "content_clean_all.csv":
                    for key in ["url", "source_snapshot", "revision_id", "lang", "source_type", "fetched_at"]:
                        empty[key] += not row[key]
                    empty["unicode_replacement_text"] += "\ufffd" in row["text"]
                if name == "review.csv" and row["reason"] == "infobox_numeric_or_production_field":
                    labels[row["text"].split("\n")[0].split(":")[0]] += 1
            result["csv_schema"][name] = {
                "rows": n,
                "columns": len(reader.fieldnames),
                "malformed": malformed,
                "duplicate_ids": duplicates,
            }
        if empty:
            result["clean_null_counts"] = dict(empty)
        if labels:
            result["removed_field_labels"] = dict(labels.most_common())
    (output / "metadata-check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def audit(data, output, tokenizer_path):
    if output.exists():
        raise ValueError("Use a new output directory")
    clean = data / "clean_runs/s2-full-v2"
    chunk = data / "chunk_runs/s2-full-v1"
    crawl = data / "crawl_runs/s2-full-20261028"
    manifest = read(clean / "manifest.json")
    report = read(clean / "report.json")
    chunk_report = preflight(chunk)  # Actual full validation, no database connection.
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    if digest(tokenizer_path) != chunk_report["tokenizer_sha256"]:
        raise ValueError("Tokenizer does not match delivered run")
    output.mkdir(parents=True)
    counts, issues = Counter(), []
    languages, types, releases = Counter(), Counter(), Counter()
    fields, reasons, reason_pages = Counter(), Counter(), defaultdict(set)
    family_pages, family_fields = Counter(), defaultdict(Counter)
    input_files = {}
    for fp in [clean / "input-fingerprints.json", chunk / "input-fingerprints.json"]:
        for name, expected in read(fp).items():
            path = Path(name)
            if not path.exists() or digest(path) != expected:
                issues.append({"kind": "input_fingerprint_mismatch", "path": name})
            else:
                counts["input_fingerprints_verified"] += 1
            if path.exists():
                input_files[name] = (path.stat().st_size, path.stat().st_mtime_ns)
    for name, info in report["csv_validation"].items():
        if digest(clean / name) != info["sha256"]:
            issues.append({"kind": "clean_csv_checksum_mismatch", "path": name})
    rows = {}
    clean_ids = set()
    for row in csv_rows(clean / "content_clean_all.csv"):
        counts["clean_records"] += 1
        if row["record_id"] in rows or None in row:
            issues.append({"kind": "clean_duplicate_or_malformed", "id": row["record_id"]})
        rows[row["record_id"]] = row
        clean_ids.add(row["source_id"])
        counts["clean_" + row["decision"]] += 1
        counts["clean_eligible"] += row["chunk_eligible"] == "True"
    for row in csv_rows(clean / "review.csv"):
        reasons[row["reason"]] += 1
        reason_pages[row["reason"]].add(row["source_id"])
    chunk_counts = Counter()
    observed_chunk_ids = set()
    image_ids_by_page = defaultdict(set)
    image_occurrences = Counter()
    blob_paths = {}
    for row in csv_rows(clean / "images.csv"):
        counts["image_occurrences"] += 1
        image_occurrences[row["media_status"]] += 1
        counts["images_license_unknown"] += row["license_status"] == "unknown_review_required"
        counts["images_empty_caption"] += not row["caption"]
        if row["image_id"]:
            image_ids_by_page[row["source_id"]].add(row["image_id"])
            blob_paths[row["local_path"]] = row["image_id"]
    for index, (name, expected) in enumerate(blob_paths.items(), 1):
        path = Path(name)
        if not path.is_file() or digest(path) != expected:
            issues.append({"kind": "image_blob_missing_or_corrupt", "path": name})
        else:
            counts["unique_image_blobs_verified"] += 1
        if index % 2000 == 0:
            print(f"MEDIA {index}/{len(blob_paths)}", flush=True)
    expected_ids = {str(p["id"]) for p in manifest["pages"]}
    title_by_id = {}
    with (output / "pages.jsonl").open("w", encoding="utf-8") as stream:
        for index, page in enumerate(manifest["pages"], 1):
            sid = str(page["id"])
            doc = read(clean / "processed/wikigg" / (sid + ".json"))
            title_by_id[sid] = doc["title"]
            raw = read(Path(doc["source_snapshot"]))
            counts["pages"] += 1
            if str(document_id(doc["source"], sid)) != doc["doc_id"]:
                issues.append({"kind": "doc_identity", "source_id": sid})
            soup = BeautifulSoup(raw["content"], "html.parser")
            body = soup.select_one(".mw-parser-output, #page-content, main")
            if body is None:
                issues.append({"kind": "missing_article_body", "source_id": sid})
                body = soup
            raw_fields = []
            for node in body.select(".pi-data"):
                label = node.select_one(".pi-data-label")
                value = node.select_one(".pi-data-value")
                key = node.get("data-source") or node.get("data-item-name") or "unknown"
                if value:
                    item = {
                        "key": key,
                        "label": label.get_text(" ", strip=True) if label else key,
                        "value": normalized(value.get_text(" ", strip=True)),
                    }
                    raw_fields.append(item)
                    fields[key] += 1
            family = next((x["value"] for x in raw_fields if x["key"] == "type"), "no_type_field")
            family_pages[family] += 1
            family_fields[family].update(set(x["key"] for x in raw_fields))
            tables = [
                t
                for t in body.select("table")
                if not t.find_parent(class_="navbox") and "navbox" not in t.get("class", [])
            ]
            stat_tables = [
                t
                for t in tables
                if re.search(
                    r"Attack Power|Damage Negation|Attribute Required|STR Scaling|Flask Charges|FP Cost",
                    t.get_text(" ", strip=True),
                    re.I,
                )
            ]
            counts["raw_non_nav_tables"] += len(tables)
            counts["raw_stat_table_candidates"] += len(stat_tables)
            counts["pages_with_stat_table_candidates"] += bool(stat_tables)
            counts["raw_tables_with_spans"] += sum(bool(t.select("[rowspan],[colspan]")) for t in tables)
            headings = [
                normalized(h.get_text(" ", strip=True)).replace("[ edit ]", "").strip()
                for h in body.select("h2,h3,h4")
                if not h.find_parent("aside")
            ]
            sections = {s["record_id"]: s for s in doc["sections"]}
            counts["source_updated_at_null"] += doc.get("source_updated_at") is None
            kept_text = normalized(" ".join(s["text"] for s in sections.values() if s["chunk_eligible"]))
            for section in sections.values():
                row = rows.get(section["record_id"])
                if not row or any(
                    row[k] != str(section[k])
                    for k in ["text", "section", "decision", "lang", "source_type", "chunk_eligible"]
                ):
                    issues.append({"kind": "csv_processed_mismatch", "source_id": sid, "record": section["record_id"]})
                if row and json.loads(row["image_ids"]) != list(dict.fromkeys(section["image_ids"])):
                    issues.append({"kind": "csv_image_mismatch", "source_id": sid})
                if not set(section["image_ids"]) <= image_ids_by_page[sid]:
                    issues.append({"kind": "section_image_unresolved", "source_id": sid})
                if not section.get("anchor"):
                    counts["sections_without_anchor"] += 1
            units = {}
            covered = defaultdict(list)
            for section in sections.values():
                if section["chunk_eligible"]:
                    for unit in prepare_units(doc, section, tokenizer, 450):
                        units[(section["record_id"], unit["unit_key"])] = unit
            chunk_texts = []
            with (chunk / "wikigg" / (sid + ".jsonl")).open(encoding="utf-8") as source:
                for ordinal, line in enumerate(source):
                    c = json.loads(line)
                    counts["chunks"] += 1
                    chunk_counts[sid] += 1
                    languages[c["lang"]] += 1
                    types[c["source_type"]] += 1
                    releases[c["release_scope"]] += 1
                    counts["chunks_dialogue"] += c["unit_kind"] == "dialogue"
                    counts["chunks_speaker_null"] += c["unit_kind"] == "dialogue" and c.get("speaker") is None
                    counts["chunks_trigger_null"] += c["unit_kind"] == "dialogue" and c.get("trigger") is None
                    counts["chunks_with_images"] += bool(c["image_ids"])
                    if c["chunk_id"] in observed_chunk_ids or c["chunk_id"] != str(
                        chunk_id(document_id(doc["source"], sid), ordinal)
                    ):
                        issues.append({"kind": "chunk_id", "source_id": sid})
                    observed_chunk_ids.add(c["chunk_id"])
                    key = (c["section_record_id"], c["unit_key"])
                    unit = units.get(key)
                    if unit is None or c["text"] != unit["text"][c["start_char"] : c["end_char"]]:
                        issues.append({"kind": "chunk_source_slice", "chunk_id": c["chunk_id"]})
                    else:
                        covered[key].append((c["start_char"], c["end_char"]))
                        if any(c.get(k) != unit.get(k) for k in ["speaker", "trigger"]):
                            issues.append({"kind": "dialogue_context", "chunk_id": c["chunk_id"]})
                    if not set(c["image_ids"]) <= set(sections[c["section_record_id"]]["image_ids"]):
                        issues.append({"kind": "chunk_image_context", "chunk_id": c["chunk_id"]})
                    encoded = len(tokenizer.encode(c["embedding_text"], add_special_tokens=True).ids)
                    if encoded != c["token_count"] or encoded > 450:
                        issues.append({"kind": "token_budget", "chunk_id": c["chunk_id"]})
                    counts["max_chunk_tokens"] = max(counts["max_chunk_tokens"], encoded)
                    chunk_texts.append(c["text"])
            for key, unit in units.items():
                end = 0
                for left, right in sorted(covered[key]):
                    if left > end:
                        issues.append({"kind": "coverage_gap", "source_id": sid, "unit": key})
                    end = max(end, right)
                if end != len(unit["text"]):
                    issues.append({"kind": "coverage_incomplete", "source_id": sid, "unit": key})
                counts["eligible_units_checked"] += 1
            chunk_text = normalized(" ".join(chunk_texts))
            for field in raw_fields:
                # Diagnostic only: short numeric values can match unrelated prose.
                field["value_substring_in_eligible_clean"] = field["value"] in kept_text
                field["value_substring_in_chunks"] = field["value"] in chunk_text
            stream.write(
                json.dumps(
                    {
                        "source_id": sid,
                        "title": doc["title"],
                        "family": family,
                        "raw_snapshot": doc["source_snapshot"],
                        "raw_fields": raw_fields,
                        "headings": headings,
                        "table_count": len(tables),
                        "stat_table_candidates": len(stat_tables),
                        "clean_records": len(sections),
                        "eligible_records": sum(s["chunk_eligible"] for s in sections.values()),
                        "chunks": chunk_counts[sid],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            if index % 200 == 0:
                print(f"PAGES {index}/{len(manifest['pages'])}", flush=True)
    for name, old_stat in input_files.items():
        path = Path(name)
        if (path.stat().st_size, path.stat().st_mtime_ns) != old_stat:
            issues.append({"kind": "input_changed_during_audit", "path": name})
    inventory = read(crawl / "inventory.json")
    crawl_report = read(crawl / "report.json")
    other_artifacts = {}
    for name in ["clean_runs", "chunk_runs", "crawl_runs", "research_runs", "raw", "media"]:
        paths = [p for p in (data / name).rglob("*") if p.is_file()]
        other_artifacts[name] = {"files": len(paths), "bytes": sum(p.stat().st_size for p in paths)}
    result = {
        "created_at": datetime.now(UTC).isoformat(),
        "scope": "All delivered 4164 pages, base + SotE; local artifacts only, not a live wiki census",
        "counts": dict(counts),
        "issues": issues,
        "cohort": {
            "inventory": len(inventory["pages"]),
            "categories": len(inventory["visited"]),
            "inventory_pending": len(inventory["pending"]),
            "clean_ids": len(clean_ids),
            "missing_clean_ids": sorted(expected_ids - clean_ids),
            "missing_chunk_ids": sorted(expected_ids - set(chunk_counts)),
            "unaccounted_inventory": sorted(
                set(inventory["pages"]) - expected_ids - {str(p["id"]) for p in crawl_report["excluded"]}
            ),
            "excluded": crawl_report["excluded"],
            "media_errors": crawl_report["errors"],
        },
        "languages": dict(languages),
        "source_types": dict(types),
        "release_labels": dict(releases),
        "raw_infobox_fields": dict(fields.most_common()),
        "family_pages": dict(family_pages.most_common()),
        "family_field_page_counts": {k: dict(v) for k, v in family_fields.items()},
        "review_reasons": {k: {"rows": v, "pages": len(reason_pages[k])} for k, v in reasons.most_common()},
        "image_occurrence_status": dict(image_occurrences),
        "folder_inventory": other_artifacts,
        "limitations": [
            "Structural/token/hash checks do not prove semantic completeness or correct wiki values.",
            "Infobox substring diagnostics do not prove a retained value has the correct label or context.",
            "Stat table recognition is a keyword heuristic, not all gameplay tables.",
            "No live website, database, vector index, OCR, embedding or AI API was queried.",
            "Historical/trial folders inventoried, not treated as accepted corpus or revalidated as production.",
            "Input fingerprints checked against saved baseline; size/mtime checked again at end.",
        ],
    }
    (output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({"counts": dict(counts), "issues": len(issues), "output": str(output)}, ensure_ascii=False),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    args = parser.parse_args()
    audit(args.data_dir.resolve(), args.output_dir.resolve(), args.tokenizer.resolve())
    metadata_audit(args.data_dir.resolve(), args.output_dir.resolve())
