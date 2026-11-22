"""`update`: batch_pages/max_pages phải là số nguyên dương, kiểm tra trước khi chạm nguồn hay kho dữ liệu.

Phụ trách: TV2 · [S5] Cập nhật dữ liệu tăng dần
"""

import pytest

from ingest.__main__ import main
from ingest.artifacts import save
from ingest.update import bootstrap_from_documents, run_update, state_path
from tests.unit.test_ingest_update_run import Builder, Docs, Index, Jobs, Wiki, iso


@pytest.fixture
def env(tmp_path):
    config = {"data_dir": tmp_path, "sources": {"wikigg": {"categories": ["NPC"], "category_depth": 1}}}
    pages = {1: {"title": "Ranni", "rev": 10}, 2: {"title": "Melina", "rev": 20}}
    state = bootstrap_from_documents(
        [{"source_id": str(i), "revision_id": p["rev"], "title": p["title"], "chunks": 2} for i, p in pages.items()]
    )
    state["watermark"] = iso(1)
    save(state_path(config, "wikigg"), state)
    wiki = Wiki(pages)
    wiki.pages[1]["rev"] = 11  # có trang đổi: nếu không chặn, lượt chạy sẽ ghi index/state
    return config, wiki, Builder(wiki), Index(), Docs(), Jobs()


async def attempt(env, **kw):
    config, wiki, builder, index, docs, jobs = env
    before = state_path(config, "wikigg").read_bytes()
    with pytest.raises(ValueError, match="pages"):
        await run_update(wiki, config, builder=builder, index=index, docs=docs, jobs=jobs, **kw)
    assert state_path(config, "wikigg").read_bytes() == before
    assert not (wiki.describe_calls or wiki.since_seen or wiki.category_calls)
    assert not (builder.built or index.synced or index.deleted or index.prepared or docs.synced or jobs.started)


@pytest.mark.parametrize("kw", [{"batch_pages": 0}, {"batch_pages": -1}, {"max_pages": 0}, {"max_pages": -5}])
async def test_non_positive_arguments_are_rejected_before_any_work(env, kw):
    await attempt(env, **kw)


@pytest.mark.parametrize("value", [0, -1, True, "5"])
async def test_invalid_batch_pages_from_config_is_rejected_before_any_work(env, value):
    env[0]["update"] = {"batch_pages": value}
    await attempt(env)


@pytest.mark.parametrize("flag", ["--batch-pages", "--max-pages"])
@pytest.mark.parametrize("value", ["0", "-3", "x"])
def test_cli_rejects_non_positive_page_limits(flag, value, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["update", flag, value])
    assert exc.value.code == 2
    assert "positive" in capsys.readouterr().err
