"""Ghi bảng ingestion_jobs (bắt đầu/kết thúc, thống kê, lỗi) cho lệnh `update`; report JSON do ingest.update ghi vào
data/reports/<job_id>.json.

DbJobLog là adapter mỏng trên core.db.repositories.start_job/finish_job; test dùng bản giả cùng giao diện
(start/finish async).

Phụ trách: TV2 · [S2] Crawl toàn bộ wiki.gg · [S5] Cập nhật dữ liệu tăng dần
"""

from core.db.models import IngestionJob
from core.db.repositories import finish_job, start_job


class DbJobLog:
    def __init__(self, sessions):
        self.sessions = sessions

    async def start(self, kind, source, external_id):
        async with self.sessions() as session, session.begin():
            return (await start_job(session, kind=kind, source=source, external_id=external_id)).id

    async def finish(self, handle, ok, failed, log):
        async with self.sessions() as session, session.begin():
            job = await session.get(IngestionJob, handle)
            await finish_job(session, job, pages_ok=ok, pages_failed=failed, log=log)
            # Lượt dở dang (max-pages) hoặc lỗi hạ tầng không có trang lỗi vẫn không được ghi succeeded.
            if log["status"] in ("partial", "failed"):
                job.status = "partial" if ok and log["status"] == "partial" else "failed"
