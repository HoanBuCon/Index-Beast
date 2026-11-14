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


def remaining_cases(report, cases):
    spent = report["attempted_turns"]
    if (
        type(spent) is not int
        or not 0 <= spent <= len(cases)
        or len(report["rows"]) != spent
        or [r["id"] for r in report["rows"]] != [c["id"] for c in cases[:spent]]
    ):
        raise ValueError("Invalid checkpoint; do not replay uncertain/spent turns")
    return cases[spent:]


def private_state(path, groups):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(groups), encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(path)


def chat_payload(response, endpoint):
    if endpoint == "chat":
        return response.json()
    events = []
    for frame in response.text.split("\n\n"):
        lines = frame.splitlines()
        event = next((line[7:] for line in lines if line.startswith("event: ")), None)
        value = next((json.loads(line[6:]) for line in lines if line.startswith("data: ")), None)
        if event:
            events.append((event, value))
    if not events or events[-1][0] != "done":
        raise ValueError("SSE did not finish successfully")
    return {
        **events[-1][1],
        "answer": "".join(v["token"] for k, v in events if k == "token"),
        **next((v for k, v in events if k == "sources"), {}),
    }


async def run_case(http, case, group, row, groups, state_path, *, case_budget, checkpoint):
    endpoint = case.get("endpoint", "chat")
    answers = iter(case.get("clarification_answers", []))
    message = case["question"]
    continuation = dict(group)
    while True:
        body = {
            "message": message,
            "channel": "web",
            "turn_id": str(uuid4()),
            "options": {"web_search": case.get("web_search", "auto"), "lang": case["lang"], "spoilers": True},
            **continuation,
        }
        response = await http.post("/api/v1/" + endpoint, json=body)
        row["http_status"] = response.status_code
        if case_budget:
            row.setdefault("http_turns", []).append({"message": message, "http_status": response.status_code})
        if response.status_code != 200:
            row.update(status="error", error=response.json().get("code", "http_error"))
            return None
        data = chat_payload(response, endpoint)
        continuation = {
            "conversation_id": data["conversation_id"],
            "conversation_token": data.pop("conversation_token", None),
        }
        if case["group"]:
            groups[case["group"]] = continuation
        if case_budget:
            row["http_turns"][-1]["response"] = data
            groups[case["id"]] = continuation
        await asyncio.to_thread(private_state, state_path, groups)
        clarification = data.get("clarification")
        if not case_budget or not clarification:
            row.update(status="ok", response=data)
            return data
        message = next(answers, None)
        if message is None:
            row.update(status="incomplete", error="clarification_answer_missing", response=data)
            return None
        continuation = {**continuation, "clarification_id": clarification["id"]}
        checkpoint()


