"""Schema Qdrant của ký ức chỉ kiểm một lần mỗi lifecycle trên đường recall; lỗi thì kiểm lại ở lần sau."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.rag.semantic_memory import MemoryScope, MemoryVectors, SemanticMemory
from core.config import Settings
from core.errors import UnavailableError


class FakeClient:
    def __init__(self, *, fail_search_once=False):
        self.get_collection_calls = 0
        self.fail_search_once = fail_search_once

    async def get_collection(self, name):
        self.get_collection_calls += 1
        vectors = {"dense": SimpleNamespace(size=384, distance=__import__("qdrant_client").models.Distance.COSINE)}
        return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=vectors, sparse_vectors=None)))

    async def query_points(self, *args, **kwargs):
        if self.fail_search_once:
            self.fail_search_once = False
            raise RuntimeError("qdrant down")
        return SimpleNamespace(points=[])


class Repo:
    async def memories(self, conversation_id, *, recent=False, ids=None, owner=None):
        return [{"id": str(uuid4()), "text": "x", "revision": 1, "kind": "fact"}] if recent else []


class Encoder:
    async def encode_dense(self, texts, *, query=False):
        return [[0.0] * 384 for _ in texts]


def build(client):
    config = Settings(_env_file=None)
    vectors = MemoryVectors(client, "mem", "corpus")
    return SemanticMemory(Repo(), vectors, Encoder(), config)


SCOPE = MemoryScope(uuid4(), "owner")


async def test_recall_validates_schema_once_even_across_calls():
    client = FakeClient()
    memory = build(client)
    await memory.recall(SCOPE, "q1")
    assert client.get_collection_calls == 1
    await memory.recall(SCOPE, "q2")
    assert client.get_collection_calls == 1


async def test_validation_flag_resets_after_search_failure():
    client = FakeClient(fail_search_once=True)
    memory = build(client)
    with pytest.raises(UnavailableError):
        await memory.recall(SCOPE, "q1")
    await memory.recall(SCOPE, "q2")
    assert client.get_collection_calls == 2
