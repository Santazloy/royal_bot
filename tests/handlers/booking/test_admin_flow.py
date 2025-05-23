# tests/handlers/booking/test_admin_flow.py

import pytest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import CallbackQuery
from handlers.booking.admin_flow import admin_click_slot, admin_click_status
from constants.booking_const import groups_data


@pytest.mark.asyncio
async def test_admin_click_slot_access_granted():
    gk = next(iter(groups_data))
    groups_data[gk]["chat_id"] = 999
    cb = AsyncMock(spec=CallbackQuery)
    cb.data = f"group_time|{gk}|Сегодня|10:00"
    cb.message = AsyncMock()
    cb.message.chat = SimpleNamespace(id=999)
    cb.from_user = SimpleNamespace(id=111)
    cb.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="administrator"))
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()

    await admin_click_slot(cb)
    cb.answer.assert_awaited()
    cb.message.edit_text.assert_awaited()


@pytest.mark.asyncio
async def test_admin_click_slot_no_access():
    gk = next(iter(groups_data))
    groups_data[gk]["chat_id"] = 999
    cb = AsyncMock(spec=CallbackQuery)
    cb.data = f"group_time|{gk}|Сегодня|10:00"
    cb.message = AsyncMock()
    cb.message.chat = SimpleNamespace(id=999)
    cb.from_user = SimpleNamespace(id=111)
    cb.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="member"))
    cb.answer = AsyncMock()

    await admin_click_slot(cb)
    cb.answer.assert_awaited()


@pytest.mark.asyncio
async def test_admin_click_status_back():
    gk = next(iter(groups_data))
    groups_data[gk]["chat_id"] = 999
    cb = AsyncMock(spec=CallbackQuery)
    cb.data = f"group_status|{gk}|Сегодня|10:00|back"
    cb.message = AsyncMock()
    cb.message.chat = SimpleNamespace(id=999)
    cb.from_user = SimpleNamespace(id=111)
    cb.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="creator"))
    cb.answer = AsyncMock()

    with patch("handlers.booking.admin_flow.update_group_message", new_callable=AsyncMock):
        await admin_click_status(cb)
        cb.answer.assert_awaited()


@pytest.mark.asyncio
async def test_admin_click_status_cancel():
    gk = next(iter(groups_data))
    groups_data[gk]["chat_id"] = 999
    groups_data[gk]["booked_slots"]["Сегодня"] = ["10:00"]
    groups_data[gk]["slot_bookers"][("Сегодня", "10:00")] = 123
    groups_data[gk]["unavailable_slots"]["Сегодня"] = {"10:30"}
    groups_data[gk]["time_slot_statuses"][("Сегодня", "10:30")] = "✅"

    cb = AsyncMock(spec=CallbackQuery)
    cb.data = f"group_status|{gk}|Сегодня|10:00|-1"
    cb.message = AsyncMock()
    cb.message.chat = SimpleNamespace(id=999)
    cb.from_user = SimpleNamespace(id=123)
    cb.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="creator"))
    cb.answer = AsyncMock()

    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.booking.admin_flow.update_group_message", new_callable=AsyncMock):
        await admin_click_status(cb)
        cb.answer.assert_awaited()
        fake_conn.execute.assert_awaited()


@pytest.mark.asyncio
async def test_admin_click_status_set_status():
    gk = next(iter(groups_data))
    groups_data[gk]["chat_id"] = 999
    groups_data[gk]["slot_bookers"][("Сегодня", "10:00")] = 123

    cb = AsyncMock(spec=CallbackQuery)
    cb.data = f"group_status|{gk}|Сегодня|10:00|0"
    cb.message = AsyncMock()
    cb.message.chat = SimpleNamespace(id=999)
    cb.from_user = SimpleNamespace(id=123)
    cb.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="creator"))
    cb.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()

    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.booking.rewards.apply_special_user_reward", new_callable=AsyncMock):
        await admin_click_status(cb)
        cb.answer.assert_awaited()
        cb.message.edit_text.assert_awaited()
