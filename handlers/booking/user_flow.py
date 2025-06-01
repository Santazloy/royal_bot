# handlers/booking/user_flow.py

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.filters.command import Command
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from constants.booking_const import (
    groups_data,
    GROUP_CHOICE_IMG,
    DAY_CHOICE_IMG,
    TIME_CHOICE_IMG,
    FINAL_BOOKED_IMG,
)
from handlers.language import get_user_language, get_message
from handlers.booking.reporting import send_booking_report, update_group_message
from handlers.booking.data_manager import BookingDataManager
from db_access.booking_repo import BookingRepo
from utils.time_utils import (
    generate_daily_time_slots as generate_time_slots,
    get_adjacent_time_slots,
    get_slot_datetime_shanghai,
)
from handlers.booking.data_manager import async_book_slot
from app_states import BookUserStates
from utils.bot_utils import safe_answer
import db

router = Router()
data_mgr = BookingDataManager(groups_data)
repo = BookingRepo(db.db_pool)


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext):
    """
    Точка входа: /book
    Показывает выбор группы.
    """
    await state.clear()
    keys = data_mgr.list_group_keys()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=k, callback_data=f"bkgrp_{k}") for k in keys[i : i + 3]]
            for i in range(0, len(keys), 3)
        ]
        + [[InlineKeyboardButton(text="« Назад", callback_data="bkmain_back")]]
    )
    await safe_answer(message, photo=GROUP_CHOICE_IMG, reply_markup=kb)
    await state.set_state(BookUserStates.waiting_for_group)


@router.callback_query(StateFilter(BookUserStates.waiting_for_group), F.data.startswith("bkgrp_"))
async def user_select_group(cb: CallbackQuery, state: FSMContext):
    """
    Шаг 1: пользователь выбрал группу.
    """
    gk = cb.data.removeprefix("bkgrp_")
    if gk not in groups_data:
        return await safe_answer(cb, "Нет такой группы!", show_alert=True)
    await state.update_data(selected_group=gk)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="bkday_Сегодня"),
                InlineKeyboardButton(text="Завтра", callback_data="bkday_Завтра"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="bkgroup_back")],
        ]
    )
    await safe_answer(cb, photo=DAY_CHOICE_IMG, reply_markup=kb)
    await cb.answer()
    await state.set_state(BookUserStates.waiting_for_day)


@router.callback_query(StateFilter(BookUserStates.waiting_for_day), F.data.startswith("bkday_"))
async def user_select_day(cb: CallbackQuery, state: FSMContext):
    """
    Шаг 2: пользователь выбрал день.
    """
    day = cb.data.removeprefix("bkday_")
    await state.update_data(selected_day=day)
    await send_time_slots(cb, day, state)


@router.callback_query(StateFilter(BookUserStates.waiting_for_day), F.data == "bkgroup_back")
async def back_to_group_choice(cb: CallbackQuery, state: FSMContext):
    """
    Вернуться к выбору группы (кнопка «Назад» на этапе выбора дня).
    """
    keys = data_mgr.list_group_keys()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=k, callback_data=f"bkgrp_{k}") for k in keys[i : i + 3]]
            for i in range(0, len(keys), 3)
        ]
        + [[InlineKeyboardButton(text="« Назад", callback_data="bkmain_back")]]
    )
    await safe_answer(cb, photo=GROUP_CHOICE_IMG, reply_markup=kb)
    await cb.answer()
    await state.set_state(BookUserStates.waiting_for_group)


@router.callback_query(StateFilter(BookUserStates.waiting_for_group), F.data == "bkmain_back")
async def back_to_main_menu(cb: CallbackQuery, state: FSMContext):
    """
    Сброс состояния и возврат из меню бронирования в общий чат.
    """
    await cb.answer()
    await state.clear()


async def send_time_slots(
    callback_query: CallbackQuery,
    selected_day: str,
    state: FSMContext,
):
    """
    Показывает выбор свободных слотов на указанный день (Сегодня/Завтра).
    Учёт занятых слотов и их соседей ±30 минут.
    """
    data = await state.get_data()
    gk = data["selected_group"]
    ginfo = groups_data[gk]

    # 1. Реально забронированные слоты
    busy: set[str] = set(ginfo["booked_slots"].get(selected_day, []))

    # 2. Соседние ±30 минут
    for booked_slot in list(busy):
        for adj in get_adjacent_time_slots(booked_slot):
            busy.add(adj)

    # 3. Формируем клавиатуру из всех слотов, которые НЕ в busy
    buttons = []
    row = []
    for slot in generate_time_slots():
        if slot not in busy:
            row.append(InlineKeyboardButton(text=slot, callback_data=f"bkslot_{slot.replace(':','_')}"))
            if len(row) == 4:
                buttons.append(row)
                row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="« Назад", callback_data="bkday_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    lang = await get_user_language(callback_query.from_user.id)
    day_label = get_message(lang, "today") if selected_day == "Сегодня" else get_message(lang, "tomorrow")
    text = f"🕒 <b>Выберите время на {day_label}</b>"

    await safe_answer(
        callback_query,
        photo=TIME_CHOICE_IMG,
        caption=text,
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback_query.answer()
    await state.set_state(BookUserStates.waiting_for_time)

@router.callback_query(StateFilter(BookUserStates.waiting_for_time), F.data.startswith("bkslot_"))
async def user_select_time(cb: CallbackQuery, state: FSMContext):
    """
    Шаг 3: пользователь выбрал слот.
    Сохраняем бронирование в памяти и БД, отправляем отчёт, обновляем состояние.
    """
    slot = cb.data.removeprefix("bkslot_").replace("_", ":")
    data = await state.get_data()
    gk, day, uid = data["selected_group"], data["selected_day"], cb.from_user.id

    # 1+2) Бронирование с ротацией эмодзи
    await async_book_slot(gk, day, slot, uid)

    # 3) Отправляем личный отчёт о брони
    await send_booking_report(cb.bot, uid, gk, slot, day)

    # 4) Сброс FSM и отправка финального сообщения
    await state.clear()
    lang = await get_user_language(uid)

    # Определяем имя пользователя
    username = None
    if getattr(cb.from_user, "full_name", None):
        username = cb.from_user.full_name
    elif getattr(cb.from_user, "username", None):
        username = cb.from_user.username
    else:
        username = f"User_{uid}"

    txt = f"🎉 <b>{username}, вы забронировали слот на {slot} ({day}) в группе {gk}</b>"
    await safe_answer(cb, photo=FINAL_BOOKED_IMG, caption=txt, parse_mode="HTML")

    await cb.answer()
    await update_group_message(cb.bot, gk)

@router.callback_query(StateFilter(BookUserStates.waiting_for_time), F.data == "bkday_back")
async def back_to_day_choice(cb: CallbackQuery, state: FSMContext):
    """
    Шаг 3.1: пользователю предложили выбрать время, он нажал «Назад» → возвращаем выбор дня.
    """
    data = await state.get_data()
    gk = data["selected_group"]
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="bkday_Сегодня"),
                InlineKeyboardButton(text="Завтра", callback_data="bkday_Завтра"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="bkgroup_back")],
        ]
    )
    await safe_answer(cb, photo=DAY_CHOICE_IMG, reply_markup=kb)
    await cb.answer()
    await state.set_state(BookUserStates.waiting_for_day)
