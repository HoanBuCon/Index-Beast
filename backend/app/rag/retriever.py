"""Online hybrid retrieval; missing/unavailable corpus never falls back to general LLM.

Phụ trách: TV3 · [S2] Module retrieval hybrid
"""

from copy import deepcopy
from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from core.errors import UnavailableError
from core.types import Encoder, Hit
from core.vector.store import QdrantStore


def hit_to_document(hit: Hit) -> Document:
    # Namespaced metadata is lossless even if source payload already has id/score fields.
    return Document(
        id=hit.id,
        page_content=hit.payload["text"],
        metadata={
            "point_id": hit.id,
            "retrieval_score": hit.score,
            "payload": deepcopy(hit.payload),
        },
    )


def document_to_hit(document: Document) -> Hit:
    metadata = document.metadata
    payload = deepcopy(metadata["payload"])
    if payload.get("text") != document.page_content:
        raise ValueError("Document content differs from original source text")
    return Hit(metadata["point_id"], metadata["retrieval_score"], payload)


class HybridRetriever(BaseRetriever):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    encoder: Any
    store: QdrantStore
    limit: int = 30
    spoilers: bool = True

    def __init__(self, encoder: Encoder, store: QdrantStore, limit: int = 30, **kwargs):
        super().__init__(encoder=encoder, store=store, limit=limit, **kwargs)

    def _get_relevant_documents(self, query: str, *, run_manager) -> list[Document]:
        raise RuntimeError("Use ainvoke for the async Qdrant retriever")

    async def _aget_relevant_documents(self, query: str, *, run_manager) -> list[Document]:
        return [hit_to_document(h) for h in await self._search(query)]

    async def retrieve(self, query: str, *, spoilers: bool = True) -> list[Hit]:
        # Backward-compatible domain API; delegates to the same LangChain retriever.
        from langsmith import tracing_context

        with tracing_context(enabled=False):
            docs = await self.model_copy(update={"spoilers": spoilers}).ainvoke(query)
        return [document_to_hit(d) for d in docs]

    async def _search(self, query: str) -> list[Hit]:
        try:
            await self.store.ready()  # Check before any model load/download.
            vectors = await self.encoder.encode([query], query=True)
            return await self.store.search(vectors[0], limit=self.limit, spoilers=self.spoilers)
        except UnavailableError:
            raise
        except Exception:
            raise UnavailableError("Không thể truy vấn kho tri thức RAG.") from None
