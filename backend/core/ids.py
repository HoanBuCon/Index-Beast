"""Sinh id ổn định: document_id từ (source, source_id), chunk_id = uuid5(document_id, ordinal) để upsert idempotent.

Cùng đầu vào luôn ra cùng id, nên crawl/chunk lại hay dựng lại DB không làm đổi id chunk trong Qdrant.
Đổi NAMESPACE là thay toàn bộ id: chỉ làm khi index lại từ đầu.

Phụ trách: TV2 · [S2] Chunking + metadata (TV1 viết bản đầu để repository dùng chung)
"""

import uuid

NAMESPACE = uuid.UUID("5b1f0c1e-8a52-4f3c-9d0e-1e7a2b6c4d10")  # cố định cho dự án, không sinh lại


def document_id(source: str, source_id: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{source}:{source_id}")


def chunk_id(doc_id: uuid.UUID, ordinal: int) -> uuid.UUID:
    return uuid.uuid5(doc_id, str(ordinal))
