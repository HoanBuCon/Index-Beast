"""Chạy thật spike True Agent trên một manifest câu hỏi (gọi DeepSeek/Tavily/Jina thật, tốn phí).

Dùng app thật (.env, lifespan) để lấy pipeline nhưng gọi thẳng `run_true_agent` (chưa nối API, không SSE, không
chọn ảnh). Câu hỏi lại: gửi lại câu gốc + lời đáp (prototype chưa có memory). Không ghi đè kết quả đã có.

Từ backend/:
  .venv/Scripts/python.exe -X utf8 -m scripts.spike_true_agent generator data/research_runs/<thư-mục-mới> \
      --manifest ../docs/testing/2026-11-22_spike-true-agent/manifest.json [--only BL-01,BL-05]
"""

import argparse
import asyncio
import json
import time
from pathlib import Path


def turn_record(message, ms, run, err):
    trace = run.prepared.trace if run else {}
    result = run.result if run else None
    return {
        "message": message,
        "client_ms": ms,
        "ok": bool(result and not err),
        "error": err,
        "stop": run.stop if run else None,
        "grounded": result.grounded if result else None,
        "answer": result.answer if result else None,
        "sources": [s.title for s in result.sources] if result else [],
        "model_calls": [c.get("phase") for c in trace.get("model_calls", [])],
        "agent_calls": run.model_calls if run else None,
        "tool_calls": run.tool_calls if run else [],
        "usage_agent": run.usage if run else None,
        "usage_generation": trace.get("usage"),
        "checked_build": bool(run and run.prepared.checked_build),
        "evidence_selection": trace.get("evidence_selection"),
        "answer_guard": trace.get("answer_guard"),
        "web_search": trace.get("web_search"),
    }


def save(out: Path, data: dict) -> None:
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


async def main(args, cases, out):
    from app.api.schemas.chat import ChatRequest
    from app.main import create_app
    from app.rag.true_agent import run_true_agent
    from core.config import Settings

    app = create_app(Settings())
    results = []
    async with app.router.lifespan_context(app):
        pipe = app.state.chat_service.pipeline
        for case in cases:
            replies, message, turns = iter(case.get("replies", [])), case["question"], []
            while True:
                req = ChatRequest(message=message, channel="web", options={"web_search": "auto", "lang": case["lang"]})
                started = time.perf_counter()
                try:
                    run = await run_true_agent(pipe, req, variant=args.variant)
                    err = run.error
                except Exception as exc:  # noqa: BLE001 - recorded in the report
                    run, err = None, f"{type(exc).__name__}: {str(exc)[:200]}"
                turns.append(turn_record(message, round((time.perf_counter() - started) * 1000), run, err))
                reply = next(replies, None) if run and run.stop == "ask_user" else None
                if reply is None:
                    break
                message = case["question"] + "\n" + reply
            results.append({"id": case["id"], "level": case.get("level"), "question": case["question"], "turns": turns})
            out.write_text(
                json.dumps({"variant": args.variant, "results": results}, ensure_ascii=False, indent=2), "utf-8"
            )
            last = turns[-1]
            print(case["id"], last["ok"], last["client_ms"], last["stop"], last["error"], flush=True)
    print("DONE", len(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("variant", choices=["generator", "final_answer"])
    parser.add_argument("out", help="New output folder (results-<variant>.json is written there)")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--only", default="", help="Comma-separated case IDs")
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"results-{args.variant}.json"
    if out.exists():
        raise SystemExit(f"{out} already exists; use a new output folder")
    only = set(args.only.split(",")) if args.only else None
    cases = [c for c in json.loads(Path(args.manifest).read_text(encoding="utf-8")) if not only or c["id"] in only]
    asyncio.run(main(args, cases, out))
