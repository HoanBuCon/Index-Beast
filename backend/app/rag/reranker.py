"""Optional reranker interface; disabled implementation preserves RRF order, no invented threshold.

Phụ trách: TV3 · [S3] Reranker service
"""

import asyncio
import logging
import math
import threading
from collections import deque
from time import monotonic, perf_counter
from typing import Protocol

import httpx

from core.types import Hit

logger = logging.getLogger(__name__)
_JINA_ENDPOINT = "https://api.jina.ai/v1/rerank"


class Reranker(Protocol):
    async def rank(self, query: str, hits: list[Hit]) -> list[Hit]: ...


class _SkipRerank(Exception):
    """Skip this rerank and keep RRF order: Jina token budget would wait too long, or the local model is busy."""


def _retry_after(response: httpx.Response) -> float:
    try:
        return min(max(float(response.headers.get("retry-after", 10)), 1.0), 60.0)
    except ValueError:
        return 10.0


class NoReranker:
    async def rank(self, query: str, hits: list[Hit]) -> list[Hit]:
        return hits


class TokenBudget:
    """Sliding 60 s window of the tokens Jina counted, so calls wait instead of hitting the per-minute limit (429).

    A call that would push the window over the limit waits until enough old usage expires; when that wait is longer
    than max_wait_seconds it is refused (the caller keeps RRF order) rather than delaying the answer. A 429 blocks the
    budget for Retry-After seconds (default 10).
    """

    WINDOW = 60.0

    def __init__(self, tokens_per_minute: int, *, clock=monotonic, sleep=asyncio.sleep) -> None:
        if tokens_per_minute < 1:
            raise ValueError("tokens_per_minute must be positive")
        self.limit = tokens_per_minute
        self.clock = clock
        self.sleep = sleep
        self.used: deque[list[float]] = deque()
        self.blocked_until = 0.0
        self.lock = asyncio.Lock()

    def _wait_for(self, tokens: int, now: float) -> float:
        while self.used and self.used[0][0] + self.WINDOW <= now:
            self.used.popleft()
        wait = max(0.0, self.blocked_until - now)
        excess = sum(entry[1] for entry in self.used) + tokens - self.limit
        for at, spent in self.used:
            if excess <= 0:
                break
            excess -= spent
            wait = max(wait, at + self.WINDOW - now)
        return wait

    async def acquire(self, tokens: int, max_wait_seconds: float) -> list[float] | None:
        """Reserve tokens (capped at the limit); returns the reservation to settle, or None when refused."""
        tokens = min(tokens, self.limit)
        async with self.lock:
            wait = self._wait_for(tokens, self.clock())
            if wait > max_wait_seconds:
                return None
            if wait > 0:
                await self.sleep(wait)
            entry = [self.clock(), float(tokens)]
            self.used.append(entry)
            return entry

    @staticmethod
    def settle(entry: list[float], tokens: int) -> None:
        entry[1] = float(tokens)

    def block(self, seconds: float) -> None:
        self.blocked_until = max(self.blocked_until, self.clock() + seconds)


def estimate_tokens(query: str, documents: list[str]) -> int:
    """Jina counts the query once per document; ~3 characters per token is a safe estimate for VI/EN text."""
    return sum(len(query) + len(doc) for doc in documents) // 3 + 1


def _document(hit: Hit, max_chars: int | None = None) -> str:
    text = "\n".join(str(value) for value in (hit.payload.get("title"), hit.payload.get("text")) if value)
    return text[:max_chars] if max_chars else text


