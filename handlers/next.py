import asyncio
import datetime
import logging
from typing import Dict

from aiogram import Router
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

from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
router = Router()


async def do_next_core(bot):
    """
    Общая логика сброса дня и отправки отчётов:
    1) Собираем отчёт за «Сегодня», отправляем в FINANCIAL_REPORT_GROUP_ID.
    2) Удаляем все записи "Сегодня" из таблиц bookings и group_time_slot_statuses.
    3) Очищаем in‐memory для «Сегодня».
    4) Переносим «Завтра»→«Сегодня» в БД и in‐memory.
    5) Обновляем групповое сообщение для каждой группы.
    """
    async with db.db_pool.acquire() as conn:
        # 1) Сбор данных за «Сегодня»
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

        # 2) Сбор отчёта по пользователям
        user_lines = []
        for uid, cnt in user_bookings_count.items():
            row_user = await conn.fetchrow(
                "SELECT username FROM users WHERE user_id = $1",
                uid
            )
            uname = row_user["username"] if (row_user and row_user["username"]) else f"User {uid}"
            user_lines.append(f"({uname}) {cnt}")
        user_report = "\n".join(user_lines) if user_lines else "нет"

        # 3) Формирование глобального отчёта
        report_lines = [
            "🗂️ <b>Отчет за сегодня (инициирован функцией do_next_core)</b> 🗂️\n",
            f"⏰ Брони: {total_bookings_today}\n",
            f"💵 Нал: {cash_count}  итог: {cash_sum}¥\n",
            f"💸 Безнал: {beznal_count}  итог: {beznal_sum}¥\n",
            f"🧮 Агент: {agent_count}  итог: {agent_sum}¥\n",
            "🏋️‍♂️ Пользователи:",
            user_report,
        ]
        report_text = "\n".join(report_lines)

        # 4) Отправляем глобальный отчёт в финансовую группу
        try:
            await bot.send_message(
                FINANCIAL_REPORT_GROUP_ID,
                report_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error("Не удалось отправить финансовый отчет в группу: %s", e)

        # 5) Удаляем все записи «Сегодня»
        await conn.execute("DELETE FROM bookings WHERE day = 'Сегодня'")
        await conn.execute("DELETE FROM group_time_slot_statuses WHERE day = 'Сегодня'")

        # 6) Очищаем in‐memory структуры для «Сегодня»
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

        # 7) Переносим «Завтра» → «Сегодня» в БД
        await conn.execute("UPDATE bookings SET day = 'Сегодня' WHERE day = 'Завтра'")
        await conn.execute("UPDATE group_time_slot_statuses SET day = 'Сегодня' WHERE day = 'Завтра'")

        # 8) Обновляем in‐memory структуры для переноса
        for gk, ginfo in groups_data.items():
            # переносим списки «Завтра» → «Сегодня»
            ginfo["booked_slots"]["Сегодня"] = ginfo["booked_slots"].get("Завтра", [])
            ginfo["unavailable_slots"]["Сегодня"] = ginfo["unavailable_slots"].get("Завтра", set())
            ginfo["booked_slots"]["Завтра"] = []
            ginfo["unavailable_slots"]["Завтра"] = set()

            # пересобираем состояния
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

        # 9) Обновляем групповое сообщение для каждой группы
        for gk in groups_data.keys():
            try:
                await update_group_message(bot, gk)
            except Exception as e:
                logger.warning("Не удалось обновить групповое сообщение для %s: %s", gk, e)


@router.message(Command("next"))
async def cmd_next(message: Message, state: FSMContext):
    """
    Ручной вызов /next – генерирует отчет за «Сегодня» и переносит «Завтра»→«Сегодня».
    Доступно только администраторам.
    """
    user_id = message.from_user.id
    user_lang = await get_user_language(user_id)

    if not is_user_admin(user_id):
        await message.reply(get_message(user_lang, "no_permission"))
        return

    # Запускаем основную логику, передавая экземпляр Bot
    await do_next_core(message.bot)

    # Ответ админу, что всё выполнено
    await message.reply(
        get_message(user_lang, "next_done", default="✅ Отчет сформирован, бронирования перенесены."),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(lambda cb: cb.data == "reset_day")
async def callback_reset_day(callback: CallbackQuery, state: FSMContext):
    """
    Тот же функционал, что и /next, но через кнопку "reset_day" в админ‐меню.
    """
    user_id = callback.from_user.id
    user_lang = await get_user_language(user_id)

    # Игнорируем колбэки, пришедшие от самого бота
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

    # Запускаем логику сброса
    await do_next_core(callback.bot)

    # Ответ админу (всплывающее окно)
    await safe_answer(
        callback,
        get_message(user_lang, "next_done", default="✅ Отчет сформирован, бронирования перенесены."),
        show_alert=True
    )


def register_daily_scheduler(dp, bot):
    """
    Регистрирует фоновую задачу, которая раз в минуту проверяет местное время Asia/Shanghai.
    Если сейчас ровно 03:00, запускает do_next_core(bot) и ждет 61 секунду, чтобы не сработать дважды за одну минуту.
    Вызывать в main.py сразу после включения всех роутеров:
        register_daily_scheduler(dp, bot)
    """
    async def _scheduler():
        while True:
            try:
                now = datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
                # Если ровно 03:00, запускаем reset
                if now.hour == 3 and now.minute == 0:
                    logger.info("Авто‐сброс: сейчас 03:00 Asia/Shanghai → запускаем do_next_core")
                    try:
                        await do_next_core(bot)
                    except Exception as e:
                        logger.error("Ошибка при автоматическом do_next_core: %s", e)
                    # Ждем чуть больше минуты, чтобы не сработать снова в ту же минуту
                    await asyncio.sleep(61)
                else:
                    # Проверяем каждую минуту
                    await asyncio.sleep(60)
            except Exception as e:
                logger.error("Ошибка в _scheduler: %s", e)
                await asyncio.sleep(60)

    # Регистрируем фоновой таск при старте polling
    async def _on_startup():
        # Стартуем планировщик как отдельную задачу
        asyncio.create_task(_scheduler())

    dp.startup.register(_on_startup)
