import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from handlers.startemoji import (
    cmd_emoji,
    callback_assign_emoji,
    callback_choose_emoji
)

@pytest.mark.asyncio
async def test_cmd_emoji_admin_and_users():
    users = [111, 222, 333, 444, 555]
    for uid in users:
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.bot = AsyncMock()
        msg.answer = AsyncMock()
        msg.answer_photo = AsyncMock()
        msg.chat = SimpleNamespace(id=uid)

        fake_conn = AsyncMock()
        fake_conn.fetch = AsyncMock(return_value=[{"user_id": uid, "emoji": "😎"}])
        fake_conn.__aenter__.return_value = fake_conn

        with patch("handlers.startemoji.db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
             patch("handlers.startemoji.is_user_admin", return_value=True), \
             patch("handlers.startemoji.get_user_language", return_value="ru"), \
             patch("handlers.startemoji.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
             patch("handlers.startemoji.safe_answer", new=AsyncMock()) as safe_mock:
            await cmd_emoji(msg, msg.bot, user_id=uid)
            safe_mock.assert_awaited()

@pytest.mark.asyncio
async def test_callback_assign_emoji_all_steps():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=7894353415)
    cb.data = "reassign_123"
    cb.message = AsyncMock()
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()
    cb.message.chat = SimpleNamespace(id=7894353415)
    with patch("handlers.startemoji.is_user_admin", return_value=True), \
         patch("handlers.startemoji.get_user_language", return_value="ru"), \
         patch("handlers.startemoji.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.startemoji.safe_answer", new=AsyncMock()) as safe_mock:
        await callback_assign_emoji(cb, FSMContext)
        safe_mock.assert_awaited()

@pytest.mark.asyncio
async def test_callback_choose_emoji_ok():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=7894353415)
    cb.data = "choose_emoji_123_😎"
    cb.message = AsyncMock()
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()
    cb.bot.send_message = AsyncMock()
    cb.message.chat = SimpleNamespace(id=7894353415)

    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    with patch("handlers.startemoji.db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.startemoji.is_user_admin", return_value=True), \
         patch("handlers.startemoji.get_user_language", return_value="ru"), \
         patch("handlers.startemoji.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.startemoji.safe_answer", new=AsyncMock()) as safe_mock:
        await callback_choose_emoji(cb, cb.bot)
        safe_mock.assert_awaited()
        cb.bot.send_message.assert_awaited()

@pytest.mark.asyncio
async def test_callback_assign_emoji_invalid_id():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=7894353415)
    cb.data = "reassign_invalid"
    cb.message = AsyncMock()
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()
    cb.message.chat = SimpleNamespace(id=7894353415)
    with patch("handlers.startemoji.is_user_admin", return_value=True), \
         patch("handlers.startemoji.get_user_language", return_value="ru"), \
         patch("handlers.startemoji.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.startemoji.safe_answer", new=AsyncMock()) as safe_mock:
        await callback_assign_emoji(cb, FSMContext)
        safe_mock.assert_awaited()

@pytest.mark.asyncio
async def test_callback_choose_emoji_invalid_data():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=7894353415)
    cb.data = "choose_emoji_invalid"
    cb.message = AsyncMock()
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()
    cb.message.chat = SimpleNamespace(id=7894353415)
    with patch("handlers.startemoji.is_user_admin", return_value=True), \
         patch("handlers.startemoji.get_user_language", return_value="ru"), \
         patch("handlers.startemoji.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.startemoji.safe_answer", new=AsyncMock()) as safe_mock:
        await callback_choose_emoji(cb, cb.bot)
        safe_mock.assert_awaited()

@pytest.mark.asyncio
async def test_callback_choose_emoji_invalid_user_id():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=7894353415)
    cb.data = "choose_emoji_notint_😎"
    cb.message = AsyncMock()
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()
    cb.message.chat = SimpleNamespace(id=7894353415)
    with patch("handlers.startemoji.is_user_admin", return_value=True), \
         patch("handlers.startemoji.get_user_language", return_value="ru"), \
         patch("handlers.startemoji.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.startemoji.safe_answer", new=AsyncMock()) as safe_mock:
        await callback_choose_emoji(cb, cb.bot)
        safe_mock.assert_awaited()

@pytest.mark.asyncio
async def test_cmd_emoji_not_admin():
    msg = AsyncMock(spec=Message)
    msg.from_user = SimpleNamespace(id=999)
    msg.bot = AsyncMock()
    msg.chat = SimpleNamespace(id=999)
    with patch("handlers.startemoji.is_user_admin", return_value=False), \
         patch("handlers.startemoji.get_user_language", return_value="ru"), \
         patch("handlers.startemoji.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
         patch("handlers.startemoji.safe_answer", AsyncMock()) as safe_mock:
        await cmd_emoji(msg, msg.bot, user_id=999)
        safe_mock.assert_awaited()
