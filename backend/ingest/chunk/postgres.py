"""Validated chunk artifact -> PostgreSQL. No embedding or vector writes."""

import argparse
import asyncio
import json
from datetime import datetime
from itertools import groupby
from pathlib import Path

from sqlalchemy import select

from core.config import Settings
from core.db.models import Chunk
from core.db.repositories import finish_job, replace_chunks, start_job, upsert_document
from core.db.session import create_engine, create_sessionmaker
from core.ids import chunk_id, document_id
from ingest.artifacts import read, save, sha256


def documents(path):
    with path.open(encoding="utf-8") as stream:
        rows = (json.loads(line) for line in stream if line.strip())
        seen = set()
        for key, group in groupby(rows, key=lambda row: row["doc_id"]):
            if key in seen:
                raise ValueError("Document chunks must be contiguous")
            seen.add(key)
            yield list(group)


def validate(rows):
    first = rows[0]
    identity = document_id(first["source"], first["source_id"])
    if str(identity) != first["doc_id"]:
        raise ValueError("Document ID does not follow core.ids")
    for ordinal, row in enumerate(rows):
        if any(row[k] != first[k] for k in ("doc_id", "source", "source_id", "revision_id", "source_snapshot")):
            raise ValueError("Inconsistent document provenance")
        if row["ordinal"] != ordinal or row["chunk_id"] != str(chunk_id(identity, ordinal)):
            raise ValueError("Chunk identity/ordinal mismatch")
        if row["game_scope"] != "base" or not 0 < row["token_count"] <= 450:
            raise ValueError("Invalid scope/token budget")
        if row["source_type"] not in {"in_game_text", "wiki_prose", "speculation"}:
            raise ValueError("Unresolved source_type")
        if row["lang"] not in {"en", "ja", "vi"}:
            raise ValueError("Unresolved language")
        if not row["embedding_text"] or sha256(row["text"].encode()) != row["text_hash"]:
            raise ValueError("Invalid content hash")
    return identity


async def load(directory, *, validate_only=False):
    report = read(directory / "report.json")
    for name, digest in report["artifact_sha256"].items():
        if sha256((directory / name).read_bytes()) != digest:
            raise ValueError("Artifact checksum mismatch")
    # Validate the entire file before any document is replaced.
    accepted, review = [], []
    for rows in documents(directory / "chunks.jsonl"):
        try:
            validate(rows)
            raw = read(Path(rows[0]["source_snapshot"]))
            if (
                raw["revision_id"] != rows[0]["revision_id"]
                or str(raw["source_id"]) != rows[0]["source_id"]
                or raw["source"] != rows[0]["source"]
                or sha256(raw["content"].encode()) != raw["content_hash"]
            ):
                raise ValueError("Raw provenance mismatch")
            accepted.append(rows[0]["doc_id"])
        except (ValueError, OSError, KeyError) as exc:
            review.append({"doc_id": rows[0]["doc_id"], "reason": str(exc)})
    if validate_only:
        result = {
            "accepted_documents": len(accepted),
            "pages_failed": len(review),
            "review": review,
            "database_writes": 0,
        }
        save(directory / "postgres-validation.json", result)
        return result
    engine = create_engine(Settings())
    sessions = create_sessionmaker(engine)
    ok, failed = 0, len(review)
    try:
        async with sessions() as session, session.begin():
            job = await start_job(session, kind="load_chunks", source="wikigg")
            job_id = job.id
        for rows in documents(directory / "chunks.jsonl"):
            if rows[0]["doc_id"] not in accepted:
                continue
            identity = validate(rows)
            first = rows[0]
            raw = read(Path(first["source_snapshot"]))
            if raw["revision_id"] != first["revision_id"] or sha256(raw["content"].encode()) != raw["content_hash"]:
                raise ValueError("Raw provenance mismatch")
            fields = [
                {
                    "id": chunk_id(identity, r["ordinal"]),
                    "ordinal": r["ordinal"],
                    "section": r["section"],
                    "text": r["embedding_text"],
                    "token_count": r["token_count"],
                    "game_scope": "base",
                    "source_type": r["source_type"],
                    "lang": r["lang"],
                }
                for r in rows
            ]
            try:
                async with sessions() as session, session.begin():
                    existing = (
                        (
                            await session.execute(
                                select(Chunk).where(Chunk.document_id == identity).order_by(Chunk.ordinal)
                            )
                        )
                        .scalars()
                        .all()
                    )
                    unchanged = len(existing) == len(fields) and all(
                        all(getattr(old, k) == value for k, value in new.items())
                        for old, new in zip(existing, fields, strict=True)
                    )
                    await upsert_document(
                        session,
                        source=first["source"],
                        source_id=first["source_id"],
                        title=first["title"],
                        url=raw["url"],
                        revision_id=first["revision_id"],
                        raw_hash=raw["content_hash"],
                        fetched_at=datetime.fromisoformat(first["fetched_at"]),
                        game_scope=None,
                        status="active",
                    )
                    if not unchanged:
                        await replace_chunks(session, identity, fields)
                ok += 1
            except Exception as exc:
                failed += 1
                review.append({"doc_id": str(identity), "reason": type(exc).__name__})
        async with sessions() as session, session.begin():
            from core.db.models import IngestionJob

            job = await session.get(IngestionJob, job_id)
            await finish_job(session, job, pages_ok=ok, pages_failed=failed, log={"review": review})
    except BaseException as exc:
        if "job_id" in locals():
            async with sessions() as session, session.begin():
                from core.db.models import IngestionJob

                job = await session.get(IngestionJob, job_id)
                await finish_job(
                    session,
                    job,
                    pages_ok=ok,
                    pages_failed=failed + 1,
                    log={"review": review, "fatal_error": type(exc).__name__},
                )
        raise
    finally:
        await engine.dispose()
    result = {"pages_ok": ok, "pages_failed": failed, "review": review}
    save(directory / "postgres-report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(load(args.input_dir, validate_only=args.validate_only))
    print(json.dumps({k: v for k, v in result.items() if k != "review"}, ensure_ascii=False))
    return 2 if result["pages_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
