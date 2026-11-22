"""delete_account với lỗi giả giữa lô và ở bước cuối: phiên phải còn nguyên để DELETE /me thử lại được (idempotent).

Kho giả có transaction thật (rollback khôi phục trạng thái); phần SQL thật ở tests/integration/test_privacy.py.

Phụ trách: TV1 · [S5] Quyền riêng tư và xóa tài khoản
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.services import privacy
from core.errors import NotFoundError, UnavailableError
from tests.unit.test_privacy import FakeQdrant


class FakeDB:
    def __init__(self, user, conversations):
        self.user = user
        self.convs = {c: user for c in conversations}  # conversation_id -> user_id
        self.sessions, self.users = {uuid4(), uuid4()}, {user}
        self.fail_on = None  # hàm (sql) -> bool: ném lỗi SQL tại câu lệnh khớp
        self.before = None  # hàm (sql): chạy trước mỗi câu lệnh (chèn dữ liệu xen vào)
        self.snapshot = None

    def __call__(self):
        return FakeSession(self)


class FakeResult:
    def __init__(self, rows=(), rowcount=0):
        self.rows, self.rowcount = list(rows), rowcount

    def scalars(self):
        return iter(self.rows)


class FakeTx:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        self.db.snapshot = (dict(self.db.convs), set(self.db.sessions), set(self.db.users))

    async def __aexit__(self, exc_type, *_):
        if exc_type is not None:
            self.db.convs, self.db.sessions, self.db.users = self.db.snapshot


class FakeSession:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def begin(self):
        return FakeTx(self.db)

    async def execute(self, stmt):
        db, compiled = self.db, stmt.compile()
        sql, params = str(compiled).replace("\n", " "), compiled.params
        if db.before:
            db.before(sql)
        if db.fail_on and db.fail_on(sql):
            raise SQLAlchemyError("boom")
        if sql.startswith("SELECT conversations.id"):
            mine = [c for c, u in db.convs.items() if u == params["user_id_1"] and params.get("id_1", c) == c]
            return FakeResult(mine[: params.get("param_1") or len(mine)])
        if sql.startswith("DELETE FROM conversations") and "RETURNING" in sql:
            gone = [c for c, u in db.convs.items() if u == params["user_id_1"]]
            for c in gone:
                del db.convs[c]
            return FakeResult(gone, len(gone))
        if sql.startswith("DELETE FROM conversations"):
            gone = [c for c in params["id_1"] if db.convs.pop(c, None) is not None]
            return FakeResult(rowcount=len(gone))
        if sql.startswith("DELETE FROM auth_sessions"):
            n, db.sessions = len(db.sessions), set()
            return FakeResult(rowcount=n)
        if sql.startswith("DELETE FROM users"):
            n = int(params["id_1"] in db.users)
            db.users.discard(params["id_1"])
            return FakeResult(rowcount=n)
        raise AssertionError(sql)


@pytest.fixture(autouse=True)
def small_batches(monkeypatch):
    monkeypatch.setattr(privacy, "BATCH_SIZE", 2)


async def test_removes_everything_and_sessions_go_with_the_final_transaction():
    user = uuid4()
    db = FakeDB(user, [uuid4() for _ in range(5)])
    counts = await privacy.delete_account(db, FakeQdrant(), "c", user)
    assert (counts.conversations, counts.sessions, counts.users) == (5, 2, 1)
    assert not db.convs and not db.sessions and not db.users


async def test_sql_failure_between_batches_keeps_session_and_retry_finishes():
    user = uuid4()
    db = FakeDB(user, [uuid4() for _ in range(5)])
    batches = []

    def second_batch(sql):
        if sql.startswith("DELETE FROM conversations") and "RETURNING" not in sql:
            batches.append(1)
            return len(batches) == 2
        return False

    db.fail_on = second_batch
    with pytest.raises(UnavailableError):
        await privacy.delete_account(db, FakeQdrant(), "c", user)
    assert len(db.convs) == 3 and db.sessions and user in db.users  # lô đầu xong; phiên và người dùng còn
    db.fail_on = None
    await privacy.delete_account(db, FakeQdrant(), "c", user)
    assert not db.convs and not db.sessions and not db.users


async def test_qdrant_failure_between_batches_keeps_session_and_unpurged_rows():
    user = uuid4()
    db = FakeDB(user, [uuid4() for _ in range(5)])

    class FailSecond(FakeQdrant):
        async def delete(self, collection, points_selector, wait):
            if self.deletes:
                raise ConnectionError("down")
            await super().delete(collection, points_selector, wait)

    with pytest.raises(UnavailableError):
        await privacy.delete_account(db, FailSecond(), "c", user)
    assert len(db.convs) == 3 and db.sessions and user in db.users
    await privacy.delete_account(db, FakeQdrant(), "c", user)
    assert not db.convs and not db.sessions and not db.users


@pytest.mark.parametrize("step", ["DELETE FROM auth_sessions", "DELETE FROM users"])
async def test_failure_in_the_final_transaction_rolls_back_everything_and_is_retryable(step):
    user, stray = uuid4(), uuid4()
    db = FakeDB(user, [])
    db.fail_on = lambda sql: sql.startswith(step)

    selects = []

    def arrive_late(sql):  # hội thoại tới sau vòng lô (lần SELECT thứ 2 là lần chọn "còn sót" của bước cuối)
        if sql.startswith("SELECT conversations.id"):
            selects.append(1)
            if len(selects) == 2:
                db.convs[stray] = user

    db.before = arrive_late
    with pytest.raises(UnavailableError):
        await privacy.delete_account(db, None, "c", user)
    assert db.sessions and user in db.users and stray in db.convs
    db.fail_on = None
    await privacy.delete_account(db, None, "c", user)
    assert not db.sessions and not db.users and not db.convs
    assert await privacy.delete_account(db, None, "c", user) == privacy.Counts()  # idempotent


async def test_vectors_are_purged_while_the_rows_still_exist():
    user, conv = uuid4(), uuid4()
    db = FakeDB(user, [conv])
    seen = []

    class Spy(FakeQdrant):
        async def delete(self, collection, points_selector, wait):
            seen.append((conv in db.convs, bool(db.sessions)))
            await super().delete(collection, points_selector, wait)

    await privacy.delete_account(db, Spy(), "c", user)
    assert seen and all(row_and_session for row_and_session in seen)


# ---------- xóa một hội thoại của tài khoản (DELETE /me/conversations/{id}) ----------


async def test_deletes_only_the_owned_conversation_and_its_vectors_first():
    user = uuid4()
    keep, gone = uuid4(), uuid4()
    db, qdrant = FakeDB(user, [keep, gone]), FakeQdrant()

    await privacy.delete_conversation(db, qdrant, "c", user, gone)

    assert set(db.convs) == {keep}
    assert len(qdrant.deletes) == 1
    assert db.users == {user} and db.sessions  # tài khoản và phiên còn nguyên


async def test_someone_elses_conversation_is_not_found_and_untouched():
    owner, stranger = uuid4(), uuid4()
    conversation = uuid4()
    db, qdrant = FakeDB(owner, [conversation]), FakeQdrant()

    with pytest.raises(NotFoundError):
        await privacy.delete_conversation(db, qdrant, "c", stranger, conversation)

    assert conversation in db.convs and not qdrant.deletes


async def test_vector_failure_keeps_the_row_so_a_retry_can_finish():
    user, conversation = uuid4(), uuid4()
    db = FakeDB(user, [conversation])

    with pytest.raises(UnavailableError):
        await privacy.delete_conversation(db, FakeQdrant(fail=True), "c", user, conversation)
    assert conversation in db.convs

    await privacy.delete_conversation(db, FakeQdrant(), "c", user, conversation)
    assert not db.convs
