"""Golden diagnostic: plan-only by default; checkpoint each explicit live request, never index."""

import argparse
import asyncio
import hashlib
import json
import math
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from core.config import REPO_ROOT
from eval.validate_golden import page, read_rows, validate

ROOT = REPO_ROOT / "backend/eval"
PROMPTS = REPO_ROOT / "backend/app/rag/prompts"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases(golden, reviews, selection, limit=None):
    validation = validate(golden, reviews)
    rows = {row["id"]: row for row in read_rows(golden)}
    manifest = json.loads(selection.read_text(encoding="utf-8-sig"))
    ids = manifest["ids"]
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or not ids or any(i not in rows for i in ids):
        raise ValueError("Invalid selection IDs")
    if limit is not None:
        if not 1 <= limit <= len(ids):
            raise ValueError("Limit must be within selection size")
        ids = ids[:limit]
    return [rows[i] for i in ids], validation, manifest


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def summary(rows):
    latency = [r["latency_ms"] for r in rows]
    factual = [r for r in rows if r["source_urls"]]
    success = [r for r in rows if r["status"] == "ok"]
    calls = [call for r in rows for call in r.get("model_outputs", [])]
    return {
        "cases_attempted": len(rows),
        "success": len(success),
        "errors": len(rows) - len(success),
        "outcomes": dict(Counter(r["outcome"] for r in rows)),
        "web_search_status": dict(
            Counter(r.get("trace", {}).get("web_search", {}).get("status", "not_run") for r in rows)
        ),
        "source_page_hit_at5": {
            "hits": sum(r.get("top5_source_page_hit") is True for r in factual),
            "denominator": len(factual),
            "note": "Draft page-target match; preparation failures count as misses. Generation errors do not erase "
            "retrieval hits. NOT evidence recall or correctness",
        },
        "median_latency_ms": percentile(latency, 0.5),
        "p95_latency_ms": percentile(latency, 0.95),
        "logical_model_calls": len(calls),
        "prompt_tokens": sum(c.get("prompt_tokens") or 0 for c in calls),
        "completion_tokens": sum(c.get("completion_tokens") or 0 for c in calls),
        "token_note": "Reported successful completions only; failed/cancelled provider usage may be unknown",
        "correctness": None,
        "faithfulness": None,
        "recall_at5": None,
        "precision_at5": None,
        "mrr": None,
    }


