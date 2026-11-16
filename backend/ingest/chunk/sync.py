"""Đồng bộ PostgreSQL cho cập nhật tăng dần: upsert document, thay toàn bộ chunk của document trong một transaction,
đánh dấu document bị xoá. Dùng lại chunk_fields của loader toàn bộ nên hai đường nạp ra cùng dòng.

Phụ trách: TV2 · [S5] Cập nhật dữ liệu tăng dần
"""

from datetime import datetime

from sqlalchemy import delete, func, select, update

from core.db.models import Chunk, Document
from core.db.repositories import replace_chunks, upsert_document
from core.ids import document_id
from ingest.chunk.load_full import chunk_fields


class PgDocuments:
    def __init__(self, sessions, source="wikigg"):
        self.sessions, self.source = sessions, source

    async def sync(self, built):
        for item in built:
            doc, chunks = item["doc"], item["chunks"]
            identity = document_id(doc["source"], doc["source_id"])
            active = doc["game_scope"] != "out_of_scope"
            async with self.sessions() as session, session.begin():
                await upsert_document(
                    session,
                    source=doc["source"],
                    source_id=doc["source_id"],
                    title=doc["title"],
                    url=doc["url"],
                    revision_id=doc["revision_id"],
                    raw_hash=doc["raw_content_hash"],
                    fetched_at=datetime.fromisoformat(doc["fetched_at"]),
                    game_scope=doc["game_scope"],
                    status="active" if active else "excluded",
                )
                await replace_chunks(session, identity, chunk_fields(identity, chunks) if active else [])

    async def delete(self, source_ids):
        identities = [document_id(self.source, i) for i in source_ids]
        async with self.sessions() as session, session.begin():
            await session.execute(delete(Chunk).where(Chunk.document_id.in_(identities)))
            await session.execute(update(Document).where(Document.id.in_(identities)).values(status="deleted"))

    async def list_documents(self):
        """Nguồn bootstrap state khi chưa có thư mục chunk: tài liệu active cùng số chunk."""
        count = select(func.count(Chunk.id)).where(Chunk.document_id == Document.id).scalar_subquery()
        query = select(Document.source_id, Document.revision_id, Document.title, Document.fetched_at, count).where(
            Document.source == self.source, Document.status == "active"
        )
        async with self.sessions() as session:
            rows = (await session.execute(query)).all()
        return [
            {"source_id": r[0], "revision_id": r[1], "title": r[2], "fetched_at": r[3].isoformat(), "chunks": r[4]}
            for r in rows
        ]
