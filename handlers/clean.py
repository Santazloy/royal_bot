# handlers/clean.py

import logging

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters.command import Command
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

import db
from config import is_user_admin
from constants.booking_const import groups_data
from handlers.language import get_user_language, get_message
from handlers.booking.reporting import update_group_message

logger = logging.getLogger(__name__)
router = Router()


class CleanupStates(StatesGroup):
    waiting_for_main_menu = State()
    waiting_for_group_choice = State()
    waiting_for_confirmation = State()


@router.message(Command("clean"))
async def cmd_clean(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if not is_user_admin(message.from_user.id):
        return await message.answer(
            get_message(lang, "no_permission"),
            parse_mode="HTML"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_message(lang, "clean_time"),   callback_data="clean_menu_time"),
            InlineKeyboardButton(text=get_message(lang, "clean_salary"), callback_data="clean_menu_salary"),
        ],
        [
            InlineKeyboardButton(text=get_message(lang, "clean_cash"),   callback_data="clean_menu_cash"),
            InlineKeyboardButton(text=get_message(lang, "clean_all"),    callback_data="clean_menu_all"),
        ],
    ])
    sent = await message.answer(
        get_message(lang, "clean_prompt"),
        parse_mode="HTML",
        reply_markup=kb
    )
    await state.update_data(
        base_msg_id=sent.message_id,
        base_chat_id=sent.chat.id
    )
    await state.set_state(CleanupStates.waiting_for_main_menu)


@router.callback_query(
    StateFilter(CleanupStates.waiting_for_main_menu),
    F.data.startswith("clean_menu_")
)
async def process_clean_menu(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    choice = cb.data.removeprefix("clean_menu_")  # time / salary / cash / all

    if choice == "all":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=get_message(lang, "clean_confirm_all"),
                callback_data="confirm_clean_all"
            )],
            [InlineKeyboardButton(
                text=get_message(lang, "btn_cancel"),
                callback_data="clean_cancel"
            )],
        ])
        await cb.message.edit_text(
            get_message(lang, "clean_confirm_all_prompt"),
            parse_mode="HTML",
            reply_markup=kb
        )
        await state.set_state(CleanupStates.waiting_for_confirmation)
        return await cb.answer()

    # выбор конкретного раздела
    label = get_message(lang, f"clean_{choice}")
    rows = [
        [InlineKeyboardButton(
            text=get_message(lang, f"clean_all_{choice}"),
            callback_data=f"sect_all_{choice}"
        )]
    ]
    for gk in groups_data:
        rows.append([InlineKeyboardButton(
            text=gk,
            callback_data=f"sect_grp_{choice}_{gk}"
        )])
    rows.append([InlineKeyboardButton(
        text=get_message(lang, "btn_cancel"),
        callback_data="clean_cancel"
    )])

    await cb.message.edit_text(
        get_message(lang, "clean_section_prompt", section=label),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await state.update_data(clean_section=choice)
    await state.set_state(CleanupStates.waiting_for_group_choice)
    await cb.answer()


@router.callback_query(
    StateFilter(CleanupStates.waiting_for_group_choice),
    F.data.startswith("sect_all_")
)
async def process_section_all(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    section = cb.data.removeprefix("sect_all_")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_message(lang, "clean_confirm_all"),
            callback_data=f"confirm_all_{section}"
        )],
        [InlineKeyboardButton(
            text=get_message(lang, "btn_cancel"),
            callback_data="clean_cancel"
        )],
    ])
    await cb.message.edit_text(
        get_message(lang, "clean_confirm_section_prompt", section=get_message(lang, f"clean_{section}")),
        parse_mode="HTML",
        reply_markup=kb
    )
    await state.set_state(CleanupStates.waiting_for_confirmation)
    await cb.answer()


