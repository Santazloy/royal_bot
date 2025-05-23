# handlers/salary.py

import logging

from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.filters.state import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import db
from config import ADMIN_IDS
from constants.booking_const import groups_data
from constants.salary import salary_options
from states.salary_states import SalaryStates
from handlers.language import get_user_language, get_message

logger = logging.getLogger(__name__)
salary_router = Router()

async def load_salary_data_from_db():
    """
    Загружает из БД поля salary_option, salary, cash и message_id в groups_data
    """
    pool = db.db_pool
    if not pool:
        logger.error("db_pool is None в load_salary_data_from_db()")
        return

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT group_key, salary_option, salary, cash, message_id
                  FROM group_financial_data
            """)
    except Exception as e:
        logger.error(f"Ошибка загрузки salary data: {e}")
        return

    for row in rows:
        gk = row["group_key"]
        if gk in groups_data:
            groups_data[gk]["salary_option"] = row["salary_option"]
            groups_data[gk]["salary"]        = row["salary"]
            groups_data[gk]["cash"]          = row["cash"]
            groups_data[gk]["message_id"]    = row["message_id"]

    logger.info("Загружены настройки salary из БД.")

@salary_router.message(Command("salary"))
async def cmd_salary(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer(get_message(lang, "admin_only"))

    keys = list(groups_data.keys())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=k, callback_data=f"salary_group_{k}") for k in keys[i : i+2]]
        for i in range(0, len(keys), 2)
    ])
    await message.answer(get_message(lang, "salary_choose_group"), reply_markup=kb)
    await state.set_state(SalaryStates.waiting_for_group_choice)

@salary_router.callback_query(F.data.startswith("salary_group_"), StateFilter(SalaryStates.waiting_for_group_choice))
async def process_group(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer(get_message(lang, "admin_only"), show_alert=True)

    group = callback.data.removeprefix("salary_group_")
    if group not in groups_data:
        return await callback.answer(get_message(lang, "no_such_group"), show_alert=True)

    await state.update_data(selected_group=group)
    current = groups_data[group].get("salary_option", 1)
    buttons = [
        InlineKeyboardButton(
            text=f"{'✅' if opt == current else '   '} {opt}",
            callback_data=f"salary_opt_{opt}"
        ) for opt in (1,2,3,4)
    ] + [[InlineKeyboardButton(text=get_message(lang, "btn_cancel"), callback_data="salary_cancel")]]
    await callback.message.edit_text(
        get_message(lang, "salary_option_prompt", group=group, current=current),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(SalaryStates.waiting_for_option_choice)
    await callback.answer()

@salary_router.callback_query(F.data.startswith("salary_opt_"), StateFilter(SalaryStates.waiting_for_option_choice))
async def process_option(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer(get_message(lang, "admin_only"), show_alert=True)

    opt = int(callback.data.removeprefix("salary_opt_"))
    data = await state.get_data()
    group = data.get("selected_group")
    if group not in groups_data or opt not in salary_options:
        await state.clear()
        return await callback.answer(get_message(lang, "invalid_data"), show_alert=True)

    groups_data[group]["salary_option"] = opt
    if db.db_pool:
        async with db.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO group_financial_data (group_key, salary_option, salary, cash)
                VALUES ($1,$2,$3,$4)
                ON CONFLICT (group_key) DO UPDATE SET salary_option=EXCLUDED.salary_option
                """,
                group, opt, groups_data[group]["salary"], groups_data[group]["cash"]
            )

    await state.clear()
    await callback.message.edit_text(
        get_message(lang, "salary_set", group=group, opt=opt),
        parse_mode="HTML"
    )
    await callback.answer(get_message(lang, "done"), show_alert=True)

    coeff_text = "\n".join(f"{emoji}: {value}" for emoji, value in salary_options[opt].items())
    await callback.message.answer(get_message(lang, "salary_coeff", opt=opt, text=coeff_text))

@salary_router.callback_query(F.data == "salary_cancel", StateFilter(SalaryStates.waiting_for_option_choice))
async def process_cancel(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await state.clear()
    await callback.answer(get_message(lang, "cancelled"), show_alert=True)
    try:
        await callback.message.delete()
    except:
        pass
