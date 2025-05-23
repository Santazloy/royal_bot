# tests/handlers/test_salary.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.salary import cmd_salary, process_cancel
from config import ADMIN_IDS
from handlers.language import get_message

@pytest.mark.asyncio
async def test_cmd_salary_multiple_admins():
    admin_ids = [111111111, 222222222, 333333333, 444444444, 555555555]
    ADMIN_IDS.extend(admin_ids)

    async def simulate(uid):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.answer = AsyncMock()
        state = AsyncMock()
        with patch("handlers.salary.get_user_language", return_value="ru"):
            await cmd_salary(msg, state)
        msg.answer.assert_awaited()
        state.set_state.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in admin_ids])
    for uid in admin_ids:
        ADMIN_IDS.remove(uid)


@pytest.mark.asyncio
async def test_process_cancel_multiple_users():
    async def simulate(uid):
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.answer = AsyncMock()
        cb.message = AsyncMock()
        cb.message.delete = AsyncMock()
        state = AsyncMock()

        with patch("handlers.salary.get_user_language", return_value="ru"):
            await process_cancel(cb, state)

        cb.answer.assert_awaited_with(get_message("ru", "cancelled"), show_alert=True)
        state.clear.assert_awaited_once()

    await asyncio.gather(*[simulate(uid) for uid in range(2001, 2006)])