@router.callback_query(
    StateFilter(CleanupStates.waiting_for_group_choice),
    F.data.startswith("sect_grp_")
)
async def process_section_group_choice(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    _, _, section, group_key = cb.data.split("_", 3)

    if group_key not in groups_data:
        return await cb.answer(get_message(lang, "no_such_group"), show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_message(lang, "clean_confirm_group"),
            callback_data=f"confirm_grp_{section}_{group_key}"
        )],
        [InlineKeyboardButton(
            text=get_message(lang, "btn_cancel"),
            callback_data="clean_cancel"
        )],
    ])
    await cb.message.edit_text(
        get_message(lang, "clean_group_prompt", section=get_message(lang, f"clean_{section}"), group=group_key),
        parse_mode="HTML",
        reply_markup=kb
    )
    await state.set_state(CleanupStates.waiting_for_confirmation)
    await cb.answer()


@router.callback_query(
    StateFilter(CleanupStates.waiting_for_confirmation),
    F.data.startswith("confirm_all_")
)
async def confirm_all_section(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    section = cb.data.removeprefix("confirm_all_")

    for gk in groups_data:
        # очистка памяти
        groups_data[gk].update({
            'booked_slots':      {'Сегодня': [], 'Завтра': []},
            'unavailable_slots': {'Сегодня': set(), 'Завтра': set()},
            'time_slot_statuses': {},
            'slot_bookers':       {},
            'salary':            0,
            'cash':              0,
        })
        # очистка БД
        if db.db_pool:
            async with db.db_pool.acquire() as conn:
                await conn.execute("DELETE FROM bookings WHERE group_key=$1", gk)
                await conn.execute("DELETE FROM group_time_slot_statuses WHERE group_key=$1", gk)
                if section == "salary":
                    await conn.execute(
                        "UPDATE group_financial_data SET salary=0 WHERE group_key=$1", gk
                    )
                elif section == "cash":
                    await conn.execute(
                        "UPDATE group_financial_data SET cash=0 WHERE group_key=$1", gk
                    )
        await update_group_message(cb.bot, gk)

    try:
        await cb.message.delete()
    except TelegramBadRequest:
        pass

    await cb.answer(
        get_message(lang, "clean_done_all", section=get_message(lang, f"clean_{section}"))
    )
    await state.clear()


@router.callback_query(
    StateFilter(CleanupStates.waiting_for_confirmation),
    F.data.startswith("confirm_grp_")
)
async def confirm_group_section(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    _, _, section, group_key = cb.data.split("_", 3)

    # очистка для конкретной группы
    if section == "time":
        groups_data[group_key].update({
            'booked_slots':      {'Сегодня': [], 'Завтра': []},
            'unavailable_slots': {'Сегодня': set(), 'Завтра': set()},
            'time_slot_statuses': {},
            'slot_bookers':       {},
        })
        if db.db_pool:
            async with db.db_pool.acquire() as conn:
                await conn.execute("DELETE FROM bookings WHERE group_key=$1", group_key)
                await conn.execute("DELETE FROM group_time_slot_statuses WHERE group_key=$1", group_key)
    elif section == "salary":
        groups_data[group_key]['salary'] = 0
        if db.db_pool:
            async with db.db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE group_financial_data SET salary=0 WHERE group_key=$1", group_key
                )
    else:  # cash
        groups_data[group_key]['cash'] = 0
        if db.db_pool:
            async with db.db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE group_financial_data SET cash=0 WHERE group_key=$1", group_key
                )

    await update_group_message(cb.bot, group_key)

    try:
        await cb.message.delete()
    except TelegramBadRequest:
        pass

    await cb.answer(
        get_message(lang, "clean_done_group", section=get_message(lang, f"clean_{section}"), group=group_key)
    )
    await state.clear()


@router.callback_query(F.data == "clean_cancel", StateFilter("*"))
async def process_clean_cancel(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    try:
        await cb.message.delete()
    except:
        pass
    await cb.answer(get_message(lang, "cancelled"))
    await state.clear()
