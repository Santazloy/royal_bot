import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.money import (
    money_command,
    money_via_button,
    process_money_type,
    process_money_group,
    process_money_op,
    process_money_amount,
    money_cancel,
    MoneyStates,
    _send_photo
)

@pytest.mark.asyncio
async def test_money_command_and_via_button_full():
    users = [101, 202, 303, 404, 505]
    states = [AsyncMock(spec=FSMContext) for _ in users]

    for uid, state in zip(users, states):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.chat = SimpleNamespace(id=uid)
        msg.answer_photo = AsyncMock()
        msg.bot = AsyncMock()
        with patch("handlers.money.get_user_language", return_value="ru"), \
             patch("handlers.money.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
             patch("handlers.money.groups_data", {"Royal_1": {"chat_id": uid, "salary": 0, "cash": 0}}), \
             patch("handlers.money._send_photo", new=AsyncMock()) as photo_mock:
            await money_command(msg, state)
            await money_via_button(msg, state)
            photo_mock.assert_awaited()
    # Проверка, что работает только для админа
    msg = AsyncMock(spec=Message)
    msg.from_user = SimpleNamespace(id=999999)
    msg.chat = SimpleNamespace(id=999999)
    with patch("handlers.money.is_user_admin", return_value=False), \
         patch("handlers.money.get_user_language", return_value="ru"), \
         patch("handlers.money.get_message", return_value="no_permission"):
        resp = await money_command(msg, AsyncMock())
        assert resp is None

@pytest.mark.asyncio
async def test_process_money_type_and_group():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=1234)
    cb.data = "money_type_salary"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.bot = AsyncMock()
    cb.message.chat = SimpleNamespace(id=1234)
    state = AsyncMock(spec=FSMContext)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    with patch("handlers.money.get_user_language", return_value="ru"), \
         patch("handlers.money.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.money.groups_data", {"Royal_1": {"chat_id": 1234, "salary": 0, "cash": 0}}), \
         patch("handlers.money._send_photo", new=AsyncMock()) as photo_mock:
        await process_money_type(cb, state)
        photo_mock.assert_awaited()
        state.set_state.assert_awaited()

    cb2 = AsyncMock(spec=CallbackQuery)
    cb2.from_user = SimpleNamespace(id=1234)
    cb2.data = "money_group_Royal_1"
    cb2.answer = AsyncMock()
    cb2.message = AsyncMock()
    cb2.bot = AsyncMock()
    cb2.message.chat = SimpleNamespace(id=1234)
    state2 = AsyncMock(spec=FSMContext)
    state2.update_data = AsyncMock()
    state2.set_state = AsyncMock()
    with patch("handlers.money.get_user_language", return_value="ru"), \
         patch("handlers.money.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.money.groups_data", {"Royal_1": {"chat_id": 1234, "salary": 0, "cash": 0}}), \
         patch("handlers.money._send_photo", new=AsyncMock()) as photo_mock:
        await process_money_group(cb2, state2)
        photo_mock.assert_awaited()
        state2.set_state.assert_awaited()

@pytest.mark.asyncio
async def test_process_money_op_and_amount():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=1234)
    cb.data = "money_op_add"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.bot = AsyncMock()
    cb.message.chat = SimpleNamespace(id=1234)
    state = AsyncMock(spec=FSMContext)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    with patch("handlers.money.get_user_language", return_value="ru"), \
         patch("handlers.money.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.money._send_photo", new=AsyncMock()) as photo_mock:
        await process_money_op(cb, state)
        photo_mock.assert_awaited()
        state.set_state.assert_awaited()

    # Тест суммы: корректная, некорректная
    msg = AsyncMock(spec=Message)
    msg.from_user = SimpleNamespace(id=1234)
    msg.text = "500"
    msg.chat = SimpleNamespace(id=1234)
    msg.bot = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    with patch("handlers.money.get_user_language", return_value="ru"), \
         patch("handlers.money.get_message", return_value="ok"), \
         patch("handlers.money.groups_data", {"Royal_1": {"salary": 0, "cash": 0}}), \
         patch("handlers.money.db.db_pool", None), \
         patch("handlers.money._send_photo", new=AsyncMock()) as photo_mock:
        await state.update_data({"group": "Royal_1", "operation": "add", "type": "salary"})
        await process_money_amount(msg, state)
        photo_mock.assert_awaited()
    # Некорректная сумма
    msg.text = "abc"
    with patch("handlers.money.get_user_language", return_value="ru"), \
         patch("handlers.money.get_message", return_value="invalid_amount"):
        resp = await process_money_amount(msg, state)
        assert resp is None

@pytest.mark.asyncio
async def test_money_cancel():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=111)
    cb.data = "money_cancel"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.bot = AsyncMock()
    cb.message.chat = SimpleNamespace(id=111)
    state = AsyncMock(spec=FSMContext)
    state.clear = AsyncMock()
    with patch("handlers.money.get_user_language", return_value="ru"), \
         patch("handlers.money.get_message", return_value="cancelled"):
        await money_cancel(cb, state)
        cb.answer.assert_awaited()
        state.clear.assert_awaited()
