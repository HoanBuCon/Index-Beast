"""Offline checks that reranking reaches real retrieval, including the Agent tool path."""

import asyncio
from types import SimpleNamespace

import pytest

from app.context import build_context
from app.rag.pipeline import ChatPipeline
from app.rag.reranker import JinaReranker
from app.rag.retriever import HybridRetriever, document_to_hit
from app.services.factory import build_chat_service
from core.config import Settings
from core.corpus import CorpusPolicy
from core.errors import UnavailableError
from core.vector.store import QdrantStore
from tests.unit.test_agent_durable import req, settings
from tests.unit.test_live_chat import FakeLLM, hit
from tests.unit.test_tool_agent import ToolsLLM, step


class Encoder:
    async def encode(self, texts, *, query):
        return [object() for _ in texts]


class Store(QdrantStore):
    def __init__(self):
        self.policy = CorpusPolicy("pilot", ("en",))

    async def ready(self):
        pass

    async def search(self, vector, *, limit, spoilers):
        return [hit(1), hit(2)]


class ReverseReranker:
    def __init__(self):
        self.queries = []

    async def rank(self, query, hits):
        self.queries.append(query)
        return list(reversed(hits))


async def test_reranker_is_used_by_retrieval_and_copied_tool_settings():
    reranker = ReverseReranker()
    retriever = HybridRetriever(Encoder(), Store(), reranker=reranker)
    documents = await retriever.model_copy(update={"spoilers": False}).ainvoke("Ranni parents")
    result = [document_to_hit(d) for d in documents]
    assert [h.id for h in result] == ["2", "1"]
    assert reranker.queries == ["Ranni parents"]
    assert result[0].score == 0.1 and result[0].payload == hit(2).payload


async def test_agent_tool_observes_reranked_candidates():
    reranker = ReverseReranker()
    llm = ToolsLLM([step("local_search", "Ranni identity"), step("finish", evidence_ids=["2"])])
    pipe = ChatPipeline(
        settings(chat_tool_agent_enabled=True), llm, HybridRetriever(Encoder(), Store(), reranker=reranker)
    )
    prepared = await pipe.prepare(req(options={"web_search": "off"}), [])
    assert [c["id"] for c in llm.observations[1]["candidates"]] == ["2", "1"]
    assert [h.id for h in prepared.hits] == ["2"]
    assert reranker.queries == ["Ranni identity"]


async def test_legacy_graph_does_not_call_provider_twice():
    reranker = ReverseReranker()
    pipe = ChatPipeline(
        settings(chat_agent_enabled=False, rag_rewrite_enabled=False),
        FakeLLM(),
        HybridRetriever(Encoder(), Store(), reranker=reranker),
    )
    prepared = await pipe.prepare(req(options={"web_search": "off"}), [])
    assert len(reranker.queries) == 1
    assert [h.id for h in prepared.hits] == ["2", "1"]


@pytest.mark.parametrize(
    "mode,key,enabled",
    [
        ("mock", "dummy", True),
        ("llm_only", "dummy", True),
        ("rag", "", True),
        ("rag", "dummy", False),
        ("rag", "dummy", True),
    ],
)
async def test_context_creates_and_closes_reranker_only_when_available(mode, key, enabled):
    config = Settings(
        _env_file=None,
        chat_mode=mode,
        deepseek_api_key=None,
        tavily_api_key=None,
        rag_reranker_enabled=enabled,
        jina_api_key=key,
    )
    ctx = build_context(config)
    active = mode == "rag" and enabled and bool(key)
    try:
        assert isinstance(ctx.reranker, JinaReranker) is active
        provider_client = ctx.reranker.client if active else None
        if active:
            service = build_chat_service(ctx)
            assert service.pipeline.retriever.reranker is ctx.reranker
    finally:
        await ctx.aclose()
    if provider_client is not None:
        assert provider_client.is_closed


def test_factory_preserves_injected_reranker():
    reranker = ReverseReranker()
    ctx = SimpleNamespace(
        settings=settings(chat_persistence="memory"), qdrant=object(), llm=FakeLLM(), reranker=reranker
    )
    service = build_chat_service(ctx)
    assert service.pipeline.retriever.reranker is reranker


async def test_search_has_its_own_budget_before_reranking():
    class SlowStore(Store):
        async def search(self, *args, **kwargs):
            await asyncio.sleep(0.1)
            return await super().search(*args, **kwargs)

    reranker = ReverseReranker()
    retriever = HybridRetriever(Encoder(), SlowStore(), reranker=reranker, search_timeout_seconds=0.01)
    with pytest.raises(UnavailableError):
        await retriever.ainvoke("Ranni")
    assert not reranker.queries


