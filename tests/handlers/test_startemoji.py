# tests/handlers/test_startemoji.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from handlers.startemoji import (
    cmd_start,
    cmd_emoji,
    callback_assign_emoji,
    callback_choose_emoji,
    callback_reassign_emoji,
)


@pytest.mark.asyncio
async def test_cmd_start_multiple_users():
    async def simulate_user(uid):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.answer = AsyncMock()
        msg.bot = AsyncMock()

        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value=None)
        fake_conn.execute = AsyncMock()
        fake_conn.__aenter__.return_value = fake_conn

        with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
            await cmd_start(msg, msg.bot)
            msg.answer.assert_awaited()

    await asyncio.gather(*[simulate_user(uid) for uid in range(1001, 1006)])


@pytest.mark.asyncio
async def test_cmd_emoji_admin():
    msg = AsyncMock(spec=Message)
    msg.from_user = SimpleNamespace(id=7894353415)
    msg.bot = AsyncMock()
    msg.answer = AsyncMock()

    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=[{"user_id": 1, "emoji": "😎"}])
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
        await cmd_emoji(msg, msg.bot)
        msg.answer.assert_awaited()


@pytest.mark.asyncio
async def test_callback_assign_emoji():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=7894353415)
    cb.data = "assign_emoji_123"
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    await callback_assign_emoji(cb, cb.bot)
    cb.answer.assert_awaited()


@pytest.mark.asyncio
async def test_callback_choose_emoji():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=7894353415)
    cb.data = "choose_emoji_123_😎"
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    cb.bot.send_message = AsyncMock()

    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
        await callback_choose_emoji(cb, cb.bot)
        cb.answer.assert_awaited()
        cb.bot.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_callback_reassign_emoji():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=7894353415)
    cb.data = "reassign_123"
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    await callback_reassign_emoji(cb, cb.bot)
    cb.answer.assert_awaited()
    cb.message.edit_text.assert_awaited()
