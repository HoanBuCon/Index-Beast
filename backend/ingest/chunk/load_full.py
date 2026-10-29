"""Validate complete S2 artifacts, then atomically load each document into PostgreSQL."""

import argparse
import asyncio
import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from core.config import Settings
from core.db.models import Chunk, IngestionJob
from core.db.repositories import finish_job, replace_chunks, start_job, upsert_document
from core.db.session import create_engine, create_sessionmaker
from core.ids import chunk_id, document_id
from ingest.artifacts import read, save, sha256


def read_lines(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def validate_document(doc, rows, cap):
    identity = document_id(doc["source"], doc["source_id"])
    if str(identity) != doc["doc_id"] or doc["game_scope"] != "elden_ring":
        raise ValueError("Document scope/identity mismatch")
    for i, c in enumerate(rows):
        if c["ordinal"] != i or c["chunk_id"] != str(chunk_id(identity, i)):
            raise ValueError("Chunk identity mismatch")
        for key in ["doc_id", "source_id", "source", "revision_id", "source_snapshot", "game_scope"]:
            if c[key] != doc[key]:
                raise ValueError("Chunk provenance mismatch")
        if c["source_type"] not in {"in_game_text", "wiki_prose", "speculation"}:
            raise ValueError("Unresolved source type")
        if not re.fullmatch(r"[a-z]{2,3}|unknown", c["lang"]):
            raise ValueError("Invalid language metadata")
        if not 0 < c["token_count"] <= cap or not c["embedding_text"]:
            raise ValueError("Invalid token budget")
        if sha256(c["text"].encode()) != c["text_hash"]:
            raise ValueError("Text hash mismatch")
    return identity


def preflight(directory):
    report = read(directory / "report.json")
    if report.get("chunking_version") != "s2-full-chunk-1.0":
        raise ValueError("Full S2 artifact required")
    for name, digest in report["artifact_sha256"].items():
        if sha256((directory / name).read_bytes()) != digest:
            raise ValueError("Artifact checksum mismatch")
    digest = hashlib.sha256()
    ids = set()
    n = 0
    for doc in read_lines(directory / "documents.jsonl"):
        if not doc["source_id"].isdigit() or doc["doc_id"] in ids:
            raise ValueError("Duplicate/invalid source identity")
        ids.add(doc["doc_id"])
        payload = (directory / "wikigg" / (doc["source_id"] + ".jsonl")).read_bytes()
        digest.update(payload)
        rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line]
        validate_document(doc, rows, report["max_tokens"])
        n += len(rows)
        raw = read(Path(doc["source_snapshot"]))
        if (
            raw["source"] != doc["source"]
            or raw["source_id"] != doc["source_id"]
            or raw["revision_id"] != doc["revision_id"]
            or raw["content_hash"] != doc["raw_content_hash"]
            or sha256(raw["content"].encode()) != raw["content_hash"]
        ):
            raise ValueError("Raw provenance mismatch")
    if (
        digest.hexdigest() != report["artifact_sha256"]["chunks.jsonl"]
        or n != report["counts"]["chunks"]
        or len(ids) != report["counts"]["pages"]
    ):
        raise ValueError("Per-document/global artifact mismatch")
    return report


async def load(directory, *, validate_only=False):
    report = preflight(directory)
    if validate_only:
        return {
            "validated_documents": report["counts"]["pages"],
            "validated_chunks": report["counts"]["chunks"],
            "database_writes": 0,
        }
    engine = create_engine(Settings())
    sessions = create_sessionmaker(engine)
    ok, failed, unchanged, count = 0, 0, 0, 0
    errors = []
    job_id = None
    try:
        async with sessions() as session, session.begin():
            job = await start_job(
                session, kind="load_full_chunks", source="wikigg", external_id="load-full-" + uuid.uuid4().hex
            )
            job_id = job.id
        for doc in read_lines(directory / "documents.jsonl"):
            try:
                rows = list(read_lines(directory / "wikigg" / (doc["source_id"] + ".jsonl")))
                identity = validate_document(doc, rows, report["max_tokens"])
                fields = [
                    {
                        "id": chunk_id(identity, c["ordinal"]),
                        "ordinal": c["ordinal"],
                        "section": c["section"],
                        "text": c["embedding_text"],
                        "token_count": c["token_count"],
                        "game_scope": "elden_ring",
                        "source_type": c["source_type"],
                        "lang": c["lang"],
                    }
                    for c in rows
                ]
                async with sessions() as session, session.begin():
                    old = (
                        (
                            await session.execute(
                                select(Chunk).where(Chunk.document_id == identity).order_by(Chunk.ordinal)
                            )
                        )
                        .scalars()
                        .all()
                    )
                    same = len(old) == len(fields) and all(
                        all(getattr(o, k) == v for k, v in f.items()) for o, f in zip(old, fields, strict=True)
                    )
                    await upsert_document(
                        session,
                        source=doc["source"],
                        source_id=doc["source_id"],
                        title=doc["title"],
                        url=doc["url"],
                        revision_id=doc["revision_id"],
                        raw_hash=doc["raw_content_hash"],
                        fetched_at=datetime.fromisoformat(doc["fetched_at"]),
                        game_scope="elden_ring",
                        status="active",
                    )
                    if not same:
                        await replace_chunks(session, identity, fields)
                ok += 1
                count += len(fields)
                unchanged += same
                if ok % 100 == 0:
                    print(f"PG {ok}/{report['counts']['pages']}", flush=True)
            except Exception as exc:
                failed += 1
                errors.append({"source_id": doc["source_id"], "error": type(exc).__name__})
        async with sessions() as session, session.begin():
            job = await session.get(IngestionJob, job_id)
            await finish_job(
                session,
                job,
                pages_ok=ok,
                pages_failed=failed,
                log={"errors": errors, "chunks": count, "unchanged_documents": unchanged},
            )
    except BaseException as exc:
        if job_id:
            async with sessions() as session, session.begin():
                job = await session.get(IngestionJob, job_id)
                await finish_job(session, job, pages_ok=ok, pages_failed=failed + 1, log={"fatal": type(exc).__name__})
        raise
    finally:
        await engine.dispose()
    result = {
        "job_id": str(job_id),
        "documents_ok": ok,
        "documents_failed": failed,
        "chunks": count,
        "unchanged_documents": unchanged,
        "errors": errors,
    }
    save(directory / "postgres-report.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input_dir", type=Path)
    p.add_argument("--validate-only", action="store_true")
    a = p.parse_args()
    result = asyncio.run(load(a.input_dir, validate_only=a.validate_only))
    print(json.dumps(result))
    return 2 if result.get("documents_failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
