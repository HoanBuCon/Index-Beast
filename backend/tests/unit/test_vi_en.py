"""VI/EN orchestration and diagnostic tests. Synthetic rankings are NOT retrieval quality evidence."""

import asyncio
import json
from copy import deepcopy

import pytest
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableLambda
from pydantic import Field, ValidationError

from app.adapters.llm import LLMError, LLMResponse
from app.api.schemas.chat import ChatRequest
from app.rag.pipeline import ChatPipeline, select_context
from app.rag.query_plan import fuse_ranked, plan_queries
from app.rag.retriever import hit_to_document
from app.rag.rewrite import rewrite, rewrite_problem
from core.config import Settings
from core.errors import UnavailableError
from core.types import Hit
from scripts import benchmark_vi_en as diagnostic


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


def rewritten(query="Who is Ranni?", **updates):
    return {
        "standalone_query_en": query,
        "lang": "vi",
        "entities": ["Ranni"],
        "out_of_scope": False,
        "ambiguous": False,
        **updates,
    }


class ScriptedLLM:
    def __init__(self, output=None, delay=0):
        self.output = output if output is not None else rewritten()
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


def pipeline(llm, retriever, **settings):
    return ChatPipeline(Settings(_env_file=None, chat_mode="rag", rag_rewrite_enabled=True, **settings), llm, retriever)


@pytest.mark.parametrize(
    "question,query,entities,problem",
    [
        ("Bloodhound's Fang là gì?", "What is Bloodhound's Fang?", ["Bloodhound's Fang"], None),
        ("Lấy Uchigatana ở đâu?", "Uchigatana lore", ["Uchigatana"], "intent_lost"),
        ("Ranni là ai?", "Who is Moonveil?", ["Moonveil"], "unverified_entity"),
        ("Ranni là ai?", "Who is the witch?", [], "proper_name_lost"),
        ("Moonveil build level 80", "Moonveil build level 150", ["Moonveil"], "numeric_constraint_lost"),
        ("Moonveil build level 80", "Moonveil build level 80 INT 40", ["Moonveil"], "numeric_constraint_added"),
        ("Moonveil build cho PvP", "Moonveil build", ["Moonveil"], "goal_lost"),
        ("Moonveil build không dùng khiên", "Moonveil build with a shield", ["Moonveil"], "negation_lost"),
        ("Moonveil build không dùng khiên", "Moonveil build without a shield", ["Moonveil"], None),
        ("Chiến thuật né Waterfowl Dance của Malenia?", "Malenia Waterfowl Dance lore", ["Malenia"], "intent_lost"),
        ("So sánh Uchigatana và Moonveil", "Uchigatana and Moonveil comparison", ["Uchigatana", "Moonveil"], None),
    ],
)
def test_surface_guards_preserve_names_constraints_and_intents(question, query, entities, problem):
    assert rewrite_problem(question, query, entities, []) == problem


def test_proper_name_cannot_be_preserved_only_as_substring_of_another_name():
    assert rewrite_problem("Ranni là ai?", "Who is Rannith?", ["Ranni"], []) == "entity_lost"


@pytest.mark.parametrize(
    "settings",
    [
        {"rag_query_mode": "unbounded"},
        {"rag_rewrite_timeout_seconds": 0},
        {"rag_retrieval_timeout_seconds": 0},
        {"rag_rewrite_max_tokens": 8192},
    ],
)
def test_query_budget_configuration_is_bounded(settings):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **settings)


async def test_reply_language_is_independent_of_query_and_model_language_field():
    llm = ScriptedLLM(rewritten(lang="en"))
    retriever = RankedRetriever()
    prepared = await pipeline(llm, retriever).prepare(ChatRequest(message="Ranni là ai?", channel="web"), [])
    assert retriever.calls == ["Who is Ranni?"]
    assert prepared.lang == prepared.values["lang"] == "vi"
    assert json.loads(prepared.values["payload"])["question"] == "Ranni là ai?"
    assert "query" not in prepared.trace["retrieval_queries"][0]
    assert len(llm.inputs) == 1 and llm.bound[0]["max_tokens"] == 512 and llm.bound[0]["thinking"] is False


@pytest.mark.parametrize(
    "output",
    [
        "broken JSON",
        LLMError("provider failed"),
        rewritten("Who is someone?", entities=[]),
        rewritten("What is Moonveil?", entities=["Moonveil"]),
    ],
)
async def test_bad_rewrites_fall_back_to_original_without_second_translation(output):
    llm, retriever = ScriptedLLM(output), RankedRetriever()
    prepared = await pipeline(llm, retriever, rag_query_mode="dual").prepare(
        ChatRequest(message="Ranni là ai?", channel="web"), []
    )
    assert retriever.calls == ["Ranni là ai?"] and len(llm.inputs) == 1
    assert prepared.trace["rewrite_fallback"] and prepared.trace["rewrite"]["status"] == "fallback"


