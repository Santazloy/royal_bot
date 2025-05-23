# tests/handlers/booking/test_payment_flow.py

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from aiogram.types import CallbackQuery, Message
import handlers.booking.payment_flow as pf
import handlers.booking.rewards as rewards_module
from handlers.booking.payment_flow import (
    process_payment_method,
    handle_agent_payment,
    process_payment_amount,
)
from app_states import BookPaymentStates
from constants.booking_const import status_mapping, groups_data

@pytest.mark.asyncio
async def test_process_payment_method_sets_amount_state(monkeypatch):
    gk, day, slot, code, method = next(iter(groups_data)), "Сегодня", "10:00", "0", "cash"
    cb = AsyncMock(spec=CallbackQuery)
    cb.data = f"payment_method|{gk}|{day}|{slot}|{code}|{method}"
    cb.from_user = SimpleNamespace(id=456)
    groups_data[gk]["chat_id"] = 789
    cb.message = SimpleNamespace(chat=SimpleNamespace(id=789), message_id=1)

    # Мокаем get_user_language и права
    monkeypatch.setattr(pf, 'get_user_language', AsyncMock(return_value='ru'))
    monkeypatch.setattr(cb.bot, 'get_chat_member', AsyncMock(return_value=SimpleNamespace(status='creator')))
    monkeypatch.setattr(cb.bot, 'edit_message_text', AsyncMock())

    # Фейковый пул БД
    import db
    fake_conn = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn
    fake_conn.__aexit__.return_value = None
    fake_conn.fetchrow = AsyncMock(return_value={'user_id': 111})
    fake_conn.execute = AsyncMock()
    class FakePool:
        def acquire(self):
            return fake_conn
    db.db_pool = FakePool()

    state = AsyncMock()
    await process_payment_method(cb, state)

    state.update_data.assert_awaited_once_with(
        group_key=gk, day=day, time_slot=slot, status_code=code, payment_method=method
    )
    state.set_state.assert_awaited_once_with(BookPaymentStates.waiting_for_amount)


@pytest.mark.asyncio
async def test_handle_agent_payment_updates_and_sends(monkeypatch):
    gk, day, slot, code = next(iter(groups_data)), "Сегодня", "10:00", "0"
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = SimpleNamespace(id=222)
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()
    groups_data[gk]["chat_id"] = 789
    cb.message = SimpleNamespace(chat=SimpleNamespace(id=789))

    # Подменяем вызовы внутри
    monkeypatch.setattr(pf, 'get_user_language', AsyncMock(return_value='ru'))
    monkeypatch.setattr(pf, 'update_user_financial_info', AsyncMock())
    monkeypatch.setattr(pf, 'apply_additional_payment', AsyncMock())
    monkeypatch.setattr(pf, 'update_group_message', AsyncMock())
    monkeypatch.setattr(pf, 'send_financial_report', AsyncMock())

    # Фейковый пул БД с нужными полями
    import db
    fake_conn = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn
    fake_conn.__aexit__.return_value = None
    # сначала возвращает user_id, потом balance
    fake_conn.fetchrow = AsyncMock(side_effect=[{'user_id': 333}, {'balance': 500}])
    fake_conn.execute = AsyncMock()
    class FakePool2:
        def acquire(self):
            return fake_conn
    db.db_pool = FakePool2()

    await handle_agent_payment(cb, gk, day, slot, code)

    assert cb.bot.send_message.await_count >= 1
    cb.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_payment_amount_updates_booking(monkeypatch):
    msg = AsyncMock(spec=Message)
    msg.from_user = SimpleNamespace(id=333)
    msg.text = "123"
    msg.answer = AsyncMock()
    msg.bot = AsyncMock()

    state = AsyncMock()
    state.get_data.return_value = {
        'group_key': next(iter(groups_data)),
        'day': 'Сегодня',
        'time_slot': '10:00',
        'status_code': '0',
        'payment_method': 'cash'
    }

    # Подменяем утилиты
    monkeypatch.setattr(pf, 'get_user_language', AsyncMock(return_value='ru'))
    monkeypatch.setattr(rewards_module, 'update_user_financial_info', AsyncMock())
    monkeypatch.setattr(rewards_module, 'apply_additional_payment', AsyncMock())
    monkeypatch.setattr(pf, 'update_group_message', AsyncMock())
    monkeypatch.setattr(pf, 'send_financial_report', AsyncMock())

    # Фейковый пул БД
    import db
    fake_conn = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn
    fake_conn.__aexit__.return_value = None
    fake_conn.fetchrow = AsyncMock(side_effect=[{'user_id': 444}, {'balance': 800}])
    fake_conn.execute = AsyncMock()
    class FakePool3:
        def acquire(self):
            return fake_conn
    db.db_pool = FakePool3()

    await process_payment_amount(msg, state)

    state.clear.assert_awaited_once()
    msg.answer.assert_awaited_once()
