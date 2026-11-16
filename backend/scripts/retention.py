"""NFR-PRIV-01: xóa dữ liệu quá N ngày (mặc định 90): hội thoại kèm tin nhắn, feedback, ký ức, trace và điểm Qdrant;
phiên đăng nhập hết hạn. Chỉ in số đếm, không in nội dung hay mã định danh.

    python -m scripts.retention --days 90 --dry-run     # chỉ đếm
    python -m scripts.retention --days 90               # xóa thật
    python -m scripts.retention --days 90 --no-vectors  # bỏ qua Qdrant (chỉ khi Qdrant tắt)

Cron mẫu: docs/privacy.md. Dùng DATABASE_URL, QDRANT_* và CHAT_MEMORY_COLLECTION như backend (không thêm cấu hình).

Phụ trách: TV1 · [S5] Quyền riêng tư và xóa tài khoản
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from app.services.privacy import Counts, apply_retention

DEFAULT_DAYS = 90


def format_counts(counts: Counts, *, dry_run: bool) -> str:
    verb = "would delete" if dry_run else "deleted"
    return (
        f"{verb}: conversations={counts.conversations} messages={counts.messages} "
        f"feedback={counts.feedback} expired_sessions={counts.sessions}"
    )


async def run(
    sessionmaker, qdrant, collection: str, *, days: int, dry_run: bool, now: datetime | None = None
) -> Counts:
    now = now or datetime.now(UTC)
    return await apply_retention(
        sessionmaker, qdrant, collection, cutoff=now - timedelta(days=days), now=now, dry_run=dry_run
    )


async def amain(args) -> None:
    from qdrant_client import AsyncQdrantClient

    from core.config import Settings
    from core.db.session import create_engine, create_sessionmaker

    settings = Settings()
    engine = create_engine(settings)
    client = (
        None if args.no_vectors else AsyncQdrantClient(url=settings.qdrant_url, timeout=settings.client_timeout_seconds)
    )
    try:
        counts = await run(
            create_sessionmaker(engine), client, settings.chat_memory_collection, days=args.days, dry_run=args.dry_run
        )
        print(format_counts(counts, dry_run=args.dry_run))
    finally:
        await engine.dispose()
        if client is not None:
            await client.close()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--dry-run", action="store_true", help="chỉ đếm, không xóa")
    parser.add_argument("--no-vectors", action="store_true", help="không xóa điểm ký ức trong Qdrant")
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("--days phải >= 1")
    asyncio.run(amain(args))


if __name__ == "__main__":
    main()
