"""Plan-only agent benchmark; opt-in execution/resume on isolated test resources."""

import argparse
import asyncio
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("eval/agent_tools_10.json"))
    budget = parser.add_mutually_exclusive_group()
    budget.add_argument("--max-cases", type=int, help="Main questions only; clarification replies stay in their case")
    budget.add_argument("--max-turns", type=int, help="Legacy flat manifest request limit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--continue-cases", action="store_true", help="Continue failed cases from their saved request")
    parser.add_argument("--recheck-case", action="append", default=[], help="Recheck a completed case by ID")
    parser.add_argument(
        "--answer-pending",
        nargs=2,
        metavar=("CASE_ID", "REPLY"),
        action="append",
        default=[],
        help="Answer an existing pending clarification without replaying the main question",
    )
    parser.add_argument(
        "--probe-images", action="store_true", help="GET/decode/hash returned images and save run-local copies"
    )
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--allow-web", action="store_true")
    parser.add_argument("--allow-embedding", action="store_true")
    args = parser.parse_args(argv)
    cases = json.loads(args.manifest.read_text(encoding="utf-8"))
    maximum = args.max_cases or (args.max_turns if args.max_turns is not None else 10)
    if not isinstance(cases, list) or not 1 <= maximum <= 1000 or args.max_cases == 0:
        parser.error("Manifest must be an array; the case/turn limit must be 1..1000")
    cases = cases[:maximum]
    ids = set()
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("question"), str)
            or not case["question"].strip()
            or case.get("lang") not in {"vi", "en"}
            or not isinstance(case.get("id"), str)
            or case["id"] in ids
            or case.get("web_search", "auto") not in {"off", "auto", "always"}
            or case.get("endpoint", "chat") not in {"chat", "chat/stream"}
        ):
            parser.error("Invalid or duplicate manifest row")
        replies = case.get("clarification_answers")
        if (args.max_cases is not None or replies is not None) and (
            args.max_turns is not None
            or not isinstance(replies if replies is not None else [], list)
            or any(not isinstance(reply, str) or not reply.strip() for reply in (replies or []))
        ):
            parser.error("Clarification answers must be an array of nonempty strings under a case budget")
        ids.add(case["id"])
        case.setdefault("group", None)
    if not cases:
        parser.error("Empty manifest")
    manifest = {"cases": cases, "maximum": maximum}
    if args.max_cases is not None or any("clarification_answers" in case for case in cases):
        manifest["budget_unit"] = "main_question"
    if not args.execute:
        print(
            json.dumps(
                {
                    "mode": "PLAN ONLY",
                    "cases" if "budget_unit" in manifest else "turns": len(cases),
                    "manifest": manifest,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if not all((args.allow_llm, args.allow_web, args.allow_embedding, args.output)):
        parser.error("Execute requires all --allow-* flags and --output")
    if (args.continue_cases or args.recheck_case or args.answer_pending) and (
        not args.resume or "budget_unit" not in manifest
    ):
        parser.error("Continuing cases requires --resume and a case budget")
    pending = dict(args.answer_pending)
    if (
        (set(args.recheck_case) | pending.keys()) - ids
        or set(args.recheck_case) & pending.keys()
        or len(pending) != len(args.answer_pending)
        or any(not reply.strip() for reply in pending.values())
    ):
        parser.error("Unknown or duplicate case ID, or empty pending reply")
    args.answer_pending = pending
    from scripts.diagnose_agent_memory import execute

    status = asyncio.run(execute(args, manifest, cases))
    if status == "complete" and any(
        row["status"] != "ok" for row in json.loads((args.output / "report.json").read_text(encoding="utf-8"))["rows"]
    ):
        raise SystemExit(1)
    if status != "complete":
        raise SystemExit(2 if status in {"blocked", "interrupted"} else 1)


if __name__ == "__main__":
    main()
