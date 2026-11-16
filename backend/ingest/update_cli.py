"""Nối `python -m ingest update` với thành phần thật: HttpClient, builder pipeline, Qdrant+FastEmbed, PostgreSQL.

Lock theo data dir chống hai lượt cập nhật chạy chồng (cron + chạy tay). Phần logic nằm ở ingest.update.

Phụ trách: TV2 · [S5] Cập nhật dữ liệu tăng dần
"""

import asyncio
import json
import sys
from contextlib import nullcontext

from ingest.chunk.full import WIKI_QUALITY_VERSION
from ingest.crawl.http import CrawlError
from ingest.transform.full import VERSION as CLEAN_VERSION
from ingest.update import (
    StateMissing,
    bootstrap_from_chunk_dir,
    bootstrap_from_documents,
    load_state,
    run_update,
    state_path,
)

PIPELINE_VERSION = f"{CLEAN_VERSION}+{WIKI_QUALITY_VERSION}"


def fail(message):
    print(json.dumps({"status": "failed", "error": message}, ensure_ascii=False), file=sys.stderr)
    return 2


def validate_target(state, target, *, dry_run):
    recorded = state.get("target")
    if recorded is None:
        if not dry_run:
            raise ValueError("State cũ chưa xác định đích; xác minh dữ liệu đang phục vụ rồi bootstrap lại")
    elif recorded != target:
        raise ValueError("Đích cập nhật khác state; kiểm tra PostgreSQL, Qdrant, collection và chính sách corpus")


async def run(args, config):
    from qdrant_client import AsyncQdrantClient

    from core.config import BACKEND_ROOT, get_settings
    from core.corpus import CorpusPolicy, parse_languages
    from core.db.session import create_engine, create_sessionmaker
    from core.encoders.onnx import FastEmbedEncoder
    from ingest.chunk.sync import PgDocuments
    from ingest.crawl.http import HttpClient
    from ingest.index.writer import QdrantIndex
    from ingest.jobs import DbJobLog
    from ingest.sources.wikigg import WikiGG
    from ingest.update_builder import PipelineBuilder, tokenizer_path

    settings = get_settings()
    path = state_path(config, args.source)
    policy = CorpusPolicy(
        args.policy or settings.rag_corpus_policy,
        parse_languages(args.languages) if args.languages else tuple(settings.rag_languages),
    )
    collection = args.collection or settings.rag_collection
    target = {
        "postgres": [settings.postgres_host, settings.postgres_port, settings.postgres_db],
        "qdrant": settings.qdrant_url,
        "collection": collection,
        "policy": policy.stamp,
        "languages": sorted(policy.languages),
    }
    engine = create_engine(settings)
    sessions = create_sessionmaker(engine)
    docs = PgDocuments(sessions, args.source)
    client = HttpClient(config)
    qdrant = None
    try:
        state = load_state(path)
        if state is None:
            if args.bootstrap_from:
                state = bootstrap_from_chunk_dir(args.bootstrap_from)
            elif args.bootstrap_from_db:
                state = bootstrap_from_documents(await docs.list_documents())
            else:
                raise StateMissing(
                    f"Chưa có state {path}: dùng --bootstrap-from <thư mục chunk> hoặc --bootstrap-from-db"
                )
            state["target"] = target
            print(json.dumps({"bootstrapped_pages": len(state["pages"]), "watermark": state["watermark"]}))
        elif args.bootstrap_from or args.bootstrap_from_db:
            raise ValueError("State đã tồn tại; xác minh đích và sao lưu state trước khi bootstrap lại")
        else:
            validate_target(state, target, dry_run=args.dry_run)
        source = WikiGG(client, config)
        builder = index = None
        if not args.dry_run:
            qdrant = AsyncQdrantClient(
                url=settings.qdrant_url,
                timeout=max(1, round(settings.client_timeout_seconds)),
                check_compatibility=False,
            )
            if not await qdrant.collection_exists(collection):
                raise ValueError("Collection Qdrant chưa tồn tại; nạp bản đầy đủ và xác minh trước khi update")
            encoder = FastEmbedEncoder(BACKEND_ROOT / settings.rag_models_dir, threads=settings.rag_encoder_threads)
            index = QdrantIndex(qdrant, collection, encoder, policy, settings.rag_batch_size)
            tokenizer = args.tokenizer or tokenizer_path(BACKEND_ROOT / settings.rag_models_dir)
            builder = PipelineBuilder(source, config, tokenizer, media=not args.no_media)
        return await run_update(
            source,
            config,
            builder=builder,
            index=index,
            docs=docs,
            jobs=DbJobLog(sessions),
            since=args.since,
            full_scan=args.full_scan,
            dry_run=args.dry_run,
            max_pages=args.max_pages,
            batch_pages=args.batch_pages,
            pipeline_version=PIPELINE_VERSION,
            state=state,
        )
    finally:
        client.close()
        if qdrant is not None:
            await qdrant.close()
        await engine.dispose()


def run_cli(args, config):
    from ingest.crawl.full import run_lock

    try:
        lock = nullcontext() if args.dry_run else run_lock(config["data_dir"] / "state")
        with lock:
            report = asyncio.run(run(args, config))
    except BlockingIOError:
        return fail("Một lượt cập nhật khác đang giữ lock")
    except (CrawlError, StateMissing, ValueError, OSError) as exc:
        return fail(str(exc))
    print(json.dumps({k: v for k, v in report.items() if k != "errors"}, ensure_ascii=False, indent=2))
    for error in report.get("errors", [])[:20]:
        print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
    return 0 if report["status"] in ("completed", "dry_run") else 2
