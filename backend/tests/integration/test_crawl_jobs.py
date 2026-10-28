"""TV2 crawl job lifecycle uses TV1 repository contracts."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from core.db.models import IngestionJob
from core.db.session import create_sessionmaker
from ingest.crawl import full
from tests.integration.test_db_schema import db_url as db_url

pytestmark = pytest.mark.integration


async def test_crawl_job_records_partial_and_interrupted_runs(db_url, monkeypatch):
    monkeypatch.setattr(full, "create_engine", lambda _: create_async_engine(db_url))
    job_id = await full.job_event("test-crawl-partial")
    await full.job_event(job_id, {"status": "partial", "counts": {"successful": 3, "failed": 1}})
    interrupted_id = await full.job_event("test-crawl-interrupted")
    await full.job_event(interrupted_id, {"status": "failed", "counts": {}})
    engine = create_async_engine(db_url)
    try:
        async with create_sessionmaker(engine)() as session:
            jobs = (await session.execute(select(IngestionJob).order_by(IngestionJob.external_id))).scalars().all()
            assert len(jobs) == 2
            by_id = {j.id: j for j in jobs}
            assert (by_id[job_id].status, by_id[job_id].pages_ok, by_id[job_id].pages_failed) == ("partial", 3, 1)
            assert by_id[interrupted_id].status == "failed"
            assert all(j.finished_at is not None for j in jobs)
    finally:
        await engine.dispose()
