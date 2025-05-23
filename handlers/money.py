# handlers/money.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.command import Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

import db
from constants.booking_const import groups_data
from handlers.booking.reporting import update_group_message, send_financial_report
from handlers.language import get_user_language, get_message
from utils.text_utils import format_html_pre

money_router = Router()

class MoneyStates(StatesGroup):
    waiting_for_selection = State()
    waiting_for_plus_minus = State()
    waiting_for_amount = State()

@money_router.message(Command("money"))
async def money_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_lang = await get_user_language(user_id)
    chat_id = message.chat.id

    selected_group_key = None
    for gk, info in groups_data.items():
        if info['chat_id'] == chat_id:
            selected_group_key = gk
            break

    if not selected_group_key:
        return await message.answer(format_html_pre(get_message(user_lang, 'no_such_group')),
                                     parse_mode=ParseMode.HTML)

    msg = await message.answer(format_html_pre(get_message(user_lang, 'choose_what_change')),
                                parse_mode=ParseMode.HTML)

    await state.update_data(
        selected_group=selected_group_key,
        base_message_id=msg.message_id,
        base_chat_id=msg.chat.id
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_message(user_lang, 'salary'), callback_data="money_salary"),
            InlineKeyboardButton(text=get_message(user_lang, 'cash'), callback_data="money_cash")
        ]
    ])
    await msg.edit_reply_markup(reply_markup=kb)
    await state.set_state(MoneyStates.waiting_for_selection)

@money_router.callback_query(
    F.data.startswith("money_"),
    StateFilter(MoneyStates.waiting_for_selection)
)
async def money_select_type(cb: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(cb.from_user.id)
    typ = cb.data.split("money_")[1]

    if typ not in ("salary", "cash"):
        return await cb.answer(get_message(user_lang, "invalid_data"), show_alert=True)

    await state.update_data(money_type=typ)
    await cb.answer()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_message(user_lang, 'plus'), callback_data="money_plus"),
            InlineKeyboardButton(text=get_message(user_lang, 'minus'), callback_data="money_minus")
        ]
    ])
    await cb.message.edit_text(format_html_pre(get_message(user_lang, 'select_operation')),
                                parse_mode=ParseMode.HTML,
                                reply_markup=kb)
    await state.set_state(MoneyStates.waiting_for_plus_minus)

@money_router.callback_query(
    F.data.startswith("money_"),
    StateFilter(MoneyStates.waiting_for_plus_minus)
)
async def money_operation(cb: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(cb.from_user.id)
    op = cb.data.split("money_")[1]

    if op not in ("plus", "minus"):
        return await cb.answer(get_message(user_lang, "invalid_data"), show_alert=True)

    await state.update_data(money_operation=op)

    await cb.message.edit_text(format_html_pre(get_message(user_lang, "enter_amount")), parse_mode=ParseMode.HTML)
    await state.set_state(MoneyStates.waiting_for_amount)
    await cb.answer()

@money_router.message(F.text, StateFilter(MoneyStates.waiting_for_amount))
async def process_amount_input(message: Message, state: FSMContext):
    user_lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    money_type = data['money_type']
    operation = data['money_operation']
    group_key = data['selected_group']
    base_chat_id = data['base_chat_id']
    base_message_id = data['base_message_id']

    try:
        value = int(message.text.strip())
    except ValueError:
        return await message.answer(format_html_pre(get_message(user_lang, "incorrect_input")), parse_mode=ParseMode.HTML)

    delta = value if operation == "plus" else -value
    current = groups_data[group_key][money_type]
    new_val = current + delta
    if new_val < 0:
        return await message.answer(format_html_pre(get_message(user_lang, "incorrect_input")), parse_mode=ParseMode.HTML)

    groups_data[group_key][money_type] = new_val
    if db.db_pool:
        async with db.db_pool.acquire() as conn:
            if money_type == "salary":
                await conn.execute("UPDATE group_financial_data SET salary=$1 WHERE group_key=$2", new_val, group_key)
            else:
                await conn.execute("UPDATE group_financial_data SET cash=$1 WHERE group_key=$2", new_val, group_key)

    await update_group_message(message.bot, group_key)
    await send_financial_report(message.bot)

    await message.answer(format_html_pre(get_message(user_lang, "done")), parse_mode=ParseMode.HTML)
    await state.clear()
