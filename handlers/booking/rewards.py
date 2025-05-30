# handlers/booking/rewards.py

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
import db
from constants.booking_const import special_payments, SPECIAL_USER_ID
from utils.bot_utils import last_bot_message
from utils.text_utils import format_html_pre

async def send_tracked(bot: Bot, chat_id: int, **kwargs):
    """
    Sends a message to chat_id, deleting the previous bot message for that chat first.
    Tracks the last sent message in last_bot_message.
    """
    prev = last_bot_message.get(chat_id)
    if prev:
        try:
            await bot.delete_message(chat_id, prev)
        except:
            pass

    try:
        sent = await bot.send_message(chat_id, **kwargs)
        last_bot_message[chat_id] = sent.message_id
        return sent
    except TelegramForbiddenError:
        # cannot initiate conversation with user — skip silently
        return None

async def apply_special_user_reward(status_code: str, bot: Bot):
    amount = special_payments.get(status_code, 0)
    if amount <= 0 or not db.db_pool:
        return

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT balance FROM users WHERE user_id=$1",
            SPECIAL_USER_ID
        )
        balance = row.get("balance") if row else 0
        balance = balance if isinstance(balance, (int, float)) else 0
        new = balance + amount

        if row:
            await conn.execute(
                "UPDATE users SET balance=$1 WHERE user_id=$2",
                new, SPECIAL_USER_ID
            )
        else:
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1, $2, $3, $3, $3)",
                SPECIAL_USER_ID, "Special User", amount
            )

    text = f"Вам начислено дополнительно {amount}¥.\nТекущий баланс: {new}¥"
    await send_tracked(bot, SPECIAL_USER_ID, text=text)

async def update_user_financial_info(user_id: int, net_amount: int, bot: Bot):
    if not db.db_pool:
        return

    try:
        member = await bot.get_chat_member(user_id, user_id)
        uname = member.user.username or f"{member.user.first_name} {member.user.last_name}"
    except:
        uname = f"User_{user_id}"

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT balance, profit, monthly_profit FROM users WHERE user_id=$1",
            user_id
        )

        if row:
            b = row.get("balance", 0) or 0
            p = row.get("profit", 0) or 0
            m = row.get("monthly_profit", 0) or 0
            nb, np, nm = b + net_amount, p + net_amount, m + net_amount
            await conn.execute(
                "UPDATE users SET balance=$1, profit=$2, monthly_profit=$3, username=$4 WHERE user_id=$5",
                nb, np, nm, uname, user_id
            )
        else:
            nb = net_amount
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1,$2,$3,$3,$3)",
                user_id, uname, net_amount
            )

    # Notify user of their updated balance
    msg = format_html_pre(f"Ваш баланс изменён на {net_amount:+}. Текущий баланс: {nb}")
    await send_tracked(bot, user_id, text=msg, parse_mode="HTML")

async def apply_additional_payment(user_id: int, status_code: str, bot: Bot):
    if user_id != SPECIAL_USER_ID:
        return

    extra = special_payments.get(status_code, 0)
    if extra <= 0 or not db.db_pool:
        return

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT balance FROM users WHERE user_id=$1",
            user_id
        )
        balance = row.get("balance") if row else 0
        balance = balance if isinstance(balance, (int, float)) else 0
        newb = balance + extra

        if row:
            await conn.execute(
                "UPDATE users SET balance=$1 WHERE user_id=$2",
                newb, user_id
            )
        else:
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1, $2, $3, $3, $3)",
                user_id, "Special User", extra
            )

    text = f"<pre>Вам начислено дополнительно {extra}¥.\nВаш текущий баланс: {newb}¥</pre>"
    await send_tracked(bot, user_id, text=text, parse_mode="HTML")
