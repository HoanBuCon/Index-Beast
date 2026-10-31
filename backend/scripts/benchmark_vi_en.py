"""Paired VI/EN stage diagnostic. Default is plan-only: no clients, models, network or file writes."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.api.schemas.chat import ChatRequest
from app.rag.overview import detect_overview
from app.rag.pipeline import ChatPipeline
from core.config import REPO_ROOT

DEFAULT_PAIRS = REPO_ROOT / "backend/eval/vi_en_pairs.jsonl"
STRATEGIES = ("original", "rewrite", "dual")


class NoLLM:
    def bind_model(self, **_kwargs):
        raise RuntimeError("LLM execution was not authorized")


class HistoryItem(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str


class Pair(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    id: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1)
    expected_behavior: str = Field(min_length=1)
    review_status: str = Field(pattern=r"^(pending|reviewed)$")
    vi: str = Field(min_length=1, max_length=2000)
    en: str = Field(min_length=1, max_length=2000)
    history_vi: list[HistoryItem] = Field(max_length=8)
    history_en: list[HistoryItem] = Field(max_length=8)
    source_targets: list[str] = Field(max_length=20)
    expected_chunk_ids: list[str] = Field(max_length=100)

    @model_validator(mode="after")
    def check_labels(self):
        if not self.vi.strip() or not self.en.strip():
            raise ValueError("Empty question")
        if any(sum(len(m.content) for m in history) > 8000 for history in (self.history_vi, self.history_en)):
            raise ValueError("History budget exceeded")
        if any(
            urlsplit(url).scheme not in {"http", "https"} or not urlsplit(url).netloc for url in self.source_targets
        ):
            raise ValueError("Invalid source target URL")
        if any(not value.strip() for value in self.expected_chunk_ids):
            raise ValueError("Empty expected chunk ID")
        if self.expected_chunk_ids and self.review_status != "reviewed":
            raise ValueError("Evidence chunk labels need cross-review")
        return self


def load_pairs(path: Path) -> list[dict]:
    pairs, seen = [], set()
    with path.open(encoding="utf-8-sig") as source:
        for line, raw in enumerate(source, 1):
            try:
                row = Pair.model_validate_json(raw).model_dump()
                if row["id"] in seen:
                    raise ValueError("Duplicate pair ID")
            except (ValueError, ValidationError):
                raise ValueError(f"Invalid paired case: {path}:{line}") from None
            seen.add(row["id"])
            pairs.append(row)
    if not pairs or len(pairs) > 100:
        raise ValueError("Use 1..100 paired cases")
    return pairs


def _url(value: str) -> str:
    return unquote(value.split("#")[0]).rstrip("/")


def retrieval_metrics(pair: dict, prepared) -> dict:
    rows = prepared.trace.get("retrieved", [])
    targets = {_url(url) for url in pair["source_targets"]}
    selected = [
        {"url": hit.payload.get("url", ""), "chunk_id": hit.payload.get("artifact_chunk_id", hit.id)}
        for hit in prepared.hits
    ]
    ids = set(pair["expected_chunk_ids"]) if pair["review_status"] == "reviewed" else set()
    return {
        "candidate_source_hit": any(_url(row.get("url") or "") in targets for row in rows) if targets else None,
        "top5_source_hit": any(_url(row["url"]) in targets for row in selected) if targets else None,
        "candidate_evidence_recall": len(ids & {row["chunk_id"] for row in rows}) / len(ids) if ids else None,
        "top5_evidence_recall": len(ids & {row["chunk_id"] for row in selected}) / len(ids) if ids else None,
    }


async def benchmark(pairs, settings, llm, retriever, strategies, *, generate=False):
    rows = []
    for strategy in strategies:
        config = settings.model_copy(
            update={
                "chat_mode": "rag",
                "rag_rewrite_enabled": strategy != "original",
                "rag_query_mode": "dual" if strategy == "dual" else "rewrite",
            }
        )
        pipeline = ChatPipeline(config, llm, retriever)
        for pair in pairs:
            for lang in ("vi", "en"):
                row = {
                    "id": pair["id"],
                    "lang": lang,
                    "strategy": strategy,
                    "question": pair[lang],
                    "expected_behavior": pair["expected_behavior"],
                    "review_status": pair["review_status"],
                    "manual_review": {"rewrite_intent": None, "correctness": None, "faithfulness": None},
                }
                rows.append(row)
                try:
                    prepared = await pipeline.prepare(
                        ChatRequest(message=pair[lang], channel="web", options={"lang": lang}),
                        pair[f"history_{lang}"],
                        diagnostic_queries=True,
                    )
                except Exception as exc:
                    trace = getattr(exc, "rag_diagnostics", {})
                    row.update(
                        status="prepare_error",
                        error_type=type(exc).__name__,
                        trace=trace,
                        failure_stage="retrieval" if "retrieval_queries" in trace else "preparation",
                    )
                    continue
                row.update(
                    status="prepared",
                    response_language=prepared.lang,
                    trace=prepared.trace,
                    metrics=retrieval_metrics(pair, prepared),
                )
                row["context"] = [
                    {
                        "chunk_id": hit.payload.get("artifact_chunk_id", hit.id),
                        "point_id": hit.id,
                        "text": hit.payload["text"],
                        "title": hit.payload["title"],
                        "url": hit.payload["url"],
                        "game_scope": hit.payload.get("game_scope"),
                        "release_scope": hit.payload.get("release_scope"),
                        "review_status": hit.payload.get("review_status"),
                    }
                    for hit in prepared.hits
                ]
                row["generation"] = {"status": "not_run"}
                if generate:
                    try:
                        result = await pipeline.generator.generate(prepared)
                        row["generation"] = {
                            "status": "ok",
                            "outcome": "static"
                            if prepared.static_answer is not None
                            else "grounded"
                            if result.grounded
                            else "insufficient",
                            "answer": result.answer,
                            "grounded": result.grounded,
                            "source_indices": [s.index for s in result.sources],
                            "static_answer": prepared.static_answer is not None,
                        }
                    except Exception as exc:
                        row["generation"] = {
                            "status": "error",
                            "outcome": "invalid_output",
                            "error_type": type(exc).__name__,
                            "format_failure": prepared.trace.get("generation_failure"),
                            "validation_failure": prepared.trace.get("validation_failure"),
                        }
                # Trace result is internal and may not be JSON serializable. Never include provider reasoning.
                row["trace"] = {key: value for key, value in prepared.trace.items() if key != "result"}
    groups = []
    for strategy in strategies:
        for lang in ("vi", "en"):
            sample = [row for row in rows if row["strategy"] == strategy and row["lang"] == lang]
            group = {
                "strategy": strategy,
                "lang": lang,
                "rows": len(sample),
                "prepare_errors": sum(row["status"] == "prepare_error" for row in sample),
            }
            for key in ("candidate_source_hit", "top5_source_hit", "candidate_evidence_recall", "top5_evidence_recall"):
                values = [row["metrics"][key] for row in sample if row.get("metrics", {}).get(key) is not None]
                group[key] = {"samples": len(values), "mean": sum(values) / len(values) if values else None}
            groups.append(group)
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "collection": settings.rag_collection,
        "overview_enabled": settings.rag_overview_enabled,
        "notes": (
            "Source-page hit is NOT evidence recall or answer correctness. Pending labels require cross-review; "
            "semantic judgments remain manual. Direct pipeline calls do not measure HTTP API errors."
        ),
        "summary": groups,
        "rows": rows,
    }


async def live(args, pairs):
    # Imports/construction below are reached ONLY with --execute and explicit LLM permission when needed.
    from qdrant_client import AsyncQdrantClient

    from app.adapters.llm import DeepSeekLLM
    from app.rag.retriever import HybridRetriever
    from core.config import get_settings
    from core.corpus import CorpusPolicy
    from core.encoders.onnx import FastEmbedEncoder
    from core.vector.store import QdrantStore

    settings = get_settings()
    client = AsyncQdrantClient(
        url=settings.qdrant_url, timeout=settings.client_timeout_seconds, check_compatibility=False
    )
    llm = None
    try:
        llm = DeepSeekLLM(settings) if args.allow_llm else NoLLM()
        retriever = HybridRetriever(
            FastEmbedEncoder(REPO_ROOT / "backend" / settings.rag_models_dir, threads=settings.rag_encoder_threads),
            QdrantStore(client, settings.rag_collection, CorpusPolicy.from_settings(settings)),
            limit=settings.rag_prefetch,
        )
        return await benchmark(pairs, settings, llm, retriever, args.strategies, generate=args.generate)
    finally:
        try:
            if isinstance(llm, DeepSeekLLM):
                await llm.aclose()
        finally:
            await client.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--strategies", nargs="+", choices=STRATEGIES, default=["original"])
    parser.add_argument("--pair-id", action="append", help="Limit to named pairs; repeat to select multiple")
    parser.add_argument("--execute", action="store_true", help="Allow query embedding/model cache and Qdrant reads")
    parser.add_argument("--allow-llm", action="store_true", help="Allow paid rewrite/generation requests")
    parser.add_argument("--generate", action="store_true", help="Also generate answers, requires --allow-llm")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        pairs = load_pairs(args.pairs)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.pair_id:
        pairs = [pair for pair in pairs if pair["id"] in args.pair_id]
        if {pair["id"] for pair in pairs} != set(args.pair_id):
            parser.error("Unknown pair ID")
    if len(set(args.strategies)) != len(args.strategies):
        parser.error("Strategies must be distinct")
    needs_llm = args.generate or any(value != "original" for value in args.strategies)
    if not args.execute:
        print(
            json.dumps(
                {
                    "mode": "plan_only",
                    "pairs": len(pairs),
                    "rows": len(pairs) * 2 * len(args.strategies),
                    "max_logical_rewrite_calls": len(pairs) * 2 * sum(value != "original" for value in args.strategies),
                    "max_retrieval_queries": sum(
                        2 if strategy == "dual" or detect_overview(pair[lang]) is not None else 1
                        for strategy in args.strategies
                        for pair in pairs
                        for lang in ("vi", "en")
                    ),
                    "generation_requested": args.generate,
                    "needs_llm_permission_on_execute": needs_llm,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if needs_llm and not args.allow_llm:
        parser.error("Rewrite/generation execution requires --allow-llm")
    if not args.output or args.output.suffix != ".json" or args.output.exists() or not args.output.parent.is_dir():
        parser.error("Execution requires --output to a NEW .json file in an existing directory")
    if args.output.resolve().is_relative_to((REPO_ROOT / "backend/data").resolve()):
        parser.error("Output must be outside original data directories")
    report = asyncio.run(live(args, pairs))
    with args.output.open("x", encoding="utf-8") as destination:
        json.dump(report, destination, ensure_ascii=False, indent=2)
    return int(
        any(
            row["status"] == "prepare_error" or row.get("generation", {}).get("status") == "error"
            for row in report["rows"]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
