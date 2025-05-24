# handlers/booking/payment_flow.py

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from handlers.booking.router import router
from handlers.language import get_user_language, get_message
from utils.text_utils import format_html_pre
from constants.booking_const import status_mapping, groups_data, distribution_variants
from constants.salary import salary_options
from handlers.booking.reporting import update_group_message, send_financial_report
from handlers.booking.rewards import update_user_financial_info
from app_states import BookPaymentStates

import db
import asyncio

SPECIAL_USER_IDS = {7935161063, 7281089930, 7894353415}

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

    if method in ("cash", "beznal"):
        await state.update_data(
            group_key=gk, day=day, time_slot=slot,
            status_code=code, payment_method=method
        )
        await cb.message.edit_text(
            format_html_pre(get_message(lang, "enter_payment_amount")),
            parse_mode=ParseMode.HTML
        )
        await state.set_state(BookPaymentStates.waiting_for_amount)
        await cb.answer()
    else:
        await handle_agent_payment(cb, gk, day, slot, code)


@router.message(F.text, StateFilter(BookPaymentStates.waiting_for_amount))
async def process_payment_amount(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
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

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot
        )
    if not row:
        await state.clear()
        return await message.reply(get_message(lang, "no_such_booking"))

    booked = row["user_id"]
    await update_booking_payment(booked, gk, day, slot, method, amt, code, message.bot, lang)
    await state.clear()
    await message.answer(get_message(lang, "payment_confirmation", amt=amt, method=method, emoji=emoji))


async def update_booking_payment(booked, gk, day, slot, method, amt, code, bot, lang):
    emoji = status_mapping.get(str(code))
    base = salary_options[groups_data[gk]["salary_option"]].get(emoji, 0)
    special_deduct = {"0": 1100, "1": 1300, "2": 2200, "3": 3300}
    standard_deduct = {"0": 1500, "1": 2100, "2": 3000, "3": 4500}
    is_special = booked in SPECIAL_USER_IDS

    deduct = special_deduct.get(str(code), 0) if is_special else standard_deduct.get(str(code), 0)
    net = (amt - deduct) / 2 if is_special else amt - deduct

    groups_data[gk]["salary"] += base
    if method == "cash":
        groups_data[gk]["cash"] += amt

    async with db.db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE group_financial_data SET salary=$1, cash=$2 WHERE group_key=$3",
            groups_data[gk]["salary"], groups_data[gk]["cash"], gk
        )
        await conn.execute(
            "UPDATE bookings SET payment_method=$1, amount=$2 WHERE group_key=$3 AND day=$4 AND time_slot=$5 AND user_id=$6",
            method, amt, gk, day, slot, booked
        )

        await update_user_financial_info(booked, net, bot)
        row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", booked)
        bal = row["balance"] if row else net
        msg = get_message(lang, "changed_balance_user", op="+" if net >= 0 else "-", amount=abs(net), balance=bal)
        await bot.send_message(booked, format_html_pre(msg), parse_mode=ParseMode.HTML)

    target_id = groups_data[gk].get("target_id")
    variant = groups_data[gk].get("distribution_variant") or "variant_400"
    dist_amt = distribution_variants[variant].get(str(code), 0)
    if dist_amt and target_id:
        await update_user_financial_info(target_id, dist_amt, bot)
        async with db.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", target_id)
        bal = row["balance"] if row else dist_amt
        msg = get_message(lang, "changed_balance_user", op="+", amount=dist_amt, balance=bal)
        await bot.send_message(target_id, format_html_pre(msg), parse_mode=ParseMode.HTML)

    await update_group_message(bot, gk)
    await send_financial_report(bot)


async def handle_agent_payment(cb: CallbackQuery, gk: str, day: str, slot: str, code: str):
    lang = await get_user_language(cb.from_user.id)
    emoji = status_mapping.get(code)
    if not emoji:
        return await cb.answer("Некорректный статус!", show_alert=True)

    ginfo = groups_data[gk]
    base = salary_options[ginfo["salary_option"]].get(emoji, 0)
    deduct_map = {"0": 1500, "1": 2100, "2": 3000, "3": 4500}
    deduct = deduct_map.get(code, 0)

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
    await update_user_financial_info(booked, -deduct, cb.bot)

    async with db.db_pool.acquire() as conn:
        bal_row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", booked)
    bal = bal_row.get("balance", 0) if bal_row else 0
    msg = get_message(lang, "changed_balance_user", op="-", amount=deduct, balance=bal)
    await cb.bot.send_message(booked, format_html_pre(msg), parse_mode=ParseMode.HTML)

    await update_group_message(cb.bot, gk)
    await send_financial_report(cb.bot)
    await cb.answer("Оплата (agent) учтена.")
