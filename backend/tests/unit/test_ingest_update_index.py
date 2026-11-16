"""QdrantIndex cho cập nhật tăng dần: upsert theo document rồi xoá point thừa; client và encoder giả."""

from unittest.mock import AsyncMock

from qdrant_client import models

from core.corpus import CorpusPolicy
from core.ids import chunk_id, document_id
from core.types import ChunkRecord, Encoded
from ingest.index.writer import QdrantIndex

DOC = document_id("wikigg", "42")


def row(ordinal, lang="en", **extra):
    return {
        "chunk_id": str(chunk_id(DOC, ordinal)),
        "source": "wikigg",
        "source_id": "42",
        "title": "Ranni",
        "section": "Lore",
        "text": f"Text {ordinal}",
        "embedding_text": f"passage: Ranni\nText {ordinal}",
        "url": "https://example.test/Ranni",
        "game_scope": "elden_ring",
        "source_type": "wiki_prose",
        "lang": lang,
        "token_count": 12,
        "spoiler_level": 1,
        **extra,
    }


class Encoder:
    def __init__(self):
        self.batches = []

    async def encode(self, texts, *, query=False):
        self.batches.append(list(texts))
        return [Encoded([1.0] + [0.0] * 383, [1], [1.0]) for _ in texts]


def make(batch_size=32):
    client, encoder = AsyncMock(), Encoder()
    return QdrantIndex(client, "test", encoder, CorpusPolicy("pilot", ("en",)), batch_size), client, encoder


def point_ids(client):
    return [p.id for call in client.upsert.call_args_list for p in call.kwargs["points"]]


async def test_sync_upserts_stable_ids_then_deletes_only_stale_points_of_that_document():
    index, client, encoder = make()
    rows = [row(0), row(1), row(2)]
    result = await index.sync({str(DOC): rows})
    expected = [str(ChunkRecord.model_validate(r).point_uuid) for r in rows]
    assert point_ids(client) == expected and result == {"upserted": 3, "excluded": 0}
    selector = client.delete.call_args.kwargs["points_selector"].filter
    assert selector.must[0].match.value == str(DOC) and selector.must_not[0].has_id == expected
    assert [c[0] for c in client.method_calls[:2]] == ["upsert", "delete"]  # upsert trước, xoá thừa sau


async def test_resync_gives_identical_points_so_the_update_is_idempotent():
    index, client, encoder = make()
    await index.sync({str(DOC): [row(0), row(1)]})
    first = point_ids(client)
    await index.sync({str(DOC): [row(0), row(1)]})
    assert point_ids(client) == first * 2


async def test_policy_excluded_chunks_are_not_indexed_and_a_fully_excluded_doc_is_cleared():
    index, client, encoder = make()
    result = await index.sync({str(DOC): [row(0, lang="ja")]})
    assert result == {"upserted": 0, "excluded": 1} and not client.upsert.called
    selector = client.delete.call_args.kwargs["points_selector"].filter
    assert selector.must_not is None  # không còn chunk nào hợp lệ: xoá hết point của tài liệu


async def test_encoding_is_batched_across_documents():
    index, client, encoder = make(batch_size=2)
    other = document_id("wikigg", "43")
    await index.sync(
        {str(DOC): [row(0), row(1)], str(other): [row(0, source_id="43", chunk_id=str(chunk_id(other, 0)))]}
    )
    assert [len(b) for b in encoder.batches] == [2, 1]


async def test_delete_removes_all_points_of_each_document():
    index, client, _ = make()
    await index.delete([str(DOC), str(document_id("wikigg", "7"))])
    assert client.delete.call_count == 2
    selector = client.delete.call_args_list[0].kwargs["points_selector"]
    assert isinstance(selector, models.FilterSelector) and selector.filter.must_not is None
