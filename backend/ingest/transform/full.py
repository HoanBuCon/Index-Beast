"""Offline full text corpus clean: S2 base+SotE policy, media failures stay separate."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from core.ids import document_id
from core.text.html_clean import clean_html
from core.text.lore_policy import block_decision, block_metadata, context_groups
from ingest.artifacts import now, read, save, sha256
from ingest.filter.rules import page_evidence
from ingest.settings import load_settings
from ingest.transform.document import csv_write, inside, stable_id

VERSION = "s2-full-clean-1.1"
SAMPLE = [
    "Elden Remembrance",
    "Scadutree Fragment",
    "Black Leather Shield",
    "Fire Grease",
    "Ranni the Witch",
    "Patches",
    "Alexander, Warrior Jar",
    "Melina",
    "Messmer the Impaler",
    "Rellana, Twin Moon Knight",
    "Sir Ansbach",
    "Redmane Freyja",
    "Erdtree",
    "Queen Marika the Eternal",
    "Starscourge Radahn",
    "Godwyn the Golden",
    "Great Épée",
    "Liurnia of the Lakes",
    "Malenia, Blade of Miquella",
    "About Stance-Breaking",
]
HEADERS = [
    "record_id",
    "doc_id",
    "source_id",
    "title",
    "section",
    "text",
    "url",
    "source",
    "revision_id",
    "fetched_at",
    "game_scope",
    "release_scope",
    "source_type",
    "lang",
    "image_ids",
    "source_snapshot",
    "content_hash",
    "cleaning_version",
    "decision",
    "reason",
    "location",
    "chunk_eligible",
]


def run(run_dir, output, limit=None):
    config = load_settings()
    root = config["data_dir"]
    if output.exists():
        raise ValueError("Use a new output directory")
    crawl = read(run_dir / "report.json")
    if not crawl.get("finished_at") or crawl["status"] not in {"completed", "partial"}:
        raise ValueError("Crawl must have finished")
    cohort = read(run_dir / "checkpoint.json")
    cohort.update({p["id"]: p for p in crawl["pages"]})
    pages = sorted(cohort.values(), key=lambda p: int(p["id"]))
    if limit == 20:
        lookup = {p["title"]: p for p in pages}
        pages = [lookup[t] for t in SAMPLE]
    elif limit:
        pages = pages[:limit]
    output.mkdir(parents=True)
    inputs = {str(p.resolve()): sha256(p.read_bytes()) for p in [run_dir / "report.json", run_dir / "checkpoint.json"]}
    entries, counts, reasons, media_counts = [], Counter(), Counter(), Counter()
    image_hashes = {}
    manifest = {
        "created_at": now(),
        "source_job": crawl["job_id"],
        "source_run": str(run_dir.resolve()),
        "game_scope": "elden_ring",
        "allowed_releases": ["base", "sote"],
        "release_unknown_allowed": True,
        "text_pages": len(pages),
        "source_crawl_status": crawl["status"],
        "pages": pages,
    }
    save(output / "manifest.json", manifest)
    rows, reviews, images, examples = [], [], [], []
    for ordinal, page in enumerate(pages):
        row_start = len(rows)
        path = inside(root, page["path"])
        raw = read(path)
        if str(raw["source_id"]) != page["id"] or raw["revision_id"] != page["revision_id"]:
            raise ValueError("Raw cohort identity mismatch")
        if sha256(raw["content"].encode()) != raw["content_hash"]:
            raise ValueError("Raw hash mismatch")
        inputs[str(path)] = sha256(path.read_bytes())
        # Filter artifact precedes metadata transformation; scope never drops SotE.
        parsed = clean_html(
            raw["content"], title=raw["title"], skip_sections=config["clean"]["skip_sections"], capture_context=True
        )
        evidence = page_evidence(raw, config["clean"])
        release = (
            "sote_candidate"
            if evidence["status"] == "excluded"
            else (
                "mixed_or_sote_candidate"
                if evidence["reason"] == "mixed_or_dlc_page_context"
                else "base_candidate"
                if evidence["status"] == "base"
                else "unknown"
            )
        )
        filtered = {
            "source_id": page["id"],
            "revision_id": raw["revision_id"],
            "raw_hash": raw["content_hash"],
            "sections": parsed["sections"],
            "removed": parsed["removed"],
        }
        for s in filtered["sections"]:
            for b in s["blocks"]:
                b["decision"], b["reason"] = block_decision(s["section"], b)
        save(output / "filtered" / ("" + page["id"] + ".json"), filtered)
        filtered = read(output / "filtered" / (page["id"] + ".json"))
        doc_id = str(document_id(raw["source"], page["id"]))
        sections = []
        for s in filtered["sections"]:
            # One context/type/language run per processed section; retain all non-excluded blocks.
            for index, blocks in enumerate(context_groups(s, parsed["html_lang"])):
                b = blocks[0]
                text = "\n".join(block["text"] for block in blocks)
                decision, reason = b["decision"], b["reason"]
                counts["blocks_" + decision] += len(blocks)
                reasons[reason] += 1
                meta = block_metadata(b, parsed["html_lang"])
                variant = b.get("variant_context") or s.get("variant_context")
                section = dict(
                    s,
                    blocks=blocks,
                    text=text,
                    **meta,
                    variant_context=variant,
                    scope_status="in_scope",
                    game_scope="elden_ring",
                    release_scope=release,
                    decision=decision,
                    reason=reason,
                    chunk_eligible=decision == "keep",
                    image_ids=[],
                )
                section["anchor"] = (variant or {}).get("anchor") or s.get("anchor") or ""
                section["record_id"] = stable_id(doc_id, s["location"], index, b["location"], VERSION)
                record = {
                    "record_id": section["record_id"],
                    "doc_id": doc_id,
                    "source_id": page["id"],
                    "title": raw["title"],
                    "section": s["section"],
                    "text": text,
                    "url": raw["url"],
                    "source": raw["source"],
                    "revision_id": raw["revision_id"],
                    "fetched_at": raw["fetched_at"],
                    "game_scope": "elden_ring",
                    "release_scope": release,
                    "source_type": meta["source_type"],
                    "lang": meta["lang"],
                    "image_ids": "[]",
                    "source_snapshot": str(path),
                    "content_hash": sha256(text.encode()),
                    "cleaning_version": VERSION,
                    "decision": decision,
                    "reason": reason,
                    "location": b["location"],
                    "chunk_eligible": decision == "keep",
                }
                if decision != "excluded":
                    sections.append(section)
                    rows.append(record)
                if decision != "keep":
                    reviews.append(record)
        for removed in filtered["removed"]:
            reviews.append(
                dict.fromkeys(HEADERS, "")
                | {
                    "record_id": stable_id(doc_id, removed["location"], removed["reason"]),
                    "doc_id": doc_id,
                    "source_id": page["id"],
                    "title": raw["title"],
                    "section": removed["section"],
                    "text": removed["text"],
                    "decision": "excluded",
                    "reason": removed["reason"],
                    "location": removed["location"],
                    "source_snapshot": str(path),
                    "revision_id": raw["revision_id"],
                    "chunk_eligible": False,
                }
            )
            counts["removed_nodes"] += 1
            reasons[removed["reason"]] += 1
        mp = inside(
            root,
            page.get("media_manifest", str((run_dir / "media" / (page["id"] + ".json")).resolve().relative_to(root))),
        )
        media = read(mp)
        if media["revision_id"] != raw["revision_id"] or media["source_id"] != page["id"]:
            raise ValueError("Media provenance mismatch")
        inputs[str(mp)] = sha256(mp.read_bytes())
        names = defaultdict(set)
        for s in sections:
            names[s["section"]].add(s["location"])
        for image in media["images"]:
            name = __import__("re").sub(r"\s*\[\s*edit\s*\]", "", image["section"], flags=__import__("re").I).strip()
            local = ""
            if image.get("path") and image["status"] in {"downloaded", "cached"}:
                file = inside(root, image["path"])
                digest = image["image_id"]
                if digest not in image_hashes:
                    image_hashes[digest] = sha256(file.read_bytes())
                if image_hashes[digest] != digest:
                    raise ValueError("Image checksum mismatch")
                local = str(file)
            association = "exact_section" if local and len(names[name]) == 1 else "review"
            if image["status"] == "excluded":
                association = "excluded_ui"
            media_counts[image["status"]] += 1
            images.append(
                {
                    "occurrence_id": stable_id(doc_id, raw["revision_id"], image["occurrence_id"]),
                    "source_id": page["id"],
                    "revision_id": raw["revision_id"],
                    "section": name,
                    "image_id": image.get("image_id", ""),
                    "local_path": local,
                    "caption": image.get("caption", ""),
                    "alt": image.get("alt", ""),
                    "source_url": image.get("source_url", image.get("display_url", "")),
                    "description_url": image.get("description_url") or "",
                    "license": image.get("license") or "",
                    "license_status": image.get("license_status", "unknown_review_required"),
                    "association": association,
                    "media_status": image["status"],
                }
            )
            if association == "exact_section":
                for s in sections:
                    if s["section"] == name and s["chunk_eligible"]:
                        s["image_ids"].append(image["image_id"])
        mapping = {s["record_id"]: list(dict.fromkeys(s["image_ids"])) for s in sections}
        for row in rows[row_start:]:
            if row["source_id"] == page["id"]:
                row["image_ids"] = json.dumps(mapping.get(row["record_id"], []), ensure_ascii=False)
        doc = {
            "doc_id": doc_id,
            "source_id": page["id"],
            "source": raw["source"],
            "title": raw["title"],
            "url": raw["url"],
            "revision_id": raw["revision_id"],
            "fetched_at": raw["fetched_at"],
            "source_updated_at": None,
            "source_snapshot": str(path),
            "raw_content_hash": raw["content_hash"],
            "game_scope": "elden_ring",
            "release_scope": release,
            "release_evidence": evidence,
            "sections": sections,
            "cleaning_version": VERSION,
        }
        save(output / "processed" / "wikigg" / (page["id"] + ".json"), doc)
        counts["pages_in"] += 1
        counts["pages_with_media_errors"] += media["status"] != "completed"
        counts["pages_without_eligible_blocks"] += not any(s["chunk_eligible"] for s in sections)
        entries.append({"id": page["id"], "title": raw["title"], "revision_id": raw["revision_id"]})
        if limit == 20:
            examples.append({"title": raw["title"], "snapshot": str(path), "sections": sections})
        if ordinal % 100 == 0:
            print(f"CLEAN {ordinal + 1}/{len(pages)} {raw['title']}", flush=True)
    expected = {"content_clean_all.csv": rows, "review.csv": reviews, "images.csv": images}
    import csv

    checks = {}
    for name, records in expected.items():
        headers = list(records[0]) if name == "images.csv" else HEADERS
        csv_write(output / name, headers, records)
        with (output / name).open(encoding="utf-8-sig", newline="") as stream:
            actual = list(csv.DictReader(stream))
        if actual != [{k: str(r.get(k, "")) for k in headers} for r in records]:
            raise ValueError("CSV round-trip mismatch")
        if len({r["occurrence_id" if name == "images.csv" else "record_id"] for r in records}) != len(records):
            raise ValueError("Duplicate artifact identity")
        checks[name] = {"rows": len(records), "sha256": sha256((output / name).read_bytes())}
    if any(sha256(Path(p).read_bytes()) != h for p, h in inputs.items()):
        raise ValueError("Input changed")
    report = {
        "created_at": now(),
        "cleaning_version": VERSION,
        "game_scope": "elden_ring",
        "scope_policy": "base+sote S2 approved",
        "source_job": crawl["job_id"],
        "input_pages": entries,
        "counts": dict(counts),
        "decision_reasons": dict(reasons),
        "media_counts": dict(media_counts),
        "csv_validation": checks,
        "input_artifacts_unchanged": True,
        "network_calls": 0,
        "encoder_calls": 0,
        "database_writes": 0,
    }
    save(output / "input-fingerprints.json", inputs)
    save(output / "report.json", report)
    if examples:
        save(output / "before-after-20.json", examples)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--limit", type=int)
    a = p.parse_args()
    print(json.dumps(run(a.run_dir.resolve(), a.output_dir.resolve(), a.limit)["counts"]))


if __name__ == "__main__":
    main()
