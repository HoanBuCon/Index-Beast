"""Lazy CPU E5/BM25 encoder, không tải model hoặc inference khi import/khởi tạo.

Phụ trách: TV3 · [S2] Embedding
"""

import asyncio
import threading
from pathlib import Path

from core.types import Encoded

E5_MODEL = "intfloat/multilingual-e5-small"
_REGISTRATION_LOCK = threading.Lock()


def prefixed(text: str, *, query: bool) -> str:
    prefix = "query:" if query else "passage:"
    if text.startswith(prefix):
        if text[len(prefix) :].lstrip().startswith(("query:", "passage:")):
            raise ValueError("Repeated E5 prefix")
        return text
    if text.startswith(("query:", "passage:")):
        raise ValueError("Wrong E5 prefix for operation")
    return f"{prefix} {text}"


class FastEmbedEncoder:
    def __init__(self, cache_dir: str | Path, *, threads: int = 2):
        if type(threads) is not int or not 1 <= threads <= 32:
            raise ValueError("Encoder threads must be between 1 and 32")
        self.cache_dir = str(cache_dir)
        self.threads = threads
        self._dense = None
        self._sparse = None
        self._lock = asyncio.Lock()

    def _ensure_dense(self):
        # Imports/model construction only happen in a worker on the first real operation.
        from fastembed import TextEmbedding
        from fastembed.common.model_description import ModelSource, PoolingType

        if self._dense is None:
            with _REGISTRATION_LOCK:
                if not any(m["model"] == E5_MODEL for m in TextEmbedding.list_supported_models()):
                    TextEmbedding.add_custom_model(
                        model=E5_MODEL,
                        pooling=PoolingType.MEAN,
                        normalization=True,
                        sources=ModelSource(hf=E5_MODEL),
                        dim=384,
                        model_file="onnx/model.onnx",
                    )
            self._dense = TextEmbedding(model_name=E5_MODEL, cache_dir=self.cache_dir, threads=self.threads)

    def _dense_arrays(self, prepared):
        self._ensure_dense()
        # FastEmbed otherwise truncates silently. Count with the exact loaded tokenizer first.
        tokenizer = self._dense.model.tokenizer
        tokenizer.no_truncation()
        if any(len(tokenizer.encode(t).ids) > 512 for t in prepared):
            raise ValueError("E5 input exceeds 512 tokens; re-chunk/rewrite instead of truncating")
        dense = list(self._dense.embed(prepared))
        return [d.tolist() for d in dense]

    def _encode_dense(self, texts, query):
        return self._dense_arrays([prefixed(t, query=query) for t in texts])

    def _encode(self, texts: list[str], query: bool) -> list[Encoded]:
        from fastembed import SparseTextEmbedding

        prepared = [prefixed(t, query=query) for t in texts]
        self._ensure_dense()
        if self._sparse is None:
            self._sparse = SparseTextEmbedding(model_name="Qdrant/bm25", cache_dir=self.cache_dir, threads=self.threads)
        dense = self._dense_arrays(prepared)
        sparse_method = self._sparse.query_embed if query else self._sparse.embed
        sparse = list(sparse_method(prepared))
        return [Encoded(d, s.indices.tolist(), s.values.tolist()) for d, s in zip(dense, sparse, strict=True)]

    async def encode(self, texts: list[str], *, query: bool = False) -> list[Encoded]:
        return await self._worker(self._encode, texts, query)

    async def encode_dense(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        return await self._worker(self._encode_dense, texts, query)

    async def _worker(self, function, *args):
        async with self._lock:
            task = asyncio.create_task(asyncio.to_thread(function, *args))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                # The worker cannot be killed: keep the model lock until it actually stops.
                try:
                    await task
                finally:
                    raise
