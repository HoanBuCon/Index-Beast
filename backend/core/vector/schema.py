"""Qdrant schema validation/creation; không drop hoặc recreate collection.

Phụ trách: TV3 · [S2] Embedding & indexing
"""

from qdrant_client import models

from core.errors import UnavailableError


async def ensure_collection(client, name: str, *, create: bool = False):
    if not await client.collection_exists(name):
        if not create:
            raise UnavailableError("Kho tri thức chưa sẵn sàng: chưa có collection RAG.")
        await client.create_collection(
            name,
            vectors_config={"dense": models.VectorParams(size=384, distance=models.Distance.COSINE)},
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
    info = await client.get_collection(name)
    params = info.config.params
    vectors = params.vectors
    dense = vectors.get("dense") if isinstance(vectors, dict) else None
    sparse = (params.sparse_vectors or {}).get("bm25")
    if dense is None or dense.size != 384 or dense.distance != models.Distance.COSINE:
        raise UnavailableError("Collection RAG không tương thích dense 384/cosine.")
    if sparse is None or sparse.modifier != models.Modifier.IDF:
        raise UnavailableError("Collection RAG không tương thích BM25/IDF.")
    if create:
        fields = (
            ("game_scope", models.PayloadSchemaType.KEYWORD),
            ("source_type", models.PayloadSchemaType.KEYWORD),
            ("document_id", models.PayloadSchemaType.KEYWORD),
            ("spoiler_level", models.PayloadSchemaType.INTEGER),
            ("review_status", models.PayloadSchemaType.KEYWORD),
        )
        for field, kind in fields:
            existing = info.payload_schema.get(field)
            if existing is not None and existing.data_type != kind:
                raise UnavailableError(f"Payload index không tương thích: {field}.")
        for field, kind in fields:
            if field not in info.payload_schema:
                await client.create_payload_index(name, field, kind, wait=True)
    return info
