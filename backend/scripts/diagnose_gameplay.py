"""Bounded real HTTP JSON/SSE diagnostic. Plan-only unless explicitly --execute --allow-llm --allow-web."""

import argparse
import asyncio
import hashlib
import json
import os
import socket
import time
from collections import Counter
from contextlib import aclosing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from core.config import REPO_ROOT

ROOT = REPO_ROOT / "backend"


def plan():
    manifest = json.loads((ROOT / "eval/gameplay_diagnostic_25.json").read_text(encoding="utf-8"))
    golden = {
        r["id"]: r for r in map(json.loads, (ROOT / "eval/golden_set.jsonl").read_text(encoding="utf-8").splitlines())
    }
    scenarios = json.loads((ROOT / "eval/gameplay_scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    rows = [{**golden[key], "mode": "auto", "group": None} for key in manifest["standalone_ids"]]
    for scenario in scenarios:
        if scenario["id"] in manifest["scenario_ids"]:
            rows.extend(
                {
                    "id": f"{scenario['id']}:{i}",
                    "question": text,
                    "lang": "vi",
                    "mode": "auto",
                    "group": scenario["id"],
                    "expected_behavior": scenario["expected"],
                }
                for i, text in enumerate(scenario["turns"], 1)
            )
    assert len(rows) == 25
    rows.extend({**golden[key], "mode": "off", "group": None} for key in manifest["paired_off_ids"])
    assert len(rows) == 30
    for row in rows:
        row["endpoint"] = "chat/stream" if row["id"] in manifest["sse_ids"] else "chat"
        row["channel"] = "discord" if row["id"] in manifest["discord_ids"] else "web"
    return manifest, rows


def save(directory, report):
    temporary = directory / "report.tmp"
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(directory / "report.json")


class CountedLLM:
    def __init__(self, delegate, maximum):
        self.delegate, self.maximum, self.calls = delegate, maximum, []

    def bind_model(self, **kwargs):
        return self.delegate.bind_model(**kwargs)

    def start(self, inputs, streaming=False):
        if len(self.calls) >= self.maximum:
            raise RuntimeError("Logical LLM call budget exhausted")
        row = {
            "phase": "generation"
            if "persona" in inputs
            else "assessment"
            if inputs["policy"].startswith("Evaluate")
            else "rewrite",
            "streaming": streaming,
            "status": "running",
        }
        self.calls.append(row)
        return row

    async def invoke_chain(self, chain, inputs):
        row = self.start(inputs)
        try:
            result = await self.delegate.invoke_chain(chain, inputs)
            row.update(
                status="ok",
                content=result.content,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                finish_reason=result.finish_reason,
            )
            return result
        except BaseException as exc:
            row.update(status="error", error_type=type(exc).__name__)
            raise

    async def stream_chain(self, chain, inputs):
        row = self.start(inputs, True)
        parts = []
        try:
            async with aclosing(self.delegate.stream_chain(chain, inputs)) as stream:
                async for part in stream:
                    parts.append(part)
                    yield part
            row.update(status="ok", content="".join(parts), prompt_tokens=None, completion_tokens=None)
        except BaseException as exc:
            row.update(status="error", content="".join(parts), error_type=type(exc).__name__)
            raise


def summary(rows, llm, tavily, planned):
    from scripts.diagnose_golden import percentile

    successful = [r for r in rows if r["status"] == "ok"]
    return {
        "planned_prompts": len({r["id"] for r in planned}),
        "planned_http_requests": len(planned),
        "recorded_cases": len(rows),
        "http_responses": sum("http_status" in r for r in rows),
        "valid_responses": len(successful),
        "errors_or_skipped": len(rows) - len(successful),
        "outcomes": dict(Counter(r.get("outcome", "error") for r in rows)),
        "web_status": dict(Counter(r.get("trace", {}).get("web_search", {}).get("status", "not_run") for r in rows)),
        "logical_llm_calls": len(llm.calls),
        "tavily_requests": len(tavily),
        "prompt_tokens_known": sum(c.get("prompt_tokens") or 0 for c in llm.calls),
        "completion_tokens_known": sum(c.get("completion_tokens") or 0 for c in llm.calls),
        "unknown_usage_calls": sum(c.get("prompt_tokens") is None for c in llm.calls),
        "p50_ms": percentile([r["latency_ms"] for r in rows], 0.5),
        "p95_ms": percentile([r["latency_ms"] for r in rows], 0.95),
        "correctness": None,
        "faithfulness": None,
        "notice": "Valid/grounded protocol is not correctness; SSE usage and failed request billing may be unknown.",
    }


async def execute(args, manifest, cases):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import httpx
    import uvicorn

    from app.context import build_context
    from app.main import create_app
    from core.config import Settings

    settings = Settings().model_copy(
        update={
            "llm_max_retries": 0,
            "chat_mode": "rag",
            "rate_limit_per_minute": 1000,
            "gameplay_clarification_enabled": True,
            "gameplay_knowledge_enabled": True,
        }
    )
    if not (ROOT / settings.rag_models_dir).is_dir() or not settings.web_search_available:
        raise ValueError("Cached encoder and configured web search are required; no downloads or implicit fallback")
    ctx = build_context(settings)
    if ctx.llm is None:
        await ctx.aclose()
        raise ValueError("DeepSeek not configured")
    llm = CountedLLM(ctx.llm, manifest["max_llm_calls"])
    ctx.llm = llm
    tavily = []
    original_post = ctx.web_search._post

    async def counted_post(endpoint, payload):
        if len(tavily) >= manifest["max_tavily_requests"]:
            raise RuntimeError("Tavily request budget exhausted")
        row = {"endpoint": endpoint, "status": "started"}
        tavily.append(row)
        try:
            result = await original_post(endpoint, payload)
            row["status"] = "ok"
            return result
        except BaseException as exc:
            row.update(status="error", error_type=type(exc).__name__)
            raise

    ctx.web_search._post = counted_post
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "manifest": manifest,
        "rows": [],
        "snapshot": settings.model_dump(
            mode="json",
            include={
                "llm_model",
                "llm_temperature",
                "llm_max_tokens",
                "rag_thinking_enabled",
                "rag_rewrite_enabled",
                "rag_collection",
                "rag_corpus_policy",
                "rag_languages",
                "rag_top_k",
                "rag_prefetch",
                "rag_context_chars",
                "chat_timeout_seconds",
                "rag_format_retries",
                "gameplay_clarification_enabled",
                "gameplay_knowledge_enabled",
            },
        ),
        "hashes": {
            str(p.relative_to(REPO_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                ROOT / "eval/golden_set.jsonl",
                ROOT / "eval/gameplay_diagnostic_25.json",
                ROOT / "app/rag/knowledge/gameplay.json",
                *sorted((ROOT / "app/rag/prompts").glob("*.md")),
                *sorted((ROOT / "app/rag").glob("*.py")),
                *sorted((ROOT / "app/services").glob("*.py")),
            ]
        },
        "overrides": {
            "transport_retries": 0,
            "rate_limit_per_minute": 1000,
            "bind": "loopback only; separate diagnostic server",
        },
        "limitations": [
            "Development cases, draft author labels",
            "No production DB writes or corpus reindex",
            "No persistent conversation state after restart",
            "Unknown usage for SSE/failed calls",
            "No independent human review",
        ],
    }
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output, report)
    sock = socket.socket()
    server, server_task = None, None
    try:
        info = await ctx.qdrant.get_collection(settings.rag_collection)
        report["collection_points_before"] = info.points_count
        sock.bind(("127.0.0.1", args.port))
        sock.listen(16)
        app = create_app(settings, context=ctx)
        async with app.router.lifespan_context(app):
            service = app.state.chat_service
            observed = {}
            original_prepare = service.pipeline.prepare

            async def tracked_prepare(*a, **kw):
                kw["diagnostic_queries"] = True
                prepared = await original_prepare(*a, **kw)
                observed["prepared"] = prepared
                return prepared

            service.pipeline.prepare = tracked_prepare
            server = uvicorn.Server(uvicorn.Config(app, lifespan="off", access_log=False, log_level="warning"))
            server_task = asyncio.create_task(server.serve(sockets=[sock]))
            async with asyncio.timeout(10):
                while not server.started:
                    if server_task.done():
                        await server_task
                        raise RuntimeError("Diagnostic server did not start")
                    await asyncio.sleep(0.05)
            groups = {}
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{args.port}/api/v1", timeout=60, trust_env=False
            ) as client:
                for case in cases:
                    started, start_llm, start_web = time.perf_counter(), len(llm.calls), len(tavily)
                    observed.clear()
                    row = {**case, "status": "error"}
                    report["rows"].append(row)
                    body = {
                        "message": case["question"],
                        "channel": case["channel"],
                        "options": {"lang": case["lang"], "spoilers": True, "web_search": case["mode"]},
                    }
                    prior = groups.get(case["group"])
                    if prior:
                        body["conversation_id"] = prior["conversation_id"]
                        if prior.get("clarification"):
                            body["clarification_id"] = prior["clarification"]["id"]
                    headers = {}
                    if case["channel"] == "discord":
                        body["external_ref"] = "diagnostic:" + uuid4().hex
                        if settings.api_service_token:
                            headers["X-Service-Token"] = settings.api_service_token.get_secret_value()
                    try:
                        response = await client.post("/" + case["endpoint"], json=body, headers=headers)
                        row["http_status"] = response.status_code
                        if response.status_code != 200:
                            row["error"] = response.json()
                        else:
                            if case["endpoint"].endswith("stream"):
                                frames = []
                                for frame in response.text.split("\n\n"):
                                    lines = frame.splitlines()
                                    if len(lines) >= 2 and lines[0].startswith("event: "):
                                        frames.append((lines[0][7:], json.loads(lines[1][6:])))
                                done = next((p for name, p in frames if name == "done"), None)
                                row["sse_events"] = [name for name, _ in frames]
                                if not done:
                                    row["sse_errors"] = [p for name, p in frames if name == "error"]
                                    raise ValueError("SSE completed without successful done; see saved frames")
                                sources = next((p for name, p in frames if name == "sources"), {})
                                data = {
                                    **done,
                                    **sources,
                                    "answer": "".join(p["token"] for name, p in frames if name == "token"),
                                }
                                row["sse_events"] = [name for name, _ in frames]
                            else:
                                data = response.json()
                            row.update(
                                status="ok",
                                response=data,
                                outcome="clarification"
                                if data.get("clarification")
                                else "grounded"
                                if data.get("grounded")
                                else "insufficient_or_static",
                            )
                            if case["group"]:
                                groups[case["group"]] = data
                            trace = service.traces.get(__import__("uuid").UUID(data["message_id"]), {})
                            row["trace"] = trace
                    except Exception as exc:
                        row.update(error_type=type(exc).__name__)
                    if "prepared" in observed:
                        prepared = observed["prepared"]
                        row["context"] = [
                            {"index": i, "id": h.id, "payload": h.payload} for i, h in enumerate(prepared.hits, 1)
                        ]
                        row.setdefault("trace", {k: v for k, v in prepared.trace.items() if k != "result"})
                    row.update(
                        latency_ms=round((time.perf_counter() - started) * 1000, 2),
                        model_outputs=llm.calls[start_llm:],
                        tavily=tavily[start_web:],
                    )
                    report["summary"] = summary(report["rows"], llm, tavily, cases)
                    save(args.output, report)
                    print(
                        f"{len(report['rows'])}/{len(cases)} {case['id']} {case['mode']} {row['status']} "
                        f"{row.get('outcome', row.get('http_status'))} "
                        f"LLM={len(llm.calls) - start_llm} web={len(tavily) - start_web}",
                        flush=True,
                    )
            report["collection_points_after"] = (await ctx.qdrant.get_collection(settings.rag_collection)).points_count
            report["status"] = "complete"
    finally:
        if server:
            server.should_exit = True
        if server_task:
            await server_task
        sock.close()
        await ctx.aclose()
        save(args.output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--allow-web", action="store_true")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--only",
        nargs="+",
        help="Focused AUTO retest of listed IDs or scenario groups; never rerun the whole set implicitly",
    )
    args = parser.parse_args()
    manifest, rows = plan()
    if args.only:
        rows = [r for r in rows if r["mode"] == "auto" and (r["id"] in args.only or r["group"] in args.only)]
        if not rows or len(rows) > 10:
            parser.error("Focused retest must select 1–10 existing AUTO prompts")
    if not args.execute:
        print(
            json.dumps(
                {
                    "prompts": len({r["id"] for r in rows}),
                    "http_requests": len(rows),
                    "paired_off": sum(r["mode"] == "off" for r in rows),
                    "llm_cap": manifest["max_llm_calls"],
                    "tavily_cap": manifest["max_tavily_requests"],
                }
            )
        )
        return
    if not (
        args.allow_llm
        and args.allow_web
        and args.port
        and 10000 < args.port < 65536
        and args.output
        and not args.output.exists()
        and args.output.resolve().is_relative_to((REPO_ROOT / "docs/testing").resolve())
    ):
        parser.error("Require explicit API allowances, a project port and a NEW docs/testing output directory")
    result = asyncio.run(execute(args, manifest, rows))
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
