"""Điều phối cập nhật tăng dần (FR-ING-07) với fake wiki/builder/index/DB/jobs: không mạng, không model.

Phụ trách: TV2 · [S5] Cập nhật dữ liệu tăng dần
"""

from datetime import UTC, datetime, timedelta

import pytest

from core.ids import document_id
from ingest.artifacts import read, save
from ingest.update import StateMissing, bootstrap_from_documents, run_update, state_path


def iso(days_ago=1):
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


class Wiki:
    """pages[id] = {"title", "rev", "cats", "missing", "redirect"}; changes = các dòng recentchanges."""

    name = "wikigg"

    def __init__(self, pages, changes=()):
        self.pages, self.changes = pages, list(changes)
        self.describe_calls, self.since_seen = [], []

    def recent_changes(self, since):
        self.since_seen.append(since)
        return self.changes

    def describe(self, ids):
        self.describe_calls.append(list(ids))
        out = []
        for i in ids:
            p = self.pages.get(i, {"missing": True})
            page = {"pageid": i, "ns": 0, "title": p.get("title", ""), "lastrevid": p.get("rev")}
            page["categories"] = [{"ns": 14, "title": "Category:" + c} for c in p.get("cats", ["NPC"])]
            if p.get("missing"):
                page["missing"] = True
            if p.get("redirect"):
                page["redirect"] = True
            out.append(page)
        return out

    def list_category(self, category):
        members = [
            {"ns": 0, "pageid": i, "title": p["title"]}
            for i, p in self.pages.items()
            if "NPC" in p.get("cats", ["NPC"]) and not p.get("missing")
        ]
        return members if category == "NPC" else []


class Builder:
    def __init__(self, wiki, chunks=2, fail=()):
        self.wiki, self.chunks, self.fail, self.built = wiki, chunks, set(fail), []

    def build(self, pages):
        built, errors = {}, {}
        for page in pages:
            key = str(page["pageid"])
            if key in self.fail:
                errors[key] = "fetch failed"
                continue
            self.built.append(key)
            rev = self.wiki.pages[page["pageid"]]["rev"]
            doc = {"source_id": key, "title": page["title"], "revision_id": rev}
            built[key] = {"doc": doc, "chunks": [{"ordinal": n, "rev": rev} for n in range(self.chunks)]}
        return built, errors


class Index:
    def __init__(self, fail_on_sync=None):
        self.synced, self.deleted, self.prepared, self.fail_on_sync = [], [], 0, fail_on_sync

    async def prepare(self):
        self.prepared += 1

    async def sync(self, docs):
        if self.fail_on_sync is not None and len(self.synced) == self.fail_on_sync:
            raise RuntimeError("qdrant down")
        self.synced.append(docs)

    async def delete(self, ids):
        self.deleted.extend(ids)


class Docs:
    def __init__(self):
        self.synced, self.deleted = [], []

    async def sync(self, built):
        self.synced.extend(b["doc"]["source_id"] for b in built)

    async def delete(self, ids):
        self.deleted.extend(ids)


class Jobs:
    def __init__(self):
        self.started, self.finished = [], []

    async def start(self, kind, source, external_id):
        self.started.append((kind, source, external_id))
        return external_id

    async def finish(self, handle, ok, failed, log):
        self.finished.append((handle, ok, failed, log["status"]))


@pytest.fixture
def env(tmp_path):
    config = {"data_dir": tmp_path, "sources": {"wikigg": {"categories": ["NPC"], "category_depth": 1}}}
    pages = {
        1: {"title": "Ranni", "rev": 10},
        2: {"title": "Melina", "rev": 20},
        3: {"title": "Godrick", "rev": 30},
    }
    state = bootstrap_from_documents(
        [{"source_id": str(i), "revision_id": p["rev"], "title": p["title"], "chunks": 2} for i, p in pages.items()]
    )
    state["watermark"] = iso(1)
    save(state_path(config, "wikigg"), state)
    wiki = Wiki(pages)
    return config, wiki, Builder(wiki), Index(), Docs(), Jobs()