class CapturedLLM:
    """Only final response text/counters; never serialize private reasoning or model/client objects."""

    def __init__(self, delegate, max_calls=100):
        self.delegate, self.outputs, self.max_calls = delegate, [], max_calls

    def bind_model(self, **kwargs):
        return self.delegate.bind_model(**kwargs)

    async def invoke_chain(self, chain, inputs):
        if len(self.outputs) >= self.max_calls:
            raise RuntimeError("Diagnostic model call budget exhausted")
        phase = (
            "generation"
            if "persona" in inputs
            else "assessment"
            if inputs["policy"].startswith("Evaluate")
            else "rewrite"
        )
        row = {"phase": phase}
        self.outputs.append(row)
        started = time.perf_counter()
        try:
            result = await self.delegate.invoke_chain(chain, inputs)
            row.update(
                status="ok",
                content=result.content,
                finish_reason=result.finish_reason,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
            )
            return result
        except asyncio.CancelledError:
            row["status"] = "cancelled"
            raise
        except Exception as exc:
            row.update(status="error", error_type=type(exc).__name__)
            raise
        finally:
            row["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)


async def diagnose(cases, pipeline, llm, *, checkpoint=None):
    """Never pass expected answers, author quotes or URLs into model/retriever inputs."""
    from app.api.schemas.chat import ChatRequest

    rows = []
    for case in cases:
        started = time.perf_counter()
        row = {
            **case,
            "status": "error",
            "outcome": "not_finished",
            "history": [],
            "answer": None,
            "sources": [],
            "context": [],
            "trace": {},
            "model_outputs": [],
            "top5_source_page_hit": False if case["source_urls"] else None,
            "manual_review": {
                "correctness": None,
                "faithfulness": None,
                "behavior_ok": None,
                "failure_layer": None,
                "comment": "",
                "reviewer": None,
            },
        }
        rows.append(row)
        start_call = len(llm.outputs)
        prepared = None
        stage = "preparation"
        try:
            async with asyncio.timeout(pipeline.settings.chat_timeout_seconds):
                prepared = await pipeline.prepare(
                    ChatRequest(
                        message=case["question"],
                        channel="web",
                        options={"lang": case["lang"], "web_search": pipeline.settings.web_search_mode},
                    ),
                    [],
                    diagnostic_queries=True,
                )
                row["context"] = [
                    {"index": i, "point_id": hit.id, "payload": hit.payload} for i, hit in enumerate(prepared.hits, 1)
                ]
                if case["source_urls"]:
                    targets = {page(url) for url in case["source_urls"]}
                    row["top5_source_page_hit"] = any(page(h.payload["url"]) in targets for h in prepared.hits)
                stage = "generation"
                result = await pipeline.generator.generate(prepared)
            row.update(
                status="ok",
                outcome="static"
                if prepared.static_answer is not None
                else "grounded"
                if result.grounded
                else "insufficient",
                answer=result.answer,
                sources=[source.model_dump(mode="json") for source in result.sources],
                grounded=result.grounded,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            row.update(
                outcome="timeout" if isinstance(exc, TimeoutError) else "error",
                failure_stage=stage,
                error_type=type(exc).__name__,
                equivalent_http_status=getattr(exc, "status_code", None),
            )
            row["trace"] = getattr(exc, "rag_diagnostics", {})
        finally:
            if prepared is not None:
                row["trace"] = {k: v for k, v in prepared.trace.items() if k != "result"}
            row["model_outputs"] = llm.outputs[start_call:]
            row["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            if checkpoint:
                checkpoint(rows)
    return rows


def save_checkpoint(directory, report):
    temporary = directory / "report.tmp"
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(directory / "report.json")


def write_review(directory, report):
    with (directory / "manual_review.jsonl").open("x", encoding="utf-8") as stream:
        for row in report["rows"]:
            stream.write(json.dumps({"id": row["id"], **row["manual_review"]}, ensure_ascii=False) + "\n")
    sections = [
        "# Phiếu đọc kết quả golden diagnostic\n",
        "Đáp án tham chiếu chưa được TV2 duyệt. Điểm để trống, không tự coi grounded là đúng.\n",
        "Chấm correctness/faithfulness 0–2; behavior_ok true/false; ghi tầng lỗi và dẫn evidence.\n",
    ]
    for row in report["rows"]:
        sections.extend(
            [
                f"## {row['id']} · {row['lang']} · {row['category']}\n",
                f"**Hỏi:** {row['question']}\n\n**Tham chiếu (draft):** {row['expected_answer']}\n",
                f"**Kết quả:** {row['status']} / {row['outcome']} · {row['latency_ms']} ms\n",
                f"**Đáp án thật:**\n\n{row['answer'] or '(Không có đáp án hợp lệ)'}\n",
                "**Context thực cấp cho generator:**\n",
            ]
        )
        for item in row["context"]:
            payload = item["payload"]
            sections.append(f"### [{item['index']}] {payload['title']}\n\n{payload['url']}\n\n{payload['text']}\n")
        sections.append(
            "**Nhận xét / điểm:** chưa chấm. Chi tiết query, lỗi và output cuối của model trong report.json.\n"
        )
    (directory / "review.md").write_text("\n".join(sections), encoding="utf-8")


async def live(args, cases, validation, selection):
    # Explicit execution gate reached before all model/network imports and construction.
    import os

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from qdrant_client import AsyncQdrantClient

    from app.adapters.llm import DeepSeekLLM
    from app.adapters.tavily import TavilySearch
    from app.rag.pipeline import ChatPipeline
    from app.rag.retriever import HybridRetriever
    from core.config import Settings
    from core.corpus import CorpusPolicy
    from core.encoders.onnx import FastEmbedEncoder
    from core.vector.store import QdrantStore

    settings = Settings().model_copy(update={"chat_mode": "rag", "web_search_mode": args.mode, "llm_max_retries": 0})
    cache = REPO_ROOT / "backend" / settings.rag_models_dir
    if not cache.is_dir():
        raise ValueError("Configured embedding cache missing; no download allowed")
    if args.mode != "off" and not settings.web_search_available:
        raise ValueError("Tavily configuration unavailable; refusing an implicit local-only comparison")
    args.output_dir.mkdir(parents=False, exist_ok=False)
    git_head = await asyncio.to_thread(subprocess.check_output, ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True)
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "rows": [],
        "golden_validation": validation,
        "selection": selection,
        "snapshot": {
            "git_head": git_head.strip(),
            "settings": settings.model_dump(
                mode="json",
                include={
                    "chat_mode",
                    "llm_model",
                    "llm_temperature",
                    "llm_max_tokens",
                    "llm_max_retries",
                    "rag_collection",
                    "rag_corpus_policy",
                    "rag_languages",
                    "rag_rewrite_enabled",
                    "rag_query_mode",
                    "rag_top_k",
                    "rag_prefetch",
                    "rag_context_chars",
                    "rag_format_retries",
                    "rag_thinking_enabled",
                    "rag_overview_enabled",
                    "chat_timeout_seconds",
                    "web_search_mode",
                    "web_search_timeout_seconds",
                    "web_search_domains",
                    "web_search_max_results",
                    "web_search_assessment_seconds",
                },
            ),
            "input_hashes": {
                str(p.resolve().relative_to(REPO_ROOT)): digest(p)
                for p in [args.golden, args.reviews, args.selection, *sorted(PROMPTS.glob("*.md"))]
            },
            "transport_retry_override": "0 for this bounded diagnostic; application .env unchanged",
        },
        "limitations": [
            "Development subset, pending answer/source review",
            "Direct pipeline, not HTTP/UI benchmark",
            "No independent correctness/entailment score until manual review",
            "No image catalog resolution; no multi-turn histories",
            "Cold first-query latency included",
        ],
    }
    save_checkpoint(args.output_dir, report)
    client = AsyncQdrantClient(
        url=settings.qdrant_url, timeout=settings.client_timeout_seconds, check_compatibility=False
    )
    delegate, web = None, None
    try:
        info = await client.get_collection(settings.rag_collection)
        report["snapshot"]["collection_points"] = info.points_count
        delegate = DeepSeekLLM(settings)
        llm = CapturedLLM(delegate, max_calls=4 * len(cases))
        web = TavilySearch(settings) if args.mode != "off" else None
        retriever = HybridRetriever(
            FastEmbedEncoder(cache, threads=settings.rag_encoder_threads),
            QdrantStore(client, settings.rag_collection, CorpusPolicy.from_settings(settings)),
            settings.rag_prefetch,
        )
        pipeline = ChatPipeline(settings, llm, retriever, web_search=web)

        def checkpoint(rows):
            report.update(rows=rows, summary=summary(rows))
            save_checkpoint(args.output_dir, report)
            last = rows[-1]
            print(
                f"{len(rows)}/{len(cases)} {last['id']} {last['status']} {last['outcome']} {last['latency_ms']}ms",
                flush=True,
            )

        await diagnose(cases, pipeline, llm, checkpoint=checkpoint)
        report["status"] = "complete"
    finally:
        try:
            if web:
                await web.aclose()
            if delegate:
                await delegate.aclose()
        finally:
            await client.close()
            save_checkpoint(args.output_dir, report)
    write_review(args.output_dir, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=ROOT / "golden_set.jsonl")
    parser.add_argument("--reviews", type=Path, default=ROOT / "reviews/s2-golden-set-review.jsonl")
    parser.add_argument("--selection", type=Path, default=ROOT / "diagnostic_25.json")
    parser.add_argument("--mode", choices=("off", "auto", "always"), default="auto")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--allow-web", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        cases, validation, selection = load_cases(args.golden, args.reviews, args.selection, args.limit)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    if not args.execute:
        print(
            json.dumps(
                {
                    "mode": "plan_only",
                    "cases": len(cases),
                    "languages": dict(Counter(c["lang"] for c in cases)),
                    "categories": dict(Counter(c["category"] for c in cases)),
                    "search_mode": args.mode,
                    "max_logical_model_calls": 4 * len(cases),
                    "max_tavily_requests": 0 if args.mode == "off" else 2 * len(cases),
                    "review_status": validation["review_status"],
                    "limitations": selection["limitations"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    if not args.allow_llm or (args.mode != "off" and not args.allow_web):
        parser.error("Execution requires --allow-llm and, for auto/always, --allow-web")
    directory = args.output_dir
    if (
        not directory
        or directory.exists()
        or not directory.parent.is_dir()
        or not directory.resolve().is_relative_to((REPO_ROOT / "docs/testing").resolve())
    ):
        parser.error("Use a NEW output directory directly under an existing docs/testing directory")
    report = asyncio.run(live(args, cases, validation, selection))
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
