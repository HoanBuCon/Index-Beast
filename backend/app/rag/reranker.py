"""Optional reranker interface; disabled implementation preserves RRF order, no invented threshold.

Phụ trách: TV3 · [S3] Reranker service
"""

from typing import Protocol

from core.types import Hit


class Reranker(Protocol):
    async def rank(self, query: str, hits: list[Hit]) -> list[Hit]: ...


class NoReranker:
    async def rank(self, query: str, hits: list[Hit]) -> list[Hit]:
        return hits
