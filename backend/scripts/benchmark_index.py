"""Measure a full corpus pass through the real index_chunks path. Explicit --allow-write required.

No LLM, crawl or notebook. Model initialization is lazy and included in the first encode timing.
Run from backend; JSON report is updated atomically during progress and on completion/failure.
"""

import argparse
import asyncio
import hashlib
import json
import platform
import time
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path

from core.config import REPO_ROOT, get_settings
from core.corpus import CorpusPolicy
from core.vector.store import QdrantStore
from ingest.indexing import index_chunks, inspect_artifact


def timestamp():
    return datetime.now(timezone(timedelta(hours=7))).isoformat()


def save(path, report):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class MeasuredEncoder:
    def __init__(self, encoder, report):
        self.encoder, self.report = encoder, report

    async def encode(self, texts, *, query=False):
        started = time.perf_counter()
        result = await self.encoder.encode(texts, query=query)
        self.report["embedding_seconds"] += time.perf_counter() - started
        self.report["embedded_records"] += len(texts)
        return result


class MeasuredStore(QdrantStore):
    def __init__(self, *args, report, report_path, **kwargs):
        super().__init__(*args, **kwargs)
        self.report, self.report_path = report, report_path
        self.last_progress = time.perf_counter()

    async def upsert(self, chunks, vectors):
        started = time.perf_counter()
        await super().upsert(chunks, vectors)
        self.report["upsert_seconds"] += time.perf_counter() - started
        self.report["completed_records"] += len(chunks)
        self.report["completed_batches"] += 1
        if time.perf_counter() - self.last_progress >= 30:
            self.report["progress_at"] = timestamp()
            save(self.report_path, self.report)
            print(
                json.dumps({k: self.report[k] for k in ("completed_records", "selected_records", "progress_at")}),
                flush=True,
            )
            self.last_progress = time.perf_counter()


async def run(args):
    settings = get_settings()
    policy = CorpusPolicy.from_settings(settings)
    report = {
        "status": "running",
        "started_at": timestamp(),
        "input": args.input.as_posix(),
        "collection": settings.rag_collection,
        "policy": policy.mode,
        "languages": list(policy.languages),
        "model": "intfloat/multilingual-e5-small",
        "dense_dimensions": 384,
        "distance": "Cosine",
        "sparse_model": "Qdrant/bm25",
        "sparse_modifier": "IDF",
        "threads": settings.rag_encoder_threads,
        "batch_size": settings.rag_batch_size,
        "embedding_seconds": 0.0,
        "upsert_seconds": 0.0,
        "embedded_records": 0,
        "completed_records": 0,
        "completed_batches": 0,
        "python": platform.python_version(),
        "processor": platform.processor(),
        "versions": {name: version(name) for name in ("fastembed", "onnxruntime", "qdrant-client")},
        "timing_notes": "One uninterrupted full selected-corpus pass, no resume/skips. Cached model weights; "
        "fresh encoder includes first model load. index_seconds includes schema check, encoding and upsert. "
        "total_elapsed_seconds includes preflight and final checks/client cleanup, excludes Docker startup. "
        "Existing collection upsert is not equivalent to building an empty collection.",
    }
    started = time.perf_counter()
    client = None
    try:
        phase = time.perf_counter()
        inspection = inspect_artifact(args.input, policy, tokenizer_path=args.tokenizer)
        report.update(
            {
                "source_sha256": inspection.sha256,
                "total_records": inspection.total,
                "selected_records": len(inspection.chunks),
                "excluded_records": len(inspection.excluded),
                "invalid_records": len(inspection.invalid),
                "preflight_seconds": time.perf_counter() - phase,
                "token_check": "local_tokenizer_reencode" if args.tokenizer else "declared_bounds_only",
            }
        )
        if inspection.invalid or not inspection.chunks:
            raise ValueError("Artifact invalid or no selected records; stopped before clients/models")
        from qdrant_client import AsyncQdrantClient

        from core.encoders.onnx import FastEmbedEncoder
        from core.vector.schema import ensure_collection

        client = AsyncQdrantClient(url=settings.qdrant_url, timeout=30, check_compatibility=False)
        existed = await client.collection_exists(settings.rag_collection)
        if existed:
            await ensure_collection(client, settings.rag_collection)
        report["collection_existed"] = existed
        report["count_before"] = (await client.count(settings.rag_collection, exact=True)).count if existed else 0
        ids = [str(c.point_uuid) for c in inspection.chunks[:8]]
        before = await client.retrieve(settings.rag_collection, ids, with_payload=True) if existed else []
        before_payloads = {str(p.id): p.payload for p in before}
        expected = {str(c.point_uuid): policy.index_payload(c.payload()) for c in inspection.chunks[:8]}
        report["sample_payloads_match_input_before"] = all(expected[k] == v for k, v in before_payloads.items())
        report["sample_existing_records"] = len(before_payloads)
        save(args.report, report)
        print(json.dumps({k: report[k] for k in ("selected_records", "count_before", "collection")}), flush=True)

        phase = time.perf_counter()
        encoder = MeasuredEncoder(
            FastEmbedEncoder(REPO_ROOT / "backend" / settings.rag_models_dir, threads=settings.rag_encoder_threads),
            report,
        )
        store = MeasuredStore(client, settings.rag_collection, policy, report=report, report_path=args.report)
        indexed = await index_chunks(inspection.chunks, encoder, store, settings.rag_batch_size)
        report["index_seconds"] = time.perf_counter() - phase
        report["index_finished_at"] = timestamp()
        report["records_per_index_second"] = indexed / report["index_seconds"]

        phase = time.perf_counter()
        report["count_after"] = (await client.count(settings.rag_collection, exact=True)).count
        after = await client.retrieve(settings.rag_collection, ids, with_payload=True)
        payloads = {str(p.id): p.payload for p in after}
        report["sample_payloads_match_input_after"] = payloads == expected
        report["sample_existing_payloads_unchanged"] = all(payloads.get(k) == v for k, v in before_payloads.items())
        report["source_unchanged"] = hashlib.sha256(args.input.read_bytes()).hexdigest() == inspection.sha256
        report["verification_seconds"] = time.perf_counter() - phase
        if (
            indexed != report["selected_records"]
            or indexed != report["embedded_records"]
            or indexed != report["completed_records"]
            or report["count_after"] < indexed
            or not report["source_unchanged"]
            or not report["sample_payloads_match_input_after"]
        ):
            raise ValueError("Final verification failed")
        report["status"] = "complete"
    except BaseException as exc:
        report.update(status="failed", error_type=type(exc).__name__)
        raise
    finally:
        try:
            if client is not None:
                await client.close()
        finally:
            report["finished_at"] = timestamp()
            report["total_elapsed_seconds"] = time.perf_counter() - started
            save(args.report, report)
            print(
                json.dumps(
                    {
                        k: report.get(k)
                        for k in ("status", "completed_records", "index_seconds", "total_elapsed_seconds")
                    }
                ),
                flush=True,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-write", action="store_true", help="Allow real embedding and Qdrant writes")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_write:
        parser.error("Explicit --allow-write required; no clients or models created")
    if args.report.suffix != ".json" or args.report.exists() or not args.report.parent.is_dir():
        parser.error("Report must be a new .json file in an existing report directory")
    if args.report.resolve().is_relative_to((REPO_ROOT / "backend" / "data").resolve()):
        parser.error("Report must be outside source data directories")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
