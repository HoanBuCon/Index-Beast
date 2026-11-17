"""Shared offline fakes for RAG tests. Synthetic rankings are NOT retrieval quality evidence."""

import asyncio
import json

from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableLambda
from pydantic import Field

from app.adapters.llm import LLMResponse
from app.rag.retriever import hit_to_document
from core.errors import UnavailableError
from core.types import Hit


def hit(key="a", **payload):
    return Hit(
        key,
        0.1,
        {
            "text": f"Evidence for {key}",
            "title": "Ranni the Witch",
            "url": "https://eldenring.wiki.gg/wiki/Ranni_the_Witch",
            "source": "wikigg",
            "source_id": "ranni",
            "revision_id": "v1",
            "section": "Lore",
            "game_scope": "base",
            "release_scope": "unknown",
            "review_status": "approved",
            "source_type": "wiki_prose",
            "lang": "en",
            **payload,
        },
    )


class ScriptedLLM:
    def __init__(self, output=None, delay=0):
        self.output = output if output is not None else {}
        self.delay, self.inputs, self.bound, self.cancelled = delay, [], [], False

    def bind_model(self, **kwargs):
        self.bound.append(kwargs)
        return RunnableLambda(lambda _: None)

    async def invoke_chain(self, _chain, inputs):
        self.inputs.append(inputs)
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if isinstance(self.output, Exception):
            raise self.output
        text = self.output if isinstance(self.output, str) else json.dumps(self.output)
        return LLMResponse(text, "fake", 10, 5, "stop")


class RankedRetriever(BaseRetriever):
    rankings: dict[str, list[Hit]] = Field(default_factory=dict)
    calls: list[str] = Field(default_factory=list)
    failures: set[str] = Field(default_factory=set)
    delays: dict[str, float] = Field(default_factory=dict)
    spoilers: bool = True

    def _get_relevant_documents(self, query, *, run_manager):
        raise RuntimeError("Async only")

    async def _aget_relevant_documents(self, query, *, run_manager):
        self.calls.append(query)
        await asyncio.sleep(self.delays.get(query, 0))
        if query in self.failures:
            raise UnavailableError()
        return [hit_to_document(row) for row in self.rankings.get(query, [])]
