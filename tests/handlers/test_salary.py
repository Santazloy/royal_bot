import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.salary import (
    salary_command,
    salary_via_button,
    process_group,
    process_option,
    process_cancel,
    _salary_init,
    load_salary_data_from_db,
    SalaryStates,
    SALARY_PHOTO
)
from config import ADMIN_IDS

@pytest.mark.asyncio
async def test_salary_command_and_via_button_multiple_admins():
    admin_ids = [7894353415, 7935161063, 1768520583, 7281089930, 7894353415]
    states = [AsyncMock(spec=FSMContext) for _ in admin_ids]
    async def simulate(uid, state):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.chat = SimpleNamespace(id=uid)
        msg.bot = AsyncMock()
        state.set_state = AsyncMock()
        with patch("handlers.salary.get_user_language", return_value="ru"), \
             patch("handlers.salary.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
             patch("handlers.salary.groups_data", {"Royal_1": {"salary_option": 1, "salary": 0, "cash": 0}}), \
             patch("handlers.salary.is_user_admin", return_value=True), \
             patch("handlers.salary.safe_answer", new_callable=AsyncMock):
            await salary_command(msg, state)
            with patch.object(msg, "answer", new=AsyncMock()) as answer_mock:
                await salary_via_button(msg, state)
                answer_mock.assert_awaited()
            assert state.set_state.await_count > 0
    await asyncio.gather(*[simulate(uid, state) for uid, state in zip(admin_ids, states)])

@pytest.mark.asyncio
async def test_process_group_and_option_cancel_multiple():
    uids = [7894353415, 7935161063, 1768520583, 7281089930, 7894353415]
    async def simulate(uid):
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.data = "salary_group_Royal_1"
        cb.answer = AsyncMock()
        cb.message = AsyncMock()
        cb.bot = AsyncMock()
        cb.message.chat = SimpleNamespace(id=uid)
        state = AsyncMock(spec=FSMContext)
        state.update_data = AsyncMock()
        state.set_state = AsyncMock()
        with patch("handlers.salary.get_user_language", return_value="ru"), \
             patch("handlers.salary.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
             patch("handlers.salary.groups_data", {"Royal_1": {"salary_option": 1, "salary": 0, "cash": 0}}), \
             patch("handlers.salary.is_user_admin", return_value=True), \
             patch("handlers.salary.safe_answer", new_callable=AsyncMock):
            await process_group(cb, state)
            assert state.set_state.await_count > 0

        cb2 = AsyncMock(spec=CallbackQuery)
        cb2.from_user = SimpleNamespace(id=uid)
        cb2.data = "salary_opt_2"
        cb2.answer = AsyncMock()
        cb2.message = AsyncMock()
        cb2.bot = AsyncMock()
        cb2.message.chat = SimpleNamespace(id=uid)
        state2 = AsyncMock(spec=FSMContext)
        state2.get_data = AsyncMock(return_value={"selected_group": "Royal_1"})
        state2.clear = AsyncMock()
        with patch("handlers.salary.get_user_language", return_value="ru"), \
             patch("handlers.salary.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
             patch("handlers.salary.groups_data", {"Royal_1": {"salary_option": 1, "salary": 0, "cash": 0}}), \
             patch("handlers.salary.db.db_pool", None), \
             patch("handlers.salary.is_user_admin", return_value=True), \
             patch("handlers.salary.safe_answer", new_callable=AsyncMock):
            await process_option(cb2, state2)
            assert state2.clear.await_count > 0

        cb3 = AsyncMock(spec=CallbackQuery)
        cb3.from_user = SimpleNamespace(id=uid)
        cb3.data = "salary_cancel"
        cb3.answer = AsyncMock()
        cb3.message = AsyncMock()
        cb3.message.delete = AsyncMock()
        cb3.message.chat = SimpleNamespace(id=uid)
        state3 = AsyncMock(spec=FSMContext)
        state3.clear = AsyncMock()
        with patch("handlers.salary.get_user_language", return_value="ru"), \
             patch("handlers.salary.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
             patch("handlers.salary.is_user_admin", return_value=True):
            await process_cancel(cb3, state3)
            assert cb3.answer.await_count > 0
            assert state3.clear.await_count > 0
    await asyncio.gather(*[simulate(uid) for uid in uids])

@pytest.mark.asyncio
async def test_load_salary_data_from_db_empty():
    with patch("handlers.salary.db.db_pool", None):
        await load_salary_data_from_db()

@pytest.mark.asyncio
async def test_salary_init_forbidden():
    msg = AsyncMock(spec=Message)
    msg.from_user = SimpleNamespace(id=1)
    msg.chat = SimpleNamespace(id=1)
    msg.bot = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    with patch("handlers.salary.get_user_language", return_value="ru"), \
         patch("handlers.salary.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.salary.is_user_admin", return_value=False), \
         patch("handlers.salary.safe_answer", new=AsyncMock()) as safe_mock:
        result = await _salary_init(msg, state)
        safe_mock.assert_awaited()