def continuation_case(case, row, group):
    previous_turns = row["http_turns"][row.get("restart_offset", 0) :]
    if not previous_turns or "response" in previous_turns[-1]:
        raise ValueError("Only a turn without a completed response can be continued")
    replies_sent = sum(bool(turn.get("response", {}).get("clarification")) for turn in previous_turns)
    prior = next(
        (
            t["response"]["clarification"]
            for t in reversed(previous_turns)
            if t.get("response", {}).get("clarification")
        ),
        None,
    )
    if prior:
        if not group.get("conversation_id") or not group.get("conversation_token"):
            # Older case reports did not persist credentials for ungrouped scenarios.
            row["restart_offset"] = len(row["http_turns"])
            return case, {}
        group = {**group, "clarification_id": prior["id"]}
    return {
        **case,
        "question": previous_turns[-1]["message"],
        "clarification_answers": case.get("clarification_answers", [])[replies_sent:],
    }, group


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
    case_budget = manifest.get("budget_unit") == "main_question"
    database = f"indexbeast_agent_test_{suffix}"
    collection = f"ib_agent_test_{suffix}"
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "status": "preflight",
        "manifest": manifest,
        "cases": cases,
        "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        "planned_turns": len(cases),
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
    if case_budget:
        report.update(budget_unit="main_question", planned_cases=len(cases))
        del report["planned_turns"]
    resume = getattr(args, "resume", False)
    continue_cases = getattr(args, "continue_cases", False)
    recheck_cases = set(getattr(args, "recheck_case", []))
    import tempfile

    state_path = Path(tempfile.gettempdir()) / (
        "indexbeast-run-" + hashlib.sha256(str(args.output.resolve()).encode()).hexdigest() + ".json"
    )
    if resume:
        previous = json.loads((args.output / "report.json").read_text(encoding="utf-8"))
        planned_field = "planned_cases" if case_budget else "planned_turns"
        if previous["manifest_sha256"] != report["manifest_sha256"] or previous[planned_field] != len(cases):
            raise ValueError("Resume manifest/budget differs")
        remaining_cases(previous, cases)
        if case_budget and any(
            row["status"] == "running" or (row["status"] == "incomplete" and row["id"] not in recheck_cases)
            for row in previous["rows"]
        ):
            raise ValueError("Case checkpoint contains an unfinished question; inspect it before starting a new run")
        report = previous
        database, collection = report["test_database"], report["test_memory_collection"]
        suffix = database.rsplit("_", 1)[-1]
        groups = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        if report["attempted_turns"] and any(c.get("group") for c in cases) and not groups:
            raise ValueError("Private resume state missing; do not replay spent turns")
    else:
        groups = {}
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
        if (
            not re.fullmatch(r"indexbeast_agent_test_[a-f0-9]{10}", database)
            or collection != f"ib_agent_test_{suffix}"
            or database == base.postgres_db
        ):
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
            if not resume or not report.get("resources_created"):
                await admin.execute(f'CREATE DATABASE "{database}"')
                report["resources_created"] = True
                save(args.output, report, secret_values)
        finally:
            await admin.close()
        settings = base.model_copy(
            update={
                "postgres_db": database,
                "chat_mode": "rag",
                "chat_persistence": "postgres",
                "chat_agent_enabled": True,
                "chat_agent_max_calls": None,
                "chat_tool_steps": None,
                "chat_tool_queries": None,
                **({"chat_clarification_max_rounds": None} if case_budget else {}),
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
                elif inputs.get("policy", "").startswith("You are IndexBeast's bounded tool"):
                    row["phase"] = "tool_decision"
                elif inputs.get("policy", "").startswith("Select images"):
                    row["phase"] = "image_selection"
                return row

        counted = CountedAgent(ctx.llm)
        counted.calls = list(report["logical_model_calls"])
        ctx.llm = counted
        original_post = ctx.web_search._post

        async def post(endpoint, payload):
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
                "chat_tool_steps",
                "chat_tool_queries",
            )
        }
        app = create_app(settings, context=ctx)
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
            unfinished = (
                [(cases[i], row) for i, row in enumerate(report["rows"]) if row["status"] == "error"]
                if continue_cases
                else []
            )
            rechecks = [
                (cases[i], row)
                for i, row in enumerate(report["rows"])
                if row["id"] in recheck_cases and row["status"] in {"ok", "incomplete"}
            ]
            queued = [*unfinished, *rechecks, *((case, None) for case in cases[report["attempted_turns"] :])]
            for case, previous_row in queued:
                group = groups.get(case["group"], {}) if case["group"] else {}
                if previous_row is not None and previous_row["status"] == "error":
                    # Use the exact failed message, and the last accepted clarification when present.
                    case, group = continuation_case(case, previous_row, groups.get(case["id"], group))
                elif previous_row is not None:
                    previous_row["restart_offset"] = len(previous_row["http_turns"])
                    previous_row.pop("response", None)
                    group = {}
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
                if previous_row is None:
                    report["rows"].append(row)
                    report["attempted_turns"] += 1
                else:
                    row = previous_row
                    row["status"] = "running"
                    row.pop("error", None)
                save(args.output, report, secret_values)
                started = time.perf_counter()
                try:
                    data = await run_case(
                        http,
                        case,
                        group,
                        row,
                        groups,
                        state_path,
                        case_budget=case_budget,
                        checkpoint=lambda: save(args.output, report, secret_values),
                    )
                    if data is not None and getattr(args, "probe_images", False):
                        import io

                        from PIL import Image

                        row["image_checks"] = []
                        for im in data.get("images", []):
                            probe = {"id": im["id"], "association": im.get("association")}
                            row["image_checks"].append(probe)
                            if not re.fullmatch(r"[0-9a-f]{64}", im["id"]) or im["url"] != "/api/v1/images/" + im["id"]:
                                probe["error"] = "invalid_server_image_url"
                                continue
                            image_response = await http.get(im["url"])
                            probe.update(
                                http_status=image_response.status_code,
                                mime=image_response.headers.get("content-type"),
                            )
                            if image_response.status_code == 200:
                                raw = image_response.content
                                probe["hash_matches"] = hashlib.sha256(raw).hexdigest() == im["id"]
                                with Image.open(io.BytesIO(raw)) as raster:
                                    raster.load()
                                    probe.update(format=raster.format, width=raster.width, height=raster.height)
                                    extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "GIF": ".gif"}[
                                        raster.format
                                    ]
                                folder = args.output / "images"
                                folder.mkdir(exist_ok=True)
                                path = folder / (im["id"] + extension)
                                path.write_bytes(raw)
                                probe["inspection_file"] = str(path.resolve())
                    prepared = observed.get("prepared")
                    if prepared:
                        row["trace"] = {k: v for k, v in prepared.trace.items() if k != "result"}
                        row["resolved_question"] = json.loads(prepared.values["payload"])["question"]
                        row["evidence_ids"] = [h.id for h in prepared.hits]
                        row["checked_build"] = prepared.checked_build
                except Exception as exc:
                    row.update(status="error", error_type=type(exc).__name__)
                finally:
                    service.pipeline.prepare = original_prepare
                    row["latency_ms"] = round(row.get("latency_ms", 0) + (time.perf_counter() - started) * 1000, 2)
                    row.setdefault("model_calls", []).extend(counted.calls[start_calls:])
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
            if case_budget:
                report["summary"].update(
                    started_main_questions=len(report["rows"]),
                    terminal_responses=sum(r["status"] == "ok" for r in report["rows"]),
                    http_requests=sum(len(r.get("http_turns", [])) for r in report["rows"]),
                )
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
                "planned": len(cases),
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
