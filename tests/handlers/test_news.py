# tests/handlers/test_news.py

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery, InputMediaPhoto

from handlers.news import (
    cmd_added, process_news_action, NewsStates,
    process_news_photos, photos_done, process_news_text,
    process_edit_text, cmd_show_news
)
from handlers.language import get_message


@pytest.mark.asyncio
async def test_cmd_added_multiple_admins():
    async def simulate(uid):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.answer = AsyncMock()
        state = AsyncMock()
        with patch("handlers.news.get_user_language", return_value="ru"), \
             patch("handlers.news.is_user_admin", return_value=True):
            await cmd_added(msg, state)
            msg.answer.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in [7894353415, 7935161063, 1768520583, 7000000001, 7000000002]])


@pytest.mark.asyncio
async def test_process_news_action_cancel():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=7894353415)
    cb.data = "news_cancel"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.message.bot.delete_message = AsyncMock()
    cb.message.chat = SimpleNamespace(id=123)
    cb.message.message_id = 1
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"base_chat_id": 123, "base_message_id": 1})
    with patch("handlers.news.get_user_language", return_value="ru"), \
         patch("handlers.news.is_user_admin", return_value=True):
        await process_news_action(cb, state)
    cb.answer.assert_awaited()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_news_action_add_edit_delete():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=7894353415)
    cb.message = AsyncMock()
    cb.answer = AsyncMock()
    state = AsyncMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    with patch("handlers.news.is_user_admin", return_value=True), \
         patch("handlers.news.get_user_language", return_value="ru"):

        cb.data = "news_add"
        await process_news_action(cb, state)
        state.set_state.assert_awaited_with(NewsStates.waiting_for_photos)

        cb.data = "news_edit"
        await process_news_action(cb, state)
        state.set_state.assert_awaited_with(NewsStates.waiting_for_edit_text)

        cb.data = "news_delete"
        state.get_data = AsyncMock(return_value={"base_chat_id": 123, "base_message_id": 1})
        fake_conn = AsyncMock()
        fake_conn.execute = AsyncMock()
        fake_conn.__aenter__.return_value = fake_conn
        with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
            await process_news_action(cb, state)
            fake_conn.execute.assert_awaited()


@pytest.mark.asyncio
async def test_process_news_photos_under_limit():
    msg = AsyncMock(spec=Message)
    msg.from_user = SimpleNamespace(id=1)
    msg.photo = [SimpleNamespace(file_id="file123")]
    msg.answer = AsyncMock()
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"file_ids": []})
    state.update_data = AsyncMock()

    with patch("handlers.news.get_user_language", return_value="ru"):
        await process_news_photos(msg, state)

    msg.answer.assert_awaited()
    state.update_data.assert_awaited()


@pytest.mark.asyncio
async def test_photos_done_with_photos():
    msg = AsyncMock(spec=Message)
    msg.from_user = SimpleNamespace(id=1)
    msg.bot.edit_message_text = AsyncMock()
    msg.bot = msg.bot
    msg.answer = AsyncMock()
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"file_ids": ["file1"], "base_chat_id": 123, "base_message_id": 123})
    state.set_state = AsyncMock()

    with patch("handlers.news.get_user_language", return_value="ru"):
        await photos_done(msg, state)

    msg.bot.edit_message_text.assert_awaited()
    state.set_state.assert_awaited()


@pytest.mark.asyncio
async def test_process_news_text():
    msg = AsyncMock(spec=Message)
    msg.text = "Hello"
    msg.from_user = SimpleNamespace(id=1)
    msg.answer = AsyncMock()
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"file_ids": ["file1"]})
    state.clear = AsyncMock()
    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.news.get_user_language", return_value="ru"):
        await process_news_text(msg, state)

    msg.answer.assert_awaited()
    fake_conn.execute.assert_awaited()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_edit_text():
    msg = AsyncMock(spec=Message)
    msg.text = "Updated news text"
    msg.from_user = SimpleNamespace(id=1)
    msg.answer = AsyncMock()
    state = AsyncMock()
    state.clear = AsyncMock()
    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.news.get_user_language", return_value="ru"):
        await process_edit_text(msg, state)

    msg.answer.assert_awaited()
    fake_conn.execute.assert_awaited()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_show_news():
    msg = AsyncMock(spec=Message)
    msg.from_user = SimpleNamespace(id=1)
    msg.answer = AsyncMock()
    msg.answer_media_group = AsyncMock()
    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=[{"id": 1, "file_ids": json.dumps(["file1"]), "text": "hello"}])
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.news.get_user_language", return_value="ru"), \
         patch("handlers.news.get_message", side_effect=lambda lang, key, **kw: key):
        await cmd_show_news(msg)

    msg.answer.assert_awaited()
    msg.answer_media_group.assert_awaited()
