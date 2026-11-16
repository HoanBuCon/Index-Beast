"""Dựng chunk cho một lô trang đổi bằng đúng pipeline production (crawl -> clean S3 -> chunk wiki-quality).

Lô được ghi thành một "run" nhỏ dưới data/update_runs/<id>/ có cùng hình dạng với crawl_runs, nên transform.full và
chunk.full chạy nguyên vẹn nhưng chỉ trên vài trang. Không có encoder, không ghi DB. Lỗi cả lô được tách ra từng trang
để một trang hỏng không làm mất các trang còn lại.

Phụ trách: TV2 · [S5] Cập nhật dữ liệu tăng dần
"""

import json
import uuid

from ingest.artifacts import now, save
from ingest.chunk.full import run as chunk_run
from ingest.crawl.http import CrawlError
from ingest.crawl.media import MediaStore
from ingest.transform.full import run as transform_run

PAGE_ERRORS = (CrawlError, ValueError, OSError, KeyError, RuntimeError)


def read_lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


class PipelineBuilder:
    def __init__(self, source, config, tokenizer, *, media=True):
        self.source, self.config, self.tokenizer, self.media = source, config, tokenizer, media

    def build(self, pages):
        """pages: dict describe() của MediaWiki. Trả (built, errors) theo source_id."""
        run_dir = self.config["data_dir"] / "update_runs" / ("update-" + uuid.uuid4().hex[:12])
        entries, errors = self.fetch(pages, run_dir)
        built = {}
        if entries:
            try:
                built = self.transform(entries, run_dir)
            except PAGE_ERRORS as exc:
                if len(entries) == 1:
                    errors[entries[0]["id"]] = f"{type(exc).__name__}: {exc}"
                else:  # tách lô để cô lập trang gây lỗi
                    for entry in entries:
                        sub = self.config["data_dir"] / "update_runs" / ("update-" + uuid.uuid4().hex[:12])
                        try:
                            built.update(self.transform([entry], sub))
                        except PAGE_ERRORS as inner:
                            errors[entry["id"]] = f"{type(inner).__name__}: {inner}"
        return built, errors

    def fetch(self, pages, run_dir):
        root = self.config["data_dir"]
        store = (
            MediaStore(self.source.client, self.config, manifest_root=run_dir / "media-working") if self.media else None
        )
        entries, errors = [], {}
        for page in pages:
            key = str(page["pageid"])
            try:
                raw = self.source.fetch(page)
                snapshot = root / "raw" / self.source.name / "snapshots" / key
                snapshot = snapshot / (str(raw["revision_id"]) + "-" + raw["content_hash"] + ".json")
                if not snapshot.exists():
                    save(snapshot, raw)
                if store:
                    manifest = store.page(self.source, raw)
                    if manifest["status"] != "completed":
                        raise ValueError("Media incomplete; retry this page")
                else:
                    manifest = {
                        "source_id": key,
                        "revision_id": raw["revision_id"],
                        "status": "completed",
                        "images": [],
                    }
                manifest_path = run_dir / "media" / (key + ".json")
                save(manifest_path, manifest)
                entries.append(
                    {
                        "id": key,
                        "title": raw["title"],
                        "revision_id": raw["revision_id"],
                        "path": snapshot.relative_to(root).as_posix(),
                        "media_manifest": manifest_path.relative_to(root).as_posix(),
                    }
                )
            except PAGE_ERRORS as exc:
                errors[key] = f"{type(exc).__name__}: {exc}"
        return entries, errors

    def transform(self, entries, run_dir):
        report = {"job_id": run_dir.name, "started_at": now(), "finished_at": now(), "status": "completed"}
        save(run_dir / "report.json", {**report, "pages": entries, "counts": {}, "errors": []})
        save(run_dir / "checkpoint.json", {})
        clean_dir, chunk_dir = run_dir / "clean", run_dir / "chunk"
        transform_run(run_dir, clean_dir, gameplay=True, structured_tables=True)
        chunk_run(clean_dir, self.tokenizer, chunk_dir, wiki_quality=True)
        built = {}
        for doc in read_lines(chunk_dir / "documents.jsonl"):
            rows = chunk_dir / "wikigg" / (doc["source_id"] + ".jsonl")
            chunks = read_lines(rows) if rows.exists() else []
            if any(c["doc_id"] != doc["doc_id"] for c in chunks):
                raise ValueError("Chunk/document identity mismatch")
            built[doc["source_id"]] = {"doc": doc, "chunks": chunks}
        if set(built) != {e["id"] for e in entries}:
            raise ValueError("Builder returned a different page set")
        return built


def tokenizer_path(models_dir):
    found = sorted(models_dir.glob("models--intfloat--multilingual-e5-small/snapshots/*/tokenizer.json"))
    if not found:
        raise ValueError("Không tìm thấy tokenizer E5 trong models; truyền --tokenizer")
    return found[-1]
