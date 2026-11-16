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
    args = SimpleNamespace(source="wikigg")

    async def no_state(args, config):
        raise update_cli.StateMissing("Chưa có state")

    monkeypatch.setattr(update_cli, "run", no_state)
    assert update_cli.run_cli(args, config) == 2
    assert "Chưa có state" in capsys.readouterr().err


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
