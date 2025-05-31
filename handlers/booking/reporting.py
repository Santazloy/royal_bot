# handlers/booking/reporting.py
from aiogram import F
from aiogram import Bot
from aiogram.types import CallbackQuery, Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

import logging, html
from handlers.language import get_user_language, get_message
import db
from constants.booking_const import (
    BOOKING_REPORT_GROUP_ID,
    FINANCIAL_REPORT_GROUP_ID,
    groups_data
)
from utils.text_utils import format_html_pre
from utils.time_utils import generate_daily_time_slots as generate_time_slots
from aiogram import Router
router = Router()

logger = logging.getLogger(__name__)

async def send_booking_report(bot: Bot, uid: int, gk: str, slot: str, day: str):
    username = f"User {uid}"
    user_emoji = "❓"
    if db.db_pool:
        try:
            async with db.db_pool.acquire() as con:
                row = await con.fetchrow(
                    "SELECT u.username, e.emoji "
                    "FROM users u LEFT JOIN user_emojis e ON u.user_id=e.user_id "
                    "WHERE u.user_id=$1",
                    uid,
                )
                if row:
                    username = row["username"] or username
                    user_emoji = (row["emoji"] or "").split(",")[0] or user_emoji
        except Exception as e:
            logger.error(e)

    body = (
        f"📅 Новый Booking\n"
        f"👤 Пользователь: {user_emoji} {html.escape(username)}\n"
        f"🌹 Группа: {gk}\n"
        f"⏰ Время: {slot} ({day})"
    )
    await bot.send_message(
        chat_id=BOOKING_REPORT_GROUP_ID,
        text=f"<pre>{body}</pre>",
        parse_mode=ParseMode.HTML,
    )

async def update_group_message(bot: Bot, group_key: str):
    ginfo = groups_data[group_key]
    chat_id = ginfo["chat_id"]
    user_lang = "ru"

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"━━━━━━  🌹🌹 {group_key} 🌹🌹  ━━━━━━",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Зп: {ginfo.get('salary',0)}¥",
        f"Нал: {ginfo.get('cash',0)}¥",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "⏰ Booking report ⏰",
    ]

    async def get_user_emoji(uid: int) -> str:
        if not db.db_pool:
            return "❓"
        try:
            async with db.db_pool.acquire() as con:
                row = await con.fetchrow("SELECT emoji FROM user_emojis WHERE user_id=$1", uid)
                if row and row["emoji"]:
                    return row["emoji"].split(",")[0]
        except:
            pass
        return "❓"

    final_statuses = {'❌❌❌','✅','✅2','✅✅','✅✅✅'}
    for day in ("Сегодня", "Завтра"):
        lines.append(f"\n{day}:")
        for slot in generate_time_slots():
            st = ginfo["time_slot_statuses"].get((day, slot))
            if st in final_statuses:
                uid = ginfo["slot_bookers"].get((day, slot))
                ue = await get_user_emoji(uid)
                lines.append(f"{slot} {st} {ue}")

    text = format_html_pre("\n".join(lines))

    old_id = ginfo.get("message_id")
    if old_id:
        try:
            await bot.delete_message(chat_id, old_id)
        except:
            pass

    builder = InlineKeyboardBuilder()
    for day in ("Сегодня","Завтра"):
        for slot in generate_time_slots():
            if ginfo["time_slot_statuses"].get((day, slot)) == "booked":
                builder.button(
                    text=f"{day} {slot}",
                    callback_data=f"group_time|{group_key}|{day}|{slot}"
                )
        builder.button(text="──────────", callback_data="ignore")
    builder.adjust(1)
    kb = builder.as_markup()

    msg = await bot.send_message(
        chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=kb
    )
    ginfo["message_id"] = msg.message_id

    if db.db_pool:
        async with db.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE group_financial_data SET message_id=$1 WHERE group_key=$2",
                msg.message_id, group_key
            )

async def send_financial_report(bot: Bot):
    if not db.db_pool:
        return
    total_sal = sum(g["salary"] for g in groups_data.values())
    total_cash = sum(g["cash"] for g in groups_data.values())

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT balance FROM users")
    users_total = sum(r["balance"] for r in rows) if rows else 0

    itog1 = total_cash - total_sal
    lines = ["═══ 📊 Сводный фин. отчёт 📊 ═══\n"]
    for k, g in groups_data.items():
        lines += [f"[{k}] Зп: {g['salary']}¥ | Нал: {g['cash']}¥",
                  "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines += [
        f"\nИтого зарплата: {total_sal}¥",
        f"Итого наличные: {total_cash}¥",
        f"Итог1 (cash - salary): {itog1}¥",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.user_id, u.username, u.balance, e.emoji
            FROM users u LEFT JOIN user_emojis e ON u.user_id=e.user_id
            ORDER BY u.user_id
        """)
    if rows:
        lines.append("═════ 👥 Пользователи 👥 ═════\n")
        for r in rows:
            uname = r["username"] or f"User {r['user_id']}"
            lines += [f"{(r['emoji'] or '❓')} {uname}: {r['balance']}¥",
                      "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n",
        f"Сумма балансов пользователей: {users_total}¥",
        f"━━━━ TOTAL (итог1 - балансы) = {itog1 - users_total}¥ ━━━━"
    ]
    report = "<pre>" + "\n".join(lines) + "</pre>"
    try:
        await bot.send_message(FINANCIAL_REPORT_GROUP_ID, report, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка фин. отчёта: {e}")

@router.callback_query(F.data == "view_all_bookings")
async def cmd_all(cb: CallbackQuery):
    lang = await get_user_language(cb.from_user.id)


    group_times = {}
    for gk, g in groups_data.items():
        for d in ("Сегодня", "Завтра"):
            ts = g["booked_slots"].get(d, [])
            if ts:
                group_times.setdefault(gk, {})[d] = ts

    if not group_times:
        text = get_message(lang, "no_active_bookings")
        try:
            await cb.message.edit_text(text)
        except TelegramBadRequest:
            await safe_delete_and_answer(cb.message, text)
        return await cb.answer()

    lines = []
    for day in ("Сегодня", "Завтра"):
        disp = get_message(lang, "today") if day == "Сегодня" else get_message(lang, "tomorrow")
        lines.append(f"📅 {get_message(lang,'all_bookings_title',day=disp)}")
        if not any(day in v for v in group_times.values()):
            lines += [get_message(lang, "no_bookings"), ""]
            continue

        lines += [
            "╔══════════╦════════════════════╗",
            "║ Группа   ║ Время бронирования ║",
            "╠══════════╬════════════════════╣",
        ]
        for gk, td in group_times.items():
            for s in td.get(day, []):
                lines.append(f"║ {gk:<9}║ {s:<18}║")
            lines.append("╠══════════╬════════════════════╣")
        lines[-1] = lines[-1].replace("╠", "╚", 1).replace("╣", "╝", 1)
        lines.append("")

    text = format_html_pre("\n".join(lines))
    try:
        await cb.message.edit_text(text, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        await safe_delete_and_answer(cb.message, text)
    await cb.answer()

async def safe_delete_and_answer(msg: Message, text: str):
    try:
        await msg.delete()
    except:
        pass
    await msg.answer(text, parse_mode=ParseMode.HTML)
