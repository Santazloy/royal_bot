# handlers/money.py

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters.command import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import db
from config import is_user_admin
from constants.booking_const import groups_data
from handlers.language import get_user_language, get_message
from handlers.booking.reporting import update_group_message

logger = logging.getLogger(__name__)
money_router = Router()


class MoneyStates(StatesGroup):
    waiting_for_type = State()
    waiting_for_group_choice = State()
    waiting_for_operation = State()
    waiting_for_amount = State()


def _safe_get(lang: str, key: str, fallback: str, **kwargs) -> str:
    """
    Получить локализованное сообщение или вернуть fallback, если оно пустое
    """
    raw = get_message(lang, key, **kwargs)
    if not raw or not str(raw).strip():
        return fallback
    return raw


async def _money_init(entry, state: FSMContext):
    # Определяем источник (Message или CallbackQuery)
    if isinstance(entry, CallbackQuery):
        user_id = entry.from_user.id
        send_fn = entry.message.answer
        finish_fn = entry.answer
    else:
        user_id = entry.from_user.id
        send_fn = entry.answer
        finish_fn = None

    lang = await get_user_language(user_id)
    if not is_user_admin(user_id):
        text = _safe_get(lang, "no_permission", "У вас нет прав для выполнения этого действия.")
        if finish_fn:
            return await finish_fn(text, show_alert=True)
        return await send_fn(text)

    # Шаг 1: выбор типа операции
    btn1 = _safe_get(lang, "money_type_salary", "Зарплата")
    btn2 = _safe_get(lang, "money_type_cash", "Наличные")
    cancel = _safe_get(lang, "btn_cancel", "Отмена")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn1, callback_data="money_type_salary")],
        [InlineKeyboardButton(text=btn2, callback_data="money_type_cash")],
        [InlineKeyboardButton(text=cancel, callback_data="money_cancel")]
    ])
    text = _safe_get(lang, "money_choose_type", "Выберите тип изменения:")
    logger.debug(f"[money] show type menu: {text}")
    await send_fn(text, reply_markup=kb)
    await state.set_state(MoneyStates.waiting_for_type)
    if finish_fn:
        await finish_fn()


@money_router.message(Command("money"))
async def cmd_money_message(message: Message, state: FSMContext):
    await _money_init(message, state)


@money_router.callback_query(F.data == "money")
async def cmd_money_callback(cb: CallbackQuery, state: FSMContext):
    await _money_init(cb, state)


@money_router.callback_query(MoneyStates.waiting_for_type, F.data.startswith("money_type_"))
async def process_money_type(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    choice = cb.data.removeprefix("money_type_")  # 'salary' или 'cash'
    await state.update_data(type=choice)

    # Шаг 2: выбор группы
    cancel = _safe_get(lang, "btn_cancel", "Отмена")
    rows = [[InlineKeyboardButton(text=grp, callback_data=f"money_group_{grp}")] for grp in groups_data]
    rows.append([InlineKeyboardButton(text=cancel, callback_data="money_cancel")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    text = _safe_get(lang, "money_choose_group", "Выберите группу:")
    logger.debug(f"[money] choose group: {text}")
    await cb.message.edit_text(text, reply_markup=kb)
    await state.set_state(MoneyStates.waiting_for_group_choice)
    await cb.answer()


@money_router.callback_query(MoneyStates.waiting_for_group_choice, F.data.startswith("money_group_"))
async def process_money_group(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    group = cb.data.removeprefix("money_group_")
    if group not in groups_data:
        text = _safe_get(lang, "no_such_group", "Нет такой группы.")
        return await cb.answer(text, show_alert=True)
    await state.update_data(group=group)

    # Шаг 3: выбор операции + или -
    cancel = _safe_get(lang, "btn_cancel", "Отмена")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕", callback_data="money_op_add")],
        [InlineKeyboardButton(text="➖", callback_data="money_op_sub")],
        [InlineKeyboardButton(text=cancel, callback_data="money_cancel")]
    ])
    text = _safe_get(lang, "money_choose_op", f"Выберите операцию для группы {group}:")
    logger.debug(f"[money] choose op for {group}: {text}")
    await cb.message.edit_text(text, reply_markup=kb)
    await state.set_state(MoneyStates.waiting_for_operation)
    await cb.answer()


@money_router.callback_query(MoneyStates.waiting_for_operation, F.data.startswith("money_op_"))
async def process_money_op(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    op = cb.data.removeprefix("money_op_")  # 'add' или 'sub'
    await state.update_data(operation=op)
    data = await state.get_data()
    group = data.get("group")

    # Шаг 4: ввод суммы
    raw = get_message(lang, "money_amount_prompt", group=group)
    prompt = raw if raw and raw.strip() else (
        f"Введите сумму для {'добавления' if op=='add' else 'вычитания'} в группе {group}:"
    )
    logger.debug(f"[money] prompt amount: {prompt}")
    await cb.message.edit_text(prompt, parse_mode="HTML")
    await state.set_state(MoneyStates.waiting_for_amount)
    await cb.answer()


@money_router.message(StateFilter(MoneyStates.waiting_for_amount), F.text)
async def process_money_amount(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    group = data.get("group")
    op = data.get("operation")
    typ = data.get("type")  # 'salary' или 'cash'

    text = message.text.strip()
    if not text.isdigit():
        err = _safe_get(lang, "invalid_amount", "Неверная сумма.")
        return await message.answer(err)
    amount = int(text)

    # Текущее значение
    col = 'salary' if typ == 'salary' else 'cash'
    current = groups_data[group].get(col, 0)
    new_value = current + amount if op == 'add' else current - amount

    # Обновляем БД
    if db.db_pool:
        async with db.db_pool.acquire() as conn:
            query = f"UPDATE group_financial_data SET {col}=$1 WHERE group_key=$2"
            await conn.execute(query, new_value, group)
    groups_data[group][col] = new_value
    # Обновляем сообщение группы с новыми данными
    await update_group_message(message.bot, group)

    # Результат
    result_text = _safe_get(
        lang,
        "money_result",
        f"Группа {group}: новое значение {col} = {new_value}",
        group=group, type=typ, amount=amount, new=new_value
    )
    await message.answer(result_text, parse_mode="HTML")
    await state.clear()


@money_router.callback_query(F.data == "money_cancel")
async def money_cancel(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    try:
        await cb.message.delete()
    except:
        pass
    text = _safe_get(lang, "cancelled", "Отменено.")
    await cb.answer(text)
    await state.clear()


# Алиас для админ-меню
async def money_command(entry, state: FSMContext):
    """
    Запустить flow изменения зарплаты/наличных из админ-меню
    """
    await _money_init(entry, state)
