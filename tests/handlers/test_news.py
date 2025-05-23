# tests/handlers/test_news.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from handlers.news import cmd_added, process_news_action, NewsStates
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
    async def simulate(uid):
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
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

        cb.answer.assert_awaited_with(get_message("ru", "cancelled"))
        state.clear.assert_awaited_once()

    await asyncio.gather(*[simulate(uid) for uid in [7894353415, 7935161063, 1768520583, 7000000001, 7000000002]])


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

        # add
        cb.data = "news_add"
        await process_news_action(cb, state)
        state.set_state.assert_awaited_with(NewsStates.waiting_for_photos)

        # edit
        cb.data = "news_edit"
        await process_news_action(cb, state)
        state.set_state.assert_awaited_with(NewsStates.waiting_for_edit_text)

        # delete
        cb.data = "news_delete"
        state.get_data = AsyncMock(return_value={"base_chat_id": 123, "base_message_id": 1})
        fake_conn = AsyncMock()
        fake_conn.execute = AsyncMock()
        fake_conn.__aenter__.return_value = fake_conn

        with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
            await process_news_action(cb, state)
            fake_conn.execute.assert_awaited()
