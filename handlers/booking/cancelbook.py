# handlers/booking/cancelbook.py

import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext

from utils.bot_utils import safe_answer
import handlers.language as lang_mod        # <--- import the entire handlers.language module
import db
from constants.booking_const import groups_data
from handlers.booking.reporting import update_group_message
from utils.time_utils import get_adjacent_time_slots

router = Router()
PHOTO_ID = "photo/IMG_2585.JPG"


# ───────────────────────────── /off (Пользователь и меню) ───────────────────────────
async def cmd_off(event):
    """
    Универсальный обработчик для отмены бронирований:
    Работает как по команде /off (Message), так и по кнопке из меню (CallbackQuery).
    """
    # Определяем uid и куда отвечать
    if isinstance(event, CallbackQuery):
        # Игнорируем колбэки от самого бота
        me = await event.bot.get_me()
        if event.from_user.id == me.id:
            return

        uid = event.from_user.id
        answer_target = event
    elif isinstance(event, Message):
        uid = event.from_user.id
        answer_target = event
    else:
        return  # неизвестный тип события

    # Получаем язык (тесты перехватят lang_mod.get_user_language)
    lang = await lang_mod.get_user_language(uid)

    # Если база данных ещё не инициализирована
    if not db.db_pool:
        return await safe_answer(
            answer_target,
            lang_mod.get_message(lang, "db_not_initialized"),
            photo=PHOTO_ID
        )

    # Берём из БД все строки для текущего user_id (без статуса)
    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, group_key, day, time_slot
            FROM bookings
            WHERE user_id = $1
            ORDER BY day, time_slot
            """,
            uid
        )

    # Если записей нет — сообщаем об отсутствии
    if not rows:
        return await safe_answer(
            answer_target,
            lang_mod.get_message(lang, "no_active_bookings"),
            photo=PHOTO_ID
        )

    # Формируем клавиатуру: кнопка для каждой брони пользователя
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"❌ {r['day']} {r['time_slot']} ({r['group_key']})",
                callback_data=f"off_cancel_user_{r['id']}"
            )
        ]
        for r in rows
    ])

    await safe_answer(
        answer_target,
        lang_mod.get_message(lang, "off_choose_booking"),
        photo=PHOTO_ID,
        reply_markup=kb
    )


# ────────────── /off для Message ──────────────
@router.message(Command("off"))
async def cmd_off_message(message: Message):
    await cmd_off(message)


# ─────────────────────────── /offad (Администратор) ───────────────────────────
@router.message(Command("offad"))
async def cmd_off_admin(message: Message):
    uid = message.from_user.id
    lang = await lang_mod.get_user_language(uid)

    # Если база данных ещё не инициализирована
    if not db.db_pool:
        return await safe_answer(
            message,
            lang_mod.get_message(lang, "db_not_initialized"),
            photo=PHOTO_ID
        )

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, group_key, day, time_slot
            FROM bookings
            ORDER BY day, time_slot
            """
        )

    if not rows:
        return await safe_answer(
            message,
            lang_mod.get_message(lang, "no_active_bookings"),
            photo=PHOTO_ID
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"❌ {r['day']} {r['time_slot']} ({r['group_key']})",
                callback_data=f"off_cancel_admin_{r['id']}"
            )
        ]
        for r in rows
    ])

    await safe_answer(
        message,
        lang_mod.get_message(lang, "off_choose_booking"),
        photo=PHOTO_ID,
        reply_markup=kb
    )


# ───────────────────── Callback: пользователь отменяет свою бронь ─────────────
@router.callback_query(F.data.startswith("off_cancel_user_"))
async def off_cancel_user(callback: CallbackQuery, state: FSMContext):
    # Игнорируем колбэки от самого бота
    me = await callback.bot.get_me()
    if callback.from_user.id == me.id:
        return

    uid = callback.from_user.id
    lang = await lang_mod.get_user_language(uid)
    bid = int(callback.data.removeprefix("off_cancel_user_"))

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT group_key, day, time_slot
            FROM bookings
            WHERE id = $1 AND user_id = $2
            """,
            bid, uid
        )
        if not row:
            return await safe_answer(
                callback,
                lang_mod.get_message(lang, "no_such_booking"),
                show_alert=True
            )

        gk, day, slot = row["group_key"], row["day"], row["time_slot"]
        # Удаляем бронь
        await conn.execute("DELETE FROM bookings WHERE id = $1", bid)
        # Удаляем связанный статус слота
        await conn.execute(
            """
            DELETE FROM group_time_slot_statuses
            WHERE group_key = $1 AND day = $2 AND time_slot = $3
            """,
            gk, day, slot
        )

    # Обновляем in-memory groups_data
    g = groups_data[gk]
    if slot in g["booked_slots"][day]:
        g["booked_slots"][day].remove(slot)
    g["slot_bookers"].pop((day, slot), None)
    g["time_slot_statuses"].pop((day, slot), None)
    g["unavailable_slots"][day].discard(slot)
    for adj in get_adjacent_time_slots(slot):
        if adj not in g["booked_slots"][day]:
            g["unavailable_slots"][day].discard(adj)
            g["time_slot_statuses"].pop((day, adj), None)

    # Обновляем групповое сообщение (если есть)
    await update_group_message(callback.bot, gk)
    await safe_answer(
        callback,
        lang_mod.get_message(lang, "booking_cancelled"),
        show_alert=True
    )


# ───────────────────── Callback: админ отменяет чужую бронь ───────────────────
@router.callback_query(F.data.startswith("off_cancel_admin_"))
async def off_cancel_admin(callback: CallbackQuery, state: FSMContext):
    # Игнорируем колбэки от самого бота
    me = await callback.bot.get_me()
    if callback.from_user.id == me.id:
        return

    lang = await lang_mod.get_user_language(callback.from_user.id)
    bid = int(callback.data.removeprefix("off_cancel_admin_"))

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT group_key, day, time_slot
            FROM bookings
            WHERE id = $1
            """,
            bid
        )
        if not row:
            return await safe_answer(
                callback,
                lang_mod.get_message(lang, "no_such_booking"),
                show_alert=True
            )

        gk = row["group_key"]
        await conn.execute("DELETE FROM bookings WHERE id = $1", bid)

    # Обновляем групповое сообщение (если есть)
    await update_group_message(callback.bot, gk)
    await safe_answer(
        callback,
        lang_mod.get_message(lang, "booking_cancelled_by_admin"),
        show_alert=True
    )
