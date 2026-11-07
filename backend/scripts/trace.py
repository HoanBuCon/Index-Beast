"""Xem trace RAG của một câu trả lời từ PostgreSQL, không cần chạy API: python -m scripts.trace <message_id>

Chỉ đọc. Trace đã được che secret lúc lưu.

Phụ trách: TV1 · [S3] Trace từng bước RAG
"""

import argparse
import asyncio
import json
from uuid import UUID


async def show(message_id: UUID) -> int:
    from app.services.memory_repository import MemoryRepository
    from core.config import Settings
    from core.db.session import create_engine, create_sessionmaker

    engine = create_engine(Settings())
    try:
        found = await MemoryRepository(create_sessionmaker(engine)).trace(message_id)
    finally:
        await engine.dispose()
    if found is None:
        print("Không tìm thấy câu trả lời này trong PostgreSQL.")
        return 1
    print(json.dumps(found, ensure_ascii=False, indent=2, default=str))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message_id", type=UUID, help="message_id của câu trả lời (assistant)")
    return asyncio.run(show(parser.parse_args(argv).message_id))


if __name__ == "__main__":
    raise SystemExit(main())
