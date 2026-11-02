"""Read-only preflight and explicit indexing. No client/model is created by validation."""

import asyncio
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from core.config import REPO_ROOT, get_settings
from core.corpus import ADMISSION_KEY, CorpusPolicy
from core.types import ChunkRecord, Encoder
from core.vector.schema import ensure_collection
from core.vector.store import QdrantStore


def rejection_reason(chunk: ChunkRecord) -> str | None:
    """Compatibility entry point: old low-level callers retain reviewed-only admission."""
    return CorpusPolicy().exclusion_reason(chunk.model_dump())


@dataclass
class Inspection:
    chunks: list[ChunkRecord] = field(default_factory=list)
    invalid: list[dict] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)
    languages: Counter = field(default_factory=Counter)
    releases: Counter = field(default_factory=Counter)
    total: int = 0
    sha256: str = ""
    tokenizer_sha256: str | None = None

    def report(self, path: Path, policy: CorpusPolicy, *, details: bool = False) -> dict:
        return {
            "input": str(path.resolve()),
            "input_sha256": self.sha256,
            "policy": policy.mode,
            "admission_stamp": policy.stamp,
            "selected_languages": list(policy.languages),
            "total": self.total,
            "accepted": len(self.chunks),
            "invalid_count": len(self.invalid),
            "excluded_count": len(self.excluded),
            "excluded_by_reason": dict(Counter(r["reason"] for r in self.excluded)),
            "invalid": self.invalid,
            "excluded" if details else "excluded_examples": self.excluded if details else self.excluded[:10],
            "languages_in_input": dict(self.languages),
            "releases_in_input": dict(self.releases),
            "token_check": "local_tokenizer" if self.tokenizer_sha256 else "declared_bounds_only",
            "tokenizer_sha256": self.tokenizer_sha256,
        }


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON key")
        obj[key] = value
    return obj


def reject_constant(value):
    raise ValueError("Non-finite JSON number")


def inspect_artifact(path: Path, policy: CorpusPolicy, *, tokenizer_path: Path | None = None) -> Inspection:
    result = Inspection()
    tokenizer = None
    if tokenizer_path is not None:
        from tokenizers import Tokenizer

        # An explicit local file only; never HuggingFace/FastEmbed model loading.
        result.tokenizer_sha256 = hashlib.sha256(tokenizer_path.read_bytes()).hexdigest()
        try:
            tokenizer = Tokenizer.from_file(str(tokenizer_path))
            tokenizer.no_truncation()
            tokenizer.no_padding()
        except Exception:
            raise ValueError(f"Invalid local tokenizer: {tokenizer_path}") from None
    identities, points = {}, {}
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for line_number, raw in enumerate(stream, 1):
            result.total += 1
            digest.update(raw)
            location = {"file": str(path), "line": line_number}
            try:
                data = json.loads(
                    raw.decode("utf-8-sig" if line_number == 1 else "utf-8"),
                    object_pairs_hook=unique_object,
                    parse_constant=reject_constant,
                )
                if not isinstance(data, dict):
                    raise ValueError("Record must be an object")
                chunk = ChunkRecord.model_validate(data)
                payload = chunk.payload()
                if ADMISSION_KEY in data:
                    raise ValueError("Reserved admission metadata collision")
                point = str(chunk.point_uuid)
                previous = identities.get(chunk.chunk_id) or points.get(point)
                if previous:
                    result.invalid.append({**location, "reason": "duplicate_artifact_id", "first_line": previous})
                    continue
                # Track IDs even for records not selected by language/policy.
                identities[chunk.chunk_id], points[point] = line_number, line_number
                if tokenizer is not None:
                    actual = len(tokenizer.encode(chunk.embedding_text).ids)
                    if actual > 512 or actual != chunk.token_count:
                        result.invalid.append({**location, "reason": "token_count_mismatch", "actual": actual})
                        continue
                result.languages[chunk.lang] += 1
                result.releases[str(data.get("release_scope", "<missing>"))] += 1
                reason = policy.exclusion_reason(payload)
                if reason:
                    result.excluded.append({**location, "reason": reason})
                else:
                    result.chunks.append(chunk)
            except ValidationError as exc:
                result.invalid.append(
                    {
                        **location,
                        "reason": "invalid_chunk_contract",
                        "problems": [
                            {
                                "field": ".".join(map(str, e["loc"])) or "<record>",
                                "type": e["type"],
                                "message": e["msg"],
                            }
                            for e in exc.errors()
                        ],
                    }
                )
            except (ValueError, TypeError, RecursionError):
                result.invalid.append({**location, "reason": "invalid_json_or_metadata"})
    result.sha256 = digest.hexdigest()
    return result


def load_chunks(path: Path) -> tuple[list[ChunkRecord], list[dict]]:
    result = inspect_artifact(path, CorpusPolicy())
    return result.chunks, result.invalid + result.excluded


async def index_chunks(chunks: list[ChunkRecord], encoder: Encoder, store: QdrantStore, batch_size: int) -> int:
    if not chunks or batch_size < 1:
        raise ValueError("No selected chunks or invalid batch size")
    for chunk in chunks:
        store.policy.index_payload(chunk.payload())
    if len({c.point_uuid for c in chunks}) != len(chunks) or len({c.chunk_id for c in chunks}) != len(chunks):
        raise ValueError("Input contains duplicate artifact IDs")
    await ensure_collection(store.client, store.collection, create=True)
    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset : offset + batch_size]
        vectors = await encoder.encode([c.embedding_text for c in batch])
        await store.upsert(batch, vectors)
    return len(chunks)


def run_cli(
    path: Path,
    *,
    dry_run: bool,
    policy: str | None = None,
    languages: str | None = None,
    collection: str | None = None,
    tokenizer_path: Path | None = None,
    details: bool = False,
) -> int:
    from core.corpus import parse_languages

    settings = get_settings()
    admission = CorpusPolicy(
        policy or settings.rag_corpus_policy,
        parse_languages(languages) if languages is not None else tuple(settings.rag_languages),
    )
    target = collection or settings.rag_collection
    try:
        result = inspect_artifact(path, admission, tokenizer_path=tokenizer_path)
    except (OSError, ValueError) as exc:
        print(json.dumps({"input": str(path), "error": str(exc), "dry_run": dry_run}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {**result.report(path, admission, details=details), "collection": target, "dry_run": dry_run},
            ensure_ascii=False,
            indent=2,
        )
    )
    if result.invalid or not result.chunks:
        return 2
    if dry_run:
        return 0

    async def run():
        from qdrant_client import AsyncQdrantClient

        from core.encoders.onnx import FastEmbedEncoder

        client = AsyncQdrantClient(
            url=settings.qdrant_url, timeout=max(1, round(settings.client_timeout_seconds)), check_compatibility=False
        )
        try:
            count = await index_chunks(
                result.chunks,
                FastEmbedEncoder(REPO_ROOT / "backend" / settings.rag_models_dir, threads=settings.rag_encoder_threads),
                QdrantStore(client, target, admission),
                settings.rag_batch_size,
            )
            print(json.dumps({"indexed": count, "collection": target}))
        finally:
            await client.close()

    asyncio.run(run())
    return 0
