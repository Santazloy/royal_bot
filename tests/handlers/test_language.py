#tests/handlers/test_language.py

import pytest
import asyncio
from unittest.mock import AsyncMock
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from handlers.language import get_user_language, set_user_language, get_message, cmd_lang, callback_set_language

@pytest.mark.asyncio
async def test_get_set_user_language_multiple_users():
    import db
    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={"language": "en"})
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    db.db_pool = type("Pool", (), {"acquire": lambda self: fake_conn})()

    async def simulate(uid):
        lang = await get_user_language(uid)
        assert lang == "en"
        await set_user_language(uid, "ru")
        fake_conn.execute.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in range(1001, 1006)])


def test_get_message_formatting():
    msg = get_message("en", "choose_time_styled", day="Monday")
    assert "Monday" in msg


@pytest.mark.asyncio
async def test_cmd_lang_multiple_users():
    async def simulate(uid):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.answer = AsyncMock()
        await cmd_lang(msg)
        msg.answer.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in range(1001, 1006)])


@pytest.mark.asyncio
async def test_callback_set_language_multiple_users():
    async def simulate(uid):
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.data = "setlang_en"
        cb.answer = AsyncMock()
        await callback_set_language(cb)
        cb.answer.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in range(1001, 1006)])
