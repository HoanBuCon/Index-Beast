"""PipelineBuilder: nối fetch -> transform.full -> chunk.full bằng stage giả; không mạng, không tokenizer thật."""

import json

import pytest

from ingest import update_builder
from ingest.artifacts import read, sha256
from ingest.update_builder import PipelineBuilder, tokenizer_path


class Source:
    name = "wikigg"
    client = None

    def __init__(self, fail=()):
        self.fail = set(fail)

    def fetch(self, page):
        if str(page["pageid"]) in self.fail:
            raise update_builder.CrawlError("boom")
        content = "html " + page["title"]
        return {
            "source_id": str(page["pageid"]),
            "title": page["title"],
            "revision_id": page["lastrevid"],
            "content": content,
            "content_hash": sha256(content.encode()),
        }


def fake_stages(monkeypatch, bad=()):
    seen = {}

    def transform(run_dir, output, **kw):
        seen["transform"] = (read(run_dir / "report.json"), kw)
        if any(p["id"] in bad for p in seen["transform"][0]["pages"]):
            raise ValueError("clean failed")
        (output).mkdir(parents=True)
        seen["root"] = run_dir.parents[1]
        return {}

    def chunk(input_dir, tokenizer, output, **kw):
        seen["chunk"] = kw
        pages = read(input_dir.parent / "report.json")["pages"]
        (output / "wikigg").mkdir(parents=True)
        docs = []
        for p in pages:
            doc = {"source_id": p["id"], "doc_id": "d" + p["id"], "title": p["title"], "revision_id": p["revision_id"]}
            docs.append(json.dumps(doc))
            rows = [json.dumps({"doc_id": "d" + p["id"], "ordinal": 0})]
            (output / "wikigg" / (p["id"] + ".jsonl")).write_text("\n".join(rows) + "\n", encoding="utf-8")
        (output / "documents.jsonl").write_text("\n".join(docs) + "\n", encoding="utf-8")

    monkeypatch.setattr(update_builder, "transform_run", transform)
    monkeypatch.setattr(update_builder, "chunk_run", chunk)
    return seen


def pages(*ids):
    return [{"pageid": i, "title": f"T{i}", "lastrevid": 100 + i} for i in ids]


def test_batch_runs_production_stages_with_the_s4_flags(tmp_path, monkeypatch):
    seen = fake_stages(monkeypatch)
    builder = PipelineBuilder(Source(), {"data_dir": tmp_path}, tmp_path / "tokenizer.json", media=False)
    built, errors = builder.build(pages(1, 2))
    assert not errors and set(built) == {"1", "2"} and len(built["1"]["chunks"]) == 1
    report, kw = seen["transform"]
    assert kw == {"gameplay": True, "structured_tables": True} and seen["chunk"] == {"wiki_quality": True}
    entry = report["pages"][0]
    assert (tmp_path / entry["path"]).exists() and (tmp_path / entry["media_manifest"]).exists()
    assert entry["path"].startswith("raw/wikigg/snapshots/1/101-")


def test_fetch_failure_only_drops_that_page(tmp_path, monkeypatch):
    fake_stages(monkeypatch)
    builder = PipelineBuilder(Source(fail={"1"}), {"data_dir": tmp_path}, tmp_path / "t.json", media=False)
    built, errors = builder.build(pages(1, 2))
    assert set(built) == {"2"} and "boom" in errors["1"]


def test_failed_batch_is_split_so_one_bad_page_does_not_lose_the_others(tmp_path, monkeypatch):
    fake_stages(monkeypatch, bad={"2"})
    builder = PipelineBuilder(Source(), {"data_dir": tmp_path}, tmp_path / "t.json", media=False)
    built, errors = builder.build(pages(1, 2, 3))
    assert set(built) == {"1", "3"} and "clean failed" in errors["2"]


def test_tokenizer_lookup_requires_a_local_file(tmp_path):
    with pytest.raises(ValueError):
        tokenizer_path(tmp_path)
    target = tmp_path / "models--intfloat--multilingual-e5-small" / "snapshots" / "abc"
    target.mkdir(parents=True)
    (target / "tokenizer.json").write_text("{}")
    assert tokenizer_path(tmp_path) == target / "tokenizer.json"
