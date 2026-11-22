"""Xóa điểm ký ức Qdrant và CLI lưu giữ 90 ngày với tài nguyên giả; phần SQL thật ở tests/integration/test_privacy.py.

Phụ trách: TV1 · [S5] Quyền riêng tư và xóa tài khoản
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.services import privacy
from core.errors import UnavailableError
from scripts import retention


class FakeQdrant:
    def __init__(self, exists=True, fail=False):
        self.exists, self.fail, self.deletes = exists, fail, []

    async def collection_exists(self, name):
        return self.exists

    async def delete(self, collection, points_selector, wait):
        if self.fail:
            raise ConnectionError("qdrant down")
        self.deletes.append((collection, points_selector, wait))


async def test_vectors_are_deleted_by_conversation_id_filter_in_bounded_chunks():
    client = FakeQdrant()
    ids = [uuid4() for _ in range(privacy._VECTOR_FILTER_CHUNK + 1)]
    await privacy.VectorPurger(client, "conversation_memories").delete_conversations(ids)
    assert len(client.deletes) == 2 and all(c == "conversation_memories" and wait for c, _, wait in client.deletes)
    condition = client.deletes[0][1].filter.must[0]
    assert condition.key == "conversation_id" and condition.match.any == [str(i) for i in ids[:200]]


@pytest.mark.parametrize("client,ids", [(None, [uuid4()]), (FakeQdrant(), []), (FakeQdrant(exists=False), [uuid4()])])
async def test_nothing_to_purge_is_a_quiet_no_op(client, ids):
    await privacy.VectorPurger(client, "conversation_memories").delete_conversations(ids)
    assert client is None or client.deletes == []


async def test_a_qdrant_failure_becomes_a_generic_503_without_internals_and_is_logged(caplog):
    with pytest.raises(UnavailableError) as raised, caplog.at_level("WARNING"):
        await privacy.VectorPurger(FakeQdrant(fail=True), "conversation_memories").delete_conversations([uuid4()])
    assert "qdrant down" not in str(raised.value)
    assert any(r.exc_info for r in caplog.records)  # chi tiết chỉ vào log máy chủ


async def test_a_programming_error_is_not_swallowed_as_a_qdrant_outage():
    class Broken(FakeQdrant):
        async def delete(self, *args, **kwargs):
            raise KeyError("bug")

    with pytest.raises(KeyError):
        await privacy.VectorPurger(Broken(), "conversation_memories").delete_conversations([uuid4()])


def test_counts_add_and_the_cli_prints_counts_only():
    total = privacy.Counts(conversations=1, messages=2)
    total.add(privacy.Counts(conversations=2, feedback=1, sessions=4))
    assert total == privacy.Counts(conversations=3, messages=2, feedback=1, sessions=4)
    assert retention.format_counts(total, dry_run=True) == (
        "would delete: conversations=3 messages=2 feedback=1 expired_sessions=4 traces=0 ingestion_logs=0"
    )
    assert retention.format_counts(total, dry_run=False).startswith("deleted: ")


async def test_the_cli_turns_days_into_a_cutoff(monkeypatch):
    seen = {}

    async def fake_apply(sessionmaker, qdrant, collection, **kwargs):
        seen.update(kwargs, collection=collection)
        return privacy.Counts()

    monkeypatch.setattr(retention, "apply_retention", fake_apply)
    now = datetime(2026, 11, 16, tzinfo=UTC)
    await retention.run(object(), None, "mem", days=90, dry_run=True, now=now)
    assert seen == {"cutoff": datetime(2026, 8, 18, tzinfo=UTC), "now": now, "dry_run": True, "collection": "mem"}


def test_the_cli_rejects_a_non_positive_window(capsys):
    with pytest.raises(SystemExit):
        retention.main(["--days", "0"])
    assert "--days" in capsys.readouterr().err


def test_retention_queries_target_only_guest_web_and_old_traces():
    from sqlalchemy.dialects import postgresql

    sql = str(privacy._stale_ids(datetime(2026, 8, 18, tzinfo=UTC)).compile(dialect=postgresql.dialect()))
    assert "conversations.channel" in sql and "conversations.user_id IS NULL" in sql
    assert "FOR UPDATE" in str(
        privacy._guest_batch(datetime(2026, 8, 18, tzinfo=UTC)).compile(dialect=postgresql.dialect())
    )
    assert "rag_trace IS NOT NULL" in str(
        privacy._old_traces(datetime(2026, 8, 18, tzinfo=UTC)).compile(dialect=postgresql.dialect())
    )


def test_log_cleanup_limits_scope_and_honors_cutoff_and_dry_run(tmp_path):
    import os
    from datetime import timedelta

    now = datetime(2026, 11, 16, tzinfo=UTC)
    old = tmp_path / "ingest-weekly-20260101-000000.log"
    fresh = tmp_path / "ingest-weekly-20261115-000000.log"
    unrelated = tmp_path / "other.log"
    old.write_text("old")
    fresh.write_text("new")
    unrelated.write_text("other")
    timestamp = (now - timedelta(days=91)).timestamp()
    os.utime(old, (timestamp, timestamp))
    os.utime(unrelated, (timestamp, timestamp))
    assert retention.prune_ingest_logs(tmp_path, cutoff=now - timedelta(days=90), dry_run=True) == 1
    assert old.exists()
    assert retention.prune_ingest_logs(tmp_path, cutoff=now - timedelta(days=90), dry_run=False) == 1
    assert not old.exists() and fresh.exists() and unrelated.exists()


def test_log_cleanup_excludes_boundary_links_and_subdirectories(tmp_path):
    import os
    from contextlib import suppress

    cutoff = datetime(2026, 8, 18, tzinfo=UTC)
    boundary = tmp_path / "ingest-weekly-20260818-000000.log"
    boundary.write_text("keep")
    os.utime(boundary, (cutoff.timestamp(), cutoff.timestamp()))
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "ingest-weekly-20200101-000000.log").write_text("keep")
    link = tmp_path / "ingest-weekly-20200101-000000.log"
    with suppress(OSError):  # Windows may not permit creating symlinks
        link.symlink_to(boundary)
    assert retention.prune_ingest_logs(tmp_path, cutoff=cutoff, dry_run=False) == 0
    assert boundary.exists() and nested.exists()


def test_old_trace_and_ingestion_log_updates_write_sql_null_and_exclude_json_null():
    from sqlalchemy.dialects import postgresql

    cutoff = datetime(2026, 8, 18, tzinfo=UTC)
    for statement in (privacy._clear_old_traces(cutoff), privacy._clear_old_ingestion_logs(cutoff)):
        sql = str(statement.compile(dialect=postgresql.dialect()))
        assert "SET " in sql and "=NULL" in sql
        assert "jsonb_typeof" in sql and "IS NOT NULL" in sql
        assert "LIMIT" in sql


def test_ingestion_log_query_uses_completion_time_and_keeps_unfinished_jobs():
    from sqlalchemy.dialects import postgresql

    sql = str(privacy._old_ingestion_logs(datetime(2026, 8, 18, tzinfo=UTC)).compile(dialect=postgresql.dialect()))
    assert "ingestion_jobs.finished_at" in sql and "ingestion_jobs.log" in sql
