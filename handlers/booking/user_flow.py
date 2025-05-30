from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.filters.command import Command
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from handlers.booking.router import router, repo, data_mgr
from constants.booking_const import (
    GROUP_CHOICE_IMG, DAY_CHOICE_IMG,
    TIME_CHOICE_IMG, FINAL_BOOKED_IMG,
    groups_data
)
from handlers.language import get_user_language, get_message
from utils.time_utils import (
    generate_daily_time_slots as generate_time_slots,
    get_adjacent_time_slots,
    get_slot_datetime_shanghai
)
from handlers.booking.reporting import send_booking_report, update_group_message
from app_states import BookUserStates
from utils.bot_utils import safe_answer


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext):
    await state.clear()
    keys = data_mgr.list_group_keys()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=k, callback_data=f"bkgrp_{k}") for k in keys[i:i+3]]
            for i in range(0, len(keys), 3)
        ] + [
            [InlineKeyboardButton(text="« Назад", callback_data="bkmain_back")]
        ]
    )
    await safe_answer(message, photo=GROUP_CHOICE_IMG, reply_markup=kb)
    await state.set_state(BookUserStates.waiting_for_group)


@router.callback_query(StateFilter(BookUserStates.waiting_for_group), F.data.startswith("bkgrp_"))
async def user_select_group(cb: CallbackQuery, state: FSMContext):
    gk = cb.data.removeprefix("bkgrp_")
    if gk not in groups_data:
        return await safe_answer(cb, "Нет такой группы!", show_alert=True)
    await state.update_data(selected_group=gk)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сегодня", callback_data="bkday_Сегодня"),
            InlineKeyboardButton(text="Завтра",   callback_data="bkday_Завтра"),
        ],
        [
            InlineKeyboardButton(text="« Назад", callback_data="bkgroup_back")
        ]
    ])
    await safe_answer(cb, photo=DAY_CHOICE_IMG, reply_markup=kb)
    await cb.answer()
    await state.set_state(BookUserStates.waiting_for_day)


@router.callback_query(StateFilter(BookUserStates.waiting_for_day), F.data.startswith("bkday_"))
async def user_select_day(cb: CallbackQuery, state: FSMContext):
    day = cb.data.removeprefix("bkday_")
    await state.update_data(selected_day=day)
    await send_time_slots(cb, day, state)


@router.callback_query(StateFilter(BookUserStates.waiting_for_day), F.data == "bkgroup_back")
async def back_to_group_choice(cb: CallbackQuery, state: FSMContext):
    keys = data_mgr.list_group_keys()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=k, callback_data=f"bkgrp_{k}") for k in keys[i:i+3]]
            for i in range(0, len(keys), 3)
        ] + [
            [InlineKeyboardButton(text="« Назад", callback_data="bkmain_back")]
        ]
    )
    await safe_answer(cb, photo=GROUP_CHOICE_IMG, reply_markup=kb)
    await cb.answer()
    await state.set_state(BookUserStates.waiting_for_group)

@router.callback_query(StateFilter(BookUserStates.waiting_for_group), F.data == "bkmain_back")
async def back_to_main_menu(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()


async def send_time_slots(
    callback_query: CallbackQuery,
    selected_day: str,
    state: FSMContext
):
    data = await state.get_data()
    gk = data["selected_group"]
    ginfo = groups_data[gk]
    busy = set(ginfo["booked_slots"].get(selected_day, []))
    for bs in list(busy):
        busy.update(get_adjacent_time_slots(bs))
    busy |= ginfo["unavailable_slots"].get(selected_day, set())
    final = {'❌❌❌', '✅', '✅2', '✅✅', '✅✅✅'}
    for (d, t), st in ginfo["time_slot_statuses"].items():
        if d == selected_day and st in final:
            busy.add(t)

    builder = InlineKeyboardBuilder()
    for slot in generate_time_slots():
        if slot not in busy:
            builder.button(text=slot, callback_data=f"bkslot_{slot.replace(':','_')}")
    builder.button(text="« Назад", callback_data="bkday_back")
    builder.adjust(4)
    kb = builder.as_markup()

    lang = await get_user_language(callback_query.from_user.id)
    day_label = get_message(lang, 'today') if selected_day == 'Сегодня' else get_message(lang, 'tomorrow')
    text = f"🕒 <b>Выберите время на {day_label}</b>"

    await safe_answer(callback_query, photo=TIME_CHOICE_IMG, caption=text, reply_markup=kb, parse_mode="HTML")
    await callback_query.answer()
    await state.set_state(BookUserStates.waiting_for_time)


@router.callback_query(StateFilter(BookUserStates.waiting_for_time), F.data.startswith("bkslot_"))
async def user_select_time(cb: CallbackQuery, state: FSMContext):
    slot = cb.data.removeprefix("bkslot_").replace("_", ":")
    data = await state.get_data()
    gk, day, uid = data["selected_group"], data["selected_day"], cb.from_user.id

    data_mgr.book_slot(gk, day, slot, uid)
    dt = get_slot_datetime_shanghai(day, slot)
    await repo.add_booking(gk, day, slot, uid, dt)
    await send_booking_report(cb.bot, uid, gk, slot, day)
    await state.clear()

    lang = await get_user_language(uid)
    # Получаем имя пользователя для отображения
    username = None
    if hasattr(cb.from_user, "full_name") and cb.from_user.full_name:
        username = cb.from_user.full_name
    elif hasattr(cb.from_user, "username") and cb.from_user.username:
        username = cb.from_user.username
    elif hasattr(cb.from_user, "first_name"):
        username = cb.from_user.first_name
    else:
        username = f"User_{uid}"
    txt = f"🎉 <b>{username}, вы забронировали слот на {slot} ({day}) в группе {gk}</b>"
    await safe_answer(cb, photo=FINAL_BOOKED_IMG, caption=txt, parse_mode="HTML")

    await cb.answer()
    await update_group_message(cb.bot, gk)

@router.callback_query(StateFilter(BookUserStates.waiting_for_time), F.data == "bkday_back")
async def back_to_day_choice(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    gk = data["selected_group"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сегодня", callback_data="bkday_Сегодня"),
            InlineKeyboardButton(text="Завтра",   callback_data="bkday_Завтра"),
        ],
        [
            InlineKeyboardButton(text="« Назад", callback_data="bkgroup_back")
        ]
    ])
    await safe_answer(cb, photo=DAY_CHOICE_IMG, reply_markup=kb)
    await cb.answer()
    await state.set_state(BookUserStates.waiting_for_day)
