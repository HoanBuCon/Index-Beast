"""Cập nhật tăng dần (FR-ING-07): chỉ xử lý trang đổi/mới/bị xoá từ lần cập nhật thành công trước.

Luồng: phát hiện (MediaWiki recentchanges hoặc quét toàn bộ revision) -> describe (lastrevid) so với state ->
với từng lô trang đổi: crawl -> clean -> chunk -> index (upsert theo chunk id ổn định, xoá point thừa của trang co lại)
-> PostgreSQL -> ghi state. Chi phí tăng theo số trang đổi, không theo kích thước corpus (trừ lần quét toàn bộ
chỉ đọc metadata, 1 request / 50 trang). Chạy lại luôn an toàn: trang đã khớp revision bị bỏ qua.

Các thành phần ngoài được tiêm vào để test không cần mạng/model:
- source: describe(ids), recent_changes(since), fetch(page) (WikiGG).
- builder: build(pages) -> (built, errors); built[id] = {"doc": dict, "chunks": [dict]} (PipelineBuilder).
- index: async prepare(), sync(docs_by_uuid) -> dict, delete(uuids) (ingest.index.writer.QdrantIndex).
- docs: async sync(built_list), delete(source_ids), list_documents() (ingest.chunk.sync.PgDocuments).
- jobs: async start(kind, source) -> handle, finish(handle, ok, failed, log) (ingest.jobs).

Phụ trách: TV2 · [S5] Cập nhật dữ liệu tăng dần
"""

import asyncio
import time
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

from core.ids import document_id
from ingest.artifacts import now, read, save
from ingest.crawl.http import CrawlError
from ingest.crawl.runner import OUT_OF_SCOPE

STATE_VERSION = 1
DEFAULTS = {"recentchanges_max_age_days": 30, "overlap_minutes": 30, "batch_pages": 50}


class StateMissing(RuntimeError):
    """Chưa có state: cần --bootstrap-from <thư mục chunk> hoặc --bootstrap-from-db."""


def state_path(config, source_name):
    return config["data_dir"] / "state" / f"{source_name}-update.json"


def load_state(path):
    return read(path) if path.exists() else None


def new_state(pages, watermark):
    return {"version": STATE_VERSION, "watermark": watermark, "scope_categories": [], "pages": pages}


def bootstrap_from_documents(rows):
    """Dựng state từ danh sách tài liệu hiện có (documents.jsonl của bản chunk hoặc bảng documents)."""
    pages = {
        str(r["source_id"]): {"revision_id": r["revision_id"], "title": r["title"], "chunks": r.get("chunks", 0)}
        for r in rows
        if r.get("revision_id")
    }
    fetched = [str(r["fetched_at"]) for r in rows if r.get("fetched_at")]
    # Mốc sớm nhất: mọi thay đổi sau lần crawl đầu đều được quét; thiếu mốc thì lần đầu quét toàn bộ.
    return new_state(pages, min(fetched, default=None))


