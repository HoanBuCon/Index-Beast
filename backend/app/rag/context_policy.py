"""Conservative duplicate grouping of web excerpts; no model/score fusion or keyword ordering."""

import json
from dataclasses import replace

from app.adapters.tavily import WebHit
from app.rag.matching import folded


def title_key(title):
    return folded(title.split(" | ")[0].removesuffix(" - Eldenpedia"))


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
