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
from handlers.states import SalaryStates
from handlers.language import get_user_language, get_message
from utils.bot_utils import safe_answer  # общая функция для удаления предыдущего сообщения

logger = logging.getLogger(__name__)
salary_router = Router()

SALARY_PHOTO = "photo/IMG_2585.JPG"


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
            rows = await conn.fetch(
                """
                SELECT group_key, salary_option, salary, cash, message_id
                  FROM group_financial_data
                """
            )
    except Exception as e:
        logger.error(f"Error loading salary data: {e}")
        return

    for row in rows:
        gk = row["group_key"]
        if gk in groups_data:
            groups_data[gk]["salary_option"] = row["salary_option"]
            groups_data[gk]["salary"] = row["salary"]
            groups_data[gk]["cash"] = row["cash"]
            groups_data[gk]["message_id"] = row["message_id"]

    logger.info("Salary settings loaded from DB.")


async def _salary_init(entry: Message | CallbackQuery, state: FSMContext):
    lang = await get_user_language(entry.from_user.id)
    if not is_user_admin(entry.from_user.id):
        if isinstance(entry, CallbackQuery):
            return await entry.answer(
                "⚠️ У вас нет прав для выполнения этого действия",
                show_alert=True
            )
        return

    # Шаг 1: выбор группы
    keys = list(groups_data.keys())
    buttons = []
    for i in range(0, len(keys), 2):
        chunk = keys[i : i + 2]
        buttons.append(
            [InlineKeyboardButton(text=k, callback_data=f"salary_group_{k}") for k in chunk]
        )
    buttons.append(
        [InlineKeyboardButton(text=get_message(lang, "btn_cancel"), callback_data="salary_cancel")]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_answer(
        entry,
        photo=SALARY_PHOTO,
        caption=get_message(lang, "salary_choose_group"),
        reply_markup=kb,
    )
    await state.set_state(SalaryStates.waiting_for_group_choice)


@salary_router.message(Command("salary"))
async def salary_command(message: Message, state: FSMContext):
    if not is_user_admin(message.from_user.id):
        return
    await _salary_init(message, state)


@salary_router.callback_query(F.data == "salary")
async def salary_via_button(cb: CallbackQuery, state: FSMContext):
    if not is_user_admin(cb.from_user.id):
        return await cb.answer(
            "⚠️ У вас нет прав для выполнения этого действия",
            show_alert=True
        )
    await _salary_init(cb, state)
    await cb.answer()


@salary_router.callback_query(
    F.data.startswith("salary_group_"),
    StateFilter(SalaryStates.waiting_for_group_choice),
)
async def process_group(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await callback.answer(
            "⚠️ У вас нет прав для выполнения этого действия",
            show_alert=True
        )

    group = callback.data.removeprefix("salary_group_")
    if group not in groups_data:
        return await callback.answer(
            get_message(lang, "no_such_group"),
            show_alert=True
        )

    await state.update_data(selected_group=group)
    current = groups_data[group].get("salary_option", 1)

    opts = []
    for opt in (1, 2, 3, 4):
        mark = "✅" if opt == current else "   "
        opts.append(
            [InlineKeyboardButton(text=f"{mark} {opt}", callback_data=f"salary_opt_{opt}")]
        )
    opts.append([InlineKeyboardButton(text=get_message(lang, "btn_cancel"), callback_data="salary_cancel")])
    kb = InlineKeyboardMarkup(inline_keyboard=opts)

    await safe_answer(
        callback,
        photo=SALARY_PHOTO,
        caption=get_message(lang, "salary_option_prompt", group=group, current=current),
        reply_markup=kb,
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
        return await callback.answer(
            "⚠️ У вас нет прав для выполнения этого действия",
            show_alert=True
        )

    opt = int(callback.data.removeprefix("salary_opt_"))
    data = await state.get_data()
    group = data.get("selected_group")
    if group not in groups_data or opt not in salary_options:
        await state.clear()
        return await callback.answer(
            get_message(lang, "invalid_data"),
            show_alert=True
        )

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
    await safe_answer(
        callback,
        get_message(lang, "salary_set", group=group, opt=opt),
        parse_mode="HTML"
    )
    await callback.answer()


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
    await callback.answer(
        get_message(await get_user_language(callback.from_user.id), "cancelled"),
        show_alert=True
    )
