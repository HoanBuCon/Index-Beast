"""Đọc lịch sử ở chế độ memory áp cùng hợp đồng phân quyền với PostgreSQL (token / chủ tài khoản / service).

Phụ trách: TV1 · [S5] Quyền riêng tư
"""

from uuid import uuid4

import pytest

from app.api.schemas.chat import ChatRequest
from core.errors import NotFoundError, UnauthorizedError
from tests.unit.test_live_chat import BODY, FakeLLM, FakeRetriever, service


def make():
    return service(llm=FakeLLM(), retriever=FakeRetriever())


def ask(live, user_id=None, **extra):
    return live.answer(ChatRequest(**{**BODY, **extra}).attach_user(user_id))


async def test_web_owner_token_reads_history_and_response_carries_capability():
    live = make()
    first = await ask(live)
    assert first.conversation_token and len(first.conversation_token) >= 32
    history = await live.stored_history(first.conversation_id, token=first.conversation_token)
    assert len(history.messages) == 2


async def test_web_without_or_with_wrong_token_is_unauthorized():
    live = make()
    first = await ask(live)
    with pytest.raises(UnauthorizedError):
        await live.stored_history(first.conversation_id)
    with pytest.raises(UnauthorizedError):
        await live.stored_history(first.conversation_id, token="z" * 40)
    # service tin cậy không mở được hội thoại web (giống đường PostgreSQL)
    with pytest.raises(UnauthorizedError):
        await live.stored_history(first.conversation_id, trusted_service=True)


async def test_token_of_another_session_cannot_read_this_one():
    live = make()
    mine, other = await ask(live), await ask(live)
    with pytest.raises(UnauthorizedError):
        await live.stored_history(mine.conversation_id, token=other.conversation_token)


async def test_owning_user_reads_without_token_but_other_user_does_not():
    live = make()
    owner, stranger = uuid4(), uuid4()
    first = await ask(live, user_id=owner)
    assert (await live.stored_history(first.conversation_id, user_id=owner)).id == first.conversation_id
    with pytest.raises(UnauthorizedError):
        await live.stored_history(first.conversation_id, user_id=stranger)


async def test_unknown_conversation_is_not_found():
    with pytest.raises(NotFoundError):
        await make().stored_history(uuid4(), token="z" * 40)


async def test_discord_history_is_for_trusted_service_only():
    live = make()
    first = await ask(live, channel="discord", external_ref="user-1")
    assert first.conversation_token is None
    with pytest.raises(UnauthorizedError):
        await live.stored_history(first.conversation_id)
    with pytest.raises(UnauthorizedError):
        await live.stored_history(first.conversation_id, token="z" * 40)
    assert (await live.stored_history(first.conversation_id, trusted_service=True)).channel == "discord"


async def test_feedback_target_check_uses_same_authorization():
    live = make()
    first = await ask(live)
    assert await live.stored_has_message(first.message_id, token=first.conversation_token)
    with pytest.raises(UnauthorizedError):
        await live.stored_has_message(first.message_id)
    assert not await live.stored_has_message(uuid4())
