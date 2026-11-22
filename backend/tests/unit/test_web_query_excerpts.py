"""Hồi quy từ đoạn Classes người dùng gửi; giá trị gameplay tổng hợp không phải nhãn chất lượng."""

import json

import httpx
import pytest

from app.adapters.tavily import TavilySearch
from app.api.deps import get_chat_service
from app.api.schemas.chat import ChatRequest
from app.rag.generator import RAGValidationError
from core.errors import UpstreamError
from core.text.web_content import clean_markdown, select_excerpts
from tests.unit.test_live_chat import BODY, FakeLLM, FakeRetriever, SequenceLLM, service
from tests.unit.test_web_search import settings


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
    chunks, dropped = select_excerpts(text)
    assert dropped == 0 and len(chunks) == 1
    assert "| Stat | Required |" in chunks[0] and "| INT | 23 |" in chunks[0]
    assert "Do not use a shield" in chunks[0]
    assert chunks[0].index("First unlock") < chunks[0].index("Then talk")


def test_blocks_keep_page_order_and_headings_without_keyword_ranking():
    # 22/11: không xếp hạng độ liên quan phía server; Agent thấy mọi khối (trong ngân sách) và tự chọn.
    history = "Unrelated history. " * 95
    raw = "# Example\n\n" + history + "\n\n" + history + "\n\n## Starting classes\n\nClass list and character creation."
    chunks, _ = select_excerpts(raw)
    assert len(chunks) == 2 and chunks[0].startswith("# Example") and "## Starting classes" in chunks[1]
    # Chunk thứ hai lại mở đầu bằng tiêu đề mục, nhưng không có tiêu đề nào lặp bên trong một chunk.
    assert chunks[1].startswith("# Example") and all(c.count("# Example") == 1 for c in chunks)
    assert chunks[1].count("## Starting classes") == 1
    # Ngân sách giữ phần đầu trang, không phải một khối "tốt nhất".
    assert select_excerpts(raw, limit=1)[0] == chunks[:1]
    oversized = "| Stat | Value |\n" + "| INT | 23 |\n" * 400
    chunks, count = select_excerpts(oversized)
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
