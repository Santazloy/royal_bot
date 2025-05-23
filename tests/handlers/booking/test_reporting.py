# tests/handlers/booking/test_reporting.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import CallbackQuery
from handlers.booking.reporting import (
    update_group_message,
)
from constants.booking_const import groups_data

# Явно указываем, чтобы не было конфликта с admin_flow
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
             patch("handlers.booking.reporting.get_message", side_effect=lambda lang, key, **kw: f"{key}"):
            await reporting_module.cmd_all(cb)
            cb.answer.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in [7894353415, 7935161063, 1768520583]])


@pytest.mark.asyncio
async def test_send_booking_report():
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=[{"day": "Сегодня", "time_slot": "10:00", "user_id": 1234}])
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.booking.reporting.get_message", side_effect=lambda lang, key, **kw: "Заглушка"):
        await reporting_module.send_booking_report(bot)
        bot.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_update_group_message():
    bot = AsyncMock()
    bot.edit_message_text = AsyncMock()

    gk = next(iter(groups_data))
    groups_data[gk].update({
        "message_id": 999,
        "chat_id": 777,
        "booked_slots": {"Сегодня": [], "Завтра": []},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "time_slot_statuses": {},
        "salary": 0,
        "cash": 0,
    })

    with patch("handlers.booking.reporting.get_message", side_effect=lambda lang, key, **kw: "Группа"):
        await update_group_message(bot, gk)
        bot.edit_message_text.assert_awaited()
