"""Synthetic-only artifact/vector tests: no model download/inference or external services.

Phụ trách: TV3 · [S2] Embedding/indexing/retrieval
"""

import json
from array import array
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from qdrant_client import AsyncQdrantClient, models

from app.rag.retriever import HybridRetriever, document_to_hit, hit_to_document
from core.encoders.onnx import FastEmbedEncoder, prefixed
from core.errors import UnavailableError
from core.types import ChunkRecord, Encoded, Hit
from core.vector.schema import ensure_collection
from core.vector.store import QdrantStore
from ingest.indexing import index_chunks, load_chunks


def record(**extra):
    return {
        "chunk_id": "tv2-hash-of-unit-span-content",
        "doc_id": "tv2-doc-hash",
        "source": "wikigg",
        "source_id": "42",
        "title": "Synthetic Ranni",
        "section": "Lore",
        "text": "Synthetic test text.",
        "embedding_text": "passage: Synthetic Ranni\nLore\nSynthetic test text.",
        "url": "https://example.test/ranni#Lore",
        "game_scope": "base",
        "source_type": "wiki_prose",
        "lang": "en",
        "token_count": 20,
        "review_status": "approved",
        "source_updated_at": None,
        "updated_at": "2026-10-28T00:00:00Z",
        "spoiler_level": 0,
        **extra,
    }


class SyntheticEncoder:
    def __init__(self):
        self.calls = []

    async def encode(self, texts, *, query=False):
        self.calls.append((texts, query))
        return [Encoded([1.0] + [0.0] * 383, [1, 3], [1.0, 0.5]) for _ in texts]


def test_id_mapping_retains_artifact_identity_and_provenance():
    original = record()
    chunk = ChunkRecord.model_validate(original)
    again = ChunkRecord.model_validate(record(updated_at="later"))
    assert chunk.point_uuid == again.point_uuid
    assert str(chunk.point_uuid) != chunk.chunk_id
    payload = chunk.payload()
    assert payload["doc_id"] == original["doc_id"]
    assert payload["artifact_chunk_id"] == original["chunk_id"]
    assert payload["source_updated_at"] is None
    assert payload["updated_at"] == original["updated_at"]
    assert ChunkRecord.model_validate(record(source_id="43")).point_uuid != chunk.point_uuid
    assert ChunkRecord.model_validate(record(chunk_id="new-span")).point_uuid != chunk.point_uuid


def test_langchain_document_roundtrip_is_lossless_and_does_not_alias_source():
    chunk = ChunkRecord.model_validate(record(revision="123", custom={"id": "x", "list": [1, None]}))
    payload = chunk.payload()
    payload.update(id="source-id", point_id="source-point", retrieval_score="source-score")
    original = Hit(str(chunk.point_uuid), 0.123, payload)
    document = hit_to_document(original)
    assert document.id == original.id and document.page_content == original.payload["text"]
    restored = document_to_hit(document)
    assert restored == original
    restored.payload["custom"]["list"].append(2)
    assert document.metadata["payload"]["custom"]["list"] == [1, None]
    document.metadata["payload"]["custom"]["id"] = "changed"
    assert original.payload["custom"]["id"] == "x"
    document.page_content = "Untracked replacement text"
    with pytest.raises(ValueError, match="original source"):
        document_to_hit(document)


async def test_qdrant_hybrid_uses_both_vectors_rrf_and_filters_every_query_branch():
    client = AsyncMock()
    client.query_points.return_value = SimpleNamespace(points=[])
    store = QdrantStore(client, "existing-collection")
    await store.search(Encoded([0.0] * 384, [7], [1.0]), limit=30, spoilers=False)
    args = client.query_points.call_args
    assert args.args == ("existing-collection",)
    query = args.kwargs
    assert query["query"].fusion == models.Fusion.RRF and query["limit"] == 30
    assert [p.using for p in query["prefetch"]] == ["dense", "bm25"]
    assert len(query["prefetch"][0].query) == 384
    assert query["prefetch"][1].query.indices == [7]
    for filters in [query["query_filter"], *[p.filter for p in query["prefetch"]]]:
        conditions = {c.key: c for c in filters.must}
        assert conditions["game_scope"].match.value == "base"
        assert conditions["review_status"].match.value == "approved"
        assert conditions["spoiler_level"].range.lte == 0


