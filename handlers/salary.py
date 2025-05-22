# handlers/salary.py

from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from constants.booking_const import groups_data
import db
from constants.salary import salary_options
from states.salary_states import SalaryStates
from config import ADMIN_IDS

salary_router = Router()

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
        [InlineKeyboardButton(text=str(opt), callback_data=f"salary_opt_{opt}") for opt in (1, 2, 3, 4)]
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
    # Сохраняем выбор
    groups_data[group]["salary_option"] = option
    # Сохраняем в БД
    conn = await db.db_pool.acquire()
    try:
        await conn.execute(
            "UPDATE group_financial_data SET salary_option=$1 WHERE group_key=$2",
            option, group
        )
    finally:
        await db.db_pool.release(conn)
    await state.clear()
    # Подтверждение
    await callback.message.edit_text(f"Опция зарплаты для {group} установлена: {option}.")
    await callback.answer("Сохранено", show_alert=True)
    # Отправляем результаты
    text = "\n".join(f"{emoji}: {value}" for emoji, value in salary_options[option].items())
    await callback.message.answer(f"Значения:\n{text}")
