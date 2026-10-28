"""Full lore inventory and revision-aware crawl, separate from S1 sampling."""

import argparse
import asyncio
import time
import uuid
from collections import Counter

from core.config import Settings
from core.db.repositories import finish_job, start_job
from core.db.session import create_engine, create_sessionmaker
from ingest.artifacts import now, read, save, sha256
from ingest.crawl.http import HttpClient
from ingest.crawl.media import MediaStore
from ingest.settings import load_settings
from ingest.sources.wikigg import WikiGG


async def job_event(job_id, report=None):
    engine = create_engine(Settings())
    try:
        async with create_sessionmaker(engine)() as session, session.begin():
            if report is None:
                job = await start_job(session, kind="crawl", source="wikigg", external_id=job_id)
                return job.id
            from core.db.models import IngestionJob

            job = await session.get(IngestionJob, job_id)
            await finish_job(
                session,
                job,
                pages_ok=report["counts"].get("successful", 0),
                pages_failed=report["counts"].get("failed", 0),
                log=report,
            )
            if report["status"] != "completed":
                job.status = "partial" if report["counts"].get("successful") else "failed"
    finally:
        await engine.dispose()


def inventory(source, config, path):
    state = (
        read(path)
        if path.exists()
        else {
            "pending": list(config["sources"][source.name]["categories"]),
            "visited": [],
            "pages": {},
            "membership": {},
            "status": "running",
        }
    )
    while state["pending"]:
        category = state["pending"][0]
        items = source.list_category(category)
        for item in items:
            if item["ns"] == 0:
                key = str(item["pageid"])
                state["pages"][key] = item
                members = state["membership"].setdefault(key, [])
                if category not in members:
                    members.append(category)
            elif item["ns"] == 14:
                child = item["title"].removeprefix("Category:")
                if child not in state["visited"] and child not in state["pending"]:
                    state["pending"].append(child)
        state["visited"].append(category)
        state["pending"].pop(0)
        state["updated_at"] = now()
        save(path, state)
    state["status"] = "completed"
    save(path, state)
    return state


def run(source, config, run_dir, *, media=True, job_id=None):
    run_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report_path = run_dir / "report.json"
    report = {
        "job_id": job_id or "crawl-full-" + uuid.uuid4().hex,
        "started_at": now(),
        "status": "running",
        "pages": [],
        "errors": [],
        "counts": {},
    }
    previous = read(report_path) if report_path.exists() else {}
    cached = {str(p["id"]): p for p in previous.get("pages", [])}
    cache_path = run_dir / "checkpoint.json"
    if cache_path.exists():
        cached.update(read(cache_path))
    counts = Counter()
    store = MediaStore(source.client, config, manifest_root=run_dir / "media-working") if media else None
    save(report_path, report)
    try:
        discovered = inventory(source, config, run_dir / "inventory.json")
        ids = sorted(discovered["pages"], key=int)
        report["inventory_pages"] = len(ids)
        for start in range(0, len(ids), 50):
            batch = ids[start : start + 50]
            described = {str(p["pageid"]): p for p in source.describe(batch)}
            for key in batch:
                page = described.get(key)
                if not page or "missing" in page or "redirect" in page or page.get("ns") != 0:
                    counts["excluded"] += 1
                    report.setdefault("excluded", []).append({"id": key, "reason": "missing_redirect_or_namespace"})
                    continue
                try:
                    old = cached.get(key)
                    raw = read(config["data_dir"] / old["path"]) if old else None
                    if not (
                        raw
                        and raw["revision_id"] == page.get("lastrevid")
                        and raw["content_hash"] == sha256(raw["content"].encode())
                    ):
                        raw = source.fetch(page)
                        counts["downloaded"] += 1
                    else:
                        counts["cache_hits"] += 1
                    snapshot = (
                        config["data_dir"]
                        / "raw"
                        / source.name
                        / "snapshots"
                        / key
                        / (str(raw["revision_id"]) + "-" + raw["content_hash"] + ".json")
                    )
                    if not snapshot.exists():
                        save(snapshot, raw)
                    entry = {
                        "id": key,
                        "title": raw["title"],
                        "revision_id": raw["revision_id"],
                        "path": snapshot.relative_to(config["data_dir"]).as_posix(),
                    }
                    if store:
                        manifest = store.page(source, raw)
                        manifest_path = run_dir / "media" / (key + ".json")
                        save(manifest_path, manifest)
                        entry["media_manifest"] = str(manifest_path.relative_to(config["data_dir"]))
                        if manifest["status"] != "completed":
                            raise ValueError("Media incomplete; retry this page")
                    report["pages"].append(entry)
                    cached[key] = entry
                    save(cache_path, cached)
                    counts["successful"] += 1
                except (ValueError, OSError, KeyError, RuntimeError) as exc:
                    counts["failed"] += 1
                    report["errors"].append({"id": key, "error": str(exc)})
                report["counts"] = dict(counts)
                save(report_path, report)
        report["status"] = "partial" if counts["failed"] else "completed"
    except BaseException:
        report["status"] = "failed"
        raise
    finally:
        report.update(counts=dict(counts), finished_at=now(), elapsed_seconds=time.monotonic() - started)
        report["raw_bytes"] = sum((config["data_dir"] / p["path"]).stat().st_size for p in report["pages"])
        save(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Reuse the same identifier to resume")
    parser.add_argument("--no-media", action="store_true")
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        parser.error("run-id must contain only letters, digits, hyphen or underscore")
    config = load_settings()
    directory = config["data_dir"] / "crawl_runs" / args.run_id
    external_id = "crawl-full-" + uuid.uuid4().hex
    db_job = asyncio.run(job_event(external_id))
    client = HttpClient(config)
    try:
        run(WikiGG(client, config), config, directory, media=not args.no_media, job_id=external_id)
    finally:
        client.close()
        if (directory / "report.json").exists():
            asyncio.run(job_event(db_job, read(directory / "report.json")))
    return 0 if read(directory / "report.json")["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
