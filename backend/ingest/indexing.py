"""Explicit offline-artifact adapter/index CLI; importing never embeds or connects.

Phụ trách: TV3 · [S2] Embedding & indexing
"""

import asyncio
import json
from pathlib import Path

from pydantic import ValidationError

from core.types import ChunkRecord, Encoder
from core.vector.schema import ensure_collection
from core.vector.store import QdrantStore


def rejection_reason(chunk: ChunkRecord) -> str | None:
    data = chunk.model_dump()
    if (
        chunk.game_scope != "base"
        or data.get("review_status") != "approved"
        or data.get("scope_status") in {"review", "excluded"}
    ):
        return "scope_or_review_not_approved"
    if chunk.source_type not in {"in_game_text", "wiki_prose", "speculation"}:
        return "unknown_source_type"
    if chunk.lang not in {"en", "vi", "ja"}:
        return "unknown_language"
    return None


def load_chunks(path: Path) -> tuple[list[ChunkRecord], list[dict]]:
    """Require explicit review approval; TV2 heuristic base alone is NOT approval."""
    accepted, rejected = [], []
    ids = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            chunk = ChunkRecord.model_validate(data)
            reason = rejection_reason(chunk)
            if str(chunk.point_uuid) in ids:
                reason = "duplicate_artifact_id"
            if reason:
                rejected.append({"line": line_number, "reason": reason})
            else:
                ids.add(str(chunk.point_uuid))
                accepted.append(chunk)
        except (ValidationError, ValueError, TypeError):
            rejected.append({"line": line_number, "reason": "invalid_chunk_contract"})
    return accepted, rejected


async def index_chunks(chunks: list[ChunkRecord], encoder: Encoder, store: QdrantStore, batch_size: int) -> int:
    # All input is validated before any mutation. No partial silent acceptance.
    if not chunks or batch_size < 1:
        raise ValueError("No approved chunks or invalid batch size")
    if any(rejection_reason(chunk) for chunk in chunks):
        raise ValueError("Input contains unapproved or unknown-metadata chunks")
    if len({c.point_uuid for c in chunks}) != len(chunks):
        raise ValueError("Input contains duplicate artifact IDs")
    await ensure_collection(store.client, store.collection, create=True)
    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset : offset + batch_size]
        vectors = await encoder.encode([c.embedding_text for c in batch])
        await store.upsert(batch, vectors)
    return len(chunks)


def run_cli(path: Path, *, dry_run: bool) -> int:
    chunks, rejected = load_chunks(path)
    print(json.dumps({"accepted": len(chunks), "rejected": rejected, "dry_run": dry_run}))
    if rejected or not chunks:
        return 2
    if dry_run:
        return 0

    async def run():
        from qdrant_client import AsyncQdrantClient

        from core.config import get_settings
        from core.encoders.onnx import FastEmbedEncoder

        settings = get_settings()
        client = AsyncQdrantClient(
            url=settings.qdrant_url,
            timeout=max(1, round(settings.client_timeout_seconds)),
            check_compatibility=False,
        )
        try:
            count = await index_chunks(
                chunks,
                FastEmbedEncoder(settings.rag_models_dir),
                QdrantStore(client, settings.rag_collection),
                settings.rag_batch_size,
            )
            print(json.dumps({"indexed": count, "collection": settings.rag_collection}))
        finally:
            await client.close()

    asyncio.run(run())
    return 0
