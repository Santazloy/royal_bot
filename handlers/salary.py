# handlers/salary.py

import logging

from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.filters.state import StateFilter
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from aiogram.fsm.context import FSMContext

import db
from config import is_user_admin
from constants.booking_const import groups_data
from constants.salary import salary_options
from states.salary_states import SalaryStates
from handlers.language import get_user_language, get_message

logger = logging.getLogger(__name__)
salary_router = Router()


async def load_salary_data_from_db():
    """
    Загружает из БД настройки salary и cash в groups_data.
    Вызывается из main.py перед стартом polling.
    """
    pool = db.db_pool
    if not pool:
        logger.error("db_pool is None in load_salary_data_from_db()")
        return

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT group_key, salary_option, salary, cash, message_id
                  FROM group_financial_data
            """)
    except Exception as e:
        logger.error(f"Error loading salary data: {e}")
        return

    for row in rows:
        gk = row["group_key"]
        if gk in groups_data:
            groups_data[gk]["salary_option"] = row["salary_option"]
            groups_data[gk]["salary"]        = row["salary"]
            groups_data[gk]["cash"]          = row["cash"]
            groups_data[gk]["message_id"]    = row["message_id"]

    logger.info("Salary settings loaded from DB.")


async def _salary_init(entry: Message | CallbackQuery, state: FSMContext):
    # Определяем источник (Message или CallbackQuery)
    if isinstance(entry, CallbackQuery):
        user_id   = entry.from_user.id
        send_fn   = entry.message.answer
        finish_fn = entry.answer
    else:
        user_id   = entry.from_user.id
        send_fn   = entry.answer
        finish_fn = None

    lang = await get_user_language(user_id)
    if not is_user_admin(user_id):
        txt = get_message(lang, "admin_only")
        if finish_fn:
            return await finish_fn(txt, show_alert=True)
        return await send_fn(txt)

    # Шаг 1: выбор группы
    keys = list(groups_data.keys())
    buttons = []
    for i in range(0, len(keys), 2):
        chunk = keys[i : i + 2]
        buttons.append(
            [InlineKeyboardButton(text=k, callback_data=f"salary_group_{k}") for k in chunk]
        )
    # Кнопка отмены
    buttons.append([InlineKeyboardButton(text=get_message(lang, "btn_cancel"), callback_data="salary_cancel")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await send_fn(get_message(lang, "salary_choose_group"), reply_markup=kb)
    await state.set_state(SalaryStates.waiting_for_group_choice)

    if finish_fn:
        await finish_fn()


@salary_router.message(Command("salary"))
async def salary_command(message: Message, state: FSMContext):
    await _salary_init(message, state)


@salary_router.callback_query(F.data == "salary")
async def salary_via_button(cb: CallbackQuery, state: FSMContext):
    await _salary_init(cb, state)
    await cb.answer()


@salary_router.callback_query(
    F.data.startswith("salary_group_"),
    StateFilter(SalaryStates.waiting_for_group_choice),
)
async def process_group(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await callback.answer(get_message(lang, "admin_only"), show_alert=True)

    group = callback.data.removeprefix("salary_group_")
    if group not in groups_data:
        return await callback.answer(get_message(lang, "no_such_group"), show_alert=True)

    await state.update_data(selected_group=group)
    current = groups_data[group].get("salary_option", 1)

    # Шаг 2: выбор опции
    opts = []
    for opt in (1, 2, 3, 4):
        mark = "✅" if opt == current else "   "
        opts.append([
            InlineKeyboardButton(
                text=f"{mark} {opt}",
                callback_data=f"salary_opt_{opt}"
            )
        ])
    opts.append([InlineKeyboardButton(text=get_message(lang, "btn_cancel"), callback_data="salary_cancel")])

    await callback.message.edit_text(
        get_message(lang, "salary_option_prompt", group=group, current=current),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=opts)
    )
    await state.set_state(SalaryStates.waiting_for_option_choice)
    await callback.answer()


@salary_router.callback_query(
    F.data.startswith("salary_opt_"),
    StateFilter(SalaryStates.waiting_for_option_choice),
)
async def process_option(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await callback.answer(get_message(lang, "admin_only"), show_alert=True)

    opt = int(callback.data.removeprefix("salary_opt_"))
    data  = await state.get_data()
    group = data.get("selected_group")
    if group not in groups_data or opt not in salary_options:
        await state.clear()
        return await callback.answer(get_message(lang, "invalid_data"), show_alert=True)

    # Сохраняем новое значение в память и БД
    groups_data[group]["salary_option"] = opt
    if db.db_pool:
        async with db.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO group_financial_data
                    (group_key, salary_option, salary, cash)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (group_key) DO UPDATE
                  SET salary_option = EXCLUDED.salary_option
                """,
                group, opt,
                groups_data[group]["salary"],
                groups_data[group]["cash"],
            )

    await state.clear()
    # Отправляем подтверждение
    await callback.message.answer(
        get_message(lang, "salary_set", group=group, opt=opt),
        parse_mode="HTML"
    )
    await callback.answer(get_message(lang, "done"), show_alert=True)

    # И выводим текущие коэффициенты
    coeff_text = "\n".join(f"{emoji}: {v}" for emoji, v in salary_options[opt].items())
    await callback.message.answer(
        get_message(lang, "salary_coeff", opt=opt, text=coeff_text)
    )


@salary_router.callback_query(
    F.data == "salary_cancel",
    StateFilter(SalaryStates.waiting_for_option_choice),
)
async def process_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer(get_message(await get_user_language(callback.from_user.id), "cancelled"))
