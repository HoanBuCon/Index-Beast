"""Chạy thật một manifest câu hỏi qua ASGI app thật (.env, lifespan, SSE /api/v1/chat/stream) và ghi trace.

Gọi DeepSeek/Tavily/Jina thật, tốn phí. Lượt bổ sung chỉ gửi khi Agent hỏi lại (`replies`) hoặc theo `followups`
(tin nhắn nối tiếp sau câu trả lời). Không ghi đè thư mục đã có kết quả.

Từ backend/:
  .venv/Scripts/python.exe -X utf8 -m scripts.run_live_manifest \\
      ../docs/testing/2026-11-22_true-agent-gd2/manifest.json data/research_runs/<thư-mục-mới>
"""

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path
from uuid import UUID, uuid4

TRACE_KEYS = (
    "graph_nodes",
    "tool_stop",
    "web_search",
    "evidence_selection",
    "selected_ids",
    "answer_basis",
    "images",
    "latency_ms",
    "node_ms",
    "writer",
    "writer_thinking",
    "answer_guard",
    "uncited_paragraphs",
    "evidence_merged",
    "internal_field_replaced",
    "generation_failure",
    "usage",
)


class Recorder(logging.Handler):
    """Cảnh báo từ app (chỉ nhóm lỗi, như trong log), cho báo cáo lần chạy."""

    def __init__(self):
        super().__init__()
        self.events = []

    def emit(self, record):
        if record.levelno >= logging.WARNING and record.name.startswith("app"):
            data = getattr(record, "data", None)
            self.events.append(
                {"logger": record.name, "msg": record.getMessage(), "data": data if isinstance(data, dict) else None}
            )


def parse_sse(text: str) -> list[tuple[str, dict | None]]:
    frames = []
    for frame in text.split("\n\n"):
        lines = frame.splitlines()
        name = next((line[7:] for line in lines if line.startswith("event: ")), None)
        data = next((line[6:] for line in lines if line.startswith("data: ")), None)
        if name:
            frames.append((name, json.loads(data) if data else None))
    return frames


def trace_summary(trace: dict | None) -> dict | None:
    if not trace:
        return None
    agent = trace.get("agent") or {}
    return {
        **{k: trace.get(k) for k in TRACE_KEYS},
        "model_calls": [c.get("phase") for c in trace.get("model_calls", [])],
        "agent": {
            k: agent.get(k)
            for k in (
                "status",
                "action",
                "intent",
                "gameplay_advice",
                "needs_reasoning",
                "thinking",
                "forced_finish",
                "steps",
                "usage",
                "model_calls",
            )
        },
    }


def save(out: Path, data: dict) -> None:
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def run_case(http, service, case: dict) -> list[dict]:
    replies, followups = iter(case.get("replies", [])), iter(case.get("followups", []))
    cont, message, turns = {}, case["question"], []
    while message is not None:
        body = {
            "message": message,
            "channel": "web",
            "turn_id": str(uuid4()),
            "options": {"web_search": "auto", "lang": case["lang"]},
            **cont,
        }
        started = time.perf_counter()
        resp = await http.post("/api/v1/chat/stream", json=body)
        turn = {
            "message": message,
            "http_status": resp.status_code,
            "client_ms": round((time.perf_counter() - started) * 1000),
        }
        turns.append(turn)
        if "text/event-stream" not in resp.headers.get("content-type", ""):
            turn["error"] = resp.json()
            break
        frames = parse_sse(resp.text)
        names = [n for n, _ in frames]
        done = next((v for n, v in frames if n == "done"), None)
        src = next((v for n, v in frames if n == "sources"), None) or {}
        turn.update(
            last_event=names[-1] if names else None,
            answer="".join(v["token"] for n, v in frames if n == "token"),
            error_frame=next((v for n, v in frames if n == "error"), None),
            sources=[{k: s.get(k) for k in ("index", "title", "url", "origin")} for s in src.get("sources", [])],
            images=len(src.get("images") or []),
            clarification=src.get("clarification"),
            grounded=done.get("grounded") if done else None,
        )
        if not done:
            break
        turn["trace"] = trace_summary(service.traces.get(UUID(done["message_id"])))
        cont = {"conversation_id": done["conversation_id"]}
        if done.get("conversation_token"):
            cont["conversation_token"] = done["conversation_token"]
        if turn["clarification"]:
            message = next(replies, None)
            cont["clarification_id"] = turn["clarification"]["id"]
        else:
            message = next(followups, None)
    return turns


