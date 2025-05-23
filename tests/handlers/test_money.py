# tests/handlers/test_money.py

import pytest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from handlers.money import money_command, money_select_type, money_operation
from aiogram.fsm.context import FSMContext


@pytest.mark.asyncio
async def test_money_command():
    msg = AsyncMock(spec=Message)
    msg.from_user = SimpleNamespace(id=1234)
    msg.chat = SimpleNamespace(id=-1002503654146)
    msg.answer = AsyncMock()
    mocked_response = AsyncMock()
    msg.answer.return_value = mocked_response
    mocked_response.edit_reply_markup = AsyncMock()

    state = AsyncMock(spec=FSMContext)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    with patch("handlers.money.get_user_language", return_value="ru"), \
         patch("handlers.money.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.money.groups_data", {
             "Royal_1": {"chat_id": -1002503654146, "salary": 0, "cash": 0}
         }):
        await money_command(msg, state)

    msg.answer.assert_awaited()
    mocked_response.edit_reply_markup.assert_awaited()


@pytest.mark.asyncio
async def test_money_select_type():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=1234)
    cb.data = "money_salary"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()

    state = AsyncMock(spec=FSMContext)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    with patch("handlers.money.get_user_language", return_value="ru"), \
         patch("handlers.money.get_message", side_effect=lambda lang, key, **kw: f"{key}"):
        await money_select_type(cb, state)

    cb.answer.assert_awaited()
    cb.message.edit_text.assert_awaited()
    state.set_state.assert_awaited()


@pytest.mark.asyncio
async def test_money_operation():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=1234)
    cb.data = "money_plus"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()

    state = AsyncMock(spec=FSMContext)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    with patch("handlers.money.get_user_language", return_value="ru"), \
         patch("handlers.money.get_message", side_effect=lambda lang, key, **kw: f"{key}"):
        await money_operation(cb, state)

    cb.answer.assert_awaited()
    cb.message.edit_text.assert_awaited()
    state.set_state.assert_awaited()
