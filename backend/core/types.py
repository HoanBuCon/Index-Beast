"""Contract online/indexing TV3; adapter giữ nguyên artifact TV2 và provenance.

Phụ trách: TV3 · [S2] Embedding/retrieval · [S3] Pipeline
"""

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.ids import NAMESPACE, document_id


class ChunkRecord(BaseModel):
    """TV2 s2-chunk JSONL. Extra metadata được giữ trong payload, không sửa artifact."""

    model_config = ConfigDict(extra="allow")
    chunk_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    section: str
    text: str = Field(min_length=1)
    embedding_text: str = Field(min_length=1)
    url: str
    game_scope: str | None
    source_type: str
    lang: str
    token_count: int = Field(gt=0, le=512)

    @field_validator("source_id", mode="before")
    @classmethod
    def string_id(cls, value: object) -> str:
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ValueError("source_id must be a string or integer")
        return str(value)

    @field_validator("url")
    @classmethod
    def source_url(cls, value: str) -> str:
        from urllib.parse import urlsplit

        if urlsplit(value).scheme not in ("http", "https") or not urlsplit(value).netloc:
            raise ValueError("source URL must be HTTP(S)")
        return value

    @property
    def document_uuid(self) -> UUID:
        return document_id(self.source, self.source_id)

    @property
    def point_uuid(self) -> UUID:
        from uuid import uuid5

        # Artifact IDs are content/span hashes, NOT TV1's ordinal-based DB chunk UUID.
        return uuid5(NAMESPACE, f"artifact-point-v1:{self.document_uuid}:{self.chunk_id}")

    def payload(self) -> dict[str, Any]:
        return {
            **self.model_dump(mode="json"),
            "document_id": str(self.document_uuid),
            "artifact_chunk_id": self.chunk_id,
            "point_id_mapping": "artifact-point-v1",
        }


@dataclass(frozen=True)
class Encoded:
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]


class Encoder(Protocol):
    async def encode(self, texts: list[str], *, query: bool = False) -> list[Encoded]: ...


@dataclass(frozen=True)
class Hit:
    id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


class Retriever(Protocol):
    async def retrieve(self, query: str, *, spoilers: bool = True) -> list[Hit]: ...
