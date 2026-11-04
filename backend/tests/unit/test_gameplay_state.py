"""State/contract and arithmetic tests; fake generation is not a quality benchmark."""

import asyncio
import hashlib
import json
from contextlib import aclosing
from pathlib import Path
from uuid import uuid4

import pytest

from app.api.schemas.chat import ChatRequest
from app.rag.build_math import SAMURAI, check_allocation
from app.rag.gameplay_knowledge import load_pack, supplements
from app.rag.generator import Prepared, RAGValidationError, validate_answer
from app.rag.pipeline import ChatPipeline
from app.services.chat import LiveChatService
from app.services.gameplay import PlayerState, advance
from core.corpus import CorpusPolicy
from core.errors import BadRequestError, NotFoundError
from core.types import Hit
from eval.validate_golden import validate
from tests.unit.test_live_chat import FakeLLM, FakeRetriever


def request(text, **kwargs):
    return ChatRequest(message=text, channel="web", **kwargs)


def live(**config):
    from core.config import Settings

    settings = Settings(_env_file=None, environment="test", chat_mode="rag", gameplay_knowledge_enabled=False, **config)
    llm, retriever = FakeLLM(), FakeRetriever()
    return LiveChatService(ChatPipeline(settings, llm, retriever), gameplay_enabled=True), llm, retriever


def test_golden_append_preserves_original_sixty_and_adds_exactly_forty():
    root = Path(__file__).parents[2] / "eval"
    lines = (root / "golden_set.jsonl").read_bytes().splitlines(keepends=True)
    assert len(lines) == 100
    assert (
        hashlib.sha256(b"".join(lines[:60])).hexdigest()
        == "85267b394c8af3bee7c55cc17e2b6738b1812e54f14197f703089cca7d570a35"
    )
    result = validate(root / "golden_set.jsonl", root / "reviews/s2-golden-set-review.jsonl")
    assert result["total"] == 100 and result["languages"]["vi"] >= 50
    assert sum(result["review_status"].values()) == 100


async def test_clarification_keeps_missing_provider_configuration_as_503():
    from core.config import Settings
    from core.errors import UnavailableError

    service = LiveChatService(
        ChatPipeline(Settings(_env_file=None, chat_mode="rag"), None, FakeRetriever()), gameplay_enabled=True
    )
    with pytest.raises(UnavailableError):
        await service.answer(request("Hướng dẫn build Moonveil"))


def test_live_diagnostic_plan_selects_25_prompts_not_the_100_question_dataset():
    from scripts.diagnose_gameplay import plan

    manifest, cases = plan()
    assert len(cases) == 30 and sum(c["mode"] == "auto" for c in cases) == 25
    assert sum(c["mode"] == "off" for c in cases) == 5
    assert len(manifest["standalone_ids"]) == 18 and len(manifest["scenario_ids"]) == 3
    assert sum(c["endpoint"] == "chat/stream" for c in cases) == 2


def test_real_http_contract_preserves_question_and_rejects_wrong_id(client):
    from app.api.deps import get_chat_service

    service, llm, retriever = live()
    llm.tokens = list(json.dumps(llm.data))
    client.app.dependency_overrides[get_chat_service] = lambda: service
    response = client.post("/api/v1/chat", json={"message": "Hướng dẫn build Moonveil", "channel": "web"})
    assert response.status_code == 200 and response.json()["clarification"]["fields"][0]["key"] == "goal"
    assert not llm.calls and not retriever.calls
    body = {
        "message": "PvE",
        "channel": "web",
        "conversation_id": response.json()["conversation_id"],
        "clarification_id": str(uuid4()),
    }
    assert client.post("/api/v1/chat", json=body).status_code == 400
    body["clarification_id"] = response.json()["clarification"]["id"]
    assert client.post("/api/v1/chat/stream", json=body).status_code == 200


async def test_abandoned_stream_does_not_commit_pending_question():
    service, _, _ = live()
    stream = await service.open_stream(request("Chia chỉ số Moonveil"))
    await stream.aclose()
    assert all(state.player is None and not state.conversation.messages for state in service._conversations.values())


def test_bounded_questions_merge_free_text_and_do_not_mutate_original_state():
    original = PlayerState()
    first = advance(original, request("Chia chỉ số Moonveil"), "vi", now=100)
    assert [f.key for f in first.clarification.fields] == ["level", "starting_class"]
    assert original.pending is None
    second = advance(first.state, request("100, Samurai, PvE"), "en", now=101)
    assert second.status == "resumed" and second.state.lang == "vi"
    assert all(s in second.query for s in ("Moonveil", "100", "Samurai", "PvE"))
    assert second.clarification is None and first.state.pending is not None


