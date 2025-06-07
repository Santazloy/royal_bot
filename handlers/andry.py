import re
import logging
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from aiogram import Router, F
from aiogram.types import Message
from aiogram.types import FSInputFile
from aiogram.filters import Command
from config import FIN_GROUP_IDS, ADMIN_IDS
import db

router = Router()
logger = logging.getLogger(__name__)

TRANSACTION_PATTERN = re.compile(r'^([+-])\s?(\d+)$')
UTC = timezone.utc

async def get_balance(pool, chat_id: int) -> float:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT balance FROM balances WHERE chat_id=$1", chat_id)
        if row:
            return float(row["balance"])
        else:
            await conn.execute("INSERT INTO balances (chat_id, balance) VALUES ($1, 0)", chat_id)
            return 0.0

async def update_balance(pool, chat_id: int, delta: float) -> float:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT balance FROM balances WHERE chat_id=$1", chat_id)
        if row:
            new_balance = float(row["balance"]) + delta
            await conn.execute(
                "UPDATE balances SET balance=$1, updated_at=NOW() WHERE chat_id=$2",
                new_balance, chat_id
            )
            return new_balance
        else:
            await conn.execute(
                "INSERT INTO balances (chat_id, balance) VALUES ($1, $2)",
                chat_id, delta
            )
            return delta

async def insert_transaction(pool, chat_id: int, user_id: int, ttype: str, amount: float):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO transactions (chat_id, user_id, type, amount)
            VALUES ($1, $2, $3, $4)
        """, chat_id, user_id, ttype, amount)

async def get_daily_stats(pool, chat_id: int, date: datetime) -> dict:
    start_of_day = datetime(date.year, date.month, date.day, 0, 0, 0, tzinfo=UTC)
    end_of_day = start_of_day + timedelta(days=1)
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT type, SUM(amount) as total
            FROM transactions
            WHERE chat_id=$1
              AND created_at >= $2
              AND created_at <  $3
            GROUP BY type
        """, chat_id, start_of_day, end_of_day)
    plus_total = 0.0
    minus_total = 0.0
    for row in rows:
        if row["type"] == '+':
            plus_total = float(row["total"])
        else:
            minus_total = float(row["total"])
    current_balance = await get_balance(pool, chat_id)
    net = plus_total - minus_total
    start_balance = current_balance - net
    return {
        "start_balance": start_balance,
        "plus_total": plus_total,
        "minus_total": minus_total,
        "net_result": net,
        "current_balance": current_balance
    }

async def generate_charts_example(pool, chat_id: int):
    end_date = datetime.now(tz=UTC)
    start_date = end_date - timedelta(days=7)
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT date(created_at) AS d, type, SUM(amount) as total
            FROM transactions
            WHERE chat_id=$1
              AND created_at >= $2
              AND created_at <= $3
            GROUP BY date(created_at), type
            ORDER BY d
        """, chat_id, start_date, end_date)
    data_by_day = {}
    for row in rows:
        day = row["d"]
        ttype = row["type"]
        total = float(row["total"])
        if day not in data_by_day:
            data_by_day[day] = {"plus": 0.0, "minus": 0.0}
        if ttype == '+':
            data_by_day[day]["plus"] += total
        else:
            data_by_day[day]["minus"] += total
    sorted_days = sorted(data_by_day.keys())
    plus_values = [data_by_day[d]["plus"] for d in sorted_days]
    minus_values = [data_by_day[d]["minus"] for d in sorted_days]
    day_labels = [d.strftime("%m-%d") for d in sorted_days]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    axes[0].plot(day_labels, plus_values, marker='o', label='Доходы')
    axes[0].plot(day_labels, minus_values, marker='o', label='Расходы')
    axes[0].legend()
    axes[0].set_title("Доходы/Расходы")
    total_plus = sum(plus_values)
    total_minus = sum(minus_values)
    axes[1].pie(
        [total_plus, total_minus],
        labels=['Доходы', 'Расходы'],
        autopct='%1.1f%%',
        startangle=140
    )
    axes[1].set_title("Доходы vs Расходы")
    balance_changes = [p - m for p, m in zip(plus_values, minus_values)]
    axes[2].bar(day_labels, balance_changes,
                color=['green' if bc >= 0 else 'red' for bc in balance_changes])
    axes[2].set_title("Изменение баланса")
    plt.tight_layout()
    chart_file = os.path.join(tempfile.gettempdir(), f"charts_{uuid.uuid4()}.png")
    plt.savefig(chart_file)
    plt.close(fig)
    return chart_file

@router.message(Command("one"))
async def on_one(message: Message):
    if message.chat.id not in FIN_GROUP_IDS:
        return
    stats = await get_daily_stats(db.db_pool, message.chat.id, datetime.now(tz=UTC))
    day_str = datetime.now(tz=UTC).strftime("%d.%m.%Y")
    plus_str = f"+{stats['plus_total']:,.0f} ¥" if stats['plus_total'] else "0 ¥"
    minus_str = f"-{stats['minus_total']:,.0f} ¥" if stats['minus_total'] else "0 ¥"
    net_sign = "+" if stats['net_result'] >= 0 else ""
    net_str = f"{net_sign}{stats['net_result']:,.0f} ¥"
    text = (
        f"📅 Итоги дня (UTC) ({day_str})\n"
        f"💳 Было: {stats['start_balance']:,.0f} ¥\n"
        f"💰 Заработано: {plus_str}\n"
        f"💸 Потрачено: {minus_str}\n"
        f"📊 Чистый результат: {net_str}\n"
        f"🏆 Баланс сейчас: {stats['current_balance']:,.0f} ¥\n"
        f"🚀 Завтра сделаем ещё больше!\n"
    )
    await message.answer(text)
    chart_file = await generate_charts_example(db.db_pool, message.chat.id)
    await message.answer_photo(FSInputFile(chart_file), caption="Пример графиков за 7 дней (UTC)")
    os.remove(chart_file)
    await send_financial_report(message.bot)

@router.message(Command("seven"))
async def on_seven(message: Message):
    pass

@router.message(Command("threeten"))
async def on_threeten(message: Message):
    pass

@router.message(F.chat.id.in_(FIN_GROUP_IDS) & F.text.regexp(r'^([+-])\s?\d+$'))
async def on_text(message: Message):
    text = (message.text or "").strip()
    match = TRANSACTION_PATTERN.match(text)
    if not match:
        return
    sign, number_str = match.groups()
    amount = float(number_str)
    old_balance = await get_balance(db.db_pool, message.chat.id)
    if sign == '+':
        delta = amount
        await insert_transaction(db.db_pool, message.chat.id, message.from_user.id, '+', amount)
    else:
        delta = -amount
        await insert_transaction(db.db_pool, message.chat.id, message.from_user.id, '-', amount)
    new_balance = await update_balance(db.db_pool, message.chat.id, delta)
    if delta >= 0:
        status_line = "💰 Баланс пополнен!"
        change_text = f"➕ Пополнение: {abs(delta):,.0f} ¥"
    else:
        status_line = "💰 Баланс уменьшен!"
        change_text = f"➖ Снятие: {abs(delta):,.0f} ¥"
    msg_text = (
        f"{status_line}\n"
        f"📈 Было: {old_balance:,.0f} ¥\n"
        f"{change_text}\n"
        f"💎 Итоговый баланс: {new_balance:,.0f} ¥\n"
    )
    await message.answer(msg_text)
    await send_financial_report(message.bot)

async def send_financial_report(bot):
    from handlers.money import send_financial_report as send_fin
    await send_fin(bot)
