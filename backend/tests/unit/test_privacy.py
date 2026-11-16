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
    await privacy.purge_memory_vectors(client, "conversation_memories", ids)
    assert len(client.deletes) == 2 and all(c == "conversation_memories" and wait for c, _, wait in client.deletes)
    condition = client.deletes[0][1].filter.must[0]
    assert condition.key == "conversation_id" and condition.match.any == [str(i) for i in ids[:200]]


@pytest.mark.parametrize("client,ids", [(None, [uuid4()]), (FakeQdrant(), []), (FakeQdrant(exists=False), [uuid4()])])
async def test_nothing_to_purge_is_a_quiet_no_op(client, ids):
    await privacy.purge_memory_vectors(client, "conversation_memories", ids)
    assert client is None or client.deletes == []


async def test_a_qdrant_failure_becomes_a_generic_503_without_internals():
    with pytest.raises(UnavailableError) as raised:
        await privacy.purge_memory_vectors(FakeQdrant(fail=True), "conversation_memories", [uuid4()])
    assert "qdrant down" not in str(raised.value)


def test_counts_add_and_the_cli_prints_counts_only():
    total = privacy.Counts(conversations=1, messages=2)
    total.add(privacy.Counts(conversations=2, feedback=1, sessions=4))
    assert total == privacy.Counts(conversations=3, messages=2, feedback=1, sessions=4)
    assert retention.format_counts(total, dry_run=True) == (
        "would delete: conversations=3 messages=2 feedback=1 expired_sessions=4"
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
