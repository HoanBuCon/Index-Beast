"""Chính sách domain web áp đồng nhất cho kết quả mới và evidence lấy lại từ state; adapter không phụ thuộc RAG."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.adapters.tavily import WebHit, web_hit_allowed
from app.rag.pipeline import ChatPipeline
from core.config import Settings


def settings(**values):
    return Settings(_env_file=None, **{"chat_mode": "rag", "tavily_api_key": "offline-test-key", **values})


def web_hit(hit_id, url):
    return WebHit(
        hit_id,
        0,
        {
            "text": "Moonveil requires Intelligence 23.",
            "title": "Moonveil",
            "url": url,
            "origin": "web",
            "source_type": "unclassified_web",
            "game_scope": "unknown",
            "release_scope": "unknown",
            "lang": "unknown",
            "review_status": "unreviewed",
            "retrieved_at": "2026-11-04T00:00:00+00:00",
        },
    )


ON_LIST = web_hit("web:one", "https://eldenring.wiki.gg/wiki/Moonveil")
OFF_LIST = web_hit("web:off", "https://example.com/Moonveil")


@pytest.mark.parametrize(
    ("mode", "kept"),
    [("restrict", ["web:one"]), ("prefer", ["web:one", "web:off"])],
)
def test_web_evidence_restored_from_state_follows_domain_policy(mode, kept):
    pipe = ChatPipeline(settings(web_search_domains_mode=mode), None)
    prepared = SimpleNamespace(static_answer=None, trace={"evidence_selection": {"ids": ["web:one", "web:off"]}})
    pipe._context({"prepared": prepared, "documents": [], "web_hits": [ON_LIST, OFF_LIST]})
    assert [h.id for h in prepared.hits] == kept


def test_web_hit_allowed_matches_adapter_policy():
    assert web_hit_allowed(OFF_LIST, settings(web_search_domains_mode="prefer"))
    assert not web_hit_allowed(OFF_LIST, settings(web_search_domains_mode="restrict"))
    assert web_hit_allowed(ON_LIST, settings(web_search_domains_mode="restrict"))


def test_adapters_do_not_import_rag_orchestration():
    root = Path(__file__).resolve().parents[2] / "app" / "adapters"
    offenders = []
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                continue
            offenders += [f"{path.name}:{n}" for n in names if n == "app.rag" or n.startswith("app.rag.")]
    assert offenders == []
