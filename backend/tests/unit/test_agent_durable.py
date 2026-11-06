"""Agent/semantic/durability behavior with scripted decisions, temporary SQL and synthetic vectors.

SQLite compiles the production repository SQL for tests, NOT an asyncpg/Postgres integration test.
"""

import json
from contextlib import aclosing
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.adapters.llm import LLMError, LLMResponse
from app.api.schemas.chat import ChatRequest
from app.api.schemas.conversation import ConversationOut, MessageOut
from app.rag.agent import AgentDecision, check_decision
from app.rag.pipeline import ChatPipeline
from app.rag.prompts import prompt
from app.rag.semantic_memory import MemoryScope, MemoryVectors, SemanticMemory
from app.services.chat import LiveChatService
from app.services.memory_repository import MemoryRepository, Snapshot, owner_hash
from core.config import Settings
from core.db.models import Conversation, ConversationMemory, ConversationRuntime, Message
from core.errors import BadRequestError, UnauthorizedError, UnavailableError, UpstreamError
from tests.unit.test_live_chat import FakeLLM, FakeRetriever


@compiles(JSONB, "sqlite")
def sqlite_json(element, compiler, **kwargs):
    return "JSON"


class Transaction:
    def __init__(self, session):
        self.transaction = session.begin()

    async def __aenter__(self):
        self.transaction.__enter__()

    async def __aexit__(self, *args):
        return self.transaction.__exit__(*args)


class AsyncFacade:
    def __init__(self, factory):
        self.session = factory()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.session.close()

    def begin(self):
        return Transaction(self.session)

    def add(self, item):
        self.session.add(item)

    async def execute(self, stmt):
        return self.session.execute(stmt)

    async def scalars(self, stmt):
        return self.session.scalars(stmt)

    async def get(self, model, key):
        return self.session.get(model, key)

    async def flush(self):
        self.session.flush()


