"""Fixed 20-turn live diagnostic. Plan-only by default; isolated PostgreSQL DB/memory collection."""

import argparse
import asyncio
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from core.config import REPO_ROOT

ROOT = REPO_ROOT / "backend"
MANIFEST = ROOT / "eval/agent_memory_20.json"


def plan():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    golden = {
        row["id"]: row
        for row in map(json.loads, (ROOT / "eval/golden_set.jsonl").read_text(encoding="utf-8").splitlines())
    }
    rows = [{**golden[key], "group": None} for key in manifest["standalone_ids"]]
    for scenario in manifest["scenarios"]:
        rows.extend(
            {**row, "id": f"{scenario['id']}:{i}", "lang": scenario["lang"], "group": scenario["id"]}
            for i, row in enumerate(scenario["turns"], 1)
        )
    if (
        len(rows) != 20
        or len({row["id"] for row in rows}) != 20
        or Counter(row["lang"] for row in rows) != {"vi": 10, "en": 10}
    ):
        raise ValueError("Manifest must contain exactly 20 unique turns, 10 VI and 10 EN")
    return manifest, rows


def save(directory, report, secrets=()):
    body = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    for secret in secrets:
        if secret and len(secret) >= 8:
            body = body.replace(secret, "[REDACTED]")
    temporary = directory / "report.tmp"
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(directory / "report.json")