async def test_legacy_fuses_all_queries_before_single_rerank(monkeypatch):
    from app.rag import pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "plan_queries", lambda *_: [("first", "q1"), ("second", "q2")])

    class RecordingReranker(ReverseReranker):
        async def rank(self, query, hits):
            self.inputs = [(h.id, h.score) for h in hits]
            return await super().rank(query, hits)

    reranker = RecordingReranker()
    pipe = ChatPipeline(
        settings(chat_agent_enabled=False, rag_rewrite_enabled=False),
        FakeLLM(),
        HybridRetriever(Encoder(), Store(), reranker=reranker),
    )
    prepared = await pipe.prepare(req(options={"web_search": "off"}), [])
    assert len(reranker.queries) == 1
    assert reranker.inputs == [("1", 2 / 61), ("2", 2 / 62)]
    assert [h.id for h in prepared.hits] == ["2", "1"]


async def test_retriever_preserves_hits_when_rerank_budget_expires():
    import time

    class SlowReranker:
        async def rank(self, query, hits):
            await asyncio.sleep(1)
            return list(reversed(hits))

    retriever = HybridRetriever(Encoder(), Store(), reranker=SlowReranker(), rerank_deadline=time.perf_counter() + 0.03)
    async with asyncio.timeout(0.2):
        docs = await retriever.ainvoke("Ranni")
    assert [document_to_hit(d).id for d in docs] == ["1", "2"]


async def test_retriever_skips_rerank_when_budget_is_exhausted():
    import time

    reranker = ReverseReranker()
    retriever = HybridRetriever(Encoder(), Store(), reranker=reranker, rerank_deadline=time.perf_counter() - 1)
    docs = await retriever.ainvoke("Ranni")
    assert [document_to_hit(d).id for d in docs] == ["1", "2"]
    assert reranker.queries == []


@pytest.mark.parametrize("stream", [False, True])
async def test_chat_passes_start_before_loading_state_to_pipeline(stream, monkeypatch):
    import json
    import time
    from contextlib import aclosing

    from app.services.chat import LiveChatService

    llm = FakeLLM(tokens=[json.dumps(FakeLLM().data)])
    pipe = ChatPipeline(
        settings(chat_agent_enabled=False, rag_rewrite_enabled=False), llm, HybridRetriever(Encoder(), Store())
    )
    service = LiveChatService(pipe)
    original_load = service._load_state
    original_prepare = pipe.prepare
    observed = {}

    async def load(*args, **kwargs):
        await asyncio.sleep(0.03)
        return await original_load(*args, **kwargs)

    async def prepare(*args, **kwargs):
        observed["elapsed"] = time.perf_counter() - kwargs["started"]
        return await original_prepare(*args, **kwargs)

    monkeypatch.setattr(service, "_load_state", load)
    monkeypatch.setattr(pipe, "prepare", prepare)
    if stream:
        async with aclosing(await service.open_stream(req(options={"web_search": "off"}))) as events:
            async for _ in events:
                pass
    else:
        await service.answer(req(options={"web_search": "off"}))
    assert observed["elapsed"] >= 0.025


async def test_agent_uses_remaining_turn_budget_and_keeps_retrieved_hits():
    import time

    class SlowReranker:
        async def rank(self, query, hits):
            await asyncio.sleep(1)
            return list(reversed(hits))

    llm = ToolsLLM([step("local_search", "Ranni identity"), step("finish", evidence_ids=["1"])])
    retriever = HybridRetriever(Encoder(), Store(), reranker=SlowReranker(), reranker_timeout_seconds=1)
    pipe = ChatPipeline(settings(chat_tool_agent_enabled=True, chat_timeout_seconds=1), llm, retriever)
    started = time.perf_counter() - 0.45
    async with asyncio.timeout(0.3):
        prepared = await pipe.prepare(req(options={"web_search": "off"}), [], started=started)
    assert [h.id for h in prepared.hits] == ["1"]
    assert [c["id"] for c in llm.observations[1]["candidates"]] == ["1", "2"]
    assert retriever.rerank_deadline is None


async def test_rerank_deadline_does_not_swallow_external_cancellation():
    import time

    entered = asyncio.Event()

    class BlockingReranker:
        async def rank(self, query, hits):
            entered.set()
            await asyncio.Event().wait()

    retriever = HybridRetriever(
        Encoder(), Store(), reranker=BlockingReranker(), rerank_deadline=time.perf_counter() + 5
    )
    task = asyncio.create_task(retriever.ainvoke("Ranni"))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
