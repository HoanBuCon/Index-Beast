"""Aggregate review scores with explicit denominators and emit eval_runs-compatible JSON."""

import argparse
import json
from collections import Counter
from pathlib import Path

from eval.validate_golden import read_rows


def summarize(manifest, scores):
    cases = {row["id"]: row for row in manifest}
    if len(cases) != len(manifest) or len({row["id"] for row in scores}) != len(scores):
        raise ValueError("Duplicate case ID")
    for row in scores:
        case = cases.get(row["id"])
        if case is None or any(row.get(key) != case[key] for key in ("lang", "difficulty", "category")):
            raise ValueError(f"Score does not match manifest: {row['id']}")
        factual = bool(case["source_urls"])
        if (
            (row["correctness"] is not None) != factual
            or (type(row["behavior_ok"]) is bool) != (not factual)
            or (factual and row["behavior_ok"] is not None)
        ):
            raise ValueError(f"Wrong scoring criteria for case: {row['id']}")
        for key in ("correctness", "faithfulness", "followup_correctness"):
            value = row[key]
            if value is not None and (type(value) is not int or value not in (0, 1, 2)):
                raise ValueError(f"Invalid {key} for case: {row['id']}")

    def group(rows):
        totals = {"main_questions": len(rows), "terminal_responses": sum(row["status"] == "ok" for row in rows)}
        for field, metric, full in (
            ("correctness", "accuracy", 2),
            ("faithfulness", "faithfulness", 2),
            ("behavior_ok", "behavior_pass", True),
            ("followup_correctness", "followup_accuracy", 2),
        ):
            grades = Counter(row[field] for row in rows if row[field] is not None)
            count = grades.total()
            totals[f"{metric}_n"] = count
            totals[f"{metric}_full"] = grades[full]
            if count:
                totals[metric] = grades[full] / count
        return totals

    return group(scores), {
        key: {value: group([row for row in scores if row[key] == value]) for value in sorted({r[key] for r in scores})}
        for key in ("lang", "difficulty")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    scores = read_rows(args.scores)
    metrics, groups = summarize(manifest, scores)
    result = {
        "config": {
            "name": args.name,
            "manifest": args.manifest.name,
            "scores": args.scores.name,
            "planned_main_questions": len(manifest),
        },
        "metrics": metrics,
        "groups": groups,
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
