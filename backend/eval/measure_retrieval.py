"""Measure page-level retrieval on raw questions with labeled source pages.

Modes: hybrid (E5 + BM25 fused with RRF; production), dense (E5-only), bm25 (BM25-only). --rerank adds the Jina
reranker on top (local cross-encoder or the Jina API, per RAG_RERANKER_PROVIDER; no LLM). From backend/:
  python -X utf8 -m eval.measure_retrieval --manifest <cases.json> --output <new.json> --mode hybrid --rerank
"""

import argparse
import asyncio
import json
import logging
import time
from collections import Counter
from pathlib import Path
from statistics import mean

from eval.validate_golden import page

NOISY = {"typo", "vi_no_diacritics", "telex", "abbreviation", "casual_case"}


class OutcomeLog(logging.Handler):
    """Kết quả mỗi lần rerank (ok/timeout/lỗi): không nhầm reranker lặng lẽ bỏ qua với reranker vô tác dụng."""

    def __init__(self):
        super().__init__()
        self.rows = []

    def emit(self, record):
        if getattr(record, "event", None) == "reranker_outcome":
            self.rows.append(
                {"status": record.status, "reason": record.reason_category, "elapsed_ms": record.elapsed_ms}
            )


class ThrottledReranker:
    """Chỉ cho lượt đo: Jina trả 429 (hết hạn mức token/phút) thì chờ rồi gọi lại, để đo tác dụng khi rerank chạy
    được. Không dùng ở runtime: ở đó lượt hỏi không thể chờ, reranker quay về thứ tự RRF."""

    def __init__(self, reranker, outcomes, wait_seconds=20, attempts=6):
        self.reranker, self.outcomes = reranker, outcomes
        self.wait_seconds, self.attempts = wait_seconds, attempts

    async def rank(self, query, hits):
        for _ in range(self.attempts):
            ranked = await self.reranker.rank(query, hits)
            last = self.outcomes.rows[-1] if self.outcomes.rows else {}
            if last.get("status") == "ok" or last.get("reason") != "http_status":
                return ranked
            await asyncio.sleep(self.wait_seconds)
        return ranked


def score(expected_urls, ranked_urls):
    expected = {page(url) for url in expected_urls}
    if not expected:
        raise ValueError("Expected at least one labeled source page")
    ranked = list(dict.fromkeys(page(url) for url in ranked_urls))[:5]
    relevant = set(ranked) & expected
    return {
        "precision_at5": len(relevant) / 5,
        "recall_at5": len(relevant) / len(expected),
        "mrr_at5": next((1 / rank for rank, url in enumerate(ranked, 1) if url in expected), 0.0),
        "hit_at5": bool(relevant),
    }


async def measure(manifest, retriever, outcomes=None):
    rows = []
    for case in manifest:
        if not case["source_urls"]:
            continue
        seen = len(outcomes.rows) if outcomes else 0
        started = time.perf_counter()
        hits = await retriever.retrieve(case["question"])
        urls = [hit.payload["url"] for hit in hits]
        rows.append(
            {
                "id": case["id"],
                "lang": case["lang"],
                "difficulty": case["difficulty"],
                "case_tags": case.get("case_tags", []),
                "expected_urls": case["source_urls"],
                "ranked_urls": urls,
                "ranked_point_ids": [hit.id for hit in hits],
                "latency_ms": round(1000 * (time.perf_counter() - started), 2),
                **(
                    {
                        "rerank": [
                            o["status"] if o["status"] == "ok" else f"{o['status']}:{o['reason']}"
                            for o in outcomes.rows[seen:]
                        ]
                    }
                    if outcomes
                    else {}
                ),
                **score(case["source_urls"], urls),
            }
        )
    return rows


def summarize(rows):
    if not rows:
        return {"n": 0}
    return {
        "n": len(rows),
        **{
            metric: mean(row[metric] for row in rows)
            for metric in ("precision_at5", "recall_at5", "mrr_at5", "hit_at5")
        },
        "latency_ms_mean": mean(row["latency_ms"] for row in rows),
    }


