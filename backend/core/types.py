"""Contract online/indexing TV3; adapter giữ nguyên artifact TV2 và provenance.

Phụ trách: TV3 · [S2] Embedding/retrieval · [S3] Pipeline
"""

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    token_count: int = Field(gt=0, le=512, strict=True)

    @field_validator("chunk_id", "source", "source_id", "title", "text", "embedding_text", "lang", "source_type")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Required text must not be blank")
        return value

    @field_validator("embedding_text")
    @classmethod
    def passage_prefix(cls, value: str) -> str:
        from core.encoders.onnx import prefixed

        if not value.startswith("passage: ") or prefixed(value, query=False) != value:
            raise ValueError("embedding_text requires one passage: prefix")
        return value

    @model_validator(mode="after")
    def optional_metadata(self):
        import math

        extra = self.model_extra or {}
        for key in (
            "review_status",
            "scope_status",
            "scope_reason",
            "reason",
            "decision",
            "release_scope",
            "continuity",
        ):
            if extra.get(key) is not None and not isinstance(extra[key], str):
                raise ValueError(f"Invalid optional metadata: {key}")
        if extra.get("chunk_eligible") is not None and type(extra["chunk_eligible"]) is not bool:
            raise ValueError("chunk_eligible must be boolean")
        level = extra.get("spoiler_level")
        if level is not None and (type(level) not in (int, float) or not math.isfinite(level) or level < 0):
            raise ValueError("spoiler_level must be a nonnegative number or null")
        return self

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

        # Keep this existing mapping stable for both older hash IDs and newer TV1 UUID IDs.
        return uuid5(NAMESPACE, f"artifact-point-v1:{self.document_uuid}:{self.chunk_id}")

    def payload(self) -> dict[str, Any]:
        original = self.model_dump(mode="json")
        mapped = {
            "document_id": str(self.document_uuid),
            "artifact_chunk_id": self.chunk_id,
            "point_id_mapping": "artifact-point-v1",
        }
        if any(k in original and original[k] != v for k, v in mapped.items()):
            raise ValueError("Reserved ID metadata collision")
        return {**original, **mapped}


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
