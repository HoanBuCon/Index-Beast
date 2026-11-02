"""Opt-in paid/manual acceptance checks against a running local API and real Qdrant corpus."""

import argparse
import asyncio
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi.testclient import TestClient
from qdrant_client import AsyncQdrantClient

from app.main import create_app
from app.rag.pipeline import select_context
from app.rag.retriever import HybridRetriever
from core.config import REPO_ROOT, Settings
from core.corpus import CorpusPolicy
from core.encoders.onnx import FastEmbedEncoder
from core.vector.store import QdrantStore
from ingest.indexing import inspect_artifact

CASES = [
    ("VI01", "vi", "Ranni là ai và cha mẹ cô là ai?", "lore"),
    ("VI02", "vi", "Vì sao Godwyn được gọi là Prince of Death?", "lore"),
    ("VI03", "vi", "Messmer là ai? Nêu rõ nếu thông tin thuộc bản mở rộng.", "related_release"),
    ("VI04", "vi", "Mối liên hệ giữa Miquella và St. Trina là gì theo nguồn?", "related_release"),
    ("VI05", "vi", "Hãy viết chương trình Python tính Fibonacci.", "out_of_scope"),
    ("EN01", "en", "Who is Melina and what does she ask the Tarnished to do?", "lore"),
    ("EN02", "en", "What is the role of the Greater Will in the Lands Between?", "lore"),
    ("EN03", "en", "Who is Rellana, and how is she related to Rennala?", "related_release"),
    ("EN04", "en", "Explain the connection between the Twinbird and Deathbirds.", "lore"),
    ("EN05", "en", "What is the confirmed connection between Nightreign and Ranni's ending?", "missing_relationship"),
]


def now():
    return datetime.now(timezone(timedelta(hours=7))).isoformat()