def capture_python(sink: list) -> None:
    """Chỉ cho lần chạy nghiên cứu: ghi code và output của mỗi lần Agent gọi run_python vào results.json."""
    from app.rag import true_agent

    original = true_agent.run_python

    def recorded(code, **kwargs):
        result = original(code, **kwargs)
        sink.append(
            {
                "code": code[:3000],
                "status": result.get("status"),
                "output": str(result.get("output") or result.get("error"))[:1500],
            }
        )
        return result

    true_agent.run_python = recorded


def capture_agent(sink: list) -> None:
    """Chỉ cho lần chạy nghiên cứu: ghi mỗi lượt Agent (tham số tool đã gọi, tóm tắt kết quả tool vừa nhận)."""
    from app.adapters.llm import ManagedChatDeepSeek

    original = ManagedChatDeepSeek.bind_tools

    class Recorded:
        def __init__(self, bound):
            self.bound = bound

        async def ainvoke(self, messages, *args, **kwargs):
            seen = []
            for m in reversed(messages):
                if m.type != "tool":
                    break
                seen.append(str(m.content)[:1200])
            ai = await self.bound.ainvoke(messages, *args, **kwargs)
            sink.append(
                {
                    "tool_results_seen": list(reversed(seen)),
                    "text": str(ai.content)[:500],
                    "calls": [{"name": c["name"], "args": c.get("args")} for c in ai.tool_calls],
                    "input_tokens": (ai.usage_metadata or {}).get("input_tokens"),
                }
            )
            return ai

    def wrapped(self, *args, **kwargs):
        return Recorded(original(self, *args, **kwargs))

    ManagedChatDeepSeek.bind_tools = wrapped


async def main(
    cases: list[dict],
    out: Path,
    recorder: Recorder,
    python_calls: list | None = None,
    agent_calls: list | None = None,
) -> None:
    import httpx

    from app.main import create_app
    from core.config import Settings

    settings = Settings()
    if settings.chat_mode != "rag":
        raise SystemExit("CHAT_MODE must be rag for a live run")
    app = create_app(settings)
    results = []
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost", timeout=120) as http:
            for case in cases:
                if python_calls is not None:
                    python_calls.clear()
                if agent_calls is not None:
                    agent_calls.clear()
                turns = await run_case(http, app.state.chat_service, case)
                results.append(
                    {"id": case["id"], "level": case.get("level"), "question": case["question"], "turns": turns}
                )
                if python_calls is not None:
                    results[-1]["python_calls"] = list(python_calls)
                if agent_calls is not None:
                    results[-1]["agent_calls"] = list(agent_calls)
                save(out, {"results": results, "events": recorder.events})
                print(
                    case["id"],
                    turns[-1].get("http_status"),
                    turns[-1].get("last_event"),
                    turns[-1]["client_ms"],
                    flush=True,
                )
    print("DONE", len(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest")
    parser.add_argument("out_dir", help="New folder; results.json is written there")
    parser.add_argument(
        "--capture-python", action="store_true", help="Ghi code/output run_python của Agent (chỉ để chẩn đoán)"
    )
    parser.add_argument(
        "--capture-agent",
        action="store_true",
        help="Ghi tham số tool và kết quả Agent thấy mỗi lượt (chỉ để chẩn đoán)",
    )
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "results.json"
    if out.exists():
        raise SystemExit(f"{out} already exists; use a new folder")
    recorder = Recorder()
    logging.getLogger("app").addHandler(recorder)
    logging.getLogger("app").setLevel(logging.INFO)
    cases = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    python_calls = [] if args.capture_python else None
    if python_calls is not None:
        capture_python(python_calls)
    agent_calls = [] if args.capture_agent else None
    if agent_calls is not None:
        capture_agent(agent_calls)
    asyncio.run(main(cases, out, recorder, python_calls, agent_calls))
