import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from handlers.clean import (
    cmd_clean, process_clean_cancel, process_clean_menu,
    confirm_all_section, process_section_group_choice,
    confirm_group_section, CleanupStates
)
from handlers.language import get_message
from constants.booking_const import groups_data

@pytest.mark.asyncio
async def test_cmd_clean_multiple_users():
    async def simulate_user(uid):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.chat = SimpleNamespace(id=uid)
        msg.bot = AsyncMock()
        state = AsyncMock()
        state.update_data = AsyncMock()
        state.set_state = AsyncMock()
        import handlers.clean
        handlers.clean.is_user_admin = lambda _: True
        with patch("handlers.clean.get_user_language", return_value="ru"), \
             patch("handlers.clean.get_message", side_effect=lambda l, k, **kw: k), \
             patch("handlers.clean.safe_answer", new=AsyncMock()) as safe_mock:
            await cmd_clean(msg, state)
            safe_mock.assert_awaited()
    await asyncio.gather(*[simulate_user(uid) for uid in range(1001, 1006)])

@pytest.mark.asyncio
async def test_process_clean_cancel_multiple_users():
    async def simulate_cancel(uid):
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.message = AsyncMock()
        cb.message.delete = AsyncMock()
        cb.answer = AsyncMock()
        state = AsyncMock()
        with patch("handlers.clean.get_user_language", return_value="ru"), \
             patch("handlers.clean.get_message", side_effect=lambda l, k, **kw: k):
            await process_clean_cancel(cb, state)
            cb.answer.assert_awaited()
            state.clear.assert_awaited_once()
    await asyncio.gather(*[simulate_cancel(uid) for uid in range(1001, 1006)])

@pytest.mark.asyncio
async def test_process_clean_menu_time():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=1)
    cb.data = "clean_menu_time"
    cb.message = AsyncMock()
    cb.answer = AsyncMock()
    state = AsyncMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    with patch("handlers.clean.get_user_language", return_value="ru"), \
         patch("handlers.clean.get_message", side_effect=lambda l, k, **kw: k), \
         patch("handlers.clean.safe_answer", new=AsyncMock()) as safe_mock:
        await process_clean_menu(cb, state)
        safe_mock.assert_awaited()
        state.set_state.assert_awaited()

@pytest.mark.asyncio
async def test_confirm_all_section():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=1)
    cb.data = "confirm_all_all"
    cb.message = AsyncMock()
    cb.message.delete = AsyncMock()
    cb.answer = AsyncMock()
    cb.bot = AsyncMock()
    state = AsyncMock()
    state.clear = AsyncMock()
    for gk in groups_data:
        groups_data[gk].update({
            "salary": 100, "cash": 100,
            "booked_slots": {"Сегодня": ["10:00"], "Завтра": []},
            "slot_bookers": {("Сегодня", "10:00"): 1},
            "time_slot_statuses": {("Сегодня", "10:00"): "✅"},
            "unavailable_slots": {"Сегодня": set(), "Завтра": set()}
        })
    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn
    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.clean.get_user_language", return_value="ru"), \
         patch("handlers.clean.get_message", side_effect=lambda l, k, **kw: k), \
         patch("handlers.clean.update_group_message", new=AsyncMock()), \
         patch("handlers.clean.safe_answer", new=AsyncMock()) as safe_mock:
        await confirm_all_section(cb, state)
        safe_mock.assert_awaited()
    state.clear.assert_awaited_once()

@pytest.mark.asyncio
async def test_confirm_group_section_time():
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=1)
    cb.data = "confirm_grp_time_Royal_1"
    cb.message = AsyncMock()
    cb.message.delete = AsyncMock()
    cb.answer = AsyncMock()
    cb.bot = AsyncMock()
    state = AsyncMock()
    state.clear = AsyncMock()
    gk = "Royal_1"
    groups_data[gk]["booked_slots"]["Сегодня"] = ["10:00"]
    groups_data[gk]["slot_bookers"] = {("Сегодня", "10:00"): 1}
    groups_data[gk]["time_slot_statuses"] = {("Сегодня", "10:00"): "✅"}
    groups_data[gk]["unavailable_slots"] = {"Сегодня": set(), "Завтра": set()}
    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn
    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
         patch("handlers.clean.get_user_language", return_value="ru"), \
         patch("handlers.clean.get_message", side_effect=lambda l, k, **kw: k), \
         patch("handlers.clean.update_group_message", new=AsyncMock()), \
         patch("handlers.clean.safe_answer", new=AsyncMock()) as safe_mock:
        await confirm_group_section(cb, state)
        safe_mock.assert_awaited()
    state.clear.assert_awaited_once()
