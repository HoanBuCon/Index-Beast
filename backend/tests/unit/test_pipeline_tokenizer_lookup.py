"""scripts/data_pipeline và `ingest update` tìm tokenizer E5 ở cùng một chỗ: settings.rag_models_dir.

Phụ trách: TV2 · [S5] Cập nhật dữ liệu tăng dần
"""

from argparse import Namespace

import pytest

from core.config import get_settings
from scripts import data_pipeline as dp


def make_tokenizer(models_dir):
    target = models_dir / "models--intfloat--multilingual-e5-small" / "snapshots" / "abc"
    target.mkdir(parents=True)
    (target / "tokenizer.json").write_text("{}")
    return target / "tokenizer.json"


@pytest.fixture(autouse=True)
def fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_tokenizer_follows_rag_models_dir(tmp_path, monkeypatch):
    first, second = make_tokenizer(tmp_path / "a"), make_tokenizer(tmp_path / "b")
    monkeypatch.setenv("RAG_MODELS_DIR", str(tmp_path / "a"))
    assert dp.tokenizer() == first
    get_settings.cache_clear()
    monkeypatch.setenv("RAG_MODELS_DIR", str(tmp_path / "b"))
    assert dp.tokenizer() == second


def test_missing_tokenizer_exits_with_a_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_MODELS_DIR", str(tmp_path / "empty"))
    with pytest.raises(SystemExit, match="tokenizer"):
        dp.tokenizer()


def test_explicit_tokenizer_wins(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(dp, "run", lambda *args: calls.append(args))
    monkeypatch.setattr(dp, "tokenizer", lambda: pytest.fail("không được tự tìm khi đã có --tokenizer"))
    (tmp_path / "clean").mkdir()
    args = Namespace(input=None, output=tmp_path / "out", tokenizer=tmp_path / "mine.json", wiki_quality=False)
    dp.chunk(args, tmp_path / "clean")
    assert str(tmp_path / "mine.json") in map(str, calls[0])
