from copy import deepcopy

import pytest

from ingest.artifacts import read, save, sha256
from ingest.crawl.full import inventory, run, run_lock, valid_media


class Source:
    name = "wikigg"
    client = None

    def __init__(self):
        self.downloads = 0
        self.revision = 1

    def list_category(self, category):
        return (
            [{"ns": 14, "pageid": 9, "title": "Category:Child"}]
            if category == "Root"
            else [{"ns": 14, "pageid": 8, "title": "Category:Root"}, {"ns": 0, "pageid": 1, "title": "Mixed page"}]
        )

    def describe(self, ids):
        return [{"ns": 0, "pageid": 1, "title": "Mixed page", "lastrevid": self.revision}]

    def fetch(self, page):
        self.downloads += 1
        return {
            "source_id": "1",
            "title": page["title"],
            "revision_id": self.revision,
            "content": "Base lore and DLC mention",
            "content_hash": sha256(b"Base lore and DLC mention"),
        }


def test_full_resume_revision_and_cycles(tmp_path):
    source = Source()
    config = {"data_dir": tmp_path, "sources": {"wikigg": {"categories": ["Root"]}}}
    directory = tmp_path / "crawl_runs" / "test"
    first = run(source, config, directory, media=False)
    assert first["inventory_pages"] == 1
    assert len(read(directory / "inventory.json")["visited"]) == 2
    original = deepcopy(first["pages"][0])
    second = run(source, config, directory, media=False)
    assert second["counts"]["cache_hits"] == 1
    assert source.downloads == 1
    source.revision = 2
    third = run(source, config, directory, media=False)
    assert source.downloads == 2
    assert third["pages"][0]["path"] != original["path"]
    assert read(tmp_path / original["path"])["revision_id"] == 1


def test_inventory_failure_does_not_mark_category_visited(tmp_path):
    class Broken(Source):
        def list_category(self, category):
            raise RuntimeError("network failure")

    config = {"sources": {"wikigg": {"categories": ["Root"]}}}
    with pytest.raises(RuntimeError):
        inventory(Broken(), config, tmp_path / "inventory.json")
    assert not (tmp_path / "inventory.json").exists()


def test_media_cache_checks_provenance_and_bytes(tmp_path):
    blob = tmp_path / "blob.jpg"
    blob.write_bytes(b"original image bytes")
    raw = {"source_id": "1", "revision_id": 2}
    entry = {"media_manifest": "manifest.json"}
    manifest = dict(
        raw,
        status="completed",
        images=[{"status": "downloaded", "path": "blob.jpg", "sha256": sha256(blob.read_bytes())}],
    )
    save(tmp_path / "manifest.json", manifest)
    assert valid_media(entry, raw, tmp_path)
    assert not valid_media(entry, dict(raw, revision_id=3), tmp_path)
    blob.write_bytes(b"corrupted")
    assert not valid_media(entry, raw, tmp_path)
    assert not valid_media({"media_manifest": "../outside.json"}, raw, tmp_path)


def test_run_lock_is_exclusive_and_released(tmp_path):
    with run_lock(tmp_path), pytest.raises(OSError), run_lock(tmp_path):
        pass
    with run_lock(tmp_path):
        pass


def test_resume_reuses_verified_media_without_network(tmp_path, monkeypatch):
    from ingest.crawl import full

    class Store:
        calls = 0

        def __init__(self, *args, **kwargs):
            pass

        def page(self, source, raw):
            Store.calls += 1
            return {
                "source_id": raw["source_id"],
                "revision_id": raw["revision_id"],
                "status": "completed",
                "images": [],
            }

    monkeypatch.setattr(full, "MediaStore", Store)
    source = Source()
    config = {"data_dir": tmp_path, "sources": {"wikigg": {"categories": ["Root"]}}}
    directory = tmp_path / "crawl_runs" / "test"
    run(source, config, directory)
    report = run(source, config, directory)
    assert Store.calls == 1
    assert source.downloads == 1
    assert report["counts"]["media_cache_hits"] == 1


def test_failed_media_still_checkpoints_raw(tmp_path, monkeypatch):
    from ingest.crawl import full

    class Store:
        def __init__(self, *args, **kwargs):
            pass

        def page(self, source, raw):
            return {
                "source_id": raw["source_id"],
                "revision_id": raw["revision_id"],
                "status": "completed_with_errors",
                "images": [],
            }

    monkeypatch.setattr(full, "MediaStore", Store)
    source = Source()
    config = {"data_dir": tmp_path, "sources": {"wikigg": {"categories": ["Root"]}}}
    directory = tmp_path / "crawl_runs" / "test"
    assert run(source, config, directory)["status"] == "partial"
    assert run(source, config, directory)["status"] == "partial"
    assert source.downloads == 1