async def update(env, **kw):
    config, wiki, builder, index, docs, jobs = env
    return await run_update(wiki, config, builder=builder, index=index, docs=docs, jobs=jobs, **kw)


def edits(wiki, *ids):
    wiki.changes = [{"pageid": i, "title": wiki.pages[i]["title"], "type": "edit"} for i in ids]


async def test_missing_state_is_an_explicit_error(tmp_path):
    config = {"data_dir": tmp_path, "sources": {"wikigg": {"categories": []}}}
    with pytest.raises(StateMissing):
        await run_update(Wiki({}), config, builder=None, index=None, docs=None, jobs=None)


async def test_only_changed_new_and_deleted_pages_are_processed(env):
    config, wiki, builder, index, docs, jobs = env
    wiki.pages[1]["rev"] = 11  # sửa
    wiki.pages[4] = {"title": "Radagon", "rev": 40}  # mới
    wiki.pages[3] = {"missing": True}  # bị xoá
    wiki.changes = [
        {"pageid": 1, "title": "Ranni", "type": "edit"},
        {"pageid": 4, "title": "Radagon", "type": "new"},
        {"pageid": 3, "title": "Godrick", "type": "log"},
        {"pageid": 2, "title": "Melina", "type": "edit"},  # sửa rồi hoàn tác: revision không đổi
    ]
    report = await update(env)
    assert report["status"] == "completed"
    assert (report["new"], report["changed"], report["deleted"], report["unchanged"]) == (1, 1, 1, 1)
    assert sorted(builder.built) == ["1", "4"] and docs.deleted == ["3"]
    assert index.deleted == [str(document_id("wikigg", "3"))]
    assert set(index.synced[0]) == {str(document_id("wikigg", "1")), str(document_id("wikigg", "4"))}
    state = read(state_path(config, "wikigg"))
    assert state["pages"]["1"]["revision_id"] == 11 and "3" not in state["pages"] and "4" in state["pages"]
    assert jobs.started[0][:2] == ("update", "wikigg") and jobs.finished[0][1:] == (3, 0, "completed")


async def test_rerun_is_idempotent_and_describes_only_candidates(env):
    config, wiki, builder, index, docs, jobs = env
    wiki.pages[1]["rev"] = 11
    edits(wiki, 1)
    await update(env)
    again = await update(env)
    assert again["changed"] == 0 and again["new"] == 0 and builder.built == ["1"]
    assert all(call == [1] for call in wiki.describe_calls)  # recentchanges không bao giờ quét cả corpus


async def test_shrunk_page_sends_the_smaller_chunk_set_and_state_records_it(env):
    config, wiki, builder, index, docs, jobs = env
    wiki.pages[2]["rev"] = 21
    edits(wiki, 2)
    builder.chunks = 1
    await update(env)
    assert len(index.synced[0][str(document_id("wikigg", "2"))]) == 1  # index xoá point thừa dựa trên tập này
    assert read(state_path(config, "wikigg"))["pages"]["2"]["chunks"] == 1


async def test_page_failure_is_partial_keeps_watermark_and_retries_only_that_page(env):
    config, wiki, builder, index, docs, jobs = env
    before = read(state_path(config, "wikigg"))["watermark"]
    wiki.pages[1]["rev"], wiki.pages[2]["rev"] = 11, 21
    edits(wiki, 1, 2)
    builder.fail = {"1"}
    report = await update(env)
    state = read(state_path(config, "wikigg"))
    assert report["status"] == "partial" and report["errors"][0]["id"] == "1"
    assert state["pages"]["1"]["revision_id"] == 10 and state["pages"]["2"]["revision_id"] == 21
    assert state["watermark"] == before and jobs.finished[0][1:] == (1, 1, "partial")
    builder.fail, builder.built = set(), []
    final = await update(env)
    assert final["status"] == "completed" and builder.built == ["1"]
    assert read(state_path(config, "wikigg"))["watermark"] != before


