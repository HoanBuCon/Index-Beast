"""Conservative duplicate grouping and entity coverage ordering; no model/score fusion."""

import json
import re
from dataclasses import replace

from app.adapters.tavily import WebHit
from app.rag.overview import folded
from app.rag.rewrite import canonical_surface


def title_key(title):
    return folded(canonical_surface(title.split(" | ")[0].removesuffix(" - Eldenpedia")))


def dedup_web(hits):
    # Only equal text, equal normalized title and equal semantic metadata may be collapsed.
    # Keep all original point IDs/URLs/timestamps; do not mutate incoming payloads.
    result, groups = [], {}
    # Compare ALL remaining metadata, including future condition fields. Missing is not null.
    identity = {"text", "title", "url", "retrieved_at", "provenance"}

    for hit in hits:
        if not isinstance(hit, WebHit):
            result.append(hit)
            continue
        payload = hit.payload
        key = (
            payload["text"],
            title_key(payload["title"]),
            json.dumps({k: v for k, v in payload.items() if k not in identity}, sort_keys=True, ensure_ascii=False),
        )
        alias = {"point_id": hit.id, "url": payload["url"], "retrieved_at": payload.get("retrieved_at")}
        aliases = [*payload.get("provenance", [])]
        if alias not in aliases:
            aliases.append(alias)
        if key not in groups:
            groups[key] = len(result)
            result.append(replace(hit, payload={**payload, "provenance": aliases}))
        else:
            position = groups[key]
            original = result[position]
            combined = [*original.payload["provenance"]]
            for alias in aliases:
                if alias not in combined:
                    combined.append(alias)
            result[position] = replace(original, payload={**original.payload, "provenance": combined})
    return result


def coverage_order(hits, entities, query):
    """Reserve a useful candidate per explicit target when present; do not invent missing evidence."""
    query = folded(query)
    if re.search(r"stat allocation|stat spread|exact stats|chia chi so|phan bo|cong diem", query):
        from app.rag.gameplay_knowledge import trusted_rule_kind

        rules = [h for h in hits if trusted_rule_kind(h)]
        if rules:
            ids = {h.id for h in rules}
            return [*rules, *coverage_order([h for h in hits if h.id not in ids], entities, query)]
    quest = any(
        word in query for word in ("quest", "nhiem vu", "bat buoc", "necessary", "optional", "after", "sau khi")
    )
    stats = any(
        word in query for word in ("upgrade", "maximum", "require", "cost", "affinity", "nang", "chi so", "bao nhieu")
    )
    if not (quest or stats) or not entities:
        return hits

    def utility(hit):
        section = folded(str(hit.payload.get("section") or ""))
        if quest and ("questline" in section or "progression" in section or "walkthrough" in section):
            return 4
        if stats and section in {"description", "notes", "infobox", "effect", "effects"}:
            return 3
        if quest and section in {"description", "notes"}:
            return 2
        return 0

    ordered = sorted(hits, key=lambda h: -utility(h))  # Stable order within each metadata tier.
    seeds, seen = [], set()
    for entity in entities:
        target = title_key(entity)
        candidates = [
            h
            for h in ordered
            if title_key(h.payload["title"]) == target or title_key(h.payload["title"]).startswith(target + " ")
        ]
        if candidates and candidates[0].id not in seen:
            seeds.append(candidates[0])
            seen.add(candidates[0].id)
    return [*seeds, *(h for h in ordered if h.id not in seen)]
