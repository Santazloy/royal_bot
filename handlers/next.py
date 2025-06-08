# handlers/next.py

import asyncio
import datetime
import logging
import html
from typing import Dict
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums.parse_mode import ParseMode

import db
from config import is_user_admin, FINANCIAL_REPORT_GROUP_ID
from handlers.language import get_user_language, get_message
from utils.bot_utils import safe_answer
from constants.booking_const import groups_data
from handlers.booking.reporting import update_group_message

from constants.salary import salary_options

logger = logging.getLogger(__name__)
router = Router()


async def do_next_core(bot):
    """
    1) Собираем отчёт за «Сегодня», отправляем в FINANCIAL_REPORT_GROUP_ID.
    2) Отправляем отчёты для каждой группы.
    3) Удаляем все записи «Сегодня».
    4) Очищаем in-memory для «Сегодня».
    5) Переносим «Завтра»→«Сегодня».
    6) Обновляем групповое сообщение.
    """
    async with db.db_pool.acquire() as conn:
        today_bookings = await conn.fetch("SELECT * FROM bookings WHERE day = 'Сегодня'")
        total_bookings_today = len(today_bookings)

        cash_count = cash_sum = 0
        beznal_count = beznal_sum = 0
        agent_count = agent_sum = 0

        user_bookings_count: Dict[int, int] = {}
        group_reports = {gk: {"salary_sum": 0, "cash_sum": 0} for gk in groups_data.keys()}

        for b in today_bookings:
            pm = b["payment_method"]
            amt = b["amount"] or 0
            uid = b["user_id"]
            gk = b["group_key"]
            status = b.get("status") or ""

            user_bookings_count[uid] = user_bookings_count.get(uid, 0) + 1
            opt = groups_data.get(gk, {}).get("salary_option", 1)
            base_salary = salary_options.get(opt, {}).get(status, 0)
            group_reports[gk]["salary_sum"] += base_salary

            if pm == "cash":
                cash_count += 1
                cash_sum += amt
                group_reports[gk]["cash_sum"] += amt
            elif pm == "beznal":
                beznal_count += 1
                beznal_sum += amt
            elif pm == "agent":
                agent_count += 1
                agent_sum += amt

        user_lines = []
        for uid, cnt in user_bookings_count.items():
            row = await conn.fetchrow("SELECT username FROM users WHERE user_id = $1", uid)
            uname = row["username"] if (row and row["username"]) else f"User {uid}"
            user_lines.append(f"({html.escape(uname)}) {cnt}")
        user_report = "\n".join(user_lines) if user_lines else "нет"

        report_lines = [
            "🗂️ <b>Отчет за сегодня</b> 🗂️\n",
            f"⏰ Брони: {total_bookings_today}\n",
            f"💵 Нал: {cash_count}  итог: {cash_sum}¥\n",
            f"💸 Безнал: {beznal_count}  итог: {beznal_sum}¥\n",
            f"🧮 Агент: {agent_count}  итог: {agent_sum}¥\n",
            "🏋️‍♂️ Пользователи:",
            user_report,
        ]
        report_text = "\n".join(report_lines)
        try:
            await bot.send_message(FINANCIAL_REPORT_GROUP_ID, report_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error("Не удалось отправить фин. отчет: %s", e)

        for gk, data in group_reports.items():
            ginfo = groups_data.get(gk)
            if not ginfo:
                continue
            chat_id = ginfo["chat_id"]
            salary_sum = data["salary_sum"]
            cash_sum_grp = data["cash_sum"]
            grp_lines = [
                f"📊 <b>Отчет по группе {html.escape(gk)} за сегодня</b>",
                f"💰 Заработок за день: {salary_sum}¥",
                f"💵 Наличные за день: {cash_sum_grp}¥",
            ]
            grp_text = "\n".join(grp_lines)
            try:
                await bot.send_message(chat_id, grp_text, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.warning("Не удалось отправить отчет группе %s: %s", gk, e)

        await conn.execute("DELETE FROM bookings WHERE day = 'Сегодня'")
        await conn.execute("DELETE FROM group_time_slot_statuses WHERE day = 'Сегодня'")

    for gk, ginfo in groups_data.items():
        ginfo["booked_slots"]["Сегодня"] = []
        ginfo["unavailable_slots"]["Сегодня"] = set()
        ginfo["time_slot_statuses"] = {
            (d, ts): st for ((d, ts), st) in ginfo["time_slot_statuses"].items() if d != "Сегодня"
        }
        ginfo["slot_bookers"] = {
            (d, ts): u for ((d, ts), u) in ginfo["slot_bookers"].items() if d != "Сегодня"
        }

    async with db.db_pool.acquire() as conn:
        await conn.execute("UPDATE bookings SET day = 'Сегодня' WHERE day = 'Завтра'")
        await conn.execute("UPDATE group_time_slot_statuses SET day = 'Сегодня' WHERE day = 'Завтра'")

    for gk, ginfo in groups_data.items():
        ginfo["booked_slots"]["Сегодня"] = ginfo["booked_slots"].get("Завтра", [])
        ginfo["unavailable_slots"]["Сегодня"] = ginfo["unavailable_slots"].get("Завтра", set())
        ginfo["booked_slots"]["Завтра"] = []
        ginfo["unavailable_slots"]["Завтра"] = set()

        new_tss = {}
        for (d, ts), st in ginfo["time_slot_statuses"].items():
            new_tss[("Сегодня" if d == "Завтра" else d, ts)] = st
        ginfo["time_slot_statuses"] = new_tss

        new_sb = {}
        for (d, ts), u in ginfo["slot_bookers"].items():
            new_sb[("Сегодня" if d == "Завтра" else d, ts)] = u
        ginfo["slot_bookers"] = new_sb

    for gk in groups_data.keys():
        try:
            await update_group_message(bot, gk)
        except Exception as e:
            logger.warning("Не удалось обновить сообщение группы %s: %s", gk, e)


# Обработчик кнопки сброса дня — запрашивает подтверждение
@router.callback_query(F.data == "reset_day")
async def prompt_reset_day(callback: CallbackQuery):
    user_id = callback.from_user.id
    me = await callback.bot.get_me()
    if user_id == me.id:
        return
    if not is_user_admin(user_id):
        return await callback.answer("⚠️ У вас нет прав для выполнения этого действия", show_alert=True)

    lang = await get_user_language(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_message(lang, "confirm_yes", default="Да"), callback_data="confirm_reset_day")],
        [InlineKeyboardButton(text=get_message(lang, "confirm_no",  default="Нет"), callback_data="cancel_reset_day")],
    ])
    await safe_answer(
        callback,
        get_message(lang, "reset_confirm_prompt", default="Вы уверены, что хотите сбросить день?"),
        reply_markup=kb
    )


