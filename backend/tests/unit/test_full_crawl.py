from copy import deepcopy

import pytest

from ingest.artifacts import read, sha256
from ingest.crawl.full import inventory, run


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
