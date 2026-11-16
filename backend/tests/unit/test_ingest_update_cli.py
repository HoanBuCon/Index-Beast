"""Bootstrap state và CLI `update` (không mạng, không DB thật)."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from ingest.__main__ import main
from ingest.settings import load_settings
from ingest.update import bootstrap_from_chunk_dir, bootstrap_from_documents


def test_bootstrap_from_chunk_dir_reads_revisions_chunk_counts_and_earliest_fetch(tmp_path):
    (tmp_path / "wikigg").mkdir()
    docs = [
        {"source_id": "1", "title": "A", "revision_id": 5, "fetched_at": "2026-10-28T10:00:00+00:00"},
        {"source_id": "2", "title": "B", "revision_id": 7, "fetched_at": "2026-10-27T10:00:00+00:00"},
    ]
    (tmp_path / "documents.jsonl").write_text("\n".join(map(json.dumps, docs)) + "\n", encoding="utf-8")
    (tmp_path / "wikigg" / "1.jsonl").write_text('{"ordinal": 0}\n{"ordinal": 1}\n', encoding="utf-8")
    state = bootstrap_from_chunk_dir(tmp_path)
    assert state["pages"] == {
        "1": {"revision_id": 5, "title": "A", "chunks": 2},
        "2": {"revision_id": 7, "title": "B", "chunks": 0},
    }
    assert state["watermark"] == "2026-10-27T10:00:00+00:00"


def test_bootstrap_without_fetch_time_forces_a_full_scan_on_first_run():
    assert bootstrap_from_documents([{"source_id": "1", "revision_id": 1, "title": "A"}])["watermark"] is None


def test_update_without_state_exits_2_with_a_clear_message(tmp_path, monkeypatch, capsys):
    from ingest import update_cli

    config = load_settings()
    config["data_dir"] = tmp_path
    args = SimpleNamespace(source="wikigg", dry_run=True)

    async def no_state(args, config):
        raise update_cli.StateMissing("Chưa có state")

    monkeypatch.setattr(update_cli, "run", no_state)
    assert update_cli.run_cli(args, config) == 2
    assert "Chưa có state" in capsys.readouterr().err
    assert not (tmp_path / "state").exists()


def test_update_command_is_registered_and_rejects_unknown_flags(capsys):
    with pytest.raises(SystemExit):
        main(["update", "--no-such-flag"])
    assert "unrecognized" in capsys.readouterr().err


def test_pg_documents_module_imports_and_its_statements_compile_for_postgres():
    from sqlalchemy import delete, update

    import ingest.chunk.sync  # noqa: F401
    from core.db.models import Chunk, Document

    for statement in (
        delete(Chunk).where(Chunk.document_id.in_([1])),
        update(Document).where(Document.id.in_([1])).values(status="deleted"),
    ):
        assert str(statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_cli_dry_run_bootstrap_does_not_persist_state(tmp_path, monkeypatch):
    from core.config import Settings
    from ingest import update_cli

    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "documents.jsonl").write_text('{"source_id":"1","title":"Test","revision_id":4}\n', encoding="utf-8")
    config = load_settings()
    config["data_dir"] = tmp_path / "data"
    config["crawl"]["contact_email"] = "ingest-test@example.org"
    settings = Settings(_env_file=None)
    monkeypatch.setattr("core.config.get_settings", lambda: settings)

    async def inspect_plan(source, config, **kwargs):
        assert kwargs["dry_run"]
        assert kwargs["state"]["pages"]["1"]["revision_id"] == 4
        assert not update_cli.state_path(config, "wikigg").exists()
        return {"status": "dry_run"}

    monkeypatch.setattr(update_cli, "run_update", inspect_plan)
    args = SimpleNamespace(
        source="wikigg",
        bootstrap_from=seed,
        bootstrap_from_db=False,
        dry_run=True,
        collection=None,
        policy=None,
        languages=None,
        since=None,
        full_scan=False,
        max_pages=None,
        batch_pages=None,
    )
    assert (await update_cli.run(args, config))["status"] == "dry_run"
    assert not update_cli.state_path(config, "wikigg").exists()


def test_update_state_rejects_a_different_collection():
    from ingest.update_cli import validate_target

    previous = {"target": {"collection": "existing"}}
    with pytest.raises(ValueError, match="Đích"):
        validate_target(previous, {"collection": "new"}, dry_run=False)
    validate_target(previous, {"collection": "existing"}, dry_run=False)


def test_update_unbound_checkpoint_requires_operator_to_verify_bootstrap():
    from ingest.update_cli import validate_target

    with pytest.raises(ValueError, match="bootstrap"):
        validate_target({"pages": {"1": {}}}, {"collection": "new"}, dry_run=False)
    validate_target({"pages": {"1": {}}}, {"collection": "new"}, dry_run=True)


@pytest.mark.asyncio
async def test_update_refuses_to_create_an_empty_baseline_collection(tmp_path, monkeypatch):
    from core.config import Settings
    from ingest import update_cli

    config = load_settings()
    config["data_dir"] = tmp_path / "data"
    config["crawl"]["contact_email"] = "ingest-test@example.org"
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "documents.jsonl").write_text('{"source_id":"1","title":"Ranni","revision_id":4}\n', encoding="utf-8")
    monkeypatch.setattr("core.config.get_settings", lambda: Settings(_env_file=None))

    class MissingCollection:
        async def collection_exists(self, name):
            assert name == "missing"
            return False

        async def close(self):
            pass

    monkeypatch.setattr("qdrant_client.AsyncQdrantClient", lambda **kwargs: MissingCollection())
    args = SimpleNamespace(
        source="wikigg",
        bootstrap_from=seed,
        bootstrap_from_db=False,
        dry_run=False,
        collection="missing",
        policy=None,
        languages=None,
    )
    with pytest.raises(ValueError, match="Collection Qdrant chưa tồn tại"):
        await update_cli.run(args, config)
    assert not update_cli.state_path(config, "wikigg").exists()


@pytest.mark.parametrize(
    "pages",
    [[], [{"pageid": 1, "lastrevid": 4}], [{"pageid": 1, "title": "Ranni"}, {"pageid": 2, "missing": True}]],
)
def test_update_aborts_if_description_is_incomplete(pages):
    from ingest.crawl.http import CrawlError
    from ingest.update import classify

    source = SimpleNamespace(describe=lambda ids: pages)
    config = load_settings()
    state = bootstrap_from_documents([{"source_id": "1", "revision_id": 4, "title": "Ranni"}])
    with pytest.raises(CrawlError, match="metadata"):
        classify(source, config, state, ["1", "2"], None)


def test_description_accepts_explicit_missing_pageid_and_rejects_ambiguous_metadata(monkeypatch):
    from ingest.crawl.http import CrawlError
    from ingest.sources.wikigg import WikiGG

    source = WikiGG(None, load_settings())
    response = {"query": {"pages": [{"pageid": 2, "missing": True}]}}
    monkeypatch.setattr(source, "api", lambda **params: response)
    assert source.describe([2]) == [{"pageid": 2, "missing": True, "categories": []}]
    response["query"]["pages"] = [{"missing": True}]
    with pytest.raises(CrawlError, match="pageid"):
        source.describe([2])
    response.clear()
    with pytest.raises(CrawlError, match="page metadata"):
        source.describe([2])
