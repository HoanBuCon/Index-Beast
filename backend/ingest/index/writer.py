"""Ghi Qdrant theo tài liệu cho cập nhật tăng dần: upsert chunk mới rồi xoá point thừa của chính tài liệu đó.

Thứ tự upsert -> xoá thừa giữ tài liệu luôn có dữ liệu hợp lệ nếu tiến trình dừng giữa chừng; chạy lại cho cùng kết quả.
Point id lấy từ ChunkRecord.point_uuid (ổn định theo document + ordinal), nên trang đổi nội dung ghi đè đúng point cũ.

Phụ trách: TV2 · [S5] Cập nhật dữ liệu tăng dần
"""

from qdrant_client import models

from core.types import ChunkRecord
from core.vector.schema import ensure_collection
from core.vector.store import QdrantStore


class QdrantIndex:
    def __init__(self, client, collection, encoder, policy, batch_size=32):
        if batch_size < 1:
            raise ValueError("Invalid batch size")
        self.client, self.collection, self.encoder, self.batch_size = client, collection, encoder, batch_size
        self.store = QdrantStore(client, collection, policy)
        self.policy = policy

    async def prepare(self):
        await ensure_collection(self.client, self.collection, create=True)

    async def sync(self, docs):
        """docs: {document_uuid: [dòng chunk JSONL]}. Chunk bị chính sách loại (ngôn ngữ, scope) không vào index."""
        admitted, keep = [], {}
        for document, rows in docs.items():
            records = [ChunkRecord.model_validate(row) for row in rows]
            chosen = [c for c in records if self.policy.exclusion_reason(c.payload()) is None]
            admitted.extend(chosen)
            keep[document] = [str(c.point_uuid) for c in chosen]
        for offset in range(0, len(admitted), self.batch_size):
            batch = admitted[offset : offset + self.batch_size]
            await self.store.upsert(batch, await self.encoder.encode([c.embedding_text for c in batch]))
        for document, ids in keep.items():
            await self._delete(document, ids)
        return {"upserted": len(admitted), "excluded": sum(map(len, docs.values())) - len(admitted)}

    async def delete(self, documents):
        for document in documents:
            await self._delete(document, [])

    async def _delete(self, document, keep_ids):
        stale = models.Filter(
            must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document))],
            must_not=[models.HasIdCondition(has_id=keep_ids)] if keep_ids else None,
        )
        await self.client.delete(self.collection, points_selector=models.FilterSelector(filter=stale), wait=True)
