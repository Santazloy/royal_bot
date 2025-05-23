# tests/handlers/booking/test_admin_flow.py
from types import SimpleNamespace
import pytest
from unittest.mock import AsyncMock, patch
from handlers.booking.rewards import (
    apply_special_user_reward,
    update_user_financial_info,
    apply_additional_payment
)
from constants.booking_const import SPECIAL_USER_ID


@pytest.mark.asyncio
async def test_apply_special_user_reward():
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={"balance": 100})
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
        await apply_special_user_reward("0", bot)
        fake_conn.execute.assert_awaited()
        bot.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_update_user_financial_info():
    bot = AsyncMock()
    bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(user=SimpleNamespace(
        username="tester", first_name="Test", last_name="User"
    )))

    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={
        "balance": 100,
        "profit": 50,
        "monthly_profit": 20
    })
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
        await update_user_financial_info(1234, 200, bot)
        fake_conn.execute.assert_awaited()


@pytest.mark.asyncio
async def test_apply_additional_payment():
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    fake_conn = AsyncMock()
    fake_conn.fetchrow = AsyncMock(return_value={"balance": 100})
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
        await apply_additional_payment(SPECIAL_USER_ID, "0", bot)
        fake_conn.execute.assert_awaited()
        bot.send_message.assert_awaited()
