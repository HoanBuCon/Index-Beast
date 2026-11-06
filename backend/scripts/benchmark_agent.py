"""Plan-only agent benchmark; opt-in execution/resume on isolated test resources."""

import argparse
import asyncio
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("eval/agent_tools_10.json"))
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--allow-web", action="store_true")
    parser.add_argument("--allow-embedding", action="store_true")
    args = parser.parse_args(argv)
    cases = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not 1 <= args.max_turns <= 1000:
        parser.error("Manifest must be an array; max-turns must be 1..1000")
    cases = cases[: args.max_turns]
    ids = set()
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("question"), str)
            or not case["question"].strip()
            or case.get("lang") not in {"vi", "en"}
            or not isinstance(case.get("id"), str)
            or case["id"] in ids
        ):
            parser.error("Invalid or duplicate manifest row")
        ids.add(case["id"])
        case.setdefault("group", None)
    if not cases:
        parser.error("Empty manifest")
    manifest = {"cases": cases, "maximum": args.max_turns}
    if not args.execute:
        print(
            json.dumps({"mode": "PLAN ONLY", "turns": len(cases), "manifest": manifest}, ensure_ascii=False, indent=2)
        )
        return
    if not all((args.allow_llm, args.allow_web, args.allow_embedding, args.output)):
        parser.error("Execute requires all --allow-* flags and --output")
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
