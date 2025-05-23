# tests/handlers/booking/test_admin_flow.py
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardMarkup
from handlers.booking.admin_flow import admin_click_slot, admin_click_status
from constants.booking_const import status_mapping, groups_data

@pytest.mark.asyncio
async def test_admin_click_slot_shows_status_buttons(monkeypatch):
    # Подготовка CallbackQuery
    gk = next(iter(groups_data))
    day, slot = "Сегодня", "10:00"
    cb = AsyncMock()
    cb.data = f"group_time|{gk}|{day}|{slot}"
    cb.message = AsyncMock()
    cb.from_user = SimpleNamespace(id=111)
    # Настроим права: чат_id совпадает и юзер — админ
    groups_data[gk]["chat_id"] = 999
    cb.message.chat = SimpleNamespace(id=999)
    member = SimpleNamespace(status="administrator")
    monkeypatch.setattr(cb.bot, "get_chat_member", AsyncMock(return_value=member))

    # Запуск
    await admin_click_slot(cb)

    # Проверка: edit_text вызван с InlineKeyboardMarkup
    cb.message.edit_text.assert_awaited_once()
    _, kwargs = cb.message.edit_text.call_args
    assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_admin_click_status_assigns_and_updates(monkeypatch):
    # Подготовка CallbackQuery
    gk = next(iter(groups_data))
    day, slot, code = "Сегодня", "10:00", next(iter(status_mapping))
    cb = AsyncMock()
    cb.data = f"group_status|{gk}|{day}|{slot}|{code}"
    cb.message = AsyncMock()
    cb.from_user = SimpleNamespace(id=111)
    groups_data[gk]["chat_id"] = 999
    cb.message.chat = SimpleNamespace(id=999)
    member = SimpleNamespace(status="creator")
    monkeypatch.setattr(cb.bot, "get_chat_member", AsyncMock(return_value=member))

    # Исправленный фейковый пул
    import db
    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={"balance": 100})
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn
    fake_conn.__aexit__.return_value = None

    class FakePool:
        def acquire(self):
            return fake_conn

    db.db_pool = FakePool()

    # Запуск
    await admin_click_status(cb)

    # Проверка
    cb.message.edit_text.assert_awaited()
