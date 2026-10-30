"""TV2 crawl job lifecycle uses TV1 repository contracts."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from core.db.models import IngestionJob
from core.db.session import create_sessionmaker
from ingest.artifacts import read, save
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


async def test_recover_orphan_preserves_history_and_closes_job(db_url, monkeypatch, tmp_path):
    monkeypatch.setattr(full, "create_engine", lambda _: create_async_engine(db_url))
    identity = "test-orphan-recovery"
    job_id = await full.job_event(identity)
    original = {"job_id": identity, "status": "running", "counts": {"successful": 7, "failed": 2}}
    save(tmp_path / "report.json", original)
    await full.recover_job(tmp_path)
    assert read(tmp_path / "history" / (identity + ".json")) == original
    assert read(tmp_path / "report.json") == original
    engine = create_async_engine(db_url)
    try:
        async with create_sessionmaker(engine)() as session:
            job = await session.get(IngestionJob, job_id)
            assert (job.status, job.pages_ok, job.pages_failed) == ("partial", 7, 2)
            assert job.log["status"] == "interrupted"
            assert "termination_observed_at" in job.log
    finally:
        await engine.dispose()
