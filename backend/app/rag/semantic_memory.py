"""Recall dense theo phạm vi; PostgreSQL kiểm từng hit vector và giữ bản plaintext."""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from qdrant_client import models as qm

from core.encoders.onnx import E5_MODEL
from core.errors import UnavailableError

EMBEDDING_VERSION = "e5-small-384-prefix-v1"


@dataclass(frozen=True)
class MemoryScope:
    conversation_id: UUID
    owner: str


class MemoryVectors:
    def __init__(self, client, collection, corpus_collection):
        if collection == corpus_collection:
            raise ValueError("Memory and corpus collections must differ")
        self.client, self.collection = client, collection
        self._validated = False  # Kiểm schema một lần mỗi lifecycle; lỗi truy cập thì kiểm lại ở lần sau.

    async def validate(self):
        if self._validated:
            return
        config = (await self.client.get_collection(self.collection)).config.params
        vectors = config.vectors
        if not isinstance(vectors, dict) or set(vectors) != {"dense"}:
            raise ValueError("Memory requires a separate named dense vector")
        if vectors["dense"].size != 384 or vectors["dense"].distance != qm.Distance.COSINE or config.sparse_vectors:
            raise ValueError("Memory schema must be 384 cosine, without sparse vectors")
        self._validated = True

    async def setup(self):
        if not await self.client.collection_exists(self.collection):
            await self.client.create_collection(
                self.collection, vectors_config={"dense": qm.VectorParams(size=384, distance=qm.Distance.COSINE)}
            )
        self._validated = False
        await self.validate()
        for key in ("conversation_id", "owner", "status", "embedding_version", "embedding_model"):
            await self.client.create_payload_index(self.collection, key, qm.PayloadSchemaType.KEYWORD, wait=True)

    async def search(self, scope, vector, limit):
        await self.validate()
        try:
            result = await self._query(scope, vector, limit)
        except Exception:
            self._validated = False
            raise
        return result.points

    async def _query(self, scope, vector, limit):
        return await self.client.query_points(
            self.collection,
            query=vector,
            using="dense",
            limit=limit,
            query_filter=qm.Filter(
                must=[
                    qm.FieldCondition(key=key, match=qm.MatchValue(value=value))
                    for key, value in {
                        "conversation_id": str(scope.conversation_id),
                        "owner": scope.owner,
                        "status": "active",
                        "embedding_version": EMBEDDING_VERSION,
                        "embedding_model": E5_MODEL,
                    }.items()
                ]
            ),
            with_payload=True,
        )

    async def upsert(self, scope, row, vector):
        await self.client.upsert(
            self.collection,
            points=[
                qm.PointStruct(
                    id=str(row.id),
                    vector={"dense": vector},
                    payload={
                        "conversation_id": str(scope.conversation_id),
                        "owner": scope.owner,
                        "status": row.status,
                        "revision": row.revision,
                        "kind": row.kind,
                        "embedding_model": E5_MODEL,
                        "embedding_version": EMBEDDING_VERSION,
                    },
                )
            ],
            wait=True,
        )

    async def available(self) -> bool:
        """Collection ký ức đã tồn tại chưa; hỏi một lần cho cả lượt xóa rồi gọi `delete_conversations` nhiều lần."""
        return await self.client.collection_exists(self.collection)

    async def delete_conversations(self, conversation_ids) -> None:
        """Xóa mọi điểm ký ức của các hội thoại này theo payload (cả điểm mồ côi). Idempotent; cần collection có sẵn."""
        ids = [str(i) for i in conversation_ids]
        if ids:
            scope = qm.Filter(must=[qm.FieldCondition(key="conversation_id", match=qm.MatchAny(any=ids))])
            await self.client.delete(self.collection, points_selector=qm.FilterSelector(filter=scope), wait=True)

    async def delete(self, memory_id):
        await self.client.delete(self.collection, points_selector=qm.PointIdsList(points=[str(memory_id)]), wait=True)


class SemanticMemory:
    def __init__(self, repository, vectors, encoder, settings):
        self.repository, self.vectors, self.encoder, self.settings = repository, vectors, encoder, settings

    async def recall(self, scope: MemoryScope, question: str):
        try:
            async with asyncio.timeout(self.settings.chat_memory_timeout_seconds):
                # Collection thiếu/không khớp thì lỗi trước khi khởi tạo model.
                await self.vectors.validate()
                recent = await self.repository.memories(scope.conversation_id, recent=True, owner=scope.owner)
                if not recent:
                    return [], {"method": "semantic", "status": "empty", "selected": 0}
                vector = (await self.encoder.encode_dense([question], query=True))[0]
                hits = await self.vectors.search(scope, vector, self.settings.chat_memory_candidates)
                valid_ids = []
                for hit in hits:
                    try:
                        valid_ids.append(str(UUID(str(hit.id))))
                    except ValueError:
                        continue
                canonical = {
                    row["id"]: row
                    for row in await self.repository.memories(scope.conversation_id, ids=valid_ids, owner=scope.owner)
                }
                rows = []
                for hit in hits:
                    row = canonical.get(str(hit.id))
                    if row and row["revision"] == (hit.payload or {}).get("revision"):
                        rows.append({**row, "cosine": hit.score})
                # Giữ điểm riêng; mốc gần đây được gắn nhãn, không gán độ tương đồng giả.
                seen = {row["id"] for row in rows}
                rows.extend({**row, "recent": True} for row in recent if row["id"] not in seen)
                used, bounded = 0, []
                for row in rows:
                    if used + len(row["text"]) <= self.settings.chat_history_chars:
                        bounded.append(row)
                        used += len(row["text"])
                return bounded, {
                    "method": "semantic",
                    "status": "ok",
                    "candidates": len(bounded),
                    "candidate_ids": [row["id"] for row in bounded],
                    "stale_or_foreign": len(hits) - len(canonical),
                }
        except (TimeoutError, ValueError):
            raise UnavailableError("Không truy hồi được ký ức hội thoại trong giới hạn xử lý.") from None
        except UnavailableError:
            raise
        except Exception:
            raise UnavailableError("Kho ký ức hội thoại chưa sẵn sàng.") from None

    async def sync(self, scope: MemoryScope):
        counts = {"indexed": 0, "deleted": 0, "skipped": 0, "failed": 0}
        try:
            await self.vectors.validate()
            for row in await self.repository.pending(scope.conversation_id, owner=scope.owner):
                try:
                    if row.status != "active":
                        await self.vectors.delete(row.id)
                        counts["deleted"] += 1
                    else:
                        vector = (await self.encoder.encode_dense([row.embedding_text]))[0]
                        await self.vectors.upsert(scope, row, vector)
                        counts["indexed"] += 1
                    await self.repository.mark_indexed(row.id, row.revision)
                except ValueError:
                    counts["skipped"] += 1
                    await self.repository.mark_indexed(row.id, row.revision, error="invalid_embedding_input")
                except Exception:
                    counts["failed"] += 1
            if counts["indexed"] and not await self.repository.conversation_exists(scope.conversation_id):
                # Hội thoại bị xóa (/clear) trong lúc đang lập chỉ mục: dọn điểm vừa ghi để không còn điểm mồ côi
                await self.vectors.delete_conversations([scope.conversation_id])
        except Exception:
            counts["failed"] += 1
        return counts
