# tests/handlers/booking/test_user_flow.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import CallbackQuery, Message
from handlers.booking.user_flow import (
    user_select_group,
    user_select_day,
    user_select_time
)
from app_states import BookUserStates
from constants.booking_const import groups_data


@pytest.mark.asyncio
async def test_user_select_group_multiple_users():
    async def simulate(uid):
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.data = "bkgrp_Royal_1"
        cb.message = AsyncMock()
        cb.message.edit_media = AsyncMock()
        cb.message.answer_photo = AsyncMock()
        cb.bot = AsyncMock()
        cb.answer = AsyncMock()

        state = AsyncMock()
        await user_select_group(cb, state)
        cb.answer.assert_awaited()
        state.set_state.assert_awaited_with(BookUserStates.waiting_for_day)

    await asyncio.gather(*[simulate(uid) for uid in range(1001, 1006)])


@pytest.mark.asyncio
async def test_user_select_day():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=1)
    cb.data = "bkday_Сегодня"
    cb.message = AsyncMock()
    cb.message.edit_media = AsyncMock()
    cb.message.answer_photo = AsyncMock()
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"selected_group": "Royal_1"})
    with patch("handlers.booking.user_flow.get_user_language", return_value="ru"):
        await user_select_day(cb, state)
    cb.answer.assert_awaited()
    state.set_state.assert_awaited_with(BookUserStates.waiting_for_time)


@pytest.mark.asyncio
async def test_user_select_time():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=1)
    cb.data = "bkslot_10_00"
    cb.message = AsyncMock()
    cb.message.edit_media = AsyncMock()
    cb.message.answer_photo = AsyncMock()
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()

    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    groups_data["Royal_1"]["booked_slots"]["Сегодня"] = []
    groups_data["Royal_1"]["unavailable_slots"]["Сегодня"] = set()
    groups_data["Royal_1"]["time_slot_statuses"] = {}
    groups_data["Royal_1"]["slot_bookers"] = {}

    state = AsyncMock()
    state.get_data = AsyncMock(return_value={
        "selected_group": "Royal_1",
        "selected_day": "Сегодня"
    })

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.booking.user_flow.get_user_language", return_value="ru"), \
         patch("handlers.booking.user_flow.update_group_message", new_callable=AsyncMock), \
         patch("handlers.booking.user_flow.send_booking_report", new_callable=AsyncMock), \
         patch("handlers.booking.user_flow.repo.add_booking", new_callable=AsyncMock), \
         patch("handlers.booking.user_flow.data_mgr.book_slot", new_callable=AsyncMock):
        await user_select_time(cb, state)
        cb.answer.assert_awaited()
        state.clear.assert_awaited_once()
