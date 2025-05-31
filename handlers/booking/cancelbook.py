# handlers/booking/cancelbook.py
from aiogram import F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext

from constants.booking_const import groups_data
from handlers.language import get_user_language, get_message
from handlers.booking.reporting import update_group_message
from utils.time_utils import get_adjacent_time_slots
from utils.bot_utils import safe_answer

import db
from handlers.booking.router import router

PHOTO_ID = "photo/IMG_2585.JPG"        # ← общий файл-картинка для всех окон

# ───────────────────────────── /off (Пользователь) ───────────────────────────
@router.message(Command("off"))
async def cmd_off(message: Message):
    uid  = message.from_user.id
    lang = await get_user_language(uid)

    if not db.db_pool:
        return await safe_answer(
            message,
            get_message(lang, "db_not_initialized"),
            photo=PHOTO_ID
        )

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, group_key, day, time_slot FROM bookings "
            "WHERE user_id=$1 AND status='booked' "
            "ORDER BY day, time_slot",
            uid
        )

    if not rows:
        return await safe_answer(
            message,
            get_message(lang, "no_active_bookings"),
            photo=PHOTO_ID
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"❌ {r['day']} {r['time_slot']} ({r['group_key']})",
            callback_data=f"off_cancel_user_{r['id']}"
        )] for r in rows
    ])
    await safe_answer(
        message,
        get_message(lang, "off_choose_booking"),
        photo=PHOTO_ID,
        reply_markup=kb
    )

# ─────────────────────────── /offad (Администратор) ───────────────────────────
@router.message(Command("offad"))
async def cmd_off_admin(message: Message):
    uid  = message.from_user.id
    lang = await get_user_language(uid)

    if not db.db_pool:
        return await safe_answer(
            message,
            get_message(lang, "db_not_initialized"),
            photo=PHOTO_ID
        )

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, group_key, day, time_slot FROM bookings "
            "WHERE status='booked' ORDER BY day, time_slot"
        )

    if not rows:
        return await safe_answer(
            message,
            get_message(lang, "no_active_bookings"),
            photo=PHOTO_ID
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"❌ {r['day']} {r['time_slot']} ({r['group_key']})",
            callback_data=f"off_cancel_admin_{r['id']}"
        )] for r in rows
    ])
    await safe_answer(
        message,
        get_message(lang, "off_choose_booking"),
        photo=PHOTO_ID,
        reply_markup=kb
    )

# ───────────────────── Callback: пользователь отменяет СВОЮ бронь ─────────────
@router.callback_query(F.data.startswith("off_cancel_user_"))
async def off_cancel_user(callback: CallbackQuery, state: FSMContext):
    uid  = callback.from_user.id
    lang = await get_user_language(uid)
    bid  = int(callback.data.removeprefix("off_cancel_user_"))

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT group_key, day, time_slot FROM bookings "
            "WHERE id=$1 AND user_id=$2",
            bid, uid
        )
        if not row:
            return await safe_answer(
                callback,
                get_message(lang, "no_such_booking"),
                show_alert=True
            )

        gk, day, slot = row["group_key"], row["day"], row["time_slot"]
        await conn.execute("DELETE FROM bookings WHERE id=$1", bid)
        await conn.execute(
            "DELETE FROM group_time_slot_statuses "
            "WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot
        )

    g = groups_data[gk]
    g["booked_slots"][day].remove(slot)
    g["slot_bookers"].pop((day, slot), None)
    g["time_slot_statuses"].pop((day, slot), None)
    g["unavailable_slots"][day].discard(slot)
    for adj in get_adjacent_time_slots(slot):
        if adj not in g["booked_slots"][day]:
            g["unavailable_slots"][day].discard(adj)
            g["time_slot_statuses"].pop((day, adj), None)

    await update_group_message(callback.bot, gk)
    await safe_answer(
        callback,
        get_message(lang, "booking_cancelled"),
        show_alert=True
    )

# ───────────────────── Callback: админ отменяет ЧУЖУЮ бронь ───────────────────
@router.callback_query(F.data.startswith("off_cancel_admin_"))
async def off_cancel_admin(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    bid  = int(callback.data.removeprefix("off_cancel_admin_"))

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT group_key, day, time_slot FROM bookings WHERE id=$1",
            bid
        )
        if not row:
            return await safe_answer(
                callback,
                get_message(lang, "no_such_booking"),
                show_alert=True
            )

        gk = row["group_key"]
        await conn.execute("DELETE FROM bookings WHERE id=$1", bid)

    await update_group_message(callback.bot, gk)
    await safe_answer(
        callback,
        get_message(lang, "booking_cancelled_by_admin"),
        show_alert=True
    )