@router.callback_query(F.data == "confirm_reset_day")
async def handle_confirm_reset(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_user_admin(user_id):
        return await callback.answer("⚠️ У вас нет прав для выполнения этого действия", show_alert=True)
    await do_next_core(callback.bot)
    lang = await get_user_language(user_id)
    await callback.answer(get_message(lang, "next_done", default="✅ Отчет сформирован, бронирования перенесены."), show_alert=True)


@router.callback_query(F.data == "cancel_reset_day")
async def handle_cancel_reset(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_user_admin(user_id):
        return await callback.answer("⚠️ У вас нет прав для выполнения этого действия", show_alert=True)
    lang = await get_user_language(user_id)
    await callback.answer(get_message(lang, "reset_cancelled", default="❌ Сброс дня отменен."), show_alert=True)


def register_daily_scheduler(dp, bot):
    async def _scheduler():
        while True:
            try:
                now = datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
                if now.hour == 3 and now.minute == 0:
                    logger.info("Авто‐сброс 03:00 Asia/Shanghai")
                    await do_next_core(bot)
                    await asyncio.sleep(61)
                else:
                    await asyncio.sleep(60)
            except Exception as e:
                logger.error("Ошибка в планировщике: %s", e)
                await asyncio.sleep(60)

    async def _on_startup():
        asyncio.create_task(_scheduler())

    dp.startup.register(_on_startup)
