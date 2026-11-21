"""Stable interleaving of local and web evidence, not score fusion."""

from app.rag.context_policy import dedup_web


def merge_evidence(local, web):
    """Web first for uncovered requests; alternate origins, dedup by URL+text, no score arithmetic."""
    if not web:
        return local
    web = dedup_web(web)
    merged, seen = [], set()
    for index in range(max(len(local), len(web))):
        for rows in (web, local):
            if index < len(rows):
                hit = rows[index]
                key = hit.id
                if key not in seen:
                    seen.add(key)
                    merged.append(hit)
    return merged
