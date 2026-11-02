"""At most two retrieval queries; rank-only fusion, no cross-query score arithmetic."""

import json

from core.types import Hit


def plan_queries(original: str, rewritten: str, mode: str) -> list[tuple[str, str]]:
    queries = [("original", original)] if rewritten == original else [("rewritten_en", rewritten)]
    if mode == "dual" and rewritten.strip().casefold() != original.strip().casefold():
        queries.append(("original", original))
    return queries


def content_key(hit: Hit) -> str | None:
    p = hit.payload
    # Do not collapse unknown provenance or different sections, conditions/releases/images.
    if not p.get("source_id") or not p.get("revision_id"):
        return None
    keys = (
        "source",
        "source_id",
        "revision_id",
        "url",
        "section",
        "text",
        "lang",
        "game_scope",
        "release_scope",
        "speaker",
        "trigger",
        "variant_context",
        "image_ids",
        "image_association",
        "source_type",
        "source_type_evidence",
        "unit_kind",
        "review_status",
        "spoiler_level",
        "indexbeast_admission",
        "game_version",
        "patch_version",
        "upgrade_level",
        "affinity",
        "ng_cycle",
    )
    return json.dumps({key: p.get(key) for key in keys}, sort_keys=True, ensure_ascii=False)


def fuse_ranked(lists: list[list[Hit]], limit: int) -> list[Hit]:
    # RRF uses rank positions ONLY; a document contributes once per query, including bad duplicate IDs.
    scores, first, hits = {}, {}, {}
    for rows in lists:
        seen = set()
        for rank, hit in enumerate(rows, 1):
            if hit.id in seen:
                continue
            seen.add(hit.id)
            if hit.id not in first:
                first[hit.id] = len(first)
                hits[hit.id] = hit
            scores[hit.id] = scores.get(hit.id, 0.0) + 1 / (60 + rank)
    ordered, seen_content = [], set()
    for point_id in sorted(scores, key=lambda key: (-scores[key], first[key])):
        hit = hits[point_id]
        key = content_key(hit)
        if key is not None and key in seen_content:
            continue
        if key is not None:
            seen_content.add(key)
        ordered.append(Hit(hit.id, scores[point_id], hit.payload))
        if len(ordered) == limit:
            break
    return ordered
