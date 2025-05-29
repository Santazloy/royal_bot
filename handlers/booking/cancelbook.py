# handlers/booking/cancelbook.py

from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from constants.booking_const import groups_data
from handlers.language import get_user_language, get_message
from handlers.booking.reporting import update_group_message
from utils.time_utils import get_adjacent_time_slots
import db
from handlers.booking.router import router
from utils.bot_utils import safe_answer

@router.message(Command("off"))
async def cmd_off(message: Message):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    if not db.db_pool:
        return await safe_answer(message, get_message(lang, "db_not_initialized"))

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, group_key, day, time_slot FROM bookings "
            "WHERE user_id=$1 AND status='booked' ORDER BY day, time_slot",
            user_id
        )

    if not rows:
        return await safe_answer(message, get_message(lang, "no_active_bookings"))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"❌ {r['day']} {r['time_slot']} ({r['group_key']})",
                callback_data=f"off_cancel_user_{r['id']}"
            )
        ] for r in rows
    ])
    await safe_answer(message, get_message(lang, "off_choose_booking"), reply_markup=kb)

@router.message(Command("offad"))
async def cmd_off_admin(message: Message):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    if not db.db_pool:
        return await safe_answer(message, get_message(lang, "db_not_initialized"))

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, group_key, day, time_slot FROM bookings "
            "WHERE status='booked' ORDER BY day, time_slot"
        )

    if not rows:
        return await safe_answer(message, get_message(lang, "no_active_bookings"))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"❌ {r['day']} {r['time_slot']} ({r['group_key']})",
                callback_data=f"off_cancel_admin_{r['id']}"
            )
        ] for r in rows
    ])
    await safe_answer(message, get_message(lang, "off_choose_booking"), reply_markup=kb)

@router.callback_query(F.data.startswith("off_cancel_user_"))
async def off_cancel_user(callback_query: CallbackQuery, state: FSMContext):
    uid = callback_query.from_user.id
    lang = await get_user_language(uid)
    bid = int(callback_query.data.split("off_cancel_user_")[1])

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT group_key, day, time_slot FROM bookings WHERE id=$1 AND user_id=$2",
            bid, uid
        )
        if not row:
            return await safe_answer(callback_query, get_message(lang, "no_such_booking"), show_alert=True)

        gk, day, slot = row["group_key"], row["day"], row["time_slot"]
        await conn.execute("DELETE FROM bookings WHERE id=$1", bid)
        await conn.execute(
            "DELETE FROM group_time_slot_statuses WHERE group_key=$1 AND day=$2 AND time_slot=$3",
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

    await update_group_message(callback_query.bot, gk)
    await safe_answer(callback_query, get_message(lang, "booking_cancelled"), show_alert=True)

@router.callback_query(F.data.startswith("off_cancel_admin_"))
async def off_cancel_admin(callback_query: CallbackQuery, state: FSMContext):
    uid = callback_query.from_user.id
    lang = await get_user_language(uid)
    bid = int(callback_query.data.split("off_cancel_admin_")[1])

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT group_key, day, time_slot FROM bookings WHERE id=$1",
            bid
        )
        if not row:
            return await safe_answer(callback_query, get_message(lang, "no_such_booking"), show_alert=True)

        gk = row["group_key"]
        await conn.execute("DELETE FROM bookings WHERE id=$1", bid)

    g = groups_data[gk]
    await update_group_message(callback_query.bot, gk)
    await safe_answer(callback_query, get_message(lang, "booking_cancelled_by_admin"), show_alert=True)
