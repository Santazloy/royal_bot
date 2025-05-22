# handlers/salary.py

import logging
from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import db
from constants.booking_const import groups_data
from constants.salary import salary_options
from states.salary_states import SalaryStates
from config import ADMIN_IDS

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
            rows = await conn.fetch(
                """
                SELECT group_key, salary_option, salary, cash, message_id
                FROM group_financial_data
                """
            )
    except Exception as e:
        logger.error(f"Ошибка загрузки salary data: {e}")
        return
    for row in rows:
        gk = row["group_key"]
        if gk in groups_data:
            groups_data[gk]["salary_option"] = row["salary_option"]
            groups_data[gk]["salary"]        = row["salary"]
            groups_data[gk]["cash"]          = row["cash"]
            groups_data[gk]["message_id"]    = row.get("message_id")
    logger.info("Загружены настройки salary из БД.")

@salary_router.message(Command("salary"))
async def cmd_salary(message: Message, state: FSMContext):
    # Проверяем админа
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("Доступ только для администраторов.")
    # Клавиатура с группами по 2 в ряд
    keys = list(groups_data.keys())
    inline_keyboard = [
        [InlineKeyboardButton(text=k, callback_data=f"salary_group_{k}") for k in keys[i:i+2]]
        for i in range(0, len(keys), 2)
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await message.answer("Выберите группу для настройки зарплаты:", reply_markup=keyboard)
    await state.set_state(SalaryStates.waiting_for_group_choice)

@salary_router.callback_query(
    F.data.startswith("salary_group_"),
    StateFilter(SalaryStates.waiting_for_group_choice)
)
async def process_group(callback: CallbackQuery, state: FSMContext):
    # Проверяем админа
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Доступ только для администраторов!", show_alert=True)
    group = callback.data.removeprefix("salary_group_")
    if group not in groups_data:
        return await callback.answer("Неизвестная группа!", show_alert=True)
    await state.update_data(selected_group=group)
    # Клавиатура опций 1–4
    inline_keyboard = [
        [InlineKeyboardButton(text=str(opt), callback_data=f"salary_opt_{opt}") for opt in (1,2,3,4)]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await callback.message.edit_text(f"Группа: {group}\nВыберите опцию:", reply_markup=keyboard)
    await state.set_state(SalaryStates.waiting_for_option_choice)
    await callback.answer()

@salary_router.callback_query(
    F.data.startswith("salary_opt_"),
    StateFilter(SalaryStates.waiting_for_option_choice)
)
async def process_option(callback: CallbackQuery, state: FSMContext):
    # Проверяем админа
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Доступ только для администраторов!", show_alert=True)
    try:
        option = int(callback.data.removeprefix("salary_opt_"))
    except ValueError:
        await callback.answer("Некорректный вариант", show_alert=True)
        await state.clear()
        return
    data = await state.get_data()
    group = data.get("selected_group")
    if not group or group not in groups_data:
        await callback.answer("Неизвестная группа!", show_alert=True)
        await state.clear()
        return
    # Сохраняем выбор в память и БД
    groups_data[group]["salary_option"] = option
    pool = db.db_pool
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE group_financial_data SET salary_option=$1 WHERE group_key=$2",
            option, group
        )
    await state.clear()
    # Подтверждение
    await callback.message.edit_text(f"Опция зарплаты для {group} установлена: {option}.")
    await callback.answer("Сохранено", show_alert=True)
    # Отправляем результаты
    text = "\n".join(f"{emoji}: {value}" for emoji, value in salary_options[option].items())
    await callback.message.answer(f"Значения:\n{text}")
