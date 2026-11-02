"""Pilot admission and indexing preflight. Only synthetic artifacts/vectors; no external services."""

import hashlib
import json
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from qdrant_client import AsyncQdrantClient

from app.rag.pipeline import ChatPipeline, select_context
from app.rag.retriever import HybridRetriever, document_to_hit, hit_to_document
from core.config import Settings
from core.corpus import ADMISSION_KEY, CorpusPolicy
from core.ids import chunk_id, document_id
from core.types import ChunkRecord, Encoded, Hit
from core.vector.store import QdrantStore
from ingest.indexing import index_chunks, inspect_artifact


def record(number=1, **extra):
    doc = document_id("wikigg", str(number))
    return {
        "doc_id": str(doc),
        "chunk_id": str(chunk_id(doc, 0)),
        "ordinal": 0,
        "source": "wikigg",
        "source_id": str(number),
        "title": "Synthetic Ranni",
        "section": "Lore",
        "text": "Ranni is an Empyrean.",
        "embedding_text": "passage: Ranni\nRanni is an Empyrean.",
        "url": "https://example.test/ranni#Lore",
        "section_anchor": "Lore",
        "game_scope": "elden_ring",
        "release_scope": "unknown",
        "lang": "en",
        "source_type": "wiki_prose",
        "token_count": 20,
        "revision_id": 123,
        "source_updated_at": None,
        "updated_at": "2026-10-29T00:00:00Z",
        "source_locations": ["dom:1:p"],
        "custom": {"nested": [None, "original"]},
        **extra,
    }


def artifact(tmp_path, rows):
    path = tmp_path / "chunks.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8-sig")
    return path


PILOT = CorpusPolicy("pilot", ("en",))


def test_default_settings_and_explicit_language_selection():
    settings = Settings(_env_file=None)
    assert settings.chat_mode == "mock"
    assert CorpusPolicy.from_settings(settings) == PILOT
    assert Settings(_env_file=None, rag_languages="en,ja,en").rag_languages == ["en", "ja"]
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rag_languages="en,,ja")


@pytest.mark.parametrize("release", ["unknown", "base_candidate", "mixed_or_sote_candidate", "sote_candidate"])
def test_pilot_keeps_candidate_and_unknown_labels_without_approving_source(tmp_path, release):
    original = record(release_scope=release, review_status="review")
    path = artifact(tmp_path, [original])
    before = path.read_bytes()
    result = inspect_artifact(path, PILOT)
    assert len(result.chunks) == 1 and not result.invalid and not result.excluded
    indexed = PILOT.index_payload(result.chunks[0].payload())
    assert indexed["release_scope"] == release and indexed["review_status"] == "review"
    assert indexed[ADMISSION_KEY] == "pilot-v1"
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "extra,allowed",
    [
        ({"scope_status": "excluded", "scope_reason": "explicit_dlc_lead_definition"}, True),
        ({"scope_status": "excluded", "scope_reason": "explicit_dlc_heading:Messmer"}, True),
        ({"scope_status": "review", "scope_reason": "no_positive_scope_evidence"}, True),
        ({"scope_status": "review", "scope_reason": "unclassified_structure"}, False),
        ({"scope_status": "excluded", "scope_reason": "unused_or_cut_section"}, False),
        ({"decision": "excluded", "scope_reason": "explicit_dlc_lead_definition"}, False),
        ({"chunk_eligible": False}, False),
        ({"review_status": "rejected"}, False),
        ({"game_scope": "dark_souls"}, False),
        ({"lang": "unknown"}, False),
    ],
)
def test_pilot_reconsiders_only_known_scope_reasons(extra, allowed):
    assert (PILOT.exclusion_reason(record(**extra)) is None) is allowed


def test_reviewed_policy_still_requires_base_and_explicit_approval():
    old = record(game_scope="base", review_status="approved")
    assert CorpusPolicy().exclusion_reason(old) is None
    assert CorpusPolicy().exclusion_reason(record()) is not None
    assert CorpusPolicy().exclusion_reason({**old, "review_status": "review"}) is not None


def test_language_selection_is_distinct_from_malformed_data_and_duplicate_ids(tmp_path):
    path = artifact(tmp_path, [record(1, lang="ja"), record(2), record(3, text="  "), record(1)])
    result = inspect_artifact(path, PILOT)
    assert result.total == 4 and len(result.chunks) == 1
    assert result.excluded == [{"file": str(path), "line": 1, "reason": "language_not_selected"}]
    assert [r["line"] for r in result.invalid] == [3, 4]
    assert result.invalid[-1]["reason"] == "duplicate_artifact_id" and result.invalid[-1]["first_line"] == 1
    assert result.chunks[0].lang == "en"
    assert (
        inspect_artifact(artifact(tmp_path, [record(lang="ja")]), CorpusPolicy("pilot", ("ja",))).chunks[0].lang == "ja"
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"embedding_text": "Ranni"},
        {"embedding_text": "passage: passage: Ranni"},
        {"embedding_text": "query: Ranni"},
        {"token_count": 513},
        {"token_count": True},
        {"url": "file:///private"},
        {"review_status": ["approved"]},
        {ADMISSION_KEY: "pilot-v1"},
        {"artifact_chunk_id": "overwrite-source"},
    ],
)
def test_invalid_contract_never_becomes_silent_policy_exclusion(tmp_path, extra):
    result = inspect_artifact(artifact(tmp_path, [record(**extra)]), PILOT)
    assert len(result.invalid) == 1 and not result.chunks and not result.excluded


