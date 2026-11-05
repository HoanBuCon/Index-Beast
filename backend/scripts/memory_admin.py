"""Operator-only memory setup/reindex. Plan-only unless --apply; no corpus writes."""

import argparse
import asyncio
from uuid import UUID


async def apply(args):
    from qdrant_client import AsyncQdrantClient

    from app.rag.semantic_memory import MemoryScope, MemoryVectors, SemanticMemory
    from app.services.memory_repository import MemoryRepository
    from core.config import REPO_ROOT, Settings
    from core.db.models import Conversation
    from core.db.session import create_engine, create_sessionmaker
    from core.encoders.onnx import FastEmbedEncoder

    settings = Settings()
    client = AsyncQdrantClient(url=settings.qdrant_url, timeout=settings.client_timeout_seconds)
    engine = create_engine(settings)
    try:
        vectors = MemoryVectors(client, settings.chat_memory_collection, settings.rag_collection)
        if args.command == "setup":
            await vectors.setup()
            print("Memory collection schema ready; corpus untouched")
            return
        if not args.conversation:
            raise ValueError("sync/rebuild require --conversation UUID")
        repository = MemoryRepository(create_sessionmaker(engine))
        async with repository.sessions() as session:
            conversation = await session.get(Conversation, args.conversation)
            if conversation is None or not conversation.client_user_ref:
                raise ValueError("Durable conversation not found")
            scope = MemoryScope(conversation.id, conversation.client_user_ref)
        if args.command == "rebuild":
            await repository.rebuild(scope.conversation_id)
        memory = SemanticMemory(
            repository,
            vectors,
            FastEmbedEncoder(REPO_ROOT / "backend" / settings.rag_models_dir, threads=settings.rag_encoder_threads),
            settings,
        )
        print(await memory.sync(scope))
        print("One bounded batch; repeat sync if pending rows remain")
    finally:
        await engine.dispose()
        await client.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup", "sync", "rebuild"])
    parser.add_argument("--conversation", type=UUID)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true")
    group.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.apply:
        print(f"PLAN ONLY: {args.command}; no client, embedding or write. Use --apply to execute.")
        return
    asyncio.run(apply(args))


if __name__ == "__main__":
    main()
