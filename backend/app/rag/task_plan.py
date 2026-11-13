"""Model-selected goals with bounded, server-owned evidence for clarification resume."""

import json

from app.adapters.tavily import WebHit, allowed_url
from app.rag.agent import GoalText
from core.types import Hit

MAX_GOALS = 4
MAX_GOAL_SOURCES = 5
MAX_SAVED_EVIDENCE_BYTES = 64_000


def start_plan(goals: list[GoalText]) -> list[dict]:
    return [{"id": f"g{i}", "goal": goal, "evidence_ids": []} for i, goal in enumerate(goals, 1)]


def update_plan(plan, step, candidate_ids):
    existing = {item["id"]: item for item in plan}
    names = {item["goal"].strip().casefold() for item in plan}
    changes = list(step.add_goals)
    if (
        (changes and not plan and len(changes) < 2)
        or len(plan) + len(changes) > MAX_GOALS
        or len(names | {goal.strip().casefold() for goal in changes}) != len(plan) + len(changes)
        or any(not goal.strip() for goal in changes)
    ):
        return False
    reopen = set(step.reopen_goals)
    if reopen - existing.keys() or reopen.intersection(step.completed_goals):
        return False
    for goal_id, ids in step.completed_goals.items():
        if goal_id not in existing or not ids or len(ids) != len(set(ids)) or not set(ids) <= candidate_ids:
            return False
    for goal_id, ids in step.completed_goals.items():
        existing[goal_id]["evidence_ids"] = ids
    for goal_id in reopen:
        existing[goal_id]["evidence_ids"] = []
    for goal in changes:
        plan.append({"id": f"g{len(plan) + 1}", "goal": goal, "evidence_ids": []})
    return True


def restore_evidence(pipe, state):
    prepared = state["prepared"]
    hits = {}
    for row in prepared.player_state.pop("plan_evidence", []):
        hit = (WebHit if row["web"] else Hit)(row["id"], row["score"], row["payload"])
        if isinstance(hit, WebHit):
            admitted = (
                state["req"].options.spoilers
                and state["search_mode"] != "off"
                and allowed_url(hit.payload.get("url"), pipe.settings.web_search_domains)
            )
        else:
            admitted = (
                row["collection"] == pipe.settings.rag_collection
                and pipe.policy.exclusion_reason(hit.payload, spoilers=state["req"].options.spoilers) is None
            )
        if admitted:
            hits[hit.id] = hit
    for item in prepared.player_state.get("plan", []):
        if not set(item["evidence_ids"]) <= hits.keys():
            item["evidence_ids"] = []
    return hits


def save_evidence(prepared, plan, hits, collection):
    rows = []
    stored = set()
    size = 0
    for item in plan:
        for key in item["evidence_ids"]:
            if key in stored or key not in hits:
                continue
            hit = hits[key]
            row = {
                "id": key,
                "score": hit.score,
                "payload": hit.payload,
                "web": isinstance(hit, WebHit),
                "collection": collection,
            }
            row_size = len(json.dumps(row, ensure_ascii=False).encode("utf-8"))
            if size + row_size > MAX_SAVED_EVIDENCE_BYTES:
                continue
            size += row_size
            stored.add(key)
            rows.append(row)
    for item in plan:
        if not set(item["evidence_ids"]) <= stored:
            item["evidence_ids"] = []
    if rows:
        prepared.player_state["plan_evidence"] = rows