def bootstrap_from_chunk_dir(directory):
    """Đọc documents.jsonl + wikigg/<id>.jsonl của một bản chunk đã nghiệm thu (chỉ đọc file)."""
    import json

    rows = []
    for line in (directory / "documents.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        chunks = directory / "wikigg" / (doc["source_id"] + ".jsonl")
        count = sum(1 for x in chunks.read_text(encoding="utf-8").splitlines() if x.strip()) if chunks.exists() else 0
        rows.append({**doc, "chunks": count})
    return bootstrap_from_documents(rows)


def parse_time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def settings_of(config):
    return {**DEFAULTS, **config.get("update", {})}


def category_names(page):
    return {c["title"].removeprefix("Category:") for c in page.get("categories", [])}


def refresh_scope(source, config, state):
    """Duyệt toàn bộ cây category như crawl.full.inventory (không giới hạn độ sâu, chỉ list category).

    Trả {pageid: item} của trang ns0 và lưu tập category thuộc phạm vi vào state."""
    pending, visited, pages = list(config["sources"]["wikigg"]["categories"]), set(), {}
    while pending:
        category = pending.pop(0)
        if category in visited or OUT_OF_SCOPE.search(category):
            continue
        visited.add(category)
        try:
            items = source.list_category(category)
        except CrawlError:
            continue  # category lỗi không làm hỏng cả lượt; trang của nó được phát hiện qua lượt sau
        for item in items:
            if item.get("ns") == 0 and not OUT_OF_SCOPE.search(item["title"]):
                pages[str(item["pageid"])] = item
            elif item.get("ns") == 14:
                pending.append(item["title"].removeprefix("Category:"))
    state["scope_categories"] = sorted(visited)
    return pages


def detect(source, config, state, *, since, full_scan):
    """Trả (chế độ, id ứng viên, id nằm trong phạm vi nếu đã quét category)."""
    cfg = settings_of(config)
    watermark = state.get("watermark")
    start = since or watermark
    too_old = start is None or parse_time(start) < datetime.now(UTC) - timedelta(days=cfg["recentchanges_max_age_days"])
    if full_scan or too_old:
        scoped = set(refresh_scope(source, config, state))
        state["_scope_fresh"] = True
        return "full_scan", sorted(scoped | set(state["pages"]), key=int), scoped
    titles = {p["title"]: key for key, p in state["pages"].items()}
    ids = set()
    for entry in source.recent_changes(start):
        title = entry.get("title")
        if (entry.get("logtype") or entry.get("log_type")) == "move" and titles.get(title):
            # Trang giữ pageid khi đổi tên; log ghi tên cũ. Cập nhật tên để log xoá về sau theo tên mới vẫn khớp.
            key = titles.pop(title)
            target = (entry.get("logparams") or entry.get("params") or {}).get("target_title")
            if target:
                state["pages"][key]["title"] = target
                titles[target] = key
        else:  # log xoá có thể có pageid 0: tra theo tên trong state
            key = str(entry["pageid"]) if entry.get("pageid") else titles.get(title, "")
        if key:
            ids.add(key)
    return "recentchanges", sorted(ids, key=int), None


def classify(source, config, state, ids, scoped):
    """Chia ứng viên thành new/changed/deleted/unchanged/skipped dựa vào lastrevid hiện tại của wiki."""
    plan = {"new": [], "changed": [], "deleted": [], "unchanged": [], "skipped": []}
    roots = set(config["sources"]["wikigg"].get("categories", []))
    fresh = state.pop("_scope_fresh", False)  # đã duyệt category trong detect: không duyệt lại

    def scope():
        return set(state.get("scope_categories", [])) | roots

    def refreshed_scope():
        nonlocal fresh
        if not fresh:  # tối đa một lần mỗi lượt
            refresh_scope(source, config, state)
            fresh = True
        return scope()

    for page in source.describe([int(i) for i in ids]):
        key = str(page["pageid"])
        known = state["pages"].get(key)
        title, cats = page.get("title", ""), category_names(page)
        gone = (
            "missing" in page
            or "redirect" in page
            or page.get("ns", 0) != 0
            or OUT_OF_SCOPE.search(title + " " + " ".join(cats))
        )
        # Chỉ coi là rời phạm vi khi describe có trả category (không xoá trang chỉ vì không hỏi category).
        if not gone and known and cats and not cats & scope():
            gone = not cats & refreshed_scope()
        if gone:
            plan["deleted" if known else "skipped"].append(
                {"id": key, "title": title or (known or {}).get("title", "")}
            )
        elif known and known["revision_id"] == page.get("lastrevid"):
            plan["unchanged"].append(key)
        elif known:
            plan["changed"].append(page)
        else:
            in_scope = key in scoped if scoped is not None else bool(cats & scope())
            if scoped is None and not in_scope:
                in_scope = bool(cats & refreshed_scope())  # category con mới chưa biết
            plan["new" if in_scope else "skipped"].append(page if in_scope else {"id": key, "title": title})
    return plan


async def run_update(
    source,
    config,
    *,
    builder,
    index,
    docs,
    jobs,
    since=None,
    full_scan=False,
    dry_run=False,
    max_pages=None,
    batch_pages=None,
    pipeline_version=None,
):
    cfg = settings_of(config)
    path = state_path(config, source.name)
    state = load_state(path)
    if state is None:
        raise StateMissing(f"Chưa có state {path}: dùng --bootstrap-from hoặc --bootstrap-from-db")
    started = datetime.now(UTC)
    warnings = []
    recorded = state.get("pipeline_version")
    if pipeline_version and recorded and recorded != pipeline_version:
        warnings.append(
            f"pipeline_version đổi ({recorded} -> {pipeline_version}): trang không đổi revision vẫn mang chunk cũ; "
            "cần dựng toàn bộ vào collection mới (docs/data-pipeline.md, mục 6)"
        )
    elif pipeline_version and not recorded:
        state["pipeline_version"] = pipeline_version
    old_watermark = state.get("watermark")
    mode, ids, scoped = detect(source, config, state, since=since, full_scan=full_scan)
    plan = classify(source, config, state, ids, scoped)
    work = sorted(plan["new"] + plan["changed"], key=lambda p: p["pageid"])
    deferred = max(0, len(work) - max_pages) if max_pages else 0
    work = work[: max_pages or None]
    summary = {
        "source": source.name,
        "mode": mode,
        "since": since or old_watermark,
        "candidates": len(ids),
        "new": len(plan["new"]),
        "changed": len(plan["changed"]),
        "deleted": len(plan["deleted"]),
        "unchanged": len(plan["unchanged"]),
        "skipped_out_of_scope": len(plan["skipped"]),
        "deferred": deferred,
        "warnings": warnings,
    }
    if dry_run:
        return {
            **summary,
            "dry_run": True,
            "status": "dry_run",
            "titles": {
                "new": [p["title"] for p in plan["new"]][:50],
                "changed": [p["title"] for p in plan["changed"]][:50],
                "deleted": [p["title"] for p in plan["deleted"]][:50],
            },
        }
    job_id = "update-" + uuid.uuid4().hex[:12]
    handle = await jobs.start("update", source.name, job_id)
    counts, errors, began = Counter(), [], time.monotonic()
    report = {"job_id": job_id, "started_at": now(), **summary}
    try:
        await index.prepare()
        if plan["deleted"]:
            await index.delete([str(document_id(source.name, p["id"])) for p in plan["deleted"]])
            await docs.delete([p["id"] for p in plan["deleted"]])
            for p in plan["deleted"]:
                state["pages"].pop(p["id"], None)
            counts["deleted_documents"] = len(plan["deleted"])
            save(path, state)
        size = batch_pages or cfg["batch_pages"]
        for offset in range(0, len(work), size):
            batch = work[offset : offset + size]
            built, failed = await asyncio.to_thread(builder.build, batch)
            errors.extend({"id": str(k), "phase": "build", "error": v} for k, v in failed.items())
            if built:
                await index.sync({str(document_id(source.name, k)): v["chunks"] for k, v in built.items()})
                await docs.sync(list(built.values()))
                for key, value in built.items():
                    title = value["doc"]["title"]
                    state["pages"][key] = {
                        "revision_id": value["doc"]["revision_id"],
                        "title": title,
                        "chunks": len(value["chunks"]),
                    }
                    counts["chunks"] += len(value["chunks"])
                save(path, state)  # điểm resume: lô đã xong không bị làm lại
            counts["pages_ok"] += len(built)
            counts["pages_failed"] += len(failed)
            counts["batches"] += 1
        ok = counts["pages_ok"] + counts["deleted_documents"]
        complete = not errors and not deferred
        # --since muộn hơn mốc hiện tại chỉ để xem thử: không được đẩy mốc qua các thay đổi chưa quét.
        covered = since is None or old_watermark is None or parse_time(since) <= parse_time(old_watermark)
        if complete and (mode == "full_scan" or covered):
            state["watermark"] = (started - timedelta(minutes=cfg["overlap_minutes"])).isoformat()
            save(path, state)
        report.update(status="completed" if complete else "partial", counts=dict(counts), errors=errors)
    except BaseException as exc:
        report.update(
            status="failed", fatal_error=type(exc).__name__ + ": " + str(exc), counts=dict(counts), errors=errors
        )
        await jobs.finish(handle, counts["pages_ok"], counts["pages_failed"] + 1, report)
        save(config["data_dir"] / "reports" / (job_id + ".json"), report)
        raise
    report.update(finished_at=now(), elapsed_seconds=round(time.monotonic() - began, 3))
    await jobs.finish(handle, ok, counts["pages_failed"], report)
    save(config["data_dir"] / "reports" / (job_id + ".json"), report)
    return report
