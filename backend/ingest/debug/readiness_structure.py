"""Independent whole-artifact source/ID/token/coverage checks and reproducible sample review material."""

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from tokenizers import Tokenizer

from core.ids import chunk_id, document_id
from core.text.chunking import prepare_units


def run(chunks_dir, clean_dir, tokenizer_path, output, name):
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    rows = [json.loads(line) for line in (chunks_dir / "chunks.jsonl").open(encoding="utf-8")]
    stats, languages, types = Counter(), Counter(), Counter()
    ids, seen_units, spans, unit_texts = set(), set(), defaultdict(list), {}
    content_hashes, errors, label_mismatches = Counter(), [], []
    doc, sections, units = None, None, None
    for c in rows:
        sid = c["source_id"]
        if doc is None or doc["source_id"] != sid:
            doc = json.loads((clean_dir / "processed/wikigg" / (sid + ".json")).read_text(encoding="utf-8"))
            sections = {s["record_id"]: s for s in doc["sections"]}
            units = {
                (s["record_id"], u["unit_key"]): u
                for s in doc["sections"]
                if s["chunk_eligible"]
                for u in prepare_units(doc, s, tokenizer, 450)
            }
        section = sections[c["section_record_id"]]
        unit = units[(c["section_record_id"], c["unit_key"])]
        key = (sid, c["section_record_id"], c["unit_key"])
        seen_units.add(key)
        unit_texts[key] = unit["text"]
        spans[key].append((c["start_char"], c["end_char"]))
        identity = str(chunk_id(document_id(c["source"], sid), c["ordinal"]))
        actual = len(tokenizer.encode(c["embedding_text"], add_special_tokens=True).ids)
        checks = {
            "source_slice": c["text"] == unit["text"][c["start_char"] : c["end_char"]],
            "chunk_identity": c["chunk_id"] == identity and identity not in ids,
            "token_count": actual == c["token_count"] and 0 < actual <= 450,
            "text_hash": hashlib.sha256(c["text"].encode()).hexdigest() == c["text_hash"],
            "image_context": c["image_ids"] == list(dict.fromkeys(section["image_ids"])),
            "dialogue_context": all(c.get(k) == unit.get(k) for k in ["speaker", "trigger"]),
            "e5_prefix": c["embedding_text"].startswith("passage: ")
            and not c["embedding_text"][9:].lstrip().startswith(("passage:", "query:")),
        }
        for check, okay in checks.items():
            if not okay:
                errors.append({"check": check, "chunk_id": identity})
        ids.add(identity)
        stats["chunks"] += 1
        stats["max_tokens"] = max(stats["max_tokens"], actual)
        stats["body_at_most_20_chars"] += len(c["text"].strip()) <= 20
        stats["tokens_below_100"] += actual < 100
        stats["tokens_100_to_299"] += 100 <= actual < 300
        stats["tokens_300_to_450"] += actual >= 300
        stats["stats_chunks"] += c["unit_kind"] == "infobox_stats"
        stats["template_chunks"] += "template" in c["title"].lower()
        stats["behind_scenes_chunks"] += "behind the scenes" in c["section"].lower()
        stats["missing_source_updated_at"] += c.get("source_updated_at") is None
        stats["missing_spoiler_level"] += c.get("spoiler_level") is None
        cjk = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]", c["text"]))
        letters = len(re.findall(r"[A-Za-z\u3040-\u30ff\u3400-\u9fff]", c["text"]))
        stats["en_with_dominant_cjk_script"] += c["lang"] == "en" and cjk > 3 and cjk / max(1, letters) > 0.3
        content_hashes[c["text_hash"]] += 1
        languages[c["lang"]] += 1
        types[c["source_type"]] += 1
        label = (c.get("variant_context") or {}).get("label")
        expected = {"🇧🇷": "pt", "🇹🇼": "zh", "JP": "ja", "JA": "ja", "🇯🇵": "ja"}.get(label)
        if expected and c["lang"] != expected:
            label_mismatches.append({"chunk_id": identity, "label": label, "lang": c["lang"]})
    for key, ranges in spans.items():
        end = 0
        for left, right in sorted(ranges):
            if left > end:
                errors.append({"check": "coverage_gap", "unit": key})
            if left < end:
                count = len(tokenizer.encode(unit_texts[key][left:end], add_special_tokens=False).ids)
                stats["max_overlap"] = max(stats["max_overlap"], count)
                if count > 50:
                    errors.append({"check": "overlap_budget", "unit": key})
            end = max(end, right)
        if end != len(unit_texts[key]):
            errors.append({"check": "coverage_end", "unit": key})
    stats["units_checked"] = len(seen_units)
    stats["duplicate_body_occurrences"] = sum(n - 1 for n in content_hashes.values())
    sample = random.Random(20261108).sample([c for c in rows if c["lang"] == "en"], 50)
    (output / ("sample50-" + name + ".jsonl")).write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in sample), encoding="utf-8"
    )
    result = {
        "counts": dict(stats),
        "languages": dict(languages),
        "source_types": dict(types),
        "errors": errors,
        "flag_label_mismatches": label_mismatches,
        "sample_population": "EN chunks; seed20261108; separate independent before/after samples",
        "note": "Short/duplicate body counts are flags, not automatic errors or semantic approval.",
    }
    (output / (name + "-structure.json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"phase": name, "counts": dict(stats), "errors": len(errors)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--clean", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    run(args.chunks, args.clean, args.tokenizer, args.output, args.name)