class LocalReranker:
    """Cross-encoder chạy trên máy bằng FastEmbed (ONNX, CPU): không key, không hạn mức, dữ liệu không ra ngoài.

    Giữ RAM ổn định (24/11 bản đầu từng ăn ~18 GB vì các lượt quá giờ vẫn chạy ngầm và chồng lên nhau):
    - Chỉ một lượt suy luận tại một thời điểm. Cờ bận chỉ được trả khi worker thật sự chạy xong, kể cả khi lượt đó
      đã quá giờ; lượt mới gặp cờ bận thì giữ thứ tự RRF ngay (reason "busy"), không xếp hàng.
    - Đưa vào model từng lô nhỏ (batch_size) và cắt mỗi đoạn còn max_chars ký tự: bộ nhớ tạm của ONNX tỉ lệ với
      lô × độ dài, nên đỉnh RAM nhỏ và gần như cố định.
    Model nạp lười; app gọi warm() lúc khởi động để câu đầu không phải chờ nạp. Lỗi, quá giờ, bận hay model chưa sẵn
    sàng đều giữ thứ tự RRF như JinaReranker. Log cùng sự kiện reranker_outcome (provider="local") để công cụ
    đo dùng chung.
    """

    def __init__(
        self,
        model: str,
        cache_dir: str,
        *,
        threads: int = 2,
        timeout_seconds: float = 3,
        max_candidates: int = 20,
        max_chars: int = 600,
        batch_size: int = 8,
    ) -> None:
        if timeout_seconds <= 0 or min(threads, max_candidates, max_chars, batch_size) < 1:
            raise ValueError("local reranker limits must be positive")
        self.model = model
        self.cache_dir = cache_dir
        self.threads = threads
        self.timeout_seconds = timeout_seconds
        self.max_candidates = max_candidates
        self.max_chars = max_chars
        self.batch_size = batch_size
        self._encoder = None
        self._load_lock = threading.Lock()
        self._busy = False

    def _ensure(self):
        with self._load_lock:
            if self._encoder is None:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                self._encoder = TextCrossEncoder(self.model, cache_dir=self.cache_dir, threads=self.threads)
        return self._encoder

    async def warm(self) -> None:
        try:
            await asyncio.to_thread(self._ensure)
        except Exception:  # noqa: BLE001 - không nạp được thì rank() giữ thứ tự RRF và log lý do
            logger.warning("Local reranker failed to load", extra={"event": "local_reranker_load_failed"})

    def _score(self, query: str, documents: list[str]) -> list[float]:
        try:
            return [float(s) for s in self._ensure().rerank(query, documents, batch_size=self.batch_size)]
        finally:
            self._busy = False  # chỉ trả cờ khi worker xong thật

    async def rank(self, query: str, hits: list[Hit]) -> list[Hit]:
        candidates = hits[: self.max_candidates]
        if len(candidates) < 2:
            return hits
        started = perf_counter()
        status, reason_category, ranked_count = "fallback", "unknown", 0
        try:
            if self._busy:
                reason_category = "busy"
                raise _SkipRerank
            self._busy = True
            documents = [_document(hit, self.max_chars) for hit in candidates]
            work = asyncio.get_running_loop().run_in_executor(None, self._score, query, documents)
            scores = await asyncio.wait_for(asyncio.shield(work), self.timeout_seconds)
            if len(scores) != len(candidates) or not all(math.isfinite(s) for s in scores):
                raise ValueError("invalid scores")
            order = sorted(range(len(candidates)), key=lambda index: scores[index], reverse=True)
            ranked_hits = [candidates[index] for index in order] + hits[len(candidates) :]
            status, reason_category, ranked_count = "ok", None, len(order)
        except _SkipRerank:
            pass
        except asyncio.CancelledError:
            reason_category = "cancelled"
            raise
        except TimeoutError:
            reason_category = "timeout"
        except Exception:  # noqa: BLE001 - lỗi model/ONNX không được làm hỏng lượt tìm
            reason_category = "model_error"
        finally:
            outcome = {
                "provider": "local",
                "model": self.model,
                "candidate_count": len(candidates),
                "ranked_count": ranked_count,
                "status": status,
                "reason_category": reason_category,
                "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            }
            level = logging.INFO if status == "ok" else logging.WARNING
            logger.log(level, "Reranker outcome", extra={"event": "reranker_outcome", **outcome})
        return ranked_hits if status == "ok" else hits


def local_reranker(settings) -> LocalReranker:
    from core.config import BACKEND_ROOT

    return LocalReranker(
        settings.rag_reranker_local_model,
        str(BACKEND_ROOT / settings.rag_models_dir),
        threads=settings.rag_reranker_local_threads,
        timeout_seconds=settings.rag_reranker_timeout_seconds,
        max_candidates=min(settings.rag_reranker_max_candidates, settings.rag_reranker_local_max_candidates),
        max_chars=settings.rag_reranker_local_max_chars,
        batch_size=settings.rag_reranker_local_batch_size,
    )


class JinaReranker:
    def __init__(
        self,
        api_key: str,
        model: str = "jina-reranker-v2-base-multilingual",
        timeout_seconds: float = 3,
        max_candidates: int = 30,
        client: httpx.AsyncClient | None = None,
        *,
        tokens_per_minute: int | None = None,
        max_wait_seconds: float = 0,
    ) -> None:
        if timeout_seconds <= 0 or max_candidates < 1 or max_wait_seconds < 0:
            raise ValueError("timeout_seconds and max_candidates must be positive")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_candidates = max_candidates
        self.client = client
        self.budget = TokenBudget(tokens_per_minute) if tokens_per_minute else None
        self.max_wait_seconds = max_wait_seconds

    async def rank(self, query: str, hits: list[Hit]) -> list[Hit]:
        candidates = hits[: self.max_candidates]
        if len(candidates) < 2:
            return hits

        body = {
            "model": self.model,
            "query": query,
            "documents": [_document(hit) for hit in candidates],
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
        reservation = None
        waited_ms = 0.0
        try:
            if self.budget is not None:
                reservation = await self.budget.acquire(
                    estimate_tokens(query, body["documents"]), self.max_wait_seconds
                )
                waited_ms = round((perf_counter() - started) * 1000, 2)
                if reservation is None:
                    reason_category = "rate_budget"
                    raise _SkipRerank
            async with asyncio.timeout(self.timeout_seconds):
                if self.client is None:
                    async with httpx.AsyncClient() as client:
                        response = await self._post(client, body)
                else:
                    response = await self._post(self.client, body)
            if reservation is not None and response.status_code == 429:
                self.budget.block(_retry_after(response))
            response.raise_for_status()
            payload = response.json()
            spent = (payload.get("usage") or {}).get("total_tokens")
            if reservation is not None and isinstance(spent, int) and spent > 0:
                self.budget.settle(reservation, spent)
            results = payload["results"]
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
        except _SkipRerank:
            pass
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
            if waited_ms >= 1:
                outcome_fields["rate_wait_ms"] = waited_ms
            if status == "ok":
                logger.info("Reranker outcome", extra={"event": "reranker_outcome", **outcome_fields})
            else:
                logger.warning("Reranker outcome", extra={"event": "reranker_outcome", **outcome_fields})
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
