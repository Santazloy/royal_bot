# tests/handlers/booking/test_reporting.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import CallbackQuery
from handlers.booking.reporting import (
    update_group_message,
    send_financial_report
)
from constants.booking_const import groups_data, BOOKING_REPORT_GROUP_ID

from handlers.booking import reporting as reporting_module

@pytest.mark.asyncio
async def test_cmd_all_multiple_admins():
    async def simulate(uid):
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.data = "all_bookings"
        cb.message = AsyncMock()
        cb.message.chat = SimpleNamespace(id=123)
        cb.answer = AsyncMock()

        fake_conn = AsyncMock()
        fake_conn.fetch = AsyncMock(return_value=[])
        fake_conn.__aenter__.return_value = fake_conn

        with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
             patch("handlers.booking.reporting.get_user_language", return_value="ru"), \
             patch("handlers.booking.reporting.get_message", side_effect=lambda lang, key, **kw: f"{key}"), \
             patch("handlers.booking.reporting.safe_delete_and_answer", new=AsyncMock()):
            await reporting_module.cmd_all(cb)
            cb.answer.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in [7894353415, 7935161063, 1768520583]])


@pytest.mark.asyncio
async def test_send_booking_report():
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={"username": "TestUser", "emoji": "😊"})
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
        await reporting_module.send_booking_report(bot, 1234, "Royal_1", "10:00", "Сегодня")

    args, kwargs = bot.send_message.await_args
    assert kwargs["chat_id"] == BOOKING_REPORT_GROUP_ID
    assert "TestUser" in kwargs["text"]


@pytest.mark.asyncio
async def test_update_group_message():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    bot.delete_message = AsyncMock()

    gk = next(iter(groups_data))
    groups_data[gk].update({
        "message_id": 999,
        "chat_id": 777,
        "booked_slots": {"Сегодня": ["10:00"], "Завтра": []},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "time_slot_statuses": {("Сегодня", "10:00"): "✅"},
        "slot_bookers": {("Сегодня", "10:00"): 1234},
        "salary": 0,
        "cash": 0,
    })

    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={"emoji": "😎"})
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.booking.reporting.get_message", side_effect=lambda lang, key, **kw: "Группа"):
        await update_group_message(bot, gk)
        bot.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_send_financial_report():
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=[
        {"user_id": 1, "username": "Test", "balance": 500, "emoji": "✅"}
    ])
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
        await send_financial_report(bot)
        bot.send_message.assert_awaited()
