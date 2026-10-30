"""Benchmark guards and counters with synthetic vectors; never runs real inference or a server."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from core.types import Encoded
from scripts import benchmark_index as benchmark


def test_benchmark_requires_explicit_write_before_settings_or_clients(monkeypatch, tmp_path):
    monkeypatch.setattr(benchmark, "get_settings", lambda: pytest.fail("settings/client path reached"))
    monkeypatch.setattr(
        "sys.argv", ["benchmark", "--input", "missing.jsonl", "--report", str(tmp_path / "report.json")]
    )
    with pytest.raises(SystemExit) as error:
        benchmark.main()
    assert error.value.code == 2 and not list(tmp_path.iterdir())


@pytest.mark.parametrize("fail", [False, True])
async def test_encoder_counts_only_completed_real_interface_calls(fail):
    class Encoder:
        async def encode(self, texts, *, query=False):
            assert not query and texts == ["passage: synthetic"]
            if fail:
                raise RuntimeError("synthetic failure")
            return [Encoded([1.0] + [0.0] * 383, [1], [1.0])]

    report = {"embedding_seconds": 0.0, "embedded_records": 0}
    measured = benchmark.MeasuredEncoder(Encoder(), report)
    if fail:
        with pytest.raises(RuntimeError):
            await measured.encode(["passage: synthetic"])
        assert report == {"embedding_seconds": 0.0, "embedded_records": 0}
    else:
        result = await measured.encode(["passage: synthetic"])
        assert report["embedded_records"] == 1 and report["embedding_seconds"] >= 0
        assert len(result[0].dense) == 384


@pytest.mark.parametrize("fail", [False, True])
async def test_upsert_counts_only_acknowledged_batches_and_saves_progress(tmp_path, fail):
    class Client:
        async def upsert(self, collection, *, points, wait):
            assert collection == "synthetic" and wait and len(points) == 1
            if fail:
                raise RuntimeError("synthetic failure")

    report = {"upsert_seconds": 0.0, "completed_records": 0, "completed_batches": 0, "selected_records": 1}
    path = tmp_path / "report.json"
    store = benchmark.MeasuredStore(Client(), "synthetic", report=report, report_path=path)
    store.last_progress -= 31
    chunk = SimpleNamespace(
        point_uuid=UUID(int=1),
        payload=lambda: {"game_scope": "base", "review_status": "approved", "source_type": "wiki_prose", "lang": "en"},
    )
    if fail:
        with pytest.raises(RuntimeError):
            await store.upsert([chunk], [Encoded([1.0] + [0.0] * 383, [1], [1.0])])
        assert report["completed_records"] == 0 and not path.exists()
    else:
        await store.upsert([chunk], [Encoded([1.0] + [0.0] * 383, [1], [1.0])])
        assert report["completed_records"] == report["completed_batches"] == 1
        assert path.exists() and not path.with_suffix(".json.tmp").exists()