async def test_rewrite_timeout_and_cancellation_do_not_guess_entities():
    llm = ScriptedLLM(delay=10)
    stats = {}
    result, fallback = await rewrite(llm, "Ranni là ai?", [], "vi", deadline_seconds=0.01, diagnostics=stats)
    assert fallback and result.standalone_query_en == "Ranni là ai?" and llm.cancelled
    assert stats["reason"] == "timeout"
    llm = ScriptedLLM(delay=10)
    task = asyncio.create_task(rewrite(llm, "Ranni?", [], "vi"))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_explicit_history_reference_and_ambiguous_nickname():
    history = [{"role": "user", "content": "Tôi muốn tìm hiểu Bloodhound's Fang."}]
    llm = ScriptedLLM(rewritten("Where can I obtain Bloodhound's Fang?", entities=["Bloodhound's Fang"]))
    retriever = RankedRetriever()
    await pipeline(llm, retriever).prepare(ChatRequest(message="Lấy nó ở đâu?", channel="web"), history)
    assert retriever.calls == ["Where can I obtain Bloodhound's Fang?"] and llm.inputs[0]["history"] == history
    llm = ScriptedLLM(rewritten("Who is the moon lady?", entities=[], ambiguous=True))
    retriever = RankedRetriever()
    prepared = await pipeline(llm, retriever).prepare(ChatRequest(message="Nguyệt nữ là ai?", channel="web"), [])
    assert not retriever.calls and prepared.static_answer
    assert prepared.trace["rewrite"]["reason"] == "ambiguous"


@pytest.mark.parametrize("question", ["Cô ấy ở đâu?", "Lấy nó ở đâu?", "Where can I obtain it?"])
async def test_rewrite_failure_does_not_guess_missing_referent(question):
    retriever = RankedRetriever()
    prepared = await pipeline(ScriptedLLM("broken JSON"), retriever).prepare(
        ChatRequest(message=question, channel="web"), []
    )
    assert not retriever.calls and prepared.static_answer and prepared.trace["rewrite_fallback"]


def test_query_plans_and_rank_fusion_ignore_native_scores_and_duplicate_ids():
    assert plan_queries("Ranni?", "Ranni?", "dual") == [("original", "Ranni?")]
    assert len(plan_queries("Ranni là ai?", "Who is Ranni?", "dual")) == 2
    a, b, c = hit("a"), Hit("b", 9999, hit("b").payload), hit("c")
    result = fuse_ranked([[a, a, b], [b, c]], 5)
    assert [row.id for row in result] == ["b", "a", "c"]
    assert result[0].payload == b.payload and result[0].score < 1


def test_duplicate_text_does_not_discard_distinct_release_trigger_or_images():
    original = hit("a")
    copied = Hit("copy", 1, deepcopy(original.payload))
    variations = [
        Hit(str(i), 1, {**original.payload, **update})
        for i, update in enumerate(
            [
                {"release_scope": "sote_candidate"},
                {"trigger": "after quest"},
                {"image_ids": ["image"]},
            ]
        )
    ]
    rows = fuse_ranked([[original, copied, *variations]], 10)
    assert len(rows) == 4 and all(row.id != "copy" for row in rows)
    context = select_context([original, copied, hit("different")], 5, 12000)
    assert [row.id for row in context] == ["a", "different"]


async def test_dual_query_budget_metadata_dedup_and_top5():
    vi, en = "Ranni là ai?", "Who is Ranni?"
    rows = [hit(str(i), artifact_chunk_id=f"artifact-{i}", release_scope="unknown") for i in range(8)]
    retriever = RankedRetriever(rankings={en: rows, vi: list(reversed(rows))})
    prepared = await pipeline(ScriptedLLM(), retriever, rag_query_mode="dual").prepare(
        ChatRequest(message=vi, channel="web"), [], diagnostic_queries=True
    )
    assert retriever.calls == [en, vi] and len(prepared.hits) == 5
    assert len({row.id for row in prepared.hits}) == 5
    assert all(
        row.payload["release_scope"] == "unknown" and row.payload["artifact_chunk_id"].startswith("artifact-")
        for row in prepared.hits
    )
    assert len(prepared.trace["retrieval_queries"]) == 2
    assert prepared.trace["retrieval_queries"][0]["query"] == en


@pytest.mark.parametrize("failure", ["unavailable", "timeout"])
async def test_one_failed_query_can_use_other_but_two_failures_are_not_insufficient(failure):
    vi, en = "Ranni là ai?", "Who is Ranni?"
    retriever = RankedRetriever(
        rankings={vi: [hit()]},
        failures={en} if failure == "unavailable" else set(),
        delays={en: 1} if failure == "timeout" else {},
    )
    config = {"rag_query_mode": "dual", "rag_retrieval_timeout_seconds": 0.5}
    prepared = await pipeline(ScriptedLLM(), retriever, **config).prepare(ChatRequest(message=vi, channel="web"), [])
    assert len(prepared.hits) == 1 and prepared.trace["retrieval_queries"][0]["status"] == "error"
    retriever.failures.add(vi)
    with pytest.raises(UnavailableError):
        await pipeline(ScriptedLLM(), retriever, **config).prepare(ChatRequest(message=vi, channel="web"), [])


