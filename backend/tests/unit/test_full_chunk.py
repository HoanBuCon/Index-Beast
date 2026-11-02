from tokenizers import Tokenizer, models, pre_tokenizers

from core.ids import document_id
from ingest.chunk.full import build_chunks


def fixture():
    doc = {
        "doc_id": str(document_id("wikigg", "1")),
        "source": "wikigg",
        "source_id": "1",
        "title": "SotE item",
        "url": "https://example.org/1",
        "revision_id": 1,
        "source_snapshot": "raw.json",
        "game_scope": "elden_ring",
        "fetched_at": "2026-10-29T00:00:00Z",
        "cleaning_version": "s2-full-clean-1.0",
    }
    text = "影 " * 1000
    section = {
        "section": "Description",
        "record_id": "s1",
        "lang": "ja",
        "source_type": "in_game_text",
        "release_scope": "sote_candidate",
        "image_ids": [],
        "anchor": "Description",
        "chunk_eligible": True,
        "text": text,
        "blocks": [{"kind": "prose", "text": text, "location": "dom:1", "notes": []}],
    }
    doc["sections"] = [section]
    tok = Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    return doc, tok


def test_full_chunk_includes_sote_and_preserves_exact_coverage():
    doc, tok = fixture()
    rows, review, coverage = build_chunks(doc, tok)
    assert len(rows) > 1 and not review
    assert all(r["game_scope"] == "elden_ring" and r["release_scope"] == "sote_candidate" for r in rows)
    assert all(r["token_count"] <= 450 and r["lang"] == "ja" for r in rows)
    assert rows[0]["start_char"] == 0 and rows[-1]["end_char"] == len(doc["sections"][0]["text"])
    assert all(b["start_char"] <= a["end_char"] for a, b in zip(rows, rows[1:], strict=False))
    assert coverage[0]["status"] == "covered"
    assert build_chunks(doc, tok)[0] == rows


def test_review_section_does_not_leak_into_chunks():
    doc, tok = fixture()
    doc["sections"][0].update(chunk_eligible=False, reason="unclassified_structure")
    rows, review, coverage = build_chunks(doc, tok)
    assert not rows and not coverage
    assert review[0]["reason"] == "unclassified_structure"
