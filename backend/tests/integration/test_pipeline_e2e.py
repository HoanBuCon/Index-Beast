"""Pipeline chat đầu-cuối: Qdrant và PostgreSQL thật, LLM và encoder giả (không gọi API ngoài).

Một collection tạm trong Qdrant và một DB tạm trong PostgreSQL; cả hai bị xóa sau test.
Encoder giả chỉ phục vụ xếp hạng tổng hợp, không nói gì về chất lượng ngữ nghĩa thật.

Chạy: make up && pytest -m integration

Phụ trách: TV1 · [S4] Test tích hợp pipeline
"""

import hashlib
import re
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.schemas.chat import ChatRequest
from app.rag.pipeline import ChatPipeline
from app.rag.retriever import HybridRetriever
from app.services.chat import LiveChatService
from app.services.memory_repository import MemoryRepository
from core.config import Settings
from core.corpus import CorpusPolicy
from core.types import ChunkRecord, Encoded
from core.vector.schema import ensure_collection
from core.vector.store import QdrantStore
from tests.integration.test_db_schema import db_url  # noqa: F401  (fixture dùng chung)
from tests.unit.test_agent_durable import AgentLLM, plan

pytestmark = pytest.mark.integration

DOCS = {
    "Ranni": "Ranni the Witch is an Empyrean and a lunar princess who rests in Nokron's Ranni's Rise.",
    "Malenia": "Malenia, Blade of Miquella, is a demigod bound to the Haligtree and wields the Hand of Malenia.",
    "Radahn": "Starscourge Radahn is a demigod general of the Starscourge, fought at Redmane Castle.",
}
DIM = 384


class HashEncoder:
    """Băm từ vào 384 chiều: cùng từ thì cùng hướng, đủ để thứ hạng dense và BM25 có nghĩa."""

    @staticmethod
    def _words(text: str) -> list[str]:
        return re.findall(r"[a-z']{3,}", text.lower())

    async def encode(self, texts: list[str], *, query: bool = False) -> list[Encoded]:
        out = []
        for text in texts:
            dense = [0.0] * DIM
            sparse: dict[int, float] = {}
            for word in self._words(text):
                slot = int(hashlib.sha1(word.encode()).hexdigest(), 16) % 10_000
                dense[slot % DIM] += 1.0
                sparse[slot] = sparse.get(slot, 0.0) + 1.0
            out.append(Encoded(dense, list(sparse), list(sparse.values())))
        return out


def chunk(name: str, text: str, index: int) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=f"c{index}",
        source="wikigg",
        source_id=str(index),
        title=name,
        section="Lore",
        text=text,
        embedding_text=f"passage: {name}\n{text}",
        url=f"https://example.test/{name.lower()}",
        game_scope="elden_ring",
        source_type="wiki_prose",
        lang="en",
        token_count=40,
        review_status="approved",
        spoiler_level=1,
    )


@pytest.fixture
async def stack(db_url: str):  # noqa: F811
    settings = Settings(
        _env_file=None,
        environment="test",
        chat_mode="rag",
        chat_agent_enabled=True,
        chat_tool_agent_enabled=False,
        chat_persistence="postgres",
        gameplay_knowledge_enabled=False,
        rag_collection=f"ib_e2e_{uuid4().hex[:8]}",
    )
    client = AsyncQdrantClient(url=settings.qdrant_url)
    engine = create_async_engine(db_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await ensure_collection(client, settings.rag_collection, create=True)
        encoder = HashEncoder()
        store = QdrantStore(client, settings.rag_collection, CorpusPolicy.from_settings(settings))
        records = [chunk(name, text, i) for i, (name, text) in enumerate(DOCS.items())]
        await store.upsert(records, await encoder.encode([r.embedding_text for r in records]))
        retriever = HybridRetriever(encoder, store, settings.rag_prefetch)
        repository = MemoryRepository(sessionmaker)

        def build(llm):
            pipeline = ChatPipeline(settings, llm, retriever)
            return LiveChatService(pipeline, repository=repository, gameplay_enabled=True)

        yield build, repository
    finally:
        await client.delete_collection(settings.rag_collection)
        await client.close()
        await engine.dispose()


def ranni_llm() -> AgentLLM:
    llm = AgentLLM([plan(search_query="Ranni the Witch lunar princess")])
    llm.data = {
        "answer": "Ranni the Witch is an Empyrean [1].",
        "evidence": [{"index": 1, "quote": "Ranni the Witch is an Empyrean"}],
        "insufficient": False,
    }
    return llm


def ask(question: str, **kwargs) -> ChatRequest:
    return ChatRequest(message=question, channel="web", **kwargs)


async def test_answer_comes_from_the_matching_source_and_is_stored(stack):
    build, repository = stack
    live = build(ranni_llm())

    reply = await live.answer(ask("Ranni là ai?"))

    assert reply.grounded and reply.sources, reply
    assert reply.sources[0].title == "Ranni"  # Qdrant thật xếp đúng nguồn lên đầu
    assert {s.title for s in reply.sources} <= set(DOCS)
    assert "Ranni" in reply.answer

    stored = await repository.load(
        reply.conversation_id, channel="web", external_ref=None, token=reply.conversation_token
    )
    roles = [m.role for m in stored.conversation.messages]
    assert roles == ["user", "assistant"]  # PostgreSQL thật giữ cả cặp hỏi-đáp


async def test_follow_up_reuses_the_stored_conversation(stack):
    build, repository = stack
    live = build(ranni_llm())
    first = await live.answer(ask("Who is Ranni the Witch?"))
    second = await live.answer(
        ask(
            "Who is Ranni the Witch?",
            conversation_id=first.conversation_id,
            conversation_token=first.conversation_token,
        )
    )

    assert second.conversation_id == first.conversation_id
    stored = await repository.load(
        first.conversation_id, channel="web", external_ref=None, token=first.conversation_token
    )
    assert [m.role for m in stored.conversation.messages] == ["user", "assistant", "user", "assistant"]


async def test_a_stranger_cannot_continue_someone_elses_conversation(stack):
    from core.errors import UnauthorizedError

    build, _ = stack
    live = build(ranni_llm())
    first = await live.answer(ask("Ranni là ai?"))

    with pytest.raises(UnauthorizedError):
        await live.answer(ask("Tiếp tục", conversation_id=first.conversation_id, conversation_token="x" * 40))