def test_paired_cases_are_pending_and_cover_required_categories():
    pairs = diagnostic.load_pairs(diagnostic.DEFAULT_PAIRS)
    assert len(pairs) == 13 and all(
        pair["review_status"] == "pending" and not pair["expected_chunk_ids"] for pair in pairs
    )
    assert {
        "acquisition",
        "quest",
        "mechanics",
        "boss_strategy",
        "build",
        "explicit_alias",
        "ambiguous_nickname",
        "missing_evidence",
        "follow_up",
    } <= {pair["category"] for pair in pairs}


def test_plan_only_has_no_clients_models_or_writes(monkeypatch, capsys):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Plan-only attempted execution/write")

    monkeypatch.setattr(diagnostic, "live", forbidden)
    monkeypatch.setattr(diagnostic.Path, "write_text", forbidden)
    assert diagnostic.main(["--strategies", "original", "rewrite", "dual"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "plan_only" and plan["rows"] == 78 and plan["max_retrieval_queries"] == 104
    assert plan["max_logical_rewrite_calls"] == 52


def test_execute_needs_explicit_llm_permission_before_clients(monkeypatch):
    monkeypatch.setattr(diagnostic, "live", lambda *_: pytest.fail("Must fail before creating clients"))
    with pytest.raises(SystemExit):
        diagnostic.main(["--execute", "--strategies", "rewrite"])


def test_invalid_pair_reports_file_line_without_echoing_body(tmp_path):
    path = tmp_path / "pairs.jsonl"
    path.write_text('{"private":"invalid case"}\n', encoding="utf-8")
    with pytest.raises(ValueError) as error:
        diagnostic.load_pairs(path)
    assert str(path) + ":1" in str(error.value) and "private" not in str(error.value)


async def test_benchmark_distinguishes_source_hit_evidence_recall_and_generation_errors():
    pair = diagnostic.load_pairs(diagnostic.DEFAULT_PAIRS)[0]
    llm = ScriptedLLM("private invalid JSON")
    retriever = RankedRetriever(rankings={pair["vi"]: [hit()], pair["en"]: [hit()]})
    report = await diagnostic.benchmark([pair], Settings(_env_file=None), llm, retriever, ["original"], generate=True)
    assert len(report["rows"]) == 2
    for row in report["rows"]:
        assert row["metrics"]["candidate_source_hit"] is True
        assert row["metrics"]["top5_evidence_recall"] is None
        assert row["generation"]["status"] == "error" and row["status"] == "prepared"
        assert row["generation"]["format_failure"]["reason"] == "invalid_json"
        assert all(value is None for value in row["manual_review"].values())
    assert "private invalid JSON" not in json.dumps(report)
    assert "NOT evidence recall" in report["notes"]


async def test_benchmark_retrieval_errors_are_separate_from_insufficient_and_no_llm_mode():
    pair = diagnostic.load_pairs(diagnostic.DEFAULT_PAIRS)[0]
    retriever = RankedRetriever(failures={pair["vi"], pair["en"]})
    report = await diagnostic.benchmark([pair], Settings(_env_file=None), diagnostic.NoLLM(), retriever, ["original"])
    assert all(row["failure_stage"] == "retrieval" and row["trace"]["retrieval_queries"] for row in report["rows"])
    llm = ScriptedLLM({"answer": "Chưa đủ bằng chứng.", "evidence": [], "insufficient": True})
    retriever = RankedRetriever(rankings={pair["vi"]: [hit()], pair["en"]: [hit()]})
    report = await diagnostic.benchmark([pair], Settings(_env_file=None), llm, retriever, ["original"], generate=True)
    assert all(
        row["generation"]["status"] == "ok" and row["generation"]["outcome"] == "insufficient" for row in report["rows"]
    )


async def test_evidence_recall_requires_reviewed_chunk_labels_not_just_source_page():
    pair = diagnostic.load_pairs(diagnostic.DEFAULT_PAIRS)[0]
    prepared = await pipeline(ScriptedLLM(), RankedRetriever(rankings={"Who is Ranni?": [hit()]})).prepare(
        ChatRequest(message="Ranni là ai?", channel="web"), []
    )
    pair.update(review_status="reviewed", expected_chunk_ids=["a", "missing"])
    metrics = diagnostic.retrieval_metrics(pair, prepared)
    assert metrics["top5_source_hit"] is True and metrics["top5_evidence_recall"] == 0.5