GROUPS = {
    "by_language": lambda r: r["lang"],
    "by_difficulty": lambda r: r["difficulty"],
    "by_input": lambda r: "noisy" if NOISY & set(r["case_tags"]) else "clean",
}


async def run(manifest, output, mode, rerank, throttle=False):
    import httpx
    from qdrant_client import AsyncQdrantClient

    from app.rag.reranker import JinaReranker
    from app.rag.retriever import HybridRetriever
    from core.config import BACKEND_ROOT, Settings
    from core.corpus import CorpusPolicy
    from core.encoders.onnx import FastEmbedEncoder
    from core.vector.store import QdrantStore

    settings = Settings()
    if rerank and not settings.reranker_available:
        raise SystemExit("--rerank needs RAG_RERANKER_ENABLED=true (and a real JINA_API_KEY for provider jina)")
    client = AsyncQdrantClient(url=settings.qdrant_url, check_compatibility=False)
    http = httpx.AsyncClient(timeout=settings.rag_reranker_timeout_seconds, follow_redirects=False, trust_env=False)
    outcomes = None
    try:
        policy = CorpusPolicy.from_settings(settings)
        encoder = FastEmbedEncoder(BACKEND_ROOT / settings.rag_models_dir, threads=settings.rag_encoder_threads)
        store = QdrantStore(client, settings.rag_collection, policy, mode=mode)
        reranker = None
        if rerank and settings.rag_reranker_provider == "local":
            from app.rag.reranker import local_reranker

            reranker = local_reranker(settings)
            await reranker.warm()
        elif rerank:
            reranker = JinaReranker(
                settings.jina_api_key.get_secret_value().strip(),
                model=settings.rag_reranker_model,
                timeout_seconds=settings.rag_reranker_timeout_seconds,
                max_candidates=settings.rag_reranker_max_candidates,
                client=http,
                tokens_per_minute=settings.rag_reranker_tokens_per_minute,
                # --throttle: chờ đủ hạn mức để mọi câu đều được Jina xếp lại (đo tác dụng thật, bỏ qua độ trễ).
                max_wait_seconds=60 if throttle else settings.rag_reranker_max_wait_seconds,
            )
        if rerank:
            outcomes = OutcomeLog()
            logging.getLogger("app.rag.reranker").addHandler(outcomes)
            logging.getLogger("app.rag.reranker").setLevel(logging.INFO)
            if throttle:
                reranker = ThrottledReranker(reranker, outcomes)
        retriever = HybridRetriever(encoder, store, limit=settings.rag_prefetch, reranker=reranker)
        before = (await client.get_collection(settings.rag_collection)).points_count
        rows = await measure(manifest, retriever, outcomes)
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
            "rerank": rerank,
            "throttle": throttle,
            "reranker_model": (
                (
                    settings.rag_reranker_local_model
                    if settings.rag_reranker_provider == "local"
                    else settings.rag_reranker_model
                )
                if rerank
                else None
            ),
            "rerank_outcomes": dict(Counter(f"{o['status']}:{o['reason']}" for o in outcomes.rows))
            if outcomes
            else None,
            "method": f"Raw question, Qdrant {mode}{' + rerank' if rerank else ''}, top five distinct pages",
            "summary": summarize(rows),
            **{
                name: {
                    key: summarize([r for r in rows if key_of(r) == key]) for key in sorted({key_of(r) for r in rows})
                }
                for name, key_of in GROUPS.items()
            },
            "rows": rows,
        }
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    finally:
        await client.close()
        await http.aclose()
    print(json.dumps({"summary": report["summary"], "rerank_outcomes": report["rerank_outcomes"]}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("hybrid", "dense", "bm25", "dense-only"), default="hybrid")
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Add the reranker of RAG_RERANKER_PROVIDER (jina: API, local: this machine)",
    )
    parser.add_argument("--throttle", action="store_true", help="Wait and retry when Jina returns 429 (rate limit)")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output file")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not any(case["source_urls"] for case in manifest):
        parser.error("No labeled source pages in manifest")
    asyncio.run(
        run(manifest, args.output, "dense" if args.mode == "dense-only" else args.mode, args.rerank, args.throttle)
    )


if __name__ == "__main__":
    main()