def test_partial_invalid_input_correction_cancel_new_topic_and_expiry():
    first = advance(PlayerState(), request("Chia chỉ số Moonveil"), "vi", now=100)
    invalid = advance(first.state, request("level=-1"), "vi", now=101)
    assert invalid.clarification and "level" not in invalid.state.slots
    partial = advance(first.state, request("level=100"), "vi", now=102)
    assert "level" not in [f.key for f in partial.clarification.fields]
    completed = advance(partial.state, request("Samurai, PvE"), "vi", now=103)
    assert completed.status == "resumed"
    updated = advance(completed.state, request("Chia chỉ số Moonveil level 120 Samurai PvP"), "vi", now=104)
    assert updated.state.slots["level"] == "120" and updated.state.slots["goal"] == "PvP"
    topic = advance(first.state, request("Ranni là ai?"), "vi", now=105)
    assert topic.clarification is None and topic.query == "Ranni là ai?"
    assert advance(first.state, request("hủy"), "vi", now=106).status == "cancelled"
    with pytest.raises(BadRequestError):
        advance(first.state, request("100", clarification_id=first.clarification.id), "vi", now=2000)
    with pytest.raises(BadRequestError):
        advance(first.state, request("100", clarification_id=uuid4()), "vi", now=107)


def test_route_asks_only_missing_state_and_resumes_with_explicit_form_fields():
    first = advance(PlayerState(), request("Tôi nên đi đâu tiếp?"), "vi", now=100)
    assert {f.key for f in first.clarification.fields} == {"current_location", "objective"}
    second = advance(
        first.state,
        request("current_location=Mistwood\nobjective=Nokron", clarification_id=first.clarification.id),
        "vi",
        now=101,
    )
    assert second.status == "resumed" and "Mistwood" in second.query and "Nokron" in second.query


def test_factual_questions_do_not_confirm_player_class_and_names_are_not_fuzzy_matched():
    state = advance(PlayerState(), request("Samurai bắt đầu có spell không?"), "vi", now=100).state
    assert "starting_class" not in state.slots
    decision = advance(state, request("Chia chỉ số Moonveillike level 100 PvE"), "vi", now=101)
    assert "weapon" not in decision.state.slots


def test_pipeline_keeps_original_allocation_intent_when_rewrite_says_distribution():
    from app.rag.retriever import hit_to_document
    from core.config import Settings
    from tests.unit.test_web_search import web_hit

    config = Settings(_env_file=None, chat_mode="rag", rag_corpus_policy="pilot", rag_languages=["en"])
    pipe = ChatPipeline(config, FakeLLM(), FakeRetriever())
    raw = "Chia chỉ số Moonveil level 100 Samurai PvE"
    state = {
        "prepared": Prepared("rag", "vi", []),
        "req": request(raw),
        "query": "Moonveil stat distribution for level 100 Samurai in PvE",
        "entities": ["Moonveil", "Samurai"],
        "documents": [hit_to_document(h) for h in supplements(raw, pipe.policy, True)],
        "web_hits": [web_hit()],
    }
    pipe._context(state)
    assert {h.payload.get("rule_kind") for h in state["prepared"].hits} >= {
        "level_rule",
        "class_rule",
        "weapon_rule",
        "respec_rule",
    }


@pytest.mark.parametrize("streaming", [False, True])
async def test_clarification_json_sse_history_and_followup_keep_subject_without_tool_call(streaming):
    service, llm, retriever = live(chat_history_messages=0)
    req = request("Chia chỉ số Moonveil")
    if streaming:
        async with aclosing(await service.open_stream(req)) as events:
            frames = [frame async for frame in events]
        assert frames[-1][0] == "done"
        clarification = next(p.clarification for name, p in frames if name == "sources")
        conversation_id = frames[-1][1].conversation_id
    else:
        answer = await service.answer(req)
        clarification, conversation_id = answer.clarification, answer.conversation_id
    assert clarification and not retriever.calls and not llm.calls
    assert service.history(conversation_id).messages[-1].clarification == clarification
    answer = await service.answer(
        request(
            "level=100\nstarting_class=Samurai\ngoal=PvE",
            conversation_id=conversation_id,
            clarification_id=clarification.id,
        )
    )
    assert answer.clarification is None and retriever.calls
    query = retriever.calls[0][0]
    assert all(s in query for s in ("Moonveil", "100", "Samurai", "PvE"))
    with pytest.raises(BadRequestError):
        await service.answer(request("100", conversation_id=conversation_id, clarification_id=clarification.id))


