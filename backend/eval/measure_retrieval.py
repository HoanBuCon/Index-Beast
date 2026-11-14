"""Measure page-level retrieval on raw questions with labeled source pages."""

import argparse
import asyncio
import json
import time
from pathlib import Path
from statistics import mean

from eval.validate_golden import page


class DenseOnlyRetriever:
    """Use the production E5 encoder and corpus filters with a single dense query."""

    def __init__(self, encoder, store, limit):
        self.encoder, self.store, self.limit = encoder, store, limit

    async def retrieve(self, query, *, spoilers):
        from core.types import Hit

        await self.store.ready()
        (vector,) = await self.encoder.encode_dense([query], query=True)
        policy = self.store.policy
        result = await self.store.client.query_points(
            self.store.collection,
            query=vector,
            using="dense",
            query_filter=policy.query_filter(spoilers=spoilers),
            limit=self.limit,
            with_payload=True,
        )
        return [
            Hit(str(point.id), point.score, point.payload or {})
            for point in result.points
            if policy.exclusion_reason(point.payload or {}, spoilers=spoilers) is None
        ]


def score(expected_urls, ranked_urls):
    expected = {page(url) for url in expected_urls}
    if not expected:
        raise ValueError("Expected at least one labeled source page")
    ranked = list(dict.fromkeys(page(url) for url in ranked_urls))[:5]
    relevant = set(ranked) & expected
    return {
        "recall_at5": len(relevant) / len(expected),
        "mrr_at5": next((1 / rank for rank, url in enumerate(ranked, 1) if url in expected), 0.0),
        "hit_at5": bool(relevant),
    }


async def measure(manifest, retriever):
    rows = []
    for case in manifest:
        if not case["source_urls"]:
            continue
        started = time.perf_counter()
        hits = await retriever.retrieve(case["question"], spoilers=True)
        urls = [hit.payload["url"] for hit in hits]
        rows.append(
            {
                "id": case["id"],
                "lang": case["lang"],
                "difficulty": case["difficulty"],
                "expected_urls": case["source_urls"],
                "ranked_urls": urls,
                "ranked_point_ids": [hit.id for hit in hits],
                "latency_ms": round(1000 * (time.perf_counter() - started), 2),
                **score(case["source_urls"], urls),
            }
        )
    return rows


def summarize(rows):
    return {
        "n": len(rows),
        **{metric: mean(row[metric] for row in rows) for metric in ("recall_at5", "mrr_at5", "hit_at5")},
    }


async def run(manifest, output, mode):
    from qdrant_client import AsyncQdrantClient

    from app.rag.retriever import HybridRetriever
    from core.config import BACKEND_ROOT, Settings
    from core.corpus import CorpusPolicy
    from core.encoders.onnx import FastEmbedEncoder
    from core.vector.store import QdrantStore

    settings = Settings()
    client = AsyncQdrantClient(url=settings.qdrant_url, check_compatibility=False)
    try:
        policy = CorpusPolicy.from_settings(settings)
        encoder = FastEmbedEncoder(BACKEND_ROOT / settings.rag_models_dir, threads=settings.rag_encoder_threads)
        store = QdrantStore(client, settings.rag_collection, policy)
        retriever_type = DenseOnlyRetriever if mode == "dense-only" else HybridRetriever
        retriever = retriever_type(encoder, store, limit=settings.rag_prefetch)
        before = (await client.get_collection(settings.rag_collection)).points_count
        rows = await measure(manifest, retriever)
        after = (await client.get_collection(settings.rag_collection)).points_count
        if before != after:
            raise ValueError("Corpus point count changed while measuring retrieval")
        report = {
            "collection": settings.rag_collection,
            "language_filter": settings.rag_languages,
            "corpus_policy": policy.mode,
            "corpus_points": before,
            "prefetch": settings.rag_prefetch,
            "mode": mode,
            "method": f"Raw question, Qdrant {mode}, top five distinct pages in returned rank order",
            "summary": summarize(rows),
            "by_language": {key: summarize([r for r in rows if r["lang"] == key]) for key in {r["lang"] for r in rows}},
            "by_difficulty": {
                key: summarize([r for r in rows if r["difficulty"] == key]) for key in {r["difficulty"] for r in rows}
            },
            "rows": rows,
        }
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    finally:
        await client.close()
    print(json.dumps(report["summary"], ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("hybrid", "dense-only"), default="hybrid")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output file")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not any(case["source_urls"] for case in manifest):
        parser.error("No labeled source pages in manifest")
    asyncio.run(run(manifest, args.output, args.mode))


if __name__ == "__main__":
    main()