async def test_resume_after_infrastructure_failure_skips_finished_batches(env):
    config, wiki, builder, index, docs, jobs = env
    for i in (1, 2, 3):
        wiki.pages[i]["rev"] += 1
    edits(wiki, 1, 2, 3)
    index.fail_on_sync = 1  # lô thứ hai lỗi
    with pytest.raises(RuntimeError):
        await update(env, batch_pages=2)
    assert jobs.finished[-1][3] == "failed"
    state = read(state_path(config, "wikigg"))
    assert state["pages"]["1"]["revision_id"] == 11 and state["pages"]["3"]["revision_id"] == 30
    index.fail_on_sync, builder.built = None, []
    report = await update(env, batch_pages=2)
    assert builder.built == ["3"] and report["status"] == "completed"


async def test_dry_run_touches_nothing(env):
    config, wiki, builder, index, docs, jobs = env
    wiki.pages[1]["rev"] = 11
    edits(wiki, 1)
    snapshot = state_path(config, "wikigg").read_bytes()
    report = await update(env, dry_run=True)
    assert report["dry_run"] and report["changed"] == 1 and report["titles"]["changed"] == ["Ranni"]
    assert not builder.built and not index.synced and not jobs.started
    assert state_path(config, "wikigg").read_bytes() == snapshot


async def test_max_pages_defers_the_rest_and_keeps_the_watermark(env):
    config, wiki, builder, index, docs, jobs = env
    before = read(state_path(config, "wikigg"))["watermark"]
    for i in (1, 2, 3):
        wiki.pages[i]["rev"] += 1
    edits(wiki, 1, 2, 3)
    report = await update(env, max_pages=2)
    assert report["deferred"] == 1 and report["status"] == "partial"
    assert read(state_path(config, "wikigg"))["watermark"] == before


async def test_stale_watermark_falls_back_to_full_scan_with_new_and_deleted_pages(env):
    config, wiki, builder, index, docs, jobs = env
    state = read(state_path(config, "wikigg"))
    state["watermark"] = iso(90)
    save(state_path(config, "wikigg"), state)
    wiki.pages[4] = {"title": "Radagon", "rev": 40}
    wiki.pages[3] = {"missing": True}
    report = await update(env)
    assert report["mode"] == "full_scan" and not wiki.since_seen
    assert (report["new"], report["deleted"], report["unchanged"]) == (1, 1, 2)
    assert builder.built == ["4"]


async def test_new_page_outside_configured_categories_is_skipped(env):
    config, wiki, builder, index, docs, jobs = env
    wiki.pages[5] = {"title": "Patch 1.0", "rev": 50, "cats": ["Patch_Notes"]}
    wiki.changes = [{"pageid": 5, "title": "Patch 1.0", "type": "new"}]
    report = await update(env)
    assert report["new"] == 0 and report["skipped_out_of_scope"] == 1 and not builder.built


async def test_redirect_is_removed_like_a_deletion(env):
    config, wiki, builder, index, docs, jobs = env
    wiki.pages[2] = {"title": "Melina", "rev": 21, "redirect": True}
    wiki.changes = [{"pageid": 2, "title": "Melina", "type": "log"}]
    report = await update(env)
    assert report["deleted"] == 1 and docs.deleted == ["2"] and "2" not in read(state_path(config, "wikigg"))["pages"]


async def test_deletion_log_entry_without_pageid_resolves_through_state_titles(env):
    config, wiki, builder, index, docs, jobs = env
    wiki.pages[3] = {"missing": True}
    wiki.changes = [{"pageid": 0, "title": "Godrick", "type": "log", "logtype": "delete"}]
    report = await update(env)
    assert report["deleted"] == 1 and docs.deleted == ["3"]