async def test_conversations_channels_and_failed_generation_do_not_share_or_commit_state():
    service, llm, retriever = live()
    first = await service.answer(request("Chia chỉ số Moonveil"))
    other = await service.answer(request("Tôi nên đi đâu tiếp?"))
    assert first.clarification.id != other.clarification.id
    with pytest.raises(BadRequestError):
        await service.answer(
            request("100", conversation_id=other.conversation_id, clarification_id=first.clarification.id)
        )
    with pytest.raises(NotFoundError):
        await service.answer(ChatRequest(message="100", channel="discord", conversation_id=first.conversation_id))
    llm.fail_at = 0

    # A failed generation must not commit the new profile or consume the pending question.
    async def failed(*args, **kwargs):
        raise RuntimeError("offline provider failure")

    llm.invoke_chain = failed
    with pytest.raises(RuntimeError):
        await service.answer(request("100, Samurai, PvE", conversation_id=first.conversation_id))
    assert service._conversations[first.conversation_id].player.pending.id == first.clarification.id


async def test_same_conversation_serializes_two_answers_and_does_not_cross_apply_stale_id():
    service, _, _ = live()
    first = await service.answer(request("Hướng dẫn build Moonveil"))
    req = request("PvE", conversation_id=first.conversation_id, clarification_id=first.clarification.id)
    results = await asyncio.gather(service.answer(req), service.answer(req), return_exceptions=True)
    assert sum(isinstance(result, BadRequestError) for result in results) == 1


def test_pack_keeps_pending_metadata_hashes_and_policy_spoilers():
    pack = load_pack()
    for group in pack["groups"]:
        for hit in group["hits"]:
            assert hashlib.sha256(hit["payload"]["text"].encode()).hexdigest() == hit["text_sha256"]
            assert hit["payload"].get("review_status") != "approved"
    policy = CorpusPolicy("pilot", ("en",))
    assert supplements("Ranni questline", policy, True)
    assert not supplements("Ranni questline", policy, False)
    assert not supplements("Ranni questline", CorpusPolicy(), True)
    assert not supplements("Who is Ranni?", policy, True)


VALID = dict(zip(SAMURAI, (40, 20, 20, 12, 18, 53, 8, 8), strict=True))
PROFILE = {"starting_class": "Samurai", "weapon": "Moonveil", "level": "100"}


def test_arithmetic_feasibility_is_not_optimality():
    result = check_allocation(VALID, PROFILE)
    assert result["attribute_total"] == 179 and result["feasible"] and not result["optimality_verified"]


def test_arithmetic_question_does_not_require_weapon_class_or_playstyle():
    query = "Does the stat spread match level 100 by the sum-minus-79 rule?"
    result = advance(PlayerState(), request(query), "en", now=100)
    assert result.clarification is None and result.query == query
    selected = supplements(query, CorpusPolicy("pilot", ("en",)), True)
    assert {h.payload.get("rule_kind") for h in selected} == {"level_rule"}


def test_accounting_sources_survive_web_interleave_within_top_five():
    from app.rag.pipeline import select_context
    from app.rag.web_search import merge_evidence
    from tests.unit.test_web_search import web_hit

    policy = CorpusPolicy("pilot", ("en",))
    query = "Chia chỉ số Moonveil level 100 Samurai PvE"
    local = supplements(query, policy, True)
    selected = select_context(merge_evidence(local, [web_hit()]), 5, 12000, policy=policy, query=query)
    assert len(selected) <= 5
    assert {h.payload.get("rule_kind") for h in selected} >= {"level_rule", "class_rule", "weapon_rule", "respec_rule"}


@pytest.mark.parametrize(
    "changes",
    [
        {"vigor": 41},
        {"faith": 7, "vigor": 41},
        {"strength": 11, "vigor": 41},
        {"intelligence": 22, "vigor": 71},
        {"vigor": True},
        {"vigor": 100},
    ],
)
def test_invalid_totals_floors_requirements_types_and_caps_rejected(changes):
    with pytest.raises(ValueError):
        check_allocation({**VALID, **changes}, PROFILE)


def test_generated_allocation_requires_real_accounting_sources_and_server_renders_values():
    rules = [g for g in load_pack()["groups"] if len(g["hits"]) == 4 and g["hits"][0]["payload"].get("rule_kind")][0][
        "hits"
    ]
    hits = [Hit(r["id"], 0, r["payload"]) for r in rules]
    prepared = Prepared("rag", "vi", [], hits=hits, values={"player_profile": PROFILE})
    data = {
        "answer": "Một ví dụ theo các ràng buộc đã nêu [1][2][3][4].",
        "evidence": [{"index": i, "quote_id": "q0"} for i in range(1, 5)],
        "insufficient": False,
        "build_allocation": VALID,
    }
    result = validate_answer(prepared, data)
    assert "Intelligence 53" in result.answer and prepared.trace["build_check"]["attribute_total"] == 179
    with pytest.raises(RAGValidationError):
        validate_answer(prepared, {**data, "build_allocation": {**VALID, "vigor": 41}})
    with pytest.raises(RAGValidationError):
        validate_answer(
            Prepared("rag", "vi", [], hits=hits, values={"player_profile": {**PROFILE, "starting_class": "Wretch"}}),
            data,
        )
