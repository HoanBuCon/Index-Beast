"""Audit Sprint 4 artifacts, verify a local payload collection, and rerun offline retrieval."""

import argparse
import re
import sqlite3
from collections import Counter
from pathlib import Path
from random import Random
from urllib.parse import unquote, urlsplit

import numpy as np
from qdrant_client import QdrantClient, models

from core.corpus import CorpusPolicy
from ingest.artifacts import read, save
from ingest.chunk.load_full import preflight, read_lines
from ingest.debug.readiness_retrieval import model
from ingest.indexing import inspect_artifact

CASES = (
    (
        "IB-GS-075",
        "Ranni the Witch",
        "Fingerslayer Blade chest north east Night's Sacred Ground Nokron Radahn",
        r"Fingerslayer Blade.{0,100}chest north.east.{0,50}Night.s Sacred Ground",
    ),
    (
        "IB-GS-052",
        "Ranni the Witch",
        "Discarded Palace Key Baleful Shadow Rennala chest Dark Moon Ring",
        r"Baleful Shadow.{0,200}Discarded Palace Key.{0,250}chest",
    ),
    (
        "IB-GS-065",
        "Samurai",
        "Samurai starting equipment armaments Uchigatana Red Thorn Roundshield longbow arrows",
        r"Armaments.*Red Thorn Roundshield.*Longbow.*Arrow x20.*Fire Arrow x10",
    ),
    (
        "IB-GS-031",
        "Messmer the Impaler",
        "Messmer the Impaler mandatory boss location Shadow Keep",
        r"mandatory boss.*Shadow Keep",
    ),
    (
        "IB-GS-041",
        "Flame, Cleanse Me",
        "Flame Cleanse Me cure poison scarlet rot burns",
        r"(?:alleviates|reduces).*poison.*scarlet rot.*cures",
    ),
    (
        "IB-GS-086",
        "Leyndell, Ashen Capital",
        "Leyndell Ashen Capital Maliketh Rune of Death ash",
        r"defeat of Maliketh.*Rune of Death",
    ),
)
COLLECTION = "s4_wiki_payload_en"


def path_key(url):
    parsed = urlsplit(url)
    return parsed.netloc.casefold(), unquote(parsed.path).replace("_", " ").casefold()


def scope_sample(directory, docs):
    rng = Random(4164)
    sample = []
    for release, size in (
        ("base_candidate", 10),
        ("sote_candidate", 10),
        ("mixed_or_sote_candidate", 10),
        ("unknown", 20),
    ):
        pool = sorted((d for d in docs if d["release_scope"] == release), key=lambda d: d["source_id"])
        for doc in rng.sample(pool, size):
            rows = list(read_lines(directory / "wikigg" / (doc["source_id"] + ".jsonl")))
            lead = next(
                (c["text"] for c in rows if c["section"] == "Introduction" and c["content_type"] == "prose"), ""
            )
            sample.append(
                {
                    **{
                        k: doc[k]
                        for k in (
                            "title",
                            "source_id",
                            "url",
                            "source_snapshot",
                            "revision_id",
                            "game_scope",
                            "game_scope_reason",
                            "release_scope",
                            "release_evidence",
                            "wiki_categories",
                            "spoiler_level",
                        )
                    },
                    "lead": lead[:800],
                    "chunk_levels": dict(Counter(c["spoiler_level"] for c in rows)),
                }
            )
    return sample


def verify_payload(directory, output):
    path = directory / "chunks.jsonl"
    policy = CorpusPolicy("pilot", ("en",))
    result = inspect_artifact(path, policy)
    if result.invalid or not result.chunks:
        raise ValueError("Invalid or empty index artifact")
    expected = {str(c.point_uuid): c.model_extra["spoiler_level"] for c in result.chunks}
    with_client = QdrantClient(path=str(output / "qdrant-payload"))
    try:
        with_client.create_collection(COLLECTION, vectors_config={})
        for start in range(0, len(result.chunks), 256):
            points = [
                models.PointStruct(id=str(c.point_uuid), vector={}, payload=policy.index_payload(c.payload()))
                for c in result.chunks[start : start + 256]
            ]
            with_client.upsert(COLLECTION, points, wait=True)
        indexed = with_client.count(COLLECTION, count_filter=policy.query_filter(), exact=True).count
        safe, offset = set(), None
        while True:
            hits, offset = with_client.scroll(
                COLLECTION,
                scroll_filter=policy.query_filter(spoilers=False),
                offset=offset,
                limit=128,
                with_vectors=False,
            )
            for point in hits:
                if policy.exclusion_reason(point.payload, spoilers=False):
                    raise ValueError("Unsafe point passed the payload filter")
                safe.add(str(point.id))
            if offset is None:
                break
        if indexed != len(expected) or safe != {k for k, v in expected.items() if v == 0} or not safe:
            raise ValueError("Unexpected payload count or spoiler filter")
        return {
            **result.report(path, policy),
            "collection": COLLECTION,
            "mode": "qdrant_local_payload_only",
            "indexed": indexed,
            "visible_without_spoilers": len(safe),
            "vectors": 0,
        }
    finally:
        with_client.close()


