"""Offline raw -> decisions -> processed -> CSV, with reproducible provenance."""

import csv
import json
import re
import uuid
from collections import Counter, defaultdict
from pathlib import Path

from core.text.html_clean import VERSION
from ingest.artifacts import now, read, save, sha256
from ingest.filter.rules import filter_document, pattern
from ingest.transform.metadata import section_metadata

LORE = [
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
    "scope_status",
    "source_type",
    "lang",
    "image_ids",
    "source_snapshot",
    "content_hash",
    "cleaning_version",
]
REVIEW = ["record_id", "source_id", "title", "section", "decision", "reason", "text", "source_snapshot", "revision_id"]
IMAGES = [
    "occurrence_id",
    "source_id",
    "revision_id",
    "section",
    "image_id",
    "local_path",
    "caption",
    "alt",
    "source_url",
    "description_url",
    "license",
    "license_status",
    "scope_status",
]
SAMPLE_TITLES = [
    "Alexander, Warrior Jar",
    "Blaidd the Half-Wolf",
    "Fia, Deathbed Companion",
    "Gurranq, Beast Clergyman",
    "Blackguard Big Boggart",
    "Ancient Hero of Zamor",
    "Dragonlord Placidusax",
    "Caria Manor",
    "Altus Plateau",
    "Caelid",
    "Cave of Knowledge",
    '"Champion\'s Song" Painting',
    "Elden Remembrance",
    "Ancient Dragon Cult",
    "Blackflame",
    "Carian Royal Family",
    "Beasts",
    "Boc's Mother",
    "About Flask of Wondrous Physick",
    "About Stance-Breaking",
]


def stable_id(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "|".join(map(str, parts))))


def inside(root, path):
    value = (root / path).resolve()
    if not value.is_relative_to(root.resolve()):
        raise ValueError("Source path escapes data directory")
    return value


def select_sample(data_dir, crawl_report=None, *, full=False):
    if full and not crawl_report:
        raise ValueError("Full cleaning requires an explicit crawl report")
    if crawl_report:
        path = crawl_report
    else:
        candidates = []
        for p in (data_dir / "reports").glob("crawl-*.json"):
            r = read(p)
            if (
                r.get("target") == 200
                and r.get("counts", {}).get("successful") == 200
                and len(r.get("pages", [])) == 200
            ):
                candidates.append(p)
        if not candidates:
            raise ValueError("No 200-page sample report found; specify --crawl-report")
        path = max(candidates, key=lambda p: p.stat().st_mtime)
    job = read(path)
    pages = job.get("pages", [])
    if full:
        if not pages or len({str(x["id"]) for x in pages}) != len(pages):
            raise ValueError("Crawl report must contain distinct page IDs")
        if job.get("status") != "completed":
            raise ValueError("Full cleaning requires a completed crawl report")
    elif len(pages) != 200 or len({str(x["id"]) for x in pages}) != 200:
        raise ValueError("Sample report must identify exactly 200 distinct pages")
    return path, job


