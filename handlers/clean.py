# handlers/clean.py

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

# Импортируйте свои объекты/методы:
from config import is_user_admin         # функция, проверяющая права
from db import db_pool                   # ваш пул asyncpg
from constants.booking_const import groups_data
from handlers.booking.router import update_group_message

logger = logging.getLogger(__name__)
router = Router()


class CleanupStates(StatesGroup):
    waiting_for_main_menu = State()
    waiting_for_group_choice = State()
    waiting_for_confirmation = State()


@router.message(Command("clean"))
async def cmd_clean(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_user_admin(user_id):
        await message.answer("<pre>У вас нет прав для этой операции.</pre>", parse_mode="HTML")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Время", callback_data="clean_menu_time"),
            InlineKeyboardButton(text="Зарплата", callback_data="clean_menu_salary")
        ],
        [
            InlineKeyboardButton(text="Наличные", callback_data="clean_menu_cash"),
            InlineKeyboardButton(text="Стереть все данные", callback_data="clean_menu_all")
        ]
    ])

    sent = await message.answer("<pre>Что вы хотите стереть?</pre>", parse_mode="HTML", reply_markup=kb)
    await state.update_data(base_msg_id=sent.message_id, base_chat_id=sent.chat.id)
    await state.set_state(CleanupStates.waiting_for_main_menu)


@router.callback_query(StateFilter(CleanupStates.waiting_for_main_menu), F.data.startswith("clean_menu_"))
async def process_clean_menu(cb: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    base_msg_id = user_data["base_msg_id"]
    base_chat_id = user_data["base_chat_id"]

    choice = cb.data.removeprefix("clean_menu_")  # time / salary / cash / all

    if choice == "all":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да, стереть все данные", callback_data="confirm_clean_all")],
            [InlineKeyboardButton(text="Отмена", callback_data="clean_cancel")]
        ])
        text = "<pre>Подтвердите удаление ВСЕХ данных (время/зарплата/наличные) по ВСЕМ группам?</pre>"
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await state.set_state(CleanupStates.waiting_for_confirmation)
        await cb.answer()
        return

    section_map = {
        "time":   "Время",
        "salary": "Зарплату",
        "cash":   "Наличные"
    }
    label = section_map.get(choice, choice)

    kb = []
    kb.append([InlineKeyboardButton(text=f"Стереть все {label}", callback_data=f"sect_all_{choice}")])
    for gk in groups_data.keys():
        kb.append([InlineKeyboardButton(text=gk, callback_data=f"sect_grp_{choice}_{gk}")])
    kb.append([InlineKeyboardButton(text="Отмена", callback_data="clean_cancel")])

    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    text = f"<pre>Вы выбрали: {label}\nВыберите группу или 'Стереть все {label}'</pre>"
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except TelegramBadRequest:
        pass

    await state.update_data(clean_section=choice)
    await state.set_state(CleanupStates.waiting_for_group_choice)
    await cb.answer()


@router.callback_query(StateFilter(CleanupStates.waiting_for_group_choice), F.data.startswith("sect_all_"))
async def process_section_all(cb: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    base_msg_id = user_data["base_msg_id"]
    base_chat_id = user_data["base_chat_id"]

    section = cb.data.removeprefix("sect_all_")  # time/salary/cash

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, стереть все!", callback_data=f"confirm_all_{section}")],
        [InlineKeyboardButton(text="Отмена", callback_data="clean_cancel")]
    ])
    text = f"<pre>Подтвердите удаление: {section} по ВСЕМ группам</pre>"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(CleanupStates.waiting_for_confirmation)
    await cb.answer()


@router.callback_query(StateFilter(CleanupStates.waiting_for_group_choice), F.data.startswith("sect_grp_"))
async def process_section_group_choice(cb: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    base_msg_id = user_data["base_msg_id"]
    base_chat_id = user_data["base_chat_id"]

    # sect_grp_time_Royal_1
    parts = cb.data.split("_", 3)  # ["sect", "grp", "time", "Royal_1"]
    section = parts[2]
    group_key = parts[3]

    if group_key not in groups_data:
        await cb.answer("Нет такой группы!", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, стереть!", callback_data=f"confirm_grp_{section}_{group_key}")],
        [InlineKeyboardButton(text="Отмена", callback_data="clean_cancel")]
    ])
    text = f"<pre>Подтвердите удаление\nРаздел: {section}\nГруппа: {group_key}</pre>"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(CleanupStates.waiting_for_confirmation)
    await cb.answer()