@pytest.fixture
def repo(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "memory.sqlite"))
    Conversation.metadata.create_all(
        engine,
        tables=[Conversation.__table__, Message.__table__, ConversationRuntime.__table__, ConversationMemory.__table__],
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    yield MemoryRepository(lambda: AsyncFacade(factory))
    engine.dispose()


def settings(**kwargs):
    return Settings(
        _env_file=None,
        **{
            "chat_mode": "rag",
            "chat_agent_enabled": True,
            "chat_tool_agent_enabled": False,
            "chat_persistence": "postgres",
            "gameplay_knowledge_enabled": False,
            **kwargs,
        },
    )


def req(message="Ranni là ai?", **kwargs):
    return ChatRequest(message=message, channel="web", **kwargs)


def plan(**kwargs):
    return {
        "intent": "lore",
        "turn_type": "new",
        "action": "retrieve",
        "rewrite": True,
        "resolved_question": "Who is Ranni?",
        "search_query": "Who is Ranni?",
        "entities": ["Ranni"],
        "selected_memory_ids": [],
        "constraints": [],
        "missing": [],
        "reply": "",
        "reason": "ready",
        **kwargs,
    }


class AgentLLM(FakeLLM):
    def __init__(self, decisions=None):
        super().__init__()
        self.decisions = decisions or [plan()]
        self.plans = []
        self.assessment_status = "sufficient"

    async def invoke_chain(self, chain, inputs):
        if inputs.get("policy") == prompt("agent"):
            payload = json.loads(inputs["question"])
            self.plans.append(payload)
            output = self.decisions[min(len(self.plans) - 1, len(self.decisions) - 1)]
            if callable(output):
                output = output(payload)
            return LLMResponse(json.dumps(output), "fake", 10, 5, "stop")
        if inputs.get("policy", "").startswith("Evaluate whether"):
            status = self.assessment_status
            return LLMResponse(
                json.dumps(
                    {
                        "status": status,
                        "covered": ["identity"] if status == "sufficient" else [],
                        "missing": [] if status == "sufficient" else ["detail"],
                        "evidence": {"1": ["q0"]} if status == "sufficient" else {},
                    }
                ),
                "fake",
                10,
                5,
                "stop",
            )
        return await super().invoke_chain(chain, inputs)


class Encoder:
    """Synthetic ranking fixture only; no claim about real multilingual semantic recall."""

    def __init__(self):
        self.calls = []

    async def encode_dense(self, texts, *, query=False):
        self.calls.append((list(texts), query))
        return [[1.0 if "Ranni" in t else 0.0, 0.0 if "Ranni" in t else 1.0, *([0.0] * 382)] for t in texts]


@pytest.fixture
async def memory(repo):
    client = AsyncQdrantClient(":memory:")
    config = settings()
    vectors = MemoryVectors(client, config.chat_memory_collection, config.rag_collection)
    await vectors.setup()
    engine = SemanticMemory(repo, vectors, Encoder(), config)
    yield engine
    await client.close()


def service(repo=None, memory=None, llm=None, **config):
    return LiveChatService(
        ChatPipeline(settings(**config), llm or AgentLLM(), FakeRetriever(), memory=memory),
        repository=repo,
        gameplay_enabled=True,
    )


def test_agent_is_default_and_no_closed_weapon_allowlist(monkeypatch):
    monkeypatch.delenv("CHAT_AGENT_ENABLED", raising=False)
    assert Settings(_env_file=None).chat_agent_enabled
    item = AgentDecision.model_validate(
        plan(
            intent="build",
            entities=["Great Stars"],
            search_query="Great Stars build",
            resolved_question="Great Stars build",
        )
    )
    check_decision(item, "Great Stars build", [], {})


async def test_model_can_greet_without_fabricating_a_search_query():
    llm = AgentLLM(
        [
            plan(
                intent="smalltalk",
                action="respond",
                resolved_question="",
                search_query="",
                entities=[],
                rewrite=False,
                reply="Chào bạn! Bạn muốn khám phá gì trong Elden Ring?",
                reason="conversation_control",
            )
        ]
    )
    live = service(llm=llm)
    result = await live.answer(req("chào bạn"))
    assert "Chào bạn" in result.answer and not live.pipeline.retriever.calls and llm.calls == 0


async def test_agent_dual_mode_keeps_original_language_for_standalone_question():
    llm = AgentLLM([plan(search_query="Ranni identity")])
    pipe = ChatPipeline(settings(rag_query_mode="dual"), llm, FakeRetriever())
    await pipe.prepare(req("Ranni là ai?"), [])
    # Existing dual retrieval prioritizes English, then includes the original-language query.
    assert pipe.retriever.calls == [("Ranni identity", True), ("Ranni là ai?", True)]


async def test_no_rewrite_uses_original_request_despite_unused_query_punctuation():
    # Captured live decision: its unused English search query drops the city's comma.
    question = "Is Maliketh optional if I want to unlock Leyndell, Ashen Capital?"
    decision = plan(
        intent="route",
        rewrite=False,
        answer_language="en",
        resolved_question=question,
        search_query="Maliketh optional required to unlock Leyndell Ashen Capital progression",
        entities=["Maliketh", "Leyndell, Ashen Capital"],
    )
    check_decision(AgentDecision.model_validate(decision), question, [], {})
    pipe = ChatPipeline(settings(rag_query_mode="rewrite"), AgentLLM([decision]), FakeRetriever())
    prepared = await pipe.prepare(req(question), [])
    assert prepared.trace["agent"]["status"] == "ok"
    assert pipe.retriever.calls == [(question, True)]


@pytest.mark.parametrize("rewrite", [False, True])
def test_active_queries_and_entities_still_require_user_provenance(rewrite):
    question = "Is Maliketh optional?"
    decision = plan(
        rewrite=rewrite,
        resolved_question=question,
        search_query="Is Maliketh optional in Leyndell?",
        entities=["Maliketh", "Leyndell"],
    )
    with pytest.raises(ValueError, match="Entity has no supplied user provenance"):
        check_decision(AgentDecision.model_validate(decision), question, [], {})


async def test_agent_language_choice_cannot_override_explicit_request_language():
    llm = AgentLLM([plan(answer_language="en")])
    pipe = ChatPipeline(settings(), llm, FakeRetriever())
    p = await pipe.prepare(req(options={"lang": "vi"}), [])
    assert p.lang == "vi" and p.values["lang"] == "vi"
    p = await pipe.prepare(req(options={"lang": "auto"}), [])
    assert p.lang == "en" and p.values["lang"] == "en"


@pytest.mark.parametrize(
    "changes",
    [
        {"action": "respond"},
        {"action": "clarify", "reply": "Which level?"},
        {"selected_memory_ids": ["invented"]},
        {"constraints": [{"key": "level", "value": "150", "source_id": "current"}]},
        {"search_query": "Ranni level 150"},
        {"entities": ["Marika"], "search_query": "Who is Marika?"},
    ],
)
def test_invalid_plans_do_not_authorize_facts_or_memory(changes):
    with pytest.raises(ValueError):
        item = AgentDecision.model_validate(plan(**changes))
        check_decision(item, "Ranni là ai?", [], {})


async def test_agent_bypasses_legacy_regex_and_selects_no_unnecessary_clarification(monkeypatch):
    import app.services.gameplay as gameplay

    def forbidden(*args, **kwargs):
        raise AssertionError("Legacy gameplay is not the agent decision maker")

    monkeypatch.setattr(gameplay, "advance", forbidden)
    llm = AgentLLM(
        [
            plan(
                intent="build",
                resolved_question="Which playstyle suits Great Stars?",
                search_query="Which playstyle suits Great Stars?",
                entities=["Great Stars"],
            )
        ]
    )
    live = service(llm=llm)
    result = await live.answer(req("Great Stars hợp lối chơi nào?"))
    assert not result.clarification and len(llm.plans) == 1
    assert "agent_decision" in live.traces[result.message_id]["graph_nodes"]
    assert live.traces[result.message_id]["agent"]["intent"] == "build"
    assert llm.plans[0]["memories"] == []


async def test_invalid_model_output_is_provider_failure_not_fake_clarification():
    llm = AgentLLM([{"wrong": "schema"}])
    live = service(llm=llm)
    with pytest.raises(UpstreamError, match="quyết định hợp lệ"):
        await live.answer(req("Nó ở đâu?"))
    assert len(llm.plans) == 1
    assert not live.pipeline.retriever.calls


async def test_budget_is_enforced_before_generation():
    llm = AgentLLM()
    live = service(llm=llm, chat_agent_max_calls=1)
    with pytest.raises(UnavailableError):
        await live.answer(req())
    assert not live.traces and llm.calls == 0 and len(llm.plans) == 1


async def test_restart_capability_replay_and_scope(repo, memory):
    llm = AgentLLM()
    live = service(repo, memory, llm)
    turn = uuid4()
    first = await live.answer(req(turn_id=turn))
    assert first.conversation_token and len(first.conversation_token) >= 32
    restored = service(repo, memory, AgentLLM())
    history = await restored.stored_history(first.conversation_id, token=first.conversation_token)
    assert len(history.messages) == 2 and history.messages[-1].content == first.answer
    with pytest.raises(UnauthorizedError):
        await restored.stored_history(first.conversation_id)
    with pytest.raises(UnauthorizedError):
        await restored.answer(req(conversation_id=first.conversation_id, conversation_token="z" * 40))
    replay = await restored.answer(
        req(conversation_id=first.conversation_id, conversation_token=first.conversation_token, turn_id=turn)
    )
    assert replay.message_id == first.message_id and not restored.pipeline.llm.plans
    assert len((await restored.stored_history(first.conversation_id, token=first.conversation_token)).messages) == 2
    with pytest.raises(BadRequestError):
        await restored.answer(
            req(
                "Different",
                conversation_id=first.conversation_id,
                conversation_token=first.conversation_token,
                turn_id=turn,
            )
        )
    with pytest.raises(BadRequestError):
        await restored.answer(req(external_ref="guessable"))
    rows, trace = await memory.recall(MemoryScope(first.conversation_id, owner_hash(first.conversation_token)), "Ranni")
    assert rows and trace["method"] == "semantic"
    assert rows[0]["source_id"] == str(history.messages[0].id)
    foreign, _ = await memory.recall(MemoryScope(uuid4(), "foreign"), "Ranni")
    assert foreign == []
    wrong_owner, _ = await memory.recall(MemoryScope(first.conversation_id, "foreign"), "Ranni")
    assert wrong_owner == []
    async with repo.sessions() as session:
        conv = await session.get(Conversation, first.conversation_id)
        assert (
            conv.client_user_ref == owner_hash(first.conversation_token)
            and first.conversation_token not in conv.client_user_ref
        )


async def test_pending_clarification_survives_restart_and_model_resumes(repo, memory):
    ask = plan(
        intent="build",
        action="clarify",
        resolved_question="Moonveil stat allocation",
        entities=["Moonveil"],
        reply="Level mục tiêu?",
        reason="missing_player_details",
        missing=[{"key": "level", "label": "Level mục tiêu?", "input_type": "number", "options": []}],
    )
    live = service(repo, memory, AgentLLM([ask]))
    first = await live.answer(req("Chia chỉ số Moonveil"))
    assert first.clarification and not live.pipeline.retriever.calls

    def resume(payload):
        pending = payload["working_state"]["pending"]
        assert pending["id"] == str(first.clarification.id)
        ids = [m["id"] for m in payload["memories"] if "Moonveil" in m["text"]]
        return plan(
            intent="build",
            turn_type="clarification_reply",
            resolved_question="Moonveil stat allocation level 100",
            search_query="Moonveil stat allocation level 100",
            entities=["Moonveil"],
            selected_memory_ids=ids[:1],
            constraints=[{"key": "level", "value": "100", "source_id": "current"}],
        )

    restored = service(repo, memory, AgentLLM([resume]))
    result = await restored.answer(
        req(
            "100",
            conversation_id=first.conversation_id,
            conversation_token=first.conversation_token,
            clarification_id=first.clarification.id,
        )
    )
    assert not result.clarification and restored.pipeline.retriever.calls
    stored = await repo.load(first.conversation_id, channel="web", external_ref=None, token=first.conversation_token)
    assert stored.working["constraints"][0]["value"] == "100" and stored.working["pending"] is None


async def test_repository_cas_rollback_and_fact_supersession(repo):
    conv = ConversationOut(id=uuid4(), channel="web", created_at=datetime.now(UTC), messages=[])
    snap = Snapshot(conv, None, owner_hash("secret"), 0, {})

    def pair(text):
        now = datetime.now(UTC)
        return [
            MessageOut(id=uuid4(), role="user", content=text, created_at=now),
            MessageOut(id=uuid4(), role="assistant", content="OK", created_at=now),
        ]

    p = pair("level 100")
    await repo.save(snap, p, {"constraints": [{"key": "level", "value": "100", "source_id": str(p[0].id)}]}, plan())
    snap.revision = 1
    p2 = pair("level 120")
    await repo.save(snap, p2, {"constraints": [{"key": "level", "value": "120", "source_id": str(p2[0].id)}]}, plan())
    with pytest.raises(UnavailableError):
        await repo.save(snap, pair("stale"), {}, plan())
    rows = await repo.memories(conv.id)
    assert [r["text"] for r in rows if r["kind"] == "fact"] == ["120"]
    async with repo.sessions() as session:
        messages = (await session.scalars(select(Message))).all()
        assert len(messages) == 4


async def test_semantic_revalidates_stale_points_and_rebuild_recovers(repo, memory):
    live = service(repo, memory)
    first = await live.answer(req())
    scope = MemoryScope(first.conversation_id, owner_hash(first.conversation_token))
    await repo.rebuild(scope.conversation_id)
    counts = await memory.sync(scope)
    assert counts["indexed"] == 1 and not counts["failed"]
    rows, _ = await memory.recall(scope, "Ranni")
    assert len(rows) == 1
    # Tombstone the canonical row without touching Qdrant; stale vectors must not authorize recall.
    from sqlalchemy import update

    async with repo.sessions() as session, session.begin():
        await session.execute(update(ConversationMemory).values(status="superseded", revision=2))
    rows, _ = await memory.recall(scope, "Ranni")
    assert rows == []
    assert (await memory.sync(scope))["deleted"] == 1


async def test_failed_vector_write_remains_pending_and_database_still_restores(repo, memory, monkeypatch):
    async def broken(*args):
        raise ConnectionError("synthetic vector outage")

    monkeypatch.setattr(memory.vectors, "upsert", broken)
    live = service(repo, memory)
    first = await live.answer(req())
    assert await repo.pending(first.conversation_id)
    assert (
        len(
            (await service(repo, memory).stored_history(first.conversation_id, token=first.conversation_token)).messages
        )
        == 2
    )


async def test_cancelled_sse_does_not_commit_pending_state_or_messages(repo, memory):
    ask = plan(
        intent="build",
        action="clarify",
        entities=["Moonveil"],
        resolved_question="Moonveil build",
        reply="Which level?",
        reason="missing_player_details",
        missing=[{"key": "level", "label": "Which level?", "input_type": "number", "options": []}],
    )
    live = service(repo, memory, AgentLLM([ask]))
    events = await live.open_stream(req("Moonveil build"))
    await events.aclose()
    async with repo.sessions() as session:
        assert not (await session.scalars(select(Conversation))).all()
    assert all(not s.lock.locked() and not s.conversation.messages for s in live._conversations.values())


async def test_durable_sse_replay_returns_same_turn_without_model(repo, memory):
    llm = AgentLLM()
    llm.tokens = list(json.dumps(llm.data))
    live = service(repo, memory, llm)
    turn = uuid4()
    async with aclosing(await live.open_stream(req(turn_id=turn))) as events:
        frames = [f async for f in events]
    done = frames[-1][1]
    assert done.conversation_token
    restored = service(repo, memory, AgentLLM())
    async with aclosing(
        await restored.open_stream(
            req(conversation_id=done.conversation_id, conversation_token=done.conversation_token, turn_id=turn)
        )
    ) as events:
        replay = [f async for f in events]
    assert replay[-1][1].message_id == done.message_id and not restored.pipeline.llm.plans


async def test_http_capability_and_feedback_restore(client, repo, memory):
    from app.api.deps import get_chat_service

    live = service(repo, memory)
    client.app.dependency_overrides[get_chat_service] = lambda: live
    result = client.post("/api/v1/chat", json={"message": "Ranni là ai?", "channel": "web"}).json()
    url = f"/api/v1/conversations/{result['conversation_id']}"
    assert client.get(url).status_code == 401
    headers = {"X-Conversation-Token": result["conversation_token"]}
    assert client.get(url, headers=headers).status_code == 200
    restored = service(repo, memory)
    client.app.dependency_overrides[get_chat_service] = lambda: restored
    assert (
        client.post(
            "/api/v1/feedback", json={"message_id": result["message_id"], "rating": 1}, headers=headers
        ).status_code
        == 204
    )


@pytest.mark.parametrize(
    "mode,status,searches",
    [("off", "insufficient", 0), ("auto", "sufficient", 0), ("auto", "insufficient", 1), ("always", "sufficient", 1)],
)
async def test_agent_preserves_web_policy_and_history_is_not_assessment_evidence(mode, status, searches):
    from tests.unit.test_web_search import FakeSearch

    llm, search = AgentLLM(), FakeSearch()
    llm.assessment_status = status
    pipe = ChatPipeline(
        settings(tavily_api_key="offline", web_search_mode=mode), llm, FakeRetriever(), web_search=search
    )
    p = await pipe.prepare(req(), [])
    assert len(search.calls) == searches and len(p.hits) <= 5 and p.values["history"] == []
    assert p.trace["agent"]["status"] == "ok"


async def test_provider_failure_is_error_not_successful_clarification():
    class Broken(AgentLLM):
        async def invoke_chain(self, *args, **kwargs):
            raise LLMError("private failure", reason="provider_request_failed")

    live = service(llm=Broken())
    with pytest.raises(UpstreamError):
        await live.answer(req())
    assert not live.traces
    assert all(not s.conversation.messages for s in live._conversations.values())


def test_negation_numbers_and_resolved_request_guards():
    with pytest.raises(ValueError):
        check_decision(
            AgentDecision.model_validate(
                plan(
                    intent="build",
                    entities=["Moonveil"],
                    search_query="Moonveil build with shield",
                    resolved_question="Moonveil build with shield",
                )
            ),
            "Moonveil build không dùng khiên",
            [],
            {},
        )
    with pytest.raises(ValueError):
        check_decision(AgentDecision.model_validate(plan(resolved_question="Ranni level 150")), "Ranni là ai?", [], {})


def test_cli_dry_run_creates_no_clients(monkeypatch, capsys):
    import qdrant_client

    from scripts import memory_admin

    def forbidden(*a, **kw):
        raise AssertionError("Client created in plan-only command")

    monkeypatch.setattr(qdrant_client, "AsyncQdrantClient", forbidden)
    memory_admin.main(["setup", "--dry-run"])
    assert "PLAN ONLY" in capsys.readouterr().out


def test_manifest_has_exactly_twenty_turns_and_runner_is_plan_only(monkeypatch, capsys):
    from scripts import diagnose_agent_memory as diagnostic

    manifest, rows = diagnostic.plan()
    assert len(rows) == 20 and len([r for r in rows if r["lang"] == "vi"]) == 10
    assert any(r.get("restart_before") for r in rows)

    def forbidden(*a, **kw):
        raise AssertionError("Plan invoked live execution")

    monkeypatch.setattr(diagnostic, "execute", forbidden)
    diagnostic.main([])
    assert "PLAN ONLY" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        diagnostic.main(["--execute"])


def test_migration_offline_only_adds_runtime_and_memory_tables():
    import io

    from alembic import command
    from alembic.config import Config

    from core.config import REPO_ROOT

    output = io.StringIO()
    cfg = Config(str(REPO_ROOT / "backend/alembic.ini"), output_buffer=output)
    cfg.attributes["configure_logger"] = False
    cfg.set_main_option("script_location", str(REPO_ROOT / "backend/migrations"))
    cfg.set_main_option("sqlalchemy.url", "postgresql+asyncpg://test:unused@127.0.0.1/unused")
    command.upgrade(cfg, "0001:head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE conversation_runtime" in sql and "CREATE TABLE conversation_memories" in sql
    assert "DROP TABLE" not in sql and "CREATE TABLE messages" not in sql


async def test_dense_memory_mode_has_one_prefix_and_never_initializes_bm25(monkeypatch, tmp_path):
    from array import array

    import fastembed

    from core.encoders.onnx import FastEmbedEncoder

    seen = []

    class Dense:
        @staticmethod
        def list_supported_models():
            return [{"model": "intfloat/multilingual-e5-small"}]

        def __init__(self, **kwargs):
            self.model = SimpleNamespace(
                tokenizer=SimpleNamespace(
                    no_truncation=lambda: None,
                    encode=lambda text: SimpleNamespace(ids=[1] * (513 if "oversize" in text else 5)),
                )
            )

        def embed(self, texts):
            seen.extend(texts)
            return [array("f", [1.0] + [0.0] * 383) for _ in texts]

    def forbidden(*a, **kw):
        raise AssertionError("Dense-only memory constructed BM25")

    monkeypatch.setattr(fastembed, "TextEmbedding", Dense)
    monkeypatch.setattr(fastembed, "SparseTextEmbedding", forbidden)
    encoder = FastEmbedEncoder(tmp_path)
    await encoder.encode_dense(["Ranni", "passage: Marika"])
    await encoder.encode_dense(["query: Ranni"], query=True)
    assert seen == ["passage: Ranni", "passage: Marika", "query: Ranni"]
    with pytest.raises(ValueError):
        await encoder.encode_dense(["passage: passage: Ranni"])
    with pytest.raises(ValueError):
        await encoder.encode_dense(["oversize"])


async def test_free_text_multiple_rounds_keep_root_without_memory_or_rules(monkeypatch):
    import app.services.gameplay as legacy

    def forbidden(*args, **kwargs):
        raise AssertionError("Agent must not call the legacy classifier")

    monkeypatch.setattr(legacy, "advance", forbidden)
    ask = plan(
        intent="build",
        action="clarify",
        entities=["Moonveil"],
        reply="Level và class của bạn?",
        missing=[{"key": "profile", "label": "Thông tin nhân vật"}],
        reason="missing_player_details",
    )

    def second(payload):
        assert payload["working_state"]["request_text"] == "Chia chỉ số Moonveil"
        assert payload["question"] == "level 100"
        return {
            **ask,
            "turn_type": "clarification_reply",
            "reply": "Bạn bắt đầu với class nào?",
            "constraints": [{"key": "level", "value": "100", "source_id": "current"}],
        }

    def resume(payload):
        assert not payload["memories"]
        assert payload["working_state"]["original"] == "Chia chỉ số Moonveil"
        level = payload["working_state"]["constraints"][0]
        assert level["source_id"] != "current"
        return plan(
            intent="build",
            turn_type="clarification_reply",
            entities=["Moonveil", "Samurai"],
            resolved_question="Moonveil stat allocation level 100 Samurai PvE",
            search_query="Moonveil stat allocation level 100 Samurai PvE",
            constraints=[
                level,
                {"key": "class", "value": "Samurai", "source_id": "current"},
                {"key": "goal", "value": "PvE", "source_id": "current"},
            ],
        )

    live = service(llm=AgentLLM([ask, second, resume]), chat_history_messages=0)
    first = await live.answer(req("Chia chỉ số Moonveil"))
    second_answer = await live.answer(
        req("level 100", conversation_id=first.conversation_id, clarification_id=first.clarification.id)
    )
    result = await live.answer(
        req(
            "Samurai, chủ yếu PvE",
            conversation_id=first.conversation_id,
            clarification_id=second_answer.clarification.id,
        )
    )
    assert result.clarification is None
    assert live.pipeline.retriever.calls[0][0] == "Moonveil stat allocation level 100 Samurai PvE"
    assert [
        m.content for m in live._conversations[first.conversation_id].conversation.messages if m.role == "user"
    ] == ["Chia chỉ số Moonveil", "level 100", "Samurai, chủ yếu PvE"]


async def test_pending_ids_expiration_and_foreign_conversation_do_not_call_model():
    ask = plan(
        action="clarify",
        reply="Bạn muốn hỏi gì về Ranni?",
        missing=[{"key": "topic", "label": "Chủ đề"}],
        reason="ambiguous_subject",
    )
    llm = AgentLLM([ask])
    live = service(llm=llm)
    first = await live.answer(req())
    for conv, ident in [(first.conversation_id, uuid4()), (None, first.clarification.id)]:
        with pytest.raises(BadRequestError):
            await live.answer(req("Lore", conversation_id=conv, clarification_id=ident))
    state = live._conversations[first.conversation_id]
    state.player["pending"]["expires_at"] = "2000-01-01T00:00:00+00:00"
    with pytest.raises(BadRequestError):
        await live.answer(req("Lore", conversation_id=first.conversation_id, clarification_id=first.clarification.id))
    assert len(llm.plans) == 1


async def test_model_cancel_clears_pending_and_old_id_cannot_resume():
    ask = plan(
        action="clarify",
        reply="Bạn muốn hỏi gì?",
        missing=[{"key": "topic", "label": "Chủ đề"}],
        reason="ambiguous_subject",
    )
    cancel = plan(
        intent="cancel",
        action="respond",
        turn_type="followup",
        entities=[],
        reply="Đã hủy yêu cầu.",
        reason="conversation_control",
    )
    live = service(llm=AgentLLM([ask, cancel]))
    first = await live.answer(req())
    result = await live.answer(
        req("Hủy yêu cầu đang chờ.", conversation_id=first.conversation_id, clarification_id=first.clarification.id)
    )
    assert result.answer == "Đã hủy yêu cầu."
    assert live._conversations[first.conversation_id].player.get("pending") is None
    with pytest.raises(BadRequestError):
        await live.answer(req("Lore", conversation_id=first.conversation_id, clarification_id=first.clarification.id))


async def test_clarification_round_budget_prevents_infinite_questions():
    ask = plan(
        action="clarify",
        reply="Bạn muốn hỏi gì?",
        missing=[{"key": "topic", "label": "Chủ đề"}],
        reason="ambiguous_subject",
    )
    llm = AgentLLM([ask, {**ask, "turn_type": "clarification_reply"}])
    live = service(llm=llm)
    result = await live.answer(req())
    for _ in range(2):
        result = await live.answer(
            req("Chưa rõ", conversation_id=result.conversation_id, clarification_id=result.clarification.id)
        )
    with pytest.raises(UnavailableError, match="giới hạn hỏi bổ sung"):
        await live.answer(
            req("Chưa rõ", conversation_id=result.conversation_id, clarification_id=result.clarification.id)
        )
    assert not live.pipeline.retriever.calls


async def test_build_resume_accepts_selected_memory_handle_and_persists_message_provenance(repo, memory):
    ask = plan(
        intent="build",
        action="clarify",
        entities=["Moonveil"],
        reply="Level và class của bạn?",
        missing=[{"key": "profile", "label": "Thông tin nhân vật"}],
        reason="missing_player_details",
    )
    selected = {}

    def resume(payload):
        row = next(m for m in payload["memories"] if "Moonveil" in m["text"])
        selected.update(row)
        return plan(
            intent="build",
            turn_type="clarification_reply",
            entities=["Moonveil", "Samurai"],
            resolved_question="Moonveil stat allocation level 100 Samurai PvE",
            search_query="Moonveil stat allocation level 100 Samurai PvE",
            selected_memory_ids=[row["id"]],
            constraints=[
                {"key": "weapon", "value": "Moonveil", "source_id": row["id"]},
                {"key": "level", "value": "100", "source_id": "current"},
                {"key": "starting_class", "value": "Samurai", "source_id": "current"},
                {"key": "goal", "value": "PvE", "source_id": "current"},
            ],
        )

    llm = AgentLLM([ask, resume])
    live = service(repo, memory, llm)
    first = await live.answer(req("Chia chỉ số Moonveil giúp tôi."))
    result = await live.answer(
        req(
            "Samurai level 100, chủ yếu PvE.",
            conversation_id=first.conversation_id,
            conversation_token=first.conversation_token,
            clarification_id=first.clarification.id,
        )
    )
    stored = await repo.load(first.conversation_id, channel="web", external_ref=None, token=first.conversation_token)
    assert stored.working["pending"] is None and len(llm.plans) == 2
    assert selected["id"] != selected["source_id"]
    assert stored.working["constraints"][0]["source_id"] == selected["source_id"]
    assert live.traces[result.message_id]["agent"]["normalized_source_refs"] == 1
    assert live.pipeline.retriever.calls[-1][0] == "Moonveil stat allocation level 100 Samurai PvE"
