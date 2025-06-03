# handlers/next.py

import logging
from typing import Dict

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command

import db
from config import is_user_admin, FINANCIAL_REPORT_GROUP_ID
from handlers.language import get_user_language, get_message
from utils.bot_utils import safe_answer
from constants.booking_const import groups_data
from handlers.booking.reporting import update_group_message

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("next"))
async def cmd_next(message: Message, state: FSMContext):
    """
    Сформировать отчёт за "Сегодня" и перенести все "Завтра" → "Сегодня".
    Работает только для администраторов.
    """
    user_id = message.from_user.id
    user_lang = await get_user_language(user_id)

    # Проверяем, что пользователь — админ
    if not is_user_admin(user_id):
        await message.reply(get_message(user_lang, "no_permission"))
        return

    # Захватываем соединение из пула
    async with db.db_pool.acquire() as conn:
        # 1) Собираем данные за «Сегодня»
        today_bookings = await conn.fetch("SELECT * FROM bookings WHERE day = 'Сегодня'")
        total_bookings_today = len(today_bookings)

        cash_count = cash_sum = 0
        beznal_count = beznal_sum = 0
        agent_count = agent_sum = 0

        user_bookings_count: Dict[int, int] = {}

        for b in today_bookings:
            pm = b["payment_method"]
            amt = b["amount"] or 0
            uid = b["user_id"]

            user_bookings_count[uid] = user_bookings_count.get(uid, 0) + 1

            if pm == "cash":
                cash_count += 1
                cash_sum += amt
            elif pm == "beznal":
                beznal_count += 1
                beznal_sum += amt
            elif pm == "agent":
                agent_count += 1
                agent_sum += amt

        # Формируем строку по пользователям
        user_lines = []
        for uid, cnt in user_bookings_count.items():
            row_user = await conn.fetchrow(
                "SELECT username FROM users WHERE user_id = $1",
                uid
            )
            uname = row_user["username"] if (row_user and row_user["username"]) else f"User {uid}"
            user_lines.append(f"({uname}) {cnt}")
        user_report = "\n".join(user_lines) if user_lines else "нет"

        # 2) Строим текст отчёта
        report_lines = [
            "🗂️ <b>Отчет за сегодня (инициирован вручную командой /next)</b> 🗂️\n",
            f"⏰ Брони: {total_bookings_today}\n",
            f"💵 Нал: {cash_count}  итог: {cash_sum}¥\n",
            f"💸 Безнал: {beznal_count}  итог: {beznal_sum}¥\n",
            f"🧮 Агент: {agent_count}  итог: {agent_sum}¥\n",
            "🏋️‍♂️ Пользователи:",
            user_report
        ]
        report_text = "\n".join(report_lines)

        # 3) Отправляем отчёт в группу
        try:
            await message.bot.send_message(
                FINANCIAL_REPORT_GROUP_ID,
                report_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error("Не удалось отправить финансовый отчет в группу: %s", e)

        # 4) Удаляем все записи «Сегодня»
        await conn.execute("DELETE FROM bookings WHERE day = 'Сегодня'")
        await conn.execute("DELETE FROM group_time_slot_statuses WHERE day = 'Сегодня'")

        # 5) Очищаем внутренние структуры в groups_data для «Сегодня»
        for gk, ginfo in groups_data.items():
            ginfo["booked_slots"]["Сегодня"] = []
            ginfo["unavailable_slots"]["Сегодня"] = set()
            ginfo["time_slot_statuses"] = {
                (d, ts): st
                for ((d, ts), st) in ginfo["time_slot_statuses"].items()
                if d != "Сегодня"
            }
            ginfo["slot_bookers"] = {
                (d, ts): u
                for ((d, ts), u) in ginfo["slot_bookers"].items()
                if d != "Сегодня"
            }

        # 6) Переносим все «Завтра» → «Сегодня» в БД
        await conn.execute("UPDATE bookings SET day = 'Сегодня' WHERE day = 'Завтра'")
        await conn.execute("UPDATE group_time_slot_statuses SET day = 'Сегодня' WHERE day = 'Завтра'")

        # 7) Обновляем структуры в памяти: переносим «Завтра» → «Сегодня»
        for gk, ginfo in groups_data.items():
            # перенести списки «Завтра» → «Сегодня»
            ginfo["booked_slots"]["Сегодня"] = ginfo["booked_slots"].get("Завтра", [])
            ginfo["unavailable_slots"]["Сегодня"] = ginfo["unavailable_slots"].get("Завтра", set())
            ginfo["booked_slots"]["Завтра"] = []
            ginfo["unavailable_slots"]["Завтра"] = set()

            # Пересобираем time_slot_statuses и slot_bookers с учётом смены дня
            new_tss = {}
            for (d, ts), st in ginfo["time_slot_statuses"].items():
                if d == "Завтра":
                    new_tss[("Сегодня", ts)] = st
                else:
                    new_tss[(d, ts)] = st
            ginfo["time_slot_statuses"] = new_tss

            new_sb = {}
            for (d, ts), u in ginfo["slot_bookers"].items():
                if d == "Завтра":
                    new_sb[("Сегодня", ts)] = u
                else:
                    new_sb[(d, ts)] = u
            ginfo["slot_bookers"] = new_sb

        # 8) Обновляем «групповые» сообщения для каждой группы
        for gk in groups_data.keys():
            try:
                await update_group_message(message.bot, gk)
            except Exception as e:
                logger.warning("Не удалось обновить групповое сообщение для %s: %s", gk, e)

    # 9) Сообщаем администратору об успешном выполнении
    await message.reply(
        get_message(user_lang, "next_done", default="✅ Отчет сформирован, бронирования перенесены."),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(lambda cb: cb.data == "reset_day")
async def callback_reset_day(callback: CallbackQuery, state: FSMContext):
    """
    Точно такая же логика, что и /next, но запускается по нажатию кнопки "reset_day"
    в админ-меню.
    """
    user_id = callback.from_user.id
    user_lang = await get_user_language(user_id)

    # Игнорируем колбэки от самого бота
    me = await callback.bot.get_me()
    if callback.from_user.id == me.id:
        return

    # Проверяем права администратора
    if not is_user_admin(user_id):
        return await safe_answer(
            callback,
            get_message(user_lang, "admin_only", default="Только для админов."),
            show_alert=True
        )

    # Повторяем ту же логику, что и для /next
    async with db.db_pool.acquire() as conn:
        today_bookings = await conn.fetch("SELECT * FROM bookings WHERE day = 'Сегодня'")
        total_bookings_today = len(today_bookings)

        cash_count = cash_sum = 0
        beznal_count = beznal_sum = 0
        agent_count = agent_sum = 0

        user_bookings_count: Dict[int, int] = {}

        for b in today_bookings:
            pm = b["payment_method"]
            amt = b["amount"] or 0
            uid = b["user_id"]

            user_bookings_count[uid] = user_bookings_count.get(uid, 0) + 1

            if pm == "cash":
                cash_count += 1
                cash_sum += amt
            elif pm == "beznal":
                beznal_count += 1
                beznal_sum += amt
            elif pm == "agent":
                agent_count += 1
                agent_sum += amt

        user_lines = []
        for uid, cnt in user_bookings_count.items():
            row_user = await conn.fetchrow(
                "SELECT username FROM users WHERE user_id = $1",
                uid
            )
            uname = row_user["username"] if (row_user and row_user["username"]) else f"User {uid}"
            user_lines.append(f"({uname}) {cnt}")
        user_report = "\n".join(user_lines) if user_lines else "нет"

        report_lines = [
            "🗂️ <b>Отчет за сегодня (инициирован кнопкой «Сброс дня»)</b> 🗂️\n",
            f"⏰ Брони: {total_bookings_today}\n",
            f"💵 Нал: {cash_count}  итог: {cash_sum}¥\n",
            f"💸 Безнал: {beznal_count}  итог: {beznal_sum}¥\n",
            f"🧮 Агент: {agent_count}  итог: {agent_sum}¥\n",
            "🏋️‍♂️ Пользователи:",
            user_report
        ]
        report_text = "\n".join(report_lines)

        try:
            await callback.bot.send_message(
                FINANCIAL_REPORT_GROUP_ID,
                report_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error("Не удалось отправить финансовый отчет в группу: %s", e)

        # Удаляем все записи «Сегодня»
        await conn.execute("DELETE FROM bookings WHERE day = 'Сегодня'")
        await conn.execute("DELETE FROM group_time_slot_statuses WHERE day = 'Сегодня'")

        # Очищаем internal structures
        for gk, ginfo in groups_data.items():
            ginfo["booked_slots"]["Сегодня"] = []
            ginfo["unavailable_slots"]["Сегодня"] = set()
            ginfo["time_slot_statuses"] = {
                (d, ts): st
                for ((d, ts), st) in ginfo["time_slot_statuses"].items()
                if d != "Сегодня"
            }
            ginfo["slot_bookers"] = {
                (d, ts): u
                for ((d, ts), u) in ginfo["slot_bookers"].items()
                if d != "Сегодня"
            }

        # Переносим «Завтра» → «Сегодня» в БД
        await conn.execute("UPDATE bookings SET day = 'Сегодня' WHERE day = 'Завтра'")
        await conn.execute("UPDATE group_time_slot_statuses SET day = 'Сегодня' WHERE day = 'Завтра'")

        # Обновляем memory structures
        for gk, ginfo in groups_data.items():
            ginfo["booked_slots"]["Сегодня"] = ginfo["booked_slots"].get("Завтра", [])
            ginfo["unavailable_slots"]["Сегодня"] = ginfo["unavailable_slots"].get("Завтра", set())
            ginfo["booked_slots"]["Завтра"] = []
            ginfo["unavailable_slots"]["Завтра"] = set()

            new_tss = {}
            for (d, ts), st in ginfo["time_slot_statuses"].items():
                if d == "Завтра":
                    new_tss[("Сегодня", ts)] = st
                else:
                    new_tss[(d, ts)] = st
            ginfo["time_slot_statuses"] = new_tss

            new_sb = {}
            for (d, ts), u in ginfo["slot_bookers"].items():
                if d == "Завтра":
                    new_sb[("Сегодня", ts)] = u
                else:
                    new_sb[(d, ts)] = u
            ginfo["slot_bookers"] = new_sb

        # Обновляем групповые сообщения
        for gk in groups_data.keys():
            try:
                await update_group_message(callback.bot, gk)
            except Exception as e:
                logger.warning("Не удалось обновить групповое сообщение для %s: %s", gk, e)

    # Отвечаем администратору (коллбэк)
    await safe_answer(
        callback,
        get_message(user_lang, "next_done", default="✅ Отчет сформирован, бронирования перенесены."),
        show_alert=True
    )
