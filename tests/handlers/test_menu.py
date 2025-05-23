# tests/handlers/test_menu.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.menu import cmd_menu, on_menu_stub
from handlers.language import get_message


@pytest.mark.asyncio
async def test_cmd_menu_multiple_users():
    async def simulate(uid):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.chat = SimpleNamespace(id=uid)
        msg.answer_photo = AsyncMock()
        msg.bot = AsyncMock()

        await cmd_menu(msg)
        msg.answer_photo.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in range(1001, 1006)])


@pytest.mark.asyncio
async def test_on_menu_stub_booking_multiple_users():
    async def simulate(uid):
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.data = "menu_stub|booking"
        cb.message = AsyncMock()
        cb.message.chat = SimpleNamespace(id=uid)
        cb.message.edit_media = AsyncMock()
        cb.answer = AsyncMock()

        state = AsyncMock()

        with patch("handlers.menu.get_user_language", return_value="ru"):
            await on_menu_stub(cb, state)

        cb.answer.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in range(1001, 1006)])


@pytest.mark.asyncio
async def test_on_menu_stub_unknown():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=1)
    cb.data = "menu_stub|unknown"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    state = AsyncMock()

    with patch("handlers.menu.get_user_language", return_value="ru"):
        await on_menu_stub(cb, state)

    cb.answer.assert_awaited_with(get_message("ru", "menu_unknown"), show_alert=True)