async def execute(args, manifest, cases):
    # Set before importing model-related modules; no missing-cache downloads are allowed.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["LANGSMITH_TRACING"] = "false"
    import asyncpg
    import httpx
    from alembic import command
    from alembic.config import Config
    from qdrant_client import AsyncQdrantClient
    from redis.asyncio import Redis

    from app.context import build_context
    from app.main import create_app
    from app.rag.semantic_memory import MemoryVectors
    from app.services.factory import build_chat_service
    from core.config import Settings
    from scripts.diagnose_gameplay import CountedLLM

    base = Settings()
    secret_values = [
        v.get_secret_value() for v in (base.deepseek_api_key, base.tavily_api_key, base.api_service_token) if v
    ]
    suffix = uuid4().hex[:10]
    database = f"indexbeast_agent_test_{suffix}"
    collection = f"ib_agent_test_{suffix}"
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "status": "preflight",
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "planned_turns": 20,
        "attempted_turns": 0,
        "rows": [],
        "preflight": [],
        "test_database": database,
        "test_memory_collection": collection,
        "logical_model_calls": [],
        "tavily_requests": [],
        "transport": "in-process ASGI HTTP, real model/tools/encoder when preflight passes",
        "limitations": [
            "Development set; no independent human review",
            "HTTP success is not correctness",
            "Service recreation tests state restoration, not a Windows reboot",
            "SSE usage may be unavailable",
        ],
    }
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output, report, secret_values)
    client = AsyncQdrantClient(url=base.qdrant_url, timeout=3)
    redis = Redis.from_url(base.redis_url, socket_timeout=3, socket_connect_timeout=3)
    ctx = None
    stage = "configuration"
    try:
        if not base.deepseek_api_key or not base.web_search_available or not (ROOT / base.rag_models_dir).is_dir():
            raise ValueError("Configured model/search and local model cache required")
        # Read-only probes precede resource creation and any paid call.
        stage = "PostgreSQL"
        conn = await asyncpg.connect(
            host=base.postgres_host,
            port=base.postgres_port,
            user=base.postgres_user,
            password=base.postgres_password.get_secret_value(),
            database=base.postgres_db,
            timeout=3,
        )
        await conn.close()
        report["preflight"].append({"resource": stage, "status": "ok"})
        stage = "Qdrant corpus"
        report["corpus_points_before"] = (await client.get_collection(base.rag_collection)).points_count
        report["preflight"].append({"resource": stage, "status": "ok"})
        stage = "Redis"
        await redis.ping()
        report["preflight"].append({"resource": stage, "status": "ok"})
        stage = "isolated resources"
        if not re.fullmatch(r"indexbeast_agent_test_[a-f0-9]{10}", database) or database == base.postgres_db:
            raise ValueError("Unsafe test resource name")
        admin = await asyncpg.connect(
            host=base.postgres_host,
            port=base.postgres_port,
            user=base.postgres_user,
            password=base.postgres_password.get_secret_value(),
            database="postgres",
            timeout=3,
        )
        try:
            await admin.execute(f'CREATE DATABASE "{database}"')
        finally:
            await admin.close()
        settings = base.model_copy(
            update={
                "postgres_db": database,
                "chat_mode": "rag",
                "chat_persistence": "postgres",
                "chat_agent_enabled": True,
                "chat_agent_max_calls": 6,
                "chat_memory_collection": collection,
                "web_search_mode": "auto",
                "llm_max_retries": 0,
                "rate_limit_per_minute": 1000,
            }
        )
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.attributes["configure_logger"] = False
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
        await asyncio.to_thread(command.upgrade, cfg, "head")
        vectors = MemoryVectors(client, collection, base.rag_collection)
        await vectors.setup()
        ctx = build_context(settings)
        # ASGI client address below gives rate-limit keys a unique test-only namespace.

        class CountedAgent(CountedLLM):
            def start(self, inputs, streaming=False):
                row = super().start(inputs, streaming)
                if inputs.get("policy", "").startswith("You are IndexBeast's request decision"):
                    row["phase"] = "decision"
                return row

        counted = CountedAgent(ctx.llm, 120)
        ctx.llm = counted
        original_post = ctx.web_search._post
        tool_counts = Counter()

        async def post(endpoint, payload):
            tool_counts[endpoint] += 1
            if tool_counts[endpoint] > 1 or endpoint not in {"search", "extract"}:
                raise RuntimeError("Per-turn Tavily budget exceeded")
            row = {"endpoint": endpoint, "status": "running"}
            report["tavily_requests"].append(row)
            try:
                data = await original_post(endpoint, payload)
                row["status"] = "ok"
                return data
            except BaseException as exc:
                row.update(status="error", error_type=type(exc).__name__)
                raise

        ctx.web_search._post = post
        report["snapshot"] = {
            key: getattr(settings, key)
            for key in (
                "llm_model",
                "llm_temperature",
                "llm_max_tokens",
                "rag_thinking_enabled",
                "rag_collection",
                "rag_top_k",
                "chat_timeout_seconds",
                "chat_agent_max_calls",
            )
        }
        app = create_app(settings, context=ctx)
        groups = {}
        stage = "live requests"
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, client=(f"ib-agent-{suffix}", 1)),
                base_url="http://agent-test",
                timeout=90,
            ) as http,
        ):
            # Warm only the cached encoder; this is not a hidden model/API diagnostic question.
            await app.state.chat_service.pipeline.retriever.encoder.encode_dense(["Ranni"], query=True)
            report["status"] = "running"
            for case in cases:
                if report["attempted_turns"] >= 20:
                    raise RuntimeError("Turn limit exceeded")
                group = groups.get(case["group"], {}) if case["group"] else {}
                if case.get("restart_before"):
                    app.state.chat_service = build_chat_service(ctx, image_catalog=app.state.image_catalog)
                service = app.state.chat_service
                observed = {}
                original_prepare = service.pipeline.prepare

                async def track(*a, _prepare=original_prepare, _observed=observed, **kw):
                    kw["diagnostic_queries"] = True
                    prepared = await _prepare(*a, **kw)
                    _observed["prepared"] = prepared
                    return prepared

                service.pipeline.prepare = track
                tool_counts.clear()
                start_calls = len(counted.calls)
                row = {
                    "id": case["id"],
                    "question": case["question"],
                    "lang": case["lang"],
                    "group": case["group"],
                    "expected": case.get("expected", case.get("expected_answer")),
                    "status": "running",
                    "manual_correctness": None,
                    "manual_faithfulness": None,
                }
                report["rows"].append(row)
                report["attempted_turns"] += 1
                save(args.output, report, secret_values)
                started = time.perf_counter()
                try:
                    body = {
                        "message": case["question"],
                        "channel": "web",
                        "turn_id": str(uuid4()),
                        "options": {"web_search": "auto", "lang": case["lang"], "spoilers": True},
                        **group,
                    }
                    endpoint = case.get("endpoint", "chat")
                    response = await http.post("/api/v1/" + endpoint, json=body)
                    row["http_status"] = response.status_code
                    if response.status_code != 200:
                        row.update(status="error", error=response.json().get("code", "http_error"))
                    else:
                        if endpoint == "chat":
                            data = response.json()
                        else:
                            events = []
                            for frame in response.text.split("\n\n"):
                                lines = frame.splitlines()
                                event = next((line[7:] for line in lines if line.startswith("event: ")), None)
                                value = next(
                                    (json.loads(line[6:]) for line in lines if line.startswith("data: ")), None
                                )
                                if event:
                                    events.append((event, value))
                            if not events or events[-1][0] != "done":
                                raise ValueError("SSE did not finish successfully")
                            data = {
                                **events[-1][1],
                                "answer": "".join(v["token"] for k, v in events if k == "token"),
                                **next((v for k, v in events if k == "sources"), {}),
                            }
                        if case["group"]:
                            groups[case["group"]] = {
                                "conversation_id": data["conversation_id"],
                                "conversation_token": data.get("conversation_token"),
                            }
                        data.pop("conversation_token", None)
                        row.update(status="ok", response=data)
                    prepared = observed.get("prepared")
                    if prepared:
                        row["trace"] = {k: v for k, v in prepared.trace.items() if k != "result"}
                        row["resolved_question"] = json.loads(prepared.values["payload"])["question"]
                        row["evidence_ids"] = [h.id for h in prepared.hits]
                except Exception as exc:
                    row.update(status="error", error_type=type(exc).__name__)
                finally:
                    service.pipeline.prepare = original_prepare
                    row["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
                    row["model_calls"] = counted.calls[start_calls:]
                    report["logical_model_calls"] = counted.calls
                    save(args.output, report, secret_values)
            report["corpus_points_after"] = (await client.get_collection(base.rag_collection)).points_count
            report["status"] = "complete"
            report["summary"] = {
                "outcomes": dict(Counter(r["status"] for r in report["rows"])),
                "logical_model_calls": len(counted.calls),
                "tavily_requests": len(report["tavily_requests"]),
                "prompt_tokens_known": sum(c.get("prompt_tokens") or 0 for c in counted.calls),
                "completion_tokens_known": sum(c.get("completion_tokens") or 0 for c in counted.calls),
                "unknown_usage_calls": sum(c.get("prompt_tokens") is None for c in counted.calls),
            }
    except Exception as exc:
        report["status"] = "blocked" if not report["attempted_turns"] else "interrupted"
        report["preflight"].append({"resource": stage, "status": "error", "error_type": type(exc).__name__})
    except BaseException:
        report["status"] = "interrupted"
        raise
    finally:
        save(args.output, report, secret_values)
        if ctx:
            await ctx.aclose()
        await client.close()
        await redis.aclose()
    print(
        json.dumps(
            {
                "status": report["status"],
                "planned": 20,
                "attempted": report["attempted_turns"],
                "report": str(args.output / "report.json"),
            },
            ensure_ascii=False,
        )
    )
    return report["status"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--allow-web", action="store_true")
    parser.add_argument("--allow-embedding", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    manifest, cases = plan()
    if not args.execute:
        print(
            json.dumps(
                {
                    "mode": "PLAN ONLY",
                    "turns": 20,
                    "languages": dict(Counter(r["lang"] for r in cases)),
                    "ids": [r["id"] for r in cases],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if not all((args.allow_llm, args.allow_web, args.allow_embedding, args.output)):
        parser.error("Execution requires --allow-llm --allow-web --allow-embedding --output NEW_DIRECTORY")
    if asyncio.run(execute(args, manifest, cases)) != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
