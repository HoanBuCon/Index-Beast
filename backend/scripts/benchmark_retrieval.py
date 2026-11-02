"""Sequential, read-only retrieval benchmark. --allow-inference permits real query embedding.

No LLM, indexing or Qdrant writes. A fresh encoder's first request is reported separately;
the same encoder/client is reused for warm requests. Qdrant time is client round-trip, not server CPU time.
"""

import argparse
import asyncio
import math
import platform
import statistics
import time
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

from qdrant_client import AsyncQdrantClient

from app.rag.retriever import HybridRetriever
from core.config import REPO_ROOT, get_settings
from core.corpus import CorpusPolicy
from core.vector.store import QdrantStore
from scripts.benchmark_index import save, timestamp

QUESTIONS = (
    ("VI01", "vi", "Ranni là ai, cha mẹ cô là ai?"),
    ("VI02", "vi", "Vì sao Godwyn được gọi là Prince of Death?"),
    ("VI03", "vi", "Flame, Cleanse Me chữa được những hiệu ứng nào?"),
    ("VI04", "vi", "So sánh Uchigatana và Rivers of Blood về blood loss."),
    ("VI05", "vi", "Làm sao bắt đầu nhiệm vụ Ranni ở Church of Elleh?"),
    ("EN01", "en", "Who is Melina and what is her connection to the Tarnished?"),
    ("EN02", "en", "How is Rellana related to Rennala?"),
    ("EN03", "en", "What does Arsenal Charm do for equipment load?"),
    ("EN04", "en", "Suggest a Bloodhound's Fang PvE build at level 80."),
    ("EN05", "en", "What is the relationship between Miquella and St. Trina?"),
)
METRICS = ("ready_ms", "embedding_ms", "qdrant_ms", "total_retrieve_ms")


class Probe:
    """Shared by sequential wrappers; never share across concurrent retrieval requests."""

    def __init__(self):
        self.metrics = {}
        self.query_calls = 0

    @contextmanager
    def stage(self, name):
        started = time.perf_counter()
        try:
            yield
        finally:
            self.metrics[name] = self.metrics.get(name, 0.0) + (time.perf_counter() - started) * 1000


class MeasuredClient(AsyncQdrantClient):
    def __init__(self, *args, probe, **kwargs):
        super().__init__(*args, **kwargs)
        self.probe = probe

    async def query_points(self, *args, **kwargs):
        self.probe.query_calls += 1
        with self.probe.stage("qdrant_ms"):
            return await super().query_points(*args, **kwargs)


class MeasuredEncoder:
    def __init__(self, encoder, probe):
        self.encoder, self.probe = encoder, probe

    async def encode(self, texts, *, query=False):
        with self.probe.stage("embedding_ms"):
            return await self.encoder.encode(texts, query=query)


class MeasuredStore(QdrantStore):
    def __init__(self, *args, probe, **kwargs):
        super().__init__(*args, **kwargs)
        self.probe = probe

    async def ready(self):
        with self.probe.stage("ready_ms"):
            return await super().ready()


def summarize(rows):
    successful = [r for r in rows if r["success"]]
    summary = {
        "requests": len(rows),
        "successful": len(successful),
        "errors": len(rows) - len(successful),
        "empty_successful_results": sum(r["hit_count"] == 0 for r in successful),
    }
    for metric in METRICS:
        values = sorted(r[metric] for r in successful)
        summary[metric] = {
            "samples": len(values),
            "min": min(values) if values else None,
            "median": statistics.median(values) if values else None,
            "p95": values[math.ceil(0.95 * len(values)) - 1] if values else None,
            "max": max(values) if values else None,
        }
    return summary


async def measure_one(retriever, probe, question, *, phase, round_number, spoilers):
    qid, lang, text = question
    row = {"id": qid, "lang": lang, "question": text, "phase": phase, "round": round_number, "success": False}
    probe.metrics = {}
    probe.query_calls = 0
    started = time.perf_counter()
    try:
        hits = await retriever.retrieve(text, spoilers=spoilers)
        if probe.query_calls != 1 or any(k not in probe.metrics for k in METRICS[:-1]):
            raise ValueError("Incomplete instrumentation")
        row.update(
            success=True,
            hit_count=len(hits),
            top5=[
                {
                    "point_id": h.id,
                    "score": h.score,
                    "title": h.payload.get("title"),
                    "lang": h.payload.get("lang"),
                    "release_scope": h.payload.get("release_scope"),
                }
                for h in hits[:5]
            ],
        )
    except Exception as exc:
        row["error_type"] = type(exc).__name__  # Never persist exception bodies/credentials/model inputs.
    finally:
        row.update(probe.metrics)
        row["total_retrieve_ms"] = (time.perf_counter() - started) * 1000
        row["query_api_calls"] = probe.query_calls
    return row


