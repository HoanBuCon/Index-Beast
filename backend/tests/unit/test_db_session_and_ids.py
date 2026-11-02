"""SessionDep commit trước khi trả response; id document/chunk ổn định.

Phụ trách: TV1 · [S2] Schema PostgreSQL & migrations
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from core.ids import chunk_id, document_id


class _FailingCommitSession:
    @asynccontextmanager
    async def begin(self):
        yield
        raise RuntimeError("commit failed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_commit_failure_is_reported_to_client_not_hidden_behind_200():
    app = FastAPI()
    app.state.ctx = type("Ctx", (), {"sessionmaker": _FailingCommitSession})()

    @app.post("/write")
    async def write(session: SessionDep):
        return {"ok": True}

    res = TestClient(app, raise_server_exceptions=False).post("/write")

    assert res.status_code == 500


def test_ids_are_deterministic_and_distinct():
    doc = document_id("wikigg", "123")

    assert doc == document_id("wikigg", "123")
    assert doc != document_id("wikigg", "124")
    assert chunk_id(doc, 0) == chunk_id(doc, 0) != chunk_id(doc, 1)
    assert isinstance(doc, uuid.UUID)