def csv_write(path, headers, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="raise", quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def verify_csv(output, expected):
    result = {}
    rows = {}
    for filename, headers in [("lore_clean.csv", LORE), ("review.csv", REVIEW), ("images.csv", IMAGES)]:
        with (output / filename).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != headers:
                raise ValueError("CSV header mismatch: " + filename)
            records = list(reader)
        if any(None in r or any(v is None for v in r.values()) for r in records):
            raise ValueError("Malformed CSV row")
        if records != [{k: str(r.get(k, "")) for k in headers} for r in expected[filename]]:
            raise ValueError("CSV round-trip changed content: " + filename)
        key = "occurrence_id" if filename == "images.csv" else "record_id"
        if len({r[key] for r in records}) != len(records):
            raise ValueError("Duplicate IDs: " + filename)
        result[filename] = {"rows": len(records), "sha256": sha256((output / filename).read_bytes())}
        rows[filename] = records
    image_ids = defaultdict(set)
    for image in rows["images.csv"]:
        if image["scope_status"] == "base" and image["local_path"]:
            image_ids[(image["source_id"], image["revision_id"], image["section"])].add(image["image_id"])
    for row in rows["lore_clean.csv"]:
        if row["scope_status"] != "base" or not row["text"]:
            raise ValueError("Unsafe clean row")
        if sha256(row["text"].encode()) != row["content_hash"]:
            raise ValueError("Clean text checksum mismatch")
        related = image_ids[(row["source_id"], row["revision_id"], row["section"])]
        if not set(json.loads(row["image_ids"])).issubset(related):
            raise ValueError("Broken image reference or cross-section association")
    return result


def run_clean(config, output, *, crawl_report=None, limit=200):
    if limit is not None and not 1 <= limit <= 200:
        raise ValueError("clean limit must be 1..200")
    data_dir = config["data_dir"]
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be new or empty")
    if any(output.is_relative_to((data_dir / name).resolve()) for name in ("raw", "media", "reports", "research")):
        raise ValueError("Output cannot overwrite input artifacts")
    report_path, job = select_sample(data_dir, crawl_report, full=limit is None)
    config = dict(config, clean=dict(config["clean"]))
    config["clean"]["uncertain_entities"] = sorted(
        {x["title"] for x in job.get("scope_excluded", []) if "Shadow of the Erdtree" in x.get("reason", "")}
    )
    pages = job["pages"]
    if limit == 20:
        by_title = {p["title"]: p for p in pages}
        if not set(SAMPLE_TITLES).issubset(by_title):
            raise ValueError("20-page fixture titles not present in this sample")
        pages = [by_title[t] for t in SAMPLE_TITLES]
    else:
        pages = pages[:limit]
    output.mkdir(parents=True, exist_ok=True)
    lore = []
    review = []
    images = []
    decisions = []
    examples = []
    input_hashes = {}
    verified_images = {}
    stats = Counter()
    reasons = Counter()
    image_reasons = Counter()
    inputs = []

    def review_row(raw, section, text, decision, reason, location, suffix=""):
        return {
            "record_id": stable_id(
                raw["source"], raw["source_id"], raw["revision_id"], location, suffix, decision, reason
            ),
            "source_id": raw["source_id"],
            "title": raw["title"],
            "section": section,
            "decision": decision,
            "reason": reason + " | location=" + location,
            "text": text,
            "source_snapshot": raw["_snapshot"],
            "revision_id": raw["revision_id"],
        }

    # Stage 1: materialize filter artifacts before transforming any document.
    filtered = output / "filtered" / "wikigg"
    filtered.mkdir(parents=True, exist_ok=True)
    for item in pages:
        path = inside(data_dir, item["path"])
        raw = read(path)
        if str(raw["source_id"]) != str(item["id"]) or raw["revision_id"] != item["revision_id"]:
            raise ValueError("Raw ID/revision does not match sample report")
        if sha256(raw["content"].encode()) != raw["content_hash"]:
            raise ValueError("Raw content checksum mismatch")
        analysis = filter_document(raw, config["clean"])
        save(filtered / (raw["source_id"] + ".json"), analysis)
        for section in analysis["sections"]:
            decisions.append(
                {
                    "source_id": raw["source_id"],
                    "revision_id": raw["revision_id"],
                    "record_id": stable_id(
                        stable_id(raw["source"], raw["source_id"]), section["location"], section["section"]
                    ),
                    "section": section["section"],
                    "location": section["location"],
                    "scope_status": section["scope_status"],
                    "reason": section["scope_reason"],
                }
            )
    (filtered / "decisions.jsonl").write_text(
        "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in decisions), encoding="utf-8"
    )
    # Stage 2: read the filter artifacts, enrich metadata and associate images.
    for item in pages:
        path = inside(data_dir, item["path"])
        raw = read(path)
        if str(raw["source_id"]) != str(item["id"]) or raw["revision_id"] != item["revision_id"]:
            raise ValueError("Raw ID/revision does not match sample report")
        if sha256(raw["content"].encode()) != raw["content_hash"]:
            raise ValueError("Raw content checksum mismatch")
        input_hashes[str(path)] = sha256(path.read_bytes())
        raw["_snapshot"] = str(path.resolve())
        stats["pages_in"] += 1
        inputs.append({"id": raw["source_id"], "title": raw["title"], "revision_id": raw["revision_id"]})
        cleaned = read(filtered / (raw["source_id"] + ".json"))
        if cleaned["raw_content_hash"] != raw["content_hash"]:
            raise ValueError("Raw changed between filter and transform")
        evidence = cleaned["page_scope_evidence"]
        for removed in cleaned["removed"]:
            review.append(
                review_row(raw, removed["section"], removed["text"], "excluded", removed["reason"], removed["location"])
            )
            reasons[removed["reason"]] += 1
            stats["removed_nodes"] += 1
        retained = []
        section_lookup = defaultdict(list)
        for section in cleaned["sections"]:
            status, reason = section["scope_status"], section["scope_reason"]
            meta = section_metadata(section, raw, cleaned["html_lang"])
            section.update(
                scope_status=status, scope_reason=reason, game_scope="base" if status == "base" else None, **meta
            )
            stats["sections_in"] += 1
            stats["sections_" + status] += 1
            reasons[reason.split(":")[0]] += 1
            doc_id = stable_id(raw["source"], raw["source_id"])
            rid = stable_id(doc_id, section["location"], section["section"])
            section.update(record_id=rid)
            section_lookup[section["section"]].append(section)
            if status == "base":
                retained.append(section)
            else:
                review.append(review_row(raw, section["section"], section["text"], status, reason, section["location"]))
            for block in section["blocks"]:
                for note in block["notes"]:
                    review.append(
                        review_row(
                            raw, section["section"], block["text"], "review", note, block["location"], "block-note"
                        )
                    )
                    reasons[note] += 1
        manifest_path = (
            inside(data_dir, item["media_manifest"])
            if item.get("media_manifest")
            else data_dir / "media/manifests" / raw["source"] / (raw["source_id"] + ".json")
        )
        if not manifest_path.exists():
            raise ValueError("Missing media manifest for " + raw["source_id"])
        manifest = read(manifest_path)
        input_hashes[str(manifest_path)] = sha256(manifest_path.read_bytes())
        if manifest["revision_id"] != raw["revision_id"]:
            raise ValueError("Media manifest revision mismatch")
        section_images = defaultdict(list)
        for image in manifest["images"]:
            name = re.sub(r"\s*\[\s*edit\s*\]", "", image["section"], flags=re.I).strip()
            matches = section_lookup.get(name, [])
            image_status = "review"
            why = "section_association_missing_or_ambiguous"
            if image["status"] == "excluded":
                image_status = "excluded"
                why = "crawler_excluded_interface"
            elif pattern(config["clean"]["dlc_markers"]).search(name):
                image_status = "excluded"
                why = "dlc_image_section"
            elif len(matches) == 1:
                image_status = matches[0]["scope_status"]
                why = "exact_section_association"
            metadata_text = " ".join(str(image.get(k) or "") for k in ("caption", "alt", "file_title"))
            if image_status != "excluded" and pattern(config["clean"]["dlc_markers"]).search(metadata_text):
                image_status, why = "review", "dlc_or_mixed_image_metadata"
            local_path = ""
            if image.get("path") and image["status"] in ("downloaded", "cached"):
                local = inside(data_dir, image["path"])
                local_path = str(local)
                if image["image_id"] not in verified_images:
                    verified_images[image["image_id"]] = (
                        local.is_file() and sha256(local.read_bytes()) == image["image_id"]
                    )
                if not verified_images[image["image_id"]]:
                    raise ValueError("Image file/checksum mismatch")
            elif image_status != "excluded":
                image_status = "review"
                why = "image_not_downloaded"
            image_reasons[why] += 1
            image_row = {
                "occurrence_id": stable_id(raw["source"], raw["source_id"], raw["revision_id"], image["occurrence_id"]),
                "source_id": raw["source_id"],
                "revision_id": raw["revision_id"],
                "section": name,
                "image_id": image.get("image_id", ""),
                "local_path": local_path,
                "caption": image.get("caption", ""),
                "alt": image.get("alt", ""),
                "source_url": image.get("source_url", image.get("display_url", "")),
                "description_url": image.get("description_url") or "",
                "license": image.get("license") or "",
                "license_status": image.get("license_status", "unknown_review_required"),
                "scope_status": image_status,
            }
            images.append(image_row)
            if image_status == "base" and local_path and len(matches) == 1:
                section_images[matches[0]["record_id"]].append(image["image_id"])
        for section in cleaned["sections"]:
            section["image_ids"] = list(dict.fromkeys(section_images[section["record_id"]]))
        for section in retained:
            lore.append(
                {
                    "record_id": section["record_id"],
                    "doc_id": stable_id(raw["source"], raw["source_id"]),
                    "source_id": raw["source_id"],
                    "title": raw["title"],
                    "section": section["section"],
                    "text": section["text"],
                    "url": raw["url"],
                    "source": raw["source"],
                    "revision_id": raw["revision_id"],
                    "fetched_at": raw["fetched_at"],
                    "game_scope": "base",
                    "scope_status": "base",
                    "source_type": section["source_type"],
                    "lang": section["lang"],
                    "image_ids": json.dumps(
                        list(dict.fromkeys(section_images[section["record_id"]])), ensure_ascii=False
                    ),
                    "source_snapshot": raw["_snapshot"],
                    "content_hash": sha256(section["text"].encode()),
                    "cleaning_version": VERSION,
                }
            )
        processed = {
            "doc_id": stable_id(raw["source"], raw["source_id"]),
            "source": raw["source"],
            "url": raw["url"],
            "fetched_at": raw["fetched_at"],
            "raw_content_hash": raw["content_hash"],
            "source_id": raw["source_id"],
            "title": raw["title"],
            "revision_id": raw["revision_id"],
            "source_snapshot": raw["_snapshot"],
            "page_scope_evidence": evidence,
            "sections": cleaned["sections"],
            "removed_nodes": cleaned["removed"],
            "cleaning_version": VERSION,
        }
        save(output / "processed" / raw["source"] / (raw["source_id"] + ".json"), processed)
        if limit == 20:
            examples.append(
                {
                    "title": raw["title"],
                    "scope_evidence": evidence,
                    "before_html_excerpt": raw["content"][:1600],
                    "after_sections": [
                        {"section": s["section"], "status": s["scope_status"], "text": s["text"]}
                        for s in cleaned["sections"]
                    ],
                    "removed_reasons": dict(Counter(x["reason"] for x in cleaned["removed"])),
                }
            )
    expected = {"lore_clean.csv": lore, "review.csv": review, "images.csv": images}
    for filename, headers in [("lore_clean.csv", LORE), ("review.csv", REVIEW), ("images.csv", IMAGES)]:
        csv_write(output / filename, headers, expected[filename])
    validation = verify_csv(output, expected)
    for filename, digest in input_hashes.items():
        if sha256(Path(filename).read_bytes()) != digest:
            raise ValueError("Input artifact changed during processing")
    report = {
        "created_at": now(),
        "cleaning_version": VERSION,
        "cleaning_config_sha256": sha256(json.dumps(config["clean"], sort_keys=True, ensure_ascii=False).encode()),
        "source_job": job["job_id"],
        "source_report": str(report_path.resolve()),
        "scope_policy": (
            "conservative configurable place/context heuristic; no semantic verification or blanket base assignment"
        ),
        "input_pages": inputs,
        "uncertain_entity_evidence": config["clean"]["uncertain_entities"],
        "counts": dict(stats),
        "decision_reasons": dict(reasons),
        "image_association_reasons": dict(image_reasons),
        "csv_validation": validation,
        "input_artifacts_unchanged": True,
        "network_calls": 0,
        "ai_calls": 0,
        "language_counts": dict(Counter(r["lang"] for r in lore)),
        "source_type_counts": dict(Counter(r["source_type"] for r in lore)),
        "limitations": [
            "base means positive configured evidence, not manual verification of every claim",
            "unknown image licenses remain unknown; gallery images have no automatic link to all sections",
            "20-page inspection and regression tests do not certify semantic correctness of the entire dataset",
        ],
    }
    save(output / "report.json", report)
    if examples:
        save(output / "before-after-20.json", examples)
    return report
