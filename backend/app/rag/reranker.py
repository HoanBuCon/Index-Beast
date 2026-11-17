"""Optional reranker interface; disabled implementation preserves RRF order, no invented threshold.

Phụ trách: TV3 · [S3] Reranker service
"""

import asyncio
import logging
import math
from time import perf_counter
from typing import Protocol

import httpx

from core.types import Hit

logger = logging.getLogger(__name__)
_JINA_ENDPOINT = "https://api.jina.ai/v1/rerank"


class Reranker(Protocol):
    async def rank(self, query: str, hits: list[Hit]) -> list[Hit]: ...


class NoReranker:
    async def rank(self, query: str, hits: list[Hit]) -> list[Hit]:
        return hits


class JinaReranker:
    def __init__(
        self,
        api_key: str,
        model: str = "jina-reranker-v2-base-multilingual",
        timeout_seconds: float = 3,
        max_candidates: int = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if timeout_seconds <= 0 or max_candidates < 1:
            raise ValueError("timeout_seconds and max_candidates must be positive")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_candidates = max_candidates
        self.client = client

    async def rank(self, query: str, hits: list[Hit]) -> list[Hit]:
        candidates = hits[: self.max_candidates]
        if len(candidates) < 2:
            return hits

        body = {
            "model": self.model,
            "query": query,
            "documents": [
                "\n".join(str(value) for value in (hit.payload.get("title"), hit.payload.get("text")) if value)
                for hit in candidates
            ],
            "top_n": len(candidates),
            "return_documents": False,
        }
        started = perf_counter()
        event_fields = {
            "provider": "jina",
            "model": self.model,
            "candidate_count": len(candidates),
        }
        logger.info("Jina reranker attempt", extra={"event": "jina_reranker_attempt", **event_fields})
        status = "fallback"
        reason_category = "unknown"
        provider_status_code = None
        ranked_count = 0
        try:
            async with asyncio.timeout(self.timeout_seconds):
                if self.client is None:
                    async with httpx.AsyncClient() as client:
                        response = await self._post(client, body)
                else:
                    response = await self._post(self.client, body)
            response.raise_for_status()
            results = response.json()["results"]
            if not isinstance(results, list) or len(results) != len(candidates):
                raise ValueError("invalid coverage")
            ranked = []
            seen = set()
            for item in results:
                index, score = item["index"], item["relevance_score"]
                if (
                    type(index) is not int
                    or not 0 <= index < len(candidates)
                    or index in seen
                    or isinstance(score, bool)
                    or not isinstance(score, (int, float))
                    or not math.isfinite(score)
                    or not 0 <= score <= 1
                ):
                    raise ValueError("invalid result")
                seen.add(index)
                ranked.append((index, score))
            ranked.sort(key=lambda item: item[1], reverse=True)
            ranked_hits = [candidates[index] for index, _ in ranked] + hits[len(candidates) :]
            status = "ok"
            reason_category = None
            ranked_count = len(ranked)
        except asyncio.CancelledError:
            reason_category = "cancelled"
            raise
        except httpx.HTTPStatusError as exc:
            reason_category = "http_status"
            provider_status_code = exc.response.status_code
        except (httpx.TimeoutException, TimeoutError):
            reason_category = "timeout"
        except httpx.HTTPError:
            reason_category = "network_error"
        except (ValueError, TypeError, KeyError, IndexError, OverflowError):
            reason_category = "invalid_response"
        finally:
            outcome_fields = {
                **event_fields,
                "ranked_count": ranked_count,
                "status": status,
                "reason_category": reason_category,
                "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            }
            if provider_status_code is not None:
                outcome_fields["provider_status_code"] = provider_status_code
            if status == "ok":
                logger.info("Jina reranker outcome", extra={"event": "jina_reranker_outcome", **outcome_fields})
            else:
                logger.warning("Jina reranker outcome", extra={"event": "jina_reranker_outcome", **outcome_fields})
        if status == "ok":
            return ranked_hits
        return hits

    async def _post(self, client: httpx.AsyncClient, body: dict) -> httpx.Response:
        return await client.post(
            _JINA_ENDPOINT,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        )
