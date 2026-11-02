"""scripts/data_pipeline: chọn đúng bản chạy toàn bộ, đầu ra mới, chặn index đè collection.

Phụ trách: TV1 · [S3] Script pipeline dữ liệu
"""

import json
import os
from argparse import Namespace

import pytest

from scripts import data_pipeline as dp


def write_report(directory, **data):
    directory.mkdir(parents=True)
    (directory / "report.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "DATA", tmp_path)
    write_report(tmp_path / "crawl_runs" / dp.DEFAULT_CRAWL_RUN, pages=[{}, {}, {}], errors=[{}])
    return tmp_path


def test_latest_skips_sample_runs_and_picks_newest_full_run(data_dir):
    full_old = data_dir / "chunk_runs" / "old"
    sample = data_dir / "chunk_runs" / "sample-20"
    full_new = data_dir / "chunk_runs" / "new"
    write_report(full_old, chunking_version="s2-full-chunk-1.0", counts={"pages": 4})
    write_report(full_new, chunking_version="s2-full-chunk-1.0", counts={"pages": 4})
    write_report(sample, chunking_version="s2-full-chunk-1.0", counts={"pages": 2})
    os.utime(full_old / "report.json", (1, 1))
    os.utime(sample / "report.json", (9_999_999_999, 9_999_999_999))  # mới nhất nhưng chỉ là lượt thử

    assert dp.latest_chunk() == full_new


def test_latest_clean_requires_full_pipeline_version(data_dir):
    write_report(data_dir / "clean_runs" / "legacy", cleaning_version="s2-clean-2.0", counts={"pages_in": 4})
    write_report(data_dir / "clean_runs" / "full", cleaning_version="s2-full-clean-1.1", counts={"pages_in": 4})

    assert dp.latest_clean() == data_dir / "clean_runs" / "full"


def test_real_index_requires_explicit_collection(data_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(dp, "run", lambda *args: calls.append(args))
    source = data_dir / "chunk_runs" / "c"
    source.mkdir(parents=True)
    args = Namespace(input=source, dry_run=False, collection=None, policy="pilot", languages="en")

    with pytest.raises(SystemExit, match="--collection"):
        dp.index(args)
    assert calls == []

    dp.index(Namespace(**{**vars(args), "dry_run": True}))
    assert calls and "--dry-run" in calls[0]


def test_clean_and_chunk_default_to_new_stamped_directories(data_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(dp, "run", lambda *args: calls.append(args))
    monkeypatch.setattr(dp, "tokenizer", lambda: data_dir / "tokenizer.json")
    args = Namespace(input=None, output=None, tokenizer=None)

    cleaned = dp.clean(args)
    (cleaned).mkdir(parents=True)
    chunked = dp.chunk(args, cleaned)

    assert cleaned.parent == data_dir / "clean_runs" and cleaned.name.startswith("clean-")
    assert chunked.parent == data_dir / "chunk_runs" and chunked.name.startswith("chunk-")
    assert [c[0] for c in calls] == ["ingest.transform.full", "ingest.chunk.full"]