def candidates(rows, queries):
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE VIRTUAL TABLE search USING fts5(title, section, body)")
        db.executemany(
            "INSERT INTO search VALUES (?, ?, ?)",
            ((c["title"], c["section"], c["embedding_text"]) for c in rows),
        )
        return [
            [
                rows[i - 1]
                for (i,) in db.execute(
                    "SELECT rowid FROM search WHERE search MATCH ? "
                    "ORDER BY bm25(search, 3.0, 1.5, 1.0), rowid LIMIT 16",
                    (
                        " OR ".join(
                            f'"{term}"' for term in dict.fromkeys(re.findall(r"\w+", q.casefold())) if len(term) > 2
                        ),
                    ),
                )
            ]
            for q in queries
        ]


def compare(before, after, golden, model_path):
    rows = [[row for row in read_lines(folder / "chunks.jsonl") if row["lang"] == "en"] for folder in (before, after)]
    questions = [c["question"] for c in golden] + [c[2] for c in CASES]
    lists = [candidates(version, questions) for version in rows]
    ranker = model(model_path)
    texts = list(
        dict.fromkeys(
            ["query: " + q for q in questions]
            + [c["embedding_text"] for version in lists for group in version for c in group]
        )
    )
    vectors = {}
    for start in range(0, len(texts), 16):
        batch = texts[start : start + 16]
        if any(len(ranker.model.tokenizer.encode(text).ids) > 512 for text in batch):
            raise ValueError("Would truncate E5 input")
        for text, vector in zip(batch, ranker.embed(batch, batch_size=16), strict=True):
            if vector.shape != (384,) or not np.isfinite(vector).all():
                raise ValueError("Invalid embedding")
            vectors[text] = vector
    ranked = [
        [
            sorted(group, key=lambda c: -float(vectors["query: " + q] @ vectors[c["embedding_text"]]))
            for q, group in zip(questions, version, strict=True)
        ]
        for version in lists
    ]

    def first_rank(group, predicate):
        return next((i for i, c in enumerate(group, 1) if predicate(c)), None)

    source_ranks = []
    for i, case in enumerate(golden):
        urls = {path_key(url) for url in case["source_urls"]}

        def expected_page(chunk, urls=urls):
            return path_key(chunk["url"]) in urls

        source_ranks.append(
            {
                "id": case["id"],
                "expected_urls": case["source_urls"],
                "fts_source_rank": [first_rank(version[i], expected_page) for version in lists],
                "e5_source_rank": [first_rank(version[i], expected_page) for version in ranked],
            }
        )
    corpus_urls = [{path_key(c["url"]) for c in version} for version in rows]
    for case in source_ranks:
        urls = {path_key(u) for u in case["expected_urls"]}
        case["evidence_pages_in_wiki"] = [len(urls & found) for found in corpus_urls]

    focused = []
    for offset, (case_id, title, query, regex) in enumerate(CASES, start=len(golden)):

        def relevant(c, title=title, regex=regex):
            return c["title"] == title and bool(re.search(regex, c["text"], re.I | re.S))

        def proof(version):
            return [
                {
                    k: c.get(k)
                    for k in (
                        "chunk_id",
                        "text",
                        "token_count",
                        "url",
                        "source_snapshot",
                        "revision_id",
                        "quest_stage",
                        "source_locations",
                        "spoiler_level",
                    )
                }
                for c in version
                if relevant(c)
            ]

        focused.append(
            {
                "id": case_id,
                "query": query,
                "source_title": title,
                "literal_proof_before_after": list(map(proof, rows)),
                "fts_proof_rank": [first_rank(version[offset], relevant) for version in lists],
                "e5_proof_rank": [first_rank(version[offset], relevant) for version in ranked],
            }
        )
    return {
        "method": "Full English FTS5 BM25 top-16 followed by local E5 cosine reranking",
        "comparison_order": ["S3", "S4"],
        "encoder": "intfloat/multilingual-e5-small",
        "model_snapshot": model_path.name,
        "unique_embedded_texts": len(vectors),
        "llm_calls": 0,
        "golden_source_diagnostic": source_ranks,
        "focused_literal_evidence": focused,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--golden-report", type=Path, required=True)
    parser.add_argument("--model-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    report = preflight(args.after)
    print("Validated raw provenance and artifact checksums", flush=True)
    docs = list(read_lines(args.after / "documents.jsonl"))
    save(args.output / "scope-sample-50.json", scope_sample(args.after, docs))
    save(args.output / "payload-index.json", verify_payload(args.after, args.output))
    print("Verified local payload collection", flush=True)
    eval_result = compare(args.before, args.after, read(args.golden_report)["manifest"]["cases"], args.model_snapshot)
    save(args.output / "retrieval-eval.json", eval_result)
    print(f"Audited {report['counts']['pages']} pages and reran {len(eval_result['golden_source_diagnostic'])} queries")


if __name__ == "__main__":
    main()
