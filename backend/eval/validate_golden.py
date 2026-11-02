"""Offline golden-set/review validation; no LLM, embedding, DB or HTTP clients.

From backend: python -m eval.validate_golden --corpus data/chunk_runs/s2-full-v1/chunks.jsonl
Add --require-reviewed to gate release on actual TV2 approval rather than draft schema validity.
"""

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

FIELDS = {"id", "question", "lang", "expected_answer", "source_urls", "category", "difficulty"}
CATEGORIES = {
    "character",
    "event",
    "location",
    "multi_hop",
    "out_of_scope",
    "mechanics",
    "equipment",
    "quest",
    "insufficient_evidence",
}
NEGATIVE = {"out_of_scope", "insufficient_evidence"}
CHECKS = {"source_urls", "expected_answer", "difficulty", "scope"}


def read_rows(path):
    rows = []
    with path.open(encoding="utf-8-sig") as stream:
        for line, text in enumerate(stream, 1):
            try:
                row = json.loads(text)
                if not isinstance(row, dict):
                    raise ValueError("Expected JSON object")
            except ValueError as exc:
                raise ValueError(f"{path}:{line}: invalid JSON object") from exc
            rows.append(row)
    return rows


def page(url):
    parsed = urlsplit(url)
    return parsed.netloc.casefold(), unquote(parsed.path).rstrip("/")


def validate(path, review_path, *, corpus=None, require_reviewed=False):
    rows, reviews = read_rows(path), read_rows(review_path)
    ids, questions = set(), set()
    for line, row in enumerate(rows, 1):
        where = f"{path}:{line}"
        if set(row) != FIELDS:
            raise ValueError(f"{where}: expected exactly seven golden-set fields")
        for key in FIELDS - {"source_urls"}:
            if not isinstance(row[key], str) or not row[key].strip() or "\ufffd" in row[key]:
                raise ValueError(f"{where}: invalid text field {key}")
        question = re.sub(r"\W+", " ", unicodedata.normalize("NFKC", row["question"]).casefold()).strip()
        if not re.fullmatch(r"IB-GS-\d{3}", row["id"]) or row["id"] in ids or question in questions:
            raise ValueError(f"{where}: invalid/duplicate ID or duplicate normalized question")
        ids.add(row["id"])
        questions.add(question)
        if (
            row["lang"] not in {"vi", "en"}
            or row["difficulty"] not in {"easy", "medium", "hard"}
            or row["category"] not in CATEGORIES
        ):
            raise ValueError(f"{where}: unsupported language/difficulty/category")
        urls = row["source_urls"]
        if not isinstance(urls, list) or any(not isinstance(u, str) for u in urls) or len(set(urls)) != len(urls):
            raise ValueError(f"{where}: source_urls must be a list of unique URLs")
        for url in urls:
            p = urlsplit(url)
            if p.scheme not in {"http", "https"} or not p.netloc or p.username or p.password or re.search(r"\s", url):
                raise ValueError(f"{where}: invalid HTTP(S) source URL")
        if (row["category"] in NEGATIVE) != (not urls):
            raise ValueError(f"{where}: factual cases require sources; behavioral negative cases use no sources")
    langs = Counter(r["lang"] for r in rows)
    if not rows or langs["vi"] * 2 < len(rows):
        raise ValueError(f"{path}: at least 50% Vietnamese required")
    by_id = {r["id"]: r for r in rows}
    if len(reviews) != len(rows) or {r.get("id") for r in reviews} != ids:
        raise ValueError(f"{review_path}: review IDs must map one-to-one to golden IDs")
    source = {}
    if corpus is not None:
        source = {r["chunk_id"]: r for r in read_rows(corpus)}
    for review in reviews:
        where = f"{review_path}:{review['id']}"
        if review.get("status") not in {"pending", "changes_requested", "approved"}:
            raise ValueError(f"{where}: invalid review status")
        checks = review.get("checks", {})
        if set(checks) != CHECKS or any(
            v not in {"pending", "pass", "fail", "not_applicable"} for v in checks.values()
        ):
            raise ValueError(f"{where}: invalid review checks")
        if review["status"] == "pending" and (
            review.get("reviewer") is not None or review.get("reviewed_at") is not None
        ):
            raise ValueError(f"{where}: pending review must not pretend to have a reviewer/date")
        if review["status"] == "approved":
            if (
                not isinstance(review.get("reviewer"), str)
                or not review["reviewer"].strip()
                or not review.get("reviewed_at")
            ):
                raise ValueError(f"{where}: approval needs actual reviewer and date")
            if any(v not in {"pass", "not_applicable"} for v in checks.values()):
                raise ValueError(f"{where}: approval requires completed checks")
            if review["reviewer"].casefold() not in {"unclething", "tv2 - unclething"}:
                raise ValueError(f"{where}: Sprint 2 cross-review must identify TV2 / UncleThing")
            if datetime.fromisoformat(review["reviewed_at"]).tzinfo is None:
                raise ValueError(f"{where}: review date needs timezone")
        for evidence in review.get("author_evidence", []):
            if corpus is None:
                continue
            chunk = source.get(evidence.get("chunk_id"))
            if chunk is None:
                raise ValueError(f"{where}: missing evidence chunk")
            quote, start = evidence.get("quote"), evidence.get("quote_start")
            if (
                not isinstance(quote, str)
                or not quote
                or type(start) is not int
                or start < 0
                or chunk["text"][start : start + len(quote)] != quote
            ):
                raise ValueError(f"{where}: quote is not an exact artifact slice")
            if hashlib.sha256(chunk["text"].encode()).hexdigest() != evidence.get("text_sha256"):
                raise ValueError(f"{where}: source text hash mismatch")
            if evidence.get("source_url") != chunk["url"] or page(chunk["url"]) not in {
                page(u) for u in by_id[review["id"]]["source_urls"]
            }:
                raise ValueError(f"{where}: source URL does not match the golden case")
    approved = sum(r["status"] == "approved" for r in reviews)
    return {
        "schema_valid": True,
        "total": len(rows),
        "languages": dict(langs),
        "vi_ratio": langs["vi"] / len(rows),
        "categories": dict(Counter(r["category"] for r in rows)),
        "difficulty": dict(Counter(r["difficulty"] for r in rows)),
        "review_status": dict(Counter(r["status"] for r in reviews)),
        "sote_cases": sum(r.get("evaluation_scope") == "sote" for r in reviews),
        "author_evidence_cases": sum(bool(r.get("author_evidence")) for r in reviews),
        "artifact_quotes_verified": corpus is not None,
        "author_evidence_cases_verified": sum(bool(r.get("author_evidence")) for r in reviews)
        if corpus is not None
        else 0,
        "review_gate_passed": approved == len(rows),
        "accepted": approved == len(rows) if require_reviewed else True,
        "note": "Schema/provenance validation is not semantic verification or TV2 review. "
        "No model evaluation executed.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).parent
    parser.add_argument("--input", type=Path, default=root / "golden_set.jsonl")
    parser.add_argument("--reviews", type=Path, default=root / "reviews/s2-golden-set-review.jsonl")
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--require-reviewed", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate(args.input, args.reviews, corpus=args.corpus, require_reviewed=args.require_reviewed)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
