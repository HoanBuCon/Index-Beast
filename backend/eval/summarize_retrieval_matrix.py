"""Reconstruct the six-cell evaluation tables from completed checkpoints."""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from eval.s4_retrieval_matrix import AUTO_IDS, MODES, combinations, load_cases, load_progress


def ratio(values):
    return {"n": len(values), "value": mean(values) if values else None}


def summarize(root):
    cases = load_cases()
    retrieval = load_progress(root / "retrieval.jsonl")
    rewrites = load_progress(root / "rewrites.jsonl")
    off, auto = (load_progress(root / f"scores-{mode}.jsonl") for mode in ("off", "auto"))
    answers = {mode: load_progress(root / f"answers-{mode}.jsonl") for mode in ("off", "auto")}
    keys = {key for key, *_ in combinations(cases)}
    auto_keys = {key for key, case, *_ in combinations(cases) if case["id"] in AUTO_IDS}
    if (
        retrieval.keys() != keys
        or off.keys() != keys
        or answers["off"].keys() != keys
        or auto.keys() != auto_keys
        or answers["auto"].keys() != auto_keys
        or rewrites.keys() != {case["id"] for case in cases}
    ):
        raise ValueError("Evaluation is incomplete or contains mismatched keys")
    slices = {
        "all": cases,
        "s4": [c for c in cases if c["id"].startswith("IB-GS-")],
        "supplement": [c for c in cases if c["id"].startswith("IB-SUP-")],
    }
    for field, values in (("lang", ("vi", "en")), ("difficulty", ("easy", "medium", "hard"))):
        slices.update({label: [c for c in cases if c[field] == label] for label in values})
    for tag in ("calculation", "typo", "query_noise", "vi_no_diacritics"):
        slices[tag] = [c for c in cases if tag in c["tags"]]

    def cell(group, mode, kind, web):
        scored = off if web == "off" else auto
        outcomes = []
        for case in group:
            key = f"{case['id']}:{mode}:{kind}"
            if key in scored:
                outcomes.append((case, retrieval[key], scored[key], answers[web][key]))
        facts = [(r, s, a) for c, r, s, a in outcomes if c["source_urls"]]
        behavior = [s for c, _, s, _ in outcomes if not c["source_urls"]]
        return {
            "cases": len(outcomes),
            **{
                f"page_{metric}": ratio([r["page_metrics"][metric] for r, _, _ in facts])
                for metric in ("recall_at5", "mrr_at5", "hit_at5")
            },
            "context_chunk_recall": ratio(
                [r["context_chunk_recall"] for r, _, _ in facts if r["context_chunk_recall"] is not None]
            ),
            "accuracy": ratio([s["correctness"] == 2 for _, s, _ in facts]),
            "mean_correctness": ratio([s["correctness"] for _, s, _ in facts if s["correctness"] is not None]),
            "behavior_pass": ratio([s["correctness"] == 2 for s in behavior]),
            "faithfulness": ratio([s["faithfulness"] == 2 for _, _, s, _ in outcomes if s["faithfulness"] is not None]),
            "judge_errors": sum(s["correctness"] is None for _, _, s, _ in outcomes),
            "answer_status": dict(Counter(a["status"] for _, _, _, a in outcomes)),
            "web_status": dict(Counter(a["web"] for _, _, _, a in outcomes)),
            "web_citations": sum(any(s["origin"] == "web" for s in a["sources"]) for _, _, _, a in outcomes),
        }

    return {
        "design": json.loads((root / "design.json").read_text(encoding="utf-8")),
        "total": {
            "questions": len(cases),
            "retrieval_runs": len(keys),
            "off_answers": len(off),
            "auto_answers": len(auto),
        },
        "rewrite_actions": dict(Counter(x["action"] for x in rewrites.values())),
        "rewritten": sum(x["rewritten"] for x in rewrites.values()),
        "rewrite_reasons": dict(
            Counter(x["trace"].get("agent", {}).get("reason", "unknown") for x in rewrites.values())
        ),
        "off": {
            label: {f"{m}:{k}": cell(group, m, k, "off") for m in MODES for k in ("raw", "rewrite")}
            for label, group in slices.items()
        },
        "auto": {f"{m}:{k}": cell(cases, m, k, "auto") for m in MODES for k in ("raw", "rewrite")},
        "auto_controls": {
            f"{m}:{k}": cell([c for c in cases if c["id"] in AUTO_IDS], m, k, "off")
            for m in MODES
            for k in ("raw", "rewrite")
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = summarize(args.run)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(summary["total"]))


if __name__ == "__main__":
    main()