def test_corrupt_json_blank_lines_duplicate_keys_and_encoding_report_locations(tmp_path):
    path = tmp_path / "broken.jsonl"
    path.write_bytes(b'{"chunk_id":"x","chunk_id":"y"}\n\n\xff\n[]\n')
    result = inspect_artifact(path, PILOT)
    assert [r["line"] for r in result.invalid] == [1, 2, 3, 4]
    assert all(r["file"] == str(path) for r in result.invalid)
    assert result.total == 4 and not result.chunks


def test_optional_local_tokenizer_checks_even_unselected_records(tmp_path):
    from tokenizers import Tokenizer, models, pre_tokenizers

    tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer_path = tmp_path / "tokenizer.json"
    tokenizer.save(str(tokenizer_path))
    row = record()
    actual = len(tokenizer.encode(row["embedding_text"]).ids)
    path = artifact(tmp_path, [{**row, "token_count": actual}, record(2, lang="ja", token_count=actual + 1)])
    result = inspect_artifact(path, PILOT, tokenizer_path=tokenizer_path)
    assert len(result.chunks) == 1 and result.invalid[0]["reason"] == "token_count_mismatch"
    assert result.tokenizer_sha256 == hashlib.sha256(tokenizer_path.read_bytes()).hexdigest()


def test_cli_dry_run_and_invalid_real_run_cannot_construct_clients(tmp_path, monkeypatch, capsys):
    from app.adapters.llm import DeepSeekLLM
    from core.encoders.onnx import FastEmbedEncoder
    from ingest.__main__ import main
    from ingest.crawl.http import HttpClient

    def forbidden(*_args, **_kwargs):
        pytest.fail("preflight constructed a model/client")

    for cls in (DeepSeekLLM, FastEmbedEncoder, AsyncQdrantClient, HttpClient):
        monkeypatch.setattr(cls, "__init__", forbidden)
    monkeypatch.setattr("ingest.indexing.get_settings", lambda: Settings(_env_file=None))
    path = artifact(tmp_path, [record(), record(2, lang="ja")])
    before = path.read_bytes()
    assert main(["index", "--input", str(path), "--policy", "pilot", "--languages", "en", "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["accepted"] == 1 and report["excluded_count"] == 1 and report["invalid_count"] == 0
    assert report["excluded_by_reason"] == {"language_not_selected": 1}
    assert path.read_bytes() == before
    path = artifact(tmp_path, [record(), record(2, text=" ")])
    assert main(["index", "--input", str(path)]) == 2  # invalid preflight stops even without --dry-run
    report = json.loads(capsys.readouterr().out)
    assert report["accepted"] == 1 and report["invalid"][0]["line"] == 2


@pytest.mark.parametrize("command", ["crawl", "survey", "report", "clean", "chunk"])
def test_existing_cli_commands_and_arguments_still_parse_without_network(command, tmp_path, monkeypatch, capsys):
    from ingest.__main__ import main

    monkeypatch.setattr("ingest.__main__.load_settings", lambda _: {"data_dir": tmp_path})
    assert (
        main(
            [
                command,
                "--dry-run",
                "--input-dir",
                str(tmp_path),
                "--output-dir",
                str(tmp_path / "out"),
                "--tokenizer",
                str(tmp_path / "local.json"),
                "--max-tokens",
                "450",
                "--overlap-tokens",
                "50",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["command"] == command


class SyntheticEncoder:
    async def encode(self, texts, *, query=False):
        return [Encoded([1.0] + [0.0] * 383, [1, 3], [1.0, 0.5]) for _ in texts]


async def test_pilot_index_retrieve_context_share_policy_ids_and_provenance():
    client = AsyncQdrantClient(location=":memory:")
    store = QdrantStore(client, "synthetic_pilot", PILOT)
    original = record(release_scope="sote_candidate")
    chunks = [ChunkRecord.model_validate(original), ChunkRecord.model_validate(record(2, spoiler_level=0))]
    try:
        await index_chunks(chunks, SyntheticEncoder(), store, 2)
        await index_chunks(chunks, SyntheticEncoder(), store, 1)
        assert (await client.count(store.collection, exact=True)).count == 2
        hits = await HybridRetriever(SyntheticEncoder(), store).retrieve("Ranni")
        assert len(hits) == 2
        assert len(select_context(hits, 5, 12000, policy=PILOT)) == 2
        retrieved = next(h for h in hits if h.id == str(chunks[0].point_uuid))
        assert retrieved.payload["chunk_id"] == original["chunk_id"]
        assert retrieved.payload["doc_id"] == original["doc_id"]
        assert retrieved.payload["release_scope"] == "sote_candidate"
        assert "review_status" not in retrieved.payload
        assert retrieved.payload["custom"] == original["custom"]
        assert document_to_hit(hit_to_document(retrieved)) == retrieved
        safe = await HybridRetriever(SyntheticEncoder(), store).retrieve("Ranni", spoilers=False)
        assert [h.id for h in safe] == [str(chunks[1].point_uuid)]
        assert len(select_context(hits, 5, 12000, policy=PILOT, spoilers=False)) == 1
        with pytest.raises(ValueError):
            await index_chunks([ChunkRecord.model_validate(record(3, lang="ja"))], SyntheticEncoder(), store, 1)
    finally:
        await client.close()


async def test_pilot_rrf_filters_all_branches_and_rechecks_payload_policy():
    from types import SimpleNamespace

    client = AsyncMock()
    client.query_points.return_value = SimpleNamespace(
        points=[
            SimpleNamespace(id="bad", score=1.0, payload=record(decision="excluded", **{ADMISSION_KEY: "pilot-v1"}))
        ]
    )
    store = QdrantStore(client, "existing", PILOT)
    assert await store.search(Encoded([0.0] * 384, [1], [1.0]), limit=30) == []
    query = client.query_points.call_args.kwargs
    assert query["query"].fusion.value == "rrf"
    for filters in [query["query_filter"], *[p.filter for p in query["prefetch"]]]:
        fields = {c.key: c for c in filters.must}
        assert fields["game_scope"].match.any == ["base", "elden_ring"]
        assert fields["lang"].match.any == ["en"]
        assert fields[ADMISSION_KEY].match.value == "pilot-v1"
        assert "review_status" not in fields


def test_direct_pipeline_rejects_policy_mismatch():
    store = QdrantStore(AsyncMock(), "existing")  # reviewed policy
    with pytest.raises(ValueError, match="same corpus policy"):
        ChatPipeline(Settings(_env_file=None, chat_mode="rag"), None, HybridRetriever(SyntheticEncoder(), store))


@pytest.mark.parametrize("fail", [False, True])
async def test_retrieval_diagnostic_is_read_only_and_closes_client(monkeypatch, fail):
    from core.errors import UnavailableError
    from scripts.check_retrieval import check_retrieval

    client = AsyncMock()
    monkeypatch.setattr("scripts.check_retrieval.AsyncQdrantClient", lambda **_: client)
    monkeypatch.setattr("scripts.check_retrieval.FastEmbedEncoder", lambda *_, **__: SyntheticEncoder())

    async def retrieve(self, query, *, spoilers):
        assert self.store.policy == PILOT and query == "Ranni" and spoilers
        if fail:
            raise UnavailableError("unavailable")
        return [Hit("point", 0.1, record())]

    monkeypatch.setattr(HybridRetriever, "retrieve", retrieve)
    if fail:
        with pytest.raises(UnavailableError):
            await check_retrieval(Settings(_env_file=None), "Ranni", limit=5, spoilers=True)
    else:
        result = await check_retrieval(Settings(_env_file=None), "Ranni", limit=5, spoilers=True)
        assert result["hits"][0]["point_id"] == "point"
        assert result["hits"][0]["release_scope"] == "unknown"
        assert result["hits"][0]["review_status"] is None
    client.close.assert_awaited_once()
    client.upsert.assert_not_called()
    client.create_collection.assert_not_called()


@pytest.mark.parametrize("threads", [0, -1, 33, True])
def test_encoder_thread_limits_are_explicit(threads, tmp_path):
    from core.encoders.onnx import FastEmbedEncoder

    with pytest.raises(ValueError, match="threads"):
        FastEmbedEncoder(tmp_path, threads=threads)


def test_live_acceptance_requires_opt_in_and_local_api(capsys):
    from scripts.run_live_acceptance import main

    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2 and "allow-paid" in capsys.readouterr().err
    with pytest.raises(SystemExit) as caught:
        main(["--allow-paid", "--api-url", "https://external.invalid"])
    assert caught.value.code == 2 and "local API" in capsys.readouterr().err
    with pytest.raises(SystemExit) as caught:
        main(["--allow-paid", "--api-url", "http://user:private@127.0.0.1:18000"])
    assert caught.value.code == 2 and "local API" in capsys.readouterr().err


def test_live_acceptance_does_not_call_http_200_or_sse_error_a_pass():
    from scripts.run_live_acceptance import acceptance_summary

    result = {
        "cases": [
            {
                "id": "EN05",
                "category": "missing_relationship",
                "http_status": 200,
                "response": {"grounded": True, "sources": [{"index": 1}]},
            }
        ],
        "sse_http_status": 200,
        "sse": {"done": None, "errors": [{"code": "upstream_error"}]},
    }
    summary = acceptance_summary(result)
    assert not summary["passed"] and "EN05:negative_grounding" in summary["failures"] and "sse" in summary["failures"]
