# tests/handlers/booking/test_payment_flow.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiogram.types import CallbackQuery, Message

from handlers.booking.payment_flow import (
    process_payment_method,
    handle_agent_payment,
    process_payment_amount,
)
from states import BookPaymentStates
from constants.booking_const import groups_data


@pytest.mark.asyncio
async def test_process_payment_method_multiple_users():
    async def simulate(uid):
        gk, day, slot, code, method = next(iter(groups_data)), "Сегодня", "10:00", "0", "cash"
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.message = AsyncMock()
        cb.message.chat = SimpleNamespace(id=groups_data[gk]["chat_id"])
        cb.data = f"payment_method|{gk}|{day}|{slot}|{code}|{method}"
        cb.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="creator"))
        cb.bot.edit_message_text = AsyncMock()
        cb.answer = AsyncMock()

        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value={"user_id": uid})
        fake_conn.__aenter__.return_value = fake_conn
        db_mock = type("Pool", (), {"acquire": lambda self: fake_conn})()

        with patch("db.db_pool", new=db_mock), \
             patch("handlers.booking.payment_flow.get_user_language", return_value="ru"):
            state = AsyncMock()
            await process_payment_method(cb, state)
            state.update_data.assert_awaited()
            state.set_state.assert_awaited_with(BookPaymentStates.waiting_for_amount)

    await asyncio.gather(*[simulate(uid) for uid in range(1001, 1006)])


@pytest.mark.asyncio
async def test_handle_agent_payment_multiple_users():
    async def simulate(uid):
        gk, day, slot, code = next(iter(groups_data)), "Сегодня", "10:00", "0"
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.bot = AsyncMock()
        cb.message = AsyncMock()
        cb.message.chat = SimpleNamespace(id=groups_data[gk]["chat_id"])
        cb.answer = AsyncMock()

        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value={"user_id": uid})
        fake_conn.execute = AsyncMock()
        fake_conn.__aenter__.return_value = fake_conn

        with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
             patch("handlers.booking.payment_flow.get_user_language", return_value="ru"), \
             patch("handlers.booking.payment_flow.update_user_financial_info", new=AsyncMock()), \
             patch("handlers.booking.payment_flow.send_financial_report", new=AsyncMock()), \
             patch("handlers.booking.payment_flow.update_group_message", new=AsyncMock()):

            await handle_agent_payment(cb, gk, day, slot, code)
            cb.answer.assert_awaited()
            cb.bot.send_message.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in range(1001, 1006)])

@pytest.mark.asyncio
async def test_process_payment_amount_multiple_users():
    async def simulate(uid):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.text = "1200"
        msg.answer = AsyncMock()
        msg.reply = AsyncMock()
        msg.bot = AsyncMock()

        gk = next(iter(groups_data))
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={
            "group_key": gk,
            "day": "Сегодня",
            "time_slot": "10:00",
            "status_code": "0",
            "payment_method": "cash",
        })

        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(side_effect=[
            {"user_id": uid},   # первый fetchrow
            {"balance": 1000}   # второй fetchrow
        ])
        fake_conn.execute = AsyncMock()
        fake_conn.__aenter__.return_value = fake_conn

        with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()), \
             patch("handlers.booking.payment_flow.get_user_language", return_value="ru"), \
             patch("handlers.booking.payment_flow.update_user_financial_info", new=AsyncMock()), \
             patch("handlers.booking.payment_flow.update_group_message", new=AsyncMock()), \
             patch("handlers.booking.payment_flow.send_financial_report", new=AsyncMock()):

            await process_payment_amount(msg, state)
            state.clear.assert_awaited()
            msg.answer.assert_awaited()

    await asyncio.gather(*[simulate(uid) for uid in range(1001, 1006)])
