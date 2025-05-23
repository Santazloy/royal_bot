# handlers/booking/rewards.py

from aiogram import Bot
import db
from constants.booking_const import special_payments, SPECIAL_USER_ID

async def apply_special_user_reward(status_code: str, bot: Bot):
    amount = special_payments.get(status_code, 0)
    if amount <= 0 or not db.db_pool:
        return
    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT balance FROM users WHERE user_id=$1",
            SPECIAL_USER_ID
        )
        if row:
            new = row.get("balance", 0) + amount
            await conn.execute(
                "UPDATE users SET balance=$1 WHERE user_id=$2",
                new, SPECIAL_USER_ID
            )
        else:
            new = amount
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1,$2,$3,$3,$3)",
                SPECIAL_USER_ID, "Special User", amount
            )
    try:
        await bot.send_message(
            SPECIAL_USER_ID,
            f"Вам начислено дополнительно {amount}¥.\nТекущий баланс: {new}¥"
        )
    except:
        pass

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
            b = row.get("balance", 0)
            p = row.get("profit", 0)
            m = row.get("monthly_profit", 0)
            nb, np, nm = b + net_amount, p + net_amount, m + net_amount
            await conn.execute(
                "UPDATE users SET balance=$1, profit=$2, monthly_profit=$3, username=$4 "
                "WHERE user_id=$5",
                nb, np, nm, uname, user_id
            )
        else:
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1,$2,$3,$3,$3)",
                user_id, uname, net_amount
            )

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
        if row:
            newb = row.get("balance", 0) + extra
            await conn.execute(
                "UPDATE users SET balance=$1 WHERE user_id=$2",
                newb, user_id
            )
        else:
            newb = extra
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1,$2,$3,$3,$3)",
                user_id, "Special User", extra
            )
    try:
        await bot.send_message(
            user_id,
            f"<pre>Вам начислено дополнительно {extra}¥.\nВаш текущий баланс: {newb}¥</pre>",
            parse_mode="HTML"
        )
    except:
        pass
