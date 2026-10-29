"""Qdrant hybrid RRF and idempotent batches; source metadata is never invented.

Phụ trách: TV3 · [S2] Module retrieval hybrid
"""

from qdrant_client import models

from core.corpus import CorpusPolicy
from core.errors import UnavailableError
from core.types import ChunkRecord, Encoded, Hit
from core.vector.schema import ensure_collection


class QdrantStore:
    def __init__(self, client, collection: str, policy: CorpusPolicy | None = None):
        self.client = client
        self.collection = collection
        self.policy = policy or CorpusPolicy()

    async def ready(self) -> None:
        info = await ensure_collection(self.client, self.collection)
        if info.points_count == 0:
            raise UnavailableError("Kho tri thức chưa sẵn sàng: collection chưa có dữ liệu.")

    async def upsert(self, chunks: list[ChunkRecord], vectors: list[Encoded]) -> None:
        points = [
            models.PointStruct(
                id=str(chunk.point_uuid),
                payload=self.policy.index_payload(chunk.payload()),
                vector={
                    "dense": v.dense,
                    "bm25": models.SparseVector(
                        indices=v.sparse_indices,
                        values=v.sparse_values,
                    ),
                },
            )
            for chunk, v in zip(chunks, vectors, strict=True)
        ]
        await self.client.upsert(self.collection, points=points, wait=True)

    async def search(self, vector: Encoded, *, limit: int, spoilers: bool = True) -> list[Hit]:
        filters = self.policy.query_filter(spoilers=spoilers)
        result = await self.client.query_points(
            self.collection,
            prefetch=[
                models.Prefetch(query=vector.dense, using="dense", limit=limit, filter=filters),
                models.Prefetch(
                    query=models.SparseVector(indices=vector.sparse_indices, values=vector.sparse_values),
                    using="bm25",
                    limit=limit,
                    filter=filters,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=filters,
            limit=limit,
            with_payload=True,
        )
        return [
            Hit(str(p.id), p.score, p.payload or {})
            for p in result.points
            if self.policy.exclusion_reason(p.payload or {}, spoilers=spoilers) is None
        ]
