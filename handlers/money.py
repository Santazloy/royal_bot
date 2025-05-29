import logging

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.filters.command import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import db
from config import is_user_admin
from constants.booking_const import groups_data
from handlers.booking.reporting import update_group_message, send_financial_report
from handlers.language import get_user_language, get_message

logger = logging.getLogger(__name__)
money_router = Router()


class MoneyStates(StatesGroup):
    waiting_for_type = State()
    waiting_for_group_choice = State()
    waiting_for_operation = State()
    waiting_for_amount = State()


# Единое фото для всех шагов
MONEY_PHOTO = (
    "AgACAgUAAyEFAASVOrsCAAIDEGg23brrLiadZoeFJf_tyxhHjaDIAALjzDEbHWu4VZUmEXsg9M7tAQADAgADeQADNgQ"
)


async def _send_photo(
    entry: Message | CallbackQuery,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
):
    """
    Удаляет предыдущее бот-сообщение (если есть), потом отправляет фото с подписью.
    """
    # Определяем, у кого удалять и кому отвечать
    if isinstance(entry, CallbackQuery):
        target = entry.message
        await entry.answer()  # закрываем спиннер
    else:
        target = entry

    # Пробуем удалить старое
    try:
        await target.delete()
    except Exception:
        pass

    # Формируем параметры для answer_photo
    params: dict = {"photo": MONEY_PHOTO, "caption": caption}
    if reply_markup:
        params["reply_markup"] = reply_markup
    if parse_mode:
        params["parse_mode"] = parse_mode

    # Отправляем новое фото
    await target.answer_photo(**params)


@money_router.message(Command("money"))
async def money_command(message: Message, state: FSMContext):
    """Точка входа: /money"""
    await _money_init(message, state)


@money_router.callback_query(F.data == "money")
async def money_via_button(cb: CallbackQuery, state: FSMContext):
    """Точка входа через инлайн-кнопку “Money”"""
    await _money_init(cb, state)


async def _money_init(entry: Message | CallbackQuery, state: FSMContext):
    """
    Шаг 1: выбор типа (salary или cash).
    """
    user_id = entry.from_user.id
    lang = await get_user_language(user_id)

    if not is_user_admin(user_id):
        text = get_message(lang, "no_permission")
        if isinstance(entry, CallbackQuery):
            return await entry.answer(text, show_alert=True)
        return await entry.answer(text)

    btn_salary = get_message(lang, "btn_salary")
    btn_cash = get_message(lang, "btn_cash")
    btn_cancel = get_message(lang, "btn_cancel")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_salary, callback_data="money_type_salary")],
        [InlineKeyboardButton(text=btn_cash, callback_data="money_type_cash")],
        [InlineKeyboardButton(text=btn_cancel, callback_data="money_cancel")],
    ])

    text = get_message(lang, "money_choose_type")
    await _send_photo(entry, text, reply_markup=kb)
    await state.set_state(MoneyStates.waiting_for_type)


@money_router.callback_query(
    F.data.startswith("money_type_"),
    StateFilter(MoneyStates.waiting_for_type),
)
async def process_money_type(cb: CallbackQuery, state: FSMContext):
    """
    Шаг 2: пользователь выбрал salary или cash.
    """
    lang = await get_user_language(cb.from_user.id)
    typ = cb.data.removeprefix("money_type_")
    if typ not in ("salary", "cash"):
        return await cb.answer(get_message(lang, "invalid_data"), show_alert=True)

    await state.update_data(type=typ)

    btn_cancel = get_message(lang, "btn_cancel")
    rows = [[InlineKeyboardButton(text=grp, callback_data=f"money_group_{grp}")]
            for grp in groups_data]
    rows.append([InlineKeyboardButton(text=btn_cancel, callback_data="money_cancel")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    text = get_message(lang, "money_choose_group")
    await _send_photo(cb, text, reply_markup=kb)
    await state.set_state(MoneyStates.waiting_for_group_choice)


@money_router.callback_query(
    F.data.startswith("money_group_"),
    StateFilter(MoneyStates.waiting_for_group_choice),
)
async def process_money_group(cb: CallbackQuery, state: FSMContext):
    """
    Шаг 3: пользователь выбрал группу ⇒ показываем ➕/➖.
    """
    lang = await get_user_language(cb.from_user.id)
    group = cb.data.removeprefix("money_group_")
    if group not in groups_data:
        return await cb.answer(get_message(lang, "no_such_group"), show_alert=True)

    await state.update_data(group=group)

    btn_cancel = get_message(lang, "btn_cancel")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕", callback_data="money_op_add")],
        [InlineKeyboardButton(text="➖", callback_data="money_op_sub")],
        [InlineKeyboardButton(text=btn_cancel, callback_data="money_cancel")],
    ])

    text = get_message(lang, "money_choose_op", group=group)
    await _send_photo(cb, text, reply_markup=kb)
    await state.set_state(MoneyStates.waiting_for_operation)


@money_router.callback_query(
    F.data.startswith("money_op_"),
    StateFilter(MoneyStates.waiting_for_operation),
)
async def process_money_op(cb: CallbackQuery, state: FSMContext):
    """
    Шаг 4: запрашиваем сумму, отправляя фото + жирный emoji-префикс.
    """
    lang = await get_user_language(cb.from_user.id)
    op = cb.data.removeprefix("money_op_")
    await state.update_data(operation=op)

    data = await state.get_data()
    group = data["group"]

    prompt = get_message(lang, "money_amount_prompt", group=group)
    if not prompt.strip():
        prompt = f"Введите сумму для {'добавления' if op=='add' else 'вычитания'} в группе {group}:"

    caption = f"<b>💰 {prompt}</b>"
    await _send_photo(cb, caption, parse_mode="HTML")
    await state.set_state(MoneyStates.waiting_for_amount)


@money_router.message(
    F.text,
    StateFilter(MoneyStates.waiting_for_amount),
)
async def process_money_amount(message: Message, state: FSMContext):
    """
    Финальный шаг: обновляем БД, in-memory, перерисовываем group-сообщение, отправляем отчёт.
    """
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    group = data["group"]
    op = data["operation"]
    typ = data["type"]
    text_ = message.text.strip()

    if not text_.isdigit():
        return await message.answer(get_message(lang, "invalid_amount"))

    amount = int(text_)
    col = "salary" if typ == "salary" else "cash"
    current = groups_data[group].get(col, 0)
    new_val = current + (amount if op == "add" else -amount)

    if db.db_pool:
        async with db.db_pool.acquire() as conn:
            await conn.execute(
                f"UPDATE group_financial_data SET {col}=$1 WHERE group_key=$2",
                new_val, group
            )

    groups_data[group][col] = new_val

    # Перерисовываем group-сообщение
    await update_group_message(message.bot, group)
    # Отправляем общий финансовый отчёт
    await send_financial_report(message.bot)

    await state.clear()


@money_router.callback_query(F.data == "money_cancel")
async def money_cancel(cb: CallbackQuery, state: FSMContext):
    """
    Отмена: удаляем меню и сбрасываем state.
    """
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer(get_message(await get_user_language(cb.from_user.id), "cancelled"))