async def run(args):
    settings = get_settings()
    policy = CorpusPolicy.from_settings(settings)
    limit = args.limit if args.limit is not None else settings.rag_prefetch
    report = {
        "status": "running",
        "started_at": timestamp(),
        "collection": settings.rag_collection,
        "policy": policy.mode,
        "languages": list(policy.languages),
        "spoilers": not args.no_spoilers,
        "prefetch_and_fusion_limit": limit,
        "context_top_k_setting": settings.rag_top_k,
        "rounds": args.rounds,
        "concurrency": 1,
        "encoder_threads": settings.rag_encoder_threads,
        "model": "intfloat/multilingual-e5-small",
        "sparse_model": "Qdrant/bm25",
        "fusion": "RRF",
        "python": platform.python_version(),
        "processor": platform.processor(),
        "versions": {p: version(p) for p in ("fastembed", "onnxruntime", "qdrant-client")},
        "percentile_method": "nearest rank: sorted[ceil(0.95*n)-1]; median uses statistics.median",
        "cold_definition": "First retrieve with fresh encoder/client and cached weights, NOT cold OS/disk cache. "
        "Client construction and read-only prechecks excluded; actual first model load included in embedding.",
        "timing_definition": "total_retrieve_ms wraps native HybridRetriever.retrieve including readiness, "
        "embedding, Query API, LangChain/Document/policy processing. qdrant_ms wraps the client's query_points "
        "round-trip including transport/decoding, excludes ready/count calls. No rewrite/rerank/context/LLM/API HTTP.",
        "rows": [],
    }
    probe, client = Probe(), None
    started = time.perf_counter()
    try:
        from core.encoders.onnx import FastEmbedEncoder

        client = MeasuredClient(
            url=settings.qdrant_url,
            timeout=max(1, round(settings.client_timeout_seconds)),
            check_compatibility=False,
            probe=probe,
        )
        store = MeasuredStore(client, settings.rag_collection, policy, probe=probe)
        await store.ready()  # Fail before model loading if collection missing/incompatible/empty.
        report["points_before"] = (await client.count(settings.rag_collection, exact=True)).count
        report["filters"] = policy.query_filter(spoilers=not args.no_spoilers).model_dump(
            mode="json", exclude_none=True
        )
        encoder = MeasuredEncoder(
            FastEmbedEncoder(REPO_ROOT / "backend" / settings.rag_models_dir, threads=settings.rag_encoder_threads),
            probe,
        )
        retriever = HybridRetriever(encoder, store, limit=limit)
        save(args.report, report)
        schedule = [("cold", 0, QUESTIONS[0])]
        schedule += [("warm", n, q) for n in range(1, args.rounds + 1) for q in QUESTIONS]
        for phase, n, question in schedule:
            row = await measure_one(
                retriever, probe, question, phase=phase, round_number=n, spoilers=not args.no_spoilers
            )
            report["rows"].append(row)
            save(args.report, report)
            print(
                f"{phase} {n} {row['id']}: success={row['success']} total_ms={row['total_retrieve_ms']:.3f}", flush=True
            )
            if phase == "cold" and not row["success"]:
                raise RuntimeError("First request failed; no valid cold/warm comparison")
        warm = [r for r in report["rows"] if r["phase"] == "warm"]
        report["warm_summary"] = summarize(warm)
        report["warm_by_language"] = {lang: summarize([r for r in warm if r["lang"] == lang]) for lang in ("vi", "en")}
        report["points_after"] = (await client.count(settings.rag_collection, exact=True)).count
        report["point_count_unchanged"] = report["points_before"] == report["points_after"]
        report["status"] = (
            "complete" if all(r["success"] for r in report["rows"]) and report["point_count_unchanged"] else "failed"
        )
    except BaseException as exc:
        report.update(status="failed", error_type=type(exc).__name__)
        raise
    finally:
        try:
            if client is not None:
                await client.close()
        except BaseException as exc:
            report.update(status="failed", error_type=type(exc).__name__)
            raise
        finally:
            report["finished_at"] = timestamp()
            report["benchmark_wall_seconds"] = time.perf_counter() - started
            save(args.report, report)
    return report["status"] == "complete"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-inference", action="store_true")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-spoilers", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_inference:
        parser.error("--allow-inference required before any client/model initialization")
    if not 1 <= args.rounds <= 20 or (args.limit is not None and not 1 <= args.limit <= 200):
        parser.error("rounds must be 1..20; limit must be 1..200")
    if args.report.exists() or args.report.suffix != ".json" or not args.report.parent.is_dir():
        parser.error("Use a new .json report in an existing directory")
    if args.report.resolve().is_relative_to((REPO_ROOT / "backend" / "data").resolve()):
        parser.error("Report must be outside source data directories")
    return 0 if asyncio.run(run(args)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
