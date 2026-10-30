import pytest

from ingest.artifacts import save
from ingest.transform.document import select_sample


def test_full_clean_uses_explicit_completed_inventory(tmp_path):
    report = tmp_path / "report.json"
    save(report, {"status": "completed", "pages": [{"id": str(i)} for i in range(215)]})
    assert len(select_sample(tmp_path, report, full=True)[1]["pages"]) == 215
    with pytest.raises(ValueError, match="exactly 200"):
        select_sample(tmp_path, report)


def test_full_clean_rejects_partial_duplicate_or_implicit_input(tmp_path):
    with pytest.raises(ValueError, match="explicit"):
        select_sample(tmp_path, full=True)
    report = tmp_path / "report.json"
    for data in (
        {"status": "partial", "pages": [{"id": "1"}]},
        {"status": "completed", "pages": [{"id": "1"}, {"id": "1"}]},
    ):
        save(report, data)
        with pytest.raises(ValueError):
            select_sample(tmp_path, report, full=True)
