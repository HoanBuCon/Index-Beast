"""Build a run manifest from the reviewed golden set: question, source pages, labels and the clarification reply.

From backend/:  python -X utf8 -m eval.golden_manifest <output.json>
The output feeds eval.measure_retrieval (cases with source_urls) and scripts.run_live_manifest (all cases).
"""

import argparse
import json
from pathlib import Path

from eval.validate_golden import read_rows

ROOT = Path(__file__).parent


def build(golden=ROOT / "golden_set.jsonl", reviews=ROOT / "reviews/s4-golden-set-review.jsonl") -> list[dict]:
    by_id = {r["id"]: r for r in read_rows(reviews)}
    cases = []
    for row in read_rows(golden):
        review = by_id[row["id"]]
        if review["status"] != "approved":
            raise ValueError(f"{row['id']} is not approved")
        followup = review.get("followup") or {}
        cases.append(
            {
                **row,
                "level": row["difficulty"],
                "case_tags": review.get("case_tags", []),
                # Chỉ gửi khi Agent hỏi lại (run_live_manifest `replies`).
                "replies": [followup["user_message"]] if followup.get("user_message") else [],
                **(
                    {
                        "followup_expected_answer": followup.get("expected_answer"),
                        "followup_source_urls": followup.get("source_urls", []),
                    }
                    if followup
                    else {}
                ),
            }
        )
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    cases = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(cases), "cases")


if __name__ == "__main__":
    main()
