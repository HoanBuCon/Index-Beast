"""Offline raw corpus audit. Provisional partitions, never production scope labels."""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from bs4 import BeautifulSoup
from tokenizers import Tokenizer

from core.text.chunking import chunk_section
from core.text.html_clean import clean_html
from ingest.artifacts import now, read, save, sha256
from ingest.debug.chunk_readiness import distribution
from ingest.filter.rules import page_evidence, pattern, section_decision
from ingest.settings import load_settings
from ingest.transform.metadata import section_metadata


def page_probe(raw, soup, config):
    """Evidence from content, never infer base from absence of DLC markers."""
    locations = " ".join(
        n.get_text(" ", strip=True)
        for n in soup.select('.pi-data[data-source="location"], .pi-data[data-source="region"]')
    )
    for node in list(soup.select("aside,.portable-infobox,.toc,.navbox,.noexcerpt,script,style")):
        if node.parent:
            node.decompose()
    body = soup.select_one(".mw-parser-output") or soup
    leads = [p.get_text(" ", strip=True) for p in body.find_all("p", recursive=False)]
    leads = [p for p in leads if p]
    lead = " ".join(leads[:2])
    text = body.get_text(" ", strip=True)
    dlc = pattern(config["dlc_markers"])
    base = pattern(config["base_places"])
    direct = re.search(r"\b(?:is|are)\b[^.]{0,200}\bin (?:the )?Shadow of the Erdtree\b", lead, re.I)
    title_location = dlc.search(raw["title"] + " " + locations)
    marker = dlc.search(text)
    place = base.search(locations + " " + lead)
    if direct:
        bucket, reason, evidence = "dlc_candidate", "explicit_dlc_definition", direct.group(0)
    elif title_location:
        bucket, reason, evidence = "dlc_candidate", "dlc_title_or_location_marker", title_location.group(0)
    elif marker:
        bucket, reason, evidence = "mixed_or_dlc_review", "dlc_mention_not_proof_whole_page_is_dlc", marker.group(0)
    elif place:
        bucket, reason, evidence = "base_context_candidate", "configured_base_place_context", place.group(0)
    else:
        bucket, reason, evidence = "unresolved_review", "no_positive_base_evidence", ""
    return {
        "partition": bucket,
        "reason": reason,
        "evidence": evidence,
        "lead": lead[:900],
        "location": locations[:500],
        "generic_2022_intro": bool(re.search(r"ELDEN RING\s*\(2022\)", lead)),
        "lead_nonempty_paragraphs": len(leads),
    }


