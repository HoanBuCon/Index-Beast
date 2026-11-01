"""load_full tìm raw theo vị trí tương đối khi artifact ghi đường dẫn tuyệt đối của máy khác.

Phụ trách: TV1 · [S2] Sửa đường dẫn artifact (đề xuất dữ liệu #4)
"""

from ingest.chunk.load_full import local_snapshot


def test_foreign_absolute_path_is_rebased_on_local_data_dir(tmp_path):
    raw = tmp_path / "raw" / "wikigg" / "snapshots" / "9" / "66711-abc.json"
    raw.parent.mkdir(parents=True)
    raw.write_text("{}", encoding="utf-8")
    recorded = r"D:\Index-Beast\backend\data\raw\wikigg\snapshots\9\66711-abc.json"

    assert local_snapshot(recorded, tmp_path) == raw


def test_existing_path_is_used_as_is(tmp_path):
    raw = tmp_path / "elsewhere.json"
    raw.write_text("{}", encoding="utf-8")

    assert local_snapshot(str(raw), tmp_path / "data") == raw


def test_path_without_raw_dir_is_returned_unchanged(tmp_path):
    recorded = r"D:\other\file.json"

    assert str(local_snapshot(recorded, tmp_path)).endswith("file.json")
