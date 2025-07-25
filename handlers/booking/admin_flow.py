# handlers/booking/admin_flow.py

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton
import logging

from constants.booking_const import status_mapping, groups_data
from handlers.booking.reporting import update_group_message
from utils.bot_utils import safe_answer
from aiogram import Router

from handlers.booking.rewards import apply_special_user_reward

router = Router()
logger = logging.getLogger(__name__)
PHOTO_ID = "photo/IMG_2585.JPG"


@router.callback_query(F.data.startswith("group_time|"))
async def admin_click_slot(cb: CallbackQuery):
    _, gk, day, slot = cb.data.split("|")
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer("Нет прав!", show_alert=True)

    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer("Только админ!", show_alert=True)

    try:
        await cb.message.delete()
    except Exception:
        pass

    codes = list(status_mapping.items())
    status_buttons = [
        [
            InlineKeyboardButton(
                text=emoji,
                callback_data=f"group_status|{gk}|{day}|{slot}|{code}"
            )
            for code, emoji in codes[:3]
        ],
        [
            InlineKeyboardButton(
                text=emoji,
                callback_data=f"group_status|{gk}|{day}|{slot}|{code}"
            )
            for code, emoji in codes[3:]
        ],
        [
            InlineKeyboardButton(
                text="« Назад",
                callback_data=f"group_status|{gk}|{day}|{slot}|back"
            )
        ]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=status_buttons)

    await safe_answer(
        cb,
        "<b>Выберите финальный статус слота:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
        photo=PHOTO_ID
    )
    await cb.answer()


@router.callback_query(F.data.startswith("group_status|"))
async def admin_click_status(cb: CallbackQuery):
    parts = cb.data.split("|")
    _, gk, day, slot, code = parts
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer("Нет прав!", show_alert=True)

    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer("Нет прав!", show_alert=True)

    try:
        await cb.message.delete()
    except Exception:
        pass

    if code == "back":
        await update_group_message(cb.bot, gk)
        return await cb.answer()

    if code == "-1":
        uid = ginfo["slot_bookers"].pop((day, slot), None)
        if uid and slot in ginfo["booked_slots"].get(day, []):
            ginfo["booked_slots"][day].remove(slot)

        from utils.time_utils import get_adjacent_time_slots

        adjs = get_adjacent_time_slots(slot)
        for adj in adjs:
            if adj in ginfo["unavailable_slots"][day]:
                ginfo["unavailable_slots"][day].remove(adj)
                ginfo["time_slot_statuses"].pop((day, adj), None)
                if ginfo["slot_bookers"].get((day, adj)) == uid:
                    ginfo["slot_bookers"].pop((day, adj), None)

        ginfo["time_slot_statuses"].pop((day, slot), None)

        import db
        try:
            if db.db_pool:
                async with db.db_pool.acquire() as con:
                    await con.execute(
                        "DELETE FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
                        gk, day, slot
                    )
                    await con.execute(
                        "DELETE FROM group_time_slot_statuses WHERE group_key=$1 AND day=$2 AND time_slot=$3",
                        gk, day, slot
                    )
        except Exception as e:
            logger.error(f"DB error on delete: {e}")

        await update_group_message(cb.bot, gk)
        return await safe_answer(cb, "Слот отменён.", photo=PHOTO_ID)

    emoji = status_mapping.get(code)
    ginfo["time_slot_statuses"][(day, slot)] = emoji

    import db
    try:
        if db.db_pool:
            async with db.db_pool.acquire() as con:
                await con.execute(
                    "UPDATE bookings SET status_code=$1, status=$2 WHERE group_key=$3 AND day=$4 AND time_slot=$5",
                    code, emoji, gk, day, slot
                )
                await con.execute(
                    """
                    INSERT INTO group_time_slot_statuses
                      (group_key, day, time_slot, status, user_id)
                    VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT (group_key, day, time_slot)
                    DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                    """,
                    gk, day, slot, emoji, ginfo["slot_bookers"].get((day, slot))
                )
    except Exception as e:
        logger.error(f"DB error: {e}")

    try:
        await apply_special_user_reward(code, cb.bot)
    except TelegramBadRequest as e:
        logger.warning(f"admin_click_status: не удалось отправить reward: {e}")
    except Exception as e:
        logger.warning(f"admin_click_status: ошибка при apply_special_user_reward: {e}")

    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="наличные",
                callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|cash"
            )
        ],
        [
            InlineKeyboardButton(
                text="безнал",
                callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|beznal"
            )
        ],
        [
            InlineKeyboardButton(
                text="агент",
                callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|agent"
            )
        ],
    ])
    await safe_answer(cb, "Выберите способ оплаты:", parse_mode=ParseMode.HTML, reply_markup=pay_kb, photo=PHOTO_ID)
    await cb.answer()
