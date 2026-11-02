"""Manual retrieval diagnostic. Running this command embeds a query and reads Qdrant; no LLM/index writes."""

import argparse
import asyncio
import json

from qdrant_client import AsyncQdrantClient

from app.rag.retriever import HybridRetriever
from core.config import REPO_ROOT, get_settings
from core.corpus import CorpusPolicy
from core.encoders.onnx import FastEmbedEncoder
from core.errors import UnavailableError
from core.vector.store import QdrantStore


async def check_retrieval(settings, query: str, *, limit: int, spoilers: bool) -> dict:
    policy = CorpusPolicy.from_settings(settings)
    client = AsyncQdrantClient(
        url=settings.qdrant_url, timeout=max(1, round(settings.client_timeout_seconds)), check_compatibility=False
    )
    try:
        retriever = HybridRetriever(
            FastEmbedEncoder(REPO_ROOT / "backend" / settings.rag_models_dir, threads=settings.rag_encoder_threads),
            QdrantStore(client, settings.rag_collection, policy),
            limit=limit,
        )
        hits = await retriever.retrieve(query, spoilers=spoilers)
        return {
            "collection": settings.rag_collection,
            "policy": policy.mode,
            "languages": list(policy.languages),
            "spoilers": spoilers,
            "hits": [
                {
                    "point_id": h.id,
                    "chunk_id": h.payload.get("artifact_chunk_id", h.payload.get("chunk_id")),
                    "score": h.score,
                    "title": h.payload.get("title"),
                    "url": h.payload.get("url"),
                    "game_scope": h.payload.get("game_scope"),
                    "release_scope": h.payload.get("release_scope"),
                    "lang": h.payload.get("lang"),
                    "review_status": h.payload.get("review_status"),
                    "text_excerpt": h.payload.get("text", "")[:300],
                }
                for h in hits
            ],
        }
    finally:
        await client.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--no-spoilers", action="store_true")
    args = parser.parse_args(argv)
    if not args.query.strip() or not 1 <= args.limit <= 200:
        parser.error("Provide a nonempty query and limit between 1 and 200")
    try:
        result = asyncio.run(
            check_retrieval(get_settings(), args.query, limit=args.limit, spoilers=not args.no_spoilers)
        )
    except UnavailableError as exc:
        print(json.dumps({"code": exc.code, "message": exc.message}, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(json.dumps({"code": "retrieval_failed", "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