@router.callback_query(StateFilter(CleanupStates.waiting_for_confirmation), F.data == "confirm_clean_all")
async def confirm_clean_all(cb: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    base_msg_id = user_data["base_msg_id"]
    base_chat_id = user_data["base_chat_id"]

    for gk in groups_data.keys():
        groups_data[gk]['booked_slots'] = {'Сегодня': [], 'Завтра': []}
        groups_data[gk]['unavailable_slots'] = {'Сегодня': set(), 'Завтра': set()}
        groups_data[gk]['time_slot_statuses'] = {}
        groups_data[gk]['slot_bookers'] = {}
        groups_data[gk]['salary'] = 0
        groups_data[gk]['cash'] = 0
        if db_pool:
            conn = await db_pool.acquire()
            try:
                await conn.execute("DELETE FROM bookings WHERE group_key=$1", gk)
                await conn.execute("DELETE FROM group_time_slot_statuses WHERE group_key=$1", gk)
                await conn.execute("UPDATE group_financial_data SET salary=0, cash=0 WHERE group_key=$1", gk)
            finally:
                await db_pool.release(conn)
        await update_group_message(cb.bot, gk)

    try:
        await cb.message.delete()
    except:
        pass

    await cb.answer("Все данные стёрты (время, зарплата, наличные и т.д.).")
    await state.clear()


@router.callback_query(StateFilter(CleanupStates.waiting_for_confirmation), F.data.startswith("confirm_all_"))
async def confirm_all_section(cb: CallbackQuery, state: FSMContext):
    section = cb.data.removeprefix("confirm_all_")  # time / salary / cash
    user_data = await state.get_data()
    base_msg_id = user_data["base_msg_id"]
    base_chat_id = user_data["base_chat_id"]

    if section == "time":
        for gk in groups_data:
            groups_data[gk]['booked_slots'] = {'Сегодня': [], 'Завтра': []}
            groups_data[gk]['unavailable_slots'] = {'Сегодня': set(), 'Завтра': set()}
            groups_data[gk]['time_slot_statuses'] = {}
            groups_data[gk]['slot_bookers'] = {}
            if db_pool:
                conn = await db_pool.acquire()
                try:
                    await conn.execute("DELETE FROM bookings WHERE group_key=$1", gk)
                    await conn.execute("DELETE FROM group_time_slot_statuses WHERE group_key=$1", gk)
                finally:
                    await db_pool.release(conn)
            await update_group_message(cb.bot, gk)

    elif section == "salary":
        for gk in groups_data:
            groups_data[gk]['salary'] = 0
            if db_pool:
                conn = await db_pool.acquire()
                try:
                    await conn.execute("UPDATE group_financial_data SET salary=0 WHERE group_key=$1", gk)
                finally:
                    await db_pool.release(conn)
            await update_group_message(cb.bot, gk)

    elif section == "cash":
        for gk in groups_data:
            groups_data[gk]['cash'] = 0
            if db_pool:
                conn = await db_pool.acquire()
                try:
                    await conn.execute("UPDATE group_financial_data SET cash=0 WHERE group_key=$1", gk)
                finally:
                    await db_pool.release(conn)
            await update_group_message(cb.bot, gk)

    try:
        await cb.message.delete()
    except:
        pass

    await cb.answer(f"Удалили всё: {section} по всем группам.")
    await state.clear()


@router.callback_query(StateFilter(CleanupStates.waiting_for_confirmation), F.data.startswith("confirm_grp_"))
async def confirm_group_section(cb: CallbackQuery, state: FSMContext):
    # confirm_grp_time_Royal_1
    parts = cb.data.split("_", 3)
    section = parts[2]
    group_key = parts[3]

    if group_key not in groups_data:
        await cb.answer("Нет такой группы!", show_alert=True)
        return

    if section == "time":
        groups_data[group_key]['booked_slots'] = {'Сегодня': [], 'Завтра': []}
        groups_data[group_key]['unavailable_slots'] = {'Сегодня': set(), 'Завтра': set()}
        groups_data[group_key]['time_slot_statuses'] = {}
        groups_data[group_key]['slot_bookers'] = {}
        if db_pool:
            conn = await db_pool.acquire()
            try:
                await conn.execute("DELETE FROM bookings WHERE group_key=$1", group_key)
                await conn.execute("DELETE FROM group_time_slot_statuses WHERE group_key=$1", group_key)
            finally:
                await db_pool.release(conn)

    elif section == "salary":
        groups_data[group_key]['salary'] = 0
        if db_pool:
            conn = await db_pool.acquire()
            try:
                await conn.execute("UPDATE group_financial_data SET salary=0 WHERE group_key=$1", group_key)
            finally:
                await db_pool.release(conn)

    elif section == "cash":
        groups_data[group_key]['cash'] = 0
        if db_pool:
            conn = await db_pool.acquire()
            try:
                await conn.execute("UPDATE group_financial_data SET cash=0 WHERE group_key=$1", group_key)
            finally:
                await db_pool.release(conn)

    await update_group_message(cb.bot, group_key)

    try:
        await cb.message.delete()
    except:
        pass

    await cb.answer("Операция завершена. Данные очищены.")
    await state.clear()


@router.callback_query(F.data == "clean_cancel", StateFilter("*"))
async def process_clean_cancel(cb: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    base_msg_id = user_data.get("base_msg_id")
    base_msg_chat_id = user_data.get("base_chat_id")

    if base_msg_id and base_msg_chat_id:
        try:
            await cb.message.delete()
        except:
            pass

    await cb.answer("Отменено.")
    await state.clear()