def test_unknown_metadata_is_rejected_without_changing_source(tmp_path):
    path = tmp_path / "chunks.jsonl"
    rows = [
        record(),
        record(chunk_id="2", source_type="unknown"),
        record(chunk_id="3", lang="unknown"),
        record(chunk_id="4", game_scope=None),
        record(chunk_id="5", review_status="review"),
        record(chunk_id="6", scope_status="excluded"),
    ]
    content = "".join(json.dumps(r) + "\n" for r in rows)
    path.write_text(content, encoding="utf-8")
    chunks, rejected = load_chunks(path)
    assert len(chunks) == 1 and len(rejected) == 5
    assert path.read_text(encoding="utf-8") == content
    assert chunks[0].embedding_text.startswith("passage:")


def test_dry_run_cli_never_constructs_encoder_or_client(tmp_path, monkeypatch, capsys):
    from ingest.__main__ import main

    path = tmp_path / "chunks.jsonl"
    path.write_text(json.dumps(record()), encoding="utf-8")
    monkeypatch.setattr(FastEmbedEncoder, "__init__", lambda *_a, **_kw: pytest.fail("encoder created"))
    monkeypatch.setattr(AsyncQdrantClient, "__init__", lambda *_a, **_kw: pytest.fail("client created"))
    assert main(["index", "--input", str(path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["accepted"] == 1


@pytest.mark.parametrize(
    "text,query,expected",
    [
        ("Ranni", True, "query: Ranni"),
        ("query: Ranni", True, "query: Ranni"),
        ("Ranni", False, "passage: Ranni"),
        ("passage: Ranni", False, "passage: Ranni"),
    ],
)
def test_e5_prefix_is_added_once(text, query, expected):
    assert prefixed(text, query=query) == expected


@pytest.mark.parametrize("text,query", [("passage: passage: text", False), ("query: text", False)])
def test_e5_repeated_or_wrong_prefix_is_an_error(text, query):
    with pytest.raises(ValueError):
        prefixed(text, query=query)


async def test_lazy_encoder_constructor_has_no_models(tmp_path):
    encoder = FastEmbedEncoder(tmp_path)
    assert encoder._dense is None and encoder._sparse is None
    assert not list(tmp_path.iterdir())


async def test_encoder_reuses_models_checks_actual_budget_and_recovers_failed_sparse_init(monkeypatch, tmp_path):
    import fastembed

    calls = {"dense_init": 0, "sparse_init": 0, "embed": [], "threads": []}

    class Dense:
        @staticmethod
        def list_supported_models():
            return [{"model": "intfloat/multilingual-e5-small"}]

        def __init__(self, **kwargs):
            calls["dense_init"] += 1
            calls["threads"].append(kwargs["threads"])
            self.model = SimpleNamespace(
                tokenizer=SimpleNamespace(
                    no_truncation=lambda: None,
                    encode=lambda text: SimpleNamespace(ids=[1] * (513 if "oversized" in text else 5)),
                )
            )

        def embed(self, texts):
            calls["embed"].append(texts)
            return [array("f", [1.0] + [0.0] * 383) for _ in texts]

    def sparse(**kwargs):
        calls["sparse_init"] += 1
        calls["threads"].append(kwargs["threads"])
        if calls["sparse_init"] == 1:
            raise RuntimeError("synthetic init failure")
        vector = SimpleNamespace(indices=array("I", [1]), values=array("f", [1.0]))
        return SimpleNamespace(
            embed=lambda texts: [vector for _ in texts], query_embed=lambda texts: [vector for _ in texts]
        )

    monkeypatch.setattr(fastembed, "TextEmbedding", Dense)
    monkeypatch.setattr(fastembed, "SparseTextEmbedding", sparse)
    encoder = FastEmbedEncoder(tmp_path, threads=4)
    with pytest.raises(RuntimeError):
        await encoder.encode(["passage: Ranni"])
    await encoder.encode(["passage: Ranni"])
    await encoder.encode(["query: Ranni"], query=True)
    with pytest.raises(ValueError, match="512"):
        await encoder.encode(["oversized"])
    assert calls["dense_init"] == 1 and calls["sparse_init"] == 2
    assert calls["threads"] == [4, 4, 4]
    assert calls["embed"] == [["passage: Ranni"], ["query: Ranni"]]


async def test_empty_collection_is_unavailable_before_encoder_load():
    client = AsyncQdrantClient(location=":memory:")
    encoder = SyntheticEncoder()
    try:
        await client.create_collection(
            "empty",
            vectors_config={"dense": models.VectorParams(size=384, distance="Cosine")},
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier="idf")},
        )
        with pytest.raises(UnavailableError, match="chưa có dữ liệu"):
            await HybridRetriever(encoder, QdrantStore(client, "empty")).retrieve("Ranni")
        assert not encoder.calls
    finally:
        await client.close()


async def test_collection_missing_is_checked_before_encoding():
    client, encoder = AsyncMock(), SyntheticEncoder()
    client.collection_exists.return_value = False
    retriever = HybridRetriever(encoder, QdrantStore(client, "missing"))
    with pytest.raises(UnavailableError):
        await retriever.retrieve("Ranni")
    assert not encoder.calls
    client.create_collection.assert_not_called()


async def test_direct_indexing_cannot_bypass_review_and_duplicate_checks():
    client, encoder = AsyncMock(), SyntheticEncoder()
    store = QdrantStore(client, "never_created")
    unreviewed = ChunkRecord.model_validate(record(review_status="review"))
    with pytest.raises(ValueError):
        await index_chunks([unreviewed], encoder, store, 32)
    approved = ChunkRecord.model_validate(record())
    with pytest.raises(ValueError):
        await index_chunks([approved, approved], encoder, store, 32)
    client.create_collection.assert_not_called()
    client.collection_exists.assert_not_called()
    assert not encoder.calls


async def test_real_query_api_with_synthetic_vectors_is_idempotent_and_filters_metadata():
    # Qdrant local memory only. Vectors are explicit numbers, not model embeddings.
    client = AsyncQdrantClient(location=":memory:")
    encoder, store = SyntheticEncoder(), QdrantStore(client, "synthetic_only")
    try:
        chunks = [
            ChunkRecord.model_validate(record()),
            ChunkRecord.model_validate(record(chunk_id="spoiler", spoiler_level=2)),
        ]
        assert await index_chunks(chunks, encoder, store, 1) == 2
        await index_chunks(chunks, encoder, store, 2)
        assert (await client.count("synthetic_only", exact=True)).count == 2
        retriever = HybridRetriever(encoder, store, limit=5)
        results = await retriever.retrieve("Ranni", spoilers=False)
        assert len(results) == 1 and results[0].id == str(chunks[0].point_uuid)
        assert encoder.calls[-1] == (["Ranni"], True)
        # Bypass index adapter to confirm search still refuses non-base/unapproved payloads.
        await client.upsert(
            "synthetic_only",
            points=[
                models.PointStruct(
                    id="00000000-0000-0000-0000-000000000001",
                    vector={"dense": [1.0] + [0.0] * 383, "bm25": models.SparseVector(indices=[1], values=[1.0])},
                    payload=record(game_scope="other", review_status="review"),
                )
            ],
        )
        assert len(await retriever.retrieve("Ranni", spoilers=False)) == 1
    finally:
        await client.close()


async def test_incompatible_collection_is_not_recreated():
    client = AsyncQdrantClient(location=":memory:")
    try:
        await client.create_collection(
            "wrong", vectors_config={"dense": models.VectorParams(size=3, distance="Cosine")}
        )
        with pytest.raises(UnavailableError):
            await ensure_collection(client, "wrong", create=True)
        assert (await client.get_collection("wrong")).config.params.vectors["dense"].size == 3
    finally:
        await client.close()
