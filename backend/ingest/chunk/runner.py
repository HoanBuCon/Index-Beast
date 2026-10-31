"""Offline chunk artifacts. Consumes clean v2, never runs embedding or writes DB/vector."""

import csv
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from tokenizers import Tokenizer

from core.ids import chunk_id, document_id
from core.text.chunking import chunk_section
from ingest.artifacts import now, read, save, sha256
from ingest.transform.document import stable_id


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def run_chunk(input_dir, tokenizer_path, output_dir, *, cap=450, overlap=50):
    if output_dir.resolve().is_relative_to(input_dir.resolve()):
        raise ValueError("Chunk output must be separate from clean input")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output directory must be new or empty")
    if not tokenizer_path.is_file():
        raise ValueError("Provide a local tokenizer.json; no automatic downloads")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    report = read(input_dir / "report.json")
    if report["cleaning_version"] not in {"s2-clean-2.0", "s2-clean-2.1"}:
        raise ValueError("Run clean v2 to recover typed dialogue/anchors first")
    for name, info in report["csv_validation"].items():
        if sha256((input_dir / name).read_bytes()) != info["sha256"]:
            raise ValueError("Clean artifact checksum mismatch")
    signature = sha256(
        json.dumps(
            {
                "cap": cap,
                "overlap": overlap,
                "tokenizer": sha256(tokenizer_path.read_bytes()),
                "version": "s2-chunk-1.0",
            },
            sort_keys=True,
        ).encode()
    )
    chunks = []
    reviews = []
    coverage = []
    source_hashes = {}
    counts = Counter()
    updated_at = now()
    for page in report["input_pages"]:
        path = input_dir / "processed/wikigg" / (page["id"] + ".json")
        doc = read(path)
        doc["doc_id"] = str(document_id(doc["source"], doc["source_id"]))
        source_hashes[str(path)] = sha256(path.read_bytes())
        per_doc = []
        for section in doc["sections"]:
            counts["sections_" + section["scope_status"]] += 1
            if section["scope_status"] != "base":
                continue
            result = chunk_section(doc, section, tokenizer, cap, overlap)
            for item in result["chunks"]:
                source_text = item.pop("source_text_hash_input")
                unit_id = stable_id(section["record_id"], item["unit_key"])
                identity = stable_id(
                    unit_id, item["start_char"], item["end_char"], signature, sha256(source_text.encode())
                )
                source_type = "in_game_text" if item["unit_kind"] == "dialogue" else section["source_type"]
                anchor = section.get("anchor") or ""
                record = dict(
                    item,
                    chunk_id=str(chunk_id(document_id(doc["source"], doc["source_id"]), len(per_doc))),
                    artifact_content_id=identity,
                    ordinal=len(per_doc),
                    unit_id=unit_id,
                    section_record_id=section["record_id"],
                    doc_id=doc["doc_id"],
                    source_id=doc["source_id"],
                    title=doc["title"],
                    section=section["section"],
                    variant_context=section.get("variant_context"),
                    section_anchor=anchor,
                    url=doc["url"] + ("#" + quote(anchor, safe="_-") if anchor else ""),
                    source=doc["source"],
                    revision_id=doc["revision_id"],
                    source_snapshot=doc["source_snapshot"],
                    game_scope="base",
                    source_type=source_type,
                    image_ids=section["image_ids"],
                    image_association="section",
                    fetched_at=doc["fetched_at"],
                    source_updated_at=doc.get("source_updated_at"),
                    updated_at=updated_at,
                    updated_at_semantics="chunk_artifact_generation_time",
                    processed_at=report["created_at"],
                    cleaning_version=doc["cleaning_version"],
                    chunking_version="s2-chunk-1.0",
                    text_hash=sha256(item["text"].encode()),
                )
                chunks.append(record)
                per_doc.append(record)
            reviews.extend(
                dict(r, title=doc["title"], section_record_id=section["record_id"]) for r in result["reviews"]
            )
            coverage.extend(dict(c, section_record_id=section["record_id"]) for c in result["coverage"])
        write_jsonl(output_dir / "wikigg" / (doc["source_id"] + ".jsonl"), per_doc)
    if len({c["chunk_id"] for c in chunks}) != len(chunks):
        raise ValueError("Duplicate chunk IDs")
    if any(c["token_count"] > cap for c in chunks):
        raise ValueError("Token budget exceeded")
    for path, digest in source_hashes.items():
        if sha256(Path(path).read_bytes()) != digest:
            raise ValueError("Processed input changed")
    write_jsonl(output_dir / "chunks.jsonl", chunks)
    write_jsonl(output_dir / "review.jsonl", reviews)
    columns = [
        "chunk_id",
        "doc_id",
        "section_record_id",
        "title",
        "section",
        "lang",
        "trigger",
        "speaker",
        "text",
        "embedding_text",
        "token_count",
        "url",
        "source_id",
        "revision_id",
        "game_scope",
        "source_type",
        "image_ids",
        "source_updated_at",
        "updated_at",
    ]
    with (output_dir / "chunks.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for c in chunks:
            writer.writerow({k: json.dumps(c[k], ensure_ascii=False) if k == "image_ids" else c[k] for k in columns})
    with (output_dir / "chunks.csv").open(encoding="utf-8-sig", newline="") as stream:
        exported = list(csv.DictReader(stream))
    if len(exported) != len(chunks):
        raise ValueError("CSV row count changed")
    for row, record in zip(exported, chunks, strict=True):
        if row["text"] != record["text"] or row["embedding_text"] != record["embedding_text"]:
            raise ValueError("Chunk CSV round-trip changed source text")
    summary = {
        "created_at": updated_at,
        "status": "completed_with_review" if reviews else "completed",
        "source_job": report["source_job"],
        "clean_input": str(input_dir.resolve()),
        "max_tokens": cap,
        "overlap_tokens": overlap,
        "tokenizer_sha256": sha256(tokenizer_path.read_bytes()),
        "signature": signature,
        "counts": dict(counts),
        "chunks": len(chunks),
        "csv_roundtrip_verified": True,
        "artifact_sha256": {n: sha256((output_dir / n).read_bytes()) for n in ("chunks.jsonl", "chunks.csv")},
        "units": len(coverage),
        "covered_units": sum(c["status"] == "covered" for c in coverage),
        "review_units": len(reviews),
        "max_observed_tokens": max((c["token_count"] for c in chunks), default=0),
        "chunks_by_language": dict(Counter(c["lang"] for c in chunks)),
        "dialogue_chunks": sum(c["unit_kind"] == "dialogue" for c in chunks),
        "units_with_trigger": sum(c.get("trigger_repeated_in_context", False) for c in coverage),
        "chunks_with_variant": sum(bool(c["variant_context"]) for c in chunks),
        "input_unchanged": True,
        "network_calls": 0,
        "encoder_calls": 0,
        "database_writes": 0,
        "logical_content_sha256": sha256(
            json.dumps(
                [{k: v for k, v in c.items() if k != "updated_at"} for c in chunks], ensure_ascii=False, sort_keys=True
            ).encode()
        ),
        "limitations": [
            "base scope is heuristic; review/excluded sections are not chunked",
            "speaker remains null unless source explicitly supplies it",
            "source_updated_at remains unknown; updated_at is artifact time, not source edit time",
            "image association remains section-level; no image embedding/retrieval",
            "token/coverage validation does not measure retrieval quality",
        ],
    }
    save(output_dir / "report.json", summary)
    save(output_dir / "coverage.json", coverage)
    return summary
