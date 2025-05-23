from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from handlers.booking.router import router
from utils.user_utils import get_user_language
from utils.text_utils import get_message, format_html_pre
from constants.booking_const import status_mapping, groups_data
from constants.salary import salary_options
from constants.booking_const import distribution_variants
import db
from handlers.booking.rewards import update_user_financial_info, apply_additional_payment
from handlers.booking.reporting import update_group_message, send_financial_report
from app_states import BookPaymentStates
import asyncio

@router.callback_query(F.data.startswith("payment_method|"))
async def process_payment_method(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split("|")
    _, gk, day, slot, code, method = parts
    lang = await get_user_language(cb.from_user.id)
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer(get_message(lang, "no_permission"), show_alert=True)

    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer(get_message(lang, "no_permission"), show_alert=True)

    if not db.db_pool:
        return await cb.answer("Нет подключения к БД", show_alert=True)

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot
        )
    if not row:
        return await cb.answer(get_message(lang, "no_such_booking"), show_alert=True)

    # Acknowledge the callback
    ack = cb.answer()
    if asyncio.iscoroutine(ack):
        await ack

    if method in ("cash", "beznal"):
        txt = get_message(lang, "enter_payment_amount")
        await state.update_data(
            group_key=gk, day=day, time_slot=slot, status_code=code, payment_method=method
        )
        try:
            await cb.bot.edit_message_text(
                chat_id=cb.message.chat.id,
                message_id=cb.message.message_id,
                text=format_html_pre(txt),
                parse_mode=ParseMode.HTML,
            )
        except TelegramBadRequest:
            pass
        await state.set_state(BookPaymentStates.waiting_for_amount)
    else:
        await handle_agent_payment(cb, gk, day, slot, code)

async def handle_agent_payment(cb: CallbackQuery, gk: str, day: str, slot: str, status_code: str):
    bot = cb.bot
    uid = cb.from_user.id
    lang = await get_user_language(uid)
    emoji = status_mapping.get(status_code)
    if not emoji:
        return await cb.answer("Некорректный статус!", show_alert=True)
    ginfo = groups_data.get(gk)
    if not ginfo:
        return await cb.answer("Нет такой группы!", show_alert=True)

    base = salary_options[ginfo["salary_option"]].get(emoji, 0)
    deduct_map = {"0": 1500, "1": 2100, "2": 3000, "3": 4500}
    deduct = deduct_map.get(status_code, 0)

    ginfo["salary"] += base
    async with db.db_pool.acquire() as conn:
        await conn.execute("UPDATE group_financial_data SET salary=$1 WHERE group_key=$2", ginfo["salary"], gk)
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot
        )
    if not row:
        return await cb.answer(get_message(lang, "no_such_booking"), show_alert=True)
    booked = row["user_id"]

    await update_user_financial_info(booked, -deduct, bot)
    async with db.db_pool.acquire() as conn:
        bal_row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", booked)
    bal = bal_row.get("balance", 0) if bal_row else 0
    msg = get_message(lang, "changed_balance_user", op="-", amount=deduct, balance=bal)
    await bot.send_message(booked, format_html_pre(msg), parse_mode=ParseMode.HTML)

    try:
        await update_group_message(bot, gk)
    except TelegramBadRequest:
        pass

    await send_financial_report(bot)
    await cb.answer("Оплата (agent) учтена.")

@router.message(F.text, StateFilter(BookPaymentStates.waiting_for_amount))
async def process_payment_amount(message: Message, state: FSMContext):
    if not hasattr(message, 'from_user'):
        raise RuntimeError("Message without from_user")
    user = message.from_user
    lang = await get_user_language(user.id)
    data = await state.get_data()
    gk, day, slot = data["group_key"], data["day"], data["time_slot"]
    code, method = data["status_code"], data["payment_method"]

    try:
        amt = int(message.text.strip())
    except ValueError:
        return await message.reply(format_html_pre(get_message(lang, "incorrect_input")), parse_mode=ParseMode.HTML)

    emoji = status_mapping.get(str(code))
    if not emoji:
        await state.clear()
        return await message.reply(get_message(lang, "invalid_data"))

    if not db.db_pool:
        await state.clear()
        return await message.reply("Нет соединения с БД.")

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot
        )
    if not row:
        await state.clear()
        return await message.reply(get_message(lang, "no_such_booking"))
    booked = row["user_id"]

    async with db.db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE bookings SET payment_method=$1, amount=$2 WHERE group_key=$3 AND day=$4 AND time_slot=$5 AND user_id=$6",
            method, amt, gk, day, slot, booked
        )

    # расчёты зарплаты и cash
    base = salary_options[groups_data[gk]["salary_option"]].get(emoji, 0)
    deduct_map = {"0": 1500, "1": 2100, "2": 3000, "3": 4500}
    deduct = deduct_map.get(str(code), 0)

    groups_data[gk]["salary"] += base
    async with db.db_pool.acquire() as conn:
        await conn.execute("UPDATE group_financial_data SET salary=$1 WHERE group_key=$2", groups_data[gk]["salary"], gk)
    if method == "cash":
        groups_data[gk]["cash"] += amt
        async with db.db_pool.acquire() as conn:
            await conn.execute("UPDATE group_financial_data SET cash=$1 WHERE group_key=$2", groups_data[gk]["cash"], gk)

    net = amt - deduct
    await update_user_financial_info(booked, net, message.bot)
    await apply_additional_payment(booked, str(code), message.bot)

    var = groups_data[gk].get("distribution_variant")
    dist_data = distribution_variants.get(var, distribution_variants["variant_400"])
    dist_amt = dist_data.get(str(code), 0)
    tgt = groups_data[gk].get("target_id")
    if dist_amt and tgt:
        await update_user_financial_info(tgt, dist_amt, message.bot)

    try:
        await update_group_message(message.bot, gk)
    except TelegramBadRequest:
        pass

    await send_financial_report(message.bot)
    await state.clear()
    await message.answer(f"Учли оплату {amt} (метод={method}), статус={emoji}.")
