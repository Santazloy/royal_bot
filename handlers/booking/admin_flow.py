# handlers/booking/admin_flow.py

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton

from handlers.booking.router import router
from constants.booking_const import status_mapping, groups_data
from handlers.booking.reporting import update_group_message
from utils.bot_utils import safe_answer

@router.callback_query(F.data.startswith("group_time|"))
async def admin_click_slot(cb: CallbackQuery):
    _, gk, day, slot = cb.data.split("|")
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer("Нет прав!", show_alert=True)

    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer("Только админ!", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=emoji,
                callback_data=f"group_status|{gk}|{day}|{slot}|{code}"
            )
            for code, emoji in status_mapping.items()
        ],
        [
            InlineKeyboardButton(
                text="❌❌❌ Отменить",
                callback_data=f"group_status|{gk}|{day}|{slot}|-1"
            )
        ],
        [
            InlineKeyboardButton(
                text="« Назад",
                callback_data=f"group_status|{gk}|{day}|{slot}|back"
            )
        ]
    ])

    await safe_answer(
        cb,
        "<b>Выберите финальный статус слота:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
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

    if code == "back":
        await update_group_message(cb.bot, gk)
        return await cb.answer()

    if code == "-1":
        # Отмена: убираем слот из памяти и из БД
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

        import db, logging
        logger = logging.getLogger(__name__)
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
        return await safe_answer(cb, "Слот отменён.")

    # Устанавливаем финальный статус
    emoji = status_mapping.get(code)
    ginfo["time_slot_statuses"][(day, slot)] = emoji

    import db, logging
    logger = logging.getLogger(__name__)
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

    # Предлагаем способ оплаты
    from handlers.booking.rewards import apply_special_user_reward
    await apply_special_user_reward(code, cb.bot)

    from aiogram.types import InlineKeyboardMarkup as _IKM, InlineKeyboardButton as _IKB
    pay_kb = _IKM(inline_keyboard=[[
        _IKB(text="наличные", callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|cash"),
        _IKB(text="безнал",   callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|beznal"),
        _IKB(text="агент",    callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|agent"),
    ]])
    await safe_answer(cb, "Выберите способ оплаты:", parse_mode=ParseMode.HTML, reply_markup=pay_kb)
    await cb.answer()
