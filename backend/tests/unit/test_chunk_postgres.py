from copy import deepcopy

import pytest

from core.ids import chunk_id, document_id
from ingest.artifacts import sha256
from ingest.chunk.postgres import validate


def record():
    identity = document_id("wikigg", "1")
    return {
        "doc_id": str(identity),
        "source": "wikigg",
        "source_id": "1",
        "revision_id": 4,
        "source_snapshot": "raw.json",
        "ordinal": 0,
        "chunk_id": str(chunk_id(identity, 0)),
        "game_scope": "base",
        "source_type": "wiki_prose",
        "lang": "en",
        "token_count": 10,
        "text": "Lore",
        "text_hash": sha256(b"Lore"),
        "embedding_text": "passage: Title\nLore",
    }


def test_core_identity_and_explicit_metadata():
    assert validate([record()]) == document_id("wikigg", "1")


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_type", "unknown"),
        ("lang", "unknown"),
        ("game_scope", "dlc"),
        ("token_count", 451),
        ("ordinal", 1),
        ("text", "Changed"),
        ("doc_id", "wrong"),
    ],
)
def test_unsafe_document_is_quarantined(field, value):
    row = deepcopy(record())
    row[field] = value
    with pytest.raises(ValueError):
        validate([row])