def save(path: Path, report: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def acceptance_summary(result: dict) -> dict:
    failures = []
    if result.get("health", {}).get("http_status") != 200:
        failures.append("health")
    for row in result.get("cases", []):
        body = row.get("response", {})
        if row.get("http_status") != 200:
            failures.append(f"{row['id']}:http")
            continue
        negative = row["category"] in {"out_of_scope", "missing_relationship"}
        if negative:
            if body.get("grounded") is not False or body.get("sources"):
                failures.append(f"{row['id']}:negative_grounding")
        elif body.get("grounded") is not True or row.get("source_quotes_verbatim_in_artifact") is not True:
            failures.append(f"{row['id']}:grounding")
    sse = result.get("sse", {})
    if (
        result.get("sse_http_status") != 200
        or not sse.get("done")
        or sse.get("errors")
        or not sse.get("sources")
        or not sse.get("answer")
        or sse.get("done", {}).get("grounded") is not True
    ):
        failures.append("sse")
    llm = result.get("llm_only", {})
    if (
        llm.get("http_status") != 200
        or llm.get("response", {}).get("grounded") is not False
        or llm.get("response", {}).get("sources")
    ):
        failures.append("llm_only")
    history = result.get("history_feedback", {})
    if (
        history.get("history_http_status") != 200
        or history.get("feedback_http_status") != 204
        or history.get("message_count") != 2
    ):
        failures.append("history_feedback")
    if (
        any(row["id"] == "EN04" for row in result.get("cases", []))
        and result.get("cross_channel_isolation_http_status") != 404
    ):
        failures.append("channel_isolation")
    return {
        "passed": not failures,
        "failures": failures,
        "qa_http_200": sum(r.get("http_status") == 200 for r in result.get("cases", [])),
        "qa_count": len(result.get("cases", [])),
    }


async def run(args):
    settings = Settings()
    policy = CorpusPolicy.from_settings(settings)
    source = REPO_ROOT / "backend/data/chunk_runs/s2-full-v1/chunks.jsonl"
    inspection = inspect_artifact(source, policy)
    by_url = defaultdict(list)
    for chunk in inspection.chunks:
        by_url[chunk.url].append(chunk.text)
    result = {
        "started_at": now(),
        "api_url": args.api_url,
        "model": settings.llm_model,
        "llm_max_tokens": settings.llm_max_tokens,
        "evidence_protocol": "server_quote_ids_v1",
        "collection": settings.rag_collection,
        "policy": policy.mode,
        "languages": list(policy.languages),
        "encoder_threads": settings.rag_encoder_threads,
        "rag_thinking_enabled": settings.rag_thinking_enabled,
        "source_sha256": inspection.sha256,
        "selected_records": len(inspection.chunks),
        "cases": [],
        "limitations": [
            "Quote/citation checks are formal checks, not semantic entailment or independent lore verification.",
            "Retrieval snapshots are separate queries with the same pipeline policy; tied results may differ.",
            "No private reasoning, credentials or HTTP authentication headers are persisted.",
        ],
    }
    report = json.loads(args.report.read_text(encoding="utf-8")) if args.report.exists() else {"runs": []}
    report["runs"].append(result)
    save(args.report, report)
    client = AsyncQdrantClient(url=settings.qdrant_url, check_compatibility=False)
    try:
        store = QdrantStore(client, settings.rag_collection, policy)
        retriever = HybridRetriever(
            FastEmbedEncoder(REPO_ROOT / "backend" / settings.rag_models_dir, threads=settings.rag_encoder_threads),
            store,
            limit=settings.rag_prefetch,
        )
        result["qdrant_exact_count"] = (await client.count(settings.rag_collection, exact=True)).count
        if result["qdrant_exact_count"] != len(inspection.chunks):
            raise RuntimeError("Finish indexing the selected corpus before running paid QA checks")
        async with httpx.AsyncClient(base_url=args.api_url, timeout=180) as api:
            health = await api.get("/api/v1/health")
            result["health"] = {"http_status": health.status_code, "body": health.json()}
            consecutive_errors = 0
            for identifier, lang, question, category in CASES:
                if args.ids and identifier not in args.ids:
                    continue
                channel = "discord" if identifier == "EN04" else "web"
                row = {"id": identifier, "lang": lang, "question": question, "category": category, "channel": channel}
                if category != "out_of_scope":
                    hits = await retriever.retrieve(question, spoilers=True)
                    selected = select_context(hits, settings.rag_top_k, settings.rag_context_chars, policy=policy)
                    row["retrieval_snapshot"] = [
                        {
                            "point_id": h.id,
                            "artifact_chunk_id": h.payload.get("artifact_chunk_id"),
                            "score": h.score,
                            "title": h.payload["title"],
                            "url": h.payload["url"],
                            "lang": h.payload.get("lang"),
                            "release_scope": h.payload.get("release_scope"),
                            "source_type": h.payload.get("source_type"),
                            "review_status": h.payload.get("review_status"),
                            "text_sha256": hashlib.sha256(h.payload["text"].encode()).hexdigest(),
                            "excerpt": h.payload["text"][:250],
                        }
                        for h in selected
                    ]
                started = time.perf_counter()
                response = await api.post(
                    "/api/v1/chat",
                    json={
                        "message": question,
                        "channel": channel,
                        "external_ref": "discord:integration-test" if channel == "discord" else None,
                        "options": {"lang": lang, "spoilers": True},
                    },
                )
                row.update(
                    http_status=response.status_code,
                    elapsed_seconds=round(time.perf_counter() - started, 3),
                    response=response.json(),
                )
                sources = row["response"].get("sources", [])
                row["source_quotes_verbatim_in_artifact"] = (
                    all(
                        source.get("text") and any(source["text"] in text for text in by_url[source["url"]])
                        for source in sources
                    )
                    if sources
                    else None
                )
                result["cases"].append(row)
                save(args.report, report)
                print(
                    json.dumps(
                        {
                            "id": identifier,
                            "http_status": response.status_code,
                            "grounded": row["response"].get("grounded"),
                            "sources": len(sources),
                            "seconds": row["elapsed_seconds"],
                        }
                    ),
                    flush=True,
                )
                consecutive_errors = consecutive_errors + 1 if response.is_error else 0
                if consecutive_errors >= 3:
                    raise RuntimeError("Stopped after three consecutive API errors")
            completed = next((r for r in result["cases"] if r["http_status"] == 200), None)
            if completed:
                body = completed["response"]
                history = await api.get(f"/api/v1/conversations/{body['conversation_id']}")
                feedback = await api.post("/api/v1/feedback", json={"message_id": body["message_id"], "rating": 1})
                result["history_feedback"] = {
                    "history_http_status": history.status_code,
                    "message_count": len(history.json().get("messages", [])),
                    "feedback_http_status": feedback.status_code,
                }
            discord_case = next((r for r in result["cases"] if r["id"] == "EN04" and r["http_status"] == 200), None)
            if discord_case:
                isolation = await api.post(
                    "/api/v1/chat",
                    json={
                        "message": "Who is Ranni?",
                        "channel": "web",
                        "conversation_id": discord_case["response"]["conversation_id"],
                    },
                )
                result["cross_channel_isolation_http_status"] = isolation.status_code
            frames, event, data = [], "", []
            async with api.stream(
                "POST",
                "/api/v1/chat/stream",
                json={
                    "message": "Twinbird và Deathbirds có quan hệ gì?",
                    "channel": "web",
                    "options": {"lang": "vi", "spoilers": True},
                },
            ) as stream:
                result["sse_http_status"] = stream.status_code
                async for line in stream.aiter_lines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data.append(line[5:].strip())
                    elif not line and data:
                        frames.append((event, json.loads("\n".join(data))))
                        event, data = "", []
            result["sse"] = {
                "event_counts": dict(Counter(n for n, _ in frames)),
                "event_sequence": [n for n, _ in frames],
                "answer": "".join(d.get("token", "") for n, d in frames if n == "token"),
                "sources": next((d.get("sources", []) for n, d in frames if n == "sources"), []),
                "done": next((d for n, d in frames if n == "done"), None),
                "errors": [d for n, d in frames if n == "error"],
            }
            save(args.report, report)
        # Real-provider llm_only through the same FastAPI lifespan/routes; no socket server or env edits.
        with TestClient(create_app(Settings(chat_mode="llm_only", environment="test"))) as api:
            response = api.post(
                "/api/v1/chat",
                json={"message": "Who is the Twinbird?", "channel": "web", "options": {"lang": "en", "spoilers": True}},
            )
            result["llm_only"] = {
                "transport": "in-process ASGI with real provider",
                "http_status": response.status_code,
                "response": response.json(),
            }
        result["finished_at"] = now()
        result["summary"] = acceptance_summary(result)
        save(args.report, report)
        print(
            json.dumps(
                {
                    "cases": len(result["cases"]),
                    "sse_done": bool(result["sse"]["done"]),
                    "llm_only_status": result["llm_only"]["http_status"],
                    "report": str(args.report),
                }
            ),
            flush=True,
        )
        return result["summary"]["passed"]
    except Exception as exc:
        result["failure"] = {"error_type": type(exc).__name__, "status_code": getattr(exc, "status_code", None)}
        result["finished_at"] = now()
        save(args.report, report)
        raise
    finally:
        await client.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-paid", action="store_true", help="Explicitly authorize real model/query calls")
    parser.add_argument("--api-url", default="http://127.0.0.1:18000")
    parser.add_argument("--ids", help="Optional comma-separated QA case IDs")
    parser.add_argument("--report", type=Path, default=REPO_ROOT / "docs/testing/2026-10-29_rag-live-results.json")
    args = parser.parse_args(argv)
    if not args.allow_paid:
        parser.error(
            "This test uses real embeddings, Qdrant reads and paid DeepSeek calls; pass --allow-paid explicitly"
        )
    address = urlsplit(args.api_url)
    if (
        address.hostname not in {"127.0.0.1", "localhost", "::1"}
        or address.username
        or address.password
        or address.query
        or address.fragment
        or address.path not in {"", "/"}
    ):
        parser.error("Use a local API URL without credentials, path or query")
    args.ids = set(args.ids.split(",")) if args.ids else None
    if args.ids and not args.ids.issubset({case[0] for case in CASES}):
        parser.error("Unknown QA case ID")
    try:
        passed = asyncio.run(run(args))
    except Exception as exc:
        print(json.dumps({"failed": True, "error_type": type(exc).__name__}))
        return 2
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
