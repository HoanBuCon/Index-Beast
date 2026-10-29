"""Full S2 clean artifact -> streamed, provenance-checked chunks. No encoder or network."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from tokenizers import Tokenizer

from core.ids import chunk_id, document_id
from core.text.chunking import chunk_section, prepare_units
from ingest.artifacts import now, read, save, sha256

VERSION = "s2-full-chunk-1.0"


def build_chunks(doc, tokenizer, cap=450, overlap=50):
    identity = document_id(doc["source"], doc["source_id"])
    if str(identity) != doc["doc_id"] or doc["game_scope"] != "elden_ring":
        raise ValueError("Document identity/scope mismatch")
    chunks, reviews, coverage = [], [], []
    for section in doc["sections"]:
        if not section["chunk_eligible"]:
            reviews.append(
                {
                    "section_record_id": section["record_id"],
                    "section": section["section"],
                    "reason": section["reason"],
                    "text": section["text"],
                }
            )
            continue
        units = {u["unit_key"]: u for u in prepare_units(doc, section, tokenizer, cap)}
        result = chunk_section(doc, section, tokenizer, cap, overlap)
        for item in result["chunks"]:
            unit = units[item["unit_key"]]
            if item["text"] != unit["text"][item["start_char"] : item["end_char"]]:
                raise ValueError("Source coverage mismatch")
            if item["token_count"] != len(tokenizer.encode(item["embedding_text"], add_special_tokens=True).ids):
                raise ValueError("Token count mismatch")
            if item["token_count"] > cap:
                raise ValueError("Token cap exceeded")
            item.pop("source_text_hash_input")
            ordinal = len(chunks)
            anchor = section.get("anchor") or ""
            chunks.append(
                dict(
                    item,
                    chunk_id=str(chunk_id(identity, ordinal)),
                    ordinal=ordinal,
                    doc_id=str(identity),
                    source_id=doc["source_id"],
                    source=doc["source"],
                    title=doc["title"],
                    section=section["section"],
                    section_record_id=section["record_id"],
                    section_anchor=anchor,
                    variant_context=section.get("variant_context"),
                    url=doc["url"] + ("#" + quote(anchor, safe="_-") if anchor else ""),
                    revision_id=doc["revision_id"],
                    source_snapshot=doc["source_snapshot"],
                    game_scope="elden_ring",
                    release_scope=section["release_scope"],
                    source_type=section["source_type"],
                    source_type_evidence=section.get("source_type_evidence"),
                    image_ids=list(dict.fromkeys(section["image_ids"])),
                    image_association="section",
                    fetched_at=doc["fetched_at"],
                    source_updated_at=doc.get("source_updated_at"),
                    text_hash=sha256(item["text"].encode()),
                    cleaning_version=doc["cleaning_version"],
                    chunking_version=VERSION,
                )
            )
        reviews.extend(
            dict(r, section_record_id=section["record_id"], section=section["section"]) for r in result["reviews"]
        )
        coverage.extend(dict(c, section_record_id=section["record_id"]) for c in result["coverage"])
    return chunks, reviews, coverage


def run(input_dir, tokenizer_path, output, cap=450, overlap=50):
    if output.exists():
        raise ValueError("Use a new output directory")
    report = read(input_dir / "report.json")
    if report["cleaning_version"] != "s2-full-clean-1.0":
        raise ValueError("Full clean version required")
    for name, info in report["csv_validation"].items():
        if sha256((input_dir / name).read_bytes()) != info["sha256"]:
            raise ValueError("Clean CSV checksum mismatch")
    with (input_dir / "content_clean_all.csv").open(encoding="utf-8-sig", newline="") as stream:
        clean_rows = {r["record_id"]: r for r in csv.DictReader(stream)}
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    output.mkdir(parents=True)
    fingerprints = {str((input_dir / "report.json").resolve()): sha256((input_dir / "report.json").read_bytes())}
    logical = hashlib.sha256()
    stats = {
        "pages": 0,
        "chunks": 0,
        "review_sections_or_units": 0,
        "units": 0,
        "covered_units": 0,
        "pages_without_chunks": 0,
        "max_tokens": 0,
    }
    languages = {}
    types = {}
    created = now()
    columns = [
        "chunk_id",
        "doc_id",
        "source_id",
        "title",
        "section",
        "text",
        "embedding_text",
        "token_count",
        "url",
        "revision_id",
        "game_scope",
        "release_scope",
        "source_type",
        "lang",
        "image_ids",
        "source_snapshot",
        "cleaning_version",
        "chunking_version",
    ]
    with (
        (output / "chunks.jsonl").open("w", encoding="utf-8") as all_chunks,
        (output / "review.jsonl").open("w", encoding="utf-8") as all_review,
        (output / "coverage.jsonl").open("w", encoding="utf-8") as all_coverage,
        (output / "documents.jsonl").open("w", encoding="utf-8") as documents,
        (output / "chunks.csv").open("w", encoding="utf-8-sig", newline="") as csv_stream,
    ):
        writer = csv.DictWriter(csv_stream, fieldnames=columns, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for page in report["input_pages"]:
            path = input_dir / "processed" / "wikigg" / (page["id"] + ".json")
            doc = read(path)
            fingerprints[str(path.resolve())] = sha256(path.read_bytes())
            if doc["source_id"] != page["id"] or doc["revision_id"] != page["revision_id"]:
                raise ValueError("Input cohort mismatch")
            for s in doc["sections"]:
                row = clean_rows[s["record_id"]]
                if any(
                    row[k] != str(s[k])
                    for k in ["section", "text", "lang", "source_type", "decision", "chunk_eligible"]
                ):
                    raise ValueError("Processed content differs from CSV")
                if json.loads(row["image_ids"]) != list(dict.fromkeys(s["image_ids"])):
                    raise ValueError("Image association mismatch")
            chunks, reviews, coverage = build_chunks(doc, tokenizer, cap, overlap)
            folder = output / "wikigg"
            folder.mkdir(exist_ok=True)
            with (folder / (page["id"] + ".jsonl")).open("w", encoding="utf-8") as per_doc:
                for c in chunks:
                    c["updated_at"] = created
                    encoded = json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n"
                    all_chunks.write(encoded)
                    per_doc.write(encoded)
                    logical.update(
                        json.dumps(
                            {k: v for k, v in c.items() if k != "updated_at"}, sort_keys=True, ensure_ascii=False
                        ).encode()
                    )
                    writer.writerow(
                        {k: json.dumps(c[k], ensure_ascii=False) if k == "image_ids" else c[k] for k in columns}
                    )
                    stats["max_tokens"] = max(stats["max_tokens"], c["token_count"])
                    languages[c["lang"]] = languages.get(c["lang"], 0) + 1
                    types[c["source_type"]] = types.get(c["source_type"], 0) + 1
            for r in reviews:
                all_review.write(
                    json.dumps(dict(r, source_id=page["id"], title=doc["title"]), ensure_ascii=False) + "\n"
                )
            for c in coverage:
                all_coverage.write(json.dumps(dict(c, source_id=page["id"]), ensure_ascii=False) + "\n")
            documents.write(
                json.dumps({k: v for k, v in doc.items() if k not in {"sections"}}, ensure_ascii=False) + "\n"
            )
            stats["pages"] += 1
            stats["chunks"] += len(chunks)
            stats["review_sections_or_units"] += len(reviews)
            stats["units"] += len(coverage)
            stats["covered_units"] += sum(c["status"] == "covered" for c in coverage)
            stats["pages_without_chunks"] += not chunks
            if stats["pages"] % 100 == 0:
                print(f"CHUNK {stats['pages']}/{len(report['input_pages'])}", flush=True)
    with (
        (output / "chunks.csv").open(encoding="utf-8-sig", newline="") as stream,
        (output / "chunks.jsonl").open(encoding="utf-8") as source,
    ):
        n = 0
        for row, line in __import__("itertools").zip_longest(csv.DictReader(stream), source):
            if row is None or line is None:
                raise ValueError("CSV row count mismatch")
            c = json.loads(line)
            if (
                row["text"] != c["text"]
                or row["embedding_text"] != c["embedding_text"]
                or json.loads(row["image_ids"]) != c["image_ids"]
            ):
                raise ValueError("CSV round-trip mismatch")
            n += 1
        if n != stats["chunks"]:
            raise ValueError("CSV count mismatch")
    if any(sha256(Path(p).read_bytes()) != h for p, h in fingerprints.items()):
        raise ValueError("Input changed")
    result = {
        "created_at": created,
        "chunking_version": VERSION,
        "clean_input": str(input_dir.resolve()),
        "source_job": report["source_job"],
        "game_scope": "elden_ring",
        "counts": stats,
        "languages": languages,
        "source_types": types,
        "max_tokens": cap,
        "overlap_tokens": overlap,
        "tokenizer_sha256": sha256(tokenizer_path.read_bytes()),
        "logical_content_sha256": logical.hexdigest(),
        "input_unchanged": True,
        "csv_roundtrip_verified": True,
        "artifact_sha256": {
            n: sha256((output / n).read_bytes())
            for n in ["chunks.jsonl", "chunks.csv", "documents.jsonl", "review.jsonl", "coverage.jsonl"]
        },
        "network_calls": 0,
        "encoder_calls": 0,
        "database_writes": 0,
    }
    save(output / "input-fingerprints.json", fingerprints)
    save(output / "report.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", type=Path, required=True)
    p.add_argument("--tokenizer", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.input_dir, a.tokenizer, a.output_dir)["counts"]))


if __name__ == "__main__":
    main()