def study(data, run_dir, tokenizer_path, output):
    data, run_dir = data.resolve(), run_dir.resolve()
    if output.exists():
        raise ValueError("Output must be new")
    if output.resolve().is_relative_to((data / "raw").resolve()):
        raise ValueError("Output cannot be inside raw")
    output.mkdir(parents=True)
    config = load_settings()["clean"]
    report_path, checkpoint_path = run_dir / "report.json", run_dir / "checkpoint.json"
    report, checkpoint = read(report_path), read(checkpoint_path)
    if report["status"] not in {"partial", "completed"} or not report.get("finished_at"):
        raise ValueError("Crawl must have ended before study")
    fingerprints = {
        str(p.resolve()): sha256(p.read_bytes()) for p in [report_path, checkpoint_path, run_dir / "inventory.json"]
    }
    accepted = {str(p["id"]): p for p in report["pages"]}
    cohort = dict(checkpoint)
    cohort.update(accepted)
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    counts, partitions, categories, headings = Counter(), Counter(), Counter(), Counter()
    legacy_pages, legacy_sections, kinds, reasons, media = Counter(), Counter(), Counter(), Counter(), Counter()
    sizes, tokens, table_sizes = [], [], []
    examples, sample = defaultdict(list), defaultdict(list)
    longest = []
    failures = []
    with (
        (output / "pages.jsonl").open("w", encoding="utf-8") as page_stream,
        (output / "sections.jsonl").open("w", encoding="utf-8") as section_stream,
    ):
        for index, key in enumerate(sorted(cohort, key=int)):
            entry = cohort[key]
            try:
                path = (data / entry["path"]).resolve()
                if not path.is_relative_to(data.resolve()):
                    raise ValueError("Snapshot outside data")
                payload = path.read_bytes()
                fingerprints[str(path)] = sha256(payload)
                raw = json.loads(payload)
                if str(raw["source_id"]) != key or raw["revision_id"] != entry["revision_id"]:
                    raise ValueError("Cohort identity mismatch")
                if sha256(raw["content"].encode()) != raw["content_hash"]:
                    raise ValueError("Raw content hash mismatch")
                soup = BeautifulSoup(raw["content"], "html.parser")
                body = soup.select_one(".mw-parser-output")
                if body is None:
                    raise ValueError("Missing article body")
                page_features = {
                    "tables": len(body.select("table")),
                    "infoboxes": len(body.select("aside,.portable-infobox")),
                    "galleries": len(body.select(".gallery")),
                    "tabs": len(body.select(".tabber__panel,.tabbertab")),
                }
                for node in body.select("table"):
                    table_sizes.append(len(node.find_all("tr")))
                probe = page_probe(raw, soup, config)
                diagnostic = clean_html(raw["content"], title=raw["title"], skip_sections=config["skip_sections"])
                legacy = page_evidence(raw, config)
                legacy_pages[legacy["status"]] += 1
                categories.update(raw["categories"])
                partitions[probe["partition"]] += 1
                counts["pages_read"] += 1
                counts["raw_only_media_failed"] += key not in accepted
                for name, value in page_features.items():
                    counts["pages_with_" + name] += bool(value)
                    counts[name] += value
                sizes.append(len(raw["content"]))
                section_stats = Counter()
                max_section_tokens, has_dialogue = 0, False
                for section in diagnostic["sections"]:
                    label, why = section_decision(section, legacy, config)
                    meta = section_metadata(section, raw, diagnostic["html_lang"])
                    body_tokens = len(tokenizer.encode(section["text"], add_special_tokens=False).ids)
                    tokens.append(body_tokens)
                    max_section_tokens = max(max_section_tokens, body_tokens)
                    headings[section["section"].split(" > ")[-1]] += 1
                    section_stats[label] += 1
                    legacy_sections[label] += 1
                    counts["source_type_" + meta["source_type"]] += 1
                    counts["lang_" + meta["lang"]] += 1
                    counts["sections_over_450_body_tokens"] += body_tokens > 450
                    for block in section["blocks"]:
                        kinds[block["kind"]] += 1
                        if block["kind"] == "dialogue":
                            has_dialogue = True
                            counts["dialogue_turns"] += len(block.get("turns", []))
                            counts["turns_with_trigger"] += sum(bool(t.get("trigger")) for t in block.get("turns", []))
                            counts["turns_with_speaker"] += sum(bool(t.get("speaker")) for t in block.get("turns", []))
                    section_stream.write(
                        json.dumps(
                            {
                                "source_id": key,
                                "revision_id": raw["revision_id"],
                                "title": raw["title"],
                                "section": section["section"],
                                "location": section["location"],
                                "anchor": section.get("anchor"),
                                "page_partition": probe["partition"],
                                "legacy_scope": label,
                                "legacy_reason": why,
                                "body_tokens": body_tokens,
                                "block_kinds": dict(Counter(b["kind"] for b in section["blocks"])),
                                "source_type": meta["source_type"],
                                "lang": meta["lang"],
                                "excerpt": section["text"][:220],
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                for node in diagnostic["removed"]:
                    reasons[node["reason"]] += 1
                manifest_path = data / entry.get(
                    "media_manifest", str((run_dir / "media" / (key + ".json")).relative_to(data))
                )
                if manifest_path.exists():
                    fingerprints[str(manifest_path.resolve())] = sha256(manifest_path.read_bytes())
                    manifest = read(manifest_path)
                    counts["manifest_revision_mismatch"] += manifest["revision_id"] != raw["revision_id"]
                    media.update("status:" + str(i["status"]) for i in manifest["images"])
                    media.update("license:" + str(i.get("license_status", "unknown")) for i in manifest["images"])
                    counts["image_occurrences"] += len(manifest["images"])
                else:
                    counts["missing_manifest"] += 1
                record = {
                    "source_id": key,
                    "title": raw["title"],
                    "revision_id": raw["revision_id"],
                    "url": raw["url"],
                    "source_snapshot": str(path),
                    "raw_hash": raw["content_hash"],
                    "crawl_media_accepted": key in accepted,
                    "categories": raw["categories"],
                    **probe,
                    **page_features,
                    "legacy_scope": legacy,
                    "diagnostic_section_counts": dict(section_stats),
                    "max_section_tokens": max_section_tokens,
                }
                page_stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                if len(examples[probe["partition"]]) < 8:
                    examples[probe["partition"]].append(record)
                for group in [probe["partition"], *[k for k, v in page_features.items() if v]]:
                    if len(sample[group]) < 5:
                        sample[group].append(entry)
                if has_dialogue and len(sample["dialogue"]) < 5:
                    sample["dialogue"].append(entry)
                longest.append((max_section_tokens, key, entry))
                longest = sorted(longest, key=lambda x: (-x[0], int(x[1])))[:10]
                if index % 100 == 0:
                    print(f"STUDY {index + 1}/{len(cohort)} {raw['title']}", flush=True)
            except (ValueError, OSError, KeyError) as exc:
                failures.append({"source_id": key, "error": str(exc)})
    # Actual chunk simulation on a stratified structure/scope sample; never writes production chunks.
    sample_entries = {p["id"]: p for group in sample.values() for p in group}
    sample_entries.update({key: entry for _, key, entry in longest})
    chunk_tokens, chunk_reviews, chunk_errors = [], [], []
    for key, entry in sample_entries.items():
        raw = read(data / entry["path"])
        parsed = clean_html(raw["content"], title=raw["title"], skip_sections=config["skip_sections"])
        for section in parsed["sections"]:
            section.update(section_metadata(section, raw, parsed["html_lang"]))
            try:
                result = chunk_section(raw, section, tokenizer, 450, 50)
                chunk_tokens.extend(c["token_count"] for c in result["chunks"])
                chunk_reviews.extend(dict(r, source_id=key, section=section["section"]) for r in result["reviews"])
            except (ValueError, KeyError) as exc:
                chunk_errors.append({"source_id": key, "section": section["section"], "error": str(exc)})
    changed = [p for p, digest in fingerprints.items() if sha256(Path(p).read_bytes()) != digest]
    summary = {
        "created_at": now(),
        "research_only": True,
        "study_version": "raw-scope-1.0",
        "scope_config": config,
        "source_job": report["job_id"],
        "crawl_counts": report["counts"],
        "inventory_pages": report["inventory_pages"],
        "cohort_pages": len(cohort),
        "counts": dict(counts),
        "provisional_partitions": dict(partitions),
        "legacy_page_scope": dict(legacy_pages),
        "legacy_section_scope": dict(legacy_sections),
        "block_kinds": dict(kinds),
        "removal_reasons": dict(reasons),
        "media": dict(media),
        "raw_html_characters": distribution(sizes),
        "section_body_tokens": distribution(tokens),
        "table_rows": distribution(table_sizes),
        "top_categories": categories.most_common(35),
        "top_headings": headings.most_common(40),
        "failures": failures,
        "changed_inputs": changed,
        "simulation": {
            "pages": len(sample_entries),
            "page_ids": list(sample_entries),
            "chunk_tokens": distribution(chunk_tokens),
            "review_units": chunk_reviews,
            "errors": chunk_errors,
            "note": "All diagnostic sections simulated, including DLC/review; not production chunk count",
        },
        "tokenizer_sha256": sha256(tokenizer_path.read_bytes()),
        "network_calls": 0,
        "encoder_calls": 0,
        "database_writes": 0,
    }
    save(output / "summary.json", summary)
    save(output / "examples.json", examples)
    save(output / "input-fingerprints.json", fingerprints)
    if changed or failures or chunk_errors:
        raise ValueError("Study has changed inputs or parsing failures; inspect summary")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    study(load_settings()["data_dir"], args.run_dir, args.tokenizer, args.output_dir)


if __name__ == "__main__":
    main()
