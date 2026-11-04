"""Regression from the user's Classes snippet; synthetic gameplay values are not quality labels."""

import json

import httpx
import pytest

from app.adapters.tavily import TavilySearch
from app.api.deps import get_chat_service
from app.api.schemas.chat import ChatRequest
from app.rag.generator import RAGValidationError
from app.rag.pipeline import ChatPipeline
from app.rag.web_content import clean_markdown, select_excerpts
from app.rag.web_query import web_query
from core.errors import UpstreamError
from tests.unit.test_live_chat import BODY, FakeLLM, FakeRetriever, SequenceLLM, service
from tests.unit.test_vi_en import RankedRetriever, ScriptedLLM
from tests.unit.test_web_search import FakeSearch, settings


@pytest.mark.parametrize("question", ["Các class khởi đầu của elden ring", "Cac class khoi dau cua Elden Ring"])
def test_starting_class_query_has_game_and_english_intent_without_losing_original(question):
    query, kind = web_query(question)
    assert question in query and kind == "starting_classes"
    assert "starting classes list character creation" in query


def test_query_keeps_entities_constraints_release_and_goals_without_new_facts():
    original = "Moonveil +10 build level 100 INT 40 PvP without shield patch 1.16 SotE"
    query, kind = web_query(original)
    assert query == "Elden Ring\n" + original and kind == "domain_anchor"
    query, _ = web_query("Elden Ring Nightreign classes")
    assert query == "Elden Ring Nightreign classes"


async def test_bad_rewrite_still_searches_classes_intent_and_records_query_only_on_opt_in():
    search = FakeSearch()
    pipeline = ChatPipeline(settings(), ScriptedLLM("invalid JSON"), RankedRetriever(), web_search=search)
    request = ChatRequest(message="Các class khởi đầu của elden ring", channel="web", options={"web_search": "always"})
    result = await pipeline.prepare(request, [])
    assert "starting classes list" in search.calls[0]
    assert "query" not in result.trace["web_search"]
    diagnostic = await pipeline.prepare(request, [], diagnostic_queries=True)
    assert diagnostic.trace["web_search"]["query"] == search.calls[-1]


@pytest.mark.parametrize("separator", ["\n", " "])
def test_classes_skin_navigation_removed_article_and_links_labels_preserved(separator):
    raw = separator.join(
        [
            '[![](/skins/fx-logo.svg)](https://fextralife.com/ "Visit the main page")',
            "[Sign In Now](https://fextralife.com/login/)",
            'Navigation * [Main page](/Elden_Ring_Wiki "Visit the main page [z]")',
            "# Classes | Elden Ring Wiki",
            "**Classes** are combat archetypes available at "
            '[Character Creation](/Character_Creation "Character Creation").',
        ]
    )
    text, stats = clean_markdown(raw)
    assert text.startswith("# Classes") and "combat archetypes" in text and "Character Creation" in text
    assert "Sign In" not in text and "Navigation" not in text and "https://" not in text
    assert stats["navigation_lines_removed"] > 0


def test_cleaning_preserves_table_headers_numbers_negation_and_step_order():
    raw = (
        "# Guide\n\nFirst unlock the door.\n\nThen talk to the NPC.\n\n"
        "| Stat | Required |\n| --- | --- |\n| INT | 23 |\n\nDo not use a shield."
    )
    text, _ = clean_markdown(raw)
    chunks, dropped = select_excerpts(text, "Elden Ring INT requirements")
    assert dropped == 0 and len(chunks) == 1
    assert "| Stat | Required |" in chunks[0] and "| INT | 23 |" in chunks[0]
    assert "Do not use a shield" in chunks[0]
    assert chunks[0].index("First unlock") < chunks[0].index("Then talk")


def test_query_relevant_late_section_can_replace_unrelated_page_start_without_cutting_table():
    unrelated = "Unrelated history. " * 160
    raw = "# Example\n\n" + unrelated + "\n\n## Starting classes\n\nClass list and character creation."
    chunks, _ = select_excerpts(raw, "starting classes list character creation", limit=1)
    assert len(chunks) == 1 and "Class list" in chunks[0]
    assert "## Starting classes" in chunks[0]
    oversized = "| Stat | Value |\n" + "| INT | 23 |\n" * 400
    chunks, count = select_excerpts(oversized, "stats")
    assert chunks == [] and count == 1


async def test_extract_receives_query_and_cleaned_evidence_not_skin_or_snippet():
    url = "https://eldenring.wiki.fextralife.com/Classes"

    def handler(request):
        body = json.loads(request.content)
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{"url": url, "title": "Classes", "content": "snippet"}]})
        assert "Elden Ring" in body["query"] and body["chunks_per_source"] == 3
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": url,
                        "raw_content": (
                            "[Sign In Now](https://fextralife.com/login/)\nNavigation\n"
                            "# Classes\n\nClasses determine starting equipment."
                        ),
                    }
                ],
                "failed_results": [],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        hits, stats = await TavilySearch(settings(), client=client).search("Elden Ring starting classes")
    assert hits and "Sign In" not in hits[0].payload["text"]
    assert "snippet" not in hits[0].payload["text"] and stats["navigation_lines_removed"] > 0


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"answer": "Read https://example.test [1]."}, "model_url"),
        ({"limitation": "Unknown detail [1]."}, "invalid_limitation"),
    ],
)
async def test_link_or_limitation_protocol_failure_regenerates_without_weakening_validation(change, reason):
    valid = FakeLLM().data
    llm = SequenceLLM([json.dumps({**valid, **change}), json.dumps(valid)])
    live = service("rag", llm, FakeRetriever())
    result = await live.answer(ChatRequest(**BODY))
    assert result.grounded and llm.attempts == 2
    assert live.traces[result.message_id]["generation_retry_reason"] == reason
    assert llm.seen[0]["payload"] == llm.seen[1]["payload"]


async def test_repeated_invalid_url_still_errors_and_does_not_save():
    data = {**FakeLLM().data, "answer": "https://unverified.test [1]."}
    llm = SequenceLLM([json.dumps(data)])
    live = service("rag", llm, FakeRetriever())
    with pytest.raises(UpstreamError):
        await live.answer(ChatRequest(**BODY))
    assert llm.attempts == 2 and not live.traces


def test_central_error_log_includes_validation_reason_without_exposing_output(client, caplog):
    class BrokenService:
        async def answer(self, body):
            raise RAGValidationError("unknown_quote_id")

    client.app.dependency_overrides[get_chat_service] = lambda: BrokenService()
    response = client.post("/api/v1/chat", json=BODY)
    assert response.status_code == 502 and "reason" not in response.json()
    assert any(r.msg == "app error" and r.data.get("reason") == "unknown_quote_id" for r in caplog.records)
