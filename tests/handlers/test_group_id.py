# tests/handlers/test_group_id.py

import pytest
from unittest.mock import AsyncMock
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from handlers.group_id import show_group_id, callback_chat_id


@pytest.mark.asyncio
async def test_show_group_id():
    msg = AsyncMock(spec=Message)
    msg.chat = SimpleNamespace(id=123456)
    msg.answer = AsyncMock()
    await show_group_id(msg)
    msg.answer.assert_awaited_with("123456")


@pytest.mark.asyncio
async def test_callback_chat_id():
    cb = AsyncMock(spec=CallbackQuery)
    cb.message = AsyncMock()
    cb.message.chat = SimpleNamespace(id=-1009876543210)
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    await callback_chat_id(cb)
    cb.message.answer.assert_awaited_with("-1009876543210")
    cb.answer.assert_awaited()
