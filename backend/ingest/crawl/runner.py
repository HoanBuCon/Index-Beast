"""Category-balanced prototype crawl; file reports precede PG integration in S2."""

import re
import time
import uuid
from collections import Counter
from itertools import zip_longest

from ingest.artifacts import now, read, save, sha256
from ingest.crawl.http import CrawlError
from ingest.crawl.media import MediaStore
from ingest.crawl.scope import sample_scope_reason

OUT_OF_SCOPE = re.compile(r"Shadow.of.the.Erdtree|Nightreign|Tarnished.Edition", re.I)


def discover(source, config):
    groups, results, all_pages = {}, [], {}
    for root in config["sources"]["wikigg"]["categories"]:
        queue, visited, members = [(root, 0)], set(), {}
        while queue:
            category, depth = queue.pop(0)
            if category in visited or OUT_OF_SCOPE.search(category):
                continue
            visited.add(category)
            try:
                items = source.list_category(category)
                pages = [x for x in items if x.get("ns") == 0]
                subcats = [x for x in items if x.get("ns") == 14]
                results.append(
                    {
                        "root": root,
                        "category": category,
                        "direct_pages": len(pages),
                        "subcategories": len(subcats),
                        "status": "ok",
                    }
                )
                for item in pages:
                    if not OUT_OF_SCOPE.search(item["title"]):
                        members[item["pageid"]] = item
                if depth < config["sources"]["wikigg"]["category_depth"]:
                    queue.extend((x["title"].removeprefix("Category:"), depth + 1) for x in subcats)
            except CrawlError as exc:
                results.append({"root": root, "category": category, "status": "failed", "error": str(exc)})
        groups[root] = sorted(members.values(), key=lambda x: x["title"])
        all_pages.update(members)
    ordered, seen = [], set()
    for row in zip_longest(*groups.values()):
        for item in row:
            if item and item["pageid"] not in seen:
                seen.add(item["pageid"])
                ordered.append(item)
    report = {
        "checked_at": now(),
        "categories": results,
        "unique_candidates": len(all_pages),
        "group_sizes": {k: len(v) for k, v in groups.items()},
        "pages": ordered,
        "count_policy": "direct counts per category; union deduplicated by pageid; configured recursion depth",
        "membership": {
            str(x["pageid"]): [k for k, v in groups.items() if any(p["pageid"] == x["pageid"] for p in v)]
            for x in ordered
        },
    }
    save(config["data_dir"] / "reports" / "categories.json", report)
    return report


def crawl(source, config, limit=200, *, page=None, with_media=True, refresh_discovery=False):
    started = time.monotonic()
    job = "crawl-" + uuid.uuid4().hex[:12]
    target = config["data_dir"] / "reports" / (job + ".json")
    report = {
        "job_id": job,
        "started_at": now(),
        "status": "running",
        "target": limit,
        "pages": [],
        "errors": [],
        "counts": {},
        "media_counts": {},
        "scope_excluded": [],
    }
    counts, media_counts = Counter(), Counter()
    save(target, report)
    store = MediaStore(source.client, config) if with_media else None
    try:
        if page:
            result = source.api(action="query", titles=page, prop="info|categories", cllimit=500)
            candidates = result.get("query", {}).get("pages", [])
        else:
            path = config["data_dir"] / "reports" / "categories.json"
            discovery = read(path) if path.exists() and not refresh_discovery else discover(source, config)
            selected = discovery["pages"][: limit * 3]
            descriptions = {x["pageid"]: x for x in source.describe([x["pageid"] for x in selected])}
            candidates = [descriptions[x["pageid"]] for x in selected if x["pageid"] in descriptions]
        for candidate in candidates:
            if counts["successful"] >= limit:
                break
            categories = [x["title"] for x in candidate.get("categories", [])]
            if "missing" in candidate or candidate.get("ns", 0) != 0 or "redirect" in candidate:
                counts["excluded"] += 1
                continue
            if OUT_OF_SCOPE.search(candidate["title"] + " " + " ".join(categories)):
                report["scope_excluded"].append(
                    {
                        "pageid": candidate["pageid"],
                        "title": candidate["title"],
                        "reason": "explicit_out_of_scope_category_or_title",
                    }
                )
                counts["excluded"] += 1
                continue
            counts["attempted"] += 1
            path = config["data_dir"] / "raw" / source.name / (str(candidate["pageid"]) + ".json")
            try:
                raw = read(path) if path.exists() else None
                if (
                    raw
                    and raw.get("revision_id") == candidate.get("lastrevid")
                    and sha256(raw["content"].encode()) == raw.get("content_hash")
                ):
                    counts["cache_hits"] += 1
                else:
                    raw = source.fetch(candidate)
                    save(path, raw)
                    counts["downloaded"] += 1
                reason = sample_scope_reason(raw)
                if reason:
                    raw["scope_status"] = "excluded_from_s1_sample"
                    raw["scope_reason"] = reason
                    save(path, raw)
                    report["scope_excluded"].append(
                        {"pageid": candidate["pageid"], "title": raw["title"], "reason": reason}
                    )
                    counts["excluded"] += 1
                    continue
                counts["successful"] += 1
                report["pages"].append(
                    {
                        "id": raw["source_id"],
                        "title": raw["title"],
                        "revision_id": raw["revision_id"],
                        "path": path.relative_to(config["data_dir"]).as_posix(),
                    }
                )
                if store:
                    manifest = store.page(source, raw)
                    media_counts.update(x["status"] for x in manifest["images"])
                    if manifest["status"] != "completed":
                        report["errors"].append(
                            {"id": raw["source_id"], "phase": "media", "error": "See page media manifest"}
                        )
                print(f"PAGE {counts['successful']}/{limit}: {raw['title']}", flush=True)
            except (CrawlError, ValueError, OSError, KeyError) as exc:
                counts["failed"] += 1
                report["errors"].append({"id": candidate["pageid"], "phase": "page", "error": str(exc)})
            report.update(counts=dict(counts), media_counts=dict(media_counts))
            save(target, report)
        report["status"] = "completed" if counts["successful"] == limit and not report["errors"] else "partial"
    except BaseException as exc:
        report.update(status="interrupted_or_failed", fatal_error=str(exc))
        raise
    finally:
        report.update(
            finished_at=now(),
            elapsed_seconds=round(time.monotonic() - started, 3),
            counts=dict(counts),
            media_counts=dict(media_counts),
            http=dict(source.client.stats),
        )
        save(target, report)
    return report
