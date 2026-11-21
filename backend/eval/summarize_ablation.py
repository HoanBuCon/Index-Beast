"""Summarize ablation runs: one row per configuration from results.json (+ judge.jsonl when present).

From backend/:
  python -X utf8 -m eval.summarize_ablation --manifest <manifest.json> --runs data/research_runs/<dir> --output <x.json>
Each sub-folder of --runs with results.json is one configuration (its name is the configuration name).
"""

import argparse
import json
from pathlib import Path
from statistics import mean, quantiles

from eval.measure_retrieval import NOISY
from eval.validate_golden import page

NEGATIVE = {"out_of_scope", "insufficient_evidence"}
DISCORD_LIMIT_MS = 45000


def pct(values):
    values = list(values)
    return round(100 * sum(values) / len(values), 1) if values else None


def p95(values):
    values = sorted(values)
    if len(values) < 2:
        return values[0] if values else None
    return round(quantiles(values, n=20)[-1])


def case_row(case: dict, result: dict, judged: dict | None) -> dict:
    turns = result["turns"]
    first, last = turns[0], turns[-1]
    trace = first.get("trace") or {}
    steps = [s for t in turns for s in ((t.get("trace") or {}).get("agent") or {}).get("steps") or []]
    usage = [((t.get("trace") or {}).get("agent") or {}).get("usage") or {} for t in turns]
    writer = [(t.get("trace") or {}).get("usage") or {} for t in turns]
    gold = {page(u) for u in case["source_urls"] + case.get("followup_source_urls", [])}
    cited = {page(s["url"]) for t in turns for s in t.get("sources") or [] if s.get("url")}
    ok = all(t.get("http_status") == 200 and t.get("last_event") == "done" for t in turns)
    rerank = result.get("rerank") or {}
    return {
        "id": case["id"],
        "difficulty": case["difficulty"],
        "lang": case["lang"],
        "noisy": bool(NOISY & set(case.get("case_tags", []))),
        "behavioral": case["category"] in NEGATIVE,
        "ok": ok,
        "grounded": bool(last.get("grounded")),
        "gold_cited": bool(gold & cited) if gold else None,
        "clarified": bool(first.get("clarification")),
        "first_ms": first.get("client_ms"),
        "case_ms": sum(t.get("client_ms") or 0 for t in turns),
        "over_45s": any((t.get("client_ms") or 0) > DISCORD_LIMIT_MS for t in turns),
        "search_web": sum(s.get("tool") == "search_web" for s in steps),
        "search_corpus": sum(s.get("tool") in {"search_corpus", "check_name"} for s in steps),
        "tokens": sum((u.get("prompt_tokens") or 0) + (u.get("completion_tokens") or 0) for u in usage + writer),
        "jina_ok": rerank.get("ok", 0),
        "jina_fallback": sum(v for k, v in rerank.items() if k != "ok"),
        "forced_finish": bool((trace.get("agent") or {}).get("forced_finish")),
        **({k: judged.get(k) for k in ("correctness", "faithfulness", "behavior", "followup")} if judged else {}),
    }


def aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0}
    factual = [r for r in rows if not r["behavioral"]]
    behavioral = [r for r in rows if r["behavioral"]]
    judged = [r for r in factual if "correctness" in r]
    faithful = [r for r in judged if r.get("faithfulness") is not None]
    calls = sum(r["jina_ok"] + r["jina_fallback"] for r in rows)
    return {
        "n": len(rows),
        "ok_pct": pct(r["ok"] for r in rows),
        "grounded_pct": pct(r["grounded"] for r in factual),
        "gold_cited_pct": pct(r["gold_cited"] for r in factual if r["gold_cited"] is not None),
        "accuracy_pct": pct(r.get("correctness") == 2 for r in judged) if judged else None,
        "correctness_mean": round(mean(r["correctness"] or 0 for r in judged), 3) if judged else None,
        "faithfulness_full_pct": pct(r["faithfulness"] == 2 for r in faithful) if faithful else None,
        "behavior_pass_pct": pct(r.get("behavior") == "pass" for r in behavioral if "behavior" in r)
        if any("behavior" in r for r in behavioral)
        else None,
        "first_ms_p50": round(quantiles([r["first_ms"] for r in rows], n=2)[0]) if len(rows) > 1 else None,
        "first_ms_p95": p95(r["first_ms"] for r in rows),
        "over_45s": sum(r["over_45s"] for r in rows),
        "search_web_per_case": round(mean(r["search_web"] for r in rows), 2),
        "search_corpus_per_case": round(mean(r["search_corpus"] for r in rows), 2),
        "tokens_per_case": round(mean(r["tokens"] for r in rows)),
        "jina_ok_pct": pct([True] * sum(r["jina_ok"] for r in rows) + [False] * sum(r["jina_fallback"] for r in rows))
        if calls
        else None,
        "forced_finish": sum(r["forced_finish"] for r in rows),
    }


def summarize(manifest: list[dict], run_dir: Path) -> dict:
    cases = {c["id"]: c for c in manifest}
    data = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    judge_file = run_dir / "judge.jsonl"
    judged = {}
    if judge_file.exists():
        for line in judge_file.read_text(encoding="utf-8").splitlines():
            if line.strip() and "error" not in (row := json.loads(line)):
                judged[row["id"]] = row
    rows = [case_row(cases[r["id"]], r, judged.get(r["id"])) for r in data["results"]]
    return {
        "config": data.get("config"),
        "summary": aggregate(rows),
        "by_difficulty": {d: aggregate([r for r in rows if r["difficulty"] == d]) for d in ("easy", "medium", "hard")},
        "by_input": {
            "noisy": aggregate([r for r in rows if r["noisy"]]),
            "clean": aggregate([r for r in rows if not r["noisy"]]),
        },
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = {d.name: summarize(manifest, d) for d in sorted(args.runs.iterdir()) if (d / "results.json").exists()}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, item in report.items():
        print(name, json.dumps(item["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
