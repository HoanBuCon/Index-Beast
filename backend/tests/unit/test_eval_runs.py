"""scripts/eval_runs: chỉ nhận số đo hợp lệ, ghép config, đọc file JSON.

Phụ trách: TV1 · [S4] Lưu kết quả đo cho TV3
"""

import json
from argparse import Namespace

import pytest

from scripts import eval_runs


def args(**kw):
    base = {"name": None, "metric": [], "config": [], "from_json": None, "git_sha": "none"}
    return Namespace(**{**base, **kw})


def test_metrics_and_config_are_parsed_and_the_name_goes_into_config():
    config, metrics = eval_runs.build(
        args(name="golden-baseline", metric=["recall@5=0.78", "accuracy = 0.64"], config=["top_k=5"])
    )
    assert metrics == {"recall@5": 0.78, "accuracy": 0.64}
    assert config == {"top_k": "5", "name": "golden-baseline"}


@pytest.mark.parametrize("bad", [["recall"], ["=0.5"], ["recall=abc"], ["recall=nan"], ["recall=inf"]])
def test_invalid_metrics_are_rejected(bad):
    with pytest.raises(SystemExit):
        eval_runs.build(args(metric=bad))


def test_at_least_one_metric_is_required():
    with pytest.raises(SystemExit, match="ít nhất một số đo"):
        eval_runs.build(args(name="empty"))


def test_json_file_is_merged_and_flags_override_it(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"config": {"k": 1, "name": "x"}, "metrics": {"recall@5": 0.5, "mrr": 0.4}}))
    config, metrics = eval_runs.build(args(from_json=str(report), metric=["recall@5=0.9"], name="final"))
    assert metrics == {"recall@5": 0.9, "mrr": 0.4}
    assert config == {"k": 1, "name": "final"}


def test_json_booleans_are_not_metrics(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"metrics": {"passed": True}}))
    with pytest.raises(SystemExit, match="true/false"):
        eval_runs.build(args(from_json=str(report)))


def test_git_sha_choices():
    assert eval_runs.git_sha("none") is None
    assert eval_runs.git_sha("abc123") == "abc123"
