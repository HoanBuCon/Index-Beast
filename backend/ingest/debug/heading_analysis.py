"""Offline S1 heading/token experiment, not a production chunking pipeline."""

import argparse
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from tokenizers import Tokenizer

from ingest.artifacts import read, save, sha256
from ingest.crawl.scope import sample_scope_reason

EXCLUDE = "script, style, .navbox, .toc, .mw-editsection, .portable-infobox, .mw-cite-backlink"


def sections(html):
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".mw-parser-output, #page-content, main") or soup
    for tag in body.select(EXCLUDE):
        if tag.parent:
            tag.decompose()
    headings = []
    result = []
    parts = []

    def flush():
        text = " ".join(" ".join(parts).split())
        if text:
            result.append({"section": " > ".join(t for _, t in headings) or "Introduction", "text": text})
        parts.clear()

    for node in body.descendants:
        if getattr(node, "name", None) in ("h1", "h2", "h3", "h4", "h5", "h6"):
            flush()
            level = int(node.name[1])
            headings = [(n, t) for n, t in headings if n < level]
            headings.append((level, node.get_text(" ", strip=True)))
        elif isinstance(node, NavigableString) and not node.find_parent(["h1", "h2", "h3", "h4", "h5", "h6"]):
            parts.append(str(node))
    flush()
    return result


def analyze(data_dir, tokenizer_path, sample_size=20):
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    files = [p for p in (data_dir / "raw" / "wikigg").glob("*.json") if not sample_scope_reason(read(p))]
    discovery = read(data_dir / "reports" / "categories.json")
    rank = {str(p["pageid"]): i for i, p in enumerate(discovery["pages"])}
    files.sort(key=lambda p: rank.get(p.stem, 10**9))
    if len(files) < sample_size:
        raise ValueError("Need at least 20 downloaded sample pages")
    # Spread selections across the downloaded balanced-discovery order.
    chosen = [files[i * (len(files) - 1) // (sample_size - 1)] for i in range(sample_size)]
    report = {
        "tokenizer": "intfloat/multilingual-e5-small",
        "tokenizer_sha256": sha256(tokenizer_path.read_bytes()),
        "sample_size": sample_size,
        "pages": [],
        "experiments": {},
        "scope": "exploratory; manual scope review still required",
    }
    for path in chosen:
        raw = read(path)
        parts = sections(raw["content"])
        row = {
            "id": raw["source_id"],
            "title": raw["title"],
            "url": raw["url"],
            "revision_id": raw["revision_id"],
            "sections": [],
            "images": {},
        }
        for part in parts:
            prefix = f"passage: {raw['title']}\n{part['section']}\n"
            row["sections"].append(
                {
                    "section": part["section"],
                    "body_tokens": len(tokenizer.encode(part["text"], add_special_tokens=False).ids),
                    "prefix_tokens": len(tokenizer.encode(prefix, add_special_tokens=False).ids),
                }
            )
        manifest = data_dir / "media" / "manifests" / "wikigg" / (raw["source_id"] + ".json")
        if manifest.exists():
            images = read(manifest)["images"]
            row["images"] = dict(Counter(x["status"] for x in images))
            row["image_examples"] = [
                {
                    k: x.get(k)
                    for k in ("occurrence_id", "section", "caption", "alt", "file_title", "path", "license_status")
                }
                for x in images[:3]
            ]
        report["pages"].append(row)
    for maximum in (350, 400, 450, 500):
        lengths = []
        short = 0
        prefix_overflow = 0
        for page in report["pages"]:
            for section in page["sections"]:
                budget = maximum - section["prefix_tokens"] - 2
                if budget <= 50:
                    prefix_overflow += 1
                    continue
                remaining = section["body_tokens"]
                while remaining > 0:
                    take = min(budget, remaining)
                    lengths.append(take + section["prefix_tokens"] + 2)
                    short += take < 300
                    if remaining <= budget:
                        break
                    remaining -= budget - 50
        report["experiments"][str(maximum)] = {
            "chunks": len(lengths),
            "max_total_tokens": max(lengths, default=0),
            "short_body_chunks": short,
            "overlong_prefix_sections": prefix_overflow,
            "overlap_tokens": 50,
            "note": "token-count window simulation; sentence/row boundaries to implement in S2",
        }
    save(data_dir / "reports" / "heading-analysis.json", report)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    p.add_argument("--tokenizer", type=Path, required=True)
    args = p.parse_args()
    result = analyze(args.data_dir, args.tokenizer)
    print(result["experiments"])


if __name__ == "__main__":
    main()
