#tests/handlers/test_clean.py

import pytest
import asyncio
from unittest.mock import AsyncMock
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from handlers.clean import cmd_clean, process_clean_cancel

@pytest.mark.asyncio
async def test_cmd_clean_multiple_users():
    async def simulate_user(uid):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.chat = SimpleNamespace(id=uid)
        msg.answer = AsyncMock()
        msg.bot = AsyncMock()

        state = AsyncMock()
        state.update_data = AsyncMock()
        state.set_state = AsyncMock()

        # is_user_admin будет True
        import handlers.clean
        handlers.clean.is_user_admin = lambda uid: True

        await cmd_clean(msg, state)
        msg.answer.assert_awaited()

    await asyncio.gather(*[simulate_user(uid) for uid in range(1001, 1006)])


@pytest.mark.asyncio
async def test_process_clean_cancel_multiple_users():
    async def simulate_cancel(uid):
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.message = AsyncMock()
        cb.message.delete = AsyncMock()
        cb.answer = AsyncMock()
        state = AsyncMock()

        await process_clean_cancel(cb, state)
        cb.answer.assert_awaited()
        state.clear.assert_awaited_once()

    await asyncio.gather(*[simulate_cancel(uid) for uid in range(1001, 1006)])
